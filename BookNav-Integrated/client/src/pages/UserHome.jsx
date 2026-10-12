// import { useEffect, useState } from "react";
// import BookDetails from "./BookDetails";

// function UserHome() {
//   const [books, setBooks] = useState([]);
//   const [searchTerm, setSearchTerm] = useState("");
//   const [loading, setLoading] = useState(true);
//   const [selectedBookId, setSelectedBookId] = useState(null);
// const [searchLoading, setSearchLoading] = useState(false);
//   useEffect(() => {
//     fetchBooks();
//   }, []);

//   const fetchBooks = async () => {
//     try {
//       const response = await fetch(
//         "http://localhost:5000/api/books"
//       );

//       const data = await response.json();

//       if (response.ok) {
//         setBooks(data);
//       } else {
//         alert("Failed to fetch books");
//       }
//     } catch (error) {
//       console.error("Fetch books error:", error);
//       alert("Could not connect to the backend");
//     } finally {
//       setLoading(false);
//     }
//   };
// const searchBooks = async (query) => {
//   setSearchLoading(true);

//   try {
//     const response = await fetch(
//       `http://localhost:5000/api/books/search?q=${encodeURIComponent(query)}`
//     );

//     const data = await response.json();

//     if (response.ok) {
//       setBooks(data);
//     } else {
//       console.error(data.message);
//     }
//    } catch (error) {
//     console.error("Search books error:", error);
//   } finally {
//     setSearchLoading(false);
//   }
// };
//   // Show book details when a book is selected
//   if (selectedBookId) {
//     return (
//       <BookDetails
//         bookId={selectedBookId}
//         onBack={() => setSelectedBookId(null)}
//       />
//     );
//   }

//   const filteredBooks = searchTerm.trim()
//   ? books.filter((book) => {
//       const search = searchTerm.toLowerCase();

//       return (
//         book.title.toLowerCase().includes(search) ||
//         book.author.toLowerCase().includes(search) ||
//         book.category.toLowerCase().includes(search)
//       );
//     })
//   : books;

//   return (
//     <div>
//       <h1>BookNav</h1>
// <p>Welcome to the BookNav Library</p>
// <h2>Find a Book</h2>

//       <input
//         type="text"
//         placeholder="Search by title, author or category..."
//         value={searchTerm}
//        onChange={(e) => {
//   const value = e.target.value;
//   setSearchTerm(value);

//   if (value.trim() === "") {
//     fetchBooks();
//   } else {
//     searchBooks(value);
//   }
// }}     />
// {searchLoading && <p>Searching...</p>}

//       <br />
//       <br />

//       {loading ? (
//         <p>Loading books...</p>
//       ) : filteredBooks.length === 0 ? (
//        <p>No books found for "{searchTerm}".</p>
//       ) : (
//         <div>
//           {filteredBooks.map((book) => (
//             <div key={book._id}>
//               <h3>{book.title}</h3>

//               <p>
//                 <strong>Author:</strong> {book.author}
//               </p>

//               <p>
//                 <strong>Category:</strong> {book.category}
//               </p>
// <p><strong>Description:</strong> {book.description}</p>
//               <p>
//                 <strong>Shelf:</strong> {book.shelf}
//               </p>

//               <p>
//                 <strong>Rack:</strong> {book.rack}
//               </p>

//               <p>
//                 <strong>Location:</strong> {book.location}
//               </p>

//               <button
//                 onClick={() => setSelectedBookId(book._id)}
//               >
//                 View Details
//               </button>

//               <hr />
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// }

// export default UserHome;


import { useEffect, useState, useRef, useCallback } from "react";
import BookDetails from "./BookDetails";

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
    // Cancel any in-flight request
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
      const response = await fetch("http://localhost:5000/api/books", {
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

  const executeSearch = useCallback(async (query, overrideMode = null) => {
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
      const response = await fetch(
        `http://localhost:5000/api/books/search?q=${encodeURIComponent(trimmed)}${modeParam}`,
        { signal: controller.signal }
      );

      const data = await response.json();

      // Only update state if this is still the most recent request
      if (reqId === latestRequestIdRef.current) {
        if (response.ok) {
          if (data && Array.isArray(data.results)) {
            setBooks(data.results);
            setCorrectionInfo({
              query: data.query,
              effectiveQuery: data.effectiveQuery,
              correctionApplied: data.correctionApplied,
              correctedQuery: data.correctedQuery,
              suggestion: data.suggestion,
              confidence: data.confidence,
              confidenceLevel: data.confidenceLevel
            });
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
    fetchBooks();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [fetchBooks]);

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
            type="text"
            placeholder="Search by title, author, category or topic..."
            value={searchTerm}
            onChange={handleInputChange}
          />

          <button type="submit" className="search-button">
            Search
          </button>

        </form>

        {searchLoading && (
          <p className="search-status">
            Searching...
          </p>
        )}

        {/* LACS High-confidence auto-correction notification */}
        {correctionInfo && correctionInfo.correctionApplied && correctionInfo.correctedQuery && (
          <div className="correction-banner" style={{
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
              type="button"
              onClick={() => {
                setSearchTerm(correctionInfo.query);
                executeSearch(correctionInfo.query, "exact");
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
          <div className="suggestion-banner" style={{
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
          <p className="search-error" style={{ color: "#e53e3e", marginTop: "8px", fontSize: "0.9rem" }}>
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

          {!loading && !searchLoading && (
            <span className="book-count">
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
        ) : displayedBooks.length === 0 ? (
          <div className="state-card empty-state">
            <div className="empty-icon">⌕</div>

            <h3>No books found</h3>

            <p>
              {searchTerm.trim()
                ? `No books found for "${searchTerm}".`
                : "No books available in the collection."}
            </p>
          </div>
        ) : (
          <div className="books-grid">

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