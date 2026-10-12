// import { useEffect, useState } from "react";
// import "./App.css";

// import AdminLogin from "./pages/AdminLogin";
// import AdminBooks from "./pages/AdminBooks";
// import UserLogin from "./pages/UserLogin";
// import UserRegister from "./pages/UserRegister";
// import UserHome from "./pages/UserHome";

// function App() {
//   const [mode, setMode] = useState("user-login");

//  const [isUserLoggedIn, setIsUserLoggedIn] = useState(false);
// const [checkingSession, setCheckingSession] = useState(true);

//   const [isAdminLoggedIn, setIsAdminLoggedIn] = useState(
//     !!localStorage.getItem("adminToken")
//   );
// useEffect(() => {
//   const checkSession = async () => {
//     try {
//       const response = await fetch(
//         "http://localhost:5000/api/user/session",
//         {
//           credentials: "include"
//         }
//       );

//       if (response.ok) {
//         setIsUserLoggedIn(true);
//       } else {
//         setIsUserLoggedIn(false);
//       }
//     } catch (error) {
//       console.error("Session check failed:", error);
//       setIsUserLoggedIn(false);
//     } finally {
//       setCheckingSession(false);
//     }
//   };

//   checkSession();
// }, []);
// if (checkingSession) {
//   return <div>Checking session...</div>;
// }
//   if (isAdminLoggedIn) {
//     return <AdminBooks />;
//   }

//   if (isUserLoggedIn) {
//     return (
//       <div className="booknav-layout">

//         <aside className="booknav-sidebar">

//           <div className="sidebar-brand">
//             <div className="sidebar-logo">
//               ▣
//             </div>

//             <div>
//               <h2>BookNav</h2>
//               <span>Smart Library</span>
//             </div>
//           </div>

//           <nav className="sidebar-nav">

//             <button className="sidebar-link active">
//               <span>⌂</span>
//               Home
//             </button>

//             <button className="sidebar-link">
//               <span>▣</span>
//               Browse Books
//             </button>

//             <button className="sidebar-link">
//               <span>♡</span>
//               My Books
//             </button>

//             <button className="sidebar-link">
//               <span>○</span>
//               Profile
//             </button>

//           </nav>

//           <div className="sidebar-bottom">

//             <button
//               className="sidebar-link logout-link"
//              onClick={async () => {
//   try {
//     await fetch(
//       "http://localhost:5000/api/user/logout",
//       {
//         method: "POST",
//         credentials: "include"
//       }
//     );
//   } catch (error) {
//     console.error("Logout error:", error);
//   }

//   setIsUserLoggedIn(false);
// }}
//             >
//               <span>↪</span>
//               Logout
//             </button>

//           </div>

//         </aside>

//         <main className="booknav-main">

//           <header className="booknav-topbar">

//             <div>
//               <p className="topbar-label">
//                 LIBRARY
//               </p>

//               <h3>
//                 Welcome to BookNav
//               </h3>
//             </div>

//             <div className="topbar-user">
//               <span className="user-avatar">
//                 V
//               </span>

//               <span>
//                 Member
//               </span>
//             </div>

//           </header>

//           <div className="booknav-content">
//             <UserHome />
//           </div>

//         </main>

//       </div>
//     );
//   }

//   /* ================================
//      ADMIN LOGIN
//      ================================ */

//   if (mode === "admin-login") {
//     return (
//       <AdminLogin
//   onLogin={() => setIsAdminLoggedIn(true)}
//   onBack={() => setMode("user-login")}
//   onRegister={() => setMode("register")}
// />
//     );
//   }

//   /* ================================
//      USER REGISTER
//      ================================ */

//   if (mode === "register") {
//     return (
//       <UserRegister
//         onRegister={() => setMode("user-login")}
//         onBack={() => setMode("user-login")}
//         onAdminLogin={() => setMode("admin-login")}
//       />
//     );
//   }

//   /* ================================
//      USER LOGIN
//      ================================ */

//   return (
//     <UserLogin
//       onLogin={() => setIsUserLoggedIn(true)}
//       onRegister={() => setMode("register")}
//       onAdminLogin={() => setMode("admin-login")}
//     />
//   );
// }

// export default App;


import { useEffect, useState } from "react";

import booknavLogo from "./assets/booknav.png";
import AdminLogin from "./pages/AdminLogin";
import AdminBooks from "./pages/AdminBooks";
import UserLogin from "./pages/UserLogin";
import UserRegister from "./pages/UserRegister";
import UserHome from "./pages/UserHome";
import "./App.css";
function App() {
  const [mode, setMode] = useState("user-login");

  const [isUserLoggedIn, setIsUserLoggedIn] = useState(false);
  const [isAdminLoggedIn, setIsAdminLoggedIn] = useState(false);

  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const checkSessions = async () => {
      try {
        // Check Admin Session
        const adminResponse = await fetch(
          "http://localhost:5000/api/admin/session",
          {
            credentials: "include"
          }
        );

        if (adminResponse.ok) {
          setIsAdminLoggedIn(true);
          setCheckingSession(false);
          return;
        }

        // Check User Session
        const userResponse = await fetch(
          "http://localhost:5000/api/user/session",
          {
            credentials: "include"
          }
        );

        if (userResponse.ok) {
          setIsUserLoggedIn(true);
        } else {
          setIsUserLoggedIn(false);
        }
      } catch (error) {
        console.error("Session check failed:", error);

        setIsUserLoggedIn(false);
        setIsAdminLoggedIn(false);
      } finally {
        setCheckingSession(false);
      }
    };

    checkSessions();
  }, []);

  // Session checking screen
  if (checkingSession) {
    return <div>Checking session...</div>;
  }

  // ================================
  // ADMIN DASHBOARD
  // ================================

  if (isAdminLoggedIn) {
    return (
      <AdminBooks
        onLogout={() => {
          setIsAdminLoggedIn(false);
          setMode("user-login");
        }}
      />
    );
  }

  // ================================
  // USER HOME
  // ================================

  if (isUserLoggedIn) {
    return (
      <div className="booknav-layout">

        <aside className="booknav-sidebar">

          <div className="sidebar-brand">
            <div className="sidebar-logo">
  <img src={booknavLogo} alt="BookNav" />
</div>

            <div>
              <h2>BookNav</h2>
              <span>Smart Library</span>
            </div>
          </div>

          <nav className="sidebar-nav">

            <button className="sidebar-link active">
              <span>⌂</span>
              Home
            </button>

            <button className="sidebar-link">
              <span>▣</span>
              Browse Books
            </button>

            <button className="sidebar-link">
              <span>♡</span>
              My Books
            </button>

            <button className="sidebar-link">
              <span>○</span>
              Profile
            </button>

          </nav>

          <div className="sidebar-bottom">

            <button
              className="sidebar-link logout-link"
              onClick={async () => {
                try {
                  await fetch(
                    "http://localhost:5000/api/user/logout",
                    {
                      method: "POST",
                      credentials: "include"
                    }
                  );
                } catch (error) {
                  console.error("Logout error:", error);
                }

                setIsUserLoggedIn(false);
                setMode("user-login");
              }}
            >
              <span>↪</span>
              Logout
            </button>

          </div>

        </aside>

        <main className="booknav-main">

          <header className="booknav-topbar">

            <div>
              <p className="topbar-label">
                LIBRARY
              </p>

              <h3>
                Welcome to BookNav
              </h3>
            </div>

            <div className="topbar-user">
              <span className="user-avatar">
                V
              </span>

              <span>
                Member
              </span>
            </div>

          </header>

          <div className="booknav-content">
            <UserHome />
          </div>

        </main>

      </div>
    );
  }

  // ================================
  // ADMIN LOGIN
  // ================================

  if (mode === "admin-login") {
    return (
      <AdminLogin
        onLogin={() => setIsAdminLoggedIn(true)}
        onBack={() => setMode("user-login")}
        onRegister={() => setMode("register")}
      />
    );
  }

  // ================================
  // USER REGISTER
  // ================================

  if (mode === "register") {
    return (
      <UserRegister
        onRegister={() => setMode("user-login")}
        onBack={() => setMode("user-login")}
        onAdminLogin={() => setMode("admin-login")}
      />
    );
  }

  // ================================
  // USER LOGIN
  // ================================

  return (
    <UserLogin
      onLogin={() => setIsUserLoggedIn(true)}
      onRegister={() => setMode("register")}
      onAdminLogin={() => setMode("admin-login")}
    />
  );
}

export default App;