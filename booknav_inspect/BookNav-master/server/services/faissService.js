const { spawn } = require("child_process");
const path = require("path");
const readline = require("readline");

const BRIDGE_PATH = path.join(__dirname, "..", "faiss_bridge.py");
const PYTHON_BIN = process.env.FAISS_PYTHON || process.env.LACS_PYTHON || "python";
const REQUEST_TIMEOUT_MS = Number(process.env.FAISS_TIMEOUT_MS || 30000);

let worker = null;
let nextId = 1;
const pending = new Map();

function rejectPending(error) {
  for (const { reject, timeout } of pending.values()) {
    clearTimeout(timeout);
    reject(error);
  }
  pending.clear();
}

function startWorker() {
  if (worker) {
    return worker;
  }

  worker = spawn(PYTHON_BIN, [BRIDGE_PATH], {
    cwd: path.join(__dirname, ".."),
    stdio: ["pipe", "pipe", "pipe"]
  });

  const reader = readline.createInterface({ input: worker.stdout });

  reader.on("line", (line) => {
    let message;
    try {
      message = JSON.parse(line);
    } catch (error) {
      console.error("Invalid FAISS response:", line);
      return;
    }

    const request = pending.get(message.id);
    if (!request) {
      return;
    }

    clearTimeout(request.timeout);
    pending.delete(message.id);

    if (message.ok) {
      request.resolve(message.data);
    } else {
      request.reject(new Error(message.error || "FAISS operation failed"));
    }
  });

  worker.stderr.on("data", (data) => {
    console.error(`FAISS stderr: ${data}`);
  });

  worker.on("exit", (code) => {
    const error = new Error(`FAISS worker exited with code ${code}`);
    worker = null;
    rejectPending(error);
  });

  worker.on("error", (error) => {
    worker = null;
    rejectPending(error);
  });

  return worker;
}

function sendCommand(payload) {
  const activeWorker = startWorker();
  const id = nextId++;

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error("FAISS operation timed out"));
    }, REQUEST_TIMEOUT_MS);

    pending.set(id, { resolve, reject, timeout });
    activeWorker.stdin.write(`${JSON.stringify({ ...payload, id })}\n`);
  });
}

/**
 * Semantic search for books matching a query.
 *
 * @param {string} query - Natural language search query.
 * @param {number} [topK=10] - Number of results to return.
 * @param {Object} [filters={}] - Metadata filters (author, category, etc.).
 * @returns {Promise<Object>} Search results with similarity scores.
 */
function semanticSearch(query, topK = 10, filters = {}) {
  return sendCommand({
    action: "search",
    query,
    top_k: topK,
    filters
  });
}

/**
 * Build the FAISS index from a list of book objects.
 *
 * @param {Array<Object>} books - Book documents from MongoDB.
 * @returns {Promise<Object>} Build result summary.
 */
function buildIndex(books) {
  return sendCommand({
    action: "build",
    books: books.map((b) => ({
      _id: String(b._id),
      title: b.title,
      author: b.author,
      category: b.category,
      keywords: b.keywords,
      description: b.description,
      shelf: b.shelf,
      rack: b.rack,
      location: b.location
    }))
  });
}

/**
 * Add a single book to the FAISS index.
 */
function addBook(book) {
  return sendCommand({
    action: "add_book",
    book: {
      _id: String(book._id),
      title: book.title,
      author: book.author,
      category: book.category,
      keywords: book.keywords,
      description: book.description,
      shelf: book.shelf,
      rack: book.rack,
      location: book.location
    }
  });
}

/**
 * Remove a book from the FAISS index.
 */
function removeBook(bookId) {
  return sendCommand({
    action: "remove_book",
    book_id: String(bookId)
  });
}

/**
 * Full rebuild of the FAISS index from a book list.
 */
function rebuildIndex(books) {
  return sendCommand({
    action: "rebuild",
    books: books.map((b) => ({
      _id: String(b._id),
      title: b.title,
      author: b.author,
      category: b.category,
      keywords: b.keywords,
      description: b.description,
      shelf: b.shelf,
      rack: b.rack,
      location: b.location
    }))
  });
}

/**
 * Get index status information.
 */
function getStatus() {
  return sendCommand({ action: "status" });
}

/**
 * Health check.
 */
function checkHealth() {
  return sendCommand({ action: "health" });
}

/**
 * Stop the FAISS Python worker.
 */
function stopWorker() {
  if (worker) {
    worker.kill();
    worker = null;
  }
}

module.exports = {
  semanticSearch,
  buildIndex,
  addBook,
  removeBook,
  rebuildIndex,
  getStatus,
  checkHealth,
  stopWorker
};
