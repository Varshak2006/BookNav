// // import { useState } from "react";

// // function UserRegister({ onRegister }) {
// //   const [formData, setFormData] = useState({
// //     username: "",
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
// //         "http://localhost:5000/api/user/register",
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
// //         alert("Registration successful!");

// //         onRegister();
// //       } else {
// //         alert(data.message || "Registration failed");
// //       }
// //     } catch (error) {
// //       console.error("Registration error:", error);
// //       alert("Could not connect to the backend");
// //     }
// //   };

// //   return (
// //     <div>
// //       <h1>BookNav User Registration</h1>

// //       <form onSubmit={handleSubmit}>
// //         <input
// //           type="text"
// //           name="username"
// //           placeholder="Username"
// //           value={formData.username}
// //           onChange={handleChange}
// //         />

// //         <br />
// //         <br />

// //         <input
// //           type="email"
// //           name="email"
// //           placeholder="Email"
// //           value={formData.email}
// //           onChange={handleChange}
// //         />

// //         <br />
// //         <br />

// //         <input
// //           type="password"
// //           name="password"
// //           placeholder="Password"
// //           value={formData.password}
// //           onChange={handleChange}
// //         />

// //         <br />
// //         <br />

// //         <button type="submit">
// //           Register
// //         </button>
// //       </form>
// //     </div>
// //   );
// // }

// // export default UserRegister;






// import { useState } from "react";

// function UserRegister({ onRegister }) {
//   const [formData, setFormData] = useState({
//     username: "",
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
//         "http://localhost:5000/api/user/register",
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
//         alert("Registration successful!");

//         onRegister();
//       } else {
//         alert(data.message || "Registration failed");
//       }
//     } catch (error) {
//       console.error("Registration error:", error);
//       alert("Could not connect to the backend");
//     }
//   };

//   return (
//     <div className="auth-page">
//       <div className="auth-brand-panel">
//         <div className="book-icon">▢</div>

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
//           <h2>Create Account</h2>

//           <p className="auth-subtitle">
//             Join the BookNav library
//           </p>

//           <form onSubmit={handleSubmit}>
//             <label>Username</label>

//             <input
//               type="text"
//               name="username"
//               placeholder="Enter your username"
//               value={formData.username}
//               onChange={handleChange}
//               required
//             />

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
//               placeholder="Create a password"
//               value={formData.password}
//               onChange={handleChange}
//               required
//             />

//             <button
//               type="submit"
//               className="auth-submit-button"
//             >
//               Create Account →
//             </button>
//           </form>

//           <div className="auth-divider">
//             <span>OR</span>
//           </div>

//           <p className="auth-bottom-text">
//             Start exploring your library with BookNav
//           </p>
//         </div>
//       </div>
//     </div>
//   );
// }

// export default UserRegister;


import { useState } from "react";

function UserRegister({
  onRegister,
  onBack,
  onAdminLogin
}) {
  const [formData, setFormData] = useState({
    username: "",
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
        "http://localhost:5000/api/user/register",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(formData)
        }
      );

      const data = await response.json();

      if (response.ok) {
        alert("Registration successful!");

        onRegister();
      } else {
        alert(data.message || "Registration failed");
      }
    } catch (error) {
      console.error("Registration error:", error);
      alert("Could not connect to the backend");
    }
  };

  return (
    <div className="auth-page">

      {/* LEFT BRAND PANEL */}
      <div className="auth-brand-panel">

        <div className="book-icon">
          ▢
        </div>

        <h1>BookNav</h1>

        <p>
          Find. Explore. Navigate.
        </p>

        <div className="brand-message">
          Your library,
          <br />
          now smarter.
        </div>

      </div>

      {/* RIGHT REGISTER PANEL */}
      <div className="auth-form-panel">

        <div className="auth-card">

          <h2>
            Create Account
          </h2>

          <p className="auth-subtitle">
            Join the BookNav library
          </p>

          <form onSubmit={handleSubmit}>

            <label>
              Username
            </label>

           <div className="input-wrapper">
  <span className="input-icon">♙</span>

  <input 
    type="text" 
    name="username" 
    placeholder="Enter your username" 
    value={formData.username} 
    onChange={handleChange} 
    required 
  />
</div>

            <label>
              Email address
            </label>

           <div className="input-wrapper">
  <span className="input-icon">✉</span>

  <input 
    type="email" 
    name="email" 
    placeholder="Enter your email" 
    value={formData.email} 
    onChange={handleChange} 
    required 
  />
</div>
            <label>
              Password
            </label>

            <div className="input-wrapper">
  <span className="input-icon">♙</span>

  <input 
    type="password" 
    name="password" 
    placeholder="Create a password" 
    value={formData.password} 
    onChange={handleChange} 
    required 
  />
</div>

            <button
              type="submit"
              className="auth-submit-button"
            >
              Sign Up →
            </button>

          </form>

          {/* OR */}
          <div className="auth-divider">
            <span>OR</span>
          </div>

          {/* BACK TO LOGIN */}
          <div className="auth-admin-section">
            <span>
              Already have an account?
            </span>

            <button
              type="button"
              className="admin-login-link"
              onClick={onBack}
            >
              Login
            </button>
          </div>

          {/* ADMIN LOGIN */}
          <button
            type="button"
            className="create-account-button"
            onClick={onAdminLogin}
          >
            Admin Login
          </button>

        </div>

      </div>

    </div>
  );
}

export default UserRegister;