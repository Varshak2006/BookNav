const express = require("express");
const bcrypt = require("bcryptjs");
const User = require("../models/User");

const router = express.Router();

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// User Registration
router.post("/register", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    if (!username || typeof username !== "string" || username.trim().length < 3 || username.trim().length > 50) {
      return res.status(400).json({
        message: "Username must be between 3 and 50 characters"
      });
    }

    if (!email || typeof email !== "string" || !EMAIL_REGEX.test(email.trim()) || email.trim().length > 100) {
      return res.status(400).json({
        message: "A valid email address is required"
      });
    }

    if (!password || typeof password !== "string" || password.length < 6) {
      return res.status(400).json({
        message: "Password must be at least 6 characters long"
      });
    }

    const cleanUsername = username.trim();
    const cleanEmail = email.trim().toLowerCase();

    const existingUser = await User.findOne({
      $or: [{ username: cleanUsername }, { email: cleanEmail }]
    });

    if (existingUser) {
      return res.status(400).json({
        message: "User already exists with this username or email"
      });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await User.create({
      username: cleanUsername,
      email: cleanEmail,
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

    if (!email || !password || typeof email !== "string" || typeof password !== "string") {
      return res.status(400).json({
        message: "Email and password are required"
      });
    }

    const cleanEmail = email.trim().toLowerCase();

    const user = await User.findOne({ email: cleanEmail });

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

    const userSessionData = {
      id: user._id.toString(),
      username: user.username,
      email: user.email,
      role: "user"
    };

    if (req.session.regenerate) {
      req.session.regenerate((err) => {
        if (err) {
          return res.status(500).json({ message: "Session creation failed", error: err.message });
        }
        req.session.user = userSessionData;
        return res.status(200).json({
          message: "User login successful",
          user: {
            id: user._id,
            username: user.username,
            email: user.email
          }
        });
      });
    } else {
      req.session.user = userSessionData;
      return res.status(200).json({
        message: "User login successful",
        user: {
          id: user._id,
          username: user.username,
          email: user.email
        }
      });
    }
  } catch (error) {
    res.status(500).json({
      message: "User login failed",
      error: error.message
    });
  }
});

// Check current user session
router.get("/session", (req, res) => {
  if (req.session && req.session.user) {
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