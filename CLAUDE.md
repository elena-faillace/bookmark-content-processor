# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the API server
uvicorn app.api:app --reload --port 8000
```

## Architecture

A bookmark manager with semantic search. Python 3.12+, managed with UV. Exposes a local HTTP API that a Chrome extension talks to.

**Modules:**

- `app/api.py` — FastAPI server. Two endpoints: `POST /save` (saves URL + triggers embedding), `GET /search?q=...` (semantic search). Serves `ui/search.html` at `GET /`. Calls `quality_check()` on shutdown via lifespan.

- `app/embeddings.py` — All storage and search logic. `extract_text(url)` uses trafilatura. `embed_and_store(url, text)` encodes with `all-MiniLM-L6-v2` and upserts into ChromaDB (`./chroma_db/`) with `date` and `text_extracted` metadata. `store_url_only(url)` embeds the URL string itself as a fallback when text extraction fails. `quality_check()` removes non-http entries from ChromaDB on shutdown. `search(query, n)` returns top-N URLs by cosine similarity. Model and ChromaDB client are lazy singletons.

- `ui/search.html` — Static search UI served by FastAPI at `GET /`.

- `extension/` — Chrome Manifest V3 extension. Reads the active tab URL and POSTs to `localhost:8000/save`.

- `docs/GUIDE.md` — Full technical guide explaining the app's flow and every technology choice.

**Data flow:** Chrome extension → `POST /save` → `extract_text()` → success: `embed_and_store()` → `chroma_db/`; failure: `store_url_only()` → `chroma_db/`. Search: `GET /search?q=` → `embeddings.search()` → ChromaDB cosine query → ranked URLs.

## Stack

- `fastapi` + `uvicorn` — HTTP server
- `sentence-transformers` — local text embeddings (`all-MiniLM-L6-v2`)
- `chromadb` — local vector database (sole storage layer)
- `trafilatura` — web content extraction
