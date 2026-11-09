"""
voice_commands.py — Rule-based voice command classifier for ArthVani.

Public API
----------
  classify(text, language) -> dict
      Returns a structured intent object. No side effects.

Intent shapes
-------------
  {"intent": "yes"}
  {"intent": "no"}
  {"intent": "undo"}
  {"intent": "pause"}
  {"intent": "query", "query_type": "today_total" | "item_total" | "last_entry"
                                   | "week_total" | "daily_summary",
                      "item": str | None}
  {"intent": "entry"}   -- utterance looks like a ledger entry (must NOT be a command)
  {"intent": "unknown"}

Design
------
  - Pure functions; no imports from db, gnani, parser, or the network.
  - Accepts Devanagari, Roman (transliterated), and mixed Hinglish.
  - Entry heuristic: if the text contains a price pattern AND a quantity
    pattern it is classified as "entry" first, before any command check.
  - All keyword sets normalise to lower-case with stripped diacritics for
    Roman text; Devanagari is matched exactly.
"""

from __future__ import annotations

import re
import unicodedata


# ════════════════════════════════════════════════════════════
# 1. NORMALISATION
# ════════════════════════════════════════════════════════════

def _normalise(text: str) -> str:
    """Lowercase; strip leading/trailing whitespace; normalise unicode."""
    return unicodedata.normalize("NFC", text.strip().lower())


# ════════════════════════════════════════════════════════════
# 2. ENTRY HEURISTIC (runs FIRST — an entry is never a command)
# ════════════════════════════════════════════════════════════

# Quantity patterns: digits (optionally with decimal / fraction word)
_QTY_PATTERN = re.compile(
    r"""
    \b(
        \d+(\.\d+)?           # number like 50, 2.5
      | \d+\s*(?:               # number with fraction word
            (?:aadha|half|डेढ़|ढाई|sava|डेढ)
        )
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Price patterns: rupee keyword near a number
_PRICE_PATTERN = re.compile(
    r"""
    \b(
        (?:rupee|rupees|rupaiye|rupaye|rupe|rs\.?|₹)\s*\d+
      | \d+\s*(?:rupee|rupees|rupaiye|rupaye|rupe|rs\.?|₹)
      | \d+\s*(?:रुपये?|रु\.?|टका|का\s*भाव)
      | (?:रुपये?|रु\.?)\s*\d+
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _looks_like_entry(text: str) -> bool:
    """Return True if text has both a quantity and a price pattern."""
    return bool(_QTY_PATTERN.search(text)) and bool(_PRICE_PATTERN.search(text))


# ════════════════════════════════════════════════════════════
# 3. KEYWORD SETS
# ════════════════════════════════════════════════════════════

_YES_TOKENS = {
    # Devanagari
    "हाँ", "हां", "हाँ", "सही है", "ठीक है", "जी",
    "बिल्कुल", "अच्छा", "चलो", "सही",
    # Roman / Hinglish — keep only phrases 3+ chars that won't collide with subwords
    "haan", "han", "hah", "sahi hai", "sahi he", "theek hai", "theek he",
    "thik hai", "thik he", "ji", "ok", "okay", "yes", "correct", "right",
    "bilkul", "acha", "achha",
    # NOTE: "ha" and "na" deliberately excluded — too short, trigger false positives
    #       inside longer words like "hatao", "hafte", "nahi"
}

_NO_TOKENS = {
    # Devanagari
    "नहीं", "नही", "गलत", "रुको", "रुक", "कैंसिल",
    "बंद", "मत", "नहीं सही",
    # Roman / Hinglish — "na" excluded (too short, substring collisions)
    "nahi", "nahin", "galat", "ruko", "ruk", "cancel",
    "no", "wrong", "mat", "band karo", "nope",
}

_UNDO_TOKENS = {
    # Devanagari
    "पिछली एंट्री हटाओ", "वापस", "पिछला हटाओ", "अनडू",
    # Roman / Hinglish
    "pichhli entry hatao", "pichli entry hatao", "last delete karo",
    "undo", "wapas", "hatao", "last entry hatao", "last entry delete karo",
    "pichli hatao",
}

_PAUSE_TOKENS = {
    # Devanagari
    "बंद करो", "रुको", "रोको", "बंद",
    # Roman / Hinglish
    "band karo", "roko", "pause", "stop listening", "stop", "band",
    "rok do", "rukjao",
}

_TODAY_TOTAL_TOKENS = {
    # Devanagari
    "आज का टोटल", "आज का कुल", "आज कितना हुआ", "आज का हिसाब",
    "आज का टोटल बताओ", "आज कितना बिका",
    # Roman / Hinglish
    "aaj ka total", "aaj ka kul", "aaj kitna hua", "today's total",
    "today total", "aaj total", "aaj ka hisaab", "aaj kitna bika",
}

_DAILY_SUMMARY_TOKENS = {
    # Devanagari
    "दिन का हिसाब", "आज का सारांश", "सारांश", "दिन का सारांश",
    "आज की रिपोर्ट",
    # Roman / Hinglish
    "din ka hisaab", "din ka hisab", "today's summary", "todays summary",
    "aaj ka summary", "daily summary", "summary", "aaj ki report",
}

_LAST_ENTRY_TOKENS = {
    # Devanagari
    "आखिरी एंट्री", "पिछली एंट्री", "आखिरी क्या था",
    # Roman / Hinglish
    "last entry", "pichli entry", "aakhri entry", "last entry kya tha",
    "last kya tha",
}

_WEEK_TOTAL_TOKENS = {
    # Devanagari
    "इस हफ्ते का टोटल", "इस सप्ताह का", "हफ्ते का टोटल",
    # Roman / Hinglish
    "week total", "is hafte ka total", "weekly total", "hafte ka total",
    "is week ka total",
}

# Item total patterns — "aaj kitna <item> bika" / "how much <item> today"
# NOTE: The second Hindi pattern requires "कितना/कितनी" explicitly to avoid
# matching "आज का टोटल" (which should be today_total, not item_total).
_ITEM_TOTAL_RE = re.compile(
    r"""
    (?:
        # Hindi: "आज कितना/कितनी/कितने <item> बिका/हुआ" (item in group 1)
        आज\s+(?:कितना|कितनी|कितने)\s+(.+?)\s+(?:बिका|बिकी|बिके|हुआ|हुई|हुए)
        # Hindi: "<item> का/की आज कितना/कितनी/कुल" — requires कितना/कितनी, NOT just टोटल
      | (.+?)\s+(?:का|की|के)\s+(?:आज\s+)?(?:कितना|कितनी)
        # English patterns
      | how\s+much\s+(.+?)\s+today
      | (?:today[''s]?\s+)?(.+?)\s+total\s+today
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ════════════════════════════════════════════════════════════
# 4. MATCHING HELPERS
# ════════════════════════════════════════════════════════════

def _exact_match(text: str, token_set: set[str]) -> bool:
    """Return True if text exactly equals any token (after normalisation)."""
    n = _normalise(text)
    return n in {_normalise(t) for t in token_set}


def _contains_match(text: str, token_set: set[str]) -> bool:
    """Return True if any token is a substring of text (after normalisation)."""
    n = _normalise(text)
    return any(_normalise(t) in n for t in token_set)


def _first_group(match: re.Match | None) -> str | None:
    """Return first non-None group from a match, stripped."""
    if match is None:
        return None
    for g in match.groups():
        if g:
            return g.strip()
    return None


# ════════════════════════════════════════════════════════════
# 5. MAIN CLASSIFIER
# ════════════════════════════════════════════════════════════

def classify(text: str, language: str = "hi") -> dict:
    """
    Classify a voice utterance into an intent dict.

    Parameters
    ----------
    text     : raw STT transcript
    language : "hi" or "en" (currently informational; classification works
               in both languages in either mode)

    Returns
    -------
    dict with at minimum {"intent": str}.
    For "query" intents, also {"query_type": str, "item": str | None}.
    """
    if not text or not text.strip():
        return {"intent": "unknown"}

    # ── Entry check (MUST run before command checks) ──────────────────────────
    if _looks_like_entry(text):
        return {"intent": "entry"}

    t = _normalise(text)

    # ── yes ───────────────────────────────────────────────────────────────────
    # Only match if the ENTIRE text is a yes phrase (exact) OR the text is
    # short (≤ 4 words) AND a yes token is a full-word match (not a substring
    # buried in longer words like "hatao" containing "ha").
    if _exact_match(t, _YES_TOKENS):
        return {"intent": "yes"}
    if len(t.split()) <= 3 and _contains_match(t, _YES_TOKENS):
        # Extra guard: reject if any word in t has a yes-token as a prefix
        # but is longer (e.g. "hatao" contains "ha" but len("hatao") > len("ha"))
        words = t.split()
        for token in _YES_TOKENS:
            nt = _normalise(token)
            # Only fire if the token appears as a complete word
            if re.search(r'(?<![^\s])' + re.escape(nt) + r'(?![^\s])', t):
                return {"intent": "yes"}

    # ── undo ─────────────────────────────────────────────────────────────────
    if _contains_match(t, _UNDO_TOKENS):
        return {"intent": "undo"}

    # ── pause ─────────────────────────────────────────────────────────────────
    if _contains_match(t, _PAUSE_TOKENS):
        return {"intent": "pause"}

    # ── no / cancel ───────────────────────────────────────────────────────────
    if _exact_match(t, _NO_TOKENS):
        return {"intent": "no"}
    if len(t.split()) <= 3 and _contains_match(t, _NO_TOKENS):
        words = t.split()
        for token in _NO_TOKENS:
            nt = _normalise(token)
            if re.search(r'(?<![^\s])' + re.escape(nt) + r'(?![^\s])', t):
                return {"intent": "no"}

    # ── daily summary ─────────────────────────────────────────────────────────
    if _contains_match(t, _DAILY_SUMMARY_TOKENS):
        return {"intent": "query", "query_type": "daily_summary", "item": None}

    # ── today total (before item_total so "आज का टोटल" doesn't match item) ───
    if _contains_match(t, _TODAY_TOTAL_TOKENS):
        return {"intent": "query", "query_type": "today_total", "item": None}

    # ── week total ────────────────────────────────────────────────────────────
    if _contains_match(t, _WEEK_TOTAL_TOKENS):
        return {"intent": "query", "query_type": "week_total", "item": None}

    # ── item total (after specific totals so "aaj ka total" etc. don't collide)
    m = _ITEM_TOTAL_RE.search(text)
    if m:
        item = _first_group(m)
        if item:
            return {"intent": "query", "query_type": "item_total", "item": item}

    # ── last entry ────────────────────────────────────────────────────────────
    if _contains_match(t, _LAST_ENTRY_TOKENS):
        return {"intent": "query", "query_type": "last_entry", "item": None}

    return {"intent": "unknown"}


# ════════════════════════════════════════════════════════════
# 6. CONFIRMATION POLICY
# ════════════════════════════════════════════════════════════

def requires_explicit_confirmation(
    parsed: dict,
    mode: str = "quick",
    high_value_threshold: float = 10_000.0,
    price_spike_ratio: float = 1.5,
    last_known_price: float | None = None,
) -> bool:
    """
    Return True if this entry ALWAYS requires an explicit yes regardless of mode.

    Conditions (any one → True):
      1. needs_review is set
      2. Any required field (item, quantity, price) is missing
      3. Total exceeds high_value_threshold
      4. Price deviates > price_spike_ratio from last known price
    """
    if parsed.get("needs_review"):
        return True

    missing = (
        not parsed.get("item")
        or parsed.get("quantity") is None
        or parsed.get("price") is None
    )
    if missing:
        return True

    total = parsed.get("total")
    if total is not None and float(total) > high_value_threshold:
        return True

    if last_known_price is not None and parsed.get("price") is not None:
        price = float(parsed["price"])
        ref   = float(last_known_price)
        if ref > 0 and abs(price - ref) / ref > (price_spike_ratio - 1.0):
            return True

    return False


def confirmation_timeout(mode: str, explicit_required: bool) -> int:
    """
    Return the auto-save / await timeout in seconds.

    Quick mode + no explicit required → 3 s auto-save
    Quick mode + explicit required    → 8 s await (treat like strict)
    Strict mode                       → 8 s await
    """
    if mode == "quick" and not explicit_required:
        return 3
    return 8

