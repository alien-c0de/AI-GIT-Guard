"""
tests/test_cache.py — Unit tests for github/cache.py
"""

import time
import tempfile
from pathlib import Path
import pytest
from github.cache import AlertCache


@pytest.fixture
def tmp_cache(tmp_path):
    db = tmp_path / "test_cache.db"
    cache = AlertCache(db_path=db, ttl_minutes=1)
    yield cache
    cache.close()


def test_set_and_get(tmp_cache):
    data = [{"id": 1, "state": "open"}]
    tmp_cache.set("key1", data)
    result = tmp_cache.get("key1")
    assert result == data


def test_get_missing_key_returns_none(tmp_cache):
    assert tmp_cache.get("nonexistent") is None


def test_cache_expiry(tmp_path):
    db = tmp_path / "ttl_test.db"
    cache = AlertCache(db_path=db, ttl_minutes=0)  # 0 min = instant expiry
    cache.set("key", {"value": 42})
    time.sleep(1)
    result = cache.get("key")
    assert result is None
    cache.close()


def test_invalidate(tmp_cache):
    tmp_cache.set("key2", {"data": True})
    tmp_cache.invalidate("key2")
    assert tmp_cache.get("key2") is None


def test_clear_all(tmp_cache):
    tmp_cache.set("a", [1, 2, 3])
    tmp_cache.set("b", [4, 5, 6])
    tmp_cache.clear_all()
    assert tmp_cache.get("a") is None
    assert tmp_cache.get("b") is None
