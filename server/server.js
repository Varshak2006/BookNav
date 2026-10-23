
require("dotenv").config();

const express = require("express");
const cors = require("cors");
const session = require("express-session");
const MongoStore = require("connect-mongo").default;
const os = require("os");

const { connectDB, getMongoUri } = require("./config/db");
const bookRoutes = require("./routes/bookRoutes");
const adminRoutes = require("./routes/adminRoutes");
const userRoutes = require("./routes/userRoutes");

// Enforce session secret policy in production.
if (process.env.NODE_ENV === "production") {
  if (
    !process.env.SESSION_SECRET ||
    process.env.SESSION_SECRET === "booknav_session_secret_default"
  ) {
    console.error(
      "FATAL: A secure SESSION_SECRET must be explicitly provided in production mode."
    );
    process.exit(1);
  }
}

const app = express();

// Security headers.
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("X-XSS-Protection", "1; mode=block");
  next();
});

// Get the current computer's IPv4 addresses for logging.
function getLocalNetworkIPs() {
  const interfaces = os.networkInterfaces();
  const addresses = [];

  for (const entries of Object.values(interfaces)) {
    for (const address of entries || []) {
      if (address.family === "IPv4" && !address.internal) {
        addresses.push(address.address);
      }
    }
  }

  return [...new Set(addresses)];
}

// CORS configuration for local development and phone testing.
const allowedOrigins = new Set([
   "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:5174",
  "http://127.0.0.1:5174",
  "http://10.20.0.104:5173",
  "http://10.20.0.104:5174",
  "http://10.156.39.21:5173",
  ...(process.env.CLIENT_URL
    ? process.env.CLIENT_URL.split(",").map((origin) => origin.trim())
    : []),
]);

app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests without an Origin header, such as direct API checks.
      if (!origin || allowedOrigins.has(origin)) {
        return callback(null, true);
      }

      console.error(`CORS blocked origin: ${origin}`);
      return callback(new Error("Origin not allowed by CORS"));
    },
    credentials: true,
  })
);

app.use(express.json());

// MongoDB configuration.
const mongoUri = getMongoUri();

// Session configuration.
app.use(
  session({
    secret:
      process.env.SESSION_SECRET || "booknav_session_secret_default",
    resave: false,
    saveUninitialized: false,
    store: MongoStore.create({
      mongoUrl: mongoUri,
      collectionName: "sessions",
    }),
    cookie: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 1000 * 60 * 60 * 24,
    },
  })
);

// API routes.
app.use("/api/user", userRoutes);
app.use("/api/books", bookRoutes);
app.use("/api/admin", adminRoutes);

// Backend health-check endpoint.
app.get("/", (req, res) => {
  res.json({
    message: "BookNav backend is running successfully!",
  });
});

// Centralized error handler.
app.use((err, req, res, next) => {
  console.error("Unhandled server error:", err.message);

  if (res.headersSent) {
    return next(err);
  }

  res.status(err.status || 500).json({
    message: "An unexpected server error occurred. Please try again later.",
  });
});

const PORT = process.env.PORT || 5000;

// Start the backend and listen on all network interfaces.
async function startServer() {
  await connectDB();

  return new Promise((resolve, reject) => {
    const server = app.listen(PORT, "0.0.0.0", () => {
      console.log(`BookNav server listening on port ${PORT}`);
      console.log(`Local API: http://localhost:${PORT}/api/books`);

      const ips = getLocalNetworkIPs();

      if (ips.length) {
        ips.forEach((ip) => {
          console.log(`Network API: http://${ip}:${PORT}/api/books`);
          console.log(`Network frontend: http://${ip}:5173/`);
        });
      }

      console.log("Allowed frontend origins:", [
        ...allowedOrigins,
      ]);

      resolve(server);
    });

    server.on("error", reject);
  });
}

if (require.main === module) {
  startServer().catch((err) => {
    console.error("Failed to start BookNav server:", err);
    process.exit(1);
  });
}

module.exports = { app, startServer };
