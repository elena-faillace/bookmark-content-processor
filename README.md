# LLM Links App — Bookmark Manager with Semantic Search

Save web pages with one click and find them later using natural language queries. Built with a local Python backend, SQLite, and a vector database — no cloud required.

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
cd LLM-links-app
uv sync
```

---

## Running the app

### Local HTTP API (recommended)

```bash
uvicorn app.api:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Search UI: http://localhost:8000

### CLI (legacy)

```bash
python main.py
```

---

## Chrome Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked** → select the `extension/` folder
4. Click the extension icon on any page → **Save this page**

> The local server must be running (`uvicorn api:app --port 8000`) for the extension to work.

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
curl -X POST http://localhost:8000/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Search via curl:**
```bash
curl "http://localhost:8000/search?q=machine+learning"
```

---

## Project Structure

```
LLM-links-app/
├── app/             # Python backend
│   ├── api.py       # FastAPI server (HTTP endpoints)
│   ├── database.py  # SQLite operations
│   └── embeddings.py# Text extraction, embedding, and vector search
├── ui/              # Frontend
│   └── search.html  # Search UI served by the API
├── extension/       # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── popup.html
│   └── popup.js
├── docs/            # Documentation
│   └── GUIDE.md     # Full technical guide
├── bookmarks.db     # SQLite database (auto-created)
└── chroma_db/       # Vector store (auto-created)
```

---

## Stack

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | HTTP server |
| `sqlite3` | Bookmark storage (built-in) |
| `sentence-transformers` | Local text embeddings (`all-MiniLM-L6-v2`, ~80MB) |
| `chromadb` | Local vector database for semantic search |
| `trafilatura` | Web page content extraction |
| `typer` + `rich` | CLI interface |
