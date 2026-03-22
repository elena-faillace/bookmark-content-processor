# bookmark-content-processor

Save web pages with one click and find them later using natural language queries. Built with a local Python backend and a vector database — no cloud required.

---

## How it works

1. **Save** a URL via the Chrome extension or the API directly
2. The app fetches the page text, embeds it with a local ML model (`all-MiniLM-L6-v2`)
3. **Search** using plain English — results are ranked by semantic similarity, not just keywords

---

## Setup

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv), Chrome

```bash
# Clone and install dependencies
git clone <repo-url>
cd bookmark-content-processor
uv sync
uv sync --group dev  # for running tests
```

---

## Running the app

### Local HTTP API (recommended)

```bash
uvicorn app.api:app --reload --port 8484
```

- API docs: http://localhost:8484/docs
- Search UI: http://localhost:8484

---

## Chrome Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked** → select the `extension/` folder
4. Click the extension icon on any page → **Save this page**

> The local server must be running (`uvicorn app.api:app --port 8484`) for the extension to work.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/save` | Save a URL. Body: `{"url": "https://..."}` |
| `GET` | `/search?q=...` | Semantic search. Returns ranked list of URLs. |
| `GET` | `/` | Search UI (served as HTML) |
| `GET` | `/docs` | Interactive API docs (Swagger) |

**Save a URL via curl:**
```bash
curl -X POST http://localhost:8484/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Search via curl:**
```bash
curl "http://localhost:8484/search?q=machine+learning"
```

---

## Project Structure

```
bookmark-content-processor/
├── app/             # Python backend
│   ├── api.py       # FastAPI server (HTTP endpoints)
│   └── embeddings.py# Text extraction, embedding, storage, and vector search
├── ui/              # Frontend
│   └── search.html  # Search UI served by the API
├── extension/       # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── popup.html
│   └── popup.js
├── docs/            # Documentation
│   └── GUIDE.md     # Full technical guide
├── tests/           # pytest test suite
│   └── test_api.py
└── chroma_db/       # Vector store (auto-created)
```

---

## Stack

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | HTTP server |
| `sentence-transformers` | Local text embeddings (`all-MiniLM-L6-v2`, ~80MB) |
| `chromadb` | Local vector database for bookmarks |
| `sqlite3` | Request log storage (`logs.db`, built-in) |
| `trafilatura` | Web page content extraction |
| `pytest` + `httpx` | Testing (dev) |
