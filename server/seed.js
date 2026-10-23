const fs = require("fs");
const path = require("path");
const mongoose = require("mongoose");
const dotenv = require("dotenv");

// Load .env from server directory or project root
const envPath = fs.existsSync(path.join(__dirname, ".env"))
  ? path.join(__dirname, ".env")
  : path.join(__dirname, "..", ".env");
dotenv.config({ path: envPath });

const { connectDB } = require("./config/db");
const Book = require("./models/Book");

async function seedDatabase() {
  console.log("=========================================");
  console.log("   BookNav Database Seeding Utility      ");
  console.log("=========================================\n");

  try {
    await connectDB();

    const mappingFile = path.join(__dirname, "faiss_data", "book_id_mapping.json");
    if (!fs.existsSync(mappingFile)) {
      console.error(`Error: Mapping file not found at ${mappingFile}`);
      process.exit(1);
    }

    const rawData = fs.readFileSync(mappingFile, "utf-8");
    const json = JSON.parse(rawData);
    const mappings = json.mappings || [];

    if (mappings.length === 0) {
      console.warn("No book mappings found in JSON file.");
      process.exit(0);
    }

    console.log(`Found ${mappings.length} books in FAISS mapping dataset.`);

    const operations = mappings.map((item) => {
      const meta = item.metadata || {};
      const bookDoc = {
        _id: new mongoose.Types.ObjectId(item.mongo_id),
        title: meta.title || "Untitled",
        author: meta.author || "Unknown Author",
        category: meta.category || "General",
        description: meta.description || "",
        keywords: meta.keywords || "",
        shelf: meta.shelf || "Shelf-A",
        rack: meta.rack || "Rack-1",
        location: meta.location || "Main Library Hall"
      };

      return {
        updateOne: {
          filter: { _id: bookDoc._id },
          update: { $set: bookDoc },
          upsert: true
        }
      };
    });

    console.log("Upserting books into MongoDB...");
    const result = await Book.bulkWrite(operations);
    console.log(`\nSuccess!`);
    console.log(`- Upserted: ${result.upsertedCount}`);
    console.log(`- Modified: ${result.modifiedCount}`);
    console.log(`- Total Books in Catalog: ${await Book.countDocuments()}`);

    console.log("\nDatabase is now synchronized with FAISS vector index mappings!");
    process.exit(0);
  } catch (error) {
    console.error("Seeding failed with error:", error);
    process.exit(1);
  }
}

seedDatabase();
