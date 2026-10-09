
const mongoose = require("mongoose");
require("dotenv").config();
const Book = require("./models/Book");

const books = [
  {
    title: "The Alchemist",
    author: "Paulo Coelho",
    category: "Fiction",
    description: "A shepherd travels in search of treasure and discovers lessons about dreams and purpose.",
    shelf: "1",
    rack: "1",
    location: "Ground Floor"
  },
  {
    title: "To Kill a Mockingbird",
    author: "Harper Lee",
    category: "Fiction",
    description: "A novel exploring justice, empathy, and prejudice in a small American town.",
    shelf: "1",
    rack: "2",
    location: "Ground Floor"
  },
  {
    title: "1984",
    author: "George Orwell",
    category: "Dystopian Fiction",
    description: "A dystopian novel about surveillance, propaganda, and authoritarian control.",
    shelf: "1",
    rack: "3",
    location: "Ground Floor"
  },
  {
    title: "Pride and Prejudice",
    author: "Jane Austen",
    category: "Classic Literature",
    description: "A classic novel about relationships, social expectations, and personal growth.",
    shelf: "1",
    rack: "4",
    location: "Ground Floor"
  },
  {
    title: "The Great Gatsby",
    author: "F. Scott Fitzgerald",
    category: "Classic Literature",
    description: "A story of ambition, wealth, and the American Dream in the 1920s.",
    shelf: "1",
    rack: "5",
    location: "Ground Floor"
  },
  {
    title: "Atomic Habits",
    author: "James Clear",
    category: "Self-Help",
    description: "Practical strategies for building good habits and changing everyday behavior.",
    shelf: "2",
    rack: "1",
    location: "First Floor"
  },
  {
    title: "Deep Work",
    author: "Cal Newport",
    category: "Productivity",
    description: "A guide to focused work and reducing distractions in demanding tasks.",
    shelf: "2",
    rack: "2",
    location: "First Floor"
  },
  {
    title: "Ikigai",
    author: "Hector Garcia and Francesc Miralles",
    category: "Self-Help",
    description: "Explores ideas about purpose, daily routines, and well-being inspired by Japanese culture.",
    shelf: "2",
    rack: "3",
    location: "First Floor"
  },
  {
    title: "Think and Grow Rich",
    author: "Napoleon Hill",
    category: "Personal Development",
    description: "A classic personal-development book about goals, persistence, and achievement.",
    shelf: "2",
    rack: "4",
    location: "First Floor"
  },
  {
    title: "The Psychology of Money",
    author: "Morgan Housel",
    category: "Finance",
    description: "Stories and lessons about how people think about money, risk, and wealth.",
    shelf: "2",
    rack: "5",
    location: "First Floor"
  },
  {
    title: "Clean Code",
    author: "Robert C. Martin",
    category: "Programming",
    description: "Principles and examples for writing readable, maintainable software.",
    shelf: "3",
    rack: "1",
    location: "Second Floor"
  },
  {
    title: "The Pragmatic Programmer",
    author: "David Thomas and Andrew Hunt",
    category: "Software Engineering",
    description: "Practical advice on software craftsmanship, problem-solving, and professional development.",
    shelf: "3",
    rack: "2",
    location: "Second Floor"
  },
  {
    title: "Introduction to Algorithms",
    author: "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, and Clifford Stein",
    category: "Algorithms",
    description: "A comprehensive textbook covering algorithms, data structures, and algorithm analysis.",
    shelf: "3",
    rack: "3",
    location: "Second Floor"
  },
  {
    title: "The C Programming Language",
    author: "Brian W. Kernighan and Dennis M. Ritchie",
    category: "Programming",
    description: "A foundational book introducing the C programming language and its core concepts.",
    shelf: "3",
    rack: "4",
    location: "Second Floor"
  },
  {
    title: "Eloquent JavaScript",
    author: "Marijn Haverbeke",
    category: "Web Development",
    description: "An introduction to JavaScript, programming concepts, and browser-based development.",
    shelf: "3",
    rack: "5",
    location: "Second Floor"
  },
  {
    title: "You Don't Know JS Yet",
    author: "Kyle Simpson",
    category: "JavaScript",
    description: "A book series exploring JavaScript fundamentals and language behavior in depth.",
    shelf: "4",
    rack: "1",
    location: "Second Floor"
  },
  {
    title: "Computer Networking: A Top-Down Approach",
    author: "James F. Kurose and Keith W. Ross",
    category: "Computer Networks",
    description: "Explains computer networking concepts through applications and network protocols.",
    shelf: "4",
    rack: "2",
    location: "Second Floor"
  },
  {
    title: "Operating System Concepts",
    author: "Abraham Silberschatz, Peter B. Galvin, and Greg Gagne",
    category: "Operating Systems",
    description: "A textbook covering processes, memory management, file systems, and operating-system design.",
    shelf: "4",
    rack: "3",
    location: "Second Floor"
  },
  {
    title: "Database System Concepts",
    author: "Abraham Silberschatz, Henry F. Korth, and S. Sudarshan",
    category: "Databases",
    description: "Covers relational databases, SQL, transactions, indexing, and database design.",
    shelf: "4",
    rack: "4",
    location: "Second Floor"
  },
  {
    title: "Artificial Intelligence: A Modern Approach",
    author: "Stuart Russell and Peter Norvig",
    category: "Artificial Intelligence",
    description: "A comprehensive introduction to AI methods, reasoning, learning, and intelligent agents.",
    shelf: "4",
    rack: "5",
    location: "Second Floor"
  },
  {
    title: "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow",
    author: "Aurélien Géron",
    category: "Machine Learning",
    description: "Practical guidance on building machine-learning models using popular Python libraries.",
    shelf: "5",
    rack: "1",
    location: "Third Floor"
  },
  {
    title: "The Selfish Gene",
    author: "Richard Dawkins",
    category: "Science",
    description: "Explores evolution and natural selection through the perspective of genes.",
    shelf: "5",
    rack: "2",
    location: "Third Floor"
  },
  {
    title: "A Brief History of Time",
    author: "Stephen Hawking",
    category: "Physics",
    description: "Introduces major ideas about the universe, space, time, and cosmology.",
    shelf: "5",
    rack: "3",
    location: "Third Floor"
  },
  {
    title: "Wings of Fire",
    author: "A. P. J. Abdul Kalam and Arun Tiwari",
    category: "Autobiography",
    description: "The autobiography of A. P. J. Abdul Kalam, describing his life and career.",
    shelf: "5",
    rack: "4",
    location: "Third Floor"
  },
  {
    title: "The Discovery of India",
    author: "Jawaharlal Nehru",
    category: "History",
    description: "A reflection on India's history, culture, and civilizational development.",
    shelf: "5",
    rack: "5",
    location: "Third Floor"
  }
];

async function seedBooks() {
  try {
    if (!process.env.MONGO_URI) {
      throw new Error("MONGO_URI is missing from the server .env file");
    }

    await mongoose.connect(process.env.MONGO_URI);
    console.log("Connected to MongoDB.");

    const result = await Book.insertMany(books, { ordered: true });

    console.log(`Successfully inserted ${result.length} books.`);
  } catch (error) {
    console.error("Book insertion failed:", error.message);
  } finally {
    await mongoose.disconnect();
    console.log("MongoDB connection closed.");
  }
}

seedBooks();