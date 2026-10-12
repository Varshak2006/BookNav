/**
 * FAISS Vector Search Service for BookNav.
 *
 * Manages the persistent Python FAISS bridge subprocess, provides
 * asynchronous request-response IPC over JSON lines, and handles
 * vector search queries, book additions, book deletions, and index status.
 */

const { spawn } = require("child_process");
const path = require("path");
const readline = require("readline");

class FaissService {
  constructor() {
    this.pythonProcess = null;
    this.rl = null;
    this.pendingRequests = new Map();
    this.nextRequestId = 1;
    this.isReady = false;
    this._intentionalStop = false;
    this._restartTimer = null;
    this.scriptPath = path.join(__dirname, "..", "faiss_bridge.py");
    this.pythonCmd = process.env.PYTHON_PATH || "python";
    this.restartAttempts = 0;
    this.maxRestartAttempts = 5;
    this._readyCallbacks = [];
  }

  waitUntilReady(timeoutMs = 15000) {
    if (this.isReady) return Promise.resolve();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this._readyCallbacks.indexOf(onReady);
        if (idx !== -1) this._readyCallbacks.splice(idx, 1);
        reject(new Error(`FAISS bridge worker did not become ready within ${timeoutMs}ms`));
      }, timeoutMs);

      const onReady = (err) => {
        clearTimeout(timer);
        if (err) reject(err);
        else resolve();
      };

      this._readyCallbacks.push(onReady);
    });
  }

  start() {
    if (this.pythonProcess) return;
    this._intentionalStop = false;

    try {
      this.pythonProcess = spawn(this.pythonCmd, [this.scriptPath], {
        cwd: path.join(__dirname, ".."),
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
          HF_HUB_OFFLINE: "1",
          TRANSFORMERS_OFFLINE: "1"
        },
        stdio: ["pipe", "pipe", "pipe"]
      });

      // Handle spawn errors (e.g., missing python executable)
      this.pythonProcess.on("error", (err) => {
        console.error("Failed to spawn FAISS bridge process:", err.message);
        this.pythonProcess = null;
        this.rl = null;
        this.isReady = false;
        const cbs = [...this._readyCallbacks];
        this._readyCallbacks = [];
        cbs.forEach((cb) => cb(err));
      });

      this.rl = readline.createInterface({
        input: this.pythonProcess.stdout,
        terminal: false
      });

      this.rl.on("line", (line) => {
        const trimmed = line.trim();
        if (!trimmed) return;

        try {
          const response = JSON.parse(trimmed);
          const reqId = response.id;
          if (this.pendingRequests.has(reqId)) {
            const { resolve, reject, timer } = this.pendingRequests.get(reqId);
            clearTimeout(timer);
            this.pendingRequests.delete(reqId);

            if (response.ok) {
              resolve(response.data);
            } else {
              reject(new Error(response.error || "FAISS bridge returned an error"));
            }
          }
        } catch (err) {
          // Malformed output — log but don't crash
          console.error("Failed to parse line from FAISS bridge:", err.message);
        }
      });

      this.pythonProcess.stderr.on("data", (data) => {
        const msg = data.toString();
        if (msg.includes("FAISS_BRIDGE_READY")) {
          this.isReady = true;
          this.restartAttempts = 0;
          console.log("FAISS bridge worker is ready.");
          const cbs = [...this._readyCallbacks];
          this._readyCallbacks = [];
          cbs.forEach((cb) => cb(null));
        } else {
          // Log other debug/warning messages from Python stderr
          const trimmed = msg.trim();
          if (trimmed) {
            console.log("[FAISS Python]", trimmed);
          }
        }
      });

      this.pythonProcess.on("exit", (code, signal) => {
        console.warn(`FAISS bridge exited with code ${code}, signal ${signal}`);
        this.pythonProcess = null;
        this.rl = null;
        this.isReady = false;

        const exitErr = new Error(`FAISS bridge process exited (code ${code}, signal ${signal})`);
        const cbs = [...this._readyCallbacks];
        this._readyCallbacks = [];
        cbs.forEach((cb) => cb(exitErr));

        // Reject all outstanding requests
        for (const [id, { reject, timer }] of this.pendingRequests.entries()) {
          clearTimeout(timer);
          reject(new Error(`FAISS bridge process exited before responding to request ${id}`));
        }
        this.pendingRequests.clear();

        // Only auto-restart on unexpected exit (not intentional stopWorker)
        if (!this._intentionalStop && this.restartAttempts < this.maxRestartAttempts) {
          this.restartAttempts++;
          const delay = Math.min(1000 * Math.pow(2, this.restartAttempts), 10000);
          console.log(`Restarting FAISS bridge worker in ${delay}ms (attempt ${this.restartAttempts})...`);
          this._restartTimer = setTimeout(() => this.start(), delay);
        }
      });
    } catch (err) {
      console.error("Failed to start FAISS bridge process:", err);
      const cbs = [...this._readyCallbacks];
      this._readyCallbacks = [];
      cbs.forEach((cb) => cb(err));
    }
  }

  async sendRequest(action, payload = {}, timeoutMs = 30000) {
    if (!this.pythonProcess) {
      this.start();
    }

    if (!this.pythonProcess) {
      throw new Error("FAISS bridge process is not available.");
    }

    // Wait until bridge signals ready before writing requests
    await this.waitUntilReady(Math.min(timeoutMs, 20000));

    return new Promise((resolve, reject) => {
      const id = this.nextRequestId++;
      const message = JSON.stringify({ id, action, ...payload }) + "\n";

      const timer = setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error(`FAISS request '${action}' timed out after ${timeoutMs}ms`));
        }
      }, timeoutMs);

      this.pendingRequests.set(id, { resolve, reject, timer });

      try {
        this.pythonProcess.stdin.write(message);
      } catch (err) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(err);
      }
    });
  }

  async search(query, topK = 10, filters = {}, candidateExpansion = null) {
    return this.sendRequest("search", {
      query,
      top_k: topK,
      filters,
      candidate_expansion: candidateExpansion
    });
  }

  async addBook(book) {
    return this.sendRequest("add_book", { book });
  }

  async deleteBook(bookId) {
    return this.sendRequest("delete_book", { book_id: bookId });
  }

  async getStatus() {
    return this.sendRequest("status");
  }

  async rebuildIndex(books = null) {
    return this.sendRequest("rebuild", { books }, 120000);
  }

  async updateBook(book) {
    return this.sendRequest("update_book", { book });
  }

  stopWorker() {
    this._intentionalStop = true;
    if (this._restartTimer) {
      clearTimeout(this._restartTimer);
      this._restartTimer = null;
    }
    if (this.pythonProcess) {
      this.pythonProcess.kill();
      this.pythonProcess = null;
      this.rl = null;
      this.isReady = false;
    }
  }
}

// Singleton instance
const faissService = new FaissService();

module.exports = faissService;
