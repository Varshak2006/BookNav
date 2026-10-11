/**
 * Build or rebuild the FAISS index from MongoDB books.
 *
 * Usage:
 *   node scripts/buildFaissIndex.js
 *
 * Connects to MongoDB, fetches all books, sends them to the
 * FAISS Python bridge to build the index, then exits.
 */

const mongoose = require("mongoose");
const dotenv = require("dotenv");
const path = require("path");

dotenv.config({ path: path.join(__dirname, "..", ".env") });

const Book = require("../models/Book");
const { buildIndex, stopWorker } = require("../services/faissService");

async function main() {
  console.log("Connecting to MongoDB...");
  await mongoose.connect(process.env.MONGO_URI);
  console.log("MongoDB connected.");

  const books = await Book.find().lean();
  console.log(`Found ${books.length} books in MongoDB.`);

  if (books.length === 0) {
    console.warn("No books found. Cannot build FAISS index.");
    await mongoose.disconnect();
    process.exit(1);
  }

  console.log("Building FAISS index...");
  try {
    const result = await buildIndex(books);
    console.log("FAISS index built successfully:");
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error("Failed to build FAISS index:", error.message);
    stopWorker();
    await mongoose.disconnect();
    process.exit(1);
  }

  stopWorker();
  await mongoose.disconnect();
  console.log("Done.");
  process.exit(0);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
