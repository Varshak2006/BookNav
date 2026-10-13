import { useState } from "react";
import { API_BASE_URL } from "../config/api";

function AdminLogin({ onLogin, onBack, onRegister }) {
  const [formData, setFormData] = useState({
    email: "",
    password: ""
  });

  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${API_BASE_URL}/admin/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        alert("Admin login successful!");
        onLogin();
      } else {
        alert(data.message || "Login failed");
      }
    } catch (error) {
      console.error("Login error:", error);
      alert("Could not connect to the backend");
    }
  };

  return (
    <div className="auth-page">
      {/* LEFT BRAND PANEL */}
      <div className="auth-brand-panel">
        <div className="book-icon">▢</div>
        <h1>BookNav</h1>
        <p>Library Management System</p>
        <div className="brand-message">
          Manage your library,
          <br />
          smarter and simpler.
        </div>
      </div>

      {/* RIGHT ADMIN LOGIN PANEL */}
      <div className="auth-form-panel">
        <div className="auth-card">
          <div className="admin-badge">ADMIN PORTAL</div>

          <h2>Welcome Back!</h2>
          <p className="auth-subtitle">Sign in to manage BookNav</p>

          <form onSubmit={handleSubmit}>
            <label>Admin email</label>
            <input
              type="email"
              name="email"
              placeholder="Enter admin email"
              value={formData.email}
              onChange={handleChange}
              required
            />

            <label>Password</label>
            <div className="input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="Enter password"
                value={formData.password}
                onChange={handleChange}
                required
              />
              <button
                type="button"
                className="password-eye"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? "👁️" : "🙈"}
              </button>
            </div>

            <button type="submit" className="auth-submit-button">
              Admin Login →
            </button>
          </form>

          <div className="auth-divider">
            <span>OR</span>
          </div>

          <button
            type="button"
            className="create-account-button"
            onClick={onBack}
          >
            Back to User Login
          </button>

          <div className="auth-admin-section">
            <span>Don't have an account?</span>
            <button
              type="button"
              className="admin-login-link"
              onClick={onRegister}
            >
              Create Account
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminLogin;