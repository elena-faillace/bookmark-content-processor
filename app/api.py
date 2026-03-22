import logging
import time
from contextlib import asynccontextmanager
from io import StringIO

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .embeddings import embed_and_store, extract_text, quality_check, search as embedding_search, store_url_only
from .request_log import init_log_db, log_request

log_stream = StringIO()
logging.basicConfig(stream=log_stream, level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_log_db()
    logging.info("Server starting up.")
    yield
    quality_check()
    with open("logged_messages.txt", "w", encoding="utf-8") as f:
        f.write(log_stream.getvalue())


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


@app.get("/search")
def search_urls(q: str = Query(..., min_length=1)):
    results = embedding_search(q)
    if not results:
        return {"query": q, "results": []}
    return {"query": q, "results": results}
