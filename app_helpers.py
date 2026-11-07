"""
app_helpers.py — Pure helper functions used by app.py.

Extracted here so tests/test_app_logic.py can import them without
triggering Streamlit's global side-effects (st.set_page_config, etc.).

No Streamlit, no API calls, no I/O in this module.
"""

import hashlib


def audio_hash(audio_bytes: bytes) -> str:
    """SHA-256 hex digest of raw audio bytes; used for de-duplication."""
    return hashlib.sha256(audio_bytes).hexdigest()


def compute_total(quantity: float | None, price: float | None) -> float | None:
    """Return round(quantity * price, 2), or None if either argument is missing."""
    if quantity is None or price is None:
        return None
    return round(float(quantity) * float(price), 2)


def build_entry_dict(item, quantity, unit, price, entry_type) -> dict:
    """
    Assemble an entry dict with the same shape as parser.parse() output.
    total is computed here (never trusted from the caller).
    """
    return {
        "item":       item,
        "quantity":   quantity,
        "unit":       unit,
        "price":      price,
        "total":      compute_total(quantity, price),
        "entry_type": entry_type,
    }


def readback_cache_key(entry: dict, lang: str) -> str:
    """
    A stable string key for caching TTS audio by entry content + language.
    Two entries with the same item/qty/unit/price in the same language
    get the same key (and therefore the same cached audio).
    """
    return (
        f"{lang}|{entry.get('item')}|{entry.get('quantity')}"
        f"|{entry.get('unit')}|{entry.get('price')}"
    )

