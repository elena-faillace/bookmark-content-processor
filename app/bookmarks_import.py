import json
from pathlib import Path

_CHROME_DIR = Path.home() / "Library/Application Support/Google/Chrome"


def _extract(node: dict) -> list[dict]:
    """Recursively extract {url, title} from a Chrome bookmark tree node."""
    if node.get("type") == "url":
        return [{"url": node["url"], "title": node.get("name", "")}]
    return [bm for child in node.get("children", []) for bm in _extract(child)]


def _read_file(path: Path) -> list[dict]:
    """Read one Chrome Bookmarks file and return all {url, title} entries."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [bm for root in data.get("roots", {}).values() if isinstance(root, dict) for bm in _extract(root)]


def read_chrome_bookmarks(chrome_dir: Path = _CHROME_DIR) -> list[dict]:
    """Return all bookmarks from every Chrome profile, deduplicated by URL."""
    if not chrome_dir.exists():
        raise FileNotFoundError(f"Chrome directory not found: {chrome_dir}")

    seen: set[str] = set()
    bookmarks: list[dict] = []

    for bookmark_file in sorted(chrome_dir.glob("*/Bookmarks")):
        for bm in _read_file(bookmark_file):
            if bm["url"] not in seen:
                seen.add(bm["url"])
                bookmarks.append(bm)

    return bookmarks
