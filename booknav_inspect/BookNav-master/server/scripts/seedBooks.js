const mongoose = require("mongoose");
const dotenv = require("dotenv");
const path = require("path");

dotenv.config({ path: path.join(__dirname, "..", ".env") });
const connectDB = require("../config/db");
const { seedBooksIfEmpty } = require("../services/seedService");
const { syncVocabulary } = require("../services/lacsService");
const Book = require("../models/Book");

async function run() {
  await connectDB();
  const res = await seedBooksIfEmpty();
  console.log("Seed result:", res);

  const books = await Book.find().select("title author category keywords description").lean();
  const syncRes = await syncVocabulary(books);
  console.log(`LACS synchronized with ${books.length} books (vocab size: ${syncRes.vocabulary_size})`);
  process.exit(0);
}

run().catch((err) => {
  console.error("Seeding failed:", err);
  process.exit(1);
});
