"""
tests/test_db.py — Pytest tests for db.py.

All tests use a tmp_path fixture so they never touch arthvani.db.
No API calls, no network, no .env access.

Run with:
    pytest tests/test_db.py -v
"""

import io
import math
import pathlib
import sys
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from db import (
    init_db,
    save_entry,
    list_entries,
    today_total,
    update_entry,
    delete_entry,
    delete_last_entry,
    entries_dataframe,
    export_xlsx,
    export_csv,
    seed_demo_entries,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Return path to a fresh temporary SQLite database."""
    p = str(tmp_path / "test.db")
    init_db(p)
    return p


@pytest.fixture
def db_with_entries(db):
    """DB pre-populated with 3 entries for query tests."""
    save_entry({"item": "चावल",  "quantity": 50.0, "unit": "kg",    "price": 60.0,  "entry_type": "sale"},
               "hi", "50 किलो चावल 60 रुपये किलो", db)
    save_entry({"item": "आलू",   "quantity": 5.0,  "unit": "kg",    "price": 20.0,  "entry_type": "sale"},
               "hi", "5 kilo aloo 20 rupaye", db)
    save_entry({"item": "rice",  "quantity": 10.0, "unit": "kg",    "price": 55.0,  "entry_type": "purchase"},
               "en", "ten kilo rice 55 rupees", db)
    return db


# ── 1. Init ───────────────────────────────────────────────────────────────────

def test_init_db_creates_file(tmp_path):
    p = str(tmp_path / "new.db")
    init_db(p)
    assert pathlib.Path(p).exists()


def test_init_db_idempotent(tmp_path):
    """Calling init_db twice must not raise or corrupt the DB."""
    p = str(tmp_path / "new.db")
    init_db(p)
    init_db(p)
    assert pathlib.Path(p).exists()


# ── 2. Save and list ──────────────────────────────────────────────────────────

def test_save_returns_id(db):
    row_id = save_entry(
        {"item": "sugar", "quantity": 5.0, "unit": "kg", "price": 40.0, "entry_type": "sale"},
        "en", "five kg sugar forty rupees", db,
    )
    assert isinstance(row_id, int)
    assert row_id > 0


def test_save_and_list(db):
    save_entry({"item": "rice", "quantity": 2.0, "unit": "kg", "price": 55.0}, "en", "", db)
    rows = list_entries(db)
    assert len(rows) == 1
    assert rows[0]["item"] == "rice"
    assert math.isclose(rows[0]["quantity"], 2.0)
    assert math.isclose(rows[0]["price"], 55.0)
    assert math.isclose(rows[0]["total"], 110.0)


def test_total_computed_in_code(db):
    """total must always be quantity * price computed here, not from caller."""
    save_entry({"item": "x", "quantity": 7.0, "price": 13.0, "total": 999.0}, "en", "", db)
    row = list_entries(db)[0]
    assert math.isclose(row["total"], round(7.0 * 13.0, 2))


def test_hindi_roundtrip(db):
    """Hindi item text must come back byte-for-byte identical."""
    item = "रिचार्ज कूपन"
    save_entry({"item": item, "quantity": 10.0, "unit": "piece", "price": 50.0}, "hi", "", db)
    rows = list_entries(db)
    assert rows[0]["item"] == item


def test_newest_first(db):
    """list_entries must return rows newest first."""
    save_entry({"item": "a", "quantity": 1.0, "price": 1.0}, "en", "", db)
    time.sleep(0.01)   # ensure different timestamp
    save_entry({"item": "b", "quantity": 1.0, "price": 1.0}, "en", "", db)
    rows = list_entries(db)
    assert rows[0]["item"] == "b"
    assert rows[1]["item"] == "a"


# ── 3. today_total ────────────────────────────────────────────────────────────

def test_today_total_sales_only(db):
    """today_total counts only 'sale' entries, not 'purchase'."""
    save_entry({"item": "rice", "quantity": 2.0, "price": 50.0, "entry_type": "sale"}, "en", "", db)
    save_entry({"item": "soap", "quantity": 3.0, "price": 30.0, "entry_type": "purchase"}, "en", "", db)
    total = today_total(db)
    assert math.isclose(total, 100.0)   # 2*50 = 100; purchase excluded


def test_today_total_empty(db):
    assert today_total(db) == 0.0


def test_today_total_multiple(db):
    save_entry({"item": "a", "quantity": 5.0, "price": 10.0, "entry_type": "sale"}, "en", "", db)
    save_entry({"item": "b", "quantity": 2.0, "price": 20.0, "entry_type": "sale"}, "en", "", db)
    assert math.isclose(today_total(db), 90.0)   # 50 + 40


# ── 4. update_entry ───────────────────────────────────────────────────────────

def test_update_price_recomputes_total(db):
    row_id = save_entry({"item": "milk", "quantity": 2.0, "price": 50.0}, "en", "", db)
    update_entry(row_id, {"price": 60.0}, db)
    row = list_entries(db)[0]
    assert math.isclose(row["price"], 60.0)
    assert math.isclose(row["total"], 120.0)


def test_update_quantity_recomputes_total(db):
    row_id = save_entry({"item": "oil", "quantity": 1.0, "price": 100.0}, "en", "", db)
    update_entry(row_id, {"quantity": 3.0}, db)
    row = list_entries(db)[0]
    assert math.isclose(row["total"], 300.0)


def test_update_item(db):
    row_id = save_entry({"item": "old_name", "quantity": 1.0, "price": 10.0}, "en", "", db)
    update_entry(row_id, {"item": "new_name"}, db)
    assert list_entries(db)[0]["item"] == "new_name"


def test_update_nonexistent_row(db):
    """Updating a non-existent row must not raise."""
    update_entry(9999, {"price": 1.0}, db)   # should silently do nothing


# ── 5. delete_entry ───────────────────────────────────────────────────────────

def test_delete_entry(db_with_entries):
    rows_before = list_entries(db_with_entries)
    target_id   = rows_before[-1]["id"]   # oldest
    delete_entry(target_id, db_with_entries)
    ids_after = [r["id"] for r in list_entries(db_with_entries)]
    assert target_id not in ids_after
    assert len(ids_after) == len(rows_before) - 1


def test_delete_nonexistent_row(db):
    """Deleting a non-existent id must not raise."""
    delete_entry(9999, db)


def test_delete_last_entry(db_with_entries):
    before = list_entries(db_with_entries)
    last_id = before[0]["id"]   # newest = first in list
    result  = delete_last_entry(db_with_entries)
    assert result is True
    after = list_entries(db_with_entries)
    assert len(after) == len(before) - 1
    assert all(r["id"] != last_id for r in after)


def test_delete_last_entry_empty(db):
    result = delete_last_entry(db)
    assert result is False


# ── 6. entries_dataframe ──────────────────────────────────────────────────────

def test_dataframe_english_headings(db_with_entries):
    df = entries_dataframe("en", db_with_entries)
    assert "Date"      in df.columns
    assert "Time"      in df.columns
    assert "Type"      in df.columns
    assert "Item"      in df.columns
    assert "Quantity"  in df.columns
    assert "Unit"      in df.columns
    assert "Price (₹)" in df.columns
    assert "Total (₹)" in df.columns


def test_dataframe_hindi_headings(db_with_entries):
    df = entries_dataframe("hi", db_with_entries)
    assert "तारीख"  in df.columns
    assert "समय"    in df.columns
    assert "प्रकार" in df.columns
    assert "सामान"  in df.columns
    assert "मात्रा" in df.columns
    assert "इकाई"   in df.columns
    assert "दाम (₹)" in df.columns
    assert "कुल (₹)" in df.columns


def test_dataframe_date_format(db_with_entries):
    """Date column must be DD-MM-YYYY."""
    df = entries_dataframe("en", db_with_entries)
    date_val = df["Date"].iloc[0]
    parts = date_val.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 2  # DD
    assert len(parts[1]) == 2  # MM
    assert len(parts[2]) == 4  # YYYY


def test_dataframe_type_translated_hindi(db_with_entries):
    """entry_type 'sale' must appear as 'बिक्री' in Hindi DataFrame."""
    df = entries_dataframe("hi", db_with_entries)
    types = df["प्रकार"].tolist()
    assert "बिक्री" in types


def test_dataframe_empty(db):
    df = entries_dataframe("en", db)
    assert df.empty or len(df) == 0


def test_dataframe_newest_first(db_with_entries):
    """First row in DataFrame should be the most recent entry."""
    df    = entries_dataframe("en", db_with_entries)
    items = df["Item"].tolist()
    # Last saved was "rice" (purchase), so it should appear first
    assert items[0] == "rice"


# ── 7. Export ─────────────────────────────────────────────────────────────────

def test_export_xlsx_nonempty(db_with_entries):
    xlsx = export_xlsx("en", db_with_entries)
    assert isinstance(xlsx, bytes)
    assert len(xlsx) > 100   # a valid xlsx is at least a few hundred bytes


def test_export_xlsx_valid_format(db_with_entries):
    """openpyxl must be able to re-read its own output."""
    import openpyxl
    xlsx = export_xlsx("en", db_with_entries)
    wb   = openpyxl.load_workbook(io.BytesIO(xlsx))
    ws   = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    assert "Item" in headers


def test_export_csv_nonempty(db_with_entries):
    csv_bytes = export_csv("en", db_with_entries)
    assert isinstance(csv_bytes, bytes)
    assert len(csv_bytes) > 10


def test_export_csv_utf8_bom(db_with_entries):
    """CSV must start with UTF-8 BOM so Hindi opens correctly in Excel."""
    csv_bytes = export_csv("hi", db_with_entries)
    assert csv_bytes[:3] == b"\xef\xbb\xbf"   # UTF-8 BOM


def test_export_csv_hindi_headings(db_with_entries):
    csv_bytes = export_csv("hi", db_with_entries)
    text = csv_bytes.decode("utf-8-sig")
    assert "सामान" in text   # Item column in Hindi


# ── 8. seed_demo_entries ──────────────────────────────────────────────────────

def test_seed_demo_entries(db):
    seed_demo_entries(db)
    rows = list_entries(db)
    assert len(rows) == 5
    items = [r["item"] for r in rows]
    # Must include both Hindi and English items
    assert any("\u0900" <= c <= "\u097F" for item in items for c in item), \
        "Expected at least one Hindi item"
    assert any(item.isascii() and item.isalpha() for item in items), \
        "Expected at least one ASCII item"


def test_seed_totals_correct(db):
    """Every seeded entry must have total == round(qty * price, 2)."""
    seed_demo_entries(db)
    for row in list_entries(db):
        expected = round(row["quantity"] * row["price"], 2)
        assert math.isclose(row["total"], expected, rel_tol=1e-6)


# ── 9. Validation ─────────────────────────────────────────────────────────────

def test_save_missing_item_raises(db):
    with pytest.raises(ValueError, match="item"):
        save_entry({"quantity": 1.0, "price": 10.0}, "en", "", db)


def test_save_missing_quantity_raises(db):
    with pytest.raises(ValueError, match="quantity"):
        save_entry({"item": "rice", "price": 10.0}, "en", "", db)


def test_save_missing_price_raises(db):
    with pytest.raises(ValueError, match="price"):
        save_entry({"item": "rice", "quantity": 1.0}, "en", "", db)


def test_entry_type_defaults_to_sale(db):
    save_entry({"item": "x", "quantity": 1.0, "price": 1.0}, "en", "", db)
    row = list_entries(db)[0]
    assert row["entry_type"] == "sale"

