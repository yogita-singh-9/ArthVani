# ArthVani — Build Progress

> Last updated: 2026-11-07  
> Contest Deadline: Nov 10, 2026, 11:59 PM IST

## Phase Checklist

| Step | Description | Status |
|------|-------------|--------|
| Phase 1 | gnani.py — STT + TTS wrappers (HTTP 200 confirmed) | ✅ Done |
| Phase 2 | parser.py + speech_text.py + tests (35/35 passing) | ✅ Done |
| Step 0  | Verification pass: source column in sentences.csv, honest test summary hook, Python 3.14 audioop-lts check | ✅ Done |
| Step 1  | strings.py (hi/en UI dictionary) + db.py (SQLite, parameterized queries, Excel & CSV exports) + tests/test_db.py (35/35 passing) | ✅ Done |
| Step 2  | gnani.py hardening (_API_LOCK concurrency serialization, 3s retry with backoff, st.secrets fallback, friendly errors) | ✅ Done |
| Step 3  | theme.css (Kirana teal & rust palette, Poppins & Noto Sans Devanagari) + app.py (Streamlit frontend) + app_helpers.py | ✅ Done |
| Step 4  | tests/noise_eval.py + recordings/labels.csv + results/.gitkeep (CLI with --dry-run, --yes, --max-calls, 6 noise conditions) | ✅ Done |
| Step 5  | README.md (Comprehensive documentation, architecture, run guide, sentence patterns, limitations, privacy) | ✅ Done |
| Pure Logic Tests | tests/test_app_logic.py (16/16 tests for audio_hash, compute_total, build_entry_dict, readback_cache_key) | ✅ Done |

---

## Test Results (Full Suite)

```
============================= 86 passed in 1.50s ==============================

tests/test_app_logic.py: 16 passed
  ✓ audio_hash deterministic, unique, empty bytes handled
  ✓ compute_total arithmetic, 2-decimal rounding, None handling, zero handling
  ✓ build_entry_dict output schema, code-recomputed total
  ✓ readback_cache_key stability, language and value sensitivity
  ✓ strings.t fallback behavior and unit_selector_labels completeness

tests/test_db.py: 35 passed
  ✓ init_db idempotent and creates table
  ✓ save_entry and list_entries in newest-first order
  ✓ total always recomputed in Python code
  ✓ Hindi text round-trips with exact Devanagari characters
  ✓ today_total calculates only today's sales (ignores purchases)
  ✓ update_entry recomputes total on price or quantity change
  ✓ delete_entry and delete_last_entry functionality
  ✓ entries_dataframe with localized DD-MM-YYYY dates and translated headings
  ✓ export_xlsx non-empty openpyxl binary
  ✓ export_csv with UTF-8 BOM (\xef\xbb\xbf) for Excel Devanagari rendering
  ✓ seed_demo_entries creates 5 valid synthetic demo entries
  ✓ input validation (missing item, quantity, or price raises ValueError)

tests/test_parser.py: 35 passed
  ════════════════════════ Parser test summary (Phase 2) ════════════════════════
    Total rows in sentences.csv : 30
      Complete (item+qty+price)  : 27  →  27 passed, 0 failed
      Needs-review (incomplete)  : 3  →  3 correctly flagged  ✓ all correct

    By language (complete rows only):
      English  total=12  complete=10 (10 passed, 0 failed)  needs-review=2
      Hindi    total=18  complete=17 (17 passed, 0 failed)  needs-review=1

    By source:
      real        2 passed, 0 failed ← actual Gnani STT output
      synthetic   25 passed, 0 failed ← hand-crafted

    Needs-review rows (3 expected, 3 correctly flagged):
      ✓  [hi] 'चावल बेचा'
      ✓  [en] 'fifty rupees'
      ✓  [en] 'rice kilo'
```

---

## Noise Evaluation CLI Status

- Tested in dry-run mode: `python tests/noise_eval.py --dry-run` ✅
- Generates evaluation plan for 6 conditions:
  - `clean` (raw recording)
  - `noise_15dB` (moderate background noise)
  - `noise_5dB` (loud market noise)
  - `noise_0dB` (extreme noise)
  - `phone_clean` (8 kHz narrowband AMR/G.711 simulation)
  - `phone_noise_5dB` (8 kHz phone line + 5 dB market noise)
- Synthetic noise fallback works if `noise/market.wav` is not provided.

---

## Environment & Dependency Notes

- **Python**: 3.14 on Windows
- **`audioop-lts`**: Installed and pinned in `requirements.txt` to support `pydub` on Python 3.13+.
- **`ffmpeg`**: Not currently installed on the host system.
  - To install on Windows: `winget install Gyan.FFmpeg`
  - Required for `noise_eval.py`'s phone-codec simulation (8 kHz resample) and `.m4a` file decoding.
  - App interface and SQLite database run without ffmpeg.
- **Security**: `.gitignore` configured to ignore `.env`, `*.db`, `*.wav`, `*.m4a`, `*.mp3`, `noise/`, `recordings/*`, and `results/*`.
