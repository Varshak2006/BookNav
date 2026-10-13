import { useEffect, useState, useRef, useCallback } from "react";
import BookDetails from "./BookDetails";
import { API_BASE_URL } from "../config/api";

function UserHome() {
  const [books, setBooks] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedBookId, setSelectedBookId] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [correctionInfo, setCorrectionInfo] = useState(null);

  // References for request cancellation and sequencing
  const abortControllerRef = useRef(null);
  const latestRequestIdRef = useRef(0);
  const debounceTimerRef = useRef(null);

  const fetchBooks = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const reqId = ++latestRequestIdRef.current;

    setLoading(true);
    setSearchError(null);
    setCorrectionInfo(null);

    try {
      const response = await fetch(`${API_BASE_URL}/books`, {
        signal: controller.signal
      });

      const data = await response.json();

      if (reqId === latestRequestIdRef.current) {
        if (response.ok) {
          setBooks(Array.isArray(data) ? data : []);
        } else {
          setSearchError("Failed to fetch library collection");
        }
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Fetch books error:", error);
        if (reqId === latestRequestIdRef.current) {
          setSearchError("Could not connect to the backend");
        }
      }
    } finally {
      if (reqId === latestRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const executeSearch = useCallback(async (query, overrideMode = null, bypassCorrection = false) => {
    const trimmed = query.trim();
    if (!trimmed) {
      fetchBooks();
      return;
    }

    // Cancel any in-flight search request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const reqId = ++latestRequestIdRef.current;

    setSearchLoading(true);
    setSearchError(null);

    try {
      const modeParam = overrideMode ? `&mode=${encodeURIComponent(overrideMode)}` : "";
      const correctParam = bypassCorrection ? `&correct=false` : "";
      const response = await fetch(
        `${API_BASE_URL}/books/search?q=${encodeURIComponent(trimmed)}${modeParam}${correctParam}`,
        { signal: controller.signal }
      );

      const data = await response.json();

      // Only update state if this is still the most recent request
      if (reqId === latestRequestIdRef.current) {
        if (response.ok) {
          if (data && Array.isArray(data.results)) {
            setBooks(data.results);
            if (data.correctionApplied || data.suggestion) {
              setCorrectionInfo({
                query: data.query,
                effectiveQuery: data.effectiveQuery,
                correctionApplied: Boolean(data.correctionApplied),
                correctedQuery: data.correctedQuery,
                suggestion: data.suggestion,
                confidence: data.confidence,
                confidenceLevel: data.confidenceLevel
              });
            } else {
              setCorrectionInfo(null);
            }
          } else if (Array.isArray(data)) {
            setBooks(data);
            setCorrectionInfo(null);
          } else {
            setBooks([]);
            setCorrectionInfo(null);
          }
        } else {
          setBooks([]);
          setCorrectionInfo(null);
          setSearchError(data.message || "Search failed");
        }
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Search books error:", error);
        if (reqId === latestRequestIdRef.current) {
          setBooks([]);
          setCorrectionInfo(null);
          setSearchError("Search service is temporarily unavailable");
        }
      }
    } finally {
      if (reqId === latestRequestIdRef.current) {
        setSearchLoading(false);
      }
    }
  }, [fetchBooks]);

  useEffect(() => {
    let ignore = false;
    async function loadInitial() {
      try {
        const response = await fetch(`${API_BASE_URL}/books`);
        const data = await response.json();
        if (!ignore && response.ok) {
          setBooks(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!ignore) {
          console.error("Initial book fetch error:", err);
          setSearchError("Could not connect to the backend");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    loadInitial();

    return () => {
      ignore = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setSearchTerm(value);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (value.trim() === "") {
      fetchBooks();
    } else {
      debounceTimerRef.current = setTimeout(() => {
        executeSearch(value);
      }, 300);
    }
  };

  const handleSearchSubmit = (e) => {
    if (e) e.preventDefault();
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    executeSearch(searchTerm);
  };

  if (selectedBookId) {
    return (
      <BookDetails
        bookId={selectedBookId}
        onBack={() => setSelectedBookId(null)}
      />
    );
  }

  // The backend owns search result selection — directly display returned books
  const displayedBooks = books;

  return (
    <div className="user-home">

      {/* Hero / Search Section */}
      <section className="search-hero">
        <div>
          <p className="eyebrow">BOOKNAV LIBRARY</p>

          <h1>Find your next book.</h1>

          <p className="hero-description">
            Search through the library and discover books
            by title, author or category with semantic AI search.
          </p>
        </div>

        <form className="search-box" onSubmit={handleSearchSubmit}>

          <input
            id="search-input"
            type="text"
            placeholder="Search by title, author, category or topic..."
            value={searchTerm}
            onChange={handleInputChange}
          />

          <button id="search-submit-btn" type="submit" className="search-button">
            Search
          </button>

        </form>

        {searchLoading && (
          <p className="search-status" id="search-status">
            Searching...
          </p>
        )}

        {/* LACS High-confidence auto-correction notification */}
        {correctionInfo && correctionInfo.correctionApplied && correctionInfo.correctedQuery && (
          <div className="correction-banner" id="correction-banner" style={{
            marginTop: "12px",
            padding: "8px 14px",
            backgroundColor: "#ebf8ff",
            border: "1px solid #bee3f8",
            borderRadius: "6px",
            color: "#2b6cb0",
            fontSize: "0.95rem"
          }}>
            <span>
              Showing results for: <strong><em>{correctionInfo.correctedQuery}</em></strong>
            </span>
            <span style={{ marginLeft: "8px", fontSize: "0.85rem", color: "#4a5568" }}>
              (spelling corrected from "{correctionInfo.query}")
            </span>
            <button
              id="search-original-query-btn"
              type="button"
              onClick={() => {
                setSearchTerm(correctionInfo.query);
                executeSearch(correctionInfo.query, "exact", true);
              }}
              style={{
                marginLeft: "12px",
                background: "none",
                border: "none",
                color: "#3182ce",
                textDecoration: "underline",
                cursor: "pointer",
                fontSize: "0.85rem"
              }}
            >
              Search instead for "{correctionInfo.query}"
            </button>
          </div>
        )}

        {/* LACS Medium-confidence "Did you mean?" suggestion */}
        {correctionInfo && !correctionInfo.correctionApplied && correctionInfo.suggestion && (
          <div className="suggestion-banner" id="suggestion-banner" style={{
            marginTop: "12px",
            padding: "8px 14px",
            backgroundColor: "#fffaf0",
            border: "1px solid #feebc8",
            borderRadius: "6px",
            color: "#c05621",
            fontSize: "0.95rem"
          }}>
            <span>Did you mean: </span>
            <button
              id="search-suggestion-btn"
              type="button"
              onClick={() => {
                setSearchTerm(correctionInfo.suggestion);
                executeSearch(correctionInfo.suggestion);
              }}
              style={{
                background: "none",
                border: "none",
                color: "#dd6b20",
                fontWeight: "bold",
                textDecoration: "underline",
                cursor: "pointer",
                padding: "0 4px",
                fontSize: "0.95rem"
              }}
            >
              {correctionInfo.suggestion}
            </button>
            <span>?</span>
          </div>
        )}

        {searchError && (
          <p className="search-error" id="search-error" style={{ color: "#e53e3e", marginTop: "8px", fontSize: "0.9rem" }}>
            {searchError}
          </p>
        )}
      </section>

      {/* Books Section */}
      <section className="books-section">

        <div className="section-heading">
          <div>
            <p className="eyebrow">LIBRARY COLLECTION</p>

            <h2>
              {searchTerm.trim()
                ? "Search Results"
                : "Explore Books"}
            </h2>
          </div>

          {!loading && !searchLoading && !searchError && (
            <span className="book-count" id="book-count">
              {displayedBooks.length}{" "}
              {displayedBooks.length === 1
                ? "Book"
                : "Books"}
            </span>
          )}
        </div>

        {loading ? (
          <div className="state-card">
            <p>Loading books...</p>
          </div>
        ) : searchError ? (
          <div className="state-card error-state" id="error-state-card" style={{ borderColor: "#feb2b2" }}>
            <div className="empty-icon" style={{ color: "#e53e3e" }}>⚠</div>
            <h3 style={{ color: "#c53030" }}>Search Service Error</h3>
            <p>{searchError}</p>
          </div>
        ) : displayedBooks.length === 0 ? (
          <div className="state-card empty-state" id="empty-state-card">
            <div className="empty-icon">⌕</div>

            <h3>No books found</h3>

            <p>
              {searchTerm.trim()
                ? `No books found for "${searchTerm}".`
                : "No books available in the collection."}
            </p>
          </div>
        ) : (
          <div className="books-grid" id="books-grid">

            {displayedBooks.map((book) => (
              <div
                className="book-card"
                key={book._id}
              >

                <div className="book-card-top">
                  <span className="category-tag">
                    {book.category}
                  </span>

                  <span className="book-symbol">
                    ▢
                  </span>
                </div>

                <h3>{book.title}</h3>

                <p className="book-author">
                  by {book.author}
                </p>

                <p className="book-description">
                  {book.description}
                </p>

                <div className="book-location">

                  <div>
                    <span>SHELF</span>
                    <strong>{book.shelf}</strong>
                  </div>

                  <div>
                    <span>RACK</span>
                    <strong>{book.rack}</strong>
                  </div>

                  <div>
                    <span>LOCATION</span>
                    <strong>{book.location}</strong>
                  </div>

                </div>

                <button
                  className="details-button"
                  onClick={() =>
                    setSelectedBookId(book._id)
                  }
                >
                  View Details →
                </button>

              </div>
            ))}

          </div>
        )}

      </section>
    </div>
  );
}

export default UserHome;