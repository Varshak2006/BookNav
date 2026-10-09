const express = require("express");
const Book = require("../models/Book");
const protectAdmin = require("../middleware/authMiddleware");
const router = express.Router();

// Add a new book
router.post("/", protectAdmin, async (req, res) => {
  try {
    const book = await Book.create(req.body);

    res.status(201).json({
      message: "Book added successfully",
      book
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to add book",
      error: error.message
    });
  }
});
// Get all books
router.get("/", async (req, res) => {
  try {
    const books = await Book.find();

    res.status(200).json(books);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch books",
      error: error.message
    });
  }
});

router.get("/search", async (req, res) => {
  try {
    const { q, filters, logic = "AND" } = req.query;

    const conditions = [];

    // Keep the existing text-search behavior.
    // if (q && q.trim() !== "") {
    //   const searchTerm = q.trim();

      // conditions.push({
      //   $or: [
      //     { title: { $regex: searchTerm, $options: "i" } },
      //     { author: { $regex: searchTerm, $options: "i" } },
      //     { category: { $regex: searchTerm, $options: "i" } }
      //   ]
      // });
    // }

    // Search by title, author, or category.
    if (q && q.trim() !== "") {
      const searchTerm = q.trim();

      conditions.push({
        $or: [
          { title: { $regex: searchTerm, $options: "i" } },
          { author: { $regex: searchTerm, $options: "i" } },
          { category: { $regex: searchTerm, $options: "i" } }
        ]
      });
    }
    // Read active metadata filters from the query string.
    const allowedFields = [
      "title",
      "author",
      "category",
      "shelf",
      "rack",
      "location"
    ];

    if (filters) {
      const filterList = Array.isArray(filters)
        ? filters
        : [filters];

      filterList.forEach((filter) => {
        const separatorIndex = filter.indexOf(":");

        if (separatorIndex === -1) return;

        const field = filter.slice(0, separatorIndex);
        const value = filter.slice(separatorIndex + 1).trim();

        if (
          allowedFields.includes(field) &&
          value !== ""
        ) {
          conditions.push({
            [field]: {
              $regex: value,
              $options: "i"
            }
          });
        }
      });
    }

    const searchLogic = logic.toUpperCase() === "OR"
      ? "$or"
      : "$and";

    let query = {};

    if (conditions.length === 1) {
      query = conditions[0];
    } else if (conditions.length > 1) {
      query = { [searchLogic]: conditions };
    }

    const books = await Book.find(query);

    res.status(200).json(books);
  } catch (error) {
    res.status(500).json({
      message: "Book search failed",
      error: error.message
    });
  }
});
router.get("/:id", async (req, res) => {
  try {
    const book = await Book.findById(req.params.id);

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    res.status(200).json(book);
  } catch (error) {
    res.status(500).json({
      message: "Failed to fetch book",
      error: error.message
    });
  }
});

// Update a book
router.put("/:id", protectAdmin, async (req, res) => {
  try {
    const book = await Book.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    res.status(200).json({
      message: "Book updated successfully",
      book
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to update book",
      error: error.message
    });
  }
});
// Delete a book
router.delete("/:id", protectAdmin, async (req, res) => {
  try {
    const book = await Book.findByIdAndDelete(req.params.id);

    if (!book) {
      return res.status(404).json({
        message: "Book not found"
      });
    }

    res.status(200).json({
      message: "Book deleted successfully"
    });
  } catch (error) {
    res.status(500).json({
      message: "Failed to delete book",
      error: error.message
    });
  }
});
module.exports = router;