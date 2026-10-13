const { spawn } = require("child_process");
const path = require("path");
const readline = require("readline");

const BRIDGE_PATH = path.join(__dirname, "..", "lacs_bridge.py");
const LIBRARY_CSV = process.env.LACS_LIBRARY_CSV ||
  path.join(__dirname, "..", "lacs_data", "library_books.csv");
const HISTORY_PATH = process.env.LACS_HISTORY_PATH ||
  path.join(__dirname, "..", "lacs_data", "correction_history.csv");
const PYTHON_BIN = process.env.LACS_PYTHON || process.env.PYTHON_PATH || "python";
const REQUEST_TIMEOUT_MS = Number(process.env.LACS_TIMEOUT_MS || 5000);

let worker = null;
let reader = null;
let nextId = 1;
let isReady = false;
let intentionalStop = false;
const pending = new Map();
const readyCallbacks = [];

function rejectPending(error) {
  for (const { reject, timeout } of pending.values()) {
    clearTimeout(timeout);
    reject(error);
  }
  pending.clear();
}

function waitUntilReady(timeoutMs = 10000) {
  if (isReady) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      const idx = readyCallbacks.indexOf(onReady);
      if (idx !== -1) readyCallbacks.splice(idx, 1);
      reject(new Error(`LACS bridge worker did not become ready within ${timeoutMs}ms`));
    }, timeoutMs);

    const onReady = (err) => {
      clearTimeout(timer);
      if (err) reject(err);
      else resolve();
    };

    readyCallbacks.push(onReady);
  });
}

function startWorker() {
  if (worker) {
    return worker;
  }
  intentionalStop = false;

  try {
    worker = spawn(PYTHON_BIN, [BRIDGE_PATH, LIBRARY_CSV, HISTORY_PATH], {
      cwd: path.join(__dirname, ".."),
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8"
      },
      stdio: ["pipe", "pipe", "pipe"]
    });

    reader = readline.createInterface({ input: worker.stdout, terminal: false });

    reader.on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      let message;
      try {
        message = JSON.parse(trimmed);
      } catch (error) {
        console.error("Invalid LACS JSON response:", trimmed);
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
      const text = data.toString();
      if (text.includes("LACS_BRIDGE_READY")) {
        isReady = true;
        console.log("LACS bridge worker is ready.");
        const cbs = [...readyCallbacks];
        readyCallbacks.length = 0;
        cbs.forEach((cb) => cb(null));
      } else {
        const trimmed = text.trim();
        if (trimmed) {
          console.error(`[LACS Python] ${trimmed}`);
        }
      }
    });

    worker.on("exit", (code, signal) => {
      console.warn(`LACS worker exited with code ${code}, signal ${signal}`);
      worker = null;
      reader = null;
      isReady = false;
      const error = new Error(`LACS worker exited with code ${code}, signal ${signal}`);
      const cbs = [...readyCallbacks];
      readyCallbacks.length = 0;
      cbs.forEach((cb) => cb(error));
      rejectPending(error);
    });

    worker.on("error", (error) => {
      console.error("LACS worker process error:", error);
      worker = null;
      reader = null;
      isReady = false;
      const cbs = [...readyCallbacks];
      readyCallbacks.length = 0;
      cbs.forEach((cb) => cb(error));
      rejectPending(error);
    });
  } catch (err) {
    console.error("Failed to start LACS worker:", err);
    worker = null;
    isReady = false;
    const cbs = [...readyCallbacks];
    readyCallbacks.length = 0;
    cbs.forEach((cb) => cb(err));
    throw err;
  }

  return worker;
}

async function sendCommand(payload, timeoutMs = REQUEST_TIMEOUT_MS) {
  const activeWorker = startWorker();
  const id = nextId++;

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`LACS operation timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    pending.set(id, { resolve, reject, timeout });
    try {
      activeWorker.stdin.write(`${JSON.stringify({ ...payload, id })}\n`);
    } catch (writeErr) {
      clearTimeout(timeout);
      pending.delete(id);
      reject(writeErr);
    }
  });
}

function correctQuery(query) {
  return sendCommand({ query });
}

function syncVocabulary(books) {
  return sendCommand({ action: "sync", books }, 30000);
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
  return sendCommand({ action: "health" }, 5000);
}

function stopWorker() {
  intentionalStop = true;
  if (worker) {
    worker.kill();
    worker = null;
    reader = null;
    isReady = false;
  }
}

function isRunning() {
  return worker !== null;
}

module.exports = {
  correctQuery,
  syncVocabulary,
  addBook,
  updateBook,
  deleteBook,
  acceptCorrection,
  checkHealth,
  stopWorker,
  isRunning,
  waitUntilReady
};
