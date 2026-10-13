/**
 * End-to-End Integration Tests for BookNav Search Pipeline.
 *
 * Runs completely isolated in dedicated test database (booknav_test)
 * and temporary LACS history file to ensure production data is never touched.
 */

const mongoose = require("mongoose");
const path = require("path");
const fs = require("fs");
const os = require("os");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });

// Use dedicated isolated test database and temporary history file
const TEST_MONGO_URI = process.env.MONGO_URI_TEST || "mongodb://localhost:27017/booknav_test";
const TEST_HISTORY_PATH = path.join(os.tmpdir(), `booknav_test_history_${Date.now()}.csv`);
fs.writeFileSync(TEST_HISTORY_PATH, "timestamp,wrong_term,correct_term,count,frequency\n", "utf-8");

process.env.MONGO_URI = TEST_MONGO_URI;
process.env.LACS_HISTORY_PATH = TEST_HISTORY_PATH;
process.env.NODE_ENV = "test";

const { connectDB } = require("../config/db");
const Book = require("../models/Book");
const { buildSearchFilter } = require("../services/bookSearch");
const {
  correctQuery,
  addBook,
  updateBook,
  deleteBook,
  syncVocabulary,
  stopWorker
} = require("../services/lacsService");

// Standard seeded books for E2E tests
const SEED_BOOKS = [
  {
    title: "Harry Potter and the Philosopher's Stone",
    author: "J. K. Rowling",
    category: "Fantasy",
    description: "A young wizard discovers his magical heritage.",
    keywords: "wizard, magic, hogwarts",
    shelf: "A1",
    rack: "R1"
  },
  {
    title: "Clean Code: A Handbook of Agile Software Craftsmanship",
    author: "Robert C. Martin",
    category: "Programming",
    description: "Best practices for writing clean and maintainable software.",
    keywords: "software, agile, coding",
    shelf: "B2",
    rack: "R2"
  },
  {
    title: "Operating System Concepts",
    author: "Abraham Silberschatz; Peter B. Galvin; Greg Gagne",
    category: "Operating Systems",
    description: "Foundational textbook on modern operating systems and kernel design.",
    keywords: "kernel, processes, memory, os",
    shelf: "C3",
    rack: "R3"
  },
  {
    title: "Introduction to Algorithms",
    author: "Thomas H. Cormen; Charles E. Leiserson; Ronald L. Rivest; Clifford Stein",
    category: "Algorithms",
    description: "Comprehensive textbook on algorithms and data structures.",
    keywords: "algorithms, sorting, graphs, dynamic programming",
    shelf: "D4",
    rack: "R4"
  },
  {
    title: "Deep Learning",
    author: "Ian Goodfellow; Yoshua Bengio; Aaron Courville",
    category: "Artificial Intelligence",
    description: "An introduction to deep neural networks and machine learning.",
    keywords: "deep learning, neural networks, machine learning, ai",
    shelf: "E5",
    rack: "R5"
  },
  {
    title: "Gitanjali",
    author: "Rabindranath Tagore",
    category: "Poetry",
    description: "A collection of devotional poetry by the Nobel laureate.",
    keywords: "poetry, literature, nobel",
    shelf: "F6",
    rack: "R6"
  }
];

async function executeSearch(query) {
  const trimmed = (query || "").trim();
  if (!trimmed) {
    return {
      originalQuery: query,
      candidates: [],
      decision: "low",
      correctedQuery: null,
      mongoCount: 0,
      results: [],
      expectedFound: true
    };
  }

  const correction = await correctQuery(trimmed);
  const applied = Boolean(correction.correctionApplied);
  const effectiveQuery = applied && correction.correctedQuery ? correction.correctedQuery : trimmed;

  const filter = buildSearchFilter(effectiveQuery);
  const results = await Book.find(filter).lean();

  return {
    originalQuery: trimmed,
    candidates: correction.suggestion ? [correction.suggestion] : (correction.correctedQuery ? [correction.correctedQuery] : []),
    decision: correction.confidenceLevel,
    correctedQuery: applied ? correction.correctedQuery : null,
    mongoCount: results.length,
    results: results.map((b) => ({ id: b._id, title: b.title, author: b.author }))
  };
}

async function runTests() {
  console.log("=================================================");
  console.log("       BOOKNAV END-TO-END SEARCH PIPELINE TESTS  ");
  console.log(`       Isolated DB: ${TEST_MONGO_URI}`);
  console.log("=================================================\n");

  await connectDB(TEST_MONGO_URI);

  // Clear test DB and seed fresh test documents
  await Book.deleteMany({});
  await Book.insertMany(SEED_BOOKS);

  const allBooks = await Book.find().select("title author category keywords description").lean();
  console.log(`Seeded test database with ${allBooks.length} sample books.`);
  await syncVocabulary(allBooks);

  const testCases = [
    {
      category: "Harry Potter misspellings",
      query: "harry poater",
      expectedTitlePart: "Harry Potter"
    },
    {
      category: "Harry Potter misspellings",
      query: "harry pottr",
      expectedTitlePart: "Harry Potter"
    },
    {
      category: "Other existing book titles",
      query: "clean coed",
      expectedTitlePart: "Clean Code"
    },
    {
      category: "Other existing book titles",
      query: "operatng system",
      expectedTitlePart: "Operating System Concepts"
    },
    {
      category: "Other existing book titles",
      query: "algorithems",
      expectedTitlePart: "Algorithms"
    },
    {
      category: "Author-name misspellings",
      query: "goodfelow",
      expectedAuthorPart: "Ian Goodfellow"
    },
    {
      category: "Author-name misspellings",
      query: "silbershatz",
      expectedAuthorPart: "Abraham Silberschatz"
    },
    {
      category: "Correct title preservation",
      query: "Deep Learning",
      expectedTitlePart: "Deep Learning"
    },
    {
      category: "Unknown query handling",
      query: "quantum teleportation textbook",
      expectedNoMatch: true
    }
  ];

  const report = [];

  for (const tc of testCases) {
    const outcome = await executeSearch(tc.query);
    let expectedFound = false;

    if (tc.expectedNoMatch) {
      expectedFound = outcome.mongoCount === 0;
    } else if (tc.expectedTitlePart) {
      expectedFound = outcome.results.some((r) => r.title.includes(tc.expectedTitlePart));
    } else if (tc.expectedAuthorPart) {
      expectedFound = outcome.results.some((r) => r.author.includes(tc.expectedAuthorPart));
    }

    report.push({
      scenario: tc.category,
      originalQuery: tc.query,
      decision: outcome.decision,
      correctedQuery: outcome.correctedQuery,
      mongoCount: outcome.mongoCount,
      expectedFound,
      matchedTitles: outcome.results.map((r) => r.title)
    });
  }

  // Dynamic Add, Update, Delete test
  console.log("\nTesting dynamic book vocabulary updates...");

  // 1. Add Dynamic Book
  const newBookDoc = await Book.create({
    title: "The Fellowship of the Ring",
    author: "J. R. R. Tolkien",
    category: "Fantasy",
    description: "The first part of The Lord of the Rings.",
    keywords: "fellowship, ring, hobbit",
    shelf: "F1",
    rack: "R1"
  });

  await addBook({
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  });

  const addSearch = await executeSearch("the fellowshp of the ring");
  const addFound = addSearch.results.some((r) => r.title === "The Fellowship of the Ring");
  report.push({
    scenario: "Dynamic Book: Add",
    originalQuery: "the fellowshp of the ring",
    decision: addSearch.decision,
    correctedQuery: addSearch.correctedQuery,
    mongoCount: addSearch.mongoCount,
    expectedFound: addFound,
    matchedTitles: addSearch.results.map((r) => r.title)
  });

  // 2. Delete Dynamic Book
  await Book.findByIdAndDelete(newBookDoc._id);
  await deleteBook({
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  });

  const deleteSearch = await executeSearch("the fellowshp of the ring");
  const deleteFound = deleteSearch.mongoCount === 0;
  report.push({
    scenario: "Dynamic Book: Delete",
    originalQuery: "the fellowshp of the ring",
    decision: deleteSearch.decision,
    correctedQuery: deleteSearch.correctedQuery,
    mongoCount: deleteSearch.mongoCount,
    expectedFound: deleteFound,
    matchedTitles: deleteSearch.results.map((r) => r.title)
  });

  console.log("\n=================== E2E TEST RESULTS ===================");
  console.table(
    report.map((r) => ({
      Scenario: r.scenario,
      Query: r.originalQuery,
      Decision: r.decision,
      Corrected: r.correctedQuery || "-",
      Results: r.mongoCount,
      ExpectedBookFound: r.expectedFound ? "YES" : "NO"
    }))
  );

  const allPassed = report.every((r) => r.expectedFound);
  console.log(`\nOverall Status: ${allPassed ? "ALL TESTS PASSED (100%)" : "SOME TESTS FAILED"}`);

  // Cleanup: drop isolated test database and temporary history file
  try {
    await mongoose.connection.db.dropDatabase();
    await mongoose.disconnect();
    stopWorker();
    if (fs.existsSync(TEST_HISTORY_PATH)) {
      fs.unlinkSync(TEST_HISTORY_PATH);
    }
  } catch (e) {
    console.error("Cleanup error:", e.message);
  }

  process.exit(allPassed ? 0 : 1);
}

runTests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
