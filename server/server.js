const dotenv = require("dotenv");
dotenv.config();

const express = require("express");
const cors = require("cors");
const session = require("express-session");
const MongoStore = require("connect-mongo").default;
const { connectDB, getMongoUri } = require("./config/db");
const bookRoutes = require("./routes/bookRoutes");
const adminRoutes = require("./routes/adminRoutes");
const userRoutes = require("./routes/userRoutes");

// Enforce session secret policy
if (process.env.NODE_ENV === "production") {
  if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET === "booknav_session_secret_default") {
    console.error("FATAL: A secure SESSION_SECRET must be explicitly provided in production mode.");
    process.exit(1);
  }
}

const app = express();

// Security headers
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("X-XSS-Protection", "1; mode=block");
  next();
});

const allowedOrigin = process.env.CLIENT_URL || "http://localhost:5173";
app.use(
  cors({
    origin: allowedOrigin,
    credentials: true
  })
);

app.use(express.json());

const mongoUri = getMongoUri();

app.use(
  session({
    secret: process.env.SESSION_SECRET || "booknav_session_secret_default",
    resave: false,
    saveUninitialized: false,
    store: MongoStore.create({
      mongoUrl: mongoUri,
      collectionName: "sessions"
    }),
    cookie: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 1000 * 60 * 60 * 24
    }
  })
);

app.use("/api/user", userRoutes);
app.use("/api/books", bookRoutes);
app.use("/api/admin", adminRoutes);

app.get("/", (req, res) => {
  res.json({
    message: "BookNav backend is running successfully!"
  });
});

// Centralized safe error handler (prevents leaking internal stack traces)
app.use((err, req, res, next) => {
  console.error("Unhandled server error:", err.message);
  if (res.headersSent) {
    return next(err);
  }
  res.status(err.status || 500).json({
    message: "An unexpected error occurred. Please try again later."
  });
});

const PORT = process.env.PORT || 5000;

async function startServer() {
  await connectDB();
  return new Promise((resolve) => {
    const server = app.listen(PORT, () => {
      console.log(`BookNav server running on http://localhost:${PORT}`);
      resolve(server);
    });
  });
}

if (require.main === module) {
  startServer().catch((err) => {
    console.error("Failed to start BookNav server:", err);
    process.exit(1);
  });
}

module.exports = { app, startServer };