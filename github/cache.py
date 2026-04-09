"""
github/cache.py — SQLite-backed cache for GitHub API responses.
Prevents repeated API calls within the configured TTL window.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / ".alert_cache.db"


class AlertCache:
    """
    Simple key-value store backed by SQLite.
    Keys are cache-key strings; values are JSON-serialised API responses.
    """

    def __init__(self, db_path: Path = DB_PATH, ttl_minutes: Optional[int] = None):
        self._db_path = db_path
        self._ttl = (ttl_minutes if ttl_minutes is not None else settings.CACHE_TTL_MINUTES) * 60
        self._conn = self._safe_connect(db_path)
        self._init_schema()
        # Restrict file permissions on the cache (owner read/write only)
        try:
            os.chmod(str(db_path), 0o600)
        except OSError:
            pass  # Windows may not support chmod fully
        logger.debug("AlertCache initialised — db: %s, ttl: %ds", db_path, self._ttl)

    def _safe_connect(self, db_path: Path) -> sqlite3.Connection:
        """Connect to SQLite, recovering from a corrupt database if needed."""
        try:
            conn = sqlite3.connect(str(db_path))
            # Quick integrity check — only fails on genuinely corrupt files
            conn.execute("PRAGMA integrity_check")
            return conn
        except sqlite3.DatabaseError:
            logger.warning("Cache database corrupted — recreating: %s", db_path)
            try:
                conn.close()
            except Exception:
                pass
            db_path.unlink(missing_ok=True)
            return sqlite3.connect(str(db_path))

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key      TEXT PRIMARY KEY,
                value    TEXT NOT NULL,
                stored   REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[list | dict]:
        """Return cached value if present and not expired; else None."""
        row = self._conn.execute(
            "SELECT value, stored FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value_json, stored_at = row
        if time.time() - stored_at > self._ttl:
            logger.debug("Cache EXPIRED for key: %s", key)
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        logger.debug("Cache HIT for key: %s", key)
        return json.loads(value_json)

    def set(self, key: str, value: list | dict) -> None:
        """Store a value under the given key with the current timestamp."""
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()
        logger.debug("Cache SET for key: %s", key)

    def invalidate(self, key: str) -> None:
        self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        self._conn.commit()

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM cache")
        self._conn.commit()
        logger.info("Alert cache cleared.")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
