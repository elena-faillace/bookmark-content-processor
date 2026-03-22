import logging
from contextlib import asynccontextmanager
from io import StringIO

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from .embeddings import embed_and_store, extract_text, quality_check, search as embedding_search, store_url_only

log_stream = StringIO()
logging.basicConfig(stream=log_stream, level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Server starting up.")
    yield
    quality_check()
    with open("logged_messages.txt", "w", encoding="utf-8") as f:
        f.write(log_stream.getvalue())


app = FastAPI(title="Bookmarks API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def serve_search_ui():
    return FileResponse("ui/search.html")


@app.post("/save")
def save_url(body: SaveRequest):
    url = str(body.url)
    text = extract_text(url)
    if text:
        embed_and_store(url, text)
        return {"status": "saved", "url": url, "embedded": True}

    store_url_only(url)
    return {"status": "saved", "url": url, "embedded": False}


@app.get("/search")
def search_urls(q: str = Query(..., min_length=1)):
    results = embedding_search(q)
    if not results:
        return {"query": q, "results": []}
    return {"query": q, "results": results}
