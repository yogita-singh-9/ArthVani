"""
speech_text.py — Build the spoken read-back sentence for TTS.

Public API
----------
  build_readback(entry: dict, language: str) -> str

  entry    — the dict returned by parser.parse()
  language — "hi" or "en"

  Returns a natural-sounding sentence with ALL numbers as spoken words
  (never digits), ready to send to gnani.tts().

  Hindi:   Devanagari script
           e.g. "पचास किलो चावल, साठ रुपये किलो, कुल तीन हज़ार रुपये। सही है?"
  English: English words
           e.g. "fifty kilos of rice, sixty rupees per kilo,
                 total three thousand rupees. Is that correct?"

Why no digits?
  The Gnani TTS (Timbre) engine mispronounces raw digit strings.
  Numbers MUST be spelled out as words before sending.

Special fractions:
  Hindi:   1.5 → "डेढ़", 2.5 → "ढाई"  (more natural than "one point five")
  English: 1.5 → "one and a half", 2.5 → "two and a half"
"""

from num2words import num2words as _n2w

# ════════════════════════════════════════════════════════════
# PUBLIC: build_short_readback  (new, for shop / voice mode)
# build_readback is kept unchanged (used by existing tests and API)
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 1. HINDI: Devanagari number-to-words
#    num2words does NOT support Hindi, so we use a hand-built table.
# ════════════════════════════════════════════════════════════

# Individual words for 1–99 (index = value)
_DEVA_ONES: list[str] = [
    "",           # 0 — handled by name
    "एक",    "दो",      "तीन",    "चार",    "पाँच",   "छह",     "सात",   "आठ",    "नौ",
    "दस",    "ग्यारह", "बारह",   "तेरह",   "चौदह",   "पंद्रह", "सोलह",  "सत्रह", "अठारह", "उन्नीस",
    "बीस",   "इक्कीस", "बाईस",   "तेईस",   "चौबीस",  "पच्चीस", "छब्बीस","सत्ताईस","अट्ठाईस","उनतीस",
    "तीस",   "इकतीस",  "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस","सैंतीस","अड़तीस", "उनतालीस",
    "चालीस", "इकतालीस","बयालीस", "तैंतालीस","चौवालीस","पैंतालीस","छियालीस","सैंतालीस","अड़तालीस","उनचास",
    "पचास",  "इक्यावन","बावन",   "तिरपन",  "चौवन",   "पचपन",   "छप्पन", "सत्तावन","अट्ठावन","उनसठ",
    "साठ",   "इकसठ",   "बासठ",   "तिरसठ",  "चौंसठ",  "पैंसठ",  "छियासठ","सड़सठ", "अड़सठ",  "उनहत्तर",
    "सत्तर", "इकहत्तर","बहत्तर", "तिहत्तर","चौहत्तर","पचहत्तर","छिहत्तर","सतहत्तर","अठहत्तर","उन्नासी",
    "अस्सी", "इक्यासी","बयासी",  "तिरासी", "चौरासी", "पचासी",  "छियासी","सत्तासी","अट्ठासी","नवासी",
    "नब्बे", "इक्यानवे","बानवे", "तिरानवे","चौरानवे","पचानवे", "छियानवे","सत्तानवे","अट्ठानवे","निन्यानवे",
]

# Common fraction words (more natural than the decimal form)
_DEVA_FRACTIONS: dict[float, str] = {
    0.25: "पाव",
    0.5:  "आधा",
    0.75: "पौने",
    1.25: "सवा",
    1.5:  "डेढ़",
    2.5:  "ढाई",
}


def _int_to_deva(n: int) -> str:
    """Convert a non-negative integer to Devanagari words (up to 99 lakh)."""
    if n == 0:
        return "शून्य"
    parts: list[str] = []
    if n >= 100_000:
        parts.append(_int_to_deva(n // 100_000) + " लाख")
        n %= 100_000
    if n >= 1_000:
        parts.append(_int_to_deva(n // 1_000) + " हज़ार")
        n %= 1_000
    if n >= 100:
        parts.append(_DEVA_ONES[n // 100] + " सौ")
        n %= 100
    if n > 0:
        parts.append(_DEVA_ONES[n])
    return " ".join(parts)


def _num_to_deva(n: float) -> str:
    """
    Convert any number to Devanagari spoken words.
    Uses special fraction words for common half/quarter values.
    """
    # Special fractions (more natural for TTS)
    if n in _DEVA_FRACTIONS:
        return _DEVA_FRACTIONS[n]

    int_part = int(n)
    frac = round(n - int_part, 6)

    if frac == 0:
        return _int_to_deva(int_part)

    # Non-special fraction: "X point Y" approach as a fallback
    # (unusual values like 1.75 or 3.3)
    int_words  = _int_to_deva(int_part) if int_part else ""
    # Build fractional digits
    frac_str   = f"{frac:.6f}".lstrip("0.").rstrip("0")
    frac_words = " ".join(_DEVA_ONES[int(d)] for d in frac_str if d.isdigit())
    if int_words:
        return f"{int_words} पॉइंट {frac_words}"
    return f"शून्य पॉइंट {frac_words}"


# ════════════════════════════════════════════════════════════
# 2. ENGLISH: use num2words (en_IN)
# ════════════════════════════════════════════════════════════

_EN_FRACTIONS: dict[float, str] = {
    0.5:  "one and a half",
    1.5:  "one and a half",
    2.5:  "two and a half",
    0.25: "a quarter",
    0.75: "three quarters",
}


def _num_to_en(n: float) -> str:
    """Convert a number to English spoken words."""
    if n in _EN_FRACTIONS:
        return _EN_FRACTIONS[n]
    # num2words en_IN handles integers and simple floats
    if n == int(n):
        return _n2w(int(n), lang="en_IN")
    return _n2w(float(n), lang="en_IN")


# ════════════════════════════════════════════════════════════
# 3. UNIT DISPLAY WORDS
# ════════════════════════════════════════════════════════════

# How to say each canonical unit in Hindi and English TTS sentences
# Each entry has: "hi" (Devanagari), "en_qty" (quantity phrase), "en_rate" (rate phrase)
_UNIT_DISPLAY: dict[str, dict[str, str]] = {
    "kg":     {"hi": "किलो",   "en_qty": "kilos",   "en_rate": "kilo"},
    "g":      {"hi": "ग्राम",  "en_qty": "grams",   "en_rate": "gram"},
    "litre":  {"hi": "लीटर",   "en_qty": "litres",  "en_rate": "litre"},
    "dozen":  {"hi": "दर्जन",  "en_qty": "dozen",   "en_rate": "dozen"},
    "packet": {"hi": "पैकेट",  "en_qty": "packets", "en_rate": "packet"},
    "piece":  {"hi": "नग",     "en_qty": "pieces",  "en_rate": "piece"},
}


def _unit_word(unit: str, lang: str, rate: bool = False) -> str:
    """Return the spoken unit word for the given language.

    Parameters
    ----------
    unit  : canonical unit key (kg, g, litre, dozen, packet, piece)
    lang  : "hi" or "en"
    rate  : True when used in a "per <unit>" rate phrase (English only)
    """
    if unit not in _UNIT_DISPLAY:
        return unit   # unknown unit — pass through as-is
    entry = _UNIT_DISPLAY[unit]
    if lang == "hi":
        return entry["hi"]
    # English: use plural form for quantity, singular for rate
    return entry["en_rate"] if rate else entry["en_qty"]


# ════════════════════════════════════════════════════════════
# 4. MAIN FUNCTION
# ════════════════════════════════════════════════════════════

def build_readback(entry: dict, language: str) -> str:
    """
    Build the spoken read-back sentence from a parsed entry dict.

    Parameters
    ----------
    entry    : dict returned by parser.parse()
    language : "hi" or "en"

    Returns
    -------
    str — full sentence with numbers as words, ready for gnani.tts().

    Hindi example:
      "पचास किलो चावल, साठ रुपये किलो, कुल तीन हज़ार रुपये। सही है?"

    English example:
      "fifty kilos of rice, sixty rupees per kilo,
       total three thousand rupees. Is that correct?"
    """
    item  = entry.get("item")  or ""
    qty   = entry.get("quantity")
    unit  = entry.get("unit")  or ""
    price = entry.get("price")
    total = entry.get("total")

    # Choose number formatter
    num = _num_to_deva if language == "hi" else _num_to_en

    if language == "hi":
        uword = _unit_word(unit, "hi") if unit else ""
        return _build_hindi(item, qty, uword, price, total, num)
    else:
        uword_qty  = _unit_word(unit, "en", rate=False) if unit else ""  # "kilos"
        uword_rate = _unit_word(unit, "en", rate=True)  if unit else ""  # "kilo"
        return _build_english(item, qty, uword_qty, uword_rate, price, total, num)


def _build_hindi(item, qty, uword, price, total, num) -> str:
    """
    Build a Devanagari read-back sentence.

    Pattern: "<qty> <unit> <item>, <price> रुपये <unit>, कुल <total> रुपये। सही है?"
    Missing fields are skipped gracefully.
    """
    parts: list[str] = []

    # Quantity + unit + item
    if qty is not None and uword and item:
        parts.append(f"{num(qty)} {uword} {item}")
    elif qty is not None and item:
        parts.append(f"{num(qty)} {item}")
    elif item:
        parts.append(item)

    # Price per unit
    if price is not None:
        if uword:
            parts.append(f"{num(price)} रुपये {uword}")
        else:
            parts.append(f"{num(price)} रुपये")

    # Total
    if total is not None:
        parts.append(f"कुल {num(total)} रुपये")

    if not parts:
        return "विवरण उपलब्ध नहीं है। सही है?"

    sentence = "، ".join(parts)   # Devanagari comma pause
    # Clean up: use standard comma
    sentence = ", ".join(parts)
    return sentence + "। सही है?"


def _build_english(item, qty, uword_qty, uword_rate, price, total, num) -> str:
    """
    Build an English read-back sentence.

    Pattern: "<qty> kilos of <item>, <price> rupees per <unit>,
              total <total> rupees. Is that correct?"

    Parameters
    ----------
    uword_qty  : plural unit word for the quantity phrase ("kilos", "litres" …)
    uword_rate : singular unit word for the per-rate phrase ("kilo", "litre" …)
    """
    parts: list[str] = []

    # Quantity + unit + item
    if qty is not None and uword_qty and item:
        parts.append(f"{num(qty)} {uword_qty} of {item}")
    elif qty is not None and item:
        parts.append(f"{num(qty)} {item}")
    elif item:
        parts.append(item)

    # Price per unit
    if price is not None:
        if uword_rate:
            parts.append(f"{num(price)} rupees per {uword_rate}")
        else:
            parts.append(f"{num(price)} rupees")

    # Total
    if total is not None:
        parts.append(f"total {num(total)} rupees")

    if not parts:
        return "Entry details not available. Is that correct?"

    return ", ".join(parts) + ". Is that correct?"



# ════════════════════════════════════════════════════════════
# 5. SHORT READ-BACK (voice / shop mode)
#    Shorter than build_readback; omits unit price unless filled from memory
#    or unusual. Never adds "Is that correct?" — that is handled by voice UI.
# ════════════════════════════════════════════════════════════

def build_short_readback(
    entry: dict,
    language: str,
    filled_from_memory: bool = False,
) -> str:
    """
    Build a brief spoken confirmation sentence for voice / shop mode.

    Parameters
    ----------
    entry              : dict returned by parser.parse()
    language           : "hi" or "en"
    filled_from_memory : True if the price was filled from db.last_price()

    Returns
    -------
    str — short TTS sentence.

    Hindi examples:
      "पचास किलो चावल, तीन हज़ार रुपये"
      "पचास किलो चावल, सामान्य दाम, तीन हज़ार रुपये"  ← memory price

    English examples:
      "fifty kilos of rice, three thousand rupees"
      "fifty kilos of rice, usual price, three thousand rupees"  ← memory
    """
    item  = (entry.get("item")  or "").strip()
    qty   = entry.get("quantity")
    unit  = (entry.get("unit")  or "").strip()
    total = entry.get("total")

    num = _num_to_deva if language == "hi" else _num_to_en

    if language == "hi":
        uword = _unit_word(unit, "hi") if unit else ""
        parts: list[str] = []

        # Qty + unit + item
        if qty is not None and uword and item:
            parts.append(f"{num(qty)} {uword} {item}")
        elif qty is not None and item:
            parts.append(f"{num(qty)} {item}")
        elif item:
            parts.append(item)

        # Memory note
        if filled_from_memory:
            parts.append("सामान्य दाम")

        # Total
        if total is not None:
            parts.append(f"{num(total)} रुपये")

        return ", ".join(parts) if parts else "विवरण उपलब्ध नहीं।"

    else:
        uword_qty  = _unit_word(unit, "en", rate=False) if unit else ""
        parts_en: list[str] = []

        if qty is not None and uword_qty and item:
            parts_en.append(f"{num(qty)} {uword_qty} of {item}")
        elif qty is not None and item:
            parts_en.append(f"{num(qty)} {item}")
        elif item:
            parts_en.append(item)

        if filled_from_memory:
            parts_en.append("usual price")

        if total is not None:
            parts_en.append(f"{num(total)} rupees")

        return ", ".join(parts_en) if parts_en else "Entry details not available."


def build_query_response(query_type: str, data: dict, language: str) -> str:
    """
    Build a brief spoken answer for a voice query command.

    Parameters
    ----------
    query_type : "today_total" | "week_total" | "daily_summary" |
                 "last_entry" | "item_total"
    data       : dict from db.day_summary() / db.summary_stats() / etc.
    language   : "hi" or "en"

    Returns
    -------
    str — TTS-ready spoken sentence.
    """
    num = _num_to_deva if language == "hi" else _num_to_en

    if query_type == "today_total":
        sales = data.get("sales", 0)
        if language == "hi":
            return f"आज की बिक्री {num(sales)} रुपये।"
        return f"Today's sales are {num(sales)} rupees."

    if query_type == "week_total":
        sales = data.get("week", {}).get("sales", 0)
        if language == "hi":
            return f"इस हफ्ते की बिक्री {num(sales)} रुपये।"
        return f"This week's sales are {num(sales)} rupees."

    if query_type == "last_entry":
        recent = data.get("recent", [])
        if not recent:
            if language == "hi":
                return "कोई एंट्री नहीं मिली।"
            return "No entries found."
        e = recent[0]
        item  = e.get("item", "")
        qty   = e.get("quantity")
        unit  = e.get("unit", "")
        total = e.get("total")
        uword = _unit_word(unit, language) if unit else ""
        if language == "hi":
            parts = []
            if qty and uword and item:
                parts.append(f"{num(qty)} {uword} {item}")
            elif item:
                parts.append(item)
            if total:
                parts.append(f"{num(total)} रुपये")
            return ", ".join(parts) + "।" if parts else "एंट्री विवरण उपलब्ध नहीं।"
        else:
            parts = []
            uword_qty = _unit_word(unit, "en", rate=False) if unit else ""
            if qty and uword_qty and item:
                parts.append(f"{num(qty)} {uword_qty} of {item}")
            elif item:
                parts.append(item)
            if total:
                parts.append(f"{num(total)} rupees")
            return ", ".join(parts) + "." if parts else "Entry details not available."

    if query_type == "daily_summary":
        sales = data.get("sales", 0)
        purchases = data.get("purchases", 0)
        net = data.get("net", 0)
        count = data.get("count", 0)
        if language == "hi":
            return (
                f"आज {num(count)} एंट्री। "
                f"बिक्री {num(sales)} रुपये, "
                f"खरीद {num(purchases)} रुपये, "
                f"शुद्ध {num(net)} रुपये।"
            )
        return (
            f"Today {num(count)} entries. "
            f"Sales {num(sales)} rupees, "
            f"purchases {num(purchases)} rupees, "
            f"net {num(net)} rupees."
        )

    if query_type == "item_total":
        item = data.get("item", "")
        total = data.get("total", 0)
        if language == "hi":
            return f"आज {item} की बिक्री {num(total)} रुपये।"
        return f"Today's sales of {item} are {num(total)} rupees."

    return ""
