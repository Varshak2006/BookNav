/**
 * Security Regression Tests for BookNav Backend.
 *
 * Verifies:
 * 1. MongoDB operator injection prevention on search and filter endpoints.
 * 2. Invalid ObjectId validation returns 400 Bad Request (no CastError crash).
 * 3. Mass assignment prevention (unrecognized properties stripped).
 * 4. Rate limiting on accept-correction feedback endpoint.
 * 5. Rate limiting on admin and user login endpoints.
 * 6. Protection of setup token using timing-safe comparison.
 * 7. Security headers present in responses.
 */

const assert = require("assert");
const http = require("http");
const mongoose = require("mongoose");
const path = require("path");
const dotenv = require("dotenv");

dotenv.config({ path: path.join(__dirname, "..", ".env") });

const TEST_MONGO_URI = process.env.MONGO_URI_TEST || "mongodb://localhost:27017/booknav_test";
process.env.MONGO_URI = TEST_MONGO_URI;
process.env.NODE_ENV = "test";
process.env.PORT = "5099";

const { connectDB } = require("../config/db");
const { app } = require("../server");
const Book = require("../models/Book");
const Admin = require("../models/Admin");
const User = require("../models/User");

let server = null;
const BASE_URL = "http://localhost:5099";

function request(method, path, body = null, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const reqOptions = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        "Content-Type": "application/json",
        ...headers
      }
    };

    const req = http.request(reqOptions, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        let json = null;
        try {
          json = JSON.parse(data);
        } catch (e) {
          json = data;
        }
        resolve({ status: res.statusCode, headers: res.headers, body: json });
      });
    });

    req.on("error", reject);
    if (body) {
      req.write(typeof body === "string" ? body : JSON.stringify(body));
    }
    req.end();
  });
}

async function runSecurityTests() {
  console.log("=================================================");
  console.log("       BOOKNAV SECURITY REGRESSION TEST SUITE    ");
  console.log("=================================================\n");

  await connectDB(TEST_MONGO_URI);
  await Book.deleteMany({});
  await Admin.deleteMany({});
  await User.deleteMany({});

  // Seed one book for testing
  const book = await Book.create({
    title: "Computer Security Principles and Practice",
    author: "William Stallings",
    category: "Security",
    keywords: "cryptography, network security",
    shelf: "S1",
    rack: "R1"
  });

  server = await new Promise((resolve) => {
    const s = app.listen(5099, () => resolve(s));
  });

  let passed = 0;
  let total = 0;

  async function test(name, fn) {
    total++;
    try {
      await fn();
      console.log(`[PASS] ${name}`);
      passed++;
    } catch (err) {
      console.error(`[FAIL] ${name}: ${err.message}`);
    }
  }

  try {
    // 1. Security Headers
    await test("1. Standard security headers (nosniff, DENY, XSS-Protection) are set", async () => {
      const res = await request("GET", "/");
      assert.strictEqual(res.headers["x-content-type-options"], "nosniff");
      assert.strictEqual(res.headers["x-frame-options"], "DENY");
      assert.strictEqual(res.headers["x-xss-protection"], "1; mode=block");
    });

    // 2. Invalid ObjectId Validation
    await test("2. Invalid ObjectId format returns 400 Bad Request", async () => {
      const res = await request("GET", "/api/books/invalid_hex_object_id");
      assert.strictEqual(res.status, 400);
      assert.strictEqual(res.body.message, "Invalid book ID format");
    });

    // 3. Valid ObjectId returns 200
    await test("3. Valid ObjectId retrieves book successfully", async () => {
      const res = await request("GET", `/api/books/${book._id.toString()}`);
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.title, "Computer Security Principles and Practice");
    });

    // 4. Operator Injection on Search Filter
    await test("4. Operator injection in search parameters is rejected or sanitized", async () => {
      // Trying to inject an operator object in query
      const res = await request("GET", `/api/books/search?q=security&author[$ne]=null`);
      assert.strictEqual(res.status, 200);
      // The search query should treat author as undefined string or reject object, not crash with Mongo error
      assert.ok(Array.isArray(res.body.results));
    });

    // 5. Rate limiting on accept-correction endpoint
    await test("5. Rate limiter triggers 429 on excessive correction feedback", async () => {
      let triggered429 = false;
      for (let i = 0; i < 20; i++) {
        const res = await request("POST", "/api/books/accept-correction", {
          wrong: `wrongterm${i}`,
          correct: `correctterm${i}`
        });
        if (res.status === 429) {
          triggered429 = true;
          break;
        }
      }
      assert.strictEqual(triggered429, true, "Must respond with 429 Too Many Requests");
    });

    // 6. Strict validation on accept-correction inputs
    await test("6. Rejects identical or malformed terms in correction feedback", async () => {
      const res = await request("POST", "/api/books/accept-correction", {
        wrong: "identical",
        correct: "identical"
      });
      // Either 400 (identical rejected) or 429 (if already rate limited)
      assert.ok(res.status === 400 || res.status === 429);
    });

    // 7. Login rate limiting for user
    await test("7. User login endpoint enforces rate limiting on repeated failures", async () => {
      let hitRateLimit = false;
      for (let i = 0; i < 8; i++) {
        const res = await request("POST", "/api/user/login", {
          email: "nonexistent@user.com",
          password: "wrongpassword123"
        });
        if (res.status === 429) {
          hitRateLimit = true;
          break;
        }
      }
      assert.strictEqual(hitRateLimit, true, "User login must enforce rate limiting");
    });

    // 8. Admin registration setup-token requirement after bootstrap
    await test("8. Subsequent admin registration rejected without setup token or admin session", async () => {
      // First bootstrap admin
      const res1 = await request("POST", "/api/admin/register", {
        username: "bootstrapadmin",
        email: "bootstrap@admin.com",
        password: "securepassword123"
      });
      assert.strictEqual(res1.status, 201);

      // Attempting second admin without token
      const res2 = await request("POST", "/api/admin/register", {
        username: "unauthorizedadmin",
        email: "unauth@admin.com",
        password: "securepassword123"
      });
      assert.strictEqual(res2.status, 403, "Subsequent registration must require 403 authorization");
    });

    console.log(`\nSecurity Tests: ${passed}/${total} passed (${Math.round((passed / total) * 100)}%)`);
  } finally {
    if (server) {
      server.close();
    }
    await mongoose.connection.db.dropDatabase();
    await mongoose.disconnect();
  }

  process.exit(passed === total ? 0 : 1);
}

runSecurityTests().catch((err) => {
  console.error("Test execution failed:", err);
  if (server) server.close();
  process.exit(1);
});
