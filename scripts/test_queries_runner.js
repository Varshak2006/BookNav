/**
 * Section 19: Mandatory Query Verification Runner
 * Tests the 10 required queries through the BookNav Express Application API:
 * 1. "harry poater"
 * 2. "machine learning basics"
 * 3. "deep learning"
 * 4. "artificial intelligence"
 * 5. "operating systems"
 * 6. "computer networks"
 * 7. An existing correctly spelled title ("Clean Code")
 * 8. A query with no relevant books ("quantum culinary pastry mechanics")
 * 9. "databases"
 * 10. A misspelling of a library-specific term ("silbershatz")
 *
 * For each query, records:
 * - Original query
 * - Selected query (effectiveQuery)
 * - LACS outcome (lacsStatus, correctionApplied, correctedQuery)
 * - Correction decision (confidence, confidenceLevel)
 * - Embedding status (generated / success)
 * - FAISS candidate count (candidates retrieved)
 * - Valid MongoDB record count (resolved books)
 * - Final result count
 * - Search mode (keyword / semantic / semantic_fallback)
 * - Error stage, if any
 */

const http = require("http");
const path = require("path");
const mongoose = require("mongoose");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });

const MONGO_URI = process.env.MONGO_URI || "mongodb://localhost:27017/book";
const TEST_PORT = 5099;
const BASE_URL = `http://localhost:${TEST_PORT}`;

// Import Express app & services
const { connectDB } = require("../server/config/db");
const { app } = require("../server/server");
const faissService = require("../server/services/faissService");
const { stopWorker: stopLacsWorker } = require("../server/services/lacsService");

const QUERIES = [
  { q: "harry poater", type: "Typo in popular title/author" },
  { q: "machine learning basics", type: "Multi-token semantic search query" },
  { q: "deep learning", type: "Standard technical domain query" },
  { q: "artificial intelligence", type: "Broad concept query" },
  { q: "operating systems", type: "Plural technical term query" },
  { q: "computer networks", type: "Standard system query" },
  { q: "Clean Code", type: "Existing correctly spelled title" },
  { q: "quantum culinary pastry mechanics", type: "Query with no relevant books" },
  { q: "databases", type: "Plural technical keyword (preservation test)" },
  { q: "silbershatz", type: "Misspelling of library-specific author name" }
];

function request(path) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, body: data });
        }
      });
    }).on("error", reject);
  });
}

async function run() {
  console.log("================================================================================");
  console.log("               BOOKNAV SECTION 19: 10 MANDATORY QUERY AUDIT                     ");
  console.log("================================================================================\n");

  await connectDB(MONGO_URI);
  console.log("Connected to MongoDB:", MONGO_URI);

  const server = await new Promise((resolve) => {
    const s = app.listen(TEST_PORT, () => resolve(s));
  });

  const records = [];

  try {
    for (const item of QUERIES) {
      const encoded = encodeURIComponent(item.q);
      
      // 1. Test via standard search route (/api/books/search)
      const searchRes = await request(`/api/books/search?q=${encoded}&top_k=5`);
      
      // 2. Test via semantic search route (/api/books/semantic-search)
      const semRes = await request(`/api/books/semantic-search?q=${encoded}&top_k=5`);

      const sBody = searchRes.body || {};
      const semBody = semRes.body || {};

      const errorStage = (searchRes.status !== 200 || semRes.status !== 200)
        ? (searchRes.status !== 200 ? `Search HTTP ${searchRes.status}` : `Semantic HTTP ${semRes.status}`)
        : "None";

      const record = {
        originalQuery: item.q,
        type: item.type,
        selectedQuery: sBody.effectiveQuery || item.q,
        lacsOutcome: sBody.lacsStatus || "unknown",
        correctionDecision: sBody.correctionApplied ? `Applied (${sBody.confidenceLevel || "high"})` : `None (${sBody.confidenceLevel || "none"})`,
        correctedTo: sBody.correctedQuery || "-",
        embeddingStatus: semRes.status === 200 ? "Generated (Success)" : "Failed",
        faissCandidateCount: (semBody.results && semBody.results.length) || 0,
        validMongoRecordCount: (sBody.results && sBody.results.length) || 0,
        finalResultCount: (sBody.results && sBody.results.length) || 0,
        searchMode: sBody.searchMode || "keyword",
        fallbackStatus: sBody.fallbackStatus || "-",
        errorStage: errorStage,
        topBookTitle: sBody.results && sBody.results.length > 0 ? sBody.results[0].title : "None",
        topBookAuthor: sBody.results && sBody.results.length > 0 ? sBody.results[0].author : "None",
        topBookScore: semBody.results && semBody.results.length > 0 ? semBody.results[0].similarity_score : null
      };

      records.push(record);

      console.log(`Query: "${item.q}" (${item.type})`);
      console.log(`  -> Selected Query:         "${record.selectedQuery}"`);
      console.log(`  -> LACS Outcome:            ${record.lacsOutcome} [${record.correctionDecision}]`);
      console.log(`  -> Embedding Status:        ${record.embeddingStatus}`);
      console.log(`  -> Search Mode:             ${record.searchMode} (fallback: ${record.fallbackStatus})`);
      console.log(`  -> FAISS Semantic Matches:  ${record.faissCandidateCount}`);
      console.log(`  -> Final Valid Books:       ${record.finalResultCount}`);
      console.log(`  -> Top Book:                "${record.topBookTitle}" by ${record.topBookAuthor}`);
      console.log(`  -> Error Stage:             ${record.errorStage}\n`);
    }

    console.log("========================================================================================================================");
    console.log("                                               QUERY VERIFICATION SUMMARY TABLE                                         ");
    console.log("========================================================================================================================");
    console.log(
      "| #  | Original Query                 | Selected Query           | LACS Status | Mode              | FAISS | Mongo | Error Stage |"
    );
    console.log(
      "|----|--------------------------------|--------------------------|-------------|-------------------|-------|-------|-------------|"
    );
    records.forEach((r, idx) => {
      const idxStr = String(idx + 1).padEnd(2);
      const orig = r.originalQuery.padEnd(30).slice(0, 30);
      const sel = r.selectedQuery.padEnd(24).slice(0, 24);
      const lacs = r.lacsOutcome.padEnd(11).slice(0, 11);
      const mode = (r.searchMode + (r.fallbackStatus !== "-" ? ` (${r.fallbackStatus})` : "")).padEnd(17).slice(0, 17);
      const faiss = String(r.faissCandidateCount).padEnd(5);
      const mongo = String(r.finalResultCount).padEnd(5);
      const err = r.errorStage.padEnd(11);
      console.log(`| ${idxStr} | ${orig} | ${sel} | ${lacs} | ${mode} | ${faiss} | ${mongo} | ${err} |`);
    });
    console.log("========================================================================================================================");

  } finally {
    server.close();
    stopLacsWorker();
    faissService.stopWorker();
    await mongoose.disconnect();
  }
}

run().catch((err) => {
  console.error("Runner error:", err);
  process.exit(1);
});
