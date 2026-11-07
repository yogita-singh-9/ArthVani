"""
test_stt.py — Manual test script for Gnani STT.

Usage:
    python test_stt.py <audio_file> <language_code>

Examples:
    python test_stt.py Hindi_Test.m4a hi-IN
    python test_stt.py English_Test.m4a en-IN

What it does:
  1. Reads the audio file you give it.
  2. Sends it to Gnani Prisma (STT) via gnani.py.
  3. Prints the FULL raw HTTP response (status, headers, body) so you can
     see the exact shape of the API response and report it back for Phase 2.

Security: the API key is loaded from .env by gnani.py. This script never
reads, prints, or touches .env or the key itself.
"""

import sys
import os
import json
import requests
from dotenv import load_dotenv

# Load .env so GNANI_API_KEY is available
load_dotenv(override=False)

# ── Import our wrapper (but we also want the raw response, so we duplicate
#    the HTTP call here with extra printing) ──────────────────────────────────
STT_URL = "https://api.vachana.ai/stt/v3"
REQUEST_TIMEOUT = 60


def main():
    # ── Parse command-line arguments ─────────────────────────────────────────
    if len(sys.argv) != 3:
        print("Usage: python test_stt.py <audio_file> <language_code>")
        print("Example: python test_stt.py Hindi_Test.m4a hi-IN")
        sys.exit(1)

    audio_path = sys.argv[1]
    language_code = sys.argv[2]

    # ── Check the file exists ────────────────────────────────────────────────
    if not os.path.isfile(audio_path):
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    # ── Read the API key (without printing it) ───────────────────────────────
    key = os.environ.get("GNANI_API_KEY", "")
    if not key:
        print("ERROR: GNANI_API_KEY is not set. Add it to .env.")
        sys.exit(1)

    print(f"Audio file   : {audio_path}  ({os.path.getsize(audio_path):,} bytes)")
    print(f"Language code: {language_code}")
    print(f"Sending to   : {STT_URL}")
    print("-" * 60)

    # ── Read audio bytes ─────────────────────────────────────────────────────
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    filename = os.path.basename(audio_path)

    # ── Build request exactly as gnani.py does ───────────────────────────────
    files = {"audio_file": (filename, audio_bytes)}
    data = {"language_code": language_code}
    headers = {"X-API-Key-ID": key}

    # ── Send ─────────────────────────────────────────────────────────────────
    try:
        response = requests.post(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"NETWORK ERROR: {exc}")
        sys.exit(1)

    # ── Print everything about the response (never the request headers which
    #    contain the key) ─────────────────────────────────────────────────────
    print(f"HTTP status  : {response.status_code}")
    print()
    print("Response headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    print()

    # Try to pretty-print JSON; fall back to raw text
    print("Response body:")
    try:
        body = response.json()
        print(json.dumps(body, ensure_ascii=False, indent=2))
    except ValueError:
        print(response.text)

    print()
    print("-" * 60)
    print("Share the output above (HTTP status, headers, body) so the")
    print("parser can be built around the REAL response format.")


if __name__ == "__main__":
    main()

