const { spawn } = require("child_process");
const path = require("path");
const readline = require("readline");

const BRIDGE_PATH = path.join(__dirname, "..", "lacs_bridge.py");
const LIBRARY_CSV = process.env.LACS_LIBRARY_CSV ||
  path.join(__dirname, "..", "lacs_data", "library_books.csv");
const HISTORY_PATH = process.env.LACS_HISTORY_PATH ||
  path.join(__dirname, "..", "lacs_data", "correction_history.csv");
const PYTHON_BIN = process.env.LACS_PYTHON || "python";
const REQUEST_TIMEOUT_MS = Number(process.env.LACS_TIMEOUT_MS || 5000);

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

  worker = spawn(PYTHON_BIN, [BRIDGE_PATH, LIBRARY_CSV, HISTORY_PATH], {
    cwd: path.join(__dirname, ".."),
    stdio: ["pipe", "pipe", "pipe"]
  });

  const reader = readline.createInterface({ input: worker.stdout });

  reader.on("line", (line) => {
    let message;
    try {
      message = JSON.parse(line);
    } catch (error) {
      console.error("Invalid LACS response:", line);
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
      request.reject(new Error(message.error || "LACS correction failed"));
    }
  });

  worker.stderr.on("data", (data) => {
    console.error(`LACS stderr: ${data}`);
  });

  worker.on("exit", (code) => {
    const error = new Error(`LACS worker exited with code ${code}`);
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
      reject(new Error("LACS operation timed out"));
    }, REQUEST_TIMEOUT_MS);

    pending.set(id, { resolve, reject, timeout });
    activeWorker.stdin.write(`${JSON.stringify({ ...payload, id })}\n`);
  });
}

function correctQuery(query) {
  return sendCommand({ query });
}

function syncVocabulary(books) {
  return sendCommand({ action: "sync", books });
}

function addBook(book) {
  return sendCommand({ action: "add_book", book });
}

function updateBook(oldBook, newBook) {
  return sendCommand({ action: "update_book", old_book: oldBook, new_book: newBook });
}

function deleteBook(book) {
  return sendCommand({ action: "delete_book", book });
}

function acceptCorrection(wrong, correct) {
  return sendCommand({ action: "accept_correction", wrong, correct });
}

function checkHealth() {
  return sendCommand({ action: "health" });
}

function stopWorker() {
  if (worker) {
    worker.kill();
    worker = null;
  }
}

module.exports = {
  correctQuery,
  syncVocabulary,
  addBook,
  updateBook,
  deleteBook,
  acceptCorrection,
  checkHealth,
  stopWorker
};
