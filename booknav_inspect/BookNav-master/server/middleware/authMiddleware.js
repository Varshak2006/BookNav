// const jwt = require("jsonwebtoken");

// const protectAdmin = (req, res, next) => {
//   try {
//     const authHeader = req.headers.authorization;

//     if (!authHeader || !authHeader.startsWith("Bearer ")) {
//       return res.status(401).json({
//         message: "Not authorized. Admin token required."
//       });
//     }

//     const token = authHeader.split(" ")[1];

//     const decoded = jwt.verify(
//       token,
//       process.env.JWT_SECRET
//     );

//     if (decoded.role !== "admin") {
//       return res.status(403).json({
//         message: "Access denied. Admin only."
//       });
//     }

//     req.admin = decoded;

//     next();
//   } catch (error) {
//     return res.status(401).json({
//       message: "Invalid or expired admin token"
//     });
//   }
// };

// module.exports = protectAdmin;

const protectAdmin = (req, res, next) => {
  try {
    if (!req.session || !req.session.admin) {
      return res.status(401).json({
        message: "Not authorized. Admin session required."
      });
    }

    if (req.session.admin.role !== "admin") {
      return res.status(403).json({
        message: "Access denied. Admin only."
      });
    }

    req.admin = req.session.admin;

    next();
  } catch (error) {
    return res.status(401).json({
      message: "Invalid admin session"
    });
  }
};

module.exports = protectAdmin;