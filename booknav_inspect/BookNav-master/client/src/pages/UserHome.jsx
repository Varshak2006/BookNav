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





import { useCallback, useEffect, useRef, useState } from "react";
import BookDetails from "./BookDetails";

function UserHome() {
  const [books, setBooks] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedBookId, setSelectedBookId] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [correctionInfo, setCorrectionInfo] = useState(null);

  const debounceTimerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const lastSearchedRef = useRef("");

  const fetchBooks = useCallback(async () => {
    try {
      const response = await fetch(
        "http://localhost:5000/api/books"
      );

      const data = await response.json();

      if (response.ok) {
        setBooks(data);
        setCorrectionInfo(null);
        lastSearchedRef.current = "";
      } else {
        alert("Failed to fetch books");
      }
    } catch (error) {
      console.error("Fetch books error:", error);
      alert("Could not connect to the backend");
    } finally {
      setLoading(false);
    }
  }, []);

  const searchBooks = useCallback(async (query, forceOriginal = false) => {
    const trimmed = (query || "").trim();
    if (!trimmed) {
      fetchBooks();
      return;
    }

    // Cancel any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setSearchLoading(true);

    try {
      const url = `http://localhost:5000/api/books/search?q=${encodeURIComponent(trimmed)}${forceOriginal ? "&forceOriginal=true" : ""}`;
      const response = await fetch(url, { signal: controller.signal });
      const data = await response.json();

      if (response.ok) {
        setBooks(Array.isArray(data) ? data : data.results || []);
        setCorrectionInfo(Array.isArray(data) ? null : data);
        lastSearchedRef.current = trimmed;
      } else {
        console.error(data.message);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Search books error:", error);
      }
    } finally {
      setSearchLoading(false);
    }
  }, [fetchBooks]);

  const executeImmediateSearch = (query, forceOriginal = false) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    lastSearchedRef.current = (query || "").trim();
    searchBooks(query, forceOriginal);
  };

  useEffect(() => {
    const query = searchTerm.trim();
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      if (query === "") {
        fetchBooks();
      } else if (query !== lastSearchedRef.current) {
        searchBooks(query);
      }
    }, 350);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [fetchBooks, searchBooks, searchTerm]);

  if (selectedBookId) {
    return (
      <BookDetails
        bookId={selectedBookId}
        onBack={() => setSelectedBookId(null)}
      />
    );
  }

  const filteredBooks = books;
  const displayQuery = correctionInfo?.correctionApplied
    ? correctionInfo.correctedQuery
    : searchTerm;

  return (
    <div className="user-home">

      {/* Hero / Search Section */}
      <section className="search-hero">
        <div>
          <p className="eyebrow">BOOKNAV LIBRARY</p>

          <h1>Find your next book.</h1>

          <p className="hero-description">
            Search through the library and discover books
            by title, author or category.
          </p>
        </div>

        <div className="search-box">

          <input
            type="text"
            placeholder="Search by title, author or category..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                executeImmediateSearch(searchTerm);
              }
            }}
          />

          <button
            className="search-button"
            type="button"
            onClick={() => executeImmediateSearch(searchTerm)}
          >
            Search
          </button>

        </div>

        {correctionInfo?.correctionApplied && (
          <p className="correction-message">
            Showing results for <strong>"{correctionInfo.correctedQuery}"</strong>.{" "}
            <span>
              (
              <button
                className="reverse-correct-button"
                type="button"
                onClick={() => {
                  setSearchTerm(correctionInfo.query);
                  executeImmediateSearch(correctionInfo.query, true);
                }}
              >
                Search instead for "{correctionInfo.query}"
              </button>
              )
            </span>
          </p>
        )}

        {correctionInfo?.originalForced && correctionInfo?.suggestion && (
          <p className="correction-message">
            Showing results for original query <strong>"{searchTerm}"</strong>.{" "}
            <span>
              (
              <button
                className="reverse-correct-button"
                type="button"
                onClick={() => {
                  const sugg = correctionInfo.suggestion;
                  setSearchTerm(sugg);
                  executeImmediateSearch(sugg, false);
                }}
              >
                Search with correction "{correctionInfo.suggestion}"
              </button>
              )
            </span>
          </p>
        )}

        {!correctionInfo?.correctionApplied && !correctionInfo?.originalForced && correctionInfo?.suggestion && (
          <p className="correction-message">
            Did you mean{" "}
            <button
              className="suggestion-button"
              type="button"
              onClick={() => {
                const sugg = correctionInfo.suggestion;
                const old = searchTerm;
                setSearchTerm(sugg);
                // Record user acceptance of suggestion into LACS history
                fetch("http://localhost:5000/api/books/accept-correction", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ wrong: old, correct: sugg })
                }).catch(() => {});
                executeImmediateSearch(sugg);
              }}
            >
              "{correctionInfo.suggestion}"
            </button>
            ?
          </p>
        )}

        {searchLoading && (
          <p className="search-status">
            Searching...
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

          {!loading && (
            <span className="book-count">
              {filteredBooks.length}{" "}
              {filteredBooks.length === 1
                ? "Book"
                : "Books"}
            </span>
          )}
        </div>

        {loading ? (
          <div className="state-card">
            <p>Loading books...</p>
          </div>
        ) : filteredBooks.length === 0 ? (
          <div className="state-card empty-state">
            <div className="empty-icon">⌕</div>

            <h3>No books found</h3>

            <p>
              No books found for "{displayQuery}".
            </p>

            {correctionInfo?.correctionApplied && (
              <div style={{ marginTop: "14px" }}>
                <p style={{ fontSize: "14px", opacity: 0.85 }}>
                  The query was automatically corrected from "{correctionInfo.query}".
                </p>
                <button
                  className="reverse-correct-button"
                  type="button"
                  style={{ marginTop: "8px" }}
                  onClick={() => {
                    setSearchTerm(correctionInfo.query);
                    executeImmediateSearch(correctionInfo.query, true);
                  }}
                >
                  Search for original query "{correctionInfo.query}" instead
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="books-grid">

            {filteredBooks.map((book) => (
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
