"""
test_tts.py — Manual test script for Gnani TTS (Timbre).

Usage:
    python test_tts.py hi      ← Hindi  (voice: Nalini, saves tts_output_hi.wav)
    python test_tts.py en      ← English (voice: Kaveri, saves tts_output_en.wav)

What it does:
  1. Builds a sample entry read-back sentence using build_readback() from
     speech_text.py — same function used in the real app.
     Hindi output is in Devanagari script; English output is in English words.
     All numbers are spoken words, never raw digits (TTS requirement).
  2. Sends it to the Gnani TTS API with the correct model, voice, and
     audio_config (from official docs).
  3. Prints the full HTTP response: status code and ALL headers.
  4. Saves the audio body to tts_output_hi.wav or tts_output_en.wav.
  5. If the response is JSON (error body), prints it instead of saving.

Security: the API key is loaded from .env by gnani.py. This script never
reads, prints, or touches the .env file or the key itself.
"""

import sys
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(override=False)

# Import our helpers
from gnani import _TTS_CONFIG, TTS_URL, REQUEST_TIMEOUT, _get_api_key
from speech_text import build_readback

# ── Sample entry — a real entry a shopkeeper might record ────────────────────
_SAMPLE_ENTRY = {
    "item":       None,  # filled per language below
    "quantity":   50.0,
    "unit":       "kg",
    "price":      60.0,
    "total":      3000.0,
    "entry_type": "sale",
}


def main():
    # ── Parse argument ───────────────────────────────────────────────────────
    if len(sys.argv) != 2 or sys.argv[1] not in ("hi", "en"):
        print("Usage: python test_tts.py hi")
        print("       python test_tts.py en")
        sys.exit(1)

    lang = sys.argv[1]
    cfg  = _TTS_CONFIG[lang]

    # Set item name in the right script
    entry = dict(_SAMPLE_ENTRY)
    entry["item"] = "चावल" if lang == "hi" else "rice"

    # Build the read-back sentence using the same function as the app
    sentence = build_readback(entry, lang)
    out_file = f"tts_output_{lang}.wav"

    print(f"Language     : {lang} → voice={cfg['voice']}, language={cfg['language']}")
    print(f"Model        : timbre-v2.5")
    print(f"Text to speak:")
    print(f"  {sentence}")
    print(f"Output file  : {out_file}")
    print("-" * 60)

    # ── Read key (without printing it) ──────────────────────────────────────
    key = _get_api_key()

    # ── Build request exactly as gnani.tts() does ────────────────────────────
    headers = {
        "X-API-Key-ID": key,
        "Content-Type": "application/json",
    }
    payload = {
        "text":     sentence,
        "voice":    cfg["voice"],
        "model":    "timbre-v2.5",
        "language": cfg["language"],
        "speed":    1.0,
        "audio_config": {
            "sample_rate":  48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding":     "linear_pcm",
            "container":    "wav",
        },
    }

    # ── Send ─────────────────────────────────────────────────────────────────
    try:
        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"NETWORK ERROR: {exc}")
        sys.exit(1)

    # ── Print response metadata ──────────────────────────────────────────────
    print(f"HTTP status  : {response.status_code}")
    print()
    print("Response headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    print()

    content_type = response.headers.get("Content-Type", "unknown")
    print(f"Content-Type : {content_type}")
    print(f"Body size    : {len(response.content):,} bytes")
    print()

    # ── Save or display body ─────────────────────────────────────────────────
    if "json" in content_type.lower() or response.status_code != 200:
        print("Response body (JSON / error):")
        try:
            body = response.json()
            print(json.dumps(body, ensure_ascii=False, indent=2))
        except ValueError:
            print(response.text[:500])
    else:
        with open(out_file, "wb") as f:
            f.write(response.content)
        print(f"Audio saved to: {out_file}")
        print("Open that file and listen — confirm it sounds natural.")

    print()
    print("-" * 60)
    print("Share the HTTP status, headers, and any error body above.")


if __name__ == "__main__":
    main()
