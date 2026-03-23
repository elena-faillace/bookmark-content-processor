# How this app works — a study guide

This document walks through every part of the app.

---

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [The two journeys: Save and Search](#2-the-two-journeys-save-and-search)
3. [The browser extensions — where everything starts](#3-the-browser-extensions--where-everything-starts)
4. [The API server — the brain of the app](#4-the-api-server--the-brain-of-the-app)
5. [The storage and embedding pipeline](#5-the-storage-and-embedding-pipeline)
6. [The search UI — asking questions](#6-the-search-ui--asking-questions)
7. [How the pieces fit together: data flow diagrams](#7-how-the-pieces-fit-together-data-flow-diagrams)
8. [Why each technology was chosen](#8-why-each-technology-was-chosen)
9. [Key concepts explained](#9-key-concepts-explained)
10. [Running the server automatically on login](#10-running-the-server-automatically-on-login)

---

## 1. The big picture

The app is a **personal bookmark manager with semantic search**. The core idea: you save web pages, and later you can search them using natural language ("what was that article about dogs and nutrition?") instead of remembering exact keywords or URLs.

There are four components that talk to each other:

```
[Browser Extension]  →  [FastAPI Server]  →  [ChromaDB]
                     ←  [Search UI]       ←  [ChromaDB]
```

- **Browser Extension** (`extension-chrome/` or `extension-firefox/`) — the button you click to save a page
- **FastAPI Server** (`api.py`) — receives requests, coordinates all the work
- **ChromaDB** (`chroma_db/`) — the single database: stores the URL, timestamp, and the *meaning* of each page as a vector
- **Search UI** (`search.html`) — a web page where you type queries and see results

These all run **locally on your machine**. Nothing is sent to any cloud service.

---

## 2. The two journeys: Save and Search

The entire app exists to serve two actions:

### Saving a bookmark

> "I am reading a page right now. Remember it."

1. You click the extension button in Chrome
2. The extension reads the current URL and sends it to the local server
3. The server fetches the full text content of the page
4. If extraction succeeds: the text is converted into a vector and stored in ChromaDB with a timestamp
5. If extraction fails (login-walled page, bot-blocked, no text): the URL itself is embedded and stored as a fallback — the bookmark is still saved and URL-searchable

### Searching bookmarks

> "Show me everything I saved about machine learning."

1. You type a query in the search UI
2. The query is converted into a vector using the same method
3. ChromaDB compares that vector to all stored vectors and finds the closest matches
4. The matching URLs are returned and displayed as clickable links

The key insight: **both the saved pages and the query are converted to the same kind of number representation (vectors)**. Searching then becomes a geometry problem — find the stored vectors that are closest to the query vector.

---

## 3. The browser extensions — where everything starts

There are two extensions — one for Chrome, one for Firefox — in `extension-chrome/` and `extension-firefox/`. They share identical `popup.html` and `popup.js`; only the `manifest.json` differs between them.

### Installing in Chrome

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension-chrome/` folder inside this repo
5. The "Bookmark Saver" icon appears in your toolbar (you may need to pin it via the puzzle-piece menu)

### Installing in Firefox

Firefox requires a few extra steps because it does not allow loading unpacked extensions permanently — only as temporary add-ons that last until the browser restarts.

**To load it temporarily (for testing):**

1. Open `about:debugging` in Firefox
2. Click **This Firefox** in the left sidebar
3. Click **Load Temporary Add-on...**
4. Navigate to the `extension-firefox/` folder and select the `manifest.json` file (not the folder itself — Firefox requires you to pick a specific file)
5. The "Bookmark Saver" icon appears in your toolbar

The extension will be removed the next time Firefox restarts. To make it persistent, you would need to sign it through Mozilla's Add-on Developer Hub — but for local personal use, re-loading it when needed is the practical approach.

**Common Firefox pitfalls:**

- **Selecting the folder instead of the file** — Firefox's file picker requires you to select `manifest.json` inside the folder, not the folder itself. Chrome is the opposite (it wants the folder).
- **"Manifest version 3 is not supported"** — this is why the Firefox extension uses `manifest_version: 2`. If you see this, you may have accidentally loaded the `extension-chrome/` folder in Firefox.
- **Icon missing after restart** — expected; temporary add-ons don't survive restarts. Re-load via `about:debugging`.

### What a browser extension is

A browser extension is a small web app (HTML + JavaScript) that the browser loads directly from a folder on your computer. It can access browser internals — like the current tab's URL — that a normal website cannot.

Extensions are defined by `manifest.json`, which tells the browser:
- What the extension is called
- What permissions it needs
- Which HTML file to show when clicked

### Why the two manifests differ

```json
// extension-chrome/manifest.json (Manifest V3)
{
  "manifest_version": 3,
  "action": { "default_popup": "popup.html" }
}
```

```json
// extension-firefox/manifest.json (Manifest V2)
{
  "manifest_version": 2,
  "browser_action": { "default_popup": "popup.html" },
  "browser_specific_settings": { "gecko": { "id": "bookmark-saver@localhost" } }
}
```

- Chrome uses Manifest V3 (`action`) — the current standard
- Firefox uses Manifest V2 (`browser_action`) — Firefox's MV3 support is still incomplete, so V2 is more reliable
- `browser_specific_settings.gecko.id` is required by Firefox to identify the extension; Chrome ignores it
- Firefox requires `"http://localhost:8484/*"` in `permissions` to allow `fetch` calls to the local server — `http://localhost/*` is not enough because Firefox only matches port 80 (the default) unless the port is made explicit; Chrome does not enforce this for localhost

The JavaScript (`popup.js`) is identical for both. Firefox maps the `chrome.*` namespace to its own `browser.*` API automatically, so the same code works in both browsers without any changes.

### popup.js — the logic (popup.js:4–40)

```js
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
const url = tab.url;
```

`chrome.tabs.query()` is a browser API that returns a list of tabs matching the criteria. `{ active: true, currentWindow: true }` means "the tab the user is looking at right now". The `[tab]` syntax is destructuring — it unpacks the first element of the returned array.

```js
const res = await fetch("http://localhost:8484/save", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url }),
});
```

`fetch()` is the browser's built-in HTTP client. This sends a POST request to the local server with the URL as a JSON body. `JSON.stringify({ url })` converts `{ url: "https://..." }` to a JSON string.

`await` means "wait for this to finish before continuing". Without it, the code would move on before the server responded.

The `try/catch/finally` block handles errors gracefully — if the server isn't running, the extension shows "Could not reach the local server" instead of crashing silently.

---

## 4. The API server

**File:** `api.py`

### What FastAPI is

FastAPI is a Python library for building HTTP servers. An HTTP server is a program that listens for requests (like the ones your browser sends when you load a page) and sends back responses. FastAPI makes it easy to define what URLs the server responds to and what it does with the data it receives.

### Startup and shutdown — api.py:17–23

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Server starting up.")
    yield
    quality_check()
    with open("logged_messages.txt", "w") as f:
        f.write(log_stream.getvalue())
```

This is a **lifespan** function — code that runs when the server starts and when it stops.

- Everything **before** `yield` runs at startup: just a log message — ChromaDB creates its collection lazily on first use, so no explicit initialisation is needed
- Everything **after** `yield` runs at shutdown: `quality_check()` removes any invalid entries from ChromaDB, logs are written to a file

`@asynccontextmanager` is a decorator that turns this function into a context manager — a pattern for "set up, do work, tear down".

### CORS middleware — api.py:28–33

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

**CORS** (Cross-Origin Resource Sharing) is a browser security rule. By default, browsers block JavaScript on one origin (e.g. a Chrome extension) from calling a server on a different origin (e.g. `localhost:8484`). Adding CORS middleware tells FastAPI to send back headers that say "this server allows requests from anywhere", which lets the extension and the search UI call the API.

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
    text = extract_text(url)
    if text:
        embed_and_store(url, text)
        return {"status": "saved", "url": url, "embedded": True}

    store_url_only(url)
    return {"status": "saved", "url": url, "embedded": False}
```

This endpoint tries to extract and embed the page content. If extraction succeeds, the full text embedding is stored. If it fails (page behind login, no text content, bot-blocked), `store_url_only` is called instead — the URL itself is embedded so the bookmark is still saved and searchable by URL string.

The response tells the caller whether full content embedding happened. `embedded: False` is not an error — the bookmark is still recorded in ChromaDB.

### GET /search — api.py:58–63

```python
@app.get("/search")
def search_urls(q: str = Query(..., min_length=1)):
    results = embedding_search(q)
    ...
```

`Query(..., min_length=1)` means `q` is a required query parameter (the `...` means "required") and must be at least 1 character long. FastAPI validates this automatically — sending `/search` with no `q` returns a 422 error.

---

## 5. The storage and embedding pipeline

**File:** `embeddings.py`

This file handles everything: text extraction, vector embedding, storage, search, and cleanup. ChromaDB is the only database — there is no SQLite.

This is also the most conceptually novel part of the app. Understanding it requires understanding what "embeddings" are.

### What an embedding is

An embedding is a way of representing text as a list of numbers (a **vector**) such that texts with similar meanings produce vectors that are close together in mathematical space.

For example:
- "How to train a dog" → `[0.21, -0.54, 0.87, ...]`
- "Puppy obedience tips" → `[0.19, -0.51, 0.83, ...]`  ← close to the above
- "Python async programming" → `[-0.63, 0.12, -0.44, ...]` ← far from the above

The model (`all-MiniLM-L6-v2`) was trained on massive amounts of text to learn this mapping. It learned that "dog" and "puppy" are semantically related, so their vectors end up close together.

The vector has 384 dimensions (numbers). You can think of it as a point in 384-dimensional space.

### Step 1: Text extraction

```python
def extract_text(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded)
    return text
```

**Trafilatura** is a library that fetches a web page and strips out everything except the main readable content — it removes navigation menus, ads, headers, footers, cookie banners. What remains is the article body or the core text of the page.

This is important because embedding the full raw HTML would pollute the vector with irrelevant content. You want the embedding to represent the *meaning* of the page, not its structure.

If extraction fails (the page is behind a login, blocks bots, or has no text content), `None` is returned and `api.py` calls `store_url_only` instead.

### Step 2a: Embedding extracted text

```python
def embed_and_store(url: str, text: str) -> None:
    model = _get_model()
    collection = _get_collection()
    embedding = model.encode(text).tolist()
    collection.upsert(
        ids=[url],
        embeddings=[embedding],
        documents=[text[:500]],
        metadatas=[{"url": url, "date": datetime.now(timezone.utc).isoformat(), "text_extracted": True}],
    )
```

`model.encode(text)` runs the text through the neural network and returns a numpy array of 384 numbers. `.tolist()` converts it to a plain Python list (required by ChromaDB).

`collection.upsert()` means "insert if new, update if already exists". The URL is used as the unique ID — so saving the same URL twice just updates the entry instead of creating a duplicate.

Each entry stores a `date` (ISO 8601 timestamp) and a `text_extracted` flag in metadata.

### Step 2b: URL-only fallback

```python
def store_url_only(url: str) -> None:
    model = _get_model()
    collection = _get_collection()
    embedding = model.encode(url).tolist()
    collection.upsert(
        ids=[url],
        embeddings=[embedding],
        documents=[url],
        metadatas=[{"url": url, "date": ..., "text_extracted": False}],
    )
```

When text extraction fails, the URL string itself is embedded. This means the bookmark is still stored in ChromaDB and will surface in searches that match the URL text (e.g. searching "github" will find `github.com` URLs). The `text_extracted: False` flag records that no page content was available.

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

### Step 3: Searching

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

## 6. The search UI — asking questions

**File:** `search.html`

This is a single self-contained HTML file served by FastAPI at `GET /`. When you open `http://localhost:8484` in a browser, FastAPI reads the file from disk and sends it back:

```python
@app.get("/")
def serve_search_ui():
    return FileResponse("search.html")
```

The page uses `fetch()` — the same browser HTTP client used in the extension — to call `/search?q=...` and render the results as a list of `<a>` links. The Enter key also triggers a search (via the `keydown` event listener).

No frameworks, no build tools — plain HTML and JavaScript. This keeps it simple and means there's nothing to install or compile to modify the UI.

---

## 7. How the pieces fit together: data flow diagrams

### Saving a URL

```
User clicks extension button
        │
        ▼
popup.js reads tab.url
        │
        ▼
fetch POST localhost:8484/save  { url: "https://example.com" }
        │
        ▼
api.py: save_url()
        │
        └──► extract_text(url)      ─────► trafilatura fetches page
                  (embeddings.py)            strips to main text
                       │
                       ├── success ──► embed_and_store(url, text)
                       │                    │
                       │                    ├──► model.encode(text)  ─► 384-dim vector
                       │                    └──► collection.upsert() ─► chroma_db/ (disk)
                       │                         metadata: {url, date, text_extracted: true}
                       │
                       └── failure ──► store_url_only(url)
                                            │
                                            ├──► model.encode(url)   ─► 384-dim vector
                                            └──► collection.upsert() ─► chroma_db/ (disk)
                                                 metadata: {url, date, text_extracted: false}
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
fetch GET localhost:8484/search?q=dog+nutrition
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

## 8. Why each technology was chosen

| Technology | What it does | Why this one |
|------------|-------------|-------------|
| **FastAPI** | HTTP server | Automatic request validation via Pydantic, auto-generated docs at `/docs`, minimal boilerplate |
| **uvicorn** | Runs the FastAPI app | The standard ASGI server for FastAPI; `--reload` restarts the server when you edit code |
| **trafilatura** | Extracts page text | Purpose-built for web content extraction; handles boilerplate removal better than raw HTML parsing |
| **sentence-transformers** | Converts text to vectors | `all-MiniLM-L6-v2` is ~80MB, runs on CPU in milliseconds, purpose-built for semantic similarity |
| **ChromaDB** | Single database: stores URLs, timestamps, and vectors | Local-first, zero config, handles cosine similarity search with fast indexing; URL-as-ID gives free deduplication |
| **Chrome Extension MV3** | Saves current tab | The only way to read the active tab URL and trigger local computation from within Chrome |
| **Pydantic** | Validates API inputs | Built into FastAPI; catches bad inputs before they reach your code |

### Why not use a bigger/smarter LLM model for search?

The BART and FLAN-T5 models explored earlier are **generative** models — they produce text. For search, you don't need generation; you need **similarity comparison**. `all-MiniLM-L6-v2` is a **sentence encoder** specifically trained for this: map two pieces of text to vectors and check how close they are. It's 100x faster and more appropriate for the task.

### Why only one database (ChromaDB)?

ChromaDB stores the URL (as the document ID), the semantic vector, a text snippet, and metadata including the timestamp. This covers everything the app needs. Using the URL as the ID gives free deduplication — upserting the same URL twice just updates the entry. A second database (SQLite) would only add complexity and create the risk of the two stores drifting out of sync.

---

## 9. Key concepts explained

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

---

## 10. Running the server automatically on login

This server is managed by **Supervisor**, configured in a separate `local-services` repository. Supervisor handles starting, stopping, and auto-restarting all local services. A single macOS **launchd** entry boots Supervisor itself at login.

**Why this split?** launchd is macOS's native boot system — it's the right tool for starting a process at login. Supervisor is a dedicated process manager — it's the right tool for managing multiple services day-to-day (logs, restarts, status). Combining them gives you the best of both: automatic boot + rich process control.

### Setup

See the `local-services` repo at `~/Documents/all_code/local-services/` for one-time setup instructions. The short version:

```bash
brew install supervisor uv
cd ~/Documents/all_code/local-services
./install.sh
```

### Day-to-day control

```bash
# Check status of all services
supervisorctl status

# Stop / start / restart this server
supervisorctl stop bookmark-processor
supervisorctl start bookmark-processor
supervisorctl restart bookmark-processor

# View logs
tail -f ~/Library/Logs/supervisor/bookmark-processor.log
```

### Adding a new service

Add a `.conf` file to `local-services/conf.d/` and run:

```bash
supervisorctl reread && supervisorctl update
```

No new launchd plists needed.

### Performance impact

At idle the server uses essentially no resources:

| State | CPU | RAM |
|---|---|---|
| Server running, nothing happening | ~0% | ~50 MB |
| After first save/search (ML model loaded) | ~0% | ~200–250 MB |
| During a save (embedding running) | brief spike, ~1–3 sec | same |

The ML model (`all-MiniLM-L6-v2`) loads into memory the first time you save or search — not at server startup. After that it stays in RAM so subsequent saves are fast. On a Mac with 8 GB+ RAM, 250 MB is a rounding error — comparable to one Chrome tab.

