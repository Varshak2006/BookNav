
import { useEffect, useState } from "react";
import booknavLogo from "./assets/booknav.png";
import AdminLogin from "./pages/AdminLogin";
import AdminBooks from "./pages/AdminBooks";
import UserLogin from "./pages/UserLogin";
import UserRegister from "./pages/UserRegister";
import UserHome from "./pages/UserHome";
import BookNavigation from "./pages/BookNavigation";
import { API_BASE_URL } from "./config/api";
import "./App.css";

function App() {
  const [mode, setMode] = useState("user-login");
  const [isUserLoggedIn, setIsUserLoggedIn] = useState(false);
  const [isAdminLoggedIn, setIsAdminLoggedIn] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  // Read the book ID from a QR-code URL, if present.
  const [navigationBookId, setNavigationBookId] = useState(() => {
    return new URLSearchParams(window.location.search).get("navigate");
  });

  // Handle QR URLs and browser back/forward navigation.
  useEffect(() => {
    const handleLocationChange = () => {
      const params = new URLSearchParams(window.location.search);
      setNavigationBookId(params.get("navigate"));
    };

    window.addEventListener("popstate", handleLocationChange);

    return () => {
      window.removeEventListener("popstate", handleLocationChange);
    };
  }, []);

  // Check existing user and admin sessions.
  useEffect(() => {
    let ignore = false;

    const checkSessions = async () => {
      try {
        // Check Admin Session.
        const adminResponse = await fetch(
          `${API_BASE_URL}/admin/session`,
          { credentials: "include" }
        );

        if (!ignore && adminResponse.ok) {
          setIsAdminLoggedIn(true);
          setCheckingSession(false);
          return;
        }

        // Check User Session.
        const userResponse = await fetch(
          `${API_BASE_URL}/user/session`,
          { credentials: "include" }
        );

        if (!ignore) {
          setIsUserLoggedIn(userResponse.ok);
        }
      } catch (error) {
        console.error("Session check failed:", error);

        if (!ignore) {
          setIsUserLoggedIn(false);
          setIsAdminLoggedIn(false);
        }
      } finally {
        if (!ignore) {
          setCheckingSession(false);
        }
      }
    };

    checkSessions();

    return () => {
      ignore = true;
    };
  }, []);

  // Return from navigation to the previous BookNav screen.
  const handleNavigationBack = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("navigate");

    window.history.replaceState(
      {},
      "",
      `${url.pathname}${url.search}${url.hash}`
    );

    setNavigationBookId(null);
  };

  // QR navigation is public so a phone can open a book directly.
  if (navigationBookId) {
    return (
      <BookNavigation
        bookId={navigationBookId}
        onBack={handleNavigationBack}
      />
    );
  }

  // Wait until the existing session check finishes.
  if (checkingSession) {
    return <div>Checking session...</div>;
  }

  // ADMIN DASHBOARD.
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

  // USER HOME.
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
                  await fetch(`${API_BASE_URL}/user/logout`, {
                    method: "POST",
                    credentials: "include",
                  });
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
              <p className="topbar-label">LIBRARY</p>
              <h3>Welcome to BookNav</h3>
            </div>

            <div className="topbar-user">
              <span className="user-avatar">V</span>
              <span>Member</span>
            </div>
          </header>

          <div className="booknav-content">
            <UserHome />
          </div>
        </main>
      </div>
    );
  }

  // ADMIN LOGIN.
  if (mode === "admin-login") {
    return (
      <AdminLogin
        onLogin={() => setIsAdminLoggedIn(true)}
        onBack={() => setMode("user-login")}
        onRegister={() => setMode("register")}
      />
    );
  }

  // USER REGISTRATION.
  if (mode === "register") {
    return (
      <UserRegister
        onRegister={() => setMode("user-login")}
        onBack={() => setMode("user-login")}
        onAdminLogin={() => setMode("admin-login")}
      />
    );
  }

  // USER LOGIN.
  return (
    <UserLogin
      onLogin={() => setIsUserLoggedIn(true)}
      onRegister={() => setMode("register")}
      onAdminLogin={() => setMode("admin-login")}
    />
  );
}

export default App;
