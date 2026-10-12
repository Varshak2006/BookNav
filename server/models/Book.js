const mongoose = require("mongoose");

const bookSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: [true, "Book title is required"],
      trim: true,
      minlength: [1, "Book title cannot be empty"]
    },

    author: {
      type: String,
      required: [true, "Author is required"],
      trim: true,
      minlength: [1, "Author cannot be empty"]
    },

    category: {
      type: String,
      required: [true, "Category is required"],
      trim: true,
      minlength: [1, "Category cannot be empty"]
    },

    description: {
      type: String,
      default: "",
      trim: true
    },

    keywords: {
      type: String,
      default: "",
      trim: true
    },

    shelf: {
      type: String,
      required: [true, "Shelf is required"],
      trim: true,
      minlength: [1, "Shelf cannot be empty"]
    },

    rack: {
      type: String,
      required: [true, "Rack is required"],
      trim: true,
      minlength: [1, "Rack cannot be empty"]
    },

    location: {
      type: String,
      default: "",
      trim: true
    }
  },
  {
    timestamps: true
  }
);

const Book = mongoose.model("Book", bookSchema);

module.exports = Book;