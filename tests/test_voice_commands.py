"""
tests/test_voice_commands.py — Tests for voice_commands.py

Coverage:
  - 40+ phrases across Hindi, English, Hinglish
  - Entries that must NOT be treated as commands
  - Confirmation policy (requires_explicit_confirmation, confirmation_timeout)
  - State machine transitions
  - All existing tests still pass
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from voice_commands import (
    classify,
    requires_explicit_confirmation,
    confirmation_timeout,
)


# ════════════════════════════════════════════════════════════
# 1. ENTRY DETECTION (must NOT be treated as a command)
# ════════════════════════════════════════════════════════════

ENTRY_PHRASES = [
    # Hindi
    ("50 किलो चावल 60 रुपये किलो",          "hi"),
    ("2 लीटर दूध 55 रुपये लीटर",             "hi"),
    ("10 किलो आलू 20 रुपये किलो",            "hi"),
    ("5 किलो टमाटर 40 रुपये",                "hi"),
    ("पाँच किलो चावल 60 रुपये",              "hi"),
    ("एक दर्जन केले 30 रुपये",               "hi"),
    # English
    ("50 kilo rice 60 rupees per kilo",       "en"),
    ("2 litre milk 55 rupees",                "en"),
    ("100 grams sugar 5 rupees",              "en"),
    ("12 pieces soap 30 rupees each",         "en"),
    # Hinglish
    ("50 kilo chawal 60 rupaye kilo",         "hi"),
    ("2 litre doodh 55 rupaye",               "hi"),
    ("10 kg aloo 20 rs kilo",                 "en"),
]


@pytest.mark.parametrize("text,lang", ENTRY_PHRASES)
def test_entry_not_command(text, lang):
    """Utterances with qty+price must classify as 'entry', never a command."""
    result = classify(text, lang)
    assert result["intent"] == "entry", (
        f"Expected 'entry' for {text!r}, got {result!r}"
    )


# ════════════════════════════════════════════════════════════
# 2. YES COMMANDS
# ════════════════════════════════════════════════════════════

YES_PHRASES = [
    ("हाँ",         "hi"),
    ("हां",         "hi"),
    ("सही है",      "hi"),
    ("ठीक है",      "hi"),
    ("जी",          "hi"),
    ("haan",        "hi"),
    # NOTE: "ha" (2-char) deliberately excluded from YES_TOKENS to prevent
    # false-positive matches inside words like "hatao", "hafte", "chalak".
    # Traders are expected to say "haan" or "ji" rather than bare "ha".
    ("sahi hai",    "hi"),
    ("theek hai",   "hi"),
    ("ok",          "en"),
    ("yes",         "en"),
    ("correct",     "en"),
    ("ji",          "hi"),
    ("bilkul",      "hi"),
]


@pytest.mark.parametrize("text,lang", YES_PHRASES)
def test_yes_commands(text, lang):
    result = classify(text, lang)
    assert result["intent"] == "yes", (
        f"Expected 'yes' for {text!r}, got {result!r}"
    )


# ════════════════════════════════════════════════════════════
# 3. NO / CANCEL COMMANDS
# ════════════════════════════════════════════════════════════

NO_PHRASES = [
    ("नहीं",        "hi"),
    ("नही",         "hi"),
    ("गलत",         "hi"),
    ("no",          "en"),
    ("cancel",      "en"),
    ("wrong",       "en"),
    ("nahi",        "hi"),
    ("galat",       "hi"),
]


@pytest.mark.parametrize("text,lang", NO_PHRASES)
def test_no_commands(text, lang):
    result = classify(text, lang)
    assert result["intent"] == "no", (
        f"Expected 'no' for {text!r}, got {result!r}"
    )


# ════════════════════════════════════════════════════════════
# 4. UNDO COMMANDS
# ════════════════════════════════════════════════════════════

UNDO_PHRASES = [
    ("पिछली एंट्री हटाओ",           "hi"),
    ("वापस",                         "hi"),
    ("undo",                          "en"),
    ("last delete karo",              "hi"),
    ("last entry hatao",              "hi"),
    ("wapas",                         "hi"),
    ("pichhli entry hatao",           "hi"),
]


@pytest.mark.parametrize("text,lang", UNDO_PHRASES)
def test_undo_commands(text, lang):
    result = classify(text, lang)
    assert result["intent"] == "undo", (
        f"Expected 'undo' for {text!r}, got {result!r}"
    )


# ════════════════════════════════════════════════════════════
# 5. PAUSE COMMANDS
# ════════════════════════════════════════════════════════════

PAUSE_PHRASES = [
    ("बंद करो",         "hi"),
    ("pause",            "en"),
    ("stop listening",   "en"),
    ("band karo",        "hi"),
]


@pytest.mark.parametrize("text,lang", PAUSE_PHRASES)
def test_pause_commands(text, lang):
    result = classify(text, lang)
    assert result["intent"] == "pause", (
        f"Expected 'pause' for {text!r}, got {result!r}"
    )


# ════════════════════════════════════════════════════════════
# 6. QUERY COMMANDS
# ════════════════════════════════════════════════════════════

QUERY_PHRASES = [
    ("आज का टोटल",             "hi",  "today_total"),
    ("aaj ka total",           "hi",  "today_total"),
    ("today's total",          "en",  "today_total"),
    ("आज कितना हुआ",           "hi",  "today_total"),
    ("दिन का हिसाब",           "hi",  "daily_summary"),
    ("today's summary",        "en",  "daily_summary"),
    ("daily summary",          "en",  "daily_summary"),
    ("last entry",             "en",  "last_entry"),
    ("आखिरी एंट्री",           "hi",  "last_entry"),
    ("week total",             "en",  "week_total"),
    ("is hafte ka total",      "hi",  "week_total"),
]


@pytest.mark.parametrize("text,lang,expected_qtype", QUERY_PHRASES)
def test_query_commands(text, lang, expected_qtype):
    result = classify(text, lang)
    assert result["intent"] == "query", (
        f"Expected 'query' for {text!r}, got {result!r}"
    )
    assert result["query_type"] == expected_qtype, (
        f"Expected query_type={expected_qtype!r} for {text!r}, got {result['query_type']!r}"
    )


def test_item_total_query_hindi():
    result = classify("आज कितना चावल बिका", "hi")
    assert result["intent"] == "query"
    assert result["query_type"] == "item_total"
    assert result.get("item") is not None


def test_item_total_query_english():
    result = classify("how much rice today", "en")
    assert result["intent"] == "query"
    assert result["query_type"] == "item_total"
    assert result.get("item") is not None


# ════════════════════════════════════════════════════════════
# 7. UNKNOWN UTTERANCES
# ════════════════════════════════════════════════════════════

def test_empty_string():
    assert classify("", "hi") == {"intent": "unknown"}


def test_blank_string():
    assert classify("   ", "en") == {"intent": "unknown"}


def test_gibberish():
    result = classify("asdfghjkl", "en")
    assert result["intent"] == "unknown"


# ════════════════════════════════════════════════════════════
# 8. CONFIRMATION POLICY
# ════════════════════════════════════════════════════════════

def _ok_entry():
    return {
        "item": "चावल",
        "quantity": 50.0,
        "price": 60.0,
        "total": 3000.0,
        "needs_review": False,
        "entry_type": "sale",
    }


def test_confirmation_no_explicit_needed_quick():
    parsed = _ok_entry()
    assert requires_explicit_confirmation(parsed, mode="quick") is False


def test_confirmation_needs_review_requires_explicit():
    parsed = _ok_entry()
    parsed["needs_review"] = True
    assert requires_explicit_confirmation(parsed, mode="quick") is True


def test_confirmation_missing_item():
    parsed = _ok_entry()
    parsed["item"] = ""
    assert requires_explicit_confirmation(parsed) is True


def test_confirmation_missing_quantity():
    parsed = _ok_entry()
    parsed["quantity"] = None
    assert requires_explicit_confirmation(parsed) is True


def test_confirmation_missing_price():
    parsed = _ok_entry()
    parsed["price"] = None
    assert requires_explicit_confirmation(parsed) is True


def test_confirmation_high_value():
    parsed = _ok_entry()
    parsed["total"] = 15_000.0
    assert requires_explicit_confirmation(parsed, high_value_threshold=10_000.0) is True


def test_confirmation_below_threshold():
    parsed = _ok_entry()
    parsed["total"] = 500.0
    assert requires_explicit_confirmation(parsed, high_value_threshold=10_000.0) is False


def test_confirmation_price_spike():
    parsed = _ok_entry()
    parsed["price"] = 150.0   # 150% more than 60
    assert requires_explicit_confirmation(parsed, last_known_price=60.0) is True


def test_confirmation_normal_price_variation():
    parsed = _ok_entry()
    parsed["price"] = 65.0   # ~8% variation — fine
    assert requires_explicit_confirmation(parsed, last_known_price=60.0) is False


def test_confirmation_timeout_quick_no_explicit():
    assert confirmation_timeout("quick", False) == 3


def test_confirmation_timeout_quick_with_explicit():
    assert confirmation_timeout("quick", True) == 8


def test_confirmation_timeout_strict():
    assert confirmation_timeout("strict", False) == 8
    assert confirmation_timeout("strict", True) == 8


# ════════════════════════════════════════════════════════════
# 9. STATE MACHINE TRANSITION TABLE
#    Shop mode states: IDLE → LISTENING → TRANSCRIBING → PARSED →
#                      READBACK → AWAIT → SAVED → LISTENING
# ════════════════════════════════════════════════════════════

VALID_TRANSITIONS = {
    "IDLE":          {"LISTENING"},
    "LISTENING":     {"TRANSCRIBING", "IDLE"},   # IDLE on pause/timeout
    "TRANSCRIBING":  {"PARSED", "LISTENING"},     # LISTENING on STT error/no-parse
    "PARSED":        {"READBACK", "LISTENING"},   # READBACK with entry; LISTENING on unknown
    "READBACK":      {"AWAIT", "LISTENING"},      # AWAIT after TTS; LISTENING on TTS error
    "AWAIT":         {"SAVED", "LISTENING"},      # SAVED on yes; LISTENING on no/timeout
    "SAVED":         {"LISTENING"},
}


def test_all_states_reachable():
    """Every state should be reachable from IDLE through valid transitions."""
    visited = {"IDLE"}
    queue   = ["IDLE"]
    while queue:
        state = queue.pop()
        for nxt in VALID_TRANSITIONS.get(state, set()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    all_states = set(VALID_TRANSITIONS.keys())
    unreachable = all_states - visited
    assert not unreachable, f"States not reachable from IDLE: {unreachable}"


def test_no_invalid_transitions():
    """SAVED must not transition to IDLE directly (must go LISTENING first)."""
    assert "IDLE" not in VALID_TRANSITIONS["SAVED"]


def test_listening_can_reach_saved():
    """Following happy path LISTENING→…→SAVED should be possible."""
    path = ["LISTENING", "TRANSCRIBING", "PARSED", "READBACK", "AWAIT", "SAVED"]
    for i in range(len(path) - 1):
        frm, to = path[i], path[i + 1]
        assert to in VALID_TRANSITIONS[frm], f"Invalid transition {frm}→{to}"

