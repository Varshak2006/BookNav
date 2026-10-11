const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const User = require("../models/User");

const router = express.Router();

// User Registration
router.post("/register", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    const existingUser = await User.findOne({
      $or: [{ username }, { email }]
    });

    if (existingUser) {
      return res.status(400).json({
        message: "User already exists with this username or email"
      });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await User.create({
      username,
      email,
      password: hashedPassword
    });

    res.status(201).json({
      message: "User registered successfully",
      user: {
        id: user._id,
        username: user.username,
        email: user.email
      }
    });
  } catch (error) {
    res.status(500).json({
      message: "User registration failed",
      error: error.message
    });
  }
});

// User Login
router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;

    const user = await User.findOne({ email });

    if (!user) {
      return res.status(401).json({
        message: "Invalid email or password"
      });
    }

    const isPasswordCorrect = await bcrypt.compare(
      password,
      user.password
    );

    if (!isPasswordCorrect) {
      return res.status(401).json({
        message: "Invalid email or password"
      });
    }

    // Create user session
    req.session.user = {
      id: user._id.toString(),
      username: user.username,
      email: user.email,
      role: "user"
    };

    res.status(200).json({
      message: "User login successful",
      user: {
        id: user._id,
        username: user.username,
        email: user.email
      }
    });
  } catch (error) {
    res.status(500).json({
      message: "User login failed",
      error: error.message
    });
  }
});

// Check current user session
router.get("/session", (req, res) => {
  if (req.session.user) {
    return res.status(200).json({
      loggedIn: true,
      user: req.session.user
    });
  }

  res.status(401).json({
    loggedIn: false,
    message: "No active session"
  });
});

// User Logout
router.post("/logout", (req, res) => {
  req.session.destroy((error) => {
    if (error) {
      return res.status(500).json({
        message: "Logout failed"
      });
    }

    res.clearCookie("connect.sid");

    res.status(200).json({
      message: "User logged out successfully"
    });
  });
});
module.exports = router;