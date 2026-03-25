# bookmark-content-processor

Save web pages with one click and find them later using natural language queries. Built with a local Python backend and a vector database — no cloud required.

---

## How it works

1. **Save** a URL via the browser extension or the API directly
2. The app fetches the page text, embeds it with a local ML model (`all-MiniLM-L6-v2`)
3. **Search** using plain English — results are ranked by semantic similarity, not keywords

---

## Setup

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv), [local-services](https://github.com/elena-faillace/local-services)

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd bookmark-content-processor
uv sync
```

### 2. Start the server via local-services

This app is managed by the [local-services](https://github.com/elena-faillace/local-services) repo, which runs it as a background service via Supervisor and launchd (auto-starts at login).

If you haven't set up `local-services` yet, follow its README — it's a one-time `./install.sh` that bootstraps everything. It will ask for the path to this repo during setup.

Once set up:

```bash
supervisorctl status                     # check all services
supervisorctl restart bookmark-processor # restart after code changes
```

- Search UI: <http://localhost:8484>
- API docs: <http://localhost:8484/docs>

> **Running without local-services:** `uvicorn app.api:app --port 8484`

---

## Browser extensions

### Chrome

1. Open `chrome://extensions`
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked** → select the `extension-chrome/` folder
4. Click the extension icon on any page → **Save this page**

### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on** → select any file inside `extension-firefox/`
3. Click the extension icon on any page → **Save this page**

> The server must be running for the extension to work.

---

## API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/save` | Save a URL. Body: `{"url": "https://..."}` |
| `GET` | `/search?q=...` | Semantic search. Returns ranked list of URLs. |
| `GET` | `/` | Search UI (served as HTML) |
| `GET` | `/docs` | Interactive API docs (Swagger) |

```bash
# Save a URL
curl -X POST http://localhost:8484/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Search
curl "http://localhost:8484/search?q=machine+learning"
```

---

## Project Structure

```text
bookmark-content-processor/
├── app/
│   ├── api.py           # FastAPI server (HTTP endpoints)
│   ├── embeddings.py    # Text extraction, embedding, storage, vector search
│   └── request_log.py   # SQLite request logging (logs.db)
├── ui/
│   └── search.html      # Search UI served by the API
├── extension-chrome/    # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── popup.html
│   └── popup.js
├── extension-firefox/   # Firefox extension (Manifest V2)
│   ├── manifest.json
│   ├── popup.html
│   └── popup.js
├── docs/
│   └── GUIDE.md         # Full technical guide
├── tests/
│   └── test_api.py
└── chroma_db/           # Vector store (auto-created)
```

---

## Stack

| Package | Purpose |
| ------- | ------- |
| `fastapi` + `uvicorn` | HTTP server |
| `sentence-transformers` | Local text embeddings (`all-MiniLM-L6-v2`, ~80MB) |
| `chromadb` | Local vector database for bookmarks |
| `sqlite3` | Request log storage (`logs.db`, built-in) |
| `trafilatura` | Web page content extraction |
| `pytest` + `httpx` | Testing (dev) |
