const fs = require("fs");
const path = require("path");
const Book = require("../models/Book");

const CSV_PATH = path.join(__dirname, "..", "lacs_data", "library_books.csv");

// Simple, robust CSV parser for library_books.csv
function parseCSV(content) {
  const lines = content.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length <= 1) return [];

  const records = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    const fields = [];
    let current = "";
    let insideQuotes = false;

    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') {
        insideQuotes = !insideQuotes;
      } else if (char === "," && !insideQuotes) {
        fields.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }
    fields.push(current.trim());

    if (fields.length >= 5) {
      records.push({
        title: fields[0],
        author: fields[1],
        category: fields[2],
        keywords: fields[3],
        description: fields[4],
        shelf: `Shelf-${String.fromCharCode(65 + (i % 6))}`,
        rack: `Rack-${(i % 5) + 1}`,
        location: "Main Library Hall"
      });
    }
  }
  return records;
}

async function seedBooksIfEmpty() {
  const count = await Book.countDocuments();
  if (count > 0) {
    return { count, seeded: false };
  }

  if (!fs.existsSync(CSV_PATH)) {
    console.warn(`Library CSV file not found at ${CSV_PATH}`);
    return { count: 0, seeded: false };
  }

  const csvContent = fs.readFileSync(CSV_PATH, "utf-8");
  const records = parseCSV(csvContent);

  if (records.length === 0) {
    return { count: 0, seeded: false };
  }

  const inserted = await Book.insertMany(records);
  console.log(`Seeded ${inserted.length} library books into MongoDB from CSV.`);
  return { count: inserted.length, seeded: true };
}

module.exports = {
  seedBooksIfEmpty,
  parseCSV
};
