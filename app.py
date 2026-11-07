"""
app.py — ArthVani Streamlit frontend.

Flow (per PRD §5):
  1. Language selector at top of page (Hindi / English)
  2. Today's total card + mic input (st.audio_input)
  3. On new audio: STT → parser → show transcript + confirmation card
  4. Confirmation card with editable fields; total recomputed in Python
  5. Read-back: build_readback() → TTS → st.audio player
  6. Correct (teal) → save to SQLite + clear card
     Wrong (rust)  → discard + allow re-record
  7. Manual "Type it instead" expander
  8. Ledger table + Download Excel / CSV + Delete last entry
  9. Sidebar: demo data, powered-by, privacy note

Security: never prints or logs the API key. Audio bytes are used for the
API call only and are not saved to disk.
"""

import hashlib
import pathlib
import sys

import streamlit as st

# ── Project imports ───────────────────────────────────────────────────────────
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import db as _db
import gnani
from parser import parse
from speech_text import build_readback
from strings import t, unit_label, unit_selector_labels, UNIT_OPTIONS
from app_helpers import audio_hash, compute_total, build_entry_dict, readback_cache_key

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="ArthVani",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Load CSS ──────────────────────────────────────────────────────────────────
_CSS_PATH = pathlib.Path(__file__).parent / "theme.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)

# ── Language-code map (UI lang → Gnani STT language_code) ────────────────────
_STT_LANG = {"hi": "hi-IN", "en": "en-IN"}

# ── DB path (project root) ────────────────────────────────────────────────────
_DB = str(pathlib.Path(__file__).parent / "arthvani.db")
_db.init_db(_DB)


# ════════════════════════════════════════════════════════════
# Session state initialisation
# ════════════════════════════════════════════════════════════

def _init_state():
    defaults = {
        "lang":            "hi",          # active UI language
        "last_audio_hash": None,          # prevents resending same audio
        "parsed":          None,          # dict from parser.parse()
        "transcript":      None,          # raw STT transcript string
        "card_item":       "",
        "card_qty":        None,
        "card_unit":       "kg",
        "card_price":      None,
        "card_type":       "sale",
        "tts_cache":       {},            # {cache_key: wav_bytes}
        "saved_msg":       None,          # one-shot "saved" flash message
        "delete_pending":  False,         # confirm step for delete
        "show_card":       False,         # whether confirmation card is visible
        "error_msg":       None,          # one-shot error message
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════════
# UI helpers
# ════════════════════════════════════════════════════════════

def _card(content_fn, css_extra=""):
    """Wrap a content function in an av-card div."""
    st.markdown(f'<div class="av-card {css_extra}">', unsafe_allow_html=True)
    content_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def _show_error(msg: str):
    st.markdown(f'<div class="av-warning">⚠ {msg}</div>', unsafe_allow_html=True)


def _show_success(msg: str):
    st.markdown(f'<div class="av-success">✓ {msg}</div>', unsafe_allow_html=True)


def _clear_card():
    """Reset confirmation card and related state."""
    for k in ("parsed", "transcript", "card_item", "card_qty",
              "card_unit", "card_price", "card_type", "show_card"):
        st.session_state[k] = None if k in ("parsed", "transcript") else (
            False if k == "show_card" else
            "kg" if k == "card_unit" else
            "sale" if k == "card_type" else
            "" if k == "card_item" else None
        )
    st.session_state["last_audio_hash"] = None


# ════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════

# Speaker-cone SVG logo (inline, no external resource)
_LOGO_SVG = (
    '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="flex-shrink:0;">'
    '<circle cx="20" cy="20" r="19" fill="#4ABA94" stroke="#2B3A39" stroke-width="1.5"/>'
    '<circle cx="20" cy="20" r="10" fill="#2B3A39"/>'
    '<circle cx="20" cy="20" r="4" fill="#4ABA94"/>'
    '<path d="M10 20 A10 10 0 0 1 30 20" stroke="#FFEDB7" stroke-width="1.2" fill="none" opacity="0.5"/>'
    '<path d="M6 20 A14 14 0 0 1 34 20" stroke="#FFEDB7" stroke-width="1" fill="none" opacity="0.3"/>'
    '</svg>'
)

# Grille strip (7 vertical bars)
_GRILLE = '<div class="av-grille">' + "".join("<span></span>" for _ in range(7)) + "</div>"

lang = st.session_state["lang"]

st.markdown(
    f'<div class="av-header">'
    f'{_LOGO_SVG}'
    f'{_GRILLE}'
    f'<div>'
    f'<div class="av-wordmark">ArthVani</div>'
    f'<div class="av-tagline">{t("tagline", lang)}</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ════════════════════════════════════════════════════════════
# LANGUAGE SELECTOR (top of main page — works on phones)
# ════════════════════════════════════════════════════════════

lang_choice = st.radio(
    label="Language / भाषा",
    options=["हिंदी", "English"],
    index=0 if st.session_state["lang"] == "hi" else 1,
    horizontal=True,
    label_visibility="collapsed",
)
new_lang = "hi" if lang_choice == "हिंदी" else "en"
if new_lang != st.session_state["lang"]:
    st.session_state["lang"] = new_lang
    _clear_card()
    st.rerun()

lang = st.session_state["lang"]   # re-read after possible change


# ════════════════════════════════════════════════════════════
# TODAY'S TOTAL CARD
# ════════════════════════════════════════════════════════════

total_today = _db.today_total(_DB)
st.markdown(
    f'<div class="av-card av-card-teal">'
    f'<div class="av-today-label">{t("today_total", lang)}</div>'
    f'<div class="av-today-amount">₹ {total_today:,.2f}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ════════════════════════════════════════════════════════════
# MIC INPUT
# ════════════════════════════════════════════════════════════

st.markdown(f"**{t('speak', lang)}** — {t('speak_hint', lang)}")
audio_value = st.audio_input(label=t("speak", lang), label_visibility="collapsed")

# Flash messages
if st.session_state.get("saved_msg"):
    _show_success(st.session_state.pop("saved_msg"))
if st.session_state.get("error_msg"):
    _show_error(st.session_state.pop("error_msg"))


# ════════════════════════════════════════════════════════════
# PROCESS NEW AUDIO
# ════════════════════════════════════════════════════════════

if audio_value is not None:
    raw_bytes = audio_value.read()
    h = audio_hash(raw_bytes)

    if h != st.session_state.get("last_audio_hash"):
        # New recording — process it
        st.session_state["last_audio_hash"] = h
        _clear_card()

        with st.spinner(t("processing", lang)):
            try:
                stt_result = gnani.stt(
                    raw_bytes,
                    language_code=_STT_LANG[lang],
                    filename="recording.wav",
                )
            except RuntimeError as exc:
                st.session_state["error_msg"] = t("error_stt", lang).replace(
                    "{detail}", str(exc)
                )
                st.rerun()
            except EnvironmentError:
                st.session_state["error_msg"] = t("error_no_key", lang)
                st.rerun()

        transcript = stt_result.get("transcript", "")
        if not transcript:
            st.session_state["error_msg"] = t("error_no_audio", lang)
            st.rerun()

        parsed = parse(stt_result, lang)

        # Populate card fields from parse result
        st.session_state["parsed"]     = parsed
        st.session_state["transcript"] = transcript
        st.session_state["card_item"]  = parsed.get("item") or ""
        st.session_state["card_qty"]   = parsed.get("quantity")
        st.session_state["card_unit"]  = parsed.get("unit") or "kg"
        st.session_state["card_price"] = parsed.get("price")
        st.session_state["card_type"]  = parsed.get("entry_type") or "sale"
        st.session_state["show_card"]  = True
        st.rerun()


# ════════════════════════════════════════════════════════════
# CONFIRMATION CARD
# ════════════════════════════════════════════════════════════

if st.session_state.get("show_card"):
    parsed = st.session_state["parsed"] or {}

    st.markdown(f"### {t('confirm_title', lang)}")

    # Raw transcript (transparency, PRD F4)
    if st.session_state.get("transcript"):
        with st.expander(t("transcript_raw", lang), expanded=False):
            st.code(st.session_state["transcript"])

    # Needs-review warning
    if parsed.get("needs_review") and parsed.get("warnings"):
        warn_text = " · ".join(parsed["warnings"])
        st.markdown(
            f'<div class="av-warning">{t("needs_review", lang)}<br>'
            f'<small>{warn_text}</small></div>',
            unsafe_allow_html=True,
        )

    # Editable fields
    unit_map   = unit_selector_labels(lang)   # {canonical: label}
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
        new_item = st.text_input(
            t("item", lang),
            value=st.session_state["card_item"] or "",
            key="edit_item",
        )
        new_qty = st.number_input(
            t("qty", lang),
            min_value=0.0, step=0.5,
            value=float(st.session_state["card_qty"] or 0.0),
            format="%.2f",
            key="edit_qty",
        )
        new_unit_disp = st.selectbox(
            t("unit", lang),
            options=unit_disp,
            index=unit_idx,
            key="edit_unit",
        )

    with col2:
        new_price = st.number_input(
            t("price", lang),
            min_value=0.0, step=0.5,
            value=float(st.session_state["card_price"] or 0.0),
            format="%.2f",
            key="edit_price",
        )
        new_type_disp = st.selectbox(
            t("type", lang),
            options=type_disp,
            index=type_idx,
            key="edit_type",
        )

    # Resolve display back to canonical
    new_unit = unit_keys[unit_disp.index(new_unit_disp)]
    new_type = type_opts[type_disp.index(new_type_disp)]

    # Recompute total live
    new_total = compute_total(new_qty or None, new_price or None)
    total_str = f"₹ {new_total:,.2f}" if new_total is not None else "—"
    st.markdown(
        f'<div class="av-card" style="text-align:center;">'
        f'<div class="av-today-label">{t("total", lang)}</div>'
        f'<div class="av-today-amount">{total_str}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Read-back ─────────────────────────────────────────────────────────────
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
                except (RuntimeError, EnvironmentError) as exc:
                    st.warning(t("error_tts", lang).replace("{detail}", str(exc)))

        cached_wav = st.session_state["tts_cache"].get(rb_key)
        if cached_wav:
            st.audio(cached_wav, format="audio/wav", autoplay=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button(t("correct", lang), type="primary", use_container_width=True):
            if not new_item:
                _show_error(t("needs_review", lang))
            else:
                entry = build_entry_dict(new_item, new_qty, new_unit, new_price, new_type)
                try:
                    _db.save_entry(
                        entry, lang,
                        transcript=st.session_state.get("transcript", ""),
                        path=_DB,
                    )
                    st.session_state["saved_msg"] = t("saved", lang)
                    _clear_card()
                    st.rerun()
                except Exception as exc:
                    _show_error(t("error_save", lang).replace("{detail}", str(exc)))

    with btn_col2:
        # Rust Wrong button via custom CSS wrapper
        st.markdown('<div class="av-btn-wrong">', unsafe_allow_html=True)
        if st.button(t("wrong", lang), use_container_width=True):
            _clear_card()
            st.session_state["saved_msg"] = None
            st.session_state["error_msg"] = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# MANUAL ENTRY EXPANDER
# ════════════════════════════════════════════════════════════

with st.expander(t("manual_entry", lang)):
    st.caption(t("confirm_hint", lang))
    unit_map  = unit_selector_labels(lang)
    unit_keys = list(unit_map.keys())
    unit_disp = list(unit_map.values())

    mc1, mc2 = st.columns(2)
    with mc1:
        m_item  = st.text_input(t("item", lang),  key="m_item")
        m_qty   = st.number_input(t("qty", lang),   min_value=0.0, step=0.5, format="%.2f", key="m_qty")
        m_udisp = st.selectbox(t("unit", lang),    options=unit_disp, key="m_unit")
    with mc2:
        m_price = st.number_input(t("price", lang), min_value=0.0, step=0.5, format="%.2f", key="m_price")
        m_tdisp = st.selectbox(t("type", lang),
                               options=[t("sale", lang), t("purchase", lang)],
                               key="m_type")

    m_unit = unit_keys[unit_disp.index(m_udisp)]
    m_type = "sale" if m_tdisp == t("sale", lang) else "purchase"
    m_total = compute_total(m_qty or None, m_price or None)
    if m_total:
        st.markdown(f"**{t('total', lang)}: ₹ {m_total:,.2f}**")

    if st.button(t("manual_save", lang), key="btn_manual_save"):
        if not m_item:
            _show_error(t("needs_review", lang))
        else:
            entry = build_entry_dict(m_item, m_qty, m_unit, m_price, m_type)
            try:
                _db.save_entry(entry, lang, transcript="[manual entry]", path=_DB)
                st.session_state["saved_msg"] = t("saved", lang)
                st.rerun()
            except Exception as exc:
                _show_error(t("error_save", lang).replace("{detail}", str(exc)))


# ════════════════════════════════════════════════════════════
# LEDGER TABLE
# ════════════════════════════════════════════════════════════

st.markdown(f"### {t('ledger_title', lang)}")

df = _db.entries_dataframe(lang, _DB)

if df.empty or len(df) == 0:
    st.info(t("empty_table", lang))
else:
    st.dataframe(df, use_container_width=True, hide_index=True)

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

    # Delete last entry with confirm step
    st.markdown("---")
    if not st.session_state.get("delete_pending"):
        if st.button(t("delete_last", lang)):
            st.session_state["delete_pending"] = True
            st.rerun()
    else:
        st.markdown(
            f'<div class="av-warning">{t("delete_confirm", lang)}</div>',
            unsafe_allow_html=True,
        )
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button(t("delete_last", lang), key="confirm_del"):
                ok = _db.delete_last_entry(_DB)
                st.session_state["delete_pending"] = False
                st.session_state["saved_msg"] = (
                    t("delete_done", lang) if ok else t("nothing_to_delete", lang)
                )
                st.rerun()
        with dc2:
            if st.button(t("wrong", lang), key="cancel_del"):
                st.session_state["delete_pending"] = False
                st.rerun()


# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"### ArthVani")
    st.caption(t("powered_by", lang))
    st.markdown("---")

    if st.button(t("demo_data", lang), use_container_width=True):
        _db.seed_demo_entries(_DB)
        st.session_state["saved_msg"] = t("demo_loaded", lang)
        st.rerun()
    st.caption("⚠ " + ("Demo entries are synthetic and do not represent real transactions."
                        if lang == "en" else
                        "डेमो एंट्री नकली हैं, असली लेनदेन नहीं।"))

    st.markdown("---")
    st.info(t("privacy_note", lang))
