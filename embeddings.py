import logging
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
            metadatas=[{"url": url}],
        )
        logging.info("Embedded and stored: %s", url)
    except Exception as e:
        logging.error("embed_and_store error for %s: %s", url, e)


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
