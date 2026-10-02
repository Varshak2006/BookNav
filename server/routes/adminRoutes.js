// const express = require("express");
// const bcrypt = require("bcryptjs");
// const jwt = require("jsonwebtoken");
// const Admin = require("../models/Admin");

// const router = express.Router();

// // Admin Registration
// router.post("/register", async (req, res) => {
//   try {
//     const { username, email, password } = req.body;

//     // Check if admin already exists
//     const existingAdmin = await Admin.findOne({
//       $or: [{ username }, { email }]
//     });

//     if (existingAdmin) {
//       return res.status(400).json({
//         message: "Admin already exists with this username or email"
//       });
//     }

//     // Hash password
//     const hashedPassword = await bcrypt.hash(password, 10);

//     // Create admin
//     const admin = await Admin.create({
//       username,
//       email,
//       password: hashedPassword
//     });

//     res.status(201).json({
//       message: "Admin registered successfully",
//       admin: {
//         id: admin._id,
//         username: admin.username,
//         email: admin.email
//       }
//     });
//   } catch (error) {
//     res.status(500).json({
//       message: "Admin registration failed",
//       error: error.message
//     });
//   }
// });

// // Admin Login
// router.post("/login", async (req, res) => {
//   try {
//     const { email, password } = req.body;

//     // Find admin
//     const admin = await Admin.findOne({ email });

//     if (!admin) {
//       return res.status(401).json({
//         message: "Invalid email or password"
//       });
//     }

//     // Check password
//     const isPasswordCorrect = await bcrypt.compare(
//       password,
//       admin.password
//     );

//     if (!isPasswordCorrect) {
//       return res.status(401).json({
//         message: "Invalid email or password"
//       });
//     }

//     // Create admin session
//     req.session.admin = {
//       id: admin._id.toString(),
//       username: admin.username,
//       email: admin.email,
//       role: "admin"
//     };

//     res.status(200).json({
//       message: "Admin login successful",
//       admin: {
//         id: admin._id,
//         username: admin.username,
//         email: admin.email
//       }
//     });
//   } catch (error) {
//     res.status(500).json({
//       message: "Admin login failed",
//       error: error.message
//     });
//   }
// });
// // Check current admin session
// router.get("/session", (req, res) => {
//   if (req.session.admin) {
//     return res.status(200).json({
//       loggedIn: true,
//       admin: req.session.admin
//     });
//   }

//   res.status(401).json({
//     loggedIn: false,
//     message: "No active admin session"
//   });
// });
// module.exports=router;


const express = require("express");
const bcrypt = require("bcryptjs");
const Admin = require("../models/Admin");

const router = express.Router();

// Admin Registration
router.post("/register", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // Check if admin already exists
    const existingAdmin = await Admin.findOne({
      $or: [{ username }, { email }]
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
      username,
      email,
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

    // Find admin
    const admin = await Admin.findOne({ email });

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

    // Create admin session
    req.session.admin = {
      id: admin._id.toString(),
      username: admin.username,
      email: admin.email,
      role: "admin"
    };

    res.status(200).json({
      message: "Admin login successful",
      admin: {
        id: admin._id,
        username: admin.username,
        email: admin.email
      }
    });
  } catch (error) {
    res.status(500).json({
      message: "Admin login failed",
      error: error.message
    });
  }
});

// Check current admin session
router.get("/session", (req, res) => {
  if (req.session.admin) {
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