# BookNav — Intelligent Library Search System

BookNav is an enterprise-grade library information retrieval application that unifies:
1. **LACS** (Library-Aware Contextual Spell Correction) — custom algorithm preserving library-specific vocabulary, phonetic mapping, n-gram context, and history weighting without relying on generic external spellcheck libraries.
2. **Sentence-BERT** (`all-MiniLM-L6-v2`) — generating dense 384-dimensional semantic text embeddings.
3. **FAISS** (Facebook AI Similarity Search) — high-performance vector indexing (`IndexIDMap2` wrapping `IndexFlatIP`) with cosine similarity via normalized inner product.
4. **MongoDB** — persistent catalog storage with dynamic document schema support (including full `keywords` propagation).
5. **Node.js & Express** — resilient backend API with persistent JSON-lines IPC bridges for Python ML models.
6. **React (Vite)** — reactive frontend with interactive correction banners, suggestion chips, and zero-loss semantic rendering.

---

## 1. System Architecture & Request Lifecycle

```
User Query
    │
    ▼
[Query Validation & Sanitization]
    │
    ▼
[LACS Spell Correction Engine]
(Character edit distance + Phonetic Soundex/Metaphone + Library frequency + Contextual n-grams)
    │
    ▼
[Confidence-Based Decision Engine]
    ├── High Confidence   ──> Auto-apply corrected query & show user feedback banner
    ├── Medium Confidence ──> Offer interactive "Did you mean?" suggestion chip
    └── Low Confidence    ──> Preserve original user query (zero false correction)
    │
    ▼
[Sentence-BERT Embedding Generation]
(`all-MiniLM-L6-v2` produces unit-normalized 384-dim dense vector)
    │
    ▼
[FAISS Vector Search Engine]
(IndexIDMap2 + IndexFlatIP inner product on normalized vectors)
    │
    ▼
[Vector ID -> MongoDB ObjectId Resolution]
(Strict ObjectId validation, stale/deleted record exclusion, score & rank preservation)
    │
    ▼
[Metadata Filtering & Database Hydration]
(Author, Category, Shelf, Rack, Location, Keywords)
    │
    ▼
[Unified Backend Response]
(Includes searchMode: 'keyword' | 'semantic' | 'semantic_fallback', correction details, scores)
    │
    ▼
[React Frontend Search View]
(Displays verified book cards, location metadata, and clickable correction bypass option)
```

---

## 2. Directory Structure

```
BookNav-master/
├── client/                             # React / Vite Frontend
│   ├── src/
│   │   ├── pages/UserHome.jsx          # Main search UI with LACS notifications & bypass
│   │   ├── pages/BookDetails.jsx       # Book metadata & physical library navigation view
│   │   ├── pages/AdminBooks.jsx        # Admin catalog management
│   │   └── pages/AdminLogin.jsx        # Admin authentication
│   ├── package.json
│   └── vite.config.js
│
├── server/                             # Express Backend & Python ML Bridges
│   ├── faiss_bridge.py                 # Resilient stdio JSON-lines bridge for FAISS & SBERT
│   ├── lacs_bridge.py                  # Resilient stdio JSON-lines bridge for LACS
│   ├── faiss_data/                     # Production FAISS index, mappings, and metadata
│   │   ├── book_vectors.index          # 1,079 vectors, 384 dimensions
│   │   ├── book_id_mapping.json        # 1,079 vector ID -> MongoDB ID mappings
│   │   └── index_metadata.json         # Generation ID, model ID, metric metadata
│   ├── faiss_engine/                   # Modular FAISS engine
│   │   ├── embedding_adapter.py        # SBERT encoder with local caching & normalization
│   │   ├── id_mapping.py               # Bi-directional ID mapping manager
│   │   ├── index_manager.py            # FAISS index persistence and generation safety
│   │   ├── index_metadata.py           # Compatibility & generation validator
│   │   ├── search_service.py           # Search logic with metadata filtering
│   │   ├── build_index.py              # CLI index builder from MongoDB records
│   │   └── benchmark.py                # FAISS latency, recall, and index benchmark suite
│   ├── lacs_data/                      # LACS dataset, vocabulary, and evaluation artifacts
│   │   ├── library_books.csv           # Baseline library catalog vocabulary
│   │   ├── correction_history.csv      # Shipped seed correction history
│   │   ├── evaluation_dataset.csv      # 220-sample evaluation dataset (SHA-256 verified)
│   │   └── evaluation_results.json     # Benchmark evaluation metrics
│   ├── lacs_engine/                    # Custom Algorithmic Spell Correction
│   │   ├── evaluate.py                 # Reproducible evaluation runner
│   │   └── lacs/                       # Custom LACS core package
│   │       ├── algorithm.py            # Multi-stage ranking & pipeline coordinator
│   │       ├── vocabulary.py           # Library-aware vocabulary & frequency manager
│   │       ├── character_similarity.py # Damerau-Levenshtein & prefix/suffix similarity
│   │       ├── phonetic_similarity.py  # Double Metaphone / Soundex distance
│   │       ├── candidate_generator.py  # Candidate generation within edit-distance bounds
│   │       ├── context_analyzer.py     # Bi-gram & tri-gram co-occurrence analyzer
│   │       ├── scorer.py               # Weighted multi-feature scoring
│   │       └── confidence.py           # Margin & threshold confidence classification
│   ├── models/
│   │   ├── Book.js                     # Schema with full keywords support
│   │   ├── User.js                     # User model
│   │   └── Admin.js                    # Admin model
│   ├── routes/
│   │   ├── bookRoutes.js               # /search, /semantic-search, /sync-lacs, /accept-correction
│   │   ├── adminRoutes.js              # Hardened admin auth with bootstrap protection
│   │   └── userRoutes.js               # Hardened user auth with session fixation protection
│   ├── services/
│   │   ├── bookSearch.js               # Tokenization and keyword filter builder
│   │   ├── faissService.js             # Express FAISS IPC bridge manager (offline mode flags)
│   │   └── lacsService.js              # Express LACS IPC bridge manager
│   ├── tests/                          # Node.js test suites
│   │   ├── faissIntegration.test.js    # FAISS bridge integration tests (9 tests)
│   │   ├── bookSearch.test.js          # Search filter unit tests (7 tests)
│   │   └── e2e_integration_test.js     # End-to-end integration & lifecycle tests (22 tests)
│   ├── config/db.js                    # Mongoose database connection
│   └── server.js                       # Express application entrypoint
│
├── tests/                              # Python Unit & Invariant Test Suites
│   ├── conftest.py                     # Pytest path configuration
│   └── lacs_tests/                     # 122 custom LACS algorithmic tests
├── scripts/
│   └── verify_queries.py               # Section 30 mandatory end-to-end query verification
├── requirements.txt                    # Python dependency manifest
├── pytest.ini                          # Root pytest configuration
├── .env.example                        # Template environment variables
└── README.md                           # Comprehensive documentation
```

---

## 3. LACS Algorithm Details

LACS is designed specifically for library catalogs, overcoming the weaknesses of general-purpose spellcheckers:
- **Zero Third-Party Spellcheck Dependencies**: Completely custom implementation.
- **Multi-Feature Scoring**:
  $$\text{Score}(c) = w_{\text{char}} S_{\text{char}} + w_{\text{phon}} S_{\text{phon}} + w_{\text{lib}} S_{\text{lib}} + w_{\text{ctx}} S_{\text{ctx}} + w_{\text{hist}} S_{\text{hist}}$$
- **Confidence Calibration**:
  - **High Confidence**: Score exceeds auto-correction threshold ($0.85$) with clear margin over candidate #2.
  - **Medium Confidence**: Candidate score exceeds suggestion threshold ($0.65$); surfaces a "Did you mean?" suggestion.
  - **Low Confidence**: Query is preserved verbatim, protecting technical terms and rare names.
- **Plural & Inflection Safeguard**: Valid plural terms such as `"databases"`, `"algorithms"`, and `"systems"` are protected from unwarranted truncation to singular forms.

---

## 4. Sentence-BERT & FAISS Integration

- **Model Identifier**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- **Text Representation**:
  $$\text{Document Text} = \text{Title} + \text{" by "} + \text{Author} + \text{" | "} + \text{Category} + \text{" | "} + \text{Keywords} + \text{" | "} + \text{Description}$$
- **Normalization**: Document and query vectors are $L_2$-normalized prior to search, making FAISS `IndexFlatIP` inner-product mathematically equivalent to Cosine Similarity:
  $$\text{Similarity}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} \in [-1, 1]$$
- **Offline Reliability**: Both `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are enforced at runtime, ensuring sub-millisecond query execution without remote DNS latency.

---

## 5. Security & Authentication Controls

1. **Admin Registration Bootstrap Protection**: Open public registration of additional admins is blocked. The first administrator can bootstrap the system; subsequent registrations require an authenticated admin session or the `x-admin-setup-token` header.
2. **Session Fixation Prevention**: User and Admin logins invoke `req.session.regenerate()` upon authentication to assign fresh session identifiers.
3. **Correction Feedback Sanitization**: `POST /api/books/accept-correction` enforces length bounds ($\le 100$ characters) and strips control/newline characters.
4. **Internal Diagnostics Protection**: `GET /api/books/vector-status` is restricted to authenticated administrators, while a lightweight `GET /api/books/health` endpoint serves unprivileged health probes.
5. **No Data Tampering During Testing**: Automated tests isolate correction history and FAISS test indices into temporary directories, preventing mutation of live library records.

---

## 6. Installation & Setup

### Prerequisites
- **Node.js**: v18.0.0 or higher (tested on v22.19.0)
- **Python**: 3.10 or 3.11 (tested on Python 3.11.7)
- **MongoDB**: v5.0+ running on `localhost:27017`

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` in the root:
```bash
copy .env.example .env
```
Key defaults:
- `PORT=5000`
- `MONGO_URI=mongodb://localhost:27017/book`
- `SESSION_SECRET=your_secure_session_secret`
- `CLIENT_URL=http://localhost:5173`

### Step 3: Install Node.js Dependencies
```bash
# Server dependencies
cd server
npm install

# Client dependencies
cd ../client
npm install
cd ..
```

---

## 7. Starting the Application

### 1. Start Express Backend
```bash
cd server
npm start
```
*Backend runs on `http://localhost:5000`.*

### 2. Start React Frontend
```bash
cd client
npm run dev
```
*Frontend runs on `http://localhost:5173`.*

---

## 8. Running Tests & Benchmarks

### A. All Python Tests (150 tests)
```bash
python -m pytest
```
*Runs all 122 LACS tests and 28 FAISS engine tests. Total time: ~0.70s.*

### B. Node.js Test Suites (38 tests)
```bash
cd server
npm test
```
*Runs FAISS Integration (9 tests), BookSearch Filter (7 tests), and End-to-End Lifecycle & Query tests (22 tests).*

### C. Run LACS Evaluation
```bash
python server/lacs_engine/evaluate.py
```
*Evaluates 220 samples across the SHA-256 verified evaluation dataset without modifying live history.*
- **Top-1 Accuracy**: 92.27%
- **Top-3 Suggestion Accuracy**: 100.00%
- **Preservation Rate**: 100.00%
- **False Correction Rate**: 0.00%
- **Mean Latency**: 0.245 ms

### D. Run FAISS Performance Benchmarks
```bash
python server/faiss_engine/benchmark.py --queries 100
```
*Measures latency distribution (p50, p95, p99) and Recall@K comparing IndexFlatIP, IndexHNSWFlat, and IndexIVFFlat.*

### E. Run Mandatory Section 30 End-to-End Query Verification
```bash
python scripts/verify_queries.py
```

### F. Client Linter & Production Build
```bash
cd client
npm run lint
npm run build
```

---

## 9. API Reference

| Endpoint | Method | Access | Description |
|---|---|---|---|
| `/api/books/search` | `GET` | Public | Standard hybrid search (`q`, `mode`, `correct`, filters). Returns `searchMode: "keyword"` or `"semantic_fallback"`. |
| `/api/books/semantic-search` | `GET` | Public | Vector similarity search (`q`, `top_k`, filters, `correct`). Returns `searchMode: "semantic"`. |
| `/api/books/health` | `GET` | Public | Minimal health probe (`status: "ok"`, `mongodb_connected: true`). |
| `/api/books/vector-status` | `GET` | Admin | Comprehensive diagnostics (FAISS index size, generation, SBERT readiness, Mongo counts). |
| `/api/books/sync-lacs` | `POST` | Admin | Synchronizes LACS vocabulary with all live MongoDB books. |
| `/api/books/accept-correction` | `POST` | Public/Auth | Records validated user-accepted spelling correction into history. |
| `/api/admin/register` | `POST` | Bootstrap/Admin | Creates administrator account. |
| `/api/admin/login` | `POST` | Public | Authenticates admin and starts secure session. |

### Correction Bypass Mechanism
If a user prefers their exact query (e.g. clicking "Search instead for 'original query'"), the frontend passes:
```
GET /api/books/search?q=harry+poater&correct=false
```
When `correct=false` (or `mode=exact`), LACS processing is completely bypassed and the exact query is searched.

---

## 10. FAISS Index Maintenance & Rebuilding

To rebuild the FAISS index safely from all books stored in MongoDB:
```bash
cd server
npm run build-index
```
The build process:
1. Streams books directly from MongoDB.
2. Generates embeddings using `EmbeddingAdapter`.
3. Validates vector dimensions and uniqueness.
4. Generates matching `book_vectors.index`, `book_id_mapping.json`, and `index_metadata.json` with matching Generation UUID.

---

## 11. Known Limitations & Recommendations

1. **Exact vs. ANN Trade-off**: At the current catalog size of 1,079 books, exact search (`IndexFlatIP`) achieves p95 query latency under $0.05$ ms with 100% recall. ANN indexes (`IndexHNSWFlat`, `IndexIVFFlat`) are implemented and benchmarked, but exact search is recommended until catalog size exceeds 50,000 documents.
2. **First-Time Model Loading**: On cold start, PyTorch loads the `all-MiniLM-L6-v2` transformer weights (~80MB). Subsequent searches are processed in under 5ms per query via the persistent bridge process.
