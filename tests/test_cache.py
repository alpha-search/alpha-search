"""Detailed tests for the real CacheManager (DuckDB-backed)."""

import os
import tempfile

import pandas as pd

from alpha_search.data.cache import CacheManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _temp_cache() -> CacheManager:
    """Return a CacheManager backed by a temporary file.

    We use a file rather than ``:memory:`` because the product code's
    ``_connection`` property reconnects on every access (``self._conn.close``
    is always truthy). With ``:memory:`` each reconnect creates a new empty
    database, so we need a persistent file for multi-operation tests.

    The temp file is *deleted* before returning so that DuckDB can create a
    valid database file at that path.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return CacheManager(tmp.name)


def _cleanup(cache: CacheManager) -> None:
    """Close the cache and remove its backing file."""
    db_path = cache.db_path
    cache.close()
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCacheSetGet:
    """Basic store / retrieve semantics."""

    def test_cache_set_get(self) -> None:
        """A stored DataFrame can be retrieved unchanged."""
        cache = _temp_cache()
        fixture = pd.DataFrame({"ticker": ["AAPL"], "close": [182.5]})

        cache.set("aapl_quote", fixture, ttl=3600)
        loaded = cache.get("aapl_quote")

        pd.testing.assert_frame_equal(loaded, fixture)
        _cleanup(cache)

    def test_cache_get_missing_returns_none(self) -> None:
        """Fetching an unknown key returns None (not KeyError)."""
        cache = _temp_cache()

        result = cache.get("nonexistent_key")
        assert result is None

        _cleanup(cache)


class TestCacheHas:
    """Key-existence checks."""

    def test_cache_has(self) -> None:
        """has() returns True for present, unexpired keys."""
        cache = _temp_cache()
        df = pd.DataFrame({"close": [150.0, 151.0, 152.0]})
        cache.set("present", df)

        assert cache.has("present") is True
        assert cache.has("absent") is False
        _cleanup(cache)


class TestCacheClear:
    """Bulk deletion."""

    def test_cache_clear(self) -> None:
        """clear() wipes every entry."""
        cache = _temp_cache()
        df = pd.DataFrame({"k": [1]})
        cache.set("k1", df)
        cache.set("k2", df)

        cache.clear()

        assert cache.has("k1") is False
        assert cache.has("k2") is False
        _cleanup(cache)


class TestCachePersistence:
    """Cache survives process restart when backed by a file."""

    def test_cache_persistence(self) -> None:
        """Data written to a file-backed cache is readable in a new connection."""
        tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        db_path = tmp.name

        try:
            # Writer session
            writer = CacheManager(db_path)
            df = pd.DataFrame({"close": [150.0, 151.0, 152.0]})
            writer.set("prices/aapl", df)
            writer.close()

            # Reader session (new process simulation)
            reader = CacheManager(db_path)
            loaded = reader.get("prices/aapl")

            pd.testing.assert_frame_equal(loaded, df)
            reader.close()
        finally:
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass


class TestCacheClose:
    """Connection lifecycle."""

    def test_cache_close(self) -> None:
        """close() releases the DuckDB connection; later access reconnects lazily."""
        tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        db_path = tmp.name

        try:
            cache = CacheManager(db_path)
            df = pd.DataFrame({"x": [1]})
            cache.set("key", df)
            assert cache.has("key") is True

            cache.close()
            # After close, has() should still work because the product code
            # lazily reconnects on every _connection access.
            assert cache.has("key") is True
            cache.close()
        finally:
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass
