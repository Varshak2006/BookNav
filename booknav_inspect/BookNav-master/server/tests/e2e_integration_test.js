const mongoose = require("mongoose");
const path = require("path");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });
const connectDB = require("../config/db");
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
  const results = await Book.find(filter);

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
  await connectDB();

  // Ensure vocabulary is synchronized with MongoDB
  const allBooks = await Book.find().select("title author category keywords description").lean();
  console.log(`Starting E2E Tests with ${allBooks.length} MongoDB books...`);
  await syncVocabulary(allBooks);

  const testCases = [
    // 1. Harry Potter misspellings
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

    // 2. Other existing book-title misspellings
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

    // 3. Author-name misspellings
    {
      category: "Author-name misspellings",
      query: "ravindranath tagor",
      expectedAuthorPart: "Rabindranath Tagore"
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

    // 4. Category-related queries
    {
      category: "Category queries",
      query: "fantazy",
      expectedCategoryPart: "Fantasy"
    },
    {
      category: "Category queries",
      query: "programing",
      expectedCategoryPart: "Programming"
    },

    // 5. Multiple misspelled words
    {
      category: "Multiple misspelled words",
      query: "machne larning",
      expectedTitlePart: "Machine Learning"
    },
    {
      category: "Multiple misspelled words",
      query: "computr netwroks",
      expectedTitlePart: "Computer Networks"
    },

    // 6. Correctly spelled titles
    {
      category: "Correctly spelled titles",
      query: "Machine Learning",
      expectedTitlePart: "Machine Learning"
    },
    {
      category: "Correctly spelled titles",
      query: "Clean Code",
      expectedTitlePart: "Clean Code"
    },

    // 7. Valid rare words
    {
      category: "Valid rare words",
      query: "Gitanjali",
      expectedTitlePart: "Gitanjali"
    },
    {
      category: "Valid rare words",
      query: "Sedgewick",
      expectedAuthorPart: "Sedgewick"
    },

    // 8. Unknown words
    {
      category: "Unknown words",
      query: "xyzqwerty",
      expectedCount: 0
    },

    // 9. Empty query
    {
      category: "Empty queries",
      query: "",
      expectedCount: 0
    }
  ];

  const report = [];

  for (const tc of testCases) {
    const outcome = await executeSearch(tc.query);
    let matched = false;

    if (tc.expectedCount !== undefined) {
      matched = outcome.mongoCount === tc.expectedCount;
    } else if (tc.expectedTitlePart) {
      matched = outcome.results.some((r) => r.title.toLowerCase().includes(tc.expectedTitlePart.toLowerCase()));
    } else if (tc.expectedAuthorPart) {
      matched = outcome.results.some((r) => r.author.toLowerCase().includes(tc.expectedAuthorPart.toLowerCase()));
    } else if (tc.expectedCategoryPart) {
      matched = outcome.mongoCount > 0;
    }

    report.push({
      scenario: tc.category,
      originalQuery: tc.query,
      decision: outcome.decision,
      correctedQuery: outcome.correctedQuery,
      mongoCount: outcome.mongoCount,
      expectedFound: matched,
      matchedTitles: outcome.results.map((r) => r.title)
    });
  }

  // 10. Dynamic Book Lifecycle (Add -> Update -> Delete)
  console.log("\nTesting Dynamic Lifecycle: Add -> Correct -> Update -> Delete...");

  // ADD
  const newBookDoc = await Book.create({
    title: "The Hobbit",
    author: "J. R. R. Tolkien",
    category: "Fantasy",
    keywords: "middle earth hobbit bilbo",
    description: "Fantasy novel about Bilbo Baggins.",
    shelf: "Shelf-F",
    rack: "Rack-4",
    location: "Main Library Hall"
  });

  await addBook({
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  });

  const addSearch = await executeSearch("tolkin");
  const addFound = addSearch.results.some((r) => r.title === "The Hobbit");
  report.push({
    scenario: "Dynamic Book: Add",
    originalQuery: "tolkin",
    decision: addSearch.decision,
    correctedQuery: addSearch.correctedQuery,
    mongoCount: addSearch.mongoCount,
    expectedFound: addFound,
    matchedTitles: addSearch.results.map((r) => r.title)
  });

  // UPDATE
  const oldBookData = {
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  };

  newBookDoc.title = "The Fellowship of the Ring";
  newBookDoc.keywords = "lord of the rings frodo sauron";
  await newBookDoc.save();

  await updateBook(oldBookData, {
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  });

  // Test Medium Confidence Suggestion
  const mediumTest = await correctQuery("fellowshp");
  report.push({
    scenario: "Medium Confidence: Did you mean?",
    originalQuery: "fellowshp",
    decision: mediumTest.confidenceLevel,
    correctedQuery: mediumTest.suggestion,
    mongoCount: 0,
    expectedFound: mediumTest.confidenceLevel === "medium" && mediumTest.suggestion === "fellowship",
    matchedTitles: []
  });

  // Test Dynamic Update with context (High Confidence Auto-correction)
  const updateSearch = await executeSearch("the fellowshp");
  const updateFound = updateSearch.results.some((r) => r.title === "The Fellowship of the Ring");
  report.push({
    scenario: "Dynamic Book: Update",
    originalQuery: "the fellowshp",
    decision: updateSearch.decision,
    correctedQuery: updateSearch.correctedQuery,
    mongoCount: updateSearch.mongoCount,
    expectedFound: updateFound,
    matchedTitles: updateSearch.results.map((r) => r.title)
  });

  // DELETE
  await Book.findByIdAndDelete(newBookDoc._id);
  await deleteBook({
    title: newBookDoc.title,
    author: newBookDoc.author,
    category: newBookDoc.category,
    keywords: newBookDoc.keywords,
    description: newBookDoc.description
  });

  const deleteSearch = await executeSearch("the fellowshp");
  const deleteFound = deleteSearch.mongoCount === 0;
  report.push({
    scenario: "Dynamic Book: Delete",
    originalQuery: "the fellowshp",
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

  stopWorker();
  await mongoose.disconnect();
  process.exit(allPassed ? 0 : 1);
}

runTests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
