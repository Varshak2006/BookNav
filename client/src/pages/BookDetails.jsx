import { useEffect, useState } from "react";
import bookCover from "../assets/the-c.jpg";
import { API_BASE_URL } from "../config/api";

function BookDetails({ bookId, onBack }) {
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;
    async function loadBook() {
      try {
        const response = await fetch(`${API_BASE_URL}/books/${bookId}`);
        const data = await response.json();
        if (!ignore) {
          if (response.ok) {
            setBook(data);
          } else {
            setError(data.message || "Book not found");
          }
        }
      } catch (err) {
        if (!ignore) {
          console.error("Fetch book error:", err);
          setError("Could not connect to the backend");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadBook();
    return () => {
      ignore = true;
    };
  }, [bookId]);

  if (loading) {
    return <p>Loading book details...</p>;
  }

  if (error || !book) {
    return (
      <div className="book-details-page">
        <button className="back-search-button" onClick={onBack}>
          ← Back to Search
        </button>
        <p style={{ marginTop: "24px", color: "#e53e3e" }}>{error || "Book not found."}</p>
      </div>
    );
  }

  return (
    <div className="book-details-page">

      <button
        className="back-search-button"
        onClick={onBack}
      >
        ← Back to Search
      </button>

      <div className="book-details-header">
        <p className="eyebrow">BOOK INFORMATION</p>
        <h1>Book Details</h1>
      </div>

      <div className="book-details-card">

        <div className="book-details-cover">
          <img
            src={bookCover}
            alt={book.title}
            className="book-details-image"
          />
        </div>

        <div className="book-details-content">

          <p className="category-tag">
            {book.category}
          </p>

          <h2>{book.title}</h2>

          <p className="book-details-author">
            by {book.author}
          </p>

          <div className="book-details-description">
            <span>Description</span>
            <p>{book.description || "No description provided."}</p>
          </div>

          {book.keywords && (
            <div className="book-details-description" style={{ marginTop: "12px" }}>
              <span>Keywords</span>
              <p style={{ fontStyle: "italic", color: "#4a5568" }}>{book.keywords}</p>
            </div>
          )}

          <div className="book-details-location">

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

          <button className="navigate-book-button">
            Navigate to Book
          </button>

        </div>

      </div>

    </div>
  );
}

export default BookDetails;