import logging
from datetime import datetime, timezone
import trafilatura
import chromadb
from sentence_transformers import SentenceTransformer

_model = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path="./chroma_db")
        _collection = client.get_or_create_collection(
            name="bookmarks",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def extract_text(url: str) -> str | None:
    """Fetch and extract main text content from a URL using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            logging.warning("trafilatura: could not fetch %s", url)
            return None
        text = trafilatura.extract(downloaded)
        if not text:
            logging.warning("trafilatura: no text extracted from %s", url)
            return None
        return text
    except Exception as e:
        logging.error("extract_text error for %s: %s", url, e)
        return None


def embed_and_store(url: str, text: str) -> None:
    """Embed text and store the vector in ChromaDB keyed by URL."""
    try:
        model = _get_model()
        collection = _get_collection()
        embedding = model.encode(text).tolist()
        collection.upsert(
            ids=[url],
            embeddings=[embedding],
            documents=[text[:500]],  # store a snippet for reference
            metadatas=[{"url": url, "date": datetime.now(timezone.utc).isoformat(), "text_extracted": True}],
        )
        logging.info("Embedded and stored: %s", url)
    except Exception as e:
        logging.error("embed_and_store error for %s: %s", url, e)


def store_url_only(url: str) -> None:
    """Store a URL with no extracted text. The URL string itself is embedded as fallback."""
    try:
        model = _get_model()
        collection = _get_collection()
        embedding = model.encode(url).tolist()
        collection.upsert(
            ids=[url],
            embeddings=[embedding],
            documents=[url],
            metadatas=[{"url": url, "date": datetime.now(timezone.utc).isoformat(), "text_extracted": False}],
        )
        logging.info("Stored URL-only (no text extraction): %s", url)
    except Exception as e:
        logging.error("store_url_only error for %s: %s", url, e)


def quality_check() -> None:
    """Remove ChromaDB entries with empty or non-http URLs."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return
        results = collection.get(include=["metadatas"])
        ids_to_delete = [
            doc_id
            for doc_id, meta in zip(results["ids"], results["metadatas"])
            if not meta.get("url", "").startswith("http")
        ]
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            logging.warning("quality_check: removed %d entries", len(ids_to_delete))
    except Exception as e:
        logging.error("quality_check error: %s", e)


def search(query: str, n: int = 10) -> list[str]:
    """Return top-N URLs whose content is most similar to the query."""
    try:
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
    except Exception as e:
        logging.error("search error: %s", e)
        return []
