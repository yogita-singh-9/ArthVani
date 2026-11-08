"""
app.py — ArthVani Streamlit frontend v2.0
"बोलिए, हिसाब हो जाएगा."

UI concept: Retro Teal Boombox × Modern Fintech.

Flow:
  1. Language segmented toggle in hero header
  2. Stats dashboard (Today's sales, purchases, net, entries)
  3. Speak section with hint chips, audio input, pipeline stepper
  4. Transcript bubble → beautiful Confirmation card with live total
     → TTS read-back autoplay → Correct (teal) / Wrong (rust)
  5. Manual "Type it" expander
  6. Ledger with custom HTML table, search, filter, edit, delete
  7. Download Excel/CSV
  8. Sidebar: demo data, How it works, privacy note

Security:
  - API key read only from .env / st.secrets — never logged or shown.
  - Audio bytes used for the API call and immediately discarded.
  - No audio saved to disk.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import html

import streamlit as st

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import db as _db
import gnani
from parser import parse
from speech_text import build_readback
from strings import t, unit_label, unit_selector_labels, UNIT_OPTIONS
from app_helpers import audio_hash, compute_total, build_entry_dict, readback_cache_key

# ── Page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="ArthVani — बोलिए, हिसाब हो जाएगा",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Inject CSS ────────────────────────────────────────────────────────────────
_CSS_PATH = pathlib.Path(__file__).parent / "theme.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
_STT_LANG  = {"hi": "hi-IN", "en": "en-IN"}
_DB        = str(pathlib.Path(__file__).parent / "arthvani.db")
_db.init_db(_DB)


# ════════════════════════════════════════════════════════════════════════════════
# Session state
# ════════════════════════════════════════════════════════════════════════════════

def _init_state():
    defaults = {
        "lang":            "hi",
        "last_audio_hash": None,
        "parsed":          None,
        "transcript":      None,
        "card_item":       "",
        "card_qty":        None,
        "card_unit":       "kg",
        "card_price":      None,
        "card_type":       "sale",
        "tts_cache":       {},
        "saved_msg":       None,
        "error_msg":       None,
        "show_card":       False,
        "delete_pending":  False,
        "pipeline_step":   0,     # 0=idle 1=listen 2=understand 3=readback 4=saved
        "edit_row_id":     None,  # row being edited inline
        "search_query":    "",
        "ledger_filter":   "all", # all / sale / purchase
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════════

def _clear_card():
    st.session_state.update({
        "parsed": None, "transcript": None, "card_item": "",
        "card_qty": None, "card_unit": "kg", "card_price": None,
        "card_type": "sale", "show_card": False,
        "last_audio_hash": None, "pipeline_step": 0,
    })

def _fmt_inr(amount: float) -> str:
    """Format as Indian number system: ₹1,23,456.00"""
    if amount is None:
        return "—"
    s = f"{amount:,.2f}"
    # Convert standard commas to Indian grouping
    # e.g. 123456.00 → 1,23,456.00
    parts = s.split(".")
    n = parts[0].replace(",", "")
    if len(n) > 3:
        last3 = n[-3:]
        rest   = n[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        n = ",".join(groups) + "," + last3
    return f"₹{n}.{parts[1]}"


def _stepper_html(step: int, lang: str) -> str:
    """Render the pipeline stepper (0=idle, 1=listen, 2=understand, 3=readback, 4=saved)."""
    labels = [
        t("step_listen",    lang),
        t("step_understand", lang),
        t("step_readback",  lang),
        t("step_saved",     lang),
    ]
    parts = []
    for i, label in enumerate(labels, 1):
        if i < step:
            cls = "done"
            dot = "✓"
        elif i == step:
            cls = "active"
            dot = ""
        else:
            cls = ""
            dot = ""
        parts.append(
            f'<span class="av-step {cls}">'
            f'  <span class="av-step-dot"></span>'
            f'  {html.escape(label)}'
            f'</span>'
        )
        if i < 4:
            parts.append('<span class="av-step-line"></span>')
    return f'<div class="av-stepper">{"".join(parts)}</div>'


def _hint_chips(lang: str) -> str:
    hints = [t("example_1", lang), t("example_2", lang), t("example_3", lang)]
    chips = "".join(f'<span class="av-chip">{html.escape(h)}</span>' for h in hints)
    return f'<div class="av-hints">{chips}</div>'


def _pill(entry_type: str, lang: str) -> str:
    css = "av-pill-sale" if entry_type == "sale" else "av-pill-purchase"
    label = t(entry_type, lang)
    return f'<span class="av-pill {css}">{html.escape(label)}</span>'


# ════════════════════════════════════════════════════════════════════════════════
# HEADER (Boombox hero)
# ════════════════════════════════════════════════════════════════════════════════

lang = st.session_state["lang"]

# Speaker-cone SVG logo
_LOGO_SVG = (
    '<svg width="44" height="44" viewBox="0 0 44 44" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="flex-shrink:0;">'
    # Outer ring
    '<circle cx="22" cy="22" r="21" fill="#4ABA94" opacity="0.15"/>'
    # Speaker cone circles
    '<circle cx="22" cy="22" r="18" fill="#2B3A39" stroke="#4ABA94" stroke-width="1.5"/>'
    '<circle cx="22" cy="22" r="12" fill="#1a2928" stroke="#4ABA94" stroke-width="1"/>'
    '<circle cx="22" cy="22" r="5" fill="#4ABA94"/>'
    '<circle cx="22" cy="22" r="2" fill="#2B3A39"/>'
    # Arc lines
    '<path d="M8 22 A14 14 0 0 1 36 22" stroke="#FFEDB7" stroke-width="1" fill="none" opacity="0.3"/>'
    '<path d="M12 22 A10 10 0 0 1 32 22" stroke="#4ABA94" stroke-width="1.2" fill="none" opacity="0.4"/>'
    # Rupee mark
    '<text x="22" y="27" text-anchor="middle" font-size="8" fill="#FFEDB7" font-weight="bold">₹</text>'
    '</svg>'
)

# Grille (9 animated bars)
_GRILLE = (
    '<div class="av-grille" aria-hidden="true">'
    + "".join(f'<span></span>' for _ in range(9))
    + "</div>"
)

# Language toggle — we use a workaround with Streamlit radio but hide it
# and show our own styled version that triggers on click
_other_lang    = "en" if lang == "hi" else "hi"
_hi_active     = " active" if lang == "hi" else ""
_en_active     = " active" if lang == "en" else ""

st.markdown(
    f'<div class="av-header">'
    f'{_LOGO_SVG}'
    f'{_GRILLE}'
    f'<div style="flex:1;min-width:0;">'
    f'<div class="av-wordmark">ArthVani<span class="av-rupee"> ₹</span></div>'
    f'<div class="av-tagline">{html.escape(t("tagline", lang))}</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# Language selector — Streamlit native (hidden chrome via label_visibility)
lang_choice = st.radio(
    "भाषा / Language",
    ["हिंदी", "English"],
    index=0 if lang == "hi" else 1,
    horizontal=True,
    label_visibility="visible",
)
new_lang = "hi" if lang_choice == "हिंदी" else "en"
if new_lang != st.session_state["lang"]:
    st.session_state["lang"] = new_lang
    _clear_card()
    st.rerun()

lang = st.session_state["lang"]


# ════════════════════════════════════════════════════════════════════════════════
# STATS DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════

stats = _db.today_stats(_DB)

st.markdown(
    f'<div class="av-stats-row">'
    f'  <div class="av-stat">'
    f'    <span class="av-stat-icon">📈</span>'
    f'    <div class="av-stat-label">{html.escape(t("today_sales", lang))}</div>'
    f'    <div class="av-stat-value teal">{_fmt_inr(stats["sales"])}</div>'
    f'  </div>'
    f'  <div class="av-stat">'
    f'    <span class="av-stat-icon">📉</span>'
    f'    <div class="av-stat-label">{html.escape(t("today_purchases", lang))}</div>'
    f'    <div class="av-stat-value rust">{_fmt_inr(stats["purchases"])}</div>'
    f'  </div>'
    f'  <div class="av-stat">'
    f'    <span class="av-stat-icon">⚖️</span>'
    f'    <div class="av-stat-label">{html.escape(t("today_net", lang))}</div>'
    f'    <div class="av-stat-value">{_fmt_inr(stats["net"])}</div>'
    f'  </div>'
    f'  <div class="av-stat">'
    f'    <span class="av-stat-icon">📋</span>'
    f'    <div class="av-stat-label">{html.escape(t("today_entries", lang))}</div>'
    f'    <div class="av-stat-value">{stats["count"]}</div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ════════════════════════════════════════════════════════════════════════════════
# FLASH MESSAGES
# ════════════════════════════════════════════════════════════════════════════════

if st.session_state.get("saved_msg"):
    st.markdown(
        f'<div class="av-success av-pop">✓ {html.escape(st.session_state.pop("saved_msg"))}</div>',
        unsafe_allow_html=True,
    )
if st.session_state.get("error_msg"):
    st.markdown(
        f'<div class="av-warning">⚠ {html.escape(st.session_state.pop("error_msg"))}</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════════════════
# SPEAK SECTION
# ════════════════════════════════════════════════════════════════════════════════

st.markdown(
    f'<div class="av-section-title">🎙️ {html.escape(t("speak", lang))}</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="av-speak-hint">{html.escape(t("speak_hint", lang))}</div>'
    + _hint_chips(lang),
    unsafe_allow_html=True,
)

# Pipeline stepper (shows progress during recording/processing)
step = st.session_state.get("pipeline_step", 0)
if step > 0:
    st.markdown(_stepper_html(step, lang), unsafe_allow_html=True)

# Audio input
audio_value = st.audio_input(
    label=t("speak", lang),
    label_visibility="collapsed",
    key="mic_input",
)


# ════════════════════════════════════════════════════════════════════════════════
# PROCESS NEW AUDIO
# ════════════════════════════════════════════════════════════════════════════════

if audio_value is not None:
    raw_bytes = audio_value.read()
    h = audio_hash(raw_bytes)

    if h != st.session_state.get("last_audio_hash"):
        st.session_state["last_audio_hash"] = h
        st.session_state["pipeline_step"]   = 1
        _clear_card()
        st.session_state["last_audio_hash"] = h  # restore after _clear_card

        # Step 1: STT
        with st.spinner(f"🎧 {t('listening', lang)}"):
            st.session_state["pipeline_step"] = 1
            try:
                stt_result = gnani.stt(
                    raw_bytes,
                    language_code=_STT_LANG[lang],
                    filename="recording.wav",
                )
            except EnvironmentError:
                st.session_state["error_msg"] = t("error_no_key", lang)
                st.session_state["pipeline_step"] = 0
                st.rerun()
            except RuntimeError as exc:
                st.session_state["error_msg"] = t("error_stt", lang).replace("{detail}", str(exc))
                st.session_state["pipeline_step"] = 0
                st.rerun()

        transcript = stt_result.get("transcript", "").strip()
        if not transcript:
            st.session_state["error_msg"] = t("error_no_audio", lang)
            st.session_state["pipeline_step"] = 0
            st.rerun()

        # Step 2: Parse
        st.session_state["pipeline_step"] = 2
        parsed = parse(stt_result, lang)

        # Populate card
        st.session_state.update({
            "parsed":      parsed,
            "transcript":  transcript,
            "card_item":   parsed.get("item") or "",
            "card_qty":    parsed.get("quantity"),
            "card_unit":   parsed.get("unit") or "kg",
            "card_price":  parsed.get("price"),
            "card_type":   parsed.get("entry_type") or "sale",
            "show_card":   True,
            "pipeline_step": 3,
        })
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# CONFIRMATION CARD
# ════════════════════════════════════════════════════════════════════════════════

if st.session_state.get("show_card"):
    parsed = st.session_state["parsed"] or {}

    # Transcript bubble
    if st.session_state.get("transcript"):
        st.markdown(
            f'<div class="av-bubble-label">{html.escape(t("transcript_raw", lang))}</div>'
            f'<div class="av-bubble">🎙 {html.escape(st.session_state["transcript"])}</div>',
            unsafe_allow_html=True,
        )

    # Needs-review warning
    if parsed.get("needs_review") and parsed.get("warnings"):
        warn_text = " · ".join(parsed["warnings"])
        st.markdown(
            f'<div class="av-warning">{html.escape(t("needs_review", lang))}'
            f'<br><small>{html.escape(warn_text)}</small></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="av-section-title">📝 {html.escape(t("confirm_title", lang))}</div>',
        unsafe_allow_html=True,
    )
    st.caption(t("confirm_hint", lang))

    # Editable fields
    unit_map   = unit_selector_labels(lang)
    unit_keys  = list(unit_map.keys())
    unit_disp  = list(unit_map.values())
    cur_unit   = st.session_state["card_unit"] or "kg"
    unit_idx   = unit_keys.index(cur_unit) if cur_unit in unit_keys else 0

    type_opts  = ["sale", "purchase"]
    type_disp  = [t("sale", lang), t("purchase", lang)]
    cur_type   = st.session_state["card_type"] or "sale"
    type_idx   = type_opts.index(cur_type) if cur_type in type_opts else 0

    col1, col2 = st.columns(2)
    with col1:
        new_item = st.text_input(t("item", lang),
                                 value=st.session_state["card_item"] or "",
                                 key="edit_item")
        new_qty = st.number_input(t("qty", lang),
                                  min_value=0.0, step=0.5, format="%.2f",
                                  value=float(st.session_state["card_qty"] or 0.0),
                                  key="edit_qty")
        new_unit_disp = st.selectbox(t("unit", lang),
                                     options=unit_disp, index=unit_idx,
                                     key="edit_unit")
    with col2:
        new_price = st.number_input(t("price", lang),
                                    min_value=0.0, step=0.5, format="%.2f",
                                    value=float(st.session_state["card_price"] or 0.0),
                                    key="edit_price")
        new_type_disp = st.selectbox(t("type", lang),
                                     options=type_disp, index=type_idx,
                                     key="edit_type")

    new_unit = unit_keys[unit_disp.index(new_unit_disp)]
    new_type = type_opts[type_disp.index(new_type_disp)]

    # Live total
    new_total = compute_total(new_qty or None, new_price or None)
    total_str = _fmt_inr(new_total) if new_total else "—"
    st.markdown(
        f'<div class="av-confirm-total">'
        f'<div class="av-confirm-total-label">{html.escape(t("total", lang))}</div>'
        f'<div class="av-confirm-total-value">{html.escape(total_str)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── TTS Read-back ─────────────────────────────────────────────────────────
    if new_item and new_qty and new_price:
        entry_for_rb = build_entry_dict(new_item, new_qty, new_unit, new_price, new_type)
        entry_for_rb["total"] = new_total
        rb_key = readback_cache_key(entry_for_rb, lang)

        if rb_key not in st.session_state["tts_cache"]:
            rb_text = build_readback(entry_for_rb, lang)
            with st.spinner(t("readback_playing", lang)):
                try:
                    wav_bytes = gnani.tts(rb_text, lang)
                    st.session_state["tts_cache"][rb_key] = wav_bytes
                    # Cap cache at 10 entries
                    if len(st.session_state["tts_cache"]) > 10:
                        oldest = next(iter(st.session_state["tts_cache"]))
                        del st.session_state["tts_cache"][oldest]
                except (RuntimeError, EnvironmentError) as exc:
                    st.warning(t("error_tts", lang).replace("{detail}", str(exc)))

        cached_wav = st.session_state["tts_cache"].get(rb_key)
        if cached_wav:
            st.audio(cached_wav, format="audio/wav", autoplay=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button(t("correct", lang), type="primary", use_container_width=True, key="btn_correct"):
            if not new_item:
                st.session_state["error_msg"] = t("needs_review", lang)
            elif not new_qty or not new_price:
                st.session_state["error_msg"] = t("needs_review", lang)
            else:
                entry = build_entry_dict(new_item, new_qty, new_unit, new_price, new_type)
                try:
                    _db.save_entry(
                        entry, lang,
                        transcript=st.session_state.get("transcript", ""),
                        path=_DB,
                    )
                    st.session_state["saved_msg"]    = t("saved", lang)
                    st.session_state["pipeline_step"] = 4
                    _clear_card()
                    st.rerun()
                except Exception as exc:
                    st.session_state["error_msg"] = t("error_save", lang).replace("{detail}", str(exc))
                    st.rerun()

    with btn_col2:
        st.markdown('<div class="av-btn-wrong">', unsafe_allow_html=True)
        if st.button(t("wrong", lang), use_container_width=True, key="btn_wrong"):
            _clear_card()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# MANUAL ENTRY EXPANDER
# ════════════════════════════════════════════════════════════════════════════════

with st.expander(t("manual_entry", lang)):
    st.caption(t("confirm_hint", lang))
    unit_map  = unit_selector_labels(lang)
    unit_keys = list(unit_map.keys())
    unit_disp = list(unit_map.values())

    mc1, mc2 = st.columns(2)
    with mc1:
        m_item  = st.text_input(t("item", lang), key="m_item")
        m_qty   = st.number_input(t("qty", lang), min_value=0.0, step=0.5,
                                  format="%.2f", key="m_qty")
        m_udisp = st.selectbox(t("unit", lang), options=unit_disp, key="m_unit")
    with mc2:
        m_price = st.number_input(t("price", lang), min_value=0.0, step=0.5,
                                  format="%.2f", key="m_price")
        m_tdisp = st.selectbox(t("type", lang),
                               options=[t("sale", lang), t("purchase", lang)],
                               key="m_type")

    m_unit = unit_keys[unit_disp.index(m_udisp)]
    m_type = "sale" if m_tdisp == t("sale", lang) else "purchase"
    m_total = compute_total(m_qty or None, m_price or None)
    if m_total:
        st.markdown(f"**{t('total', lang)}: {_fmt_inr(m_total)}**")

    if st.button(t("manual_save", lang), key="btn_manual_save"):
        if not m_item:
            st.error(t("needs_review", lang))
        elif not m_qty or not m_price:
            st.error(t("needs_review", lang))
        else:
            entry = build_entry_dict(m_item, m_qty, m_unit, m_price, m_type)
            try:
                _db.save_entry(entry, lang, transcript="[manual entry]", path=_DB)
                st.session_state["saved_msg"] = t("saved", lang)
                st.rerun()
            except Exception as exc:
                st.error(t("error_save", lang).replace("{detail}", str(exc)))


# ════════════════════════════════════════════════════════════════════════════════
# LEDGER TABLE
# ════════════════════════════════════════════════════════════════════════════════

st.markdown(
    f'<div class="av-section-title">📒 {html.escape(t("ledger_title", lang))}</div>',
    unsafe_allow_html=True,
)

# Search + filter row
search_col, filter_col = st.columns([3, 2])
with search_col:
    search_q = st.text_input(
        "Search",
        value=st.session_state.get("search_query", ""),
        placeholder=t("search_placeholder", lang),
        label_visibility="collapsed",
        key="search_input",
    )
    st.session_state["search_query"] = search_q

with filter_col:
    filter_opts = {
        t("filter_all", lang):       "all",
        t("filter_sales", lang):     "sale",
        t("filter_purchases", lang): "purchase",
    }
    filter_disp = st.selectbox(
        "Filter",
        options=list(filter_opts.keys()),
        label_visibility="collapsed",
        key="filter_select",
    )
    st.session_state["ledger_filter"] = filter_opts[filter_disp]

# Fetch and filter entries
all_rows = _db.list_entries(_DB)
active_filter = st.session_state.get("ledger_filter", "all")
if active_filter != "all":
    all_rows = [r for r in all_rows if r.get("entry_type") == active_filter]
if search_q:
    sq = search_q.lower()
    all_rows = [r for r in all_rows if sq in str(r.get("item", "")).lower()]

if not all_rows:
    st.markdown(
        '<div class="av-empty">'
        '<span class="av-empty-icon">📋</span>'
        f'<div class="av-empty-title">{html.escape(t("empty_table", lang))}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    # Custom HTML table
    unit_map_disp = unit_selector_labels(lang)

    def _unit_disp(u):
        return unit_map_disp.get(u, u) if u else "—"

    def _date_disp(ts):
        if not ts or len(ts) < 10:
            return ts or "—"
        return f"{ts[8:10]}-{ts[5:7]}-{ts[:4]}"

    def _time_disp(ts):
        return ts[11:16] if ts and len(ts) >= 16 else "—"

    # Build column headers (translated)
    col_date  = t("date", lang)
    col_time  = t("time", lang)
    col_type  = t("type", lang)
    col_item  = t("item", lang)
    col_qty   = t("qty", lang)
    col_unit  = t("unit", lang)
    col_price = t("price", lang)
    col_total = t("total", lang)

    thead = (
        f"<thead><tr>"
        f"<th>{html.escape(col_date)}</th>"
        f"<th>{html.escape(col_time)}</th>"
        f"<th>{html.escape(col_type)}</th>"
        f"<th>{html.escape(col_item)}</th>"
        f"<th style='text-align:right'>{html.escape(col_qty)}</th>"
        f"<th>{html.escape(col_unit)}</th>"
        f"<th style='text-align:right'>{html.escape(col_price)}</th>"
        f"<th style='text-align:right'>{html.escape(col_total)}</th>"
        f"</tr></thead>"
    )

    tbody_rows = []
    for row in all_rows:
        typ  = row.get("entry_type", "sale")
        pill = _pill(typ, lang)
        qty  = row.get("quantity", 0)
        price= row.get("price", 0)
        total= row.get("total", 0)
        tbody_rows.append(
            f"<tr>"
            f"<td>{html.escape(_date_disp(row.get('created_at', '')))}</td>"
            f"<td style='color:var(--grey);font-size:0.8rem'>{html.escape(_time_disp(row.get('created_at', '')))}</td>"
            f"<td>{pill}</td>"
            f"<td class='av-table-item'>{html.escape(str(row.get('item', '')))}</td>"
            f"<td style='text-align:right'>{qty:g}</td>"
            f"<td style='color:var(--grey)'>{html.escape(_unit_disp(row.get('unit', '')))}</td>"
            f"<td style='text-align:right;color:var(--grey)'>₹{price:,.2f}</td>"
            f"<td>₹{total:,.2f}</td>"
            f"</tr>"
        )

    table_html = (
        '<div class="av-table-wrap">'
        f'<table class="av-table">{thead}<tbody>'
        + "".join(tbody_rows)
        + "</tbody></table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # Download buttons
    dl1, dl2 = st.columns(2)
    with dl1:
        xlsx_bytes = _db.export_xlsx(lang, _DB)
        st.download_button(
            label=t("download_xlsx", lang),
            data=xlsx_bytes,
            file_name="arthvani_ledger.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with dl2:
        csv_bytes = _db.export_csv(lang, _DB)
        st.download_button(
            label=t("download_csv", lang),
            data=csv_bytes,
            file_name="arthvani_ledger.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Delete last entry (2-step confirm)
    st.markdown("---")
    if not st.session_state.get("delete_pending"):
        if st.button(t("delete_last", lang), key="btn_del"):
            st.session_state["delete_pending"] = True
            st.rerun()
    else:
        st.markdown(
            f'<div class="av-warning">{html.escape(t("delete_confirm", lang))}</div>',
            unsafe_allow_html=True,
        )
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button(t("delete_last", lang), key="btn_del_confirm", type="primary"):
                ok = _db.delete_last_entry(_DB)
                st.session_state["delete_pending"] = False
                st.session_state["saved_msg"] = (
                    t("delete_done", lang) if ok else t("nothing_to_delete", lang)
                )
                st.rerun()
        with dc2:
            if st.button(t("wrong", lang), key="btn_del_cancel"):
                st.session_state["delete_pending"] = False
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.3rem;font-weight:800;color:var(--ink);margin-bottom:0.2rem">'
        '🎙️ ArthVani</div>',
        unsafe_allow_html=True,
    )
    st.caption(t("powered_by", lang))
    st.markdown("---")

    # Demo data
    st.markdown("**🎭 Demo Data**")
    if st.button(t("demo_data", lang), use_container_width=True, key="btn_demo"):
        _db.seed_demo_entries(_DB)
        st.session_state["saved_msg"] = t("demo_loaded", lang)
        st.rerun()
    st.caption("⚠ " + (
        "Demo entries are synthetic and do not represent real transactions."
        if lang == "en" else
        "डेमो एंट्री नकली हैं, असली लेनदेन नहीं।"
    ))

    st.markdown("---")

    # How it works
    with st.expander(t("how_it_works", lang)):
        st.markdown(
            f"- {t('how_step1', lang)}\n"
            f"- {t('how_step2', lang)}\n"
            f"- {t('how_step3', lang)}\n"
            f"- {t('how_step4', lang)}\n"
        )

    # Supported examples
    with st.expander("💬 " + ("Sentence Examples" if lang == "en" else "वाक्य उदाहरण")):
        st.markdown(
            f"- {t('example_1', lang)}\n"
            f"- {t('example_2', lang)}\n"
            f"- {t('example_3', lang)}\n"
        )

    st.markdown("---")
    st.info(t("privacy_note", lang))
