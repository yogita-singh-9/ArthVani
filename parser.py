"""
parser.py — Rule-based parser for voice-recorded shop entries.

Public API
----------
  parse(stt_result: dict, language: str) -> dict

  stt_result is the dict returned by gnani.stt():
    {"transcript": str, "literal": str}

  language is "hi" (Hindi) or "en" (English).

  Returns a dict:
    item        : str | None   — item name in the original script
    quantity    : float | None
    unit        : str | None   — normalised: kg, g, litre, dozen, packet, piece
    price       : float | None — per unit
    total       : float | None — quantity * price, computed in Python
    entry_type  : "sale" | "purchase"
    needs_review: bool         — True if any field is missing or ambiguous
    warnings    : list[str]    — short messages shown on the confirmation card

Design principles
-----------------
  Deterministic: same input → same output, no randomness, no model calls.
  Total is ALWAYS computed as round(quantity * price, 2). Never trusted from text.
  If a field cannot be found, it is None and needs_review is True.
  Arithmetic by number words is done via lookup tables — no eval().
"""

import re
from typing import Optional

# ════════════════════════════════════════════════════════════
# 1. NUMBER WORD DICTIONARIES
# ════════════════════════════════════════════════════════════

# Devanagari number words — from real Gnani STT literal output (hi-IN)
_DEVA: dict[str, float] = {
    "शून्य": 0,
    "एक": 1,   "दो": 2,   "तीन": 3,   "चार": 4,
    "पाँच": 5, "पांच": 5, "छह": 6,    "छः": 6,   "सात": 7,
    "आठ": 8,   "नौ": 9,
    "दस": 10,  "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14,
    "पंद्रह": 15, "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19,
    "बीस": 20,
    "इक्कीस": 21, "बाईस": 22,  "तेईस": 23,  "चौबीस": 24,
    "पच्चीस": 25, "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाईस": 28,
    "उनतीस": 29, "तीस": 30,
    "इकतीस": 31, "बत्तीस": 32, "तैंतीस": 33, "चौंतीस": 34,
    "पैंतीस": 35, "छत्तीस": 36, "सैंतीस": 37, "अड़तीस": 38,
    "उनतालीस": 39, "चालीस": 40,
    "इकतालीस": 41, "बयालीस": 42, "तैंतालीस": 43, "चौवालीस": 44,
    "पैंतालीस": 45, "छियालीस": 46, "सैंतालीस": 47, "अड़तालीस": 48,
    "उनचास": 49,  "पचास": 50,
    "इक्यावन": 51, "बावन": 52,  "तिरपन": 53, "चौवन": 54,
    "पचपन": 55,   "छप्पन": 56, "सत्तावन": 57, "अट्ठावन": 58,
    "उनसठ": 59,   "साठ": 60,
    "इकसठ": 61,  "बासठ": 62, "तिरसठ": 63, "चौंसठ": 64,
    "पैंसठ": 65, "छियासठ": 66, "सड़सठ": 67, "अड़सठ": 68,
    "उनहत्तर": 69, "सत्तर": 70,
    "इकहत्तर": 71, "बहत्तर": 72, "तिहत्तर": 73, "चौहत्तर": 74,
    "पचहत्तर": 75, "छिहत्तर": 76, "सतहत्तर": 77, "अठहत्तर": 78,
    "उन्नासी": 79, "अस्सी": 80,
    "इक्यासी": 81, "बयासी": 82, "तिरासी": 83, "चौरासी": 84,
    "पचासी": 85,  "छियासी": 86, "सत्तासी": 87, "अट्ठासी": 88,
    "नवासी": 89,  "नब्बे": 90,
    "इक्यानवे": 91, "बानवे": 92, "तिरानवे": 93, "चौरानवे": 94,
    "पचानवे": 95, "छियानवे": 96, "सत्तानवे": 97, "अट्ठानवे": 98,
    "निन्यानवे": 99,
    # Scale words
    "सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100_000,
    # Fraction words (each is a standalone value, not combined with scale)
    "डेढ": 1.5, "डेढ़": 1.5,
    "ढाई": 2.5, "ढाइ": 2.5,
    "सवा": 1.25,
    "आधा": 0.5, "आधी": 0.5,
    "पाव": 0.25, "पौने": 0.75,
}

# Roman-script Hindi (Hinglish) — spoken Hindi transcribed in Roman letters
_ROMAN_HI: dict[str, float] = {
    "shunya": 0,
    "ek": 1,    "do": 2,    "teen": 3,   "chaar": 4,
    "paanch": 5, "panch": 5, "chhah": 6,  "chheh": 6, "saat": 7,
    "aath": 8,  "nau": 9,
    "das": 10,  "gyaarah": 11, "baarah": 12, "terah": 13,  "chaudah": 14,
    "pandrah": 15, "solah": 16,  "satrah": 17, "atharah": 18, "unees": 19,
    "bees": 20,
    "ikkees": 21,     "baais": 22,      "teis": 23,       "chaubees": 24,
    "pachchees": 25,  "pachees": 25,    "chhabbees": 26,  "sattaees": 27,
    "atthaees": 28,   "unattees": 29,   "tees": 30,
    "ikattees": 31,   "battees": 32,    "taintees": 33,   "chautees": 34,
    "paintees": 35,   "chhattees": 36,  "saaintees": 37,  "artees": 38,
    "untaalees": 39,  "chaalees": 40,
    "iktalees": 41,   "bayaalees": 42,  "tentaalees": 43, "chauwalees": 44,
    "paintaalees": 45,"chhiyaalees": 46,"saintaalees": 47, "artaalees": 48,
    "unchaas": 49,    "pachaas": 50,
    "ikkyavan": 51,   "baavan": 52,     "tirpan": 53,     "chauvan": 54,
    "pachpan": 55,    "chhappan": 56,   "sattavan": 57,   "atthavan": 58,
    "unsath": 59,     "saath": 60,
    "iksath": 61,     "basath": 62,     "tirsath": 63,    "chausath": 64,
    "painsath": 65,   "chhiyasath": 66, "sarsath": 67,    "arsath": 68,
    "unhattar": 69,   "sattar": 70,
    "ikhattar": 71,   "bahattar": 72,   "tihattar": 73,   "chauhattar": 74,
    "pachhattar": 75, "chhihattar": 76, "sathattar": 77,  "athattar": 78,
    "unnasi": 79,     "assi": 80,
    "ikyaasi": 81,    "byaasi": 82,     "tiraasi": 83,    "chauraasi": 84,
    "pachaasi": 85,   "chhiyaasi": 86,  "sattaasi": 87,   "atthaasi": 88,
    "navaasi": 89,    "nabbe": 90,
    # Scale words
    "sau": 100, "hazaar": 1000, "lakh": 100_000,
    # Fraction words
    "dedh": 1.5,  "dhai": 2.5,  "dhaai": 2.5,
    "sava": 1.25, "aadha": 0.5, "adha": 0.5,
    "paav": 0.25, "paune": 0.75,
}

# English number words
_ENG: dict[str, float] = {
    "zero": 0,  "one": 1,   "two": 2,     "three": 3,  "four": 4,
    "five": 5,  "six": 6,   "seven": 7,   "eight": 8,  "nine": 9,
    "ten": 10,  "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20,  "thirty": 30,  "forty": 40,   "fifty": 50,
    "sixty": 60,   "seventy": 70, "eighty": 80,  "ninety": 90,
    # Scale words
    "hundred": 100, "thousand": 1000, "lakh": 100_000,
    # Fractions
    "half": 0.5, "quarter": 0.25,
}

# Combined lookup (order matters: Devanagari checked first by iteration)
_ALL_WORDS: dict[str, float] = {**_ENG, **_ROMAN_HI, **_DEVA}

# Scale words that multiply or add to the running total
_SCALES: dict[str, int] = {
    "sau": 100,   "hazaar": 1000,   "lakh": 100_000,
    "hundred": 100, "thousand": 1000,
    "सौ": 100,    "हज़ार": 1000,    "हजार": 1000,   "लाख": 100_000,
}

# Fraction words that stand alone (never combined with scale)
_FRACTIONS: set[str] = {
    "dedh", "dhai", "dhaai", "sava", "aadha", "adha", "paav", "paune",
    "डेढ", "डेढ़", "ढाई", "ढाइ", "सवा", "आधा", "आधी", "पाव", "पौने",
    "half", "quarter",
}

# ════════════════════════════════════════════════════════════
# 2. UNIT MAP
# ════════════════════════════════════════════════════════════

# Maps every spoken variant → canonical key used in the database
UNIT_MAP: dict[str, str] = {
    # kg
    "kilo": "kg",      "kilogram": "kg",    "kilograms": "kg",
    "kg": "kg",        "kgs": "kg",
    "किलो": "kg",      "किलोग्राम": "kg",
    # gram
    "gram": "g",       "grams": "g",        "gm": "g",   "gms": "g",
    "ग्राम": "g",
    # litre
    "litre": "litre",  "litres": "litre",   "liter": "litre",
    "liters": "litre", "ltr": "litre",
    "लीटर": "litre",
    # dozen
    "dozen": "dozen",  "darjan": "dozen",   "darzin": "dozen",
    "दर्जन": "dozen",
    # packet
    "packet": "packet", "packets": "packet", "pkt": "packet",
    "पैकेट": "packet",
    # piece / count
    "piece": "piece",  "pieces": "piece",   "pcs": "piece",
    "pc": "piece",     "nag": "piece",
    "नग": "piece",     "पीस": "piece",
}

# ════════════════════════════════════════════════════════════
# 3. CURRENCY & FILLER WORDS
# ════════════════════════════════════════════════════════════

# A token that IS a currency word signals that the number near it is the price
CURRENCY_WORDS: set[str] = {
    "rupaye", "rupee", "rupees", "rupaya", "rupaiye", "rs",
    "रुपये", "रुपए", "रुपया",
}

# Total marker words: a number right after one of these is a total, not a price
TOTAL_WORDS: set[str] = {"total", "kul", "कुल"}

# Filler words: stripped out when extracting the item name
FILLER_WORDS: set[str] = {
    *CURRENCY_WORDS,
    *TOTAL_WORDS,
    # Hindi grammatical particles
    "ka", "ki", "ke", "ko", "se", "me", "mein",
    "का", "की", "के", "को", "से", "में",
    # Context / location
    "aaj", "आज",
    # Action words (not the item)
    "becha", "bechi", "बेचा", "बेची",
    "kharida", "kharidi", "khareeda", "खरीदा", "खरीदी",
    "bought", "purchased", "purchase",
    # Price qualifiers
    "per", "each", "प्रति", "भाव", "rate", "पर",
    # Misc
    "hai", "hain", "aur",
}

# Entry-type keywords
_PURCHASE_WORDS: set[str] = {
    "kharida", "kharidi", "khareeda", "खरीदा", "खरीदी",
    "bought", "purchased", "purchase",
}

# ════════════════════════════════════════════════════════════
# 4. HELPER: NUMBER PARSING
# ════════════════════════════════════════════════════════════

def _word_to_num(tok: str) -> Optional[float]:
    """Return the numeric value of a single word token, or None."""
    return _ALL_WORDS.get(tok) if tok in _ALL_WORDS else _ALL_WORDS.get(tok.lower())


def _try_parse_num_at(tokens: list[str], i: int) -> Optional[tuple[float, int]]:
    """
    Try to parse a number (possibly multi-word) starting at tokens[i].
    Returns (value, next_index) or None.

    Handles:
      - Bare digits: "50", "60.5"
      - ₹-prefixed digits: "₹60"  (the ₹ is stripped; caller marks is_price)
      - Single word numbers: "pachaas", "साठ"
      - Scale composites: "teen hazaar" → 3000, "paanch sau" → 500
      - English tens+ones: "twenty five" → 25, "fifty five" → 55
      - Multi-level: "teen hazaar paanch sau" → 3500
    """
    raw = tokens[i]
    clean = raw.lstrip("₹").rstrip(".")   # strip ₹ prefix and trailing dot

    # ── Digit ────────────────────────────────────────────────────────────────
    try:
        val = float(clean)
        end = i + 1
        # A digit can be followed by a scale: "5 sau" = 500
        if end < len(tokens) and tokens[end] in _SCALES:
            scale = _SCALES[tokens[end]]
            if scale > val:          # only multiply up, not down
                val *= scale
                end += 1
                # One additive level: "5 hazaar 3 sau" = 5300
                sub = _try_parse_num_at(tokens, end)
                if sub and sub[0] < val:
                    val += sub[0]
                    end = sub[1]
        return (val, end)
    except ValueError:
        pass

    # ── Word number ──────────────────────────────────────────────────────────
    val = _word_to_num(clean)
    if val is None:
        return None

    end = i + 1

    # Fraction words stand alone — never combined with scales
    if clean in _FRACTIONS or clean.lower() in _FRACTIONS:
        return (val, end)

    # Scale word immediately after? (e.g. "teen hazaar")
    if end < len(tokens) and tokens[end] in _SCALES:
        scale = _SCALES[tokens[end]]
        if scale > val:
            val *= scale
            end += 1
            # Additive remainder: "teen hazaar paanch sau" → 3000 + 500
            sub = _try_parse_num_at(tokens, end)
            if sub and sub[0] < val:
                val += sub[0]
                end = sub[1]
        return (val, end)

    # English tens+ones compound: "twenty" + "five" = 25
    if val in (20, 30, 40, 50, 60, 70, 80, 90) and end < len(tokens):
        nxt = _word_to_num(tokens[end])
        if nxt is not None and 1 <= nxt <= 9:
            val += nxt
            end += 1

    return (val, end)


def _find_numbers(tokens: list[str]) -> list[dict]:
    """
    Scan tokens left-to-right and return a list of number spans.

    Each span is a dict:
      start      : int   — first token index
      end        : int   — first token index AFTER the span
      value      : float — numeric value
      is_price   : bool  — True if the raw token had a ₹ prefix
    """
    spans = []
    consumed: set[int] = set()
    i = 0
    while i < len(tokens):
        if i in consumed:
            i += 1
            continue
        tok = tokens[i]
        is_price = tok.startswith("₹")
        result = _try_parse_num_at(tokens, i)
        if result is not None:
            val, end = result
            spans.append({"start": i, "end": end, "value": val, "is_price": is_price})
            consumed.update(range(i, end))
            i = end
        else:
            i += 1
    return spans


# ════════════════════════════════════════════════════════════
# 5. HELPER: UNIT DETECTION
# ════════════════════════════════════════════════════════════

def _unit_at(tokens: list[str], idx: int) -> Optional[str]:
    """Return the canonical unit if tokens[idx] is a unit word, else None."""
    t = tokens[idx]
    return UNIT_MAP.get(t) or UNIT_MAP.get(t.lower())


def _find_units(tokens: list[str]) -> list[tuple[int, str]]:
    """Return [(index, canonical_unit)] for every unit token."""
    return [(i, u) for i, t in enumerate(tokens) if (u := _unit_at(tokens, i))]


# ════════════════════════════════════════════════════════════
# 6. HELPER: ITEM EXTRACTION
# ════════════════════════════════════════════════════════════

_RATE_QUALIFIERS: set[str] = {"per", "each", "प्रति", "भाव", "rate", "पर"}

def _extract_item(tokens: list[str], skip: set[int]) -> str:
    """
    Return the item name: tokens not in `skip` and not in FILLER_WORDS.
    Original script and word order are preserved.
    """
    skip_all = set(skip)
    # The token directly following a rate qualifier (e.g. '₹5 पर केला' -> 'केला') is the price divisor
    for i, t in enumerate(tokens):
        if (t in _RATE_QUALIFIERS or t.lower() in _RATE_QUALIFIERS) and i + 1 < len(tokens):
            skip_all.add(i + 1)

    parts = []
    for i, t in enumerate(tokens):
        if i in skip_all:
            continue
        t_low = t.lower().lstrip("₹")
        if t_low in FILLER_WORDS or t in FILLER_WORDS:
            continue
        if not t_low:
            continue
        parts.append(t)
    return " ".join(parts).strip()


# ════════════════════════════════════════════════════════════
# 7. MAIN PARSE FUNCTION
# ════════════════════════════════════════════════════════════

def parse(stt_result: dict, language: str) -> dict:
    """
    Extract item, quantity, unit, price from a Gnani STT result dict.

    Parameters
    ----------
    stt_result : {"transcript": str, "literal": str}
                 as returned by gnani.stt()
    language   : "hi" or "en"

    Returns
    -------
    dict:
      item        : str | None
      quantity    : float | None
      unit        : str | None   (normalised: kg, g, litre, dozen, packet, piece)
      price       : float | None (per unit)
      total       : float | None (computed as round(qty * price, 2))
      entry_type  : "sale" | "purchase"
      needs_review: bool
      warnings    : list[str]
    """
    transcript = (stt_result.get("transcript") or "").strip()
    literal    = (stt_result.get("literal")    or "").strip()

    warnings: list[str] = []

    # ── Choose working text ───────────────────────────────────────────────────
    # Prefer transcript (has digits and ₹). Fall back to literal only if
    # transcript is empty or contains no digit characters at all.
    if re.search(r"\d", transcript):
        text = transcript
    elif literal:
        text = literal
        if transcript:
            warnings.append("Used word-form (literal) because transcript had no digits.")
    else:
        text = transcript  # may still have word numbers in Devanagari

    if not text:
        return _result(None, None, None, None, "sale", True,
                       ["No transcript received. Please speak again."])

    # ── Normalize ─────────────────────────────────────────────────────────────
    # Strip punctuation (keep ₹) and collapse whitespace
    text = re.sub(r"[,।|.!?;:'\"()]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()

    # ── Entry type ────────────────────────────────────────────────────────────
    entry_type = "sale"
    for t in tokens:
        if t in _PURCHASE_WORDS or t.lower() in _PURCHASE_WORDS:
            entry_type = "purchase"
            break

    # ── Find all numbers ──────────────────────────────────────────────────────
    num_spans = _find_numbers(tokens)
    num_indices: set[int] = set()
    for sp in num_spans:
        num_indices.update(range(sp["start"], sp["end"]))

    # ── Find all units ────────────────────────────────────────────────────────
    unit_positions = _find_units(tokens)   # [(idx, unit)]
    unit_indices   = {idx for idx, _ in unit_positions}

    # ── Find currency-word positions ──────────────────────────────────────────
    curr_indices: set[int] = set()
    for i, t in enumerate(tokens):
        if t in CURRENCY_WORDS or t.lower() in CURRENCY_WORDS:
            curr_indices.add(i)

    # ── Find total-word positions ─────────────────────────────────────────────
    total_indices: set[int] = set()
    for i, t in enumerate(tokens):
        if t in TOTAL_WORDS or t.lower() in TOTAL_WORDS:
            total_indices.add(i)

    # ── Assign numbers to quantity and price ─────────────────────────────────
    #
    # Key rule (from spec): Quantity = FIRST number. Price = the NEXT number.
    # This makes "50 kilo rice 60 kilo per kg" work: qty=50 kg, price=60.
    #
    # Exceptions handled in order:
    #   a) ₹-prefixed number → price (strong signal)
    #   b) Number right after a currency word → price
    #   c) Number right after a total word → it's the total (not price);
    #      derive price = total / qty
    #   d) Otherwise: first number = qty, second number = price

    qty_span    = None
    price_span  = None
    total_span  = None       # the span whose value became total_spoken
    total_spoken = None      # a total explicitly said in the sentence

    for sp in num_spans:
        # Rule (a): ₹ prefix → price
        if sp["is_price"] and price_span is None:
            price_span = sp
            continue

        # Rule (c): preceded by total keyword
        prev = sp["start"] - 1
        if prev >= 0 and prev in total_indices:
            total_spoken = sp["value"]
            total_span   = sp          # remember so fallback won't reuse it
            continue

        # Rule (b): followed or preceded by a currency word
        after  = sp["end"]
        before = sp["start"] - 1
        near_currency = (
            (after < len(tokens) and after in curr_indices) or
            (before >= 0 and before in curr_indices)
        )
        if near_currency and price_span is None:
            price_span = sp
            continue

        # Default: first unassigned → qty, second → price
        if qty_span is None:
            qty_span = sp
        elif price_span is None:
            price_span = sp
        # (extra numbers are ignored; they go into the item candidates and
        #  will be stripped out there)

    # ── If no price found yet but we have ≥2 numbers, use positional rule ────
    # First number = qty, second number = price (handles the STT mis-hear case
    # "50 kilo rice 60 kilo per kg" where "60" is the second number).
    # Always skip total_span — that number is already accounted for.
    _used = {id(s) for s in (qty_span, price_span, total_span) if s is not None}

    if qty_span is None and price_span is None and len(num_spans) >= 2:
        candidates = [s for s in num_spans if id(s) not in _used]
        if len(candidates) >= 2:
            qty_span   = candidates[0]
            price_span = candidates[1]
        elif len(candidates) == 1:
            qty_span = candidates[0]
    elif qty_span is None and price_span is not None:
        # Only a price found — first remaining span is qty
        for sp in num_spans:
            if id(sp) not in _used:
                qty_span = sp
                break
    elif qty_span is not None and price_span is None and total_span is None:
        # Only qty found so far, and no total word captured — next span is price
        for sp in num_spans:
            if id(sp) not in _used:
                price_span = sp
                break

    qty_val   = qty_span["value"]   if qty_span   else None
    price_val = price_span["value"] if price_span else None

    # ── Derive price from total if that was given instead ────────────────────
    if total_spoken is not None and qty_val and price_val is None:
        price_val = round(total_spoken / qty_val, 4)
        warnings.append("Price derived from spoken total ÷ quantity.")

    # ── Assign unit ───────────────────────────────────────────────────────────
    unit = None
    if unit_positions:
        # Find the unit token closest (adjacent) to the qty span
        if qty_span is not None:
            best = None
            best_dist = 999
            for (ui, un) in unit_positions:
                # Prefer unit immediately after qty, then before
                dist = abs(ui - qty_span["end"] + 1)
                if dist < best_dist:
                    best_dist = dist
                    best = un
            unit = best
        else:
            unit = unit_positions[0][1]  # just take the first one

    # If a count-type entry has no unit, default to piece (PRD rule)
    if unit is None and qty_val is not None and price_val is not None:
        unit = "piece"
        warnings.append("No unit heard — assumed 'piece'.")

    # ── Compute total ─────────────────────────────────────────────────────────
    total = None
    if qty_val is not None and price_val is not None:
        total = round(qty_val * price_val, 2)

    # ── Extract item ──────────────────────────────────────────────────────────
    skip = num_indices | unit_indices | curr_indices | total_indices
    # Also skip tokens that are filler words
    item_text = _extract_item(tokens, skip)
    item = item_text if item_text else None

    # ── Determine needs_review ────────────────────────────────────────────────
    missing = []
    if item     is None: missing.append("item")
    if qty_val  is None: missing.append("quantity")
    if price_val is None: missing.append("price")
    if missing:
        warnings.append(f"Could not detect: {', '.join(missing)}. Please fill in.")

    needs_review = bool(missing) or bool(warnings)

    return _result(item, qty_val, unit, price_val, entry_type, needs_review, warnings,
                   total=total)


# ════════════════════════════════════════════════════════════
# 8. RESULT BUILDER
# ════════════════════════════════════════════════════════════

def _result(item, quantity, unit, price, entry_type,
            needs_review, warnings, total=None) -> dict:
    """Assemble the standard result dict. Total is always computed here."""
    if total is None and quantity is not None and price is not None:
        total = round(quantity * price, 2)
    return {
        "item":         item,
        "quantity":     quantity,
        "unit":         unit,
        "price":        price,
        "total":        total,
        "entry_type":   entry_type,
        "needs_review": needs_review,
        "warnings":     warnings,
    }
