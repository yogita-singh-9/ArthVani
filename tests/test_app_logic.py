"""
tests/test_app_logic.py — Unit tests for pure app logic and helpers.

No Streamlit, no API calls, no network, no database I/O.
Tests audio_hash, compute_total, build_entry_dict, readback_cache_key.
"""

import hashlib
import pathlib
import sys

# Ensure project root is importable
_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import pytest
from app_helpers import (
    audio_hash,
    compute_total,
    build_entry_dict,
    readback_cache_key,
)
from strings import t, unit_selector_labels, UNIT_OPTIONS


# ── audio_hash tests ─────────────────────────────────────────────────────────

def test_audio_hash_deterministic():
    data = b"RIFF....WAVEfmt ...."
    assert audio_hash(data) == audio_hash(data)
    assert audio_hash(data) == hashlib.sha256(data).hexdigest()


def test_audio_hash_different_inputs():
    assert audio_hash(b"audio-1") != audio_hash(b"audio-2")


def test_audio_hash_empty_bytes():
    assert audio_hash(b"") == hashlib.sha256(b"").hexdigest()


# ── compute_total tests ───────────────────────────────────────────────────────

def test_compute_total_standard():
    assert compute_total(50, 60) == 3000.0
    assert compute_total(2, 45.5) == 91.0
    assert compute_total(1.5, 30) == 45.0
    assert compute_total(0.5, 80) == 40.0


def test_compute_total_rounding():
    # 3.33 * 3 = 9.99
    assert compute_total(3, 3.3333) == 10.0
    assert compute_total(1.25, 33.33) == 41.66


def test_compute_total_none_handling():
    assert compute_total(None, 60) is None
    assert compute_total(50, None) is None
    assert compute_total(None, None) is None


def test_compute_total_zero():
    assert compute_total(0, 50) == 0.0
    assert compute_total(50, 0) == 0.0


# ── build_entry_dict tests ────────────────────────────────────────────────────

def test_build_entry_dict_shape():
    e = build_entry_dict("चावल", 50, "kg", 60, "sale")
    assert e == {
        "item": "चावल",
        "quantity": 50,
        "unit": "kg",
        "price": 60,
        "total": 3000.0,
        "entry_type": "sale",
    }


def test_build_entry_dict_recomputes_total():
    # Even if total was None, it computes it
    e = build_entry_dict("rice", 2.5, "kg", 40, "sale")
    assert e["total"] == 100.0


def test_build_entry_dict_missing_fields_yield_none_total():
    e = build_entry_dict("oil", None, "litre", 120, "purchase")
    assert e["total"] is None
    assert e["entry_type"] == "purchase"


# ── readback_cache_key tests ──────────────────────────────────────────────────

def test_readback_cache_key_stable():
    e = {"item": "rice", "quantity": 50, "unit": "kg", "price": 60}
    assert readback_cache_key(e, "en") == readback_cache_key(e, "en")
    assert readback_cache_key(e, "en") == "en|rice|50|kg|60"


def test_readback_cache_key_language_sensitive():
    e = {"item": "चावल", "quantity": 50, "unit": "kg", "price": 60}
    assert readback_cache_key(e, "hi") != readback_cache_key(e, "en")


def test_readback_cache_key_value_sensitive():
    e1 = {"item": "rice", "quantity": 50, "unit": "kg", "price": 60}
    e2 = {"item": "rice", "quantity": 50, "unit": "kg", "price": 65}
    assert readback_cache_key(e1, "en") != readback_cache_key(e2, "en")


def test_readback_cache_key_handles_none_values():
    e = {"item": None, "quantity": None, "unit": None, "price": None}
    key = readback_cache_key(e, "hi")
    assert "None" in key


# ── UI strings helpers smoke tests ────────────────────────────────────────────

def test_unit_selector_labels_complete():
    for lang in ("hi", "en"):
        labels = unit_selector_labels(lang)
        for unit in UNIT_OPTIONS:
            assert unit in labels
            assert len(labels[unit]) > 0


def test_t_fallback_smoke():
    # Known key exists in both languages
    assert t("app_name", "hi") == "अर्थवाणी"
    assert t("app_name", "en") == "ArthVani"
    # Non-existent key raises KeyError to catch typos in dev
    with pytest.raises(KeyError):
        t("non_existent_key_xyz", "hi")
