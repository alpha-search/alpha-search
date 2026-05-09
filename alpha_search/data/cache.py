"""DuckDB-based cache manager for Alpha Search."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from alpha_search.core.config import get_config

logger = logging.getLogger(__name__)


class CacheManager:
    """Persistent cache backed by DuckDB.

    Stores pandas DataFrames keyed by a string *key*. Each entry carries
    a Unix timestamp so stale records can be purged.

    Example::

        cache = CacheManager()
        cache.set("AAPL_2020_2021", df, ttl=86400)
        df = cache.get("AAPL_2020_2021")
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        config = get_config()
        if db_path is None:
            db_path = str(config.cache_path / "alpha_search_cache.duckdb")
        self.db_path = db_path
        self._conn: Optional[object] = None
        self._ensure_table()

    @property
    def _connection(self):
        import duckdb

        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def _ensure_table(self) -> None:
        """Create the cache table if it does not exist."""
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                cache_key VARCHAR PRIMARY KEY,
                created_at BIGINT,
                expires_at BIGINT,
                data BLOB
            )
            """
        )

    def _key_hash(self, key: str) -> str:
        """Hash a potentially long key to a fixed-length string."""
        return hashlib.sha256(key.encode()).hexdigest()

    def set(self, key: str, data: pd.DataFrame, ttl: int = 86400) -> None:
        """Store *data* under *key* with a time-to-live in seconds.

        Args:
            key: Cache lookup key.
            data: DataFrame to persist.
            ttl: Seconds until the entry expires (default 24 h).
        """
        try:
            now = int(time.time())
            expires = now + ttl
            # Serialize DataFrame to Parquet bytes
            buf = data.to_parquet()
            hk = self._key_hash(key)
            self._connection.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)",
                [hk, now, expires, buf],
            )
            logger.debug("Cache SET key=%s ttl=%ds", key, ttl)
        except Exception as exc:
            logger.warning("Cache set failed for key=%s: %s", key, exc)

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve a DataFrame by *key* if present and not expired.

        Returns:
            The cached DataFrame, or ``None`` if missing / expired.
        """
        try:
            hk = self._key_hash(key)
            result = self._connection.execute(
                "SELECT data, expires_at FROM cache WHERE cache_key = ?", [hk]
            ).fetchone()
            if result is None:
                return None
            data_blob, expires_at = result
            if int(time.time()) > expires_at:
                logger.debug("Cache EXPIRED key=%s", key)
                self.delete(key)
                return None
            df = pd.read_parquet(pd.io.common.BytesIO(data_blob))
            logger.debug("Cache HIT key=%s rows=%d", key, len(df))
            return df
        except Exception as exc:
            logger.warning("Cache get failed for key=%s: %s", key, exc)
            return None

    def has(self, key: str) -> bool:
        """Return ``True`` if *key* exists and is not expired."""
        try:
            hk = self._key_hash(key)
            row = self._connection.execute(
                "SELECT expires_at FROM cache WHERE cache_key = ?", [hk]
            ).fetchone()
            if row is None:
                return False
            if int(time.time()) > row[0]:
                self.delete(key)
                return False
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        """Remove a single cache entry."""
        try:
            hk = self._key_hash(key)
            self._connection.execute(
                "DELETE FROM cache WHERE cache_key = ?", [hk]
            )
        except Exception as exc:
            logger.warning("Cache delete failed for key=%s: %s", key, exc)

    def clear(self) -> None:
        """Drop the entire cache table."""
        try:
            self._connection.execute("DROP TABLE IF EXISTS cache")
            self._ensure_table()
            logger.info("Cache cleared.")
        except Exception as exc:
            logger.warning("Cache clear failed: %s", exc)

    def clear_expired(self) -> int:
        """Remove all expired entries and return the count removed."""
        try:
            now = int(time.time())
            result = self._connection.execute(
                "DELETE FROM cache WHERE expires_at < ? RETURNING cache_key", [now]
            ).fetchall()
            n = len(result)
            logger.info("Cleared %d expired cache entries.", n)
            return n
        except Exception as exc:
            logger.warning("clear_expired failed: %s", exc)
            return 0

    def __repr__(self) -> str:
        return f"<CacheManager db={self.db_path!r}>"

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Attempt graceful shutdown on garbage collection."""
        try:
            self.close()
        except Exception:
            pass
