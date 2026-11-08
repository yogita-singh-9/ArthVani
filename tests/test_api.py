"""
tests/test_api.py — FastAPI endpoint tests (no real Gnani calls).

Uses FastAPI TestClient (httpx) with a temporary SQLite database.
Gnani STT/TTS calls are mocked so no network is required.
"""

from __future__ import annotations

import io
import os
import pathlib
import sys
from unittest.mock import patch

import pytest

# Ensure project root is on path
_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# Set a dummy API key so gnani doesn't raise EnvironmentError
os.environ.setdefault("GNANI_API_KEY", "test_dummy_key")

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    """Create a fresh temporary database for the test module."""
    db_path = str(tmp_path_factory.mktemp("db") / "test.db")
    return db_path


@pytest.fixture(scope="module")
def client(tmp_db):
    """Return a TestClient wired to the tmp DB."""
    import db as _db
    _db.init_db(tmp_db)

    # Patch the DB path used by the app
    import main as _main
    _main._DB_PATH = tmp_db
    _db.DB_PATH    = tmp_db

    return TestClient(_main.app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "api_key_configured" in data


# ── i18n ──────────────────────────────────────────────────────────────────────

def test_i18n_hi(client):
    r = client.get("/api/i18n/hi")
    assert r.status_code == 200
    data = r.json()
    assert "tagline" in data
    assert "बोलिए" in data.get("tagline", "")


def test_i18n_en(client):
    r = client.get("/api/i18n/en")
    assert r.status_code == 200
    data = r.json()
    assert "tagline" in data
    assert "Speak" in data.get("tagline", "")


def test_i18n_invalid_lang(client):
    r = client.get("/api/i18n/fr")
    assert r.status_code == 400


# ── Parse text ────────────────────────────────────────────────────────────────

def test_parse_text_hi(client):
    r = client.post("/api/parse-text", json={"text": "50 किलो चावल 60 रुपये किलो", "language": "hi"})
    assert r.status_code == 200
    data = r.json()
    assert data["parsed"]["item"] == "चावल"
    assert data["parsed"]["quantity"] == 50.0
    assert data["parsed"]["price"]    == 60.0
    assert data["parsed"]["unit"]     == "kg"
    assert data["parsed"]["total"]    == 3000.0


def test_parse_text_en(client):
    r = client.post("/api/parse-text", json={"text": "50 kilo rice 60 rupees per kilo", "language": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["parsed"]["item"]     == "rice"
    assert data["parsed"]["quantity"] == 50.0
    assert data["parsed"]["price"]    == 60.0


def test_parse_text_needs_review(client):
    r = client.post("/api/parse-text", json={"text": "चावल बेचा", "language": "hi"})
    assert r.status_code == 200
    assert r.json()["parsed"]["needs_review"] is True


def test_parse_text_invalid_lang(client):
    r = client.post("/api/parse-text", json={"text": "rice", "language": "fr"})
    assert r.status_code == 400


# ── Entries CRUD ──────────────────────────────────────────────────────────────

def test_create_entry(client):
    payload = {
        "item": "चावल", "quantity": 10.0, "unit": "kg",
        "price": 60.0, "entry_type": "sale",
        "language": "hi", "transcript": "दस किलो चावल",
    }
    r = client.post("/api/entries", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["item"]     == "चावल"
    assert data["total"]    == 600.0
    assert data["id"] is not None


def test_list_entries(client):
    r = client.get("/api/entries")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert "total" in data
    assert data["total"] >= 1


def test_filter_entries_by_type(client):
    r = client.get("/api/entries?filter=sale")
    assert r.status_code == 200
    for e in r.json()["entries"]:
        assert e["entry_type"] == "sale"


def test_search_entries(client):
    r = client.get("/api/entries?search=चावल")
    assert r.status_code == 200
    data = r.json()
    assert any("चावल" in e["item"] for e in data["entries"])


def test_update_entry(client):
    # Create a fresh entry
    payload = {"item": "milk", "quantity": 2.0, "unit": "litre", "price": 55.0,
               "entry_type": "sale", "language": "en"}
    create_r = client.post("/api/entries", json=payload)
    row_id = create_r.json()["id"]

    r = client.put(f"/api/entries/{row_id}", json={"price": 60.0})
    assert r.status_code == 200
    data = r.json()
    assert data["price"] == 60.0
    assert data["total"] == 120.0  # 2 * 60


def test_delete_entry(client):
    payload = {"item": "soap", "quantity": 5.0, "unit": "piece",
               "price": 30.0, "entry_type": "sale", "language": "en"}
    create_r = client.post("/api/entries", json=payload)
    row_id = create_r.json()["id"]

    r = client.delete(f"/api/entries/{row_id}")
    assert r.status_code == 204

    # Verify gone
    list_r = client.get(f"/api/entries?search=soap")
    assert not any(e["id"] == row_id for e in list_r.json()["entries"])


def test_update_nonexistent_entry(client):
    r = client.put("/api/entries/999999", json={"price": 50.0})
    assert r.status_code == 404


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary(client):
    r = client.get("/api/summary")
    assert r.status_code == 200
    data = r.json()
    assert "today"     in data
    assert "week"      in data
    assert "series_14d" in data
    assert "top_items"  in data
    assert len(data["series_14d"]) == 14
    assert "sales" in data["today"]
    assert "purchases" in data["today"]
    assert "net"       in data["today"]


# ── Exports ───────────────────────────────────────────────────────────────────

def test_export_xlsx(client):
    r = client.get("/api/export.xlsx?lang=en")
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    assert len(r.content) > 100  # actual xlsx bytes


def test_export_csv(client):
    r = client.get("/api/export.csv?lang=hi")
    assert r.status_code == 200
    assert "csv" in r.headers["content-type"].lower()
    # UTF-8-sig BOM
    assert r.content[:3] == b'\xef\xbb\xbf'


# ── Transcribe (mocked) ───────────────────────────────────────────────────────

def test_transcribe_no_audio(client):
    """Empty audio blob should return 400."""
    r = client.post("/api/transcribe", data={"language": "hi"},
                    files={"audio_file": ("rec.webm", b"", "audio/webm")})
    assert r.status_code == 400


def test_transcribe_mocked(client):
    """Mock gnani.stt to test the full transcribe pipeline without network."""
    mock_stt = {"transcript": "50 किलो चावल ₹60 किलो", "literal": "पचास किलो चावल साठ रुपए किलो"}
    with patch("gnani.stt", return_value=mock_stt):
        fake_audio = b"\x00" * 5000  # non-empty fake bytes
        r = client.post("/api/transcribe", data={"language": "hi"},
                        files={"audio_file": ("rec.webm", fake_audio, "audio/webm")})
    assert r.status_code == 200
    data = r.json()
    assert data["transcript"] == mock_stt["transcript"]
    assert data["parsed"]["item"] == "चावल"
    assert data["parsed"]["quantity"] == 50.0
    assert data["parsed"]["price"]    == 60.0


# ── TTS (mocked) ──────────────────────────────────────────────────────────────

def test_tts_mocked(client):
    with patch("gnani.tts", return_value=b"RIFF\x00\x00\x00\x00WAVEfmt "):
        r = client.post("/api/tts", json={"text": "चावल पचास किलो", "language": "hi"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")


def test_tts_invalid_lang(client):
    r = client.post("/api/tts", json={"text": "rice", "language": "fr"})
    assert r.status_code == 400


# ── Demo data ─────────────────────────────────────────────────────────────────

def test_demo_load_idempotent(client):
    r1 = client.post("/api/demo/load")
    assert r1.status_code == 200
    inserted1 = r1.json()["inserted"]
    assert inserted1 > 0

    r2 = client.post("/api/demo/load")
    assert r2.status_code == 200
    assert r2.json()["inserted"] == 0  # already seeded — no duplicates


def test_demo_clear(client):
    client.post("/api/demo/load")  # ensure seeded

    list_r = client.get("/api/entries?limit=500")
    before = list_r.json()["total"]

    r = client.post("/api/demo/clear")
    assert r.status_code == 200
    deleted = r.json()["deleted"]
    assert deleted > 0

    list_r2 = client.get("/api/entries?limit=500")
    after = list_r2.json()["total"]
    assert after == before - deleted

