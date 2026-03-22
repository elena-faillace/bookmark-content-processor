import logging
import sqlite3
from datetime import datetime, timezone

_DB_PATH = "logs.db"


def init_log_db() -> None:
    """Create the api_logs table if it doesn't exist."""
    conn = sqlite3.connect(_DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                method      TEXT    NOT NULL,
                path        TEXT    NOT NULL,
                query       TEXT,
                status_code INTEGER,
                duration_ms REAL,
                client_ip   TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def log_request(
    method: str,
    path: str,
    query: str | None,
    status_code: int,
    duration_ms: float,
    client_ip: str | None,
) -> None:
    """Insert one row into api_logs for a completed request."""
    try:
        conn = sqlite3.connect(_DB_PATH)
        try:
            conn.execute(
                """
                INSERT INTO api_logs (timestamp, method, path, query, status_code, duration_ms, client_ip)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    method,
                    path,
                    query or None,
                    status_code,
                    duration_ms,
                    client_ip,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logging.error("request_log: failed to write log entry: %s", e)
