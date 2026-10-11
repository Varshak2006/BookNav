const express = require("express");
const Book = require("../models/Book");
const protectAdmin = require("../middleware/authMiddleware");
const {
  correctQuery,
  addBook,
  updateBook,
  deleteBook,
  acceptCorrection,
  syncVocabulary
} = require("../services/lacsService");
const {
  semanticSearch,
  addBook: faissAddBook,
  removeBook: faissRemoveBook,
  rebuildIndex: faissRebuildIndex,
  getStatus: faissGetStatus,
  buildIndex: faissBuildIndex
} = require("../services/faissService");
const { buildSearchFilter } = require("../services/bookSearch");
const router = express.Router();

async function searchBooks(searchTerm) {
  return Book.find(buildSearchFilter(searchTerm));
}

// Add a new book
router.post("/", protectAdmin, async (req, res) => {
  try {
    const book = await Book.create(req.body);

    // Keep LACS vocabulary synchronized with MongoDB
    try {
      await addBook({
        title: book.title,
        author: book.author,
        category: book.category,
        keywords: book.keywords,
        description: book.description
      });
    } catch (lacsError) {
      console.error("LACS vocabulary update error (non-fatal):", lacsError.message);
    }

    // Keep FAISS index synchronized with MongoDB
    try {
      await faissAddBook({
        _id: book._id,
        title: book.title,
        author: book.author,
        category: book.category,
        keywords: book.keywords,
        description: book.description,
        shelf: book.shelf,
        rack: book.rack,
        location: book.location
      });
    } catch (faissError) {
      console.error("FAISS index update error (non-fatal):", faissError.message);
    }

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

// Search books with LACS spell correction
router.get("/search", async (req, res) => {
  try {
    const { q, forceOriginal } = req.query;

    if (!q || q.trim() === "") {
      return res.status(400).json({
        message: "Search query is required"
      });
    }

    // Limit input query length to 300 characters to prevent excessive processing
    const searchTerm = q.trim().slice(0, 300);
    const shouldForceOriginal = forceOriginal === "true" || forceOriginal === "1";

    let correction = {
      query: searchTerm,
      correctedQuery: null,
      correctionApplied: false,
      suggestion: null,
      confidence: null,
      confidenceLevel: "low"
    };

    try {
      correction = await correctQuery(searchTerm);
    } catch (error) {
      console.error("LACS unavailable, searching original query:", error.message);
    }

    const applied = !shouldForceOriginal && Boolean(correction.correctionApplied);
    const effectiveQuery = applied && correction.correctedQuery
      ? correction.correctedQuery
      : searchTerm;

    const books = await searchBooks(effectiveQuery);

    res.status(200).json({
      query: searchTerm,
      correctedQuery: applied ? correction.correctedQuery : null,
      correctionApplied: applied,
      originalForced: shouldForceOriginal,
      suggestion: shouldForceOriginal
        ? (correction.correctedQuery || correction.suggestion)
        : correction.suggestion,
      confidence: correction.confidence,
      confidenceLevel: correction.confidenceLevel,
      results: books
    });
  } catch (error) {
    res.status(500).json({
      message: "Book search failed",
      error: error.message
    });
  }
});

// Semantic search using FAISS vector similarity
router.get("/semantic-search", async (req, res) => {
  try {
    const { q, top_k, author, category, keywords } = req.query;

    if (!q || q.trim() === "") {
      return res.status(400).json({
        message: "Search query is required"
      });
    }

    const searchTerm = q.trim().slice(0, 300);
    const topK = Math.max(1, Math.min(100, Number(top_k) || 10));

    // Build metadata filters from query parameters
    const filters = {};
    if (author) filters.author = String(author).trim();
    if (category) filters.category = String(category).trim();
    if (keywords) filters.keywords = String(keywords).trim();

    // Apply LACS spell correction to the query first
    let effectiveQuery = searchTerm;
    let correction = null;

    try {
      correction = await correctQuery(searchTerm);
      if (correction.correctionApplied && correction.correctedQuery) {
        effectiveQuery = correction.correctedQuery;
      }
    } catch (lacsError) {
      console.error("LACS unavailable for semantic search (non-fatal):", lacsError.message);
    }

    // Perform FAISS semantic search
    let searchResult;
    try {
      searchResult = await semanticSearch(effectiveQuery, topK, filters);
    } catch (faissError) {
      console.error("FAISS search failed:", faissError.message);
      return res.status(503).json({
        message: "Semantic search is temporarily unavailable",
        error: "FAISS index may not be built yet. Run: npm run faiss:build"
      });
    }

    // Enrich results with full book data from MongoDB
    const enrichedResults = [];
    for (const result of (searchResult.results || [])) {
      try {
        const book = await Book.findById(result.book_id).lean();
        if (book) {
          enrichedResults.push({
            ...book,
            similarity_score: result.similarity_score,
            rank: result.rank
          });
        } else {
          // Book was deleted from MongoDB but still in FAISS
          enrichedResults.push({
            _id: result.book_id,
            title: result.title || "Unknown",
            author: result.author || "Unknown",
            category: result.category || "",
            similarity_score: result.similarity_score,
            rank: result.rank,
            _stale: true
          });
        }
      } catch (dbError) {
        console.error(`Failed to fetch book ${result.book_id}:`, dbError.message);
      }
    }

    res.status(200).json({
      query: searchTerm,
      effectiveQuery: effectiveQuery,
      correctionApplied: correction ? correction.correctionApplied : false,
      correctedQuery: correction ? correction.correctedQuery : null,
      suggestion: correction ? correction.suggestion : null,
      filters_applied: searchResult.filters_applied || {},
      result_count: enrichedResults.length,
      total_candidates: searchResult.total_candidates,
      search_time_ms: searchResult.search_time_ms,
      distance_metric: searchResult.distance_metric,
      results: enrichedResults
    });
  } catch (error) {
    res.status(500).json({
      message: "Semantic search failed",
      error: error.message
    });
  }
});

// FAISS index status
router.get("/faiss-status", async (req, res) => {
  try {
    const status = await faissGetStatus();
    res.status(200).json(status);
  } catch (error) {
    res.status(503).json({
      message: "FAISS service unavailable",
      error: error.message
    });
  }
});

// Rebuild FAISS index from MongoDB (admin only)
router.post("/faiss-rebuild", protectAdmin, async (req, res) => {
  try {
    const books = await Book.find().lean();
    const result = await faissRebuildIndex(books);
    res.status(200).json({ message: "FAISS index rebuilt", result });
  } catch (error) {
    res.status(500).json({
      message: "FAISS index rebuild failed",
      error: error.message
    });
  }
});

// Accept user correction feedback
router.post("/accept-correction", async (req, res) => {
  try {
    const { wrong, correct } = req.body;
    if (!wrong || !correct) {
      return res.status(400).json({ message: "wrong and correct terms are required" });
    }
    await acceptCorrection(String(wrong), String(correct));
    res.status(200).json({ message: "Correction accepted and stored in history" });
  } catch (error) {
    res.status(500).json({ message: "Failed to record correction", error: error.message });
  }
});

// Synchronize LACS vocabulary with all MongoDB books
router.post("/sync-lacs", protectAdmin, async (req, res) => {
  try {
    const books = await Book.find().select("title author category keywords description").lean();
    const result = await syncVocabulary(books);
    res.status(200).json({ message: "Vocabulary synchronized with MongoDB", result });
  } catch (error) {
    res.status(500).json({ message: "Synchronization failed", error: error.message });
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

    // Keep LACS vocabulary synchronized with MongoDB
    try {
      await updateBook(
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
      );
    } catch (lacsError) {
      console.error("LACS vocabulary update error (non-fatal):", lacsError.message);
    }

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

    // Keep LACS vocabulary synchronized with MongoDB
    try {
      await deleteBook({
        title: book.title,
        author: book.author,
        category: book.category,
        keywords: book.keywords,
        description: book.description
      });
    } catch (lacsError) {
      console.error("LACS vocabulary delete error (non-fatal):", lacsError.message);
    }

    // Keep FAISS index synchronized
    try {
      await faissRemoveBook(book._id);
    } catch (faissError) {
      console.error("FAISS index delete error (non-fatal):", faissError.message);
    }

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
