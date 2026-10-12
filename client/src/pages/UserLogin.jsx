// // // // import { useState } from "react";

// // // // function UserLogin({ onLogin }) {
// // // //   const [formData, setFormData] = useState({
// // // //     email: "",
// // // //     password: ""
// // // //   });

// // // //   const handleChange = (e) => {
// // // //     setFormData({
// // // //       ...formData,
// // // //       [e.target.name]: e.target.value
// // // //     });
// // // //   };

// // // //   const handleSubmit = async (e) => {
// // // //     e.preventDefault();

// // // //     try {
// // // //       const response = await fetch(
// // // //         "http://localhost:5000/api/user/login",
// // // //         {
// // // //           method: "POST",
// // // //           headers: {
// // // //             "Content-Type": "application/json"
// // // //           },
// // // //           body: JSON.stringify(formData)
// // // //         }
// // // //       );

// // // //       const data = await response.json();

// // // //       if (response.ok) {
// // // //         alert("Login successful!");

// // // //         localStorage.setItem("userToken", data.token);

// // // //         console.log("User:", data.user);

// // // //         onLogin();
// // // //       } else {
// // // //         alert(data.message || "Login failed");
// // // //       }
// // // //     } catch (error) {
// // // //       console.error("Login error:", error);
// // // //       alert("Could not connect to the backend");
// // // //     }
// // // //   };

// // // //   return (
// // // //     <div>
// // // //       <h1>BookNav User Login</h1>

// // // //       <form onSubmit={handleSubmit}>
// // // //         <input
// // // //           type="email"
// // // //           name="email"
// // // //           placeholder="Email"
// // // //           value={formData.email}
// // // //           onChange={handleChange}
// // // //         />

// // // //         <br />
// // // //         <br />

// // // //         <input
// // // //           type="password"
// // // //           name="password"
// // // //           placeholder="Password"
// // // //           value={formData.password}
// // // //           onChange={handleChange}
// // // //         />

// // // //         <br />
// // // //         <br />

// // // //         <button type="submit">
// // // //           Login
// // // //         </button>
// // // //       </form>
// // // //     </div>
// // // //   );
// // // // }

// // // // export default UserLogin;



// // // import { useState } from "react";

// // // function UserLogin({ onLogin }) {
// // //   const [formData, setFormData] = useState({
// // //     email: "",
// // //     password: ""
// // //   });

// // //   const handleChange = (e) => {
// // //     setFormData({
// // //       ...formData,
// // //       [e.target.name]: e.target.value
// // //     });
// // //   };

// // //   const handleSubmit = async (e) => {
// // //     e.preventDefault();

// // //     try {
// // //       const response = await fetch(
// // //         "http://localhost:5000/api/user/login",
// // //         {
// // //           method: "POST",
// // //           headers: {
// // //             "Content-Type": "application/json"
// // //           },
// // //           body: JSON.stringify(formData)
// // //         }
// // //       );

// // //       const data = await response.json();

// // //       if (response.ok) {
// // //         alert("Login successful!");

// // //         localStorage.setItem("userToken", data.token);

// // //         console.log("User:", data.user);

// // //         onLogin();
// // //       } else {
// // //         alert(data.message || "Login failed");
// // //       }
// // //     } catch (error) {
// // //       console.error("Login error:", error);
// // //       alert("Could not connect to the backend");
// // //     }
// // //   };

// // //   return (
// // //     <div className="auth-page">
// // //       <div className="auth-brand-panel">
// // //         <div className="book-icon">▢</div>

// // //         <h1>BookNav</h1>

// // //         <p>Find. Explore. Navigate.</p>

// // //         <div className="brand-message">
// // //           Your library,
// // //           <br />
// // //           now smarter.
// // //         </div>
// // //       </div>

// // //       <div className="auth-form-panel">
// // //         <div className="auth-card">
// // //           <h2>Welcome Back!</h2>

// // //           <p className="auth-subtitle">
// // //             Sign in to your account
// // //           </p>

// // //           <form onSubmit={handleSubmit}>
// // //             <label>Email address</label>

// // //             <input
// // //               type="email"
// // //               name="email"
// // //               placeholder="Enter your email"
// // //               value={formData.email}
// // //               onChange={handleChange}
// // //               required
// // //             />

// // //             <label>Password</label>

// // //             <input
// // //               type="password"
// // //               name="password"
// // //               placeholder="Enter your password"
// // //               value={formData.password}
// // //               onChange={handleChange}
// // //               required
// // //             />

// // //             <button
// // //               type="submit"
// // //               className="auth-submit-button"
// // //             >
// // //               Login →
// // //             </button>
// // //           </form>

// // //           <div className="auth-divider">
// // //             <span>OR</span>
// // //           </div>

// // //           <p className="auth-bottom-text">
// // //             Welcome to BookNav
// // //           </p>
// // //         </div>
// // //       </div>
// // //     </div>
// // //   );
// // // }

// // // export default UserLogin;





// // import { useState } from "react";

// // function UserLogin({ onLogin, onRegister, onAdminLogin }) {
// //   const [formData, setFormData] = useState({
// //     email: "",
// //     password: ""
// //   });

// //   const handleChange = (e) => {
// //     setFormData({
// //       ...formData,
// //       [e.target.name]: e.target.value
// //     });
// //   };

// //   const handleSubmit = async (e) => {
// //     e.preventDefault();

// //     try {
// //       const response = await fetch(
// //         "http://localhost:5000/api/user/login",
// //         {
// //           method: "POST",
// //           headers: {
// //             "Content-Type": "application/json"
// //           },
// //           body: JSON.stringify(formData)
// //         }
// //       );

// //       const data = await response.json();

// //       if (response.ok) {
// //         alert("Login successful!");

// //         localStorage.setItem("userToken", data.token);

// //         console.log("User:", data.user);

// //         onLogin();
// //       } else {
// //         alert(data.message || "Login failed");
// //       }
// //     } catch (error) {
// //       console.error("Login error:", error);
// //       alert("Could not connect to the backend");
// //     }
// //   };

// //   return (
// //     <div className="auth-page">

// //       {/* LEFT BRAND PANEL */}
// //       <div className="auth-brand-panel">

// //         <div className="book-icon">
// //           ▢
// //         </div>

// //         <h1>BookNav</h1>

// //         <p>
// //           Find. Explore. Navigate.
// //         </p>

// //         <div className="brand-message">
// //           Your library,
// //           <br />
// //           now smarter.
// //         </div>

// //       </div>

// //       {/* RIGHT LOGIN PANEL */}
// //       <div className="auth-form-panel">

// //         <div className="auth-card">

// //           <h2>
// //             Welcome Back!
// //           </h2>

// //           <p className="auth-subtitle">
// //             Sign in to your account
// //           </p>

// //           <form onSubmit={handleSubmit}>

// //             <label>
// //               Email address
// //             </label>

// //             <input
// //               type="email"
// //               name="email"
// //               placeholder="Enter your email"
// //               value={formData.email}
// //               onChange={handleChange}
// //               required
// //             />

// //             <label>
// //               Password
// //             </label>

// //             <input
// //               type="password"
// //               name="password"
// //               placeholder="Enter your password"
// //               value={formData.password}
// //               onChange={handleChange}
// //               required
// //             />

// //             <button
// //               type="submit"
// //               className="auth-submit-button"
// //             >
// //               Login →
// //             </button>

// //           </form>

// //           {/* OR */}
// //           <div className="auth-divider">
// //             <span>OR</span>
// //           </div>

// //           {/* REGISTER BUTTON */}
// //           <button
// //             type="button"
// //             className="create-account-button"
// //             onClick={onRegister}
// //           >
// //             Create a new account
// //           </button>

// //           {/* ADMIN */}
// //           <div className="auth-admin-section">

// //             <span>
// //               Admin?
// //             </span>

// //             <button
// //               type="button"
// //               className="admin-login-link"
// //               onClick={onAdminLogin}
// //             >
// //               Login
// //             </button>

// //           </div>

// //         </div>

// //       </div>

// //     </div>
// //   );
// // }

// // export default UserLogin;

// import { useState } from "react";

// function UserLogin({ onLogin, onRegister, onAdminLogin }) {
//   const [formData, setFormData] = useState({
//     email: "",
//     password: ""
//   });

//   const handleChange = (e) => {
//     setFormData({
//       ...formData,
//       [e.target.name]: e.target.value
//     });
//   };

//   const handleSubmit = async (e) => {
//     e.preventDefault();

//     try {
//       const response = await fetch(
//         "http://localhost:5000/api/user/login",
//         {
//           method: "POST",
//           headers: {
//             "Content-Type": "application/json"
//           },
//           body: JSON.stringify(formData)
//         }
//       );

//       const data = await response.json();

//       if (response.ok) {
//         alert("Login successful!");

//         localStorage.setItem("userToken", data.token);

//         onLogin();
//       } else {
//         alert(data.message || "Login failed");
//       }
//     } catch (error) {
//       console.error("Login error:", error);
//       alert("Could not connect to the backend");
//     }
//   };

//   return (
//     <div className="auth-page">

//       <div className="auth-brand-panel">

//         <div className="book-icon">
//           ▢
//         </div>

//         <h1>BookNav</h1>

//         <p>Find. Explore. Navigate.</p>

//         <div className="brand-message">
//           Your library,
//           <br />
//           now smarter.
//         </div>

//       </div>

//       <div className="auth-form-panel">

//         <div className="auth-card">

//           <h2>Welcome Back!</h2>

//           <p className="auth-subtitle">
//             Sign in to your account
//           </p>

//           <form onSubmit={handleSubmit}>

//             <label>Email address</label>

//             <input
//               type="email"
//               name="email"
//               placeholder="Enter your email"
//               value={formData.email}
//               onChange={handleChange}
//               required
//             />

//             <label>Password</label>

//             <input
//               type="password"
//               name="password"
//               placeholder="Enter your password"
//               value={formData.password}
//               onChange={handleChange}
//               required
//             />

//             <button
//               type="submit"
//               className="auth-submit-button"
//             >
//               Login →
//             </button>

//           </form>

//           <div className="auth-divider">
//             <span>OR</span>
//           </div>

//           <button
//             type="button"
//             className="create-account-button"
//             onClick={onRegister}
//           >
//             Create a new account
//           </button>

//           <div className="auth-admin-section">
//             <span>Admin?</span>

//             <button
//               type="button"
//               className="admin-login-link"
//               onClick={onAdminLogin}
//             >
//               Login
//             </button>
//           </div>

//         </div>

//       </div>

//     </div>
//   );
// }

// export default UserLogin;


import { useState } from "react";

function UserLogin({ onLogin, onRegister, onAdminLogin }) {
  const [formData, setFormData] = useState({
    email: "",
    password: ""
  });

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(
        "http://localhost:5000/api/user/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          credentials: "include",
          body: JSON.stringify(formData)
        }
      );

      const data = await response.json();

      if (response.ok) {
        alert("Login successful!");
        // localStorage.setItem("userToken", data.token);
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
      <div className="auth-brand-panel">

        <div className="book-icon">
          <span>▱</span>
        </div>

        <h1>BookNav</h1>

        <p>Find. Explore. Navigate.</p>

        <div className="brand-message">
          Your library,
          <br />
          now smarter.
        </div>

      </div>

      <div className="auth-form-panel">

        <div className="auth-card">

          <h2>Welcome Back!</h2>

          <p className="auth-subtitle">
            Sign in to your account
          </p>

          <form onSubmit={handleSubmit}>

            <label>Email address</label>

            <div className="input-wrapper">
              <span className="input-icon">✉</span>

              <input
                type="email"
                name="email"
                placeholder="Email address"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>

            <label>Password</label>

            <div className="input-wrapper">
              <span className="input-icon">♧</span>

              <input
                type="password"
                name="password"
                placeholder="Password"
                value={formData.password}
                onChange={handleChange}
                required
              />

              <span className="password-eye">◉</span>
            </div>

            <div className="login-options">

              <label className="remember-option">
                <input type="checkbox" />
                <span>Remember me</span>
              </label>

              <button
                type="button"
                className="forgot-password"
              >
                Forgot password?
              </button>

            </div>

            <button
              type="submit"
              className="auth-submit-button"
            >
              Login →
            </button>

          </form>

          <div className="auth-divider">
            <span>OR</span>
          </div>

          <button
            type="button"
            className="create-account-button"
            onClick={onRegister}
          >
            Create a new account
          </button>

          <div className="auth-admin-section">
            <span>Admin?</span>

            <button
              type="button"
              className="admin-login-link"
              onClick={onAdminLogin}
            >
              Login
            </button>
          </div>

        </div>

      </div>
    </div>
  );
}

export default UserLogin;