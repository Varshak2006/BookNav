/**
 * Integration Tests for BookNav FAISS Service & REST Endpoints.
 *
 * Verifies:
 * 1. IPC communication between Node.js and Python faiss_bridge.
 * 2. Semantic search execution, scoring, and ranking.
 * 3. Library metadata filtering (category, author, non-matching).
 * 4. Error handling for empty or malformed queries.
 */

const assert = require("assert");
const faissService = require("../services/faissService");

async function runIntegrationTests() {
  console.log("=================================================");
  console.log("       FAISS SERVICE NODE.JS INTEGRATION TESTS   ");
  console.log("=================================================\n");

  let passed = 0;
  let total = 0;

  async function test(name, fn) {
    total++;
    try {
      await fn();
      console.log(`[PASS] ${name}`);
      passed++;
    } catch (err) {
      console.error(`[FAIL] ${name}: ${err.message}`);
    }
  }

  // 1. Status Test
  await test("1. FAISS Bridge status and initialization", async () => {
    const status = await faissService.getStatus();
    assert.strictEqual(status.initialized, true, "Index should be initialized");
    assert(status.vectors_indexed > 0, "Index should contain indexed vectors");
    assert.strictEqual(status.dimension, 384, "Embedding dimension should be 384");
    assert.strictEqual(status.metric, "IP", "Metric should be IP");
    console.log(`       -> Vectors indexed: ${status.vectors_indexed}, Dim: ${status.dimension}`);
  });

  // 2. Semantic Search Test
  await test("2. Semantic search query retrieval and ranking", async () => {
    const res = await faissService.search("artificial intelligence and machine learning", 5);
    assert.strictEqual(typeof res.results_count, "number");
    assert(res.results.length > 0, "Should return results for valid semantic query");

    const top = res.results[0];
    assert(top.book_id, "Result must have book_id");
    assert(top.title, "Result must have title");
    assert.strictEqual(top.rank, 1, "Top item must have rank 1");
    assert.strictEqual(top.metric, "cosine_similarity", "Metric should be cosine_similarity");
    assert(top.score >= -1.0 && top.score <= 1.0, "Cosine score must be in [-1, 1]");

    console.log(`       -> Top result: "${top.title}" by ${top.author} (Score: ${top.score})`);
  });

  // 3. Category Filter Test
  await test("3. Metadata filtering: category filter", async () => {
    const res = await faissService.search("algorithms and computer science", 5, {
      category: "Algorithms"
    });
    assert(res.results.length > 0, "Should return books matching category Algorithms");
    for (const b of res.results) {
      assert(
        b.category.toLowerCase().includes("algorithms"),
        `Category '${b.category}' must contain 'algorithms'`
      );
    }
    console.log(`       -> Retrieved ${res.results.length} books in category 'Algorithms'`);
  });

  // 4. Author Filter Test
  await test("4. Metadata filtering: author filter", async () => {
    const res = await faissService.search("textbook", 5, {
      author: "Goodfellow"
    });
    assert(res.results.length > 0, "Should find book by Goodfellow");
    assert(
      res.results[0].author.toLowerCase().includes("goodfellow"),
      "Author must match Goodfellow"
    );
    console.log(`       -> Retrieved: "${res.results[0].title}" by ${res.results[0].author}`);
  });

  // 5. Non-Matching Filter Handling
  await test("5. Non-matching filter handles empty results gracefully", async () => {
    const res = await faissService.search("computer science", 5, {
      category: "NonExistentCategoryXYZ"
    });
    assert.strictEqual(res.results.length, 0, "Non-existent category should return 0 results");
    assert.strictEqual(res.results_count, 0);
  });

  // 6. Empty Query Error Handling
  await test("6. Reject empty search query", async () => {
    let errorCaught = false;
    try {
      await faissService.search("", 5);
    } catch (err) {
      errorCaught = true;
      assert(err.message.includes("empty"), "Error message should mention empty");
    }
    assert.strictEqual(errorCaught, true, "Empty query must throw an error");
  });

  // 7. Enriched Status and Health Checks
  await test("7. Enriched status reports counts, health, and generation", async () => {
    const status = await faissService.getStatus();
    assert.strictEqual(typeof status.counts_match, "boolean", "Status should report counts_match");
    assert.strictEqual(typeof status.healthy, "boolean", "Status should report healthy boolean");
    assert(Array.isArray(status.health_issues), "Status should include health_issues array");
    assert.strictEqual(typeof status.mapping_count, "number", "Status should report mapping_count");
    console.log(`       -> Health: ${status.healthy ? 'HEALTHY' : 'UNHEALTHY'}, counts_match: ${status.counts_match}`);
  });

  // 8. Unsupported Filter Field Rejection
  await test("8. Reject search with unsupported filter keys", async () => {
    let errorCaught = false;
    try {
      await faissService.search("artificial intelligence", 5, {
        unsupported_field_xyz: "some_value"
      });
    } catch (err) {
      errorCaught = true;
      assert(err.message.includes("Unsupported filter field"), "Error message should mention unsupported filter field");
    }
    assert.strictEqual(errorCaught, true, "Unsupported filter field must be rejected");
  });

  // 9. Book Update Integration
  await test("9. Update book in FAISS index", async () => {
    // Perform update on a test book definition
    const updateResult = await faissService.updateBook({
      _id: "test_integration_book_999",
      title: "Advanced Quantum Machine Learning",
      author: "Test Author",
      category: "Quantum",
      description: "Quantum algorithms for tensor network embeddings",
      shelf: "Q1",
      rack: "R9"
    });
    assert.strictEqual(updateResult.success, true, "Update book should return success: true");
    assert.strictEqual(updateResult.book_id, "test_integration_book_999");

    // Clean up test vector
    const delResult = await faissService.deleteBook("test_integration_book_999");
    assert.strictEqual(delResult.success, true, "Cleanup delete should succeed");
  });

  console.log("\n=================================================");
  console.log(`Test Results: ${passed}/${total} passed (${Math.round((passed / total) * 100)}%)`);
  console.log("=================================================");

  faissService.stopWorker();
  process.exit(passed === total ? 0 : 1);
}

runIntegrationTests().catch((err) => {
  console.error("Test execution failed:", err);
  faissService.stopWorker();
  process.exit(1);
});
