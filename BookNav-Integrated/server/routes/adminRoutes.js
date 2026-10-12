const express = require("express");
const bcrypt = require("bcryptjs");
const Admin = require("../models/Admin");

const router = express.Router();

// Simple email regex for validation
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Admin Registration (Guarded: allows first bootstrap admin, otherwise requires existing admin session or ADMIN_SETUP_TOKEN)
router.post("/register", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // Input Validation
    if (!username || typeof username !== "string" || username.trim().length < 3 || username.trim().length > 50) {
      return res.status(400).json({
        message: "Username must be a valid string between 3 and 50 characters"
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

    // Authorization check: First admin can bootstrap. Subsequent admins require existing admin or setup token.
    const adminCount = await Admin.countDocuments();
    if (adminCount > 0) {
      const hasAdminSession = req.session && req.session.admin && req.session.admin.role === "admin";
      const setupToken = req.headers["x-admin-setup-token"];
      const hasValidToken = process.env.ADMIN_SETUP_TOKEN && setupToken && setupToken === process.env.ADMIN_SETUP_TOKEN;

      if (!hasAdminSession && !hasValidToken) {
        return res.status(403).json({
          message: "Registration restricted: Authorization required to create additional admin accounts"
        });
      }
    }

    // Check if admin already exists
    const existingAdmin = await Admin.findOne({
      $or: [{ username: cleanUsername }, { email: cleanEmail }]
    });

    if (existingAdmin) {
      return res.status(400).json({
        message: "Admin already exists with this username or email"
      });
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create admin
    const admin = await Admin.create({
      username: cleanUsername,
      email: cleanEmail,
      password: hashedPassword
    });

    res.status(201).json({
      message: "Admin registered successfully",
      admin: {
        id: admin._id,
        username: admin.username,
        email: admin.email
      }
    });
  } catch (error) {
    res.status(500).json({
      message: "Admin registration failed",
      error: error.message
    });
  }
});

// Admin Login
router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password || typeof email !== "string" || typeof password !== "string") {
      return res.status(400).json({
        message: "Email and password are required"
      });
    }

    const cleanEmail = email.trim().toLowerCase();

    // Find admin
    const admin = await Admin.findOne({ email: cleanEmail });

    if (!admin) {
      return res.status(401).json({
        message: "Invalid email or password"
      });
    }

    // Check password
    const isPasswordCorrect = await bcrypt.compare(
      password,
      admin.password
    );

    if (!isPasswordCorrect) {
      return res.status(401).json({
        message: "Invalid email or password"
      });
    }

    // Create admin session (prevent session fixation)
    const adminSessionData = {
      id: admin._id.toString(),
      username: admin.username,
      email: admin.email,
      role: "admin"
    };

    if (req.session.regenerate) {
      req.session.regenerate((err) => {
        if (err) {
          return res.status(500).json({ message: "Session generation failed", error: err.message });
        }
        req.session.admin = adminSessionData;
        return res.status(200).json({
          message: "Admin login successful",
          admin: adminSessionData
        });
      });
    } else {
      req.session.admin = adminSessionData;
      return res.status(200).json({
        message: "Admin login successful",
        admin: adminSessionData
      });
    }
  } catch (error) {
    res.status(500).json({
      message: "Admin login failed",
      error: error.message
    });
  }
});

// Check current admin session
router.get("/session", (req, res) => {
  if (req.session && req.session.admin) {
    return res.status(200).json({
      loggedIn: true,
      admin: req.session.admin
    });
  }

  res.status(401).json({
    loggedIn: false,
    message: "No active admin session"
  });
});

// Admin Logout
router.post("/logout", (req, res) => {
  req.session.destroy((error) => {
    if (error) {
      return res.status(500).json({
        message: "Logout failed"
      });
    }

    res.clearCookie("connect.sid");

    res.status(200).json({
      message: "Admin logged out successfully"
    });
  });
});

module.exports = router;