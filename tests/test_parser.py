"""
tests/test_parser.py — Pytest tests for parser.parse() and speech_text.build_readback().

Runs every row in sentences.csv through parse() and checks the extracted
fields. Rows with empty expected_item/quantity/price are the 'needs_review'
cases: the test only checks that needs_review==True.

No API calls are made in this file. Pure function tests only.

Run with:
    pytest tests/test_parser.py -v
"""

import csv
import math
import pathlib
import sys

import pytest

# Make sure the project root is on the path so we can import parser.py
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from parser import parse
from speech_text import build_readback

# ── Load the CSV once for all tests ─────────────────────────────────────────
CSV_PATH = pathlib.Path(__file__).parent / "sentences.csv"


def _load_rows() -> list[dict]:
    rows = []
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


ROWS = _load_rows()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _float_or_none(s: str):
    s = s.strip()
    return float(s) if s else None


def _str_or_none(s: str):
    s = s.strip()
    return s if s else None


def _is_incomplete(row: dict) -> bool:
    """A row is 'incomplete' (needs_review expected) if qty or price is empty."""
    return not row["quantity"].strip() or not row["price"].strip()


# ── Parametrised test: one test per CSV row ───────────────────────────────────

@pytest.mark.parametrize("row", ROWS, ids=[f"row_{i+1}" for i in range(len(ROWS))])
def test_parse_row(row):
    stt = {"transcript": row["transcript"], "literal": row["literal"]}
    lang = row["language"].strip()

    result = parse(stt, lang)

    if _is_incomplete(row):
        # For deliberately incomplete sentences, only check needs_review flag
        assert result["needs_review"], (
            f"Expected needs_review=True for incomplete sentence: "
            f"{row['transcript']!r}, got result: {result}"
        )
        return

    exp_item     = _str_or_none(row["item"])
    exp_qty      = _float_or_none(row["quantity"])
    exp_unit     = _str_or_none(row["unit"])
    exp_price    = _float_or_none(row["price"])
    exp_total    = _float_or_none(row["total"])
    exp_type     = row["entry_type"].strip() or "sale"

    # Item check (case-insensitive strip for safety)
    if exp_item is not None:
        assert result["item"] is not None, (
            f"Expected item {exp_item!r} but got None. "
            f"Transcript: {row['transcript']!r}"
        )
        assert result["item"].strip() == exp_item, (
            f"Item mismatch: got {result['item']!r}, expected {exp_item!r}. "
            f"Transcript: {row['transcript']!r}"
        )

    # Quantity check (allow small float tolerance)
    if exp_qty is not None:
        assert result["quantity"] is not None, (
            f"Expected quantity={exp_qty} but got None. "
            f"Transcript: {row['transcript']!r}"
        )
        assert math.isclose(result["quantity"], exp_qty, rel_tol=1e-4), (
            f"Quantity mismatch: got {result['quantity']}, expected {exp_qty}. "
            f"Transcript: {row['transcript']!r}"
        )

    # Unit check
    if exp_unit is not None:
        assert result["unit"] == exp_unit, (
            f"Unit mismatch: got {result['unit']!r}, expected {exp_unit!r}. "
            f"Transcript: {row['transcript']!r}"
        )

    # Price check
    if exp_price is not None:
        assert result["price"] is not None, (
            f"Expected price={exp_price} but got None. "
            f"Transcript: {row['transcript']!r}"
        )
        assert math.isclose(result["price"], exp_price, rel_tol=1e-4), (
            f"Price mismatch: got {result['price']}, expected {exp_price}. "
            f"Transcript: {row['transcript']!r}"
        )

    # Total: always computed in code — verify arithmetic is correct
    if exp_total is not None and result["total"] is not None:
        assert math.isclose(result["total"], exp_total, rel_tol=1e-4), (
            f"Total mismatch: got {result['total']}, expected {exp_total}. "
            f"Transcript: {row['transcript']!r}"
        )
    # Also verify our own arithmetic (never trust the spoken total)
    if result["quantity"] is not None and result["price"] is not None:
        expected_computed = round(result["quantity"] * result["price"], 2)
        assert result["total"] == expected_computed, (
            f"total != quantity * price: "
            f"{result['total']} != {result['quantity']} * {result['price']}. "
            f"Transcript: {row['transcript']!r}"
        )

    # Entry type
    assert result["entry_type"] == exp_type, (
        f"Entry type mismatch: got {result['entry_type']!r}, expected {exp_type!r}. "
        f"Transcript: {row['transcript']!r}"
    )


# ── Readback tests: spot-check that build_readback() produces sensible text ──

def test_readback_hindi():
    """build_readback for a Hindi entry must be Devanagari and end with सही है?"""
    entry = {
        "item": "चावल", "quantity": 50.0, "unit": "kg",
        "price": 60.0,  "total": 3000.0, "entry_type": "sale",
    }
    text = build_readback(entry, "hi")
    assert "सही है?" in text, f"Hindi readback missing confirmation: {text!r}"
    # Must contain Devanagari characters
    assert any("\u0900" <= c <= "\u097F" for c in text), (
        f"Hindi readback has no Devanagari characters: {text!r}"
    )
    # Number words, not digits
    assert "50" not in text and "60" not in text and "3000" not in text, (
        f"Hindi readback contains raw digits: {text!r}"
    )


def test_readback_english():
    """build_readback for English must end with 'Is that correct?' and have no digits."""
    entry = {
        "item": "rice", "quantity": 50.0, "unit": "kg",
        "price": 60.0,  "total": 3000.0, "entry_type": "sale",
    }
    text = build_readback(entry, "en")
    assert "Is that correct?" in text, f"English readback missing confirmation: {text!r}"
    assert "50" not in text and "60" not in text and "3000" not in text, (
        f"English readback contains raw digits: {text!r}"
    )
    assert "fifty" in text.lower(), f"Expected 'fifty' in readback: {text!r}"
    assert "three thousand" in text.lower(), f"Expected 'three thousand': {text!r}"


def test_readback_fractions_hindi():
    """Devanagari fraction words must be used (dedh for 1.5, dhai for 2.5)."""
    for qty, expected in [(1.5, "डेढ़"), (2.5, "ढाई")]:
        entry = {
            "item": "tamatar", "quantity": qty, "unit": "kg",
            "price": 40.0, "total": round(qty * 40, 2), "entry_type": "sale",
        }
        text = build_readback(entry, "hi")
        assert expected in text, (
            f"Expected {expected!r} in readback for qty={qty}: {text!r}"
        )


def test_readback_fractions_english():
    """English fraction words must use 'one and a half' / 'two and a half'."""
    for qty, expected in [(1.5, "one and a half"), (2.5, "two and a half")]:
        entry = {
            "item": "milk", "quantity": qty, "unit": "litre",
            "price": 55.0, "total": round(qty * 55, 2), "entry_type": "sale",
        }
        text = build_readback(entry, "en")
        assert expected in text.lower(), (
            f"Expected {expected!r} in readback for qty={qty}: {text!r}"
        )


def test_incomplete_needs_review():
    """An empty audio transcript must set needs_review=True."""
    result = parse({"transcript": "", "literal": ""}, "hi")
    assert result["needs_review"]
    assert result["warnings"]


# ── Summary reporter: print pass count per language ──────────────────────────

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """After all tests run, print pass/fail per language from the CSV rows."""
    hi_pass = hi_fail = en_pass = en_fail = 0
    for row in ROWS:
        if _is_incomplete(row):
            continue   # incomplete rows counted separately
        lang = row["language"].strip()
        # We can't easily hook into per-parametrize results here,
        # so we just re-run parse() silently and tally.
        stt = {"transcript": row["transcript"], "literal": row["literal"]}
        try:
            r = parse(stt, lang)
            exp_item  = _str_or_none(row["item"])
            exp_price = _float_or_none(row["price"])
            exp_qty   = _float_or_none(row["quantity"])
            ok = True
            if exp_item and r["item"] and r["item"].strip() != exp_item:
                ok = False
            if exp_qty and r["quantity"] and not math.isclose(r["quantity"], exp_qty, rel_tol=1e-4):
                ok = False
            if exp_price and r["price"] and not math.isclose(r["price"], exp_price, rel_tol=1e-4):
                ok = False
        except Exception:
            ok = False

        if lang == "hi":
            if ok: hi_pass += 1
            else:  hi_fail += 1
        else:
            if ok: en_pass += 1
            else:  en_fail += 1

    print(f"\n── Parser accuracy summary ──────────────────────────")
    print(f"  Hindi   : {hi_pass} passed, {hi_fail} failed  ({hi_pass+hi_fail} tested)")
    print(f"  English : {en_pass} passed, {en_fail} failed  ({en_pass+en_fail} tested)")
    print(f"────────────────────────────────────────────────────")

