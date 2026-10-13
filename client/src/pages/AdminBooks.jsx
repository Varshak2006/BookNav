import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config/api";

function AdminBooks() {
  const [editingBookId, setEditingBookId] = useState(null);

  const [formData, setFormData] = useState({
    title: "",
    author: "",
    category: "",
    description: "",
    keywords: "",
    shelf: "",
    rack: "",
    location: ""
  });

  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Handle form input changes
  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  // Add / Update book
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (
      !formData.title.trim() ||
      !formData.author.trim() ||
      !formData.category.trim() ||
      !formData.shelf.trim() ||
      !formData.rack.trim()
    ) {
      alert("Please fill in Title, Author, Category, Shelf and Rack.");
      return;
    }

    try {
      let response;

      if (editingBookId) {
        // Update existing book
        response = await fetch(`${API_BASE_URL}/books/${editingBookId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json"
          },
          credentials: "include",
          body: JSON.stringify(formData)
        });
      } else {
        // Add new book
        response = await fetch(`${API_BASE_URL}/books`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          credentials: "include",
          body: JSON.stringify(formData)
        });
      }

      const data = await response.json();

      if (response.ok) {
        setMessage(
          editingBookId
            ? "Book updated successfully!"
            : "Book added successfully!"
        );
        setError("");

        setFormData({
          title: "",
          author: "",
          category: "",
          description: "",
          keywords: "",
          shelf: "",
          rack: "",
          location: ""
        });

        setEditingBookId(null);
        fetchBooks();
      } else {
        alert(data.message || "Operation failed");
      }
    } catch (err) {
      console.error("Error:", err);
      alert("Could not connect to the backend");
    }
  };

  // Fetch all books
  const fetchBooks = async () => {
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/books`, {
        credentials: "include"
      });

      const data = await response.json();

      if (response.ok) {
        setBooks(Array.isArray(data) ? data : []);
        setError("");
      } else {
        setError(data.message || "Could not load books.");
      }
    } catch (err) {
      console.error("Error fetching books:", err);
      setError("Could not load books. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Fetch books when page loads
  useEffect(() => {
    fetchBooks();
  }, []);

  // Edit book
  const handleEdit = (book) => {
    setEditingBookId(book._id);

    setMessage(`Editing "${book.title}"`);
    setError("");

    setFormData({
      title: book.title || "",
      author: book.author || "",
      category: book.category || "",
      description: book.description || "",
      keywords: book.keywords || "",
      shelf: book.shelf || "",
      rack: book.rack || "",
      location: book.location || ""
    });
  };

  // Delete book
  const handleDelete = async (id) => {
    const confirmDelete = window.confirm("Are you sure you want to delete this book?");
    if (!confirmDelete) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/books/${id}`, {
        method: "DELETE",
        credentials: "include"
      });

      const data = await response.json();

      if (response.ok) {
        setMessage("Book deleted successfully!");
        setError("");
        fetchBooks();
      } else {
        alert(data.message || "Failed to delete book");
      }
    } catch (err) {
      console.error("Error deleting book:", err);
      alert("Could not connect to the backend");
    }
  };

  // Cancel editing
  const handleCancelEdit = () => {
    setEditingBookId(null);
    setMessage("");
    setError("");

    setFormData({
      title: "",
      author: "",
      category: "",
      description: "",
      keywords: "",
      shelf: "",
      rack: "",
      location: ""
    });
  };

  // Admin logout
  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE_URL}/admin/logout`, {
        method: "POST",
        credentials: "include"
      });
    } catch (err) {
      console.error("Logout error:", err);
    }
    window.location.reload();
  };

  return (
    <div>
      <div>
        <h1>BookNav Admin</h1>
        <button onClick={handleLogout}>Logout</button>
      </div>

      {message && <p>{message}</p>}

      <h2>{editingBookId ? "Edit Book" : "Add New Book"}</h2>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          name="title"
          placeholder="Book Title"
          value={formData.title}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="author"
          placeholder="Author"
          value={formData.author}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="category"
          placeholder="Category"
          value={formData.category}
          onChange={handleChange}
        />
        <br /><br />

        <textarea
          name="description"
          placeholder="Description"
          value={formData.description}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="keywords"
          placeholder="Keywords (e.g. machine learning, algorithms)"
          value={formData.keywords}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="shelf"
          placeholder="Shelf"
          value={formData.shelf}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="rack"
          placeholder="Rack"
          value={formData.rack}
          onChange={handleChange}
        />
        <br /><br />

        <input
          type="text"
          name="location"
          placeholder="Library Location"
          value={formData.location}
          onChange={handleChange}
        />
        <br /><br />

        <button type="submit">
          {editingBookId ? "Update Book" : "Add Book"}
        </button>

        {editingBookId && (
          <button type="button" onClick={handleCancelEdit}>
            Cancel Edit
          </button>
        )}
      </form>

      <h2>Library Books</h2>

      {error && <p>{error}</p>}

      {loading ? (
        <p>Loading books...</p>
      ) : books.length === 0 ? (
        <p>No books available.</p>
      ) : (
        <div>
          {books.map((book) => (
            <div key={book._id}>
              <h3>{book.title}</h3>
              <p>Author: {book.author}</p>
              <p>Category: {book.category}</p>
              <p>Description: {book.description}</p>
              {book.keywords && <p>Keywords: {book.keywords}</p>}
              <p>Shelf: {book.shelf}</p>
              <p>Rack: {book.rack}</p>
              <p>Location: {book.location}</p>

              <button onClick={() => handleEdit(book)}>Edit</button>
              <button onClick={() => handleDelete(book._id)}>Delete</button>
              <hr />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AdminBooks;