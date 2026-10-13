# BookNav — Integrated Library Search System

BookNav is an enterprise-grade library information retrieval application that unifies:
1. **LACS (Library-Aware Contextual Spell Correction)**: Custom algorithmic spell-correction engine built specifically for library catalogs without external spellcheck libraries. Incorporates Damerau-Levenshtein edit distance, phonetic mapping (Double Metaphone / Soundex), library frequency, n-gram contextual co-occurrence, and historical feedback weighting.
2. **Sentence-BERT (`all-MiniLM-L6-v2`)**: Dense 384-dimensional semantic text embeddings with unit $L_2$ normalization and offline cache isolation.
3. **FAISS (Facebook AI Similarity Search)**: Vector indexing via `IndexIDMap2` wrapping `IndexFlatIP`, providing cosine similarity search, index readiness validation, staged rebuilding, and generation safety.
4. **MongoDB Catalog Storage**: Persistent catalog storage (`Book` schema supporting `title`, `author`, `category`, `description`, `keywords`, `shelf`, `rack`, `location`).
5. **Node.js & Express Backend**: Resilient REST API with persistent JSON-lines IPC bridges for Python ML workers, bounded over-fetching, rate limiting, and session security.
6. **React (Vite) Frontend**: Modern search interface with real-time spell-correction chips, original-query bypass, and semantic result cards.

---

## 1. System Architecture & Request Lifecycle

```
User Query (Frontend)
    │
    ▼
[Express Server: Input Validation & Operator Stripping]
    │
    ├── Mode = "exact" OR correct = "false" (Bypass Activated)
    │     └── Bypass LACS, effectiveQuery = originalQuery, lacsStatus = "bypassed"
    │
    ▼
[LACS Spell Correction Engine (Python IPC Bridge)]
(Character edit distance + Phonetic Soundex/Metaphone + Library frequency + Contextual n-grams)
    │
    ├── High Confidence   ──> Auto-apply corrected query & show user feedback banner
    ├── Medium Confidence ──> Offer interactive "Did you mean?" suggestion chip
    └── Low Confidence    ──> Preserve original user query (zero false correction)
    │
    ▼
[Keyword Search (MongoDB)]
    ├── If matches found ──> Return books immediately (searchMode: "keyword")
    └── If 0 matches found ──> Trigger Semantic Fallback
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
    [Enriched Response]
    (searchMode: "semantic_fallback", fallbackStatus: "success")
```

---

## 2. Directory Structure

```
BookNav-Integrated/
├── client/                             # React / Vite Frontend
│   ├── src/
│   │   ├── config/api.js               # Centralized API URL configuration
│   │   ├── pages/UserHome.jsx          # Main search UI with LACS notifications & bypass
│   │   ├── pages/BookDetails.jsx       # Book metadata & physical library navigation view
│   │   ├── pages/AdminBooks.jsx        # Admin catalog management (with keywords input)
│   │   ├── pages/AdminLogin.jsx        # Admin authentication
│   │   ├── pages/UserLogin.jsx         # User authentication
│   │   └── pages/UserRegister.jsx      # User registration
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
│   │   ├── validator.py                # Comprehensive index readiness validator (13 checks)
│   │   ├── embedding_adapter.py        # SBERT encoder with local caching & normalization
│   │   ├── id_mapping.py               # Bi-directional ID mapping manager
│   │   ├── index_manager.py            # FAISS index persistence and generation safety
│   │   ├── index_metadata.py           # Compatibility & generation validator
│   │   ├── search_service.py           # Search logic with metadata filtering
│   │   ├── build_index.py              # Safe staged index builder with rollback
│   │   └── benchmark.py                # FAISS latency, recall, and index benchmark suite
│   ├── lacs_data/                      # LACS dataset, vocabulary, and evaluation artifacts
│   │   ├── library_books.csv           # Baseline library catalog vocabulary
│   │   ├── correction_history.csv      # Seed correction history
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
│   │   ├── bookRoutes.js               # /search, /semantic-search, /reconcile, /sync-diagnostics
│   │   ├── adminRoutes.js              # Hardened admin auth with rate limiting & bootstrap token
│   │   └── userRoutes.js               # Hardened user auth with rate limiting & session regeneration
│   ├── services/
│   │   ├── bookSearch.js               # Tokenization and keyword filter builder
│   │   ├── faissService.js             # Express FAISS IPC bridge manager (readiness tracking)
│   │   └── lacsService.js              # Express LACS IPC bridge manager
│   ├── tests/                          # Node.js test suites
│   │   ├── faissIntegration.test.js    # FAISS bridge integration tests (9 tests)
│   │   ├── bookSearch.test.js          # Search filter unit tests (6 tests)
│   │   ├── e2e_integration_test.js     # End-to-end integration & lifecycle tests (11 tests)
│   │   ├── securityRegression.test.js  # Security regression tests (8 tests)
│   │   ├── staleResults.test.js        # Stale results exclusion tests (4 tests)
│   │   ├── originalQueryBypass.test.js # Query bypass regression tests (4 tests)
│   │   └── verify_queries_runner.js    # Section 19 10-query validation runner (10 tests)
│   ├── config/db.js                    # Mongoose database connection
│   └── server.js                       # Express application entrypoint
│
├── tests/                              # Python Unit & Invariant Test Suites
│   ├── conftest.py                     # Pytest path configuration
│   └── lacs_tests/                     # 122 custom LACS algorithmic tests
├── scripts/
│   └── verify_queries.py               # Python end-to-end query verification
├── requirements.txt                    # Python dependency manifest
├── pytest.ini                          # Root pytest configuration
├── .env.example                        # Template environment variables
└── README.md                           # Comprehensive documentation
```

---

## 3. LACS Algorithm Details

LACS is designed specifically for library catalogs, avoiding general-purpose spellcheck libraries:
- **Zero Third-Party Spellcheck Dependencies**: Pure Python algorithm with domain-specific heuristics.
- **Multi-Feature Scoring**:
  $$\text{Score}(c) = w_{\text{char}} S_{\text{char}} + w_{\text{phon}} S_{\text{phon}} + w_{\text{lib}} S_{\text{lib}} + w_{\text{ctx}} S_{\text{ctx}} + w_{\text{hist}} S_{\text{hist}}$$
- **Confidence Calibration**:
  - **High Confidence**: Score exceeds auto-correction threshold ($0.85$) with clear margin over candidate #2. Applied automatically.
  - **Medium Confidence**: Candidate score exceeds suggestion threshold ($0.65$); surfaces a "Did you mean?" suggestion chip.
  - **Low Confidence**: Query is preserved verbatim, protecting technical terms and rare names.
- **Plural & Inflection Safeguard**: Valid plural terms such as `"databases"`, `"algorithms"`, and `"systems"` are protected from unwarranted truncation to singular forms.
- **Correction Feedback**: User feedback accepted via `POST /api/books/accept-correction` is sanitized and recorded into `correction_history.csv` to boost future candidate scores.

---

## 4. Sentence-BERT & FAISS Integration

- **Model Identifier**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- **Document Text Representation**: The identical formatting template is used for batch indexing and incremental updates:
  $$\text{Document Text} = \text{Title} + \text{" by "} + \text{Author} + \text{" | "} + \text{Category} + \text{" | "} + \text{Keywords} + \text{" | "} + \text{Description}$$
- **Normalization**: Document and query vectors are $L_2$-normalized prior to search, making FAISS `IndexFlatIP` inner-product mathematically equivalent to Cosine Similarity:
  $$\text{Similarity}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} \in [-1, 1]$$
- **Readiness Verification (`validator.py`)**: Checks all 13 integrity conditions before serving:
  1. Index file existence and loadability
  2. ID mapping file existence and loadability
  3. Metadata file existence and valid JSON
  4. Generation UUID consistency between index, mapping, and metadata
  5. Vector count equals mapping entry count exactly
  6. Sequential ID consistency (`0` through `N-1`)
  7. Vector dimension matches configuration (384)
  8. Similarity metric matches configuration (`inner_product`)
  9. Model identifier matches configuration (`all-MiniLM-L6-v2`)
  10. Non-empty vector count unless explicitly allowed
  11. Index corruption detection
  12. Truncated file detection
  13. Model loading availability

If validation fails, the service reports unready (`INDEX_NOT_READY`), blocks invalid searches, and prevents silent substitution of empty indexes.

---

## 5. Safe Index Rebuilding & Staged Activation

Index rebuilding never mutates the active generation in place:
1. Rebuild artifacts are written to `.staged` files (`book_vectors.index.staged`, `book_id_mapping.json.staged`, `index_metadata.json.staged`).
2. Artifacts are fully validated using `validate_index_artifacts()`. Empty rebuilds are rejected unless `--allow-empty` is passed.
3. The existing generation is backed up to `.prev` files (`book_vectors.index.prev`, etc.).
4. The staged files are atomically activated.
5. If any validation or building error occurs, the previous generation remains untouched.
6. A rollback command (`python -m faiss_engine.build_index --restore`) restores the `.prev` generation instantly.

---

## 6. Stale FAISS Results & Bounded Over-Fetching

When books are deleted or modified in MongoDB:
- `resolveFaissResults()` strictly validates all MongoDB ObjectIds before querying.
- Missing or deleted records in FAISS are excluded safely without fabricating placeholder objects.
- FAISS vector scores and relative ranking are preserved for all valid records.
- To prevent returning fewer results than requested when stale vectors exist, the search pipeline performs bounded over-fetching:
  $$\text{Candidate Limit} = \min(100, \max(\text{requestedLimit}, \lceil 1.5 \times \text{requestedLimit} \rceil))$$
- An admin reconciliation endpoint (`POST /api/books/reconcile`) is available to sync LACS vocabulary and rebuild the FAISS index against live MongoDB state.

---

## 7. Keywords Data Flow

The `keywords` field is a core attribute of the `Book` schema and is preserved end-to-end:
1. **Admin UI (`AdminBooks.jsx`)**: Dedicated form field for entering comma-separated keywords.
2. **MongoDB Model (`Book.js`)**: Declared as `keywords: { type: String, default: "" }`.
3. **Admin Create / Update Operations**: Sanitized via `ALLOWED_BOOK_FIELDS` and saved to MongoDB.
4. **LACS Vocabulary**: Synced into `library_books.csv` during book creation and vocabulary reconciliation.
5. **FAISS Embedding**: Included directly in `Document Text` embedding string.
6. **Keyword Search**: Queried via `$regex` in `buildSearchFilter()`.
7. **Semantic Search Filter**: Supports filtering by `?keywords=...`.

---

## 8. Security & Hardening Controls

1. **Production Session Secret**: `server.js` requires `SESSION_SECRET` in production (`NODE_ENV=production`), preventing startup with insecure defaults.
2. **Security Headers**: Standard security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`) added to all responses.
3. **Rate Limiting**:
   - Admin Login: 5 attempts per 15 minutes per IP (`/api/admin/login`).
   - User Login: 5 attempts per 15 minutes per IP (`/api/users/login`).
   - Correction Feedback: 15 submissions per 15 minutes per IP (`/api/books/accept-correction`).
4. **Admin Bootstrap Protection**: Open public registration of additional admins is blocked. Subsequent registrations require an authenticated session or timing-safe `x-admin-setup-token` header (`safeTokenCompare`).
5. **Session Fixation Prevention**: User and Admin logins invoke `req.session.regenerate()` upon authentication.
6. **Input Sanitization & Injection Prevention**:
   - Query filters strip MongoDB operators (`$gt`, `$ne`, etc.) by enforcing strict string types.
   - Book create/update routes enforce `ALLOWED_BOOK_FIELDS` to prevent mass assignment.
   - ObjectIds on `/:id` are validated via `mongoose.Types.ObjectId.isValid()`, returning 400 on invalid IDs.
7. **Information Disclosure Prevention**: Error handlers return generic user-friendly messages (`message: "Internal server error"`) without leaking internal Python tracebacks or stack traces.

---

## 9. Configuration & Environment Variables

Copy `.env.example` to `.env` in the root and in `server/.env`:
```bash
copy .env.example .env
copy .env.example server\.env
```

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Express server port |
| `MONGO_URI` | `mongodb://localhost:27017/book` | MongoDB connection URI |
| `SESSION_SECRET` | Required in production | Express session encryption secret |
| `NODE_ENV` | `development` | Environment mode (`development` / `production` / `test`) |
| `CLIENT_URL` | `http://localhost:5173` | Allowed CORS frontend origin |
| `SEMANTIC_RELEVANCE_THRESHOLD` | `null` (disabled) | Optional cosine similarity floor (disabled by default) |
| `LACS_VOCAB_PATH` | `server/lacs_data/library_books.csv` | LACS catalog vocabulary CSV |
| `LACS_HISTORY_PATH` | `server/lacs_data/correction_history.csv` | LACS correction feedback CSV |
| `FAISS_DATA_DIR` | `server/faiss_data` | FAISS index, mapping, and metadata directory |
| `SBERT_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Sentence-BERT model identifier |
| `EMBEDDING_DIM` | `384` | Vector dimension |

---

## 10. Installation & Setup

### Prerequisites
- **Node.js**: v18.0.0 or higher (verified on v22.19.0)
- **Python**: 3.10 or 3.11 (verified on Python 3.11.7)
- **MongoDB**: v5.0+ running on `localhost:27017`

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install Node.js Dependencies
```bash
# Backend dependencies
cd server
npm install

# Frontend dependencies
cd ../client
npm install
cd ..
```

---

## 11. Starting the Application

### 1. Start MongoDB
Ensure MongoDB is running locally:
```bash
# If using Windows Service:
net start MongoDB
```

### 2. Start Express Backend
```bash
cd server
npm start
```
*Backend runs on `http://localhost:5000`.*

### 3. Start React Frontend
```bash
cd client
npm run dev
```
*Frontend runs on `http://localhost:5173`.*

---

## 12. Running Tests & Benchmarks

### A. All Python Tests (164 tests)
```bash
python -m pytest
```
*Runs 122 LACS algorithmic tests, 28 FAISS engine tests, and 14 readiness & staged rebuild tests.*

### B. All Node.js Test Suites
```bash
cd server
npm run test:all
```
*Runs all 6 Node.js test suites sequentially:*
1. `tests/faissIntegration.test.js`: FAISS IPC bridge and vector operations (9 tests)
2. `tests/bookSearch.test.js`: Keyword filter tokenization and queries (6 tests)
3. `tests/e2e_integration_test.js`: End-to-end CRUD, search, and diagnostics (11 tests)
4. `tests/securityRegression.test.js`: Headers, injection, rate limiting, and auth (8 tests)
5. `tests/staleResults.test.js`: Stale exclusions, deduplication, and bounds (4 tests)
6. `tests/originalQueryBypass.test.js`: LACS bypass and query preservation (4 tests)
7. `tests/verify_queries_runner.js`: Section 19 mandatory query audit (10 queries)

### C. Run LACS Evaluation
```bash
python server/lacs_engine/evaluate.py
```
*Evaluates 220 labeled test cases across the SHA-256 verified evaluation dataset:*
- **Top-1 Accuracy**: 92.27%
- **Top-3 Accuracy**: 100.00%
- **Preservation Rate**: 100.00%
- **False Correction Rate**: 0.00%
- **Mean Latency**: 0.216 ms

### D. Run FAISS Performance Benchmarks
```bash
python -m faiss_engine.benchmark --queries 100
```
*Evaluates latency distribution (p50, p95, p99) and Recall@K comparing IndexFlatIP, IndexHNSWFlat, and IndexIVFFlat.*
- **FlatIP Build Time**: 0.54 ms
- **Search Latency (p50)**: 0.036 ms
- **Search Latency (p95)**: 0.046 ms
- **Recall@10**: 100.00%

### E. Frontend Linter & Production Build
```bash
cd client
npm run lint
npm run build
```

---

## 13. Index Validation, Rebuild & Recovery

### Validate Current Index
```bash
python -c "from faiss_engine.validator import validate_index_artifacts; print(validate_index_artifacts('server/faiss_data', 384, 'inner_product', 'sentence-transformers/all-MiniLM-L6-v2'))"
```

### Safe Staged Rebuild from MongoDB
```bash
cd server
npm run build-index
```

### Restore Previous Generation (Rollback)
```bash
python -m faiss_engine.build_index --restore
```

### Full Online Reconciliation (Admin Endpoint)
```bash
curl -X POST http://localhost:5000/api/books/reconcile \
  -H "Cookie: connect.sid=..."
```

---

## 14. API Reference

| Endpoint | Method | Access | Description |
|---|---|---|---|
| `/api/books/search` | `GET` | Public | Standard hybrid search (`q`, `mode`, `correct`, filters). Returns `searchMode: "keyword"` or `"semantic_fallback"`. |
| `/api/books/semantic-search` | `GET` | Public | Vector similarity search (`q`, `top_k`, filters, `correct`). Returns `searchMode: "semantic"`. |
| `/api/books/health` | `GET` | Public | Health probe (`mongodb_connected: true`, `faiss_ready: true`). |
| `/api/books/vector-status` | `GET` | Admin | Comprehensive diagnostics (FAISS index size, generation, SBERT readiness, Mongo counts). |
| `/api/books/sync-diagnostics` | `GET` | Admin | Checks if MongoDB count matches FAISS vector count and LACS vocab size. |
| `/api/books/reconcile` | `POST` | Admin | Re-synchronizes LACS vocabulary and rebuilds FAISS index safely. |
| `/api/books/sync-lacs` | `POST` | Admin | Synchronizes LACS vocabulary with all live MongoDB books. |
| `/api/books/accept-correction` | `POST` | Public | Records validated user-accepted spelling correction into history (rate-limited). |
| `/api/admin/login` | `POST` | Public | Authenticates admin (rate-limited, session regenerated). |
| `/api/admin/register` | `POST` | Bootstrap/Admin | Creates administrator account. |
| `/api/users/login` | `POST` | Public | Authenticates user (rate-limited, session regenerated). |

### Correction Bypass Parameter
To bypass LACS correction explicitly:
```
GET /api/books/search?q=harry+poater&correct=false
```
Returns:
- `query`: `"harry poater"`
- `effectiveQuery`: `"harry poater"`
- `correctionApplied`: `false`
- `lacsStatus`: `"bypassed"`

---

## 15. Troubleshooting

1. **FAISS Service Returns 503 (`INDEX_NOT_READY`)**:
   - Cause: Index vector count does not match ID mapping count, files are missing, or generation IDs mismatch.
   - Solution: Run `cd server && npm run build-index` to safely rebuild the index from MongoDB.
2. **PyTorch Offline Mode Error**:
   - Cause: `HF_HUB_OFFLINE=1` is set but the model `sentence-transformers/all-MiniLM-L6-v2` has not been downloaded to cache.
   - Solution: Run Python once with internet access:
     `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"`
3. **MongoDB Connection Failed on Startup**:
   - Cause: MongoDB service is not started on `localhost:27017`.
   - Solution: Start MongoDB service (`net start MongoDB` on Windows) before starting the Express server.
4. **Admin Registration Blocked (`403 Forbidden`)**:
   - Cause: An admin already exists in MongoDB and open registration is blocked.
   - Solution: Log in as the existing admin, or supply the `x-admin-setup-token` matching `ADMIN_SETUP_TOKEN` in `.env`.

---

## 16. Known Limitations

1. **Exact vs. ANN Trade-off**: At the current catalog size of 1,079 books, exact search (`IndexFlatIP`) achieves p95 query latency under $0.05$ ms with 100% recall. Approximate indexes (`IndexHNSWFlat`, `IndexIVFFlat`) are supported and benchmarked, but exact search is recommended until catalog size exceeds 50,000 documents.
2. **Cold Start Model Loading**: On cold start, PyTorch loads the `all-MiniLM-L6-v2` transformer weights (~80MB). Subsequent searches are processed in under 5ms per query via the persistent bridge process.
3. **Semantic Relevance Threshold**: Cosine similarity distribution varies across domain queries. The `SEMANTIC_RELEVANCE_THRESHOLD` parameter is optional and disabled by default (`null`) to avoid false-negative exclusions on broad technical queries until a domain-specific calibration set is configured.
