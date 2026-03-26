import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path("data/deleted.db")


def init_deleted_db() -> None:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deleted_bookmarks (
                url       TEXT PRIMARY KEY,
                title     TEXT NOT NULL DEFAULT '',
                deleted_at TEXT NOT NULL
            )
        """)


def add_deleted(url: str, title: str = "") -> None:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deleted_bookmarks (url, title, deleted_at) VALUES (?, ?, ?)",
            (url, title, datetime.now(timezone.utc).isoformat()),
        )


def get_all_deleted() -> list[dict]:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT url, title, deleted_at FROM deleted_bookmarks ORDER BY deleted_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def restore_deleted(url: str) -> bool:
    """Remove a URL from the deleted list. Returns True if it was present."""
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.execute("DELETE FROM deleted_bookmarks WHERE url = ?", (url,))
    return cur.rowcount > 0
