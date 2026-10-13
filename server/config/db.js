const mongoose = require("mongoose");

function getMongoUri() {
  return process.env.MONGO_URI || "mongodb://localhost:27017/book";
}

const connectDB = async (customUri = null) => {
  try {
    const uri = customUri || getMongoUri();
    await mongoose.connect(uri);
    const maskedUri = uri.replace(/\/\/[^:]+:[^@]+@/, "//***:***@");
    console.log(`MongoDB connected successfully to ${maskedUri}`);
    return mongoose.connection;
  } catch (error) {
    console.error("MongoDB connection failed:", error.message);
    if (process.env.NODE_ENV !== "test") {
      process.exit(1);
    }
    throw error;
  }
};

module.exports = { connectDB, getMongoUri };