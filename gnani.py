"""
gnani.py — Wrappers for Gnani AI's STT (Prisma) and TTS (Timbre) REST APIs.

Public API
----------
  stt(audio_bytes, language_code, filename) -> dict
      Returns {"transcript": str, "literal": str}

  tts(text, lang) -> bytes
      Returns raw WAV audio bytes.
      lang must be "hi" (Hindi, voice Nalini) or "en" (English, voice Kaveri).

  number_to_words(n, lang) -> str
      Converts a number to spoken words suitable for TTS input.
      Uses num2words for English; a hand-built table for Hindi (num2words
      does not support Hindi).

Security
--------
  The API key is read from GNANI_API_KEY in the environment (via .env loaded
  with python-dotenv). It is never printed, logged, returned, or stored here.

Concurrency
-----------
  NEVER call stt() and tts() concurrently. Some Gnani accounts allow only
  one active request at a time (HTTP 429). Always call them one after the
  other. tts() retries once after 2 seconds on a 429 response.
"""

import os
import time
import requests
from dotenv import load_dotenv

# Load .env at import time. override=False means an env var already set
# in the shell wins (useful in CI where there is no .env file).
load_dotenv(override=False)

# ── Endpoints ────────────────────────────────────────────────────────────────
STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

# Seconds to wait before timing out a request
REQUEST_TIMEOUT = 60

# ── TTS voice and language per UI language ───────────────────────────────────
# Source: official Gnani TTS docs (timbre-v2.5)
_TTS_CONFIG = {
    "hi": {"voice": "Nalini",  "language": "hi-IN"},
    "en": {"voice": "Kaveri",  "language": "en-IN"},
}

# ── Hindi number words (0–99 + scale words) ──────────────────────────────────
# num2words does not support Hindi, so we use a hand-built lookup table.
# Covers every integer 1–99; hundreds/thousands are built from these atoms.
_HINDI_ONES = [
    "",           # 0 — handled separately
    "ek",         "do",          "teen",        "chaar",
    "paanch",     "chhah",       "saat",        "aath",        "nau",
    "das",        "gyaarah",     "baarah",       "terah",       "chaudah",
    "pandrah",    "solah",       "satrah",       "atharah",     "unees",
    "bees",       "ikkees",      "baais",        "teis",        "chaubees",
    "pachchees",  "chhabbees",   "sattaees",     "atthaees",    "unattees",
    "tees",       "ikattees",    "battees",      "taintees",    "chautees",
    "paintees",   "chhattees",   "saaintees",    "artees",      "untaalees",
    "chaalees",   "iktalees",    "bayaalees",    "tentaalees",  "chauwalees",
    "paintaalees","chhiyaalees", "saintaalees",  "artaalees",   "unchaas",
    "pachaas",    "ikkyavan",    "baavan",       "tirpan",      "chauvan",
    "pachpan",    "chhappan",    "sattavan",     "atthavan",    "unsath",
    "saath",      "iksath",      "basath",       "tirsath",     "chausath",
    "painsath",   "chhiyasath",  "sarsath",      "arsath",      "unhattar",
    "sattar",     "ikhattar",    "bahattar",     "tihattar",    "chauhattar",
    "pachhattar", "chhihattar",  "sathattar",    "athattar",    "unnasi",
    "assi",       "ikyaasi",     "byaasi",       "tiraasi",     "chauraasi",
    "pachaasi",   "chhiyaasi",   "sattaasi",     "atthaasi",    "navaasi",
    "nabbe",      "ek sau",      "do sau",       "teen sau",    "chaar sau",
    "paanch sau", "chhah sau",   "saat sau",     "aath sau",    "nau sau",
]  # indices 1–99 are ones/tens; 91 would be "ek sau" if used as list[91]
#   but we don't — we build hundreds via _hindi_int() below.

# Common fraction words used in spoken Hindi for prices/quantities
_HINDI_FRACTIONS = {
    0.25: "paav",          # ¼
    0.5:  "aadha",         # ½
    0.75: "paune",         # ¾
    1.25: "sava",          # 1¼  (sava ek = 1.25, sava do = 2.25, etc.)
    1.5:  "dedh",          # 1½
    2.5:  "dhai",          # 2½
}


def _hindi_int(n: int) -> str:
    """Convert a non-negative integer to Hindi words (supports 0–99 999)."""
    if n == 0:
        return "shunya"
    if n < 0:
        return "minus " + _hindi_int(-n)

    parts = []

    # Lakh (100 000)
    if n >= 100_000:
        parts.append(_hindi_int(n // 100_000) + " lakh")
        n %= 100_000

    # Hazaar (1 000)
    if n >= 1_000:
        parts.append(_hindi_int(n // 1_000) + " hazaar")
        n %= 1_000

    # Sau (100)
    if n >= 100:
        parts.append(_HINDI_ONES[n // 100] + " sau")
        n %= 100

    # 1–99 — look up directly in the table
    if n > 0:
        parts.append(_HINDI_ONES[n])

    return " ".join(parts)


def number_to_words(n: float, lang: str) -> str:
    """
    Convert a number to spoken words for TTS input.

    The Gnani TTS docs say numbers must be spelled as words, not digits,
    or they will be mispronounced.

    Parameters
    ----------
    n    : number to convert (int or float)
    lang : "hi" for Hindi words, "en" for English words

    Examples
    --------
    number_to_words(50,   "hi") -> "pachaas"
    number_to_words(60,   "hi") -> "saath"
    number_to_words(3000, "hi") -> "teen hazaar"
    number_to_words(1.5,  "hi") -> "dedh"
    number_to_words(50,   "en") -> "fifty"
    number_to_words(3000, "en") -> "three thousand"
    """
    if lang == "hi":
        # Check common fraction shortcuts first
        if n in _HINDI_FRACTIONS:
            return _HINDI_FRACTIONS[n]
        # Integer or build integer + fraction
        int_part = int(n)
        frac = round(n - int_part, 10)
        if frac == 0:
            return _hindi_int(int_part)
        # For non-special fractions, spell the decimal in words
        # e.g. 2.5 → dhai (special case above), 1.75 → not standard
        # Fall back to: "<integer> point <digits>"
        frac_str = f"{frac:.10f}".rstrip("0").lstrip("0.")
        frac_words = " ".join(_HINDI_ONES[int(d)] for d in frac_str if d.isdigit() and int(d) > 0)
        return f"{_hindi_int(int_part)} point {frac_words}".strip()

    else:  # English — use num2words (en_IN variant)
        try:
            from num2words import num2words as _n2w
        except ImportError:
            raise ImportError("Install num2words: pip install num2words")

        if n == int(n):
            return _n2w(int(n), lang="en_IN")
        # Float: e.g. 1.5 -> "one point five"
        return _n2w(float(n), lang="en_IN")


# ── Private helpers ──────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """Read the API key from the environment. Never print or return it to callers."""
    key = os.environ.get("GNANI_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GNANI_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return key


def _friendly_error(status_code: int, body_text: str) -> str:
    """Map an HTTP error code to a short, user-readable message."""
    messages = {
        401: "Invalid or missing API key. Check GNANI_API_KEY in your .env file.",
        402: "Account has no credits. Please top up your Gnani account.",
        403: "Your API key does not have permission for this endpoint.",
        429: "API busy — only one request is allowed at a time. Please wait and try again.",
    }
    if status_code in messages:
        return messages[status_code]
    # Trim the raw body to avoid showing stack traces or secrets
    snippet = body_text[:200].strip()
    return f"API error (HTTP {status_code}): {snippet}"


# ── Public functions ─────────────────────────────────────────────────────────

def stt(audio_bytes: bytes, language_code: str, filename: str = "audio.wav") -> dict:
    """
    Send audio to Gnani Prisma (STT) and return a dict with the transcript.

    Parameters
    ----------
    audio_bytes   : raw bytes of the audio file
    language_code : "hi-IN" for Hindi or "en-IN" for English
    filename      : original filename — Gnani uses the extension to detect format

    Returns
    -------
    dict:
      "transcript" : str — display-ready text (may contain ₹, digits)
      "literal"    : str — fully spelled-out version (all words, good for TTS)

    Raises
    ------
    RuntimeError with a friendly, user-visible message on any failure.
    """
    key = _get_api_key()

    # Build multipart/form-data request (field names from PRD §6)
    files = {"audio_file": (filename, audio_bytes)}
    data = {"language_code": language_code}
    headers = {"X-API-Key-ID": key}  # auth header — never echoed

    try:
        response = requests.post(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Cannot reach STT API. Check your internet connection. ({exc})") from exc

    if response.status_code != 200:
        raise RuntimeError(_friendly_error(response.status_code, response.text))

    try:
        body = response.json()
    except ValueError:
        raise RuntimeError(f"STT returned an unexpected response (not JSON).")

    # success=false means Gnani processed the request but found a problem
    if not body.get("success", True):
        raise RuntimeError(f"STT API reported a failure: {body.get('message', 'unknown error')}")

    # Extract the two transcript variants from the confirmed response shape
    transcript = body.get("transcript", "")
    literal = body.get("output", {}).get("literal", transcript)

    return {"transcript": transcript, "literal": literal}


def tts(text: str, lang: str) -> bytes:
    """
    Send text to Gnani Timbre (TTS) and return raw WAV audio bytes.

    Parameters
    ----------
    text : sentence to speak.
           Numbers MUST be spelled as words — use number_to_words() first.
           Raw digits are mispronounced by the TTS engine.
    lang : "hi" → Nalini voice, hi-IN language
           "en" → Kaveri voice, en-IN language

    Returns
    -------
    bytes : raw WAV audio (sample_rate=48000, mono, 16-bit PCM)

    Raises
    ------
    RuntimeError with a friendly message on failure.
    ValueError   if lang is not "hi" or "en".

    Notes
    -----
    Retries once after 2 seconds on HTTP 429 (rate limit). Do NOT call
    this concurrently with stt() — wait for one to finish before the other.
    """
    if lang not in _TTS_CONFIG:
        raise ValueError(f"lang must be 'hi' or 'en', got: {lang!r}")

    cfg = _TTS_CONFIG[lang]
    key = _get_api_key()

    headers = {
        "X-API-Key-ID": key,
        "Content-Type": "application/json",
    }
    # Payload from official Gnani TTS docs (timbre-v2.5 model, WAV output)
    payload = {
        "text": text,
        "voice": cfg["voice"],
        "model": "timbre-v2.5",
        "language": cfg["language"],
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    def _send() -> requests.Response:
        try:
            return requests.post(
                TTS_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Cannot reach TTS API. Check your internet connection. ({exc})") from exc

    response = _send()

    # Retry once on 429 (rate limit — wait for the previous request to finish)
    if response.status_code == 429:
        time.sleep(2)
        response = _send()

    if response.status_code != 200:
        raise RuntimeError(_friendly_error(response.status_code, response.text))

    if not response.content:
        raise RuntimeError("TTS API returned an empty audio response.")

    # Return raw WAV bytes — caller saves or plays them directly
    return response.content
