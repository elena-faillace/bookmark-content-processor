# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the API server
uvicorn api:app --reload --port 8000
```

## Architecture

A bookmark manager with semantic search. Python 3.12+, managed with UV. Exposes a local HTTP API that a Chrome extension talks to.

**Modules:**

- `api.py` — FastAPI server. Two endpoints: `POST /save` (saves URL + triggers embedding), `GET /search?q=...` (semantic search). Serves `search.html` at `GET /`. Calls `databset_init()` on startup and `quality_check()` on shutdown via lifespan.

- `database.py` — All SQLite operations (`bookmarks.db`). Functions: `databset_init()`, `add_link(url)`, `quality_check()`, `get_list_links()`. Uses a `@log_database_interactions` decorator. Quality check strips empty/null rows, removes duplicates, enforces `http` prefix.

- `embeddings.py` — Text extraction and vector search. `extract_text(url)` uses trafilatura. `embed_and_store(url, text)` encodes with `all-MiniLM-L6-v2` and upserts into ChromaDB (`./chroma_db/`). `search(query, n)` returns top-N URLs by cosine similarity. Model and ChromaDB client are lazy singletons.

- `search.html` — Static search UI served by FastAPI at `GET /`.

- `extension/` — Chrome Manifest V3 extension. Reads the active tab URL and POSTs to `localhost:8000/save`.

**Data flow:** Chrome extension → `POST /save` → `add_link()` → `bookmarks.db` + `embed_and_store()` → `chroma_db/`. Search: `GET /search?q=` → `embeddings.search()` → ChromaDB cosine query → ranked URLs.

## Stack

- `fastapi` + `uvicorn` — HTTP server
- `sqlite3` — bookmark storage (built-in)
- `sentence-transformers` — local text embeddings (`all-MiniLM-L6-v2`)
- `chromadb` — local vector database
- `trafilatura` — web content extraction
- `rich` — terminal formatting (used in `database.py` output)
