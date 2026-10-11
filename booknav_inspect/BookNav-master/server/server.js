const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");
const session = require("express-session");
const MongoStore = require("connect-mongo").default;
const connectDB = require("./config/db");
const bookRoutes = require("./routes/bookRoutes");
const adminRoutes = require("./routes/adminRoutes");
const userRoutes = require("./routes/userRoutes");
const { syncVocabulary } = require("./services/lacsService");
const { buildIndex: faissBuildIndex, checkHealth: faissHealth } = require("./services/faissService");
const { seedBooksIfEmpty } = require("./services/seedService");
const Book = require("./models/Book");
dotenv.config();

connectDB().then(async () => {
  try {
    await seedBooksIfEmpty();
    const books = await Book.find().select("title author category keywords description").lean();
    const res = await syncVocabulary(books || []);
    console.log(`LACS synchronized with ${books.length} MongoDB books (vocab size: ${res.vocabulary_size})`);
  } catch (err) {
    console.error("LACS initial sync from MongoDB (non-fatal):", err.message);
  }

  // Initialize FAISS index
  try {
    const health = await faissHealth();
    if (health.is_ready) {
      console.log(`FAISS index loaded: ${health.total_vectors} vectors`);
    } else {
      // No existing index — build from MongoDB
      console.log("No FAISS index found, building from MongoDB...");
      const allBooks = await Book.find().lean();
      if (allBooks.length > 0) {
        const result = await faissBuildIndex(allBooks);
        console.log(`FAISS index built: ${result.indexed} vectors indexed`);
      } else {
        console.log("No books in MongoDB. FAISS index will be empty.");
      }
    }
  } catch (err) {
    console.error("FAISS initialization (non-fatal):", err.message);
  }
}).catch((err) => {
  console.error("Database initialization error:", err.message);
});

const app = express();

app.use(
  cors({
    origin: "http://localhost:5173",
    credentials: true
  })
);

app.use(express.json());

app.use(
  session({
    secret: process.env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,

    store: MongoStore.create({
      mongoUrl: process.env.MONGO_URI,
      collectionName: "sessions"
    }),

    cookie: {
      httpOnly: true,
      secure: false,
      maxAge: 1000 * 60 * 60 * 24
    }
  })
);
app.use("/api/user",userRoutes);
app.use("/api/books", bookRoutes);
app.use("/api/admin", adminRoutes);
app.get("/", (req, res) => {
  res.json({
    message: "BookNav backend is running successfully!"
  });
});

const PORT = 5000;

app.listen(PORT, () => {
  console.log(`BookNav server running on http://localhost:${PORT}`);
});
