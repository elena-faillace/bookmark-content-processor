import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .bookmarks_import import read_chrome_bookmarks
from .deleted_db import add_deleted, get_all_deleted, init_deleted_db, restore_deleted
from .embeddings import delete_url, embed_and_store, extract_text, get_all_stored_ids, get_url_metadata, quality_check, search as embedding_search, store_url_only
from .request_log import init_log_db, log_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_log_db()
    init_deleted_db()
    yield
    quality_check()


app = FastAPI(title="Bookmarks API", lifespan=lifespan)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_request(
            method=request.method,
            path=request.url.path,
            query=str(request.url.query) or None,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
        )
        return response


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveRequest(BaseModel):
    url: HttpUrl
    title: str = ""


class RestoreRequest(BaseModel):
    url: HttpUrl
    title: str = ""


@app.get("/")
def serve_search_ui():
    return FileResponse("ui/search.html")


@app.post("/save")
def save_url(body: SaveRequest):
    url = str(body.url)
    title = body.title
    text = extract_text(url)
    if text:
        embed_and_store(url, text, title)
        return {"status": "saved", "url": url, "embedded": True}

    store_url_only(url, title)
    return {"status": "saved", "url": url, "embedded": False}


@app.get("/import/bookmarks/preview")
def preview_bookmarks():
    """Return counts of new vs already-saved bookmarks without importing anything."""
    try:
        bookmarks = read_chrome_bookmarks()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Chrome bookmarks file not found.")

    existing = get_all_stored_ids()
    deleted_urls = {d["url"] for d in get_all_deleted()}
    to_import = [
        bm for bm in bookmarks
        if bm["url"].startswith("http") and bm["url"] not in existing and bm["url"] not in deleted_urls
    ]
    return {
        "to_import": len(to_import),
        "already_saved": len(bookmarks) - len(to_import),
        "total_found": len(bookmarks),
    }


@app.post("/import/bookmarks")
def import_bookmarks():
    """Import new Chrome bookmarks, streaming SSE progress events."""
    try:
        bookmarks = read_chrome_bookmarks()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Chrome bookmarks file not found.")

    existing = get_all_stored_ids()
    deleted_urls = {d["url"] for d in get_all_deleted()}
    queue = [
        bm for bm in bookmarks
        if bm["url"].startswith("http") and bm["url"] not in existing and bm["url"] not in deleted_urls
    ]
    total = len(queue)

    def generate():
        for i, bm in enumerate(queue, start=1):
            text = extract_text(bm["url"])
            if text:
                embed_and_store(bm["url"], text, bm["title"])
            else:
                store_url_only(bm["url"], bm["title"])
            yield f"data: {json.dumps({'imported': i, 'total': total})}\n\n"
        yield f"data: {json.dumps({'done': True, 'imported': total, 'total': total})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.delete("/bookmark")
def delete_bookmark(url: str = Query(...)):
    meta = get_url_metadata(url)
    if not delete_url(url):
        raise HTTPException(status_code=404, detail="Bookmark not found.")
    add_deleted(url, title=meta.get("title", "") if meta else "")
    return {"status": "deleted", "url": url}


@app.get("/deleted")
def list_deleted():
    return {"deleted": get_all_deleted()}


@app.post("/deleted/restore")
def restore_bookmark(body: RestoreRequest):
    url = str(body.url)
    if not restore_deleted(url):
        raise HTTPException(status_code=404, detail="URL not in deleted list.")
    text = extract_text(url)
    if text:
        embed_and_store(url, text, body.title)
    else:
        store_url_only(url, body.title)
    return {"status": "restored", "url": url}


@app.get("/search")
def search_urls(q: str = Query(..., min_length=1)):
    results = embedding_search(q)
    if not results:
        return {"query": q, "results": []}
    return {"query": q, "results": results}
