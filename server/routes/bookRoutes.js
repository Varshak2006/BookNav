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

// Allowed fields for Book schema to prevent mass assignment
const ALLOWED_BOOK_FIELDS = [
  "title",
  "author",
  "category",
  "description",
  "keywords",
  "shelf",
  "rack",
  "location"
];

function sanitizeBookInput(body) {
  const sanitized = {};
  for (const field of ALLOWED_BOOK_FIELDS) {
    if (body[field] !== undefined) {
      sanitized[field] = typeof body[field] === "string" ? body[field].trim() : String(body[field]);
    }
  }
  return sanitized;
}

// In-memory rate limiting map for accept-correction feedback
const correctionRateLimitMap = new Map();
function checkCorrectionRateLimit(ip) {
  const now = Date.now();
  const windowMs = 15 * 60 * 1000; // 15 minutes
  const maxAttempts = 15;
  const record = correctionRateLimitMap.get(ip) || { count: 0, resetAt: now + windowMs };

  if (now > record.resetAt) {
    record.count = 1;
    record.resetAt = now + windowMs;
    correctionRateLimitMap.set(ip, record);
    return true;
  }

  if (record.count >= maxAttempts) {
    return false;
  }

  record.count++;
  correctionRateLimitMap.set(ip, record);
  return true;
}

// Bounded over-fetching helper to resolve FAISS vector results to actual MongoDB documents
async function resolveFaissResults(faissResults, requestedLimit = null) {
  if (!Array.isArray(faissResults) || faissResults.length === 0) {
    return [];
  }

  // Validate MongoDB ObjectIds strictly to prevent CastErrors or injection
  const validMongoIds = faissResults
    .map((r) => r.book_id)
    .filter((id) => id && typeof id === "string" && mongoose.Types.ObjectId.isValid(id));

  if (validMongoIds.length === 0) {
    return [];
  }

  // Query actual MongoDB records only
  const booksFromDb = await Book.find({ _id: { $in: validMongoIds } }).lean();
  const dbMap = new Map(booksFromDb.map((b) => [b._id.toString(), b]));

  const resolved = [];
  const seenIds = new Set();
  let currentRank = 1;

  for (const item of faissResults) {
    const idStr = String(item.book_id || "");
    if (!idStr || seenIds.has(idStr)) continue;
    seenIds.add(idStr);

    const bookDoc = dbMap.get(idStr);
    if (bookDoc) {
      resolved.push({
        ...bookDoc,
        similarity_score: item.score,
        rank: currentRank++
      });

      if (requestedLimit && resolved.length >= requestedLimit) {
        break;
      }
    }
    // Stale or deleted records in FAISS are safely omitted (no placeholder objects)
  }

  return resolved;
}

// Safe asynchronous synchronization with retry capability
async function syncFaissAdd(book, maxRetries = 2) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await faissService.addBook(book);
      return;
    } catch (err) {
      console.warn(`FAISS async index error on book add (attempt ${attempt}/${maxRetries}):`, err.message);
      if (attempt < maxRetries) await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }
}

async function syncFaissUpdate(book, maxRetries = 2) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await faissService.updateBook(book);
      return;
    } catch (err) {
      console.warn(`FAISS async index error on book update (attempt ${attempt}/${maxRetries}):`, err.message);
      if (attempt < maxRetries) await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }
}

async function syncFaissDelete(bookId, maxRetries = 2) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await faissService.deleteBook(bookId);
      return;
    } catch (err) {
      console.warn(`FAISS async index error on book delete (attempt ${attempt}/${maxRetries}):`, err.message);
      if (attempt < maxRetries) await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }
}

// Sanitize query filter values to prevent operator injection
function extractSafeString(value) {
  if (value === undefined || value === null) return undefined;
  if (typeof value === "string") return value.trim();
  return undefined;
}

// Add a new book (Admin only)
router.post("/", protectAdmin, async (req, res) => {
  try {
    const bookData = sanitizeBookInput(req.body);

    if (!bookData.title || !bookData.author || !bookData.category || !bookData.shelf || !bookData.rack) {
      return res.status(400).json({
        message: "Missing required fields: title, author, category, shelf, and rack are mandatory."
      });
    }

    const book = await Book.create(bookData);

    // Sync to FAISS vector index asynchronously with retries
    syncFaissAdd(book).catch((err) => {
      console.error("FAISS sync failed after retries:", err.message);
    });

    // Sync to LACS vocabulary asynchronously
    lacsAddBook({
      title: book.title,
      author: book.author,
      category: book.category,
      keywords: book.keywords || "",
      description: book.description || ""
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
    const books = await Book.find().lean();
    res.status(200).json(books);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch books",
      error: "Database error occurred while fetching books"
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
    res.status(500).json({ status: "error", error: "Health check failed" });
  }
});

// Vector & LACS Comprehensive Status & Health Diagnostics endpoint (Admin only)
router.get("/vector-status", protectAdmin, async (req, res) => {
  try {
    const totalBooksInDb = await Book.countDocuments();
    const mongoStatus = {
      connected: mongoose.connection.readyState === 1,
      readyState: mongoose.connection.readyState,
      total_books_in_db: totalBooksInDb
    };

    let faissStatus = null;
    try {
      faissStatus = await faissService.getStatus();
    } catch (fErr) {
      faissStatus = {
        initialized: false,
        ready: false,
        readiness_state: "ERROR",
        readiness_reason: fErr.message,
        error: fErr.message
      };
    }

    let lacsStatus = null;
    try {
      lacsStatus = await lacsCheckHealth();
    } catch (lErr) {
      lacsStatus = { status: "unhealthy", ready: false, error: lErr.message };
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
      error: "Internal error retrieving diagnostics"
    });
  }
});

// Synchronization Diagnostics endpoint (Admin only)
router.get("/sync-diagnostics", protectAdmin, async (req, res) => {
  try {
    const totalMongo = await Book.countDocuments();
    let faissInfo = null;
    try {
      faissInfo = await faissService.getStatus();
    } catch (e) {
      faissInfo = { error: e.message, vectors_indexed: null };
    }

    let lacsInfo = null;
    try {
      lacsInfo = await lacsCheckHealth();
    } catch (e) {
      lacsInfo = { error: e.message, vocabulary_size: null };
    }

    const vectorsCount = faissInfo ? faissInfo.vectors_indexed : null;
    const isFaissInSync = vectorsCount !== null && vectorsCount === totalMongo;

    res.status(200).json({
      synchronized: isFaissInSync,
      mongodb_count: totalMongo,
      faiss_vector_count: vectorsCount,
      faiss_in_sync: isFaissInSync,
      faiss_ready: Boolean(faissInfo && faissInfo.ready),
      lacs_vocabulary_size: lacsInfo ? lacsInfo.vocabulary_size : null,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({ message: "Failed to run synchronization diagnostics", error: "Internal error" });
  }
});

// Full Reconciliation endpoint (Admin only)
router.post("/reconcile", protectAdmin, async (req, res) => {
  try {
    const allBooks = await Book.find().lean();
    console.log(`Starting index reconciliation for ${allBooks.length} books...`);

    // 1. Reconcile LACS vocabulary
    const lacsResult = await syncVocabulary(allBooks);

    // 2. Rebuild / reconcile FAISS index safely
    const faissResult = await faissService.rebuildIndex(allBooks, false);

    res.status(200).json({
      message: "Reconciliation complete",
      total_books: allBooks.length,
      lacs: lacsResult,
      faiss: faissResult
    });
  } catch (error) {
    console.error("Reconciliation error:", error);
    res.status(500).json({
      message: "Reconciliation failed",
      error: "Internal error during reconciliation: " + error.message
    });
  }
});

// Synchronize LACS vocabulary with all MongoDB books (Admin only)
router.post("/sync-lacs", protectAdmin, async (req, res) => {
  try {
    const books = await Book.find().select("title author category keywords description").lean();
    const result = await syncVocabulary(books);
    res.status(200).json({ message: "Vocabulary synchronized with MongoDB", result });
  } catch (error) {
    res.status(500).json({ message: "Synchronization failed", error: "Internal error during synchronization" });
  }
});

// Accept user correction feedback with rate limiting and strict validation
router.post("/accept-correction", async (req, res) => {
  try {
    const clientIp = req.ip || req.connection.remoteAddress || "unknown";
    if (!checkCorrectionRateLimit(clientIp)) {
      return res.status(429).json({
        message: "Too many feedback submissions. Please try again later."
      });
    }

    const { wrong, correct } = req.body;
    if (typeof wrong !== "string" || typeof correct !== "string") {
      return res.status(400).json({ message: "wrong and correct terms must be strings" });
    }

    const cleanWrong = wrong.trim().toLowerCase();
    const cleanCorrect = correct.trim().toLowerCase();

    // Strict validation
    const termRegex = /^[a-z0-9\s'-]+$/;
    if (!cleanWrong || !cleanCorrect) {
      return res.status(400).json({ message: "wrong and correct terms cannot be empty" });
    }
    if (cleanWrong.length < 2 || cleanWrong.length > 50 || cleanCorrect.length < 2 || cleanCorrect.length > 50) {
      return res.status(400).json({ message: "term length must be between 2 and 50 characters" });
    }
    if (!termRegex.test(cleanWrong) || !termRegex.test(cleanCorrect)) {
      return res.status(400).json({ message: "terms contain invalid characters" });
    }
    if (cleanWrong === cleanCorrect) {
      return res.status(400).json({ message: "wrong and correct terms cannot be identical" });
    }

    await acceptCorrection(cleanWrong, cleanCorrect);
    res.status(200).json({ message: "Correction accepted and stored in history" });
  } catch (error) {
    res.status(500).json({ message: "Failed to record correction", error: "Internal error recording correction" });
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

    // Strictly validate filter parameters to strings only (prevent operator injection)
    const filters = {};
    const safeAuthor = extractSafeString(author);
    const safeCategory = extractSafeString(category);
    const safeShelf = extractSafeString(shelf);
    const safeRack = extractSafeString(rack);
    const safeLocation = extractSafeString(location);
    const safeKeywords = extractSafeString(keywords);

    if (safeAuthor) filters.author = safeAuthor;
    if (safeCategory) filters.category = safeCategory;
    if (safeShelf) filters.shelf = safeShelf;
    if (safeRack) filters.rack = safeRack;
    if (safeLocation) filters.location = safeLocation;
    if (safeKeywords) filters.keywords = safeKeywords;

    // Step 1: LACS Spell Correction (unless bypassed)
    let correction = null;
    let effectiveQuery = searchTerm;
    let lacsStatus = bypassCorrection ? "bypassed" : "no_correction";

    if (!bypassCorrection) {
      try {
        correction = await correctQuery(searchTerm);
        if (correction && correction.correctionApplied && correction.correctedQuery) {
          effectiveQuery = correction.correctedQuery;
          lacsStatus = "corrected";
        } else if (correction && correction.suggestion) {
          lacsStatus = "suggested";
        } else {
          lacsStatus = "no_correction";
        }
      } catch (lacsErr) {
        console.warn("LACS correction note:", lacsErr.message);
        lacsStatus = "unavailable";
        effectiveQuery = searchTerm;
      }
    }

    // Step 2: FAISS Vector Search with bounded over-fetching
    const candidateLimit = Math.min(100, Math.max(limit, Math.ceil(limit * 1.5)));
    let searchResult;
    try {
      searchResult = await faissService.search(effectiveQuery, candidateLimit, filters);
    } catch (faissErr) {
      console.error("FAISS search error:", faissErr.message);
      const isNotReady = faissErr.code === "INDEX_NOT_READY" || (faissErr.message && faissErr.message.includes("not ready"));
      return res.status(503).json({
        message: isNotReady
          ? "Semantic search is currently not ready or undergoing initialization."
          : "Semantic search service encountered an error.",
        error_code: isNotReady ? "INDEX_NOT_READY" : "FAISS_ERROR",
        readiness_state: faissService.readinessState
      });
    }

    // Step 3: Resolve MongoDB Book Records (bounded to requested limit)
    const enrichedResults = await resolveFaissResults(searchResult.results || [], limit);

    res.status(200).json({
      query: searchTerm,
      effectiveQuery: effectiveQuery,
      searchMode: "semantic",
      lacsStatus,
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
      message: "Semantic vector search failed",
      error: "Internal server error during semantic vector search"
    });
  }
});

// Standard search endpoint (LACS -> Keyword Filter -> FAISS Semantic fallback/hybrid)
router.get("/search", async (req, res) => {
  try {
    const { q, mode, correct, top_k, author, category, shelf, rack, location, keywords } = req.query;

    if (!q || typeof q !== "string" || q.trim() === "") {
      return res.status(400).json({
        message: "Search query is required and cannot be empty"
      });
    }

    const searchTerm = q.trim();
    const limit = top_k ? Math.max(1, Math.min(parseInt(top_k, 10) || 10, 100)) : 10;
    const bypassCorrection = correct === "false" || correct === false || mode === "exact";

    // Strictly validate filter parameters to strings only
    const filters = {};
    const safeAuthor = extractSafeString(author);
    const safeCategory = extractSafeString(category);
    const safeShelf = extractSafeString(shelf);
    const safeRack = extractSafeString(rack);
    const safeLocation = extractSafeString(location);
    const safeKeywords = extractSafeString(keywords);

    if (safeAuthor) filters.author = safeAuthor;
    if (safeCategory) filters.category = safeCategory;
    if (safeShelf) filters.shelf = safeShelf;
    if (safeRack) filters.rack = safeRack;
    if (safeLocation) filters.location = safeLocation;
    if (safeKeywords) filters.keywords = safeKeywords;

    // STEP 1: Pass query through LACS Spell Correction (unless bypassed)
    let correction = null;
    let effectiveQuery = searchTerm;
    let lacsStatus = bypassCorrection ? "bypassed" : "no_correction";

    if (!bypassCorrection) {
      try {
        correction = await correctQuery(searchTerm);
        if (correction && correction.correctionApplied && correction.correctedQuery) {
          effectiveQuery = correction.correctedQuery;
          lacsStatus = "corrected";
        } else if (correction && correction.suggestion) {
          lacsStatus = "suggested";
        } else {
          lacsStatus = "no_correction";
        }
      } catch (lacsErr) {
        console.warn("LACS correction note (falling back to original query):", lacsErr.message);
        lacsStatus = "unavailable";
        effectiveQuery = searchTerm;
      }
    }

    // Helper to send standardized response
    const sendResponse = (books, searchMode, fallbackInfo = {}) => {
      return res.status(200).json({
        query: searchTerm,
        effectiveQuery,
        searchMode: searchMode || "keyword",
        lacsStatus,
        correctionApplied: correction ? correction.correctionApplied : false,
        correctedQuery: correction ? correction.correctedQuery : null,
        suggestion: correction ? correction.suggestion : null,
        confidence: correction ? correction.confidence : null,
        confidenceLevel: correction ? correction.confidenceLevel : null,
        ...fallbackInfo,
        results: books
      });
    };

    // If explicit semantic mode requested
    if (mode === "semantic") {
      try {
        const candidateLimit = Math.min(100, Math.max(limit, Math.ceil(limit * 1.5)));
        const searchResult = await faissService.search(effectiveQuery, candidateLimit, filters);
        const resolved = await resolveFaissResults(searchResult.results || [], limit);
        return sendResponse(resolved, "semantic");
      } catch (faissErr) {
        console.error("Explicit FAISS search failed:", faissErr.message);
        const isNotReady = faissErr.code === "INDEX_NOT_READY" || (faissErr.message && faissErr.message.includes("not ready"));
        return res.status(503).json({
          message: isNotReady
            ? "Semantic search is currently not ready."
            : "Semantic search service encountered an error.",
          error_code: isNotReady ? "INDEX_NOT_READY" : "FAISS_UNAVAILABLE"
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
    let fallbackInfo = {};

    if (books.length === 0) {
      try {
        const candidateLimit = Math.min(100, Math.max(limit, Math.ceil(limit * 1.5)));
        const searchResult = await faissService.search(effectiveQuery, candidateLimit, filters);
        if (searchResult && Array.isArray(searchResult.results) && searchResult.results.length > 0) {
          books = await resolveFaissResults(searchResult.results, limit);
          if (books.length > 0) {
            searchMode = "semantic_fallback";
            fallbackInfo = { fallbackAttempted: true, fallbackStatus: "success" };
          } else {
            fallbackInfo = { fallbackAttempted: true, fallbackStatus: "no_matches" };
          }
        } else {
          fallbackInfo = { fallbackAttempted: true, fallbackStatus: "no_matches" };
        }
      } catch (faissErr) {
        console.warn("FAISS fallback query note:", faissErr.message);
        fallbackInfo = {
          fallbackAttempted: true,
          fallbackStatus: "failed",
          fallbackError: "Semantic search fallback was unavailable"
        };
      }
    }

    return sendResponse(books, searchMode, fallbackInfo);
  } catch (error) {
    console.error("Book search error:", error);
    return res.status(500).json({
      message: "Book search failed",
      error: "Internal server error during search"
    });
  }
});

// Get book by ID
router.get("/:id", async (req, res) => {
  try {
    if (!mongoose.Types.ObjectId.isValid(req.params.id)) {
      return res.status(400).json({
        message: "Invalid book ID format"
      });
    }

    const book = await Book.findById(req.params.id).lean();

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    res.status(200).json(book);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch book",
      error: "Database error occurred"
    });
  }
});

// Update a book (Admin only)
router.put("/:id", protectAdmin, async (req, res) => {
  try {
    if (!mongoose.Types.ObjectId.isValid(req.params.id)) {
      return res.status(400).json({
        message: "Invalid book ID format"
      });
    }

    const oldBook = await Book.findById(req.params.id);
    if (!oldBook) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    const updateData = sanitizeBookInput(req.body);

    const book = await Book.findByIdAndUpdate(
      req.params.id,
      updateData,
      { new: true, runValidators: true }
    );

    // Detect if searchable text changed
    const searchableChanged =
      oldBook.title !== book.title ||
      oldBook.author !== book.author ||
      oldBook.category !== book.category ||
      oldBook.keywords !== book.keywords ||
      oldBook.description !== book.description;

    // Sync updated book to FAISS vector index
    syncFaissUpdate(book).catch((err) => {
      console.error("FAISS async index error on book update:", err.message);
    });

    // Sync to LACS vocabulary
    lacsUpdateBook(
      {
        title: oldBook.title,
        author: oldBook.author,
        category: oldBook.category,
        keywords: oldBook.keywords || "",
        description: oldBook.description || ""
      },
      {
        title: book.title,
        author: book.author,
        category: book.category,
        keywords: book.keywords || "",
        description: book.description || ""
      }
    ).catch((err) => {
      console.error("LACS async update error on book update:", err.message);
    });

    res.status(200).json({
      message: "Book updated successfully",
      searchable_text_changed: searchableChanged,
      book
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to update book",
      error: error.message
    });
  }
});

// Delete a book (Admin only)
router.delete("/:id", protectAdmin, async (req, res) => {
  try {
    if (!mongoose.Types.ObjectId.isValid(req.params.id)) {
      return res.status(400).json({
        message: "Invalid book ID format"
      });
    }

    const book = await Book.findByIdAndDelete(req.params.id);

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    // Sync deletion to FAISS vector index asynchronously
    syncFaissDelete(req.params.id).catch((err) => {
      console.error("FAISS async delete error:", err.message);
    });

    // Sync deletion to LACS vocabulary asynchronously
    lacsDeleteBook({
      title: book.title,
      author: book.author,
      category: book.category,
      keywords: book.keywords || "",
      description: book.description || ""
    }).catch((err) => {
      console.error("LACS async delete error on book delete:", err.message);
    });

    res.status(200).json({
      message: "Book deleted successfully"
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to delete book",
      error: "Database error occurred while deleting book"
    });
  }
});

module.exports = router;