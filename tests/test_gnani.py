"""
tests/test_gnani.py — Tests for gnani.py wrapper error paths and responses with mocked HTTP.

No real network calls or Gnani credits are consumed.
"""

from __future__ import annotations

import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import gnani


@pytest.fixture(autouse=True)
def ensure_api_key(monkeypatch):
    """Ensure GNANI_API_KEY is present for tests."""
    monkeypatch.setenv("GNANI_API_KEY", "test_mock_key_vach_dummy")


# ── STT ───────────────────────────────────────────────────────────────────────

def test_stt_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "transcript": "50 किलो चावल 60 रुपये किलो",
        "output": {"literal": "पचास किलो चावल साठ रुपये किलो"},
    }

    with patch("requests.post", return_value=mock_resp):
        res = gnani.stt(b"fake_audio", "hi-IN")
        assert res["transcript"] == "50 किलो चावल 60 रुपये किलो"
        assert res["literal"] == "पचास किलो चावल साठ रुपये किलो"


def test_stt_401_unauthorized():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Invalid or missing API key"):
            gnani.stt(b"fake_audio", "hi-IN")


def test_stt_429_rate_limit():
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="API busy"):
            gnani.stt(b"fake_audio", "hi-IN")


def test_stt_500_server_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Gnani server error"):
            gnani.stt(b"fake_audio", "hi-IN")


def test_stt_timeout():
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        with pytest.raises(RuntimeError, match="Speech recognition timed out"):
            gnani.stt(b"fake_audio", "hi-IN")


def test_stt_network_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Network down")):
        with pytest.raises(RuntimeError, match="Cannot reach STT API"):
            gnani.stt(b"fake_audio", "hi-IN")


# ── TTS ───────────────────────────────────────────────────────────────────────

def test_tts_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"RIFF\x00\x00\x00\x00WAVEfmt "

    with patch("requests.post", return_value=mock_resp):
        res = gnani.tts("चावल पचास किलो", "hi")
        assert res.startswith(b"RIFF")


def test_tts_429_retries_and_succeeds():
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.content = b"RIFFaudio"

    with patch("time.sleep", return_value=None):
        with patch("requests.post", side_effect=[resp_429, resp_200]) as mock_post:
            audio = gnani.tts("two litre milk", "en")
            assert audio == b"RIFFaudio"
            assert mock_post.call_count == 2


def test_tts_401_unauthorized():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Invalid or missing API key"):
            gnani.tts("test", "en")


def test_tts_timeout():
    with patch("requests.post", side_effect=requests.exceptions.Timeout):
        with pytest.raises(RuntimeError, match="Text-to-speech timed out"):
            gnani.tts("test", "en")


def test_tts_empty_content_raises():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b""

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="empty audio response"):
            gnani.tts("test", "en")


def test_tts_invalid_language():
    with pytest.raises(ValueError, match="lang must be 'hi' or 'en'"):
        gnani.tts("test", "fr")


# ── Number to words ───────────────────────────────────────────────────────────

def test_number_to_words_hindi():
    assert gnani.number_to_words(50, "hi") == "pachaas"
    assert gnani.number_to_words(1.5, "hi") == "dedh"
    assert gnani.number_to_words(2.5, "hi") == "dhai"
    assert gnani.number_to_words(100, "hi") == "ek sau"


def test_number_to_words_english():
    assert "fifty" in gnani.number_to_words(50, "en").lower()
    assert "three thousand" in gnani.number_to_words(3000, "en").lower()


# ── Missing Key ───────────────────────────────────────────────────────────────

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    monkeypatch.setattr(gnani, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(EnvironmentError, match="GNANI_API_KEY is not set"):
        gnani._get_api_key()
