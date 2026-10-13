const assert = require("node:assert/strict");

const {
  bookMatchesSearch,
  buildSearchFilter,
  escapeRegex,
  tokenizeSearchTerm
} = require("../services/bookSearch");

const books = [
  {
    title: "Harry Potter and the Philosopher's Stone",
    author: "J. K. Rowling",
    category: "Fantasy",
    description: "Fantasy novel about Harry Potter."
  },
  {
    title: "Data Structures and Algorithms in Python",
    author: "Michael T. Goodrich",
    category: "Programming",
    description: "Data structures textbook."
  },
  {
    title: "Computer Networks",
    author: "Andrew S. Tanenbaum",
    category: "Networking",
    description: "Computer networking textbook."
  }
];

function test(name, fn) {
  fn();
  console.log(`ok - ${name}`);
}

test("tokenizeSearchTerm normalizes and deduplicates query terms", () => {
  assert.deepEqual(tokenizeSearchTerm(" Harry, Harry Potter! "), ["harry", "potter"]);
});

test("escapeRegex treats user input as literal text", () => {
  assert.equal(escapeRegex("harry.*potter?"), "harry\\.\\*potter\\?");
});

test("bookMatchesSearch keeps direct phrase matches", () => {
  assert.equal(bookMatchesSearch(books[0], "harry potter"), true);
});

test("bookMatchesSearch matches corrected title terms separated by stopwords", () => {
  assert.equal(bookMatchesSearch(books[1], "data structures algorithms python"), true);
});

test("bookMatchesSearch matches author and category terms", () => {
  assert.equal(bookMatchesSearch(books[2], "tanenbaum networking"), true);
});

test("bookMatchesSearch rejects unrelated unknown terms", () => {
  assert.equal(bookMatchesSearch(books[0], "zzqxxunknown"), false);
});

test("buildSearchFilter combines phrase matching with all-token fallback", () => {
  const filter = buildSearchFilter("data structures algorithms python");
  assert.ok(Array.isArray(filter.$or));
  assert.ok(filter.$or.some((condition) => condition.$and));
});
