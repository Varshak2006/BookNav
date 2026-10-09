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





import { useEffect, useState } from "react";
import BookDetails from "./BookDetails";

function UserHome() {
  const [books, setBooks] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedBookId, setSelectedBookId] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [filters, setFilters] = useState([]);
  const [filterField, setFilterField] = useState("category");
  const [filterValue, setFilterValue] = useState("");
  const [filterLogic, setFilterLogic] = useState("AND");
  useEffect(() => {
    fetchBooks();
  }, []);

  const fetchBooks = async () => {
    try {
      const response = await fetch(
        "http://localhost:5000/api/books"
      );

      const data = await response.json();

      if (response.ok) {
        setBooks(data);
      } else {
        alert("Failed to fetch books");
      }
    } catch (error) {
      console.error("Fetch books error:", error);
      alert("Could not connect to the backend");
    } finally {
      setLoading(false);
    }
  };

  const searchBooks = async (query) => {
    setSearchLoading(true);

    try {
      const response = await fetch(
        `http://localhost:5000/api/books/search?q=${encodeURIComponent(query)}`
      );

      const data = await response.json();

      if (response.ok) {
        setBooks(data);
      } else {
        console.error(data.message);
      }
    } catch (error) {
      console.error("Search books error:", error);
    } finally {
      setSearchLoading(false);
    }
  };

  const addFilter = () => {
    if (!filterValue.trim()) {
      alert("Please enter a filter value");
      return;
    }

    const newFilter = {
      id: Date.now(),
      field: filterField,
      value: filterValue.trim(),
      active: true
    };

    setFilters((previousFilters) => [
      ...previousFilters,
      newFilter
    ]);

    setFilterValue("");
  };
  
  const toggleFilter = (id) => {
    setFilters((previousFilters) =>
      previousFilters.map((filter) =>
        filter.id === id
          ? { ...filter, active: !filter.active }
          : filter
      )
    );
  };

  const removeFilter = (id) => {
    setFilters((previousFilters) =>
      previousFilters.filter((filter) => filter.id !== id)
    );
  };
  
  const applyFilters = async () => {
    setSearchLoading(true);

    try {
      const params = new URLSearchParams();

      if (searchTerm.trim()) {
        params.set("q", searchTerm.trim());
      }

      params.set("logic", filterLogic);

      filters
        .filter((filter) => filter.active)
        .forEach((filter) => {
          params.append(
            "filters",
            `${filter.field}:${filter.value}`
          );
        });

      const response = await fetch(
        `http://localhost:5000/api/books/search?${params.toString()}`
      );

      const data = await response.json();

      if (response.ok) {
        setBooks(data);
      } else {
        alert(data.message || "Failed to apply filters");
      }
    } catch (error) {
      console.error("Apply filters error:", error);
      alert("Could not connect to the backend");
    } finally {
      setSearchLoading(false);
    }
  };
  if (selectedBookId) {
    return (
      <BookDetails
        bookId={selectedBookId}
        onBack={() => setSelectedBookId(null)}
      />
    );
  }
// const getCombinedScore = (book) => {
//   const textScore = scoreBook(book);

//   const filterScore = filters
//     .filter((filter) => filter.active)
//     .reduce((score, filter) => {
//       const bookValue = String(book[filter.field] ?? "").toLowerCase();
//       const filterValue = filter.value.toLowerCase();

//       return bookValue.includes(filterValue) ? score + 2 : score;
//     }, 0);

//   return textScore + filterScore;
// };
const getTextScore = (book) => {
  const query = searchTerm.trim().toLowerCase();

  if (!query) return 0;

  const title = book.title?.toLowerCase().trim() || "";
  const author = book.author?.toLowerCase().trim() || "";
  const category = book.category?.toLowerCase().trim() || "";

  let score = 0;

  if (title === query) score += 10;
  else if (title.includes(query)) score += 5;

  if (author === query) score += 6;
  else if (author.includes(query)) score += 3;

  if (category === query) score += 4;
  else if (category.includes(query)) score += 2;

  return score;
};
 const getFilterScore = (book) =>
  filters
    .filter((filter) => filter.active)
    .reduce((score, filter) => {
      const bookValue = String(book[filter.field] ?? "").toLowerCase();
      const filterValue = filter.value.toLowerCase();

      return bookValue.includes(filterValue) ? score + 2 : score;
    }, 0);

const filteredBooks = [...books].sort((a, b) => {
  const scoreA = getTextScore(a) + getFilterScore(a);
  const scoreB = getTextScore(b) + getFilterScore(b);

  return scoreB - scoreA;
});
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
              const value = e.target.value;
              setSearchTerm(value);

              if (value.trim() === "") {
                fetchBooks();
              } else {
                searchBooks(value);
              }
            }}
          />

         <button
  className="search-button"
  type="button"
  onClick={() => searchBooks(searchTerm)}
>
  Search
</button>

        </div>

        <div className="filter-panel">
          <h3>Filter Books</h3>

          <div className="filter-controls">
            <select
              value={filterField}
              onChange={(e) => setFilterField(e.target.value)}
            >
              <option value="title">Title</option>
              <option value="author">Author</option>
              <option value="category">Category</option>
              <option value="shelf">Shelf</option>
              <option value="rack">Rack</option>
              <option value="location">Location</option>
            </select>

            <input
              type="text"
              placeholder="Enter filter value..."
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
            />

            <button type="button" onClick={addFilter}>
              Add Filter
            </button>
          </div>

          <div className="filter-logic">
            <label htmlFor="filter-logic">Match filters using:</label>

            <select
              id="filter-logic"
              value={filterLogic}
              onChange={(e) => setFilterLogic(e.target.value)}
            >
              <option value="AND">AND — match all</option>
              <option value="OR">OR — match any</option>
            </select>

            <button type="button" onClick={applyFilters}>
              Apply Filters
            </button>
          </div>

          <div className="active-filters">
            {filters.length === 0 ? (
              <p>No filters added yet.</p>
            ) : (
              filters.map((filter) => (
                <div className="filter-item" key={filter.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={filter.active}
                      onChange={() => toggleFilter(filter.id)}
                    />

                    <span>
                      {filter.field}: {filter.value}
                      {!filter.active && " (Inactive)"}
                    </span>
                  </label>

                  <button
                    type="button"
                    onClick={() => removeFilter(filter.id)}
                  >
                    Remove
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
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
              No books found for "{searchTerm}".
            </p>
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
{searchTerm.trim() !== "" && (
  <p className="relevance-score">
    Relevance score: {getTextScore(book) + getFilterScore(book)}
  </p>
)}
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