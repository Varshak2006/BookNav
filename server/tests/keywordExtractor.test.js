
const assert = require("node:assert/strict");

const {
  extractKeywords,
  normalizeText
} = require("../services/keywordExtractor");

const book = {
  title: "Introduction to Machine Learning",
  author: "John Smith",
  category: "Artificial Intelligence",
  description:
    "Learn machine learning algorithms and neural networks"
};

const keywords = extractKeywords(book);
const normalized = normalizeText(keywords);

assert.ok(normalized.includes("machine learning"));
assert.ok(normalized.includes("artificial intelligence"));
assert.ok(normalized.includes("neural networks"));

assert.equal(
  extractKeywords({ title: "Computer Networks" })
    .includes("computer networks"),
  true
);

assert.equal(
  extractKeywords({ title: "Data Structures", keywords: "custom topic" })
    .includes("custom topic"),
  true
);

assert.equal(
  extractKeywords({ title: "Machine Learning" }),
  extractKeywords({ title: "Machine Learning" })
);

console.log("All keyword extractor tests passed!");
