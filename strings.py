"""
strings.py — All UI text for ArthVani in Hindi and English.

Usage
-----
  from strings import t, UNIT_LABELS

  t("speak", "hi")        -> "बोलिए"
  t("speak", "en")        -> "Speak"
  UNIT_LABELS["kg"]["hi"] -> "किलो"
  UNIT_LABELS["kg"]["en"] -> "kg"

Design
------
  Every string that appears in the UI lives here.
  Hindi text is always in Devanagari script.
  No formatting or logic — pure lookup table.
"""

from __future__ import annotations

# ════════════════════════════════════════════════════════════
# 1. MAIN UI STRING TABLE
# ════════════════════════════════════════════════════════════

_STRINGS: dict[str, dict[str, str]] = {
    # App identity
    "app_name":       {"en": "ArthVani",          "hi": "अर्थवाणी"},
    "tagline":        {"en": "Speak, and the ledger is done.",
                       "hi": "बोलिए, हिसाब हो जाएगा।"},

    # Navigation
    "nav_dashboard":  {"en": "Dashboard",          "hi": "डैशबोर्ड"},
    "nav_speak":      {"en": "Speak",              "hi": "बोलिए"},
    "nav_ledger":     {"en": "Ledger",             "hi": "बही-खाता"},
    "nav_reports":    {"en": "Reports",            "hi": "रिपोर्ट"},
    "nav_settings":   {"en": "Settings",           "hi": "सेटिंग"},

    # Status
    "status_api":     {"en": "API",                "hi": "API"},
    "status_mic":     {"en": "Mic",                "hi": "माइक"},

    # Greeting
    "greeting_morning":   {"en": "Good morning",   "hi": "सुप्रभात"},
    "greeting_afternoon": {"en": "Good afternoon", "hi": "नमस्ते"},
    "greeting_evening":   {"en": "Good evening",   "hi": "शुभ संध्या"},

    # Dashboard
    "chart_title":    {"en": "14-Day Overview",    "hi": "14 दिन का सारांश"},
    "top_items":      {"en": "Top Items",          "hi": "शीर्ष सामान"},
    "recent_entries": {"en": "Recent Entries",     "hi": "हालिया एंट्री"},
    "hero_cta_title": {"en": "Ready to record?",   "hi": "एंट्री दर्ज करने के लिए तैयार?"},
    "hero_cta_sub":   {"en": "Tap the button and say your entry in Hindi or English.",
                       "hi": "बटन दबाएं और हिंदी या English में एंट्री बोलें।"},

    # Speak
    "try_saying":     {"en": "Try saying:",        "hi": "बोलकर देखें:"},
    "save_entry":     {"en": "Save entry",         "hi": "एंट्री सेव करें"},
    "rerecord":       {"en": "Re-record",          "hi": "फिर से बोलें"},
    "discard":        {"en": "Discard",            "hi": "रद्द करें"},
    "discarded":      {"en": "Entry discarded.",   "hi": "एंट्री रद्द की।"},
    "undo":           {"en": "Undo",               "hi": "वापस लें"},
    "undo_done":      {"en": "Entry removed.",     "hi": "एंट्री हटाई।"},

    # Ledger filters – date
    "date_all":       {"en": "All time",           "hi": "सभी समय"},
    "date_today":     {"en": "Today",              "hi": "आज"},
    "date_7d":        {"en": "Last 7 days",        "hi": "पिछले 7 दिन"},
    "date_30d":       {"en": "Last 30 days",       "hi": "पिछले 30 दिन"},

    # Edit / delete
    "edit":           {"en": "Edit",               "hi": "संपादित करें"},
    "delete":         {"en": "Delete",             "hi": "हटाएं"},
    "edit_entry":     {"en": "Edit Entry",         "hi": "एंट्री बदलें"},
    "delete_confirm_title": {"en": "Delete entry?","hi": "एंट्री हटाएं?"},
    "delete_confirm_body":  {"en": "This action cannot be undone.",
                              "hi": "यह क्रिया वापस नहीं होगी।"},
    "save":           {"en": "Save",               "hi": "सेव करें"},
    "cancel":         {"en": "Cancel",             "hi": "रद्द करें"},

    # Reports
    "period":         {"en": "Period",             "hi": "समयावधि"},
    "summary":        {"en": "Summary",            "hi": "सारांश"},
    "sales_vs_purchases": {"en": "Sales vs Purchases", "hi": "बिक्री बनाम खरीद"},

    # Settings
    "settings_shop":        {"en": "Shop",         "hi": "दुकान"},
    "settings_shop_name":   {"en": "Shop Name",    "hi": "दुकान का नाम"},
    "settings_language":    {"en": "Language",     "hi": "भाषा"},
    "settings_examples":    {"en": "Supported Sentence Patterns", "hi": "समर्थित वाक्य"},
    "demo_data_title":      {"en": "Demo Data",    "hi": "डेमो डेटा"},
    "demo_data_desc":       {"en": "Load realistic sample entries to explore the app. Clear them any time — your real entries are never touched.",
                             "hi": "ऐप को एक्सप्लोर करने के लिए डेमो एंट्री लोड करें। कभी भी हटाएं — असली एंट्री सुरक्षित रहेंगी।"},
    "privacy_title":        {"en": "Privacy & Security", "hi": "गोपनीयता और सुरक्षा"},
    "privacy_note2":        {"en": "No customer data is stored in the cloud. Your ledger lives locally on this device.",
                             "hi": "ग्राहक डेटा क्लाउड में सेव नहीं होता। आपका हिसाब केवल इस डिवाइस पर है।"},

    # Error - mic
    "error_mic_denied":  {"en": "Microphone access denied. Please allow mic in browser settings.",
                           "hi": "माइक की अनुमति नहीं मिली। ब्राउज़र सेटिंग में माइक अनुमति दें।"},
    "error_audio_too_long": {"en": "Audio too long (max 60 s). Please try again.",
                              "hi": "ऑडियो बहुत लंबी है (अधिकतम 60 सेकंड)। फिर कोशिश करें।"},

    # Language selector labels (shown in English always so user can switch)
    "lang_hindi":     {"en": "हिंदी",              "hi": "हिंदी"},
    "lang_english":   {"en": "English",             "hi": "English"},

    # Mic / recording
    "speak":          {"en": "Speak",               "hi": "बोलिए"},
    "speak_hint":     {"en": 'Tap the mic and say an entry, e.g. "50 kilo rice 60 rupees per kilo"',
                       "hi": 'माइक दबाएं और एक एंट्री बोलें, जैसे "50 किलो चावल 60 रुपये किलो"'},
    "listening":      {"en": "Listening…",          "hi": "सुन रहा हूँ…"},
    "processing":     {"en": "Processing…",         "hi": "प्रोसेस हो रहा है…"},

    # Transcript display
    "transcript":     {"en": "Transcript",          "hi": "ट्रांसक्रिप्ट"},
    "transcript_raw": {"en": "What we heard",       "hi": "जो सुना"},

    # Confirmation card
    "confirm_title":  {"en": "Confirm entry",       "hi": "एंट्री की पुष्टि करें"},
    "confirm_hint":   {"en": "Edit any field, then tap Correct.",
                       "hi": "कोई भी फ़ील्ड बदलें, फिर 'सही है' दबाएं।"},

    # Field labels
    "date":           {"en": "Date",                "hi": "तारीख"},
    "time":           {"en": "Time",                "hi": "समय"},
    "type":           {"en": "Type",                "hi": "प्रकार"},
    "item":           {"en": "Item",                "hi": "सामान"},
    "qty":            {"en": "Quantity",            "hi": "मात्रा"},
    "unit":           {"en": "Unit",                "hi": "इकाई"},
    "price":          {"en": "Price (₹/unit)",      "hi": "दाम (₹/इकाई)"},
    "total":          {"en": "Total (₹)",           "hi": "कुल (₹)"},
    "today_total":    {"en": "Today's total",       "hi": "आज का कुल"},
    "transcript_col": {"en": "Transcript",          "hi": "ट्रांसक्रिप्ट"},
    "language_col":   {"en": "Language",            "hi": "भाषा"},

    # Entry type options
    "sale":           {"en": "Sale",                "hi": "बिक्री"},
    "purchase":       {"en": "Purchase",            "hi": "खरीद"},

    # Action buttons
    "correct":        {"en": "✓  Correct",          "hi": "✓  सही है"},
    "wrong":          {"en": "✗  Wrong",             "hi": "✗  गलत है"},
    "saved":          {"en": "✓ Entry saved.",       "hi": "✓ एंट्री सेव हो गई।"},
    "retry":          {"en": "Recording cleared. Speak again.",
                       "hi": "रिकॉर्डिंग हटा दी। फिर से बोलें।"},

    # Manual entry
    "manual_entry":   {"en": "⌨  Type it instead",  "hi": "⌨  खुद लिखें"},
    "manual_save":    {"en": "Save entry",           "hi": "एंट्री सेव करें"},

    # Ledger table
    "ledger_title":   {"en": "Ledger",              "hi": "बही-खाता"},
    "empty_table":    {"en": "No entries yet. Speak or type your first entry above.",
                       "hi": "अभी कोई एंट्री नहीं है। ऊपर बोलें या लिखें।"},

    # Downloads
    "download_xlsx":  {"en": "⬇  Download Excel",   "hi": "⬇  Excel डाउनलोड करें"},
    "download_csv":   {"en": "⬇  Download CSV",     "hi": "⬇  CSV डाउनलोड करें"},

    # Delete
    "delete_last":    {"en": "Delete last entry",   "hi": "आखिरी एंट्री हटाएं"},
    "delete_confirm": {"en": "⚠ Tap again to confirm deletion.",
                       "hi": "⚠ पुष्टि के लिए फिर से दबाएं।"},
    "delete_done":    {"en": "Last entry deleted.",  "hi": "आखिरी एंट्री हटा दी।"},
    "nothing_to_delete": {"en": "No entries to delete.", "hi": "हटाने के लिए कोई एंट्री नहीं।"},

    # Demo data
    "demo_data":      {"en": "Load demo entries",   "hi": "डेमो एंट्री लोड करें"},
    "demo_loaded":    {"en": "5 demo entries loaded (synthetic data).",
                       "hi": "5 डेमो एंट्री लोड हुईं (नकली डेटा)।"},
    "clear_demo":     {"en": "Clear demo entries",  "hi": "डेमो एंट्री हटाएं"},

    # Sidebar / info
    "powered_by":     {"en": "Powered by Gnani AI Prisma & Timbre",
                       "hi": "Gnani AI Prisma और Timbre द्वारा संचालित"},
    "privacy_note":   {"en": "🔒 Audio is sent to Gnani only for transcription and is not stored.",
                       "hi": "🔒 ऑडियो केवल ट्रांसक्रिप्शन के लिए Gnani को भेजा जाता है, स्टोर नहीं होता।"},

    # Read-back
    "readback_playing": {"en": "Playing read-back…", "hi": "पढ़ा जा रहा है…"},

    # Review / warnings
    "needs_review":   {"en": "⚠ Some fields could not be detected. Please fill them in.",
                       "hi": "⚠ कुछ फ़ील्ड नहीं मिलीं। कृपया भरें।"},

    # Dashboard stats
    "today_sales":    {"en": "Today's Sales",       "hi": "आज की बिक्री"},
    "today_purchases":{"en": "Today's Purchases",   "hi": "आज की खरीद"},
    "today_net":      {"en": "Net",                 "hi": "शुद्ध"},
    "today_entries":  {"en": "Entries",             "hi": "एंट्री"},

    # Stepper steps
    "step_listen":    {"en": "Listening",           "hi": "सुन रहे"},
    "step_understand":{"en": "Understanding",       "hi": "समझ रहे"},
    "step_readback":  {"en": "Reading back",        "hi": "पढ़ रहे"},
    "step_saved":     {"en": "Saved",               "hi": "सेव"},

    # Ledger filters
    "filter_all":     {"en": "All",                 "hi": "सभी"},
    "filter_sales":   {"en": "Sales only",          "hi": "केवल बिक्री"},
    "filter_purchases":{"en": "Purchases only",     "hi": "केवल खरीद"},
    "search_placeholder": {"en": "Search item…",   "hi": "सामान खोजें…"},

    # How it works
    "how_it_works":   {"en": "How it works",        "hi": "कैसे काम करता है"},
    "how_step1":      {"en": "1. Tap Speak and say an entry",
                       "hi": "1. बोलिए दबाएं और एंट्री बोलें"},
    "how_step2":      {"en": "2. App hears, understands and reads it back",
                       "hi": "2. ऐप सुनेगा, समझेगा और पढ़कर सुनाएगा"},
    "how_step3":      {"en": "3. Confirm or correct, then it's saved",
                       "hi": "3. पुष्टि करें या सुधारें, एंट्री सेव हो जाएगी"},
    "how_step4":      {"en": "4. Download your ledger as Excel or CSV",
                       "hi": "4. Excel या CSV में बही-खाता डाउनलोड करें"},

    # Sentence examples
    "example_1":      {"en": "\"50 kilo rice 60 rupees per kilo\"",
                       "hi": '"50 किलो चावल 60 रुपये किलो"'},
    "example_2":      {"en": "\"2 litre milk 55 rupees per litre\"",
                       "hi": '"2 लीटर दूध 55 रुपये लीटर"'},
    "example_3":      {"en": "\"12 soap 30 rupees each\"",
                       "hi": '"12 साबुन 30 रुपये प्रति"'},

    # Errors
    "error_no_audio":    {"en": "No audio received. Please try again.",
                          "hi": "कोई ऑडियो नहीं मिला। फिर से कोशिश करें।"},
    "error_stt":         {"en": "Speech recognition failed: {detail}",
                          "hi": "आवाज़ पहचान नहीं हुई: {detail}"},
    "error_tts":         {"en": "Could not play read-back: {detail}",
                          "hi": "पढ़ा नहीं जा सका: {detail}"},
    "error_save":        {"en": "Could not save entry: {detail}",
                          "hi": "एंट्री सेव नहीं हुई: {detail}"},
    "error_no_key":      {"en": "API key not configured. Add GNANI_API_KEY to your .env file.",
                          "hi": "API key सेट नहीं है। .env फ़ाइल में GNANI_API_KEY डालें।"},
    "error_network":     {"en": "Network error. Check your internet connection.",
                          "hi": "नेटवर्क एरर। इंटरनेट कनेक्शन जांचें।"},
    "error_generic":     {"en": "Something went wrong: {detail}",
                          "hi": "कुछ गलत हुआ: {detail}"},
}


# ════════════════════════════════════════════════════════════
# 2. UNIT LABELS
# ════════════════════════════════════════════════════════════

# Canonical unit key → display label per language
UNIT_LABELS: dict[str, dict[str, str]] = {
    "kg":     {"en": "kg",      "hi": "किलो"},
    "g":      {"en": "g",       "hi": "ग्राम"},
    "litre":  {"en": "litre",   "hi": "लीटर"},
    "dozen":  {"en": "dozen",   "hi": "दर्जन"},
    "packet": {"en": "packet",  "hi": "पैकेट"},
    "piece":  {"en": "piece",   "hi": "नग"},
}

# Ordered list for the unit selector drop-down
UNIT_OPTIONS: list[str] = ["kg", "g", "litre", "dozen", "packet", "piece"]


# ════════════════════════════════════════════════════════════
# 3. PUBLIC HELPER
# ════════════════════════════════════════════════════════════

def t(key: str, lang: str) -> str:
    """
    Return the UI string for `key` in `lang` ("hi" or "en").

    Falls back to English if the key or language is missing.
    Raises KeyError only in development (key not in table at all).

    Parameters
    ----------
    key  : string key from _STRINGS
    lang : "hi" or "en"
    """
    entry = _STRINGS.get(key)
    if entry is None:
        # Hard error in dev so missing keys are caught early
        raise KeyError(f"strings.t(): unknown key {key!r}")
    return entry.get(lang) or entry.get("en") or ""


def unit_label(unit: str, lang: str) -> str:
    """Return the display label for a canonical unit key."""
    entry = UNIT_LABELS.get(unit, {})
    return entry.get(lang) or entry.get("en") or unit


def unit_selector_labels(lang: str) -> dict[str, str]:
    """
    Return an ordered dict of {canonical_key: display_label} for the unit
    selector widget, in the given language.
    """
    return {k: unit_label(k, lang) for k in UNIT_OPTIONS}

