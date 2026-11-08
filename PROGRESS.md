# ArthVani — Build Progress

> Last updated: 2026-11-08  
> Contest Deadline: Nov 10, 2026, 11:59 PM IST

## Phase Checklist

| Step | Description | Status |
|------|-------------|--------|
| Phase 1 | `gnani.py` — STT + TTS wrappers (HTTP 200 confirmed, serialization lock, retry) | ✅ Done |
| Phase 2 | `parser.py` + `speech_text.py` + tests (rule-based parser, fractions, readback) | ✅ Done |
| Phase 3 | `db.py` SQLite persistence, auto-migration for `is_demo`, Excel/CSV exports | ✅ Done |
| Phase 4 | Full FastAPI backend (`main.py` + `run.py`) exposing 14 REST endpoints | ✅ Done |
| Phase 5 | Vanilla JS SPA in `/static` (`index.html`, `styles.css`, `app.js`) with **Royal Rose** design system | ✅ Done |
| Phase 6 | Realistic 30-day demo dataset (~92 entries across staples, dairy, veggies, packaged) | ✅ Done |
| Phase 7 | Test expansion: 141 pytest tests passing across API, DB, parser, gnani mocks, helpers | ✅ Done |
| Phase 8 | Security audit: zero secret leaks in code, logs, repo, or API responses | ✅ Done |

---

## Test Results (Full Suite: 141 Passed)

```
============================ 141 passed in 4.08s ==============================

tests/test_api.py: 24 passed
  ✓ /api/health returns 200 with status ok and api_key_configured
  ✓ /api/i18n/{lang} returns localized UI text, unit options, and unit labels
  ✓ /api/parse-text parses Hindi, English, flags incomplete sentences
  ✓ /api/entries CRUD (create, list, filter by type, search item, update price, delete)
  ✓ /api/summary returns today stats, 14-day series, top items, recent rows
  ✓ /api/export.xlsx returns valid OpenPyXL spreadsheet
  ✓ /api/export.csv returns UTF-8 BOM CSV compatible with Microsoft Excel
  ✓ /api/transcribe handles empty audio (400) and mocked STT pipeline
  ✓ /api/tts returns raw audio bytes
  ✓ /api/demo/load is idempotent (never creates duplicates)
  ✓ /api/demo/clear deletes only demo entries

tests/test_app_logic.py: 16 passed
  ✓ audio_hash deterministic, unique, empty bytes handled
  ✓ compute_total arithmetic, 2-decimal rounding, None handling, zero handling
  ✓ build_entry_dict output schema, code-recomputed total
  ✓ readback_cache_key stability, language and value sensitivity
  ✓ strings.t fallback behavior and unit_selector_labels completeness

tests/test_db.py: 39 passed
  ✓ init_db idempotent and creates table
  ✓ save_entry and list_entries in newest-first order
  ✓ total always recomputed in Python code (quantity * price)
  ✓ Hindi text round-trips with exact Devanagari characters
  ✓ today_total calculates only today's sales (ignores purchases)
  ✓ update_entry recomputes total on price or quantity change
  ✓ delete_entry and delete_last_entry functionality
  ✓ entries_dataframe with localized DD-MM-YYYY dates and translated headings
  ✓ export_xlsx non-empty openpyxl binary
  ✓ export_csv with UTF-8 BOM (\xef\xbb\xbf) for Excel Devanagari rendering
  ✓ seed_demo_entries creates 92 realistic synthetic demo entries
  ✓ seed_idempotent ensures seed cannot duplicate data
  ✓ clear_demo_entries leaves real user entries intact
  ✓ is_demo column auto-migrated without data loss
  ✓ input validation (missing item, quantity, or price raises ValueError)

tests/test_gnani.py: 15 passed
  ✓ stt success, 401 unauthorized, 429 rate limit, 500 server error, timeout, network error
  ✓ tts success, 429 retry logic, 401 unauthorized, timeout, empty content
  ✓ number_to_words for Hindi and English
  ✓ missing API key raises EnvironmentError

tests/test_parser.py: 47 passed
  ════════════════════════ Parser test summary (Phase 2) ════════════════════════
    Total rows in sentences.csv : 42
      Complete (item+qty+price)  : 39  →  39 passed, 0 failed
      Needs-review (incomplete)  : 3  →  3 correctly flagged  ✓ all correct

    By language (complete rows only):
      English  total=17  complete=15 (15 passed, 0 failed)  needs-review=2
      Hindi    total=25  complete=24 (24 passed, 0 failed)  needs-review=1

    By source:
      real        2 passed, 0 failed ← actual Gnani STT output
      synthetic   37 passed, 0 failed ← hand-crafted

    Needs-review rows (3 expected, 3 correctly flagged):
      ✓  [hi] 'चावल बेचा'
      ✓  [en] 'fifty rupees'
      ✓  [en] 'rice kilo'
```

---

## Architecture Summary

- **Backend**: FastAPI + Uvicorn server (`main.py`, `run.py`).
- **Frontend**: Vanilla JS SPA in `/static` (`index.html`, `styles.css`, `app.js`).
- **Palette**: Royal Rose (Royal Plum `#3A0F2E`, Raspberry `#B8336A`, Rose `#E85D9A`, Pearl `#FFF7FB`, White `#FFFFFF`, Antique Gold `#C9A227`).
- **Persistence**: SQLite with parameterized queries, auto-migration, and `is_demo` separation.
- **Speech Stack**: Gnani AI Prisma STT (`hi-IN`, `en-IN`) + Gnani AI Timbre TTS (`timbre-v2.5`, voices Nalini & Kaveri).
