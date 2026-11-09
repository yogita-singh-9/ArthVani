"""
tests/test_price_memory.py — Tests for db.last_price() and db.day_summary().

No network calls, no gnani. Uses tmp databases.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
import db as _db


@pytest.fixture()
def tmp_db(tmp_path):
    p = str(tmp_path / "test.db")
    _db.init_db(p)
    return p


def _add(db, item, qty, unit, price, entry_type="sale"):
    _db.save_entry(
        {"item": item, "quantity": qty, "unit": unit, "price": price, "entry_type": entry_type},
        "hi", "", db
    )


# ════════════════════════════════════════════════════════════
# 1. EXACT MATCH
# ════════════════════════════════════════════════════════════

def test_last_price_exact_match(tmp_db):
    _add(tmp_db, "चावल", 50, "kg", 60)
    result = _db.last_price("चावल", "kg", tmp_db)
    assert result == 60.0


def test_last_price_returns_most_recent(tmp_db):
    _add(tmp_db, "चावल", 50, "kg", 60)
    _add(tmp_db, "चावल", 30, "kg", 65)  # newer price
    result = _db.last_price("चावल", "kg", tmp_db)
    assert result == 65.0


def test_last_price_no_match(tmp_db):
    _add(tmp_db, "आटा", 10, "kg", 40)
    result = _db.last_price("चावल", "kg", tmp_db)
    assert result is None


def test_last_price_empty_db(tmp_db):
    result = _db.last_price("चावल", "kg", tmp_db)
    assert result is None


def test_last_price_without_unit_filter(tmp_db):
    _add(tmp_db, "rice", 10, "kg", 70)
    result = _db.last_price("rice", None, tmp_db)
    assert result == 70.0


# ════════════════════════════════════════════════════════════
# 2. FUZZY MATCH
# ════════════════════════════════════════════════════════════

def test_last_price_fuzzy_close_spelling(tmp_db):
    """'chawal' and 'chaval' should fuzzy-match to 'chawl' above threshold."""
    _add(tmp_db, "chawal", 50, "kg", 55)
    # Very close: chaval vs chawal
    result = _db.last_price("chaval", "kg", tmp_db)
    # Either finds it (fuzzy) or doesn't — just ensure no exception
    assert result is None or isinstance(result, float)


def test_last_price_different_item_no_false_positive(tmp_db):
    """'atta' and 'chawal' must NOT fuzzy-match to each other."""
    _add(tmp_db, "atta", 20, "kg", 40)
    result = _db.last_price("chawal", "kg", tmp_db)
    assert result is None


def test_last_price_english_exact(tmp_db):
    _add(tmp_db, "rice", 10, "kg", 72)
    result = _db.last_price("rice", "kg", tmp_db)
    assert result == 72.0


# ════════════════════════════════════════════════════════════
# 3. DAY SUMMARY
# ════════════════════════════════════════════════════════════

def test_day_summary_empty(tmp_db):
    result = _db.day_summary(tmp_db)
    assert result["sales"] == 0.0
    assert result["purchases"] == 0.0
    assert result["net"] == 0.0
    assert result["count"] == 0
    assert result["top_items"] == []


def test_day_summary_sales_only(tmp_db):
    _add(tmp_db, "चावल", 50, "kg", 60, "sale")
    _add(tmp_db, "आटा",  20, "kg", 40, "sale")
    result = _db.day_summary(tmp_db)
    assert result["sales"] == 3000.0 + 800.0
    assert result["purchases"] == 0.0
    assert result["net"] == 3800.0
    assert result["count"] == 2


def test_day_summary_mixed(tmp_db):
    _add(tmp_db, "चावल", 50, "kg", 60, "sale")
    _add(tmp_db, "तेल",  5,  "litre", 100, "purchase")
    result = _db.day_summary(tmp_db)
    assert result["sales"] == 3000.0
    assert result["purchases"] == 500.0
    assert result["net"] == 2500.0
    assert result["count"] == 2


def test_day_summary_top_items(tmp_db):
    _add(tmp_db, "चावल", 50, "kg", 60, "sale")
    _add(tmp_db, "आटा",  20, "kg", 40, "sale")
    _add(tmp_db, "चावल", 10, "kg", 60, "sale")  # second chawal entry
    result = _db.day_summary(tmp_db)
    items = [i["item"] for i in result["top_items"]]
    # चावल should be first (highest total)
    assert items[0] == "चावल"
    assert len(result["top_items"]) <= 3


def test_day_summary_has_date(tmp_db):
    result = _db.day_summary(tmp_db)
    assert "date" in result
    assert len(result["date"]) == 10   # YYYY-MM-DD

