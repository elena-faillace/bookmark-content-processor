"""Tests for the Bookmarks API endpoints."""
import json
from pathlib import Path
from unittest.mock import patch, call

import pytest
from fastapi.testclient import TestClient

from app.api import app

MOCK_RESULTS = [{"url": "https://example.com/", "title": "Example"}]


@pytest.fixture(autouse=True)
def mock_infrastructure():
    """Patch all external I/O so tests run without ChromaDB, SQLite, or network."""
    with (
        patch("app.api.init_log_db"),
        patch("app.api.log_request"),
        patch("app.api.quality_check"),
    ):
        yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /save
# ---------------------------------------------------------------------------

class TestSave:
    def test_valid_url_text_extracted(self, client):
        with (
            patch("app.api.extract_text", return_value="page content"),
            patch("app.api.embed_and_store") as mock_embed,
        ):
            res = client.post("/save", json={"url": "https://example.com", "title": "Example"})

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "saved"
        assert body["embedded"] is True
        mock_embed.assert_called_once()

    def test_valid_url_extraction_fails(self, client):
        with (
            patch("app.api.extract_text", return_value=None),
            patch("app.api.store_url_only") as mock_store,
        ):
            res = client.post("/save", json={"url": "https://example.com"})

        assert res.status_code == 200
        assert res.json()["embedded"] is False
        mock_store.assert_called_once()

    def test_title_defaults_to_empty_string(self, client):
        with (
            patch("app.api.extract_text", return_value=None),
            patch("app.api.store_url_only") as mock_store,
        ):
            client.post("/save", json={"url": "https://example.com"})

        args, _ = mock_store.call_args
        assert args[1] == ""  # title is second positional arg

    def test_title_forwarded_to_embed(self, client):
        with (
            patch("app.api.extract_text", return_value="content"),
            patch("app.api.embed_and_store") as mock_embed,
        ):
            client.post("/save", json={"url": "https://example.com", "title": "My Title"})

        args, _ = mock_embed.call_args
        assert args[2] == "My Title"  # title is third positional arg

    def test_invalid_url_rejected(self, client):
        res = client.post("/save", json={"url": "not-a-url"})
        assert res.status_code == 422

    def test_missing_url_rejected(self, client):
        res = client.post("/save", json={})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_returns_results(self, client):
        with patch("app.api.embedding_search", return_value=MOCK_RESULTS):
            res = client.get("/search?q=example")

        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "example"
        assert data["results"] == MOCK_RESULTS

    def test_no_results(self, client):
        with patch("app.api.embedding_search", return_value=[]):
            res = client.get("/search?q=nothing")

        assert res.status_code == 200
        assert res.json()["results"] == []

    def test_empty_query_rejected(self, client):
        res = client.get("/search?q=")
        assert res.status_code == 422

    def test_missing_query_rejected(self, client):
        res = client.get("/search")
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# POST /import/bookmarks
# ---------------------------------------------------------------------------

MOCK_BOOKMARKS = [
    {"url": "https://example.com", "title": "Example"},
    {"url": "https://new-site.com", "title": "New Site"},
    {"url": "file:///local/file.html", "title": "Local File"},  # should be skipped
]


def _parse_sse(response) -> list[dict]:
    """Parse all SSE data lines from a streaming response into a list of dicts."""
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestImportPreview:
    def test_returns_counts(self, client):
        with (
            patch("app.api.read_chrome_bookmarks", return_value=MOCK_BOOKMARKS),
            patch("app.api.get_all_stored_ids", return_value=set()),
        ):
            res = client.get("/import/bookmarks/preview")

        assert res.status_code == 200
        data = res.json()
        assert data["to_import"] == 2       # 2 http URLs
        assert data["already_saved"] == 1   # file:// not counted as saved, just excluded
        assert data["total_found"] == 3

    def test_deduplication_in_preview(self, client):
        with (
            patch("app.api.read_chrome_bookmarks", return_value=MOCK_BOOKMARKS),
            patch("app.api.get_all_stored_ids", return_value={"https://example.com"}),
        ):
            res = client.get("/import/bookmarks/preview")

        assert res.status_code == 200
        assert res.json()["to_import"] == 1

    def test_file_not_found_returns_404(self, client):
        with patch("app.api.read_chrome_bookmarks", side_effect=FileNotFoundError):
            res = client.get("/import/bookmarks/preview")
        assert res.status_code == 404


class TestImport:
    def test_streams_sse_progress(self, client):
        with (
            patch("app.api.read_chrome_bookmarks", return_value=MOCK_BOOKMARKS),
            patch("app.api.get_all_stored_ids", return_value=set()),
            patch("app.api.extract_text", return_value="page content"),
            patch("app.api.embed_and_store"),
        ):
            res = client.post("/import/bookmarks")

        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        events = _parse_sse(res)
        assert events[-1]["done"] is True
        assert events[-1]["imported"] == 2

    def test_deduplication_skips_existing(self, client):
        with (
            patch("app.api.read_chrome_bookmarks", return_value=MOCK_BOOKMARKS),
            patch("app.api.get_all_stored_ids", return_value={"https://example.com"}),
            patch("app.api.extract_text", return_value=None),
            patch("app.api.store_url_only") as mock_store,
        ):
            res = client.post("/import/bookmarks")

        events = _parse_sse(res)
        assert events[-1]["imported"] == 1   # only new-site.com
        mock_store.assert_called_once()

    def test_skips_non_http_urls(self, client):
        bookmarks = [{"url": "file:///local.html", "title": "Local"}]
        with (
            patch("app.api.read_chrome_bookmarks", return_value=bookmarks),
            patch("app.api.get_all_stored_ids", return_value=set()),
        ):
            res = client.post("/import/bookmarks")

        events = _parse_sse(res)
        assert events[-1]["imported"] == 0

    def test_file_not_found_returns_404(self, client):
        with patch("app.api.read_chrome_bookmarks", side_effect=FileNotFoundError):
            res = client.post("/import/bookmarks")
        assert res.status_code == 404

    def test_extraction_failure_falls_back_to_url_only(self, client):
        with (
            patch("app.api.read_chrome_bookmarks", return_value=[MOCK_BOOKMARKS[0]]),
            patch("app.api.get_all_stored_ids", return_value=set()),
            patch("app.api.extract_text", return_value=None),
            patch("app.api.store_url_only") as mock_store,
        ):
            res = client.post("/import/bookmarks")

        mock_store.assert_called_once_with("https://example.com", "Example")


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestUI:
    def test_serves_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class TestRequestLogging:
    def test_each_request_is_logged(self, client):
        with patch("app.api.log_request") as mock_log:
            with patch("app.api.embedding_search", return_value=[]):
                client.get("/search?q=test")

        mock_log.assert_called_once()
        kwargs = mock_log.call_args
        args = kwargs[1] if kwargs[1] else dict(zip(
            ["method", "path", "query", "status_code", "duration_ms", "client_ip"],
            kwargs[0],
        ))
        assert args.get("method") == "GET" or mock_log.call_args[1].get("method") == "GET"

    def test_log_captures_status_code(self, client):
        with patch("app.api.log_request") as mock_log:
            client.get("/search")  # missing q → 422

        _, kwargs = mock_log.call_args
        assert kwargs["status_code"] == 422
