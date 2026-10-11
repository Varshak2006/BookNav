// import { useEffect, useState } from "react";

// function AdminBooks() {
//     const [editingBookId, setEditingBookId] = useState(null);
//   const [formData, setFormData] = useState({
//     title: "",
//     author: "",
//     category: "",
//     description: "",
//     shelf: "",
//     rack: "",
//     location: ""
//   });
// const [books, setBooks] = useState([]);
// const [loading, setLoading] = useState(true);
// const [error, setError] = useState("");
// const [message, setMessage] = useState("");
//   const handleChange = (e) => {
//     setFormData({
//       ...formData,
//       [e.target.name]: e.target.value
//     });
//   };

//  const handleSubmit = async (e) => {
//   e.preventDefault();

//   if (
//     !formData.title.trim() ||
//     !formData.author.trim() ||
//     !formData.category.trim() ||
//     !formData.shelf.trim() ||
//     !formData.rack.trim()
//   ) {
//     alert(
//       "Please fill in Title, Author, Category, Shelf and Rack."
//     );
//     return;
//   }

//   try {
//     let response;

//     if (editingBookId) {
//       // Update existing book
//       response = await fetch(
//         `http://localhost:5000/api/books/${editingBookId}`,
//         {
//           method: "PUT",
//           headers: {
//   "Content-Type": "application/json",
//   Authorization: `Bearer ${localStorage.getItem("adminToken")}`
// },
//           body: JSON.stringify(formData)
//         }
//       );
//     } else {
//       // Add new book
//       response = await fetch("http://localhost:5000/api/books", {
//         method: "POST",
//        headers: {
//   "Content-Type": "application/json",
//   Authorization: `Bearer ${localStorage.getItem("adminToken")}`
// },
//         body: JSON.stringify(formData)
//       });
//     }

//     const data = await response.json();

//    if (response.ok) {
//   setMessage(
//     editingBookId
//       ? "Book updated successfully!"
//       : "Book added successfully!"
//   );
//   setError("");

//       setFormData({
//         title: "",
//         author: "",
//         category: "",
//         description: "",
//         shelf: "",
//         rack: "",
//         location: ""
//       });

//       setEditingBookId(null);
//       fetchBooks();
//     } else {
//       alert(data.message || "Operation failed");
//     }
//   } catch (error) {
//     console.error("Error:", error);
//     alert("Could not connect to the backend");
//   }
// };
// const fetchBooks = async () => {
//    setLoading(true);
//   try {
//     const response = await fetch("http://localhost:5000/api/books");
//     const data = await response.json();

//     if (response.ok) {
//       setBooks(data);
//     }
//   } catch (error) {
//   console.error("Error fetching books:", error);
//   setError("Could not load books. Please try again.");
// } finally{
//     setLoading(false);
//   }
// };

// useEffect(() => {
//   fetchBooks();
// }, []);
// const handleEdit = (book) => {
//   setEditingBookId(book._id);
//   setMessage(`Editing "${book.title}"`);
//   setError("");

//   setFormData({
//     title: book.title,
//     author: book.author,
//     category: book.category,
//     description: book.description,
//     shelf: book.shelf,
//     rack: book.rack,
//     location: book.location
//   });
// };
// const handleDelete = async (id) => {
//   const confirmDelete = window.confirm(
//     "Are you sure you want to delete this book?"
//   );

//   if (!confirmDelete) {
//     return;
//   }

//   try {
//     const response = await fetch(
//       `http://localhost:5000/api/books/${id}`,
//       {
//   method: "DELETE",
//   headers: {
//     Authorization: `Bearer ${localStorage.getItem("adminToken")}`
//   }
// }
//     );

//     const data = await response.json();

//     if (response.ok) {
//   setMessage("Book deleted successfully!");
//   setError("");
//   fetchBooks();
// } else {
//       alert(data.message || "Failed to delete book");
//     }
//   } catch (error) {
//     console.error("Error deleting book:", error);
//     alert("Could not connect to the backend");
//   }
// };

//   return (
//     <div>
//      <div>
//   <h1>BookNav Admin</h1>

//   <button
//     onClick={() => {
//       localStorage.removeItem("adminToken");
//       window.location.reload();
//     }}
//   >
//     Logout
//   </button>
// </div>
// {message && <p>{message}</p>}
//       <h2>{editingBookId ? "Edit Book" : "Add New Book"}</h2>

//       <form onSubmit={handleSubmit}>
//         <input
//           type="text"
//           name="title"
//           placeholder="Book Title"
//           value={formData.title}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <input
//           type="text"
//           name="author"
//           placeholder="Author"
//           value={formData.author}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <input
//           type="text"
//           name="category"
//           placeholder="Category"
//           value={formData.category}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <textarea
//           name="description"
//           placeholder="Description"
//           value={formData.description}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <input
//           type="text"
//           name="shelf"
//           placeholder="Shelf"
//           value={formData.shelf}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <input
//           type="text"
//           name="rack"
//           placeholder="Rack"
//           value={formData.rack}
//           onChange={handleChange}
//         />

//         <br /><br />

//         <input
//           type="text"
//           name="location"
//           placeholder="Library Location"
//           value={formData.location}
//           onChange={handleChange}
//         />

//         <br /><br />

//        <button type="submit">
//   {editingBookId ? "Update Book" : "Add Book"}
// </button>
// {editingBookId && (
//   <button
//     type="button"
//     onClick={() => {
//       setEditingBookId(null);
// setMessage("");
// setError("");
//       setFormData({
//         title: "",
//         author: "",
//         category: "",
//         description: "",
//         shelf: "",
//         rack: "",
//         location: ""
//       });
//     }}
//   >
//     Cancel Edit
//   </button>
// )}
//    </form>

// <h2>Library Books</h2>
// {error && <p>{error}</p>}
// {loading ? (
//   <p>Loading books...</p>
// ) : books.length === 0 ? (
//   <p>No books available.</p>
// ) : (
//   <div>
//     {books.map((book) => (
//       <div key={book._id}>
//         <h3>{book.title}</h3>
//         <p>Author: {book.author}</p>
//         <p>Category: {book.category}</p>
//         <p>Shelf: {book.shelf}</p>
//         <p>Rack: {book.rack}</p>
//        <p>Location: {book.location}</p>
// <button onClick={() => handleEdit(book)}>
//   Edit
// </button>

// <button onClick={() => handleDelete(book._id)}>
//   Delete
// </button>

// <hr />
//       </div>
//     ))}
//   </div>
// )}

//     </div>
//   );
// }

// export default AdminBooks;


import { useEffect, useState } from "react";

function AdminBooks() {
  const [editingBookId, setEditingBookId] = useState(null);

  const [formData, setFormData] = useState({
    title: "",
    author: "",
    category: "",
    description: "",
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
      alert(
        "Please fill in Title, Author, Category, Shelf and Rack."
      );
      return;
    }

    try {
      let response;

      if (editingBookId) {
        // Update existing book
        response = await fetch(
          `http://localhost:5000/api/books/${editingBookId}`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify(formData)
          }
        );
      } else {
        // Add new book
        response = await fetch(
          "http://localhost:5000/api/books",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify(formData)
          }
        );
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
          shelf: "",
          rack: "",
          location: ""
        });

        setEditingBookId(null);

        fetchBooks();
      } else {
        alert(data.message || "Operation failed");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Could not connect to the backend");
    }
  };

  // Fetch all books
  const fetchBooks = async () => {
    setLoading(true);

    try {
      const response = await fetch(
        "http://localhost:5000/api/books"
      );

      const data = await response.json();

      if (response.ok) {
        setBooks(data);
        setError("");
      } else {
        setError(data.message || "Could not load books.");
      }
    } catch (error) {
      console.error("Error fetching books:", error);
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
      shelf: book.shelf || "",
      rack: book.rack || "",
      location: book.location || ""
    });
  };

  // Delete book
  const handleDelete = async (id) => {
    const confirmDelete = window.confirm(
      "Are you sure you want to delete this book?"
    );

    if (!confirmDelete) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:5000/api/books/${id}`,
        {
          method: "DELETE",
          credentials: "include"
        }
      );

      const data = await response.json();

      if (response.ok) {
        setMessage("Book deleted successfully!");
        setError("");

        fetchBooks();
      } else {
        alert(data.message || "Failed to delete book");
      }
    } catch (error) {
      console.error("Error deleting book:", error);
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
      shelf: "",
      rack: "",
      location: ""
    });
  };

  // Admin logout
  const handleLogout = async () => {
    try {
      const response = await fetch(
        "http://localhost:5000/api/admin/logout",
        {
          method: "POST",
          credentials: "include"
        }
      );

      const data = await response.json();

      if (response.ok) {
        alert("Admin logged out successfully!");
      } else {
        console.error(data.message);
      }
    } catch (error) {
      console.error("Logout error:", error);
    }

    window.location.reload();
  };

  return (
    <div>
      <div>
        <h1>BookNav Admin</h1>

        <button onClick={handleLogout}>
          Logout
        </button>
      </div>

      {message && <p>{message}</p>}

      <h2>
        {editingBookId ? "Edit Book" : "Add New Book"}
      </h2>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          name="title"
          placeholder="Book Title"
          value={formData.title}
          onChange={handleChange}
        />

        <br />
        <br />

        <input
          type="text"
          name="author"
          placeholder="Author"
          value={formData.author}
          onChange={handleChange}
        />

        <br />
        <br />

        <input
          type="text"
          name="category"
          placeholder="Category"
          value={formData.category}
          onChange={handleChange}
        />

        <br />
        <br />

        <textarea
          name="description"
          placeholder="Description"
          value={formData.description}
          onChange={handleChange}
        />

        <br />
        <br />

        <input
          type="text"
          name="shelf"
          placeholder="Shelf"
          value={formData.shelf}
          onChange={handleChange}
        />

        <br />
        <br />

        <input
          type="text"
          name="rack"
          placeholder="Rack"
          value={formData.rack}
          onChange={handleChange}
        />

        <br />
        <br />

        <input
          type="text"
          name="location"
          placeholder="Library Location"
          value={formData.location}
          onChange={handleChange}
        />

        <br />
        <br />

        <button type="submit">
          {editingBookId ? "Update Book" : "Add Book"}
        </button>

        {editingBookId && (
          <button
            type="button"
            onClick={handleCancelEdit}
          >
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

              <p>
                Author: {book.author}
              </p>

              <p>
                Category: {book.category}
              </p>

              <p>
                Description: {book.description}
              </p>

              <p>
                Shelf: {book.shelf}
              </p>

              <p>
                Rack: {book.rack}
              </p>

              <p>
                Location: {book.location}
              </p>

              <button
                onClick={() => handleEdit(book)}
              >
                Edit
              </button>

              <button
                onClick={() => handleDelete(book._id)}
              >
                Delete
              </button>

              <hr />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AdminBooks;