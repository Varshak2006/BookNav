
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { API_BASE_URL } from "../config/api";
import "./BookNavigation.css";

function BookNavigation({ bookId, onBack }) {
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function fetchBook() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `${API_BASE_URL}/books/${encodeURIComponent(bookId)}`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error(
            response.status === 404
              ? "Book not found."
              : "Could not load book information."
          );
        }

        const data = await response.json();
        setBook(data);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message || "Could not load book information.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchBook();

    return () => controller.abort();
  }, [bookId]);

  const speakDirections = () => {
    if (!book || !("speechSynthesis" in window)) {
      setError("Voice guidance is not supported by this browser.");
      return;
    }

    window.speechSynthesis.cancel();

    const instructions = [
      `You are looking for ${book.title} by ${book.author}.`,
      book.location ? `Library location: ${book.location}.` : "",
      `Find rack ${book.rack}.`,
      `Look for shelf ${book.shelf}.`,
      "Check the book title before taking it."
    ].filter(Boolean).join(" ");

    const utterance = new SpeechSynthesisUtterance(instructions);
    utterance.lang = "en-IN";
    window.speechSynthesis.speak(utterance);
  };

  if (loading) {
    return <main className="navigation-page"><p>Loading book location...</p></main>;
  }

  if (error && !book) {
    return (
      <main className="navigation-page">
        <p role="alert">{error}</p>
        <button onClick={onBack}>Back to books</button>
      </main>
    );
  }

  if (!book) return null;

  // The QR opens this navigation page for this particular book.
  const navigationUrl = new URL(
    window.location.pathname,
    window.location.origin
  );
  navigationUrl.searchParams.set("navigate", book._id);

  const directions = [
    book.location ? `Go to ${book.location}` : "Locate the correct library area",
    `Find rack ${book.rack}`,
    `Locate shelf ${book.shelf}`,
    `Verify the title: ${book.title}`
  ];

  return (
    <main className="navigation-page">
      <button className="back-button" onClick={onBack}>
        ← Back to books
      </button>

      <header className="navigation-header">
        <p className="eyebrow">BOOKNAV • FROM SEARCH TO SHELF</p>
        <h1>Find your book</h1>
        <p>Follow the location details to find your selected book.</p>
      </header>

      <section className="navigation-card">
        <h2>{book.title}</h2>
        <p>by {book.author}</p>

        <div className="navigation-location">
          <div>
            <span>LOCATION</span>
            <strong>{book.location || "Not specified"}</strong>
          </div>
          <div>
            <span>RACK</span>
            <strong>{book.rack}</strong>
          </div>
          <div>
            <span>SHELF</span>
            <strong>{book.shelf}</strong>
          </div>
        </div>

        <h3>Step-by-step directions</h3>
        <ol className="navigation-steps">
          {directions.map((direction, index) => (
            <li key={index}>{direction}</li>
          ))}
        </ol>

        <button className="voice-button" onClick={speakDirections}>
          🔊 Read directions aloud
        </button>
      </section>

      <section className="qr-card">
        <h2>Scan to open on your phone</h2>
        <p>Scan this code to open this book's navigation page.</p>
        <QRCodeSVG value={navigationUrl.toString()} size={220} level="M" />
        <p className="qr-note">
          Your phone must be able to access this application's address.
        </p>
      </section>
    </main>
  );
}

export default BookNavigation;
