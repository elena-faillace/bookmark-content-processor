"""Unit tests for the Chrome bookmarks parser."""
import json
import pytest
from pathlib import Path

from app.bookmarks_import import read_chrome_bookmarks, _extract


def _make_bookmark_file(tmp_path: Path, profile: str, bookmarks: list[dict]) -> None:
    """Write a minimal Chrome Bookmarks JSON file into a profile folder."""
    profile_dir = tmp_path / profile
    profile_dir.mkdir()
    data = {
        "roots": {
            "bookmark_bar": {
                "type": "folder",
                "name": "Bookmarks Bar",
                "children": bookmarks,
            },
            "other": {"type": "folder", "name": "Other", "children": []},
        }
    }
    (profile_dir / "Bookmarks").write_text(json.dumps(data), encoding="utf-8")


def _url_node(url: str, name: str) -> dict:
    return {"type": "url", "url": url, "name": name}


def _folder_node(name: str, children: list) -> dict:
    return {"type": "folder", "name": name, "children": children}


class TestExtract:
    def test_url_node_returns_entry(self):
        node = _url_node("https://example.com", "Example")
        assert _extract(node) == [{"url": "https://example.com", "title": "Example"}]

    def test_folder_node_recurses(self):
        node = _folder_node("Folder", [
            _url_node("https://a.com", "A"),
            _url_node("https://b.com", "B"),
        ])
        result = _extract(node)
        assert len(result) == 2
        assert result[0]["url"] == "https://a.com"

    def test_nested_folders(self):
        node = _folder_node("Outer", [
            _folder_node("Inner", [
                _url_node("https://deep.com", "Deep"),
            ])
        ])
        result = _extract(node)
        assert result == [{"url": "https://deep.com", "title": "Deep"}]

    def test_unknown_type_ignored(self):
        node = {"type": "other", "name": "Weird"}
        assert _extract(node) == []


class TestReadChromeBookmarks:
    def test_reads_single_profile(self, tmp_path):
        _make_bookmark_file(tmp_path, "Default", [
            _url_node("https://example.com", "Example"),
        ])
        result = read_chrome_bookmarks(tmp_path)
        assert result == [{"url": "https://example.com", "title": "Example"}]

    def test_merges_multiple_profiles(self, tmp_path):
        _make_bookmark_file(tmp_path, "Default", [_url_node("https://a.com", "A")])
        _make_bookmark_file(tmp_path, "Profile 1", [_url_node("https://b.com", "B")])
        result = read_chrome_bookmarks(tmp_path)
        urls = [bm["url"] for bm in result]
        assert "https://a.com" in urls
        assert "https://b.com" in urls
        assert len(result) == 2

    def test_deduplicates_across_profiles(self, tmp_path):
        _make_bookmark_file(tmp_path, "Default", [_url_node("https://same.com", "Same")])
        _make_bookmark_file(tmp_path, "Profile 1", [_url_node("https://same.com", "Same again")])
        result = read_chrome_bookmarks(tmp_path)
        assert len(result) == 1
        assert result[0]["url"] == "https://same.com"

    def test_missing_chrome_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_chrome_bookmarks(tmp_path / "nonexistent")
