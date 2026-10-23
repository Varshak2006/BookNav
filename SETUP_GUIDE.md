# 📚 BookNav — Complete Step-by-Step Setup & Run Guide

Welcome to **BookNav**! This guide contains everything you need to set up, connect the database and datasets, and run the complete application from scratch on your machine.

---

## 🧭 What is BookNav?

BookNav is an intelligent library information retrieval system featuring:
- **React (Vite) Frontend**: Modern user and admin search interface with physical library shelf & rack navigation.
- **Node.js & Express API**: Backend coordinating queries, authentication, and machine learning processes.
- **LACS (Library-Aware Contextual Spell Correction)**: Custom Python spell engine built specifically for library catalogs (fixes typos like *"harry poater"* or *"machin learnin"*).
- **Sentence-BERT & FAISS Vector Search**: Dense 384-dimensional semantic similarity engine that finds relevant books even when exact keywords don't match.
- **MongoDB**: Database for book catalog storage, user accounts, and physical location coordinates.

---

## 📋 System Prerequisites

Before starting, make sure you have the following installed:

| Software | Minimum Version | Download Link |
|---|---|---|
| **Node.js** | `v18.0.0` or higher | [nodejs.org](https://nodejs.org/) |
| **Python** | `3.10` or `3.11` | [python.org](https://www.python.org/downloads/) *(⚠️ Check "Add Python to PATH" during installation)* |
| **MongoDB** | `v5.0` or higher | [MongoDB Community Server](https://www.mongodb.com/try/download/community) or [MongoDB Atlas (Free Cloud)](https://www.mongodb.com/cloud/atlas) |
| **Git** | Any modern version | [git-scm.com](https://git-scm.com/) |

---

## 🚀 Step 1: Clone the Repository

Open your terminal or command prompt and clone the repository:

```bash
git clone https://github.com/Varshak2006/BookNav.git
cd BookNav
```

Switch to the active feature branch:
```bash
git checkout feature/library-navigation
```

---

## ⚙️ Step 2: Configure Environment Variables (`.env`)

BookNav requires configuration for ports, database URI, and ML bridge settings.

### 1. Create Root `.env`
In the root directory of the project, create a file named `.env` (or copy from `.env.example`):

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
Copy-Item .env.example server\.env
```

**On Linux / macOS:**
```bash
cp .env.example .env
cp .env.example server/.env
```

### 2. Verify `.env` Contents
Open `.env` (and `server/.env`) to ensure the settings match your local environment:

```env
# Server Configuration
PORT=5000
NODE_ENV=development
CLIENT_URL=http://localhost:5173

# Database Connection (MongoDB)
# If using local MongoDB:
MONGO_URI=mongodb://localhost:27017/book
# If using MongoDB Atlas Cloud, paste your connection string:
# MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/book?retryWrites=true&w=majority

SESSION_SECRET=booknav_super_secret_session_key_2026
ADMIN_SETUP_TOKEN=booknav_admin_setup_token_secure

# Python Bridge Executable (use 'python' on Windows, or 'python3' on Linux/macOS)
LACS_PYTHON=python
PYTHON_PATH=python

# Request Timeouts
LACS_TIMEOUT_MS=5000
FAISS_TIMEOUT_MS=30000

# Embedding Hyperparameters
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
FAISS_METRIC=inner_product
SEMANTIC_RELEVANCE_THRESHOLD=0.50

# HuggingFace Offline Flags (Set to 0 if downloading the model for the first time)
HF_HUB_OFFLINE=0
TRANSFORMERS_OFFLINE=0
```

---

## 🐍 Step 3: Install Python Dependencies

BookNav uses Python for the LACS spell corrector and FAISS semantic vector search.

### 1. (Recommended) Create a Virtual Environment
From the root directory:

**On Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Required Python Packages
```bash
pip install -r requirements.txt
```

*This installs FAISS (`faiss-cpu`), Sentence-Transformers, PyTorch, NumPy, and PyMongo.*

---

## 📦 Step 4: Install Node.js Dependencies

You need to install dependencies for both the backend server and the frontend client.

### 1. Install Backend Dependencies
```bash
cd server
npm install
cd ..
```

### 2. Install Frontend Dependencies
```bash
cd client
npm install
cd ..
```

---

## 🗄️ Step 5: Database Connection & Seeding Datasets

### 1. Start MongoDB
Make sure MongoDB is running on your machine:
- **Windows Service**: Run `net start MongoDB` or ensure MongoDB service is running in `services.msc`.
- **MongoDB Compass**: You can connect to `mongodb://localhost:27017` to view your data visually.
- **Mac / Linux**: Run `sudo systemctl start mongod` or `brew services start mongodb-community`.

### 2. Seed the Catalog into MongoDB
The project comes with a pre-configured library dataset of **1,079 books** that are mapped to the FAISS vector index.

Run the automated seeder script from the `server/` directory:

```bash
cd server
npm run seed
```

**Expected Output:**
```
=========================================
   BookNav Database Seeding Utility      
=========================================

MongoDB connected successfully to mongodb://localhost:27017/book
Found 1079 books in FAISS mapping dataset.
Upserting books into MongoDB...

Success!
- Upserted: 1079
- Total Books in Catalog: 1079

Database is now synchronized with FAISS vector index mappings!
```

---

## 🖥️ Step 6: Start the Application

You need two terminal windows open: one for the backend server and one for the frontend client.

### Terminal 1: Start Backend Server
```bash
cd server
npm start
```
*Output: `Server is running on port 5000` and `MongoDB connected successfully`.*

### Terminal 2: Start Frontend Client
```bash
cd client
npm run dev
```
*Output: `VITE v... ready in ... ms` with Local URL `http://localhost:5173/`.*

---

## 🌐 Step 7: Explore & Test BookNav

Open your browser and visit: **[http://localhost:5173](http://localhost:5173)**

### Try These Features:

1. **Typo & Spell Correction (LACS)**:
   - Search: `"harry poater"` ➔ LACS corrects it to `"harry potter"`.
   - Search: `"machin learnin"` ➔ Suggests `"machine learning"`.
   - Search: `"pythn crash"` ➔ Suggests `"python crash course"`.

2. **Semantic Vector Search (FAISS)**:
   - Search for conceptual queries without knowing exact titles:
     - `"neural networks and deep learning"`
     - `"building web apps with javascript"`
     - `"algorithms and data structures"`
   - If exact keyword match produces 0 results, semantic fallback triggers automatically to find conceptually related books.

3. **Physical Library Navigation**:
   - Click on any book card.
   - View its physical **Shelf**, **Rack**, and **Library Hall Location** with the interactive visual map!

---

## 🧪 Optional: Running Tests & Verification

If you want to verify that all components and algorithms are passing tests:

### Run Python Algorithmic Tests (164 tests):
```bash
python -m pytest
```

### Run Node.js Integration & Security Test Suites:
```bash
cd server
npm run test:all
```

### Rebuilding FAISS Index (If you add custom books):
```bash
cd server
npm run build-index
```

---

## ❓ Troubleshooting & FAQs

### 1. `Cannot connect to MongoDB` / `ECONNREFUSED 127.0.0.1:27017`
- Ensure MongoDB server is running.
- On Windows, run: `net start MongoDB` in an Administrator terminal.
- Alternatively, check if MongoDB Compass connects to `mongodb://localhost:27017`.

### 2. `python: command not found`
- Make sure Python is in your system's PATH.
- If using `python3`, update `LACS_PYTHON=python3` and `PYTHON_PATH=python3` in your `.env`.

### 3. Sentence-BERT model download on first run
- If running offline or behind a firewall, ensure `HF_HUB_OFFLINE=0` and `TRANSFORMERS_OFFLINE=0` in `.env` so PyTorch can download the lightweight `all-MiniLM-L6-v2` embedding model (~80 MB) on first startup.

### 4. Port 5000 or 5173 already in use
- Change `PORT=5001` in `.env` and `server/.env`.
- Update `VITE_API_BASE_URL=http://localhost:5001/api` in `client/src/config/api.js`.

---

🎉 **You are all set! Share this file (`SETUP_GUIDE.md`) with your friend to get them up and running in minutes.**
