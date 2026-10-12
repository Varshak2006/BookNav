const express = require("express");
const mongoose = require("mongoose");
const Book = require("../models/Book");
const protectAdmin = require("../middleware/authMiddleware");
const faissService = require("../services/faissService");
const {
  correctQuery,
  addBook: lacsAddBook,
  updateBook: lacsUpdateBook,
  deleteBook: lacsDeleteBook,
  syncVocabulary,
  acceptCorrection,
  checkHealth: lacsCheckHealth
} = require("../services/lacsService");
const { buildSearchFilter } = require("../services/bookSearch");
const router = express.Router();

// Helper to resolve FAISS vector results to MongoDB documents preserving order
async function resolveFaissResults(faissResults) {
  if (!Array.isArray(faissResults) || faissResults.length === 0) {
    return [];
  }
  // Validate MongoDB ObjectIds to prevent Mongoose CastErrors or unmapped junk
  const validMongoIds = faissResults
    .map((r) => r.book_id)
    .filter((id) => id && mongoose.Types.ObjectId.isValid(String(id)));

  if (validMongoIds.length === 0) {
    return [];
  }

  const booksFromDb = await Book.find({ _id: { $in: validMongoIds } }).lean();
  const dbMap = new Map(booksFromDb.map((b) => [b._id.toString(), b]));

  const resolved = [];
  const seenIds = new Set();
  for (const item of faissResults) {
    const idStr = String(item.book_id || "");
    if (!idStr || seenIds.has(idStr)) continue;
    seenIds.add(idStr);

    const bookDoc = dbMap.get(idStr);
    if (bookDoc) {
      resolved.push({
        ...bookDoc,
        similarity_score: item.score,
        rank: item.rank
      });
    }
    // If book is deleted in MongoDB, do not fabricate placeholder records
  }
  return resolved;
}

// Add a new book
router.post("/", protectAdmin, async (req, res) => {
  try {
    const book = await Book.create(req.body);

    // Sync to FAISS vector index asynchronously
    faissService.addBook(book).catch((err) => {
      console.error("FAISS async index error on book add:", err.message);
    });

    // Sync to LACS vocabulary asynchronously
    lacsAddBook({
      title: book.title,
      author: book.author,
      category: book.category,
      keywords: book.keywords,
      description: book.description
    }).catch((err) => {
      console.error("LACS async vocabulary error on book add:", err.message);
    });

    res.status(201).json({
      message: "Book added successfully",
      book
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to add book",
      error: error.message
    });
  }
});

// Get all books
router.get("/", async (req, res) => {
  try {
    const books = await Book.find();
    res.status(200).json(books);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch books",
      error: error.message
    });
  }
});

// Public minimal health check endpoint
router.get("/health", async (req, res) => {
  try {
    const mongoConnected = mongoose.connection.readyState === 1;
    res.status(200).json({
      status: mongoConnected ? "ok" : "degraded",
      mongodb_connected: mongoConnected,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({ status: "error", error: error.message });
  }
});

// Vector & LACS Comprehensive Status & Health Diagnostics endpoint (Admin only)
router.get("/vector-status", protectAdmin, async (req, res) => {
  try {
    const mongoStatus = {
      connected: mongoose.connection.readyState === 1,
      readyState: mongoose.connection.readyState,
      total_books_in_db: await Book.countDocuments()
    };
    const faissStatus = await faissService.getStatus();
    let lacsStatus = null;
    try {
      lacsStatus = await lacsCheckHealth();
    } catch (lErr) {
      lacsStatus = { status: "unhealthy", error: lErr.message };
    }

    res.status(200).json({
      mongodb: mongoStatus,
      faiss: faissStatus,
      lacs: lacsStatus,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to retrieve vector or system diagnostics",
      error: error.message
    });
  }
});

// Synchronize LACS vocabulary with all MongoDB books (admin only)
router.post("/sync-lacs", protectAdmin, async (req, res) => {
  try {
    const books = await Book.find().select("title author category keywords description").lean();
    const result = await syncVocabulary(books);
    res.status(200).json({ message: "Vocabulary synchronized with MongoDB", result });
  } catch (error) {
    res.status(500).json({ message: "Synchronization failed", error: error.message });
  }
});

// Accept user correction feedback with strict input validation
router.post("/accept-correction", async (req, res) => {
  try {
    const { wrong, correct } = req.body;
    if (typeof wrong !== "string" || typeof correct !== "string") {
      return res.status(400).json({ message: "wrong and correct terms must be strings" });
    }
    const cleanWrong = wrong.trim().replace(/[\r\n\t]/g, " ");
    const cleanCorrect = correct.trim().replace(/[\r\n\t]/g, " ");
    if (!cleanWrong || !cleanCorrect) {
      return res.status(400).json({ message: "wrong and correct terms cannot be empty" });
    }
    if (cleanWrong.length > 100 || cleanCorrect.length > 100) {
      return res.status(400).json({ message: "term length cannot exceed 100 characters" });
    }
    await acceptCorrection(cleanWrong, cleanCorrect);
    res.status(200).json({ message: "Correction accepted and stored in history" });
  } catch (error) {
    res.status(500).json({ message: "Failed to record correction", error: error.message });
  }
});

// Semantic Vector Search endpoint with LACS spelling pre-processing
router.get("/semantic-search", async (req, res) => {
  try {
    const { q, top_k, author, category, shelf, rack, location, keywords, correct, mode } = req.query;

    if (!q || typeof q !== "string" || q.trim() === "") {
      return res.status(400).json({
        message: "Search query 'q' is required for semantic search"
      });
    }

    const searchTerm = q.trim();
    const limit = top_k ? Math.max(1, Math.min(parseInt(top_k, 10) || 10, 100)) : 10;
    const bypassCorrection = correct === "false" || correct === false || mode === "exact";

    const filters = {};
    if (author) filters.author = author;
    if (category) filters.category = category;
    if (shelf) filters.shelf = shelf;
    if (rack) filters.rack = rack;
    if (location) filters.location = location;
    if (keywords) filters.keywords = keywords;

    // Step 1: LACS Spell Correction (unless bypassed)
    let correction = null;
    let effectiveQuery = searchTerm;
    if (!bypassCorrection) {
      try {
        correction = await correctQuery(searchTerm);
        if (correction && correction.correctionApplied && correction.correctedQuery) {
          effectiveQuery = correction.correctedQuery;
        }
      } catch (lacsErr) {
        console.warn("LACS correction note:", lacsErr.message);
      }
    }

    // Step 2: FAISS Vector Search
    let searchResult;
    try {
      searchResult = await faissService.search(effectiveQuery, limit, filters);
    } catch (faissErr) {
      console.error("FAISS search error:", faissErr.message);
      const isNotReady = faissErr.message.includes("not ready") ||
        faissErr.message.includes("SERVICE_NOT_READY") ||
        faissErr.message.includes("INDEX_NOT_READY");
      return res.status(503).json({
        errorCode: isNotReady ? "INDEX_NOT_READY" : "FAISS_UNAVAILABLE",
        message: isNotReady
          ? "Vector search index is not ready or requires rebuild"
          : "Semantic search service encountered an error"
      });
    }

    // Step 3: Resolve MongoDB Book Records
    const enrichedResults = await resolveFaissResults(searchResult.results || []);

    res.status(200).json({
      query: searchTerm,
      effectiveQuery: effectiveQuery,
      searchMode: "semantic",
      correctionApplied: correction ? correction.correctionApplied : false,
      correctedQuery: correction ? correction.correctedQuery : null,
      suggestion: correction ? correction.suggestion : null,
      confidence: correction ? correction.confidence : null,
      confidenceLevel: correction ? correction.confidenceLevel : null,
      filters_applied: searchResult.filters_applied || {},
      results_count: enrichedResults.length,
      total_indexed: searchResult.total_indexed,
      metric: searchResult.metric,
      results: enrichedResults
    });
  } catch (error) {
    console.error("Semantic search error:", error);
    res.status(500).json({
      errorCode: "SEARCH_FAILED",
      message: "Semantic vector search failed"
    });
  }
});

// Standard search endpoint (LACS -> Keyword Filter -> FAISS Semantic fallback/hybrid)
router.get("/search", async (req, res) => {
  try {
    const { q, mode, correct, top_k, author, category, shelf, rack, location } = req.query;

    if (!q || typeof q !== "string" || q.trim() === "") {
      return res.status(400).json({
        errorCode: "INVALID_QUERY",
        message: "Search query is required and cannot be empty"
      });
    }

    const searchTerm = q.trim();
    const limit = top_k ? Math.max(1, Math.min(parseInt(top_k, 10) || 10, 100)) : 10;
    const bypassCorrection = correct === "false" || correct === false || mode === "exact";

    const filters = {};
    if (author) filters.author = author;
    if (category) filters.category = category;
    if (shelf) filters.shelf = shelf;
    if (rack) filters.rack = rack;
    if (location) filters.location = location;

    // STEP 1: Pass query through LACS Spell Correction (unless bypassed)
    let correction = null;
    let effectiveQuery = searchTerm;
    if (!bypassCorrection) {
      try {
        correction = await correctQuery(searchTerm);
        if (correction && correction.correctionApplied && correction.correctedQuery) {
          effectiveQuery = correction.correctedQuery;
        }
      } catch (lacsErr) {
        console.warn("LACS correction note (falling back to original query):", lacsErr.message);
      }
    }

    // Helper to send standardized response
    const sendResponse = (books, searchMode, fallbackError = null) => {
      const resp = {
        query: searchTerm,
        effectiveQuery,
        searchMode: searchMode || "keyword",
        correctionApplied: correction ? correction.correctionApplied : false,
        correctedQuery: correction ? correction.correctedQuery : null,
        suggestion: correction ? correction.suggestion : null,
        confidence: correction ? correction.confidence : null,
        confidenceLevel: correction ? correction.confidenceLevel : null,
        results: books
      };
      if (fallbackError) {
        resp.fallbackError = fallbackError;
      }
      return res.status(200).json(resp);
    };

    // If explicit semantic mode requested
    if (mode === "semantic") {
      try {
        const searchResult = await faissService.search(effectiveQuery, limit, filters);
        const resolved = await resolveFaissResults(searchResult.results || []);
        return sendResponse(resolved, "semantic");
      } catch (faissErr) {
        console.error("Explicit FAISS search failed:", faissErr.message);
        const isNotReady = faissErr.message.includes("not ready") ||
          faissErr.message.includes("SERVICE_NOT_READY") ||
          faissErr.message.includes("INDEX_NOT_READY");
        return res.status(503).json({
          errorCode: isNotReady ? "INDEX_NOT_READY" : "FAISS_UNAVAILABLE",
          message: isNotReady
            ? "Vector search index is not ready or requires rebuild"
            : "Semantic search service encountered an error"
        });
      }
    }

    // STEP 2: Keyword search with effective query
    const keywordFilter = buildSearchFilter(effectiveQuery);
    if (Object.keys(filters).length > 0) {
      Object.assign(keywordFilter, filters);
    }
    let books = await Book.find(keywordFilter).limit(limit).lean();

    // STEP 3: If keyword search produces 0 results, fall back to FAISS semantic search
    let searchMode = "keyword";
    let fallbackError = null;
    if (books.length === 0 && mode !== "keyword") {
      try {
        const searchResult = await faissService.search(effectiveQuery, limit, filters);
        if (searchResult && Array.isArray(searchResult.results) && searchResult.results.length > 0) {
          books = await resolveFaissResults(searchResult.results);
          if (books.length > 0) {
            searchMode = "semantic_fallback";
          }
        }
      } catch (faissErr) {
        console.warn("FAISS fallback query note:", faissErr.message);
        fallbackError = "semantic_fallback_unavailable";
      }
    }

    return sendResponse(books, searchMode, fallbackError);
  } catch (error) {
    console.error("Book search error:", error);
    return res.status(500).json({
      errorCode: "SEARCH_FAILED",
      message: "Book search failed"
    });
  }
});

router.get("/:id", async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    res.status(200).json(book);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch book",
      error: error.message
    });
  }
});

// Update a book
router.put("/:id", protectAdmin, async (req, res) => {
  try {
    const oldBook = await Book.findById(req.params.id);
    if (!oldBook) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    const book = await Book.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    // Sync updated book to FAISS vector index
    faissService.updateBook(book).catch((err) => {
      console.error("FAISS async index error on book update:", err.message);
    });

    // Sync to LACS vocabulary
    lacsUpdateBook(
      {
        title: oldBook.title,
        author: oldBook.author,
        category: oldBook.category,
        keywords: oldBook.keywords,
        description: oldBook.description
      },
      {
        title: book.title,
        author: book.author,
        category: book.category,
        keywords: book.keywords,
        description: book.description
      }
    ).catch((err) => {
      console.error("LACS async update error on book update:", err.message);
    });

    res.status(200).json({
      message: "Book updated successfully",
      book
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to update book",
      error: error.message
    });
  }
});

// Delete a book
router.delete("/:id", protectAdmin, async (req, res) => {
  try {
    const book = await Book.findByIdAndDelete(req.params.id);

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    // Sync deletion to FAISS vector index asynchronously
    faissService.deleteBook(req.params.id).catch((err) => {
      console.error("FAISS async delete error:", err.message);
    });

    // Sync deletion to LACS vocabulary asynchronously
    lacsDeleteBook({
      title: book.title,
      author: book.author,
      category: book.category,
      keywords: book.keywords,
      description: book.description
    }).catch((err) => {
      console.error("LACS async delete error on book delete:", err.message);
    });

    res.status(200).json({
      message: "Book deleted successfully"
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to delete book",
      error: error.message
    });
  }
});

module.exports = router;