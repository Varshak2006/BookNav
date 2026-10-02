import { useEffect, useState } from "react";
import bookCover from "../assets/the-c.jpg";

function BookDetails({ bookId, onBack }) {
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBook();
  }, []);

  const fetchBook = async () => {
    try {
      const response = await fetch(
        `http://localhost:5000/api/books/${bookId}`
      );

      const data = await response.json();

      if (response.ok) {
        setBook(data);
      } else {
        alert(data.message || "Book not found");
      }
    } catch (error) {
      console.error("Fetch book error:", error);
      alert("Could not connect to the backend");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <p>Loading book details...</p>;
  }

  if (!book) {
    return <p>Book not found.</p>;
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
            <p>{book.description}</p>
          </div>

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