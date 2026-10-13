/**
 * Regression Tests for Original-Query Bypass & LACS Correction Toggle.
 *
 * Verifies:
 * 1. Default search executes LACS correction on misspelled queries.
 * 2. Bypass parameter (correct=false or mode=exact) explicitly bypasses LACS.
 * 3. Bypassed search does NOT reuse the corrected query.
 * 4. effectiveQuery equals original query when bypassed.
 * 5. lacsStatus reports "bypassed" and correctionApplied is false.
 */

const assert = require("assert");
const http = require("http");
const mongoose = require("mongoose");
const path = require("path");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });

const TEST_MONGO_URI = process.env.MONGO_URI_TEST || "mongodb://localhost:27017/booknav_test";
process.env.MONGO_URI = TEST_MONGO_URI;
process.env.NODE_ENV = "test";
process.env.PORT = "5098";

const { connectDB } = require("../config/db");
const { app } = require("../server");
const Book = require("../models/Book");
const { syncVocabulary, stopWorker } = require("../services/lacsService");

let server = null;
const BASE_URL = "http://localhost:5098";

function request(method, path) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const reqOptions = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search
    };

    const req = http.request(reqOptions, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        let json = null;
        try {
          json = JSON.parse(data);
        } catch (e) {
          json = data;
        }
        resolve({ status: res.statusCode, body: json });
      });
    });
    req.on("error", reject);
    req.end();
  });
}

async function runBypassTests() {
  console.log("=================================================");
  console.log("       ORIGINAL QUERY BYPASS REGRESSION TESTS    ");
  console.log("=================================================\n");

  await connectDB(TEST_MONGO_URI);
  await Book.deleteMany({});

  // Seed sample books
  await Book.create([
    {
      title: "Harry Potter and the Goblet of Fire",
      author: "J. K. Rowling",
      category: "Fantasy",
      keywords: "wizard, magic",
      shelf: "A1",
      rack: "R1"
    },
    {
      title: "Operating System Concepts",
      author: "Silberschatz",
      category: "OS",
      keywords: "kernel, processes",
      shelf: "B2",
      rack: "R2"
    }
  ]);

  const allBooks = await Book.find().lean();
  await syncVocabulary(allBooks);

  server = await new Promise((resolve) => {
    const s = app.listen(5098, () => resolve(s));
  });

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

  try {
    // 1. Misspelled query with default auto-correction
    await test("1. Misspelled query triggers LACS auto-correction by default", async () => {
      const res = await request("GET", "/api/books/search?q=harry+poater");
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.query, "harry poater");
      assert.strictEqual(res.body.correctionApplied, true);
      assert.strictEqual(res.body.effectiveQuery, "harry potter");
      assert.strictEqual(res.body.lacsStatus, "corrected");
      assert.ok(res.body.results.length > 0, "Should find Harry Potter book");
      assert.ok(res.body.results[0].title.includes("Harry Potter"));
    });

    // 2. Misspelled query with correct=false explicitly bypasses LACS
    await test("2. correct=false explicitly bypasses LACS and preserves original query", async () => {
      const res = await request("GET", "/api/books/search?q=harry+poater&correct=false");
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.query, "harry poater");
      assert.strictEqual(res.body.correctionApplied, false);
      assert.strictEqual(res.body.effectiveQuery, "harry poater");
      assert.strictEqual(res.body.correctedQuery, null);
      assert.strictEqual(res.body.lacsStatus, "bypassed");
    });

    // 3. Misspelled query with mode=exact explicitly bypasses LACS
    await test("3. mode=exact explicitly bypasses LACS correction", async () => {
      const res = await request("GET", "/api/books/search?q=harry+poater&mode=exact");
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.query, "harry poater");
      assert.strictEqual(res.body.correctionApplied, false);
      assert.strictEqual(res.body.effectiveQuery, "harry poater");
      assert.strictEqual(res.body.lacsStatus, "bypassed");
    });

    // 4. Semantic search endpoint also honors correct=false bypass
    await test("4. Semantic search endpoint honors correct=false bypass", async () => {
      const res = await request("GET", "/api/books/semantic-search?q=harry+poater&correct=false");
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.query, "harry poater");
      assert.strictEqual(res.body.effectiveQuery, "harry poater");
      assert.strictEqual(res.body.correctionApplied, false);
      assert.strictEqual(res.body.lacsStatus, "bypassed");
    });

    console.log(`\nOriginal Query Bypass Tests: ${passed}/${total} passed (${Math.round((passed / total) * 100)}%)`);
  } finally {
    if (server) server.close();
    stopWorker();
    await mongoose.connection.db.dropDatabase();
    await mongoose.disconnect();
  }

  process.exit(passed === total ? 0 : 1);
}

runBypassTests().catch((err) => {
  console.error("Test execution failed:", err);
  if (server) server.close();
  process.exit(1);
});
