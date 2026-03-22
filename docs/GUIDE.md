# How this app works — a study guide

This document walks through every part of the app from first principles. No prior knowledge assumed.

---

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [The two journeys: Save and Search](#2-the-two-journeys-save-and-search)
3. [The Chrome extension — where everything starts](#3-the-chrome-extension--where-everything-starts)
4. [The API server — the brain of the app](#4-the-api-server--the-brain-of-the-app)
5. [The database layer — storing raw URLs](#5-the-database-layer--storing-raw-urls)
6. [The embedding pipeline — teaching the app to understand meaning](#6-the-embedding-pipeline--teaching-the-app-to-understand-meaning)
7. [The search UI — asking questions](#7-the-search-ui--asking-questions)
8. [How the pieces fit together: data flow diagrams](#8-how-the-pieces-fit-together-data-flow-diagrams)
9. [Why each technology was chosen](#9-why-each-technology-was-chosen)
10. [Key concepts explained](#10-key-concepts-explained)

---

## 1. The big picture

The app is a **personal bookmark manager with semantic search**. The core idea: you save web pages, and later you can search them using natural language ("what was that article about dogs and nutrition?") instead of remembering exact keywords or URLs.

There are four components that talk to each other:

```
[Chrome Extension]  →  [FastAPI Server]  →  [SQLite database]
                                        →  [ChromaDB vector store]
                    ←  [Search UI]      ←  [ChromaDB vector store]
```

- **Chrome Extension** (`extension/`) — the button you click to save a page
- **FastAPI Server** (`api.py`) — receives requests, coordinates all the work
- **SQLite database** (`bookmarks.db`) — stores the raw URLs + timestamps
- **ChromaDB vector store** (`chroma_db/`) — stores the *meaning* of each page so you can search by concept
- **Search UI** (`search.html`) — a web page where you type queries and see results

These all run **locally on your machine**. Nothing is sent to any cloud service.

---

## 2. The two journeys: Save and Search

The entire app exists to serve two actions:

### Saving a bookmark

> "I am reading a page right now. Remember it."

1. You click the extension button in Chrome
2. The extension reads the current URL and sends it to the local server
3. The server saves the URL to the SQLite database (so it's never lost)
4. The server fetches the full text content of the page
5. That text is converted into a vector (a list of numbers that captures the meaning)
6. The vector is saved to ChromaDB alongside the URL

### Searching bookmarks

> "Show me everything I saved about machine learning."

1. You type a query in the search UI
2. The query is converted into a vector using the same method
3. ChromaDB compares that vector to all stored vectors and finds the closest matches
4. The matching URLs are returned and displayed as clickable links

The key insight: **both the saved pages and the query are converted to the same kind of number representation (vectors)**. Searching then becomes a geometry problem — find the stored vectors that are closest to the query vector.

---

## 3. The Chrome extension — where everything starts

**Files:** `extension/manifest.json`, `extension/popup.html`, `extension/popup.js`

### What a Chrome extension is

A Chrome extension is a small web app (HTML + JavaScript) that Chrome loads directly from a folder on your computer. It can access browser internals — like the current tab's URL — that a normal website cannot.

Extensions are defined by `manifest.json`, which tells Chrome:
- What the extension is called
- What permissions it needs
- Which HTML file to show when clicked

### manifest.json

```json
{
  "manifest_version": 3,
  "permissions": ["activeTab", "tabs"],
  "action": {
    "default_popup": "popup.html"
  }
}
```

- `manifest_version: 3` — the current (modern) version of the Chrome extension API
- `"activeTab"` — permission to read information about the tab the user is currently on
- `"tabs"` — permission to query the browser's tab list
- `"default_popup"` — when the user clicks the extension icon, show `popup.html`

### popup.js — the logic (extension/popup.js:4–40)

```js
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
const url = tab.url;
```

`chrome.tabs.query()` is a browser API that returns a list of tabs matching the criteria. `{ active: true, currentWindow: true }` means "the tab the user is looking at right now". The `[tab]` syntax is destructuring — it unpacks the first element of the returned array.

```js
const res = await fetch("http://localhost:8000/save", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url }),
});
```

`fetch()` is the browser's built-in HTTP client. This sends a POST request to the local server with the URL as a JSON body. `JSON.stringify({ url })` converts `{ url: "https://..." }` to a JSON string.

`await` means "wait for this to finish before continuing". Without it, the code would move on before the server responded.

The `try/catch/finally` block handles errors gracefully — if the server isn't running, the extension shows "Could not reach the local server" instead of crashing silently.

### Why this approach

The alternative would be a browser bookmark (Ctrl+D). But browser bookmarks can't run code — they can't extract page text, embed it, or enable semantic search. A Chrome extension is the lightest way to trigger a local computation from within the browser.

---

## 4. The API server — the brain of the app

**File:** `api.py`

### What FastAPI is

FastAPI is a Python library for building HTTP servers. An HTTP server is a program that listens for requests (like the ones your browser sends when you load a page) and sends back responses. FastAPI makes it easy to define what URLs the server responds to and what it does with the data it receives.

### Startup and shutdown — api.py:17–23

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    databset_init()
    yield
    quality_check()
    with open("logged_messages.txt", "w") as f:
        f.write(log_stream.getvalue())
```

This is a **lifespan** function — code that runs when the server starts and when it stops.

- Everything **before** `yield` runs at startup: `databset_init()` creates the SQLite table if it doesn't exist yet
- Everything **after** `yield` runs at shutdown: `quality_check()` cleans dirty data, logs are written to a file

`@asynccontextmanager` is a decorator that turns this function into a context manager — a pattern for "set up, do work, tear down".

### CORS middleware — api.py:28–33

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

**CORS** (Cross-Origin Resource Sharing) is a browser security rule. By default, browsers block JavaScript on one origin (e.g. a Chrome extension) from calling a server on a different origin (e.g. `localhost:8000`). Adding CORS middleware tells FastAPI to send back headers that say "this server allows requests from anywhere", which lets the extension and the search UI call the API.

### Input validation — api.py:36–37

```python
class SaveRequest(BaseModel):
    url: HttpUrl
```

`BaseModel` comes from Pydantic, a data validation library that FastAPI uses automatically. `HttpUrl` is a type that validates the value is a well-formed URL starting with `http://` or `https://`. If the extension sends something invalid, FastAPI automatically rejects it with a 422 error — no manual validation code needed.

### POST /save — api.py:45–55

```python
@app.post("/save")
def save_url(body: SaveRequest):
    url = str(body.url)
    add_link(url)

    text = extract_text(url)
    if text:
        embed_and_store(url, text)
        return {"status": "saved", "url": url, "embedded": True}

    return {"status": "saved", "url": url, "embedded": False}
```

This endpoint does two things in sequence:
1. **Always** save the URL to SQLite (via `add_link`)
2. **Try** to extract text and embed it — if the page is unreachable or has no extractable text, the URL is still saved, just not searchable

The response tells the caller whether embedding happened. `embedded: False` is not an error — the URL is still recorded.

### GET /search — api.py:58–63

```python
@app.get("/search")
def search_urls(q: str = Query(..., min_length=1)):
    results = embedding_search(q)
    ...
```

`Query(..., min_length=1)` means `q` is a required query parameter (the `...` means "required") and must be at least 1 character long. FastAPI validates this automatically — sending `/search` with no `q` returns a 422 error.

---

## 5. The database layer — storing raw URLs

**File:** `database.py`

### What SQLite is

SQLite is a database that lives in a single file (`bookmarks.db`). Unlike databases like PostgreSQL or MySQL, it has no separate server process — the Python code reads and writes the file directly. This makes it perfect for local, single-user apps where simplicity matters more than scalability.

### The table schema — database.py:37–43

```sql
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Date DATE DEFAULT CURRENT_TIMESTAMP,
    URL TEXT
)
```

The `links` table has three columns:
- `id` — a unique number assigned automatically to each row (AUTOINCREMENT)
- `Date` — the timestamp when the URL was saved, filled in automatically
- `URL` — the actual URL text

`CREATE TABLE IF NOT EXISTS` means this is safe to run every time the server starts — it only creates the table if it doesn't already exist.

### The decorator — database.py:8–23

```python
def log_database_interactions(func):
    def wrapper(*args, **kwargs):
        if func.__name__ == "databset_init":
            logging.info("Initializing the database...")
        ...
        result = func(*args, **kwargs)
        return result
    return wrapper
```

A **decorator** is a function that wraps another function to add behaviour before or after it runs, without modifying the original function's code. Here it logs what operation is about to happen before executing the actual database function. `@log_database_interactions` above a function definition applies the decorator.

### Parameterised queries — database.py:64–68

```python
cur.execute('''
    INSERT INTO links (Date, URL) VALUES (CURRENT_TIMESTAMP, ?)
''', (url,))
```

The `?` is a placeholder, not string interpolation. The database driver substitutes the value safely. This prevents **SQL injection** — if a URL contained SQL code (e.g. `'; DROP TABLE links; --`), the `?` approach treats it as literal text, not executable SQL.

### Quality check — database.py:81–147

This runs at shutdown and performs three cleanup passes using SQL queries:
1. Delete rows where `URL IS NULL OR URL = ''`
2. Delete duplicate rows (keep only the earliest entry per URL, identified by the minimum `id`)
3. Delete rows where `URL NOT LIKE 'http%'` (not a valid web URL)

The duplicates query uses a subquery: it first finds the minimum `id` for each unique URL, then deletes everything not in that set.

---

## 6. The embedding pipeline — teaching the app to understand meaning

**File:** `embeddings.py`

This is the most conceptually novel part of the app. Understanding it requires understanding what "embeddings" are.

### What an embedding is

An embedding is a way of representing text as a list of numbers (a **vector**) such that texts with similar meanings produce vectors that are close together in mathematical space.

For example:
- "How to train a dog" → `[0.21, -0.54, 0.87, ...]`
- "Puppy obedience tips" → `[0.19, -0.51, 0.83, ...]`  ← close to the above
- "Python async programming" → `[-0.63, 0.12, -0.44, ...]` ← far from the above

The model (`all-MiniLM-L6-v2`) was trained on massive amounts of text to learn this mapping. It learned that "dog" and "puppy" are semantically related, so their vectors end up close together.

The vector has 384 dimensions (numbers). You can think of it as a point in 384-dimensional space.

### Step 1: Text extraction — embeddings.py:28–42

```python
def extract_text(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded)
    return text
```

**Trafilatura** is a library that fetches a web page and strips out everything except the main readable content — it removes navigation menus, ads, headers, footers, cookie banners. What remains is the article body or the core text of the page.

This is important because embedding the full raw HTML would pollute the vector with irrelevant content. You want the embedding to represent the *meaning* of the page, not its structure.

If extraction fails (the page is behind a login, blocks bots, or has no text content), `None` is returned and the URL is still saved to SQLite — just without a searchable embedding.

### Step 2: Computing the embedding — embeddings.py:45–58

```python
def embed_and_store(url: str, text: str) -> None:
    model = _get_model()
    collection = _get_collection()
    embedding = model.encode(text).tolist()
    collection.upsert(
        ids=[url],
        embeddings=[embedding],
        documents=[text[:500]],
        metadatas=[{"url": url}],
    )
```

`model.encode(text)` runs the text through the neural network and returns a numpy array of 384 numbers. `.tolist()` converts it to a plain Python list (required by ChromaDB).

`collection.upsert()` means "insert if new, update if already exists". The URL is used as the unique ID — so saving the same URL twice just updates the entry instead of creating a duplicate.

The first 500 characters of the text are also stored as a `document` — this is a human-readable snippet for reference, not used in search calculations.

### The singleton pattern — embeddings.py:6–25

```python
_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model
```

Loading the ML model takes a few seconds and uses significant memory. The singleton pattern ensures it is loaded only once — the first time it's needed — and then reused for every subsequent request. `global _model` tells Python to modify the module-level variable, not create a local one.

The same pattern is used for the ChromaDB collection (`_get_collection()`).

### Step 3: Searching — embeddings.py:62–77

```python
def search(query: str, n: int = 10) -> list[str]:
    model = _get_model()
    collection = _get_collection()
    if collection.count() == 0:
        return []
    query_embedding = model.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n, collection.count()),
    )
    return [meta["url"] for meta in results["metadatas"][0]]
```

The query is embedded with the **same model** — this is essential. Both the stored page vectors and the query vector must live in the same mathematical space for the comparison to be meaningful.

`collection.query()` finds the `n` stored vectors closest to the query vector. "Closest" is measured using **cosine similarity** (specified when the collection was created: `"hnsw:space": "cosine"`).

**Cosine similarity** measures the angle between two vectors, not their absolute distance. Two vectors pointing in the same direction have similarity 1.0 (identical meaning); pointing in opposite directions gives -1.0. This works well for text because the overall magnitude of a vector isn't meaningful — only its direction is.

`min(n, collection.count())` prevents an error if you ask for 10 results but only 3 URLs have been saved.

The return value is a list of URLs extracted from the `metadatas` field, ordered from most to least similar.

### What ChromaDB does

ChromaDB is a **vector database** — a database specifically built for storing and querying vectors. It uses an indexing algorithm called HNSW (Hierarchical Navigable Small World) that makes nearest-neighbour search fast even with millions of entries. Data persists to disk in the `./chroma_db/` folder.

You could technically store vectors in SQLite as binary blobs, but you'd have to load all of them into memory and compare manually. ChromaDB handles this efficiently and with a clean API.

---

## 7. The search UI — asking questions

**File:** `search.html`

This is a single self-contained HTML file served by FastAPI at `GET /`. When you open `http://localhost:8000` in a browser, FastAPI reads the file from disk and sends it back:

```python
@app.get("/")
def serve_search_ui():
    return FileResponse("search.html")
```

The page uses `fetch()` — the same browser HTTP client used in the extension — to call `/search?q=...` and render the results as a list of `<a>` links. The Enter key also triggers a search (via the `keydown` event listener).

No frameworks, no build tools — plain HTML and JavaScript. This keeps it simple and means there's nothing to install or compile to modify the UI.

---

## 8. How the pieces fit together: data flow diagrams

### Saving a URL

```
User clicks extension button
        │
        ▼
popup.js reads tab.url
        │
        ▼
fetch POST localhost:8000/save  { url: "https://example.com" }
        │
        ▼
api.py: save_url()
        │
        ├──► add_link(url)          ─────► INSERT INTO links ... ─► bookmarks.db
        │         (database.py)               (SQLite)
        │
        ├──► extract_text(url)      ─────► trafilatura fetches page
        │         (embeddings.py)            strips to main text
        │                                    returns plain string
        │
        └──► embed_and_store(url, text)
                  (embeddings.py)
                       │
                       ├──► model.encode(text)   ─► 384 numbers (vector)
                       │
                       └──► collection.upsert()  ─► chroma_db/ (disk)
        │
        ▼
Response: { "status": "saved", "embedded": true/false }
        │
        ▼
popup.js shows "Saved!" in the popup
```

### Searching

```
User types "dog nutrition" in search.html
        │
        ▼
fetch GET localhost:8000/search?q=dog+nutrition
        │
        ▼
api.py: search_urls()
        │
        └──► embedding_search("dog nutrition")
                  (embeddings.py)
                       │
                       ├──► model.encode("dog nutrition")  ─► query vector
                       │
                       └──► collection.query(query_vector)
                                   │
                                   ▼
                            ChromaDB compares query vector
                            to all stored vectors using
                            cosine similarity
                                   │
                                   ▼
                            Returns top-10 closest matches
                                   │
                                   ▼
                            Extract URL from each result's metadata
        │
        ▼
Response: { "query": "dog nutrition", "results": ["https://...", ...] }
        │
        ▼
search.html renders list of clickable links
```

---

## 9. Why each technology was chosen

| Technology | What it does | Why this one |
|------------|-------------|-------------|
| **FastAPI** | HTTP server | Automatic request validation via Pydantic, auto-generated docs at `/docs`, minimal boilerplate |
| **uvicorn** | Runs the FastAPI app | The standard ASGI server for FastAPI; `--reload` restarts the server when you edit code |
| **SQLite** | Stores raw URLs | Built into Python, zero configuration, single file — perfect for local single-user data |
| **trafilatura** | Extracts page text | Purpose-built for web content extraction; handles boilerplate removal better than raw HTML parsing |
| **sentence-transformers** | Converts text to vectors | `all-MiniLM-L6-v2` is ~80MB, runs on CPU in milliseconds, purpose-built for semantic similarity |
| **ChromaDB** | Stores and queries vectors | Local-first, zero config, handles cosine similarity search with fast indexing |
| **Chrome Extension MV3** | Saves current tab | The only way to read the active tab URL and trigger local computation from within Chrome |
| **Pydantic** | Validates API inputs | Built into FastAPI; catches bad inputs before they reach your code |

### Why not use a bigger/smarter LLM model for search?

The BART and FLAN-T5 models explored earlier are **generative** models — they produce text. For search, you don't need generation; you need **similarity comparison**. `all-MiniLM-L6-v2` is a **sentence encoder** specifically trained for this: map two pieces of text to vectors and check how close they are. It's 100x faster and more appropriate for the task.

### Why two databases (SQLite + ChromaDB)?

They serve different purposes:
- **SQLite** is the source of truth for your bookmarks. It stores the URL and when you saved it. It's simple, reliable, and queryable with standard SQL.
- **ChromaDB** stores the *semantic meaning* of each page as a vector. This is completely separate data — if ChromaDB were deleted, you'd lose search capability but not your bookmarks. You could also rebuild the vectors from the SQLite URLs at any time.

---

## 10. Key concepts explained

### HTTP and REST

HTTP is the protocol browsers and servers use to communicate. A **REST API** is a server that responds to HTTP requests at specific URLs (called **endpoints**) in a predictable way:
- `GET /something` — retrieve data
- `POST /something` — send data to create or trigger something

FastAPI's `@app.get("/search")` and `@app.post("/save")` define these endpoints.

### JSON

JSON (JavaScript Object Notation) is a text format for structured data. `{"url": "https://example.com"}` is JSON. It's what the extension sends to the server and what the server sends back. Python's `json` module and FastAPI handle the conversion to/from Python dicts automatically.

### Vectors and vector spaces

A vector is just a list of numbers, like `[0.2, -0.5, 0.8]`. A **vector space** is the mathematical space where all these vectors live. Each dimension corresponds to some learned feature of the text (though the dimensions are not human-interpretable). Closeness in this space corresponds to semantic similarity — texts with similar meanings end up near each other.

### Cosine similarity

Imagine two arrows pointing from the origin. Cosine similarity measures the cosine of the angle between them. If they point in the same direction: angle = 0°, cos(0°) = 1.0 (identical). If perpendicular: cos(90°) = 0.0 (unrelated). This is preferred over plain distance because it's insensitive to the vector's length — only its direction matters.

### Async vs sync

`async def` and `await` are Python keywords for **asynchronous** code. Normally, when Python waits for something (a network request, a database query), it blocks — nothing else can run. Async allows the program to handle other requests while waiting. FastAPI supports both async and regular (`def`) functions. The current code uses regular `def` endpoints, which FastAPI runs in a thread pool automatically.

### The `finally` block

```python
try:
    conn = sqlite3.connect(...)
    ...
except sqlite3.Error as error:
    ...
finally:
    if conn:
        conn.close()
```

`finally` runs **regardless** of whether an exception was raised. This guarantees the database connection is always closed, even if something went wrong halfway through. Unclosed connections can cause resource leaks or lock the database file.
