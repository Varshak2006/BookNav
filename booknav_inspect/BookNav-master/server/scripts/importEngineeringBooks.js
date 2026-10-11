/**
 * Safe MongoDB Import Script for Engineering Books.
 *
 * Requirements:
 * - Validates records against Mongoose Book schema.
 * - Defaults to safe DRY-RUN mode unless --apply is explicitly specified.
 * - Deduplicates against existing records to prevent duplicate insertion.
 * - Never deletes or overwrites existing records.
 * - Reports detailed metrics: inserted, skipped, failed.
 * - Handles connection failures gracefully.
 * - Can be safely rerun idempotently.
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const mongoose = require("mongoose");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });
const connectDB = require("../config/db");
const Book = require("../models/Book");
const { syncVocabulary } = require("../services/lacsService");

// Parse Command Line Arguments
const args = process.argv.slice(2);
const isApply = args.includes("--apply");
const isDryRun = !isApply || args.includes("--dry-run");

let csvPath = path.resolve(__dirname, "..", "..", "..", "datasets", "engineering_books.csv");
const csvArgIdx = args.indexOf("--csv");
if (csvArgIdx !== -1 && args[csvArgIdx + 1]) {
  csvPath = path.resolve(args[csvArgIdx + 1]);
}

let limitCount = Infinity;
const limitArgIdx = args.indexOf("--limit");
if (limitArgIdx !== -1 && args[limitArgIdx + 1]) {
  limitCount = parseInt(args[limitArgIdx + 1], 10) || Infinity;
}

function parseCSVLine(line) {
  const fields = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      fields.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current.trim());
  return fields;
}

async function loadCSVRecords(filePath, maxLimit) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`CSV file not found: ${filePath}`);
  }

  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });

  let headers = null;
  const records = [];

  for await (const line of rl) {
    if (!line.trim()) continue;
    const fields = parseCSVLine(line);
    if (!headers) {
      headers = fields;
      continue;
    }
    const record = {};
    headers.forEach((h, idx) => {
      record[h] = fields[idx] || "";
    });
    records.push(record);
    if (records.length >= maxLimit) break;
  }

  return records;
}

function mapToBookModel(rec, index) {
  const title = (rec.title || "").trim();
  const author = (rec.authors || "Unknown Author").trim();
  const rawSubj = (rec.subjects || "").trim();
  const primaryCategory = rawSubj.split(";")[0].trim() || "Computer Science";
  const workId = (rec.openlibrary_work_id || "").trim();

  // Validate required schema fields
  if (!title || !author) {
    return null;
  }

  const shelfLetter = String.fromCharCode(65 + (index % 6)); // Shelf-A to Shelf-F
  const rackNum = (index % 5) + 1; // Rack-1 to Rack-5

  return {
    title,
    author,
    category: primaryCategory.slice(0, 50),
    description: `Open Library Work ID: ${workId}. Subjects: ${rawSubj.slice(0, 150)}`,
    keywords: `${title} ${primaryCategory} ${workId}`.toLowerCase().slice(0, 200),
    shelf: `Shelf-${shelfLetter}`,
    rack: `Rack-${rackNum}`,
    location: "Engineering Library Stack"
  };
}

async function runImport() {
  console.log("================================================================================");
  console.log("BOOKNAV SAFE MONGODB IMPORT UTILITY");
  console.log("================================================================================");
  console.log(`Source File:    ${csvPath}`);
  console.log(`Execution Mode: ${isDryRun ? "DRY-RUN (Simulated — No changes will be written to MongoDB)" : "APPLY (Live Insertion into MongoDB)"}`);
  if (limitCount < Infinity) console.log(`Record Limit:   ${limitCount}`);
  console.log("--------------------------------------------------------------------------------");

  // Step 1: Connect to MongoDB
  try {
    await connectDB();
  } catch (err) {
    console.error("FATAL: MongoDB connection failed:", err.message);
    process.exit(1);
  }

  // Step 2: Query existing books for safe deduplication
  const existingBooks = await Book.find().select("title author").lean();
  console.log(`Found ${existingBooks.length} existing book records in MongoDB.`);
  const existingSet = new Set(
    existingBooks.map((b) => `${(b.title || "").toLowerCase().trim()}|${(b.author || "").toLowerCase().trim()}`)
  );

  // Step 3: Load CSV records
  console.log("Reading CSV records...");
  const rawRecords = await loadCSVRecords(csvPath, limitCount);
  console.log(`Read ${rawRecords.length} records from CSV.`);

  const toInsert = [];
  let skippedDuplicates = 0;
  let invalidRecords = 0;

  rawRecords.forEach((rec, idx) => {
    const bookData = mapToBookModel(rec, idx);
    if (!bookData) {
      invalidRecords++;
      return;
    }

    const key = `${bookData.title.toLowerCase()}|${bookData.author.toLowerCase()}`;
    if (existingSet.has(key)) {
      skippedDuplicates++;
      return;
    }

    // Deduplicate within current batch as well
    existingSet.add(key);
    toInsert.push(bookData);
  });

  console.log("\n--------------------------------------------------------------------------------");
  console.log("IMPORT ANALYSIS SUMMARY");
  console.log("--------------------------------------------------------------------------------");
  console.log(`Total Records Evaluated:     ${rawRecords.length}`);
  console.log(`Valid New Books to Insert:   ${toInsert.length}`);
  console.log(`Existing Duplicates Skipped: ${skippedDuplicates}`);
  console.log(`Invalid Records Skipped:     ${invalidRecords}`);

  if (toInsert.length > 0) {
    console.log("\nSample candidate records for import:");
    toInsert.slice(0, 3).forEach((b, i) => {
      console.log(`  [${i + 1}] "${b.title}" by ${b.author}`);
      console.log(`      Category: ${b.category} | Shelf: ${b.shelf} | Rack: ${b.rack}`);
    });
  }

  if (isDryRun) {
    console.log("\n================================================================================");
    console.log("DRY-RUN COMPLETE: No changes were committed to MongoDB.");
    console.log("To perform actual insertion, rerun with: node importEngineeringBooks.js --apply");
    console.log("================================================================================");
    process.exit(0);
  }

  // Step 4: Execute Live Insertion (Apply Mode)
  console.log("\nProceeding with live insertion into MongoDB...");
  let insertedCount = 0;
  let failedCount = 0;

  try {
    const BATCH_SIZE = 100;
    for (let i = 0; i < toInsert.length; i += BATCH_SIZE) {
      const batch = toInsert.slice(i, i + BATCH_SIZE);
      const res = await Book.insertMany(batch, { ordered: false });
      insertedCount += res.length;
      console.log(`  Inserted batch ${Math.floor(i / BATCH_SIZE) + 1}: ${res.length} books.`);
    }
  } catch (err) {
    if (err.insertedDocs) {
      insertedCount += err.insertedDocs.length;
    }
    console.error("Warning during batch insertion:", err.message);
    failedCount = toInsert.length - insertedCount;
  }

  console.log("\n--------------------------------------------------------------------------------");
  console.log("LIVE IMPORT EXECUTION RESULTS");
  console.log("--------------------------------------------------------------------------------");
  console.log(`Successfully Inserted: ${insertedCount} books`);
  console.log(`Duplicates Skipped:    ${skippedDuplicates} books`);
  console.log(`Failed Insertions:     ${failedCount} books`);

  // Step 5: Synchronize LACS vocabulary
  try {
    console.log("Synchronizing LACS vocabulary with updated MongoDB catalogue...");
    const allBooks = await Book.find().select("title author category keywords description").lean();
    const syncRes = await syncVocabulary(allBooks);
    console.log(`LACS synchronized with ${allBooks.length} MongoDB books (vocabulary size: ${syncRes.vocabulary_size})`);
  } catch (syncErr) {
    console.warn("LACS sync warning (non-fatal):", syncErr.message);
  }

  console.log("================================================================================");
  console.log("IMPORT COMPLETE");
  console.log("================================================================================");
  process.exit(0);
}

runImport().catch((err) => {
  console.error("FATAL ERROR:", err);
  process.exit(1);
});
