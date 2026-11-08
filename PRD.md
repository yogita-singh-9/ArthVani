# ArthVani — Product Requirements Document

**Tagline:** बोलिए, हिसाब हो जाएगा. (Speak, and the ledger is done.)
**Version:** 1.0 (contest MVP)
**Contest:** Gnani AI — The Great Indian AI Internship Challenge
**Submission deadline:** Nov 10, 2026, 11:59 PM IST (aim to submit by Nov 9)

*Name meaning: **Arth** (अर्थ — money, meaning) + **Vani** (वाणी — voice).*

---

## 1. Summary

ArthVani is a voice-first ledger for small shops and street vendors. The shopkeeper taps one button and says a sale in Hindi or English, for example:

> "50 kilo chawal, 60 rupaye kilo"

ArthVani listens, understands the item, quantity and price, works out the total, reads the entry back for confirmation, and saves it in a neat table with the date and time. The table can be downloaded as Excel/CSV.

It is built on Gnani AI's speech models:

- **Prisma** (speech-to-text) to hear the shopkeeper, including noisy and phone-quality audio.
- **Timbre** (text-to-speech) to read the entry back in Hindi or English.

## 2. Problem

Small shopkeepers and vendors keep paper khatas or nothing at all. Their hands are busy, the surroundings are noisy, many are more comfortable speaking than typing, and many are more comfortable in Hindi than English. Most billing apps need typing and English menus, so people skip record-keeping, and then cannot see what they sold, earned or are owed.

## 3. Target users

- **Primary:** kirana/general store owners, vegetable and fruit vendors, small mandi traders, street food sellers.
- **Secondary:** their helpers and family members who write the khata.

Assumed context: noisy environment, low typing comfort, a mid-range phone or a shared laptop, Hindi-first, some English.

## 4. Goals and non-goals

### Goals (MVP)

1. Record a sale by voice in Hindi or English in under ~6 seconds end to end.
2. Work for **any item**, not a fixed product list.
3. Show every entry in a clean table with **date and time**, in the user's chosen language.
4. Let the user confirm or correct an entry before it is saved.
5. Export the table to Excel/CSV.
6. Demonstrate honest accuracy numbers on clean, noisy and phone-quality audio.

### Non-goals (do not build)

- User accounts or login
- Cloud database or sync
- Native mobile app (React Native, etc.)
- Payments, GST invoices, inventory or stock tracking
- Languages other than Hindi and English
- Any real customer data, real phone numbers, or recordings of real calls (use synthetic data and the team's own voices only)

## 5. Key user flow

1. User opens ArthVani and picks a language (Hindi / English) in the sidebar.
2. User taps the large round **Speak / बोलिए** button and says an entry.
3. App sends the audio to Gnani speech-to-text with the selected language code.
4. App extracts **item, quantity, unit, price** from the text.
5. App calculates **total = quantity × price in code** (never by a language model).
6. App shows a confirmation card with editable fields and **reads the entry aloud** using Gnani text-to-speech: "50 किलो चावल, 60 रुपये किलो, कुल 3000 रुपये। सही है?"
7. User taps **Correct / सही है** (saved) or **Wrong / गलत है** (re-record or edit fields manually).
8. The entry appears at the top of the ledger table; "Today's total" updates.
9. User can download the table as Excel or CSV.

## 6. Functional requirements

Priority: **P0** = must ship, **P1** = should ship if time allows, **P2** = stretch.

| ID | Requirement | Priority |
|---|---|---|
| F1 | Language selector (Hindi, English) in sidebar; drives STT language code, TTS voice, and UI text | P0 |
| F2 | Mic button capturing audio in the browser (Streamlit `st.audio_input`) | P0 |
| F3 | Call Gnani STT (`POST https://api.vachana.ai/stt/v3`, multipart, header `X-API-Key-ID`, fields `audio_file` and `language_code`, max 60 s) | P0 |
| F4 | Show the raw transcript to the user for transparency | P0 |
| F5 | Extract item, quantity, unit, price from the transcript (see section 8) | P0 |
| F6 | Compute total in Python | P0 |
| F7 | Confirmation card with **editable** item, quantity, unit, price, total | P0 |
| F8 | Call Gnani TTS (`POST https://api.vachana.ai/api/v1/tts/inference`, JSON with `text` and `voice`) to read the entry back and play it | P0 |
| F9 | Save confirmed entries in SQLite with timestamp, language, transcript | P0 |
| F10 | Ledger table, newest first, with translated column headings | P0 |
| F11 | "Today's total" shown above the table | P0 |
| F12 | Download table as Excel (.xlsx) and CSV | P0 |
| F13 | Friendly error messages for network, API, empty-audio and parse failures (never show a raw stack trace to the user) | P0 |
| F14 | Entry type: Sale or Purchase (detect "becha / sold" vs "kharida / bought"; default Sale) | P1 |
| F15 | Voice confirmation ("haan" / "nahi") instead of buttons | P2 |
| F16 | Voice query: "aaj ka kul kitna hua?" answered aloud | P2 |
| F17 | Delete or edit a saved entry | P1 |

## 7. Language and localization

- Languages: **Hindi (hi-IN)** and **English** (verify the exact English language code on the Gnani STT docs page; likely `en-IN`).
- Items are stored **exactly as transcribed**, in the script they were spoken in. Do not auto-translate item names.
- Dates are stored as ISO timestamps and displayed as **DD-MM-YYYY** with 24-hour time, in both languages.
- UI strings live in one dictionary (`strings.py`) keyed by language. Minimum set:

| Key | English | हिंदी |
|---|---|---|
| speak | Speak | बोलिए |
| date | Date | तारीख |
| time | Time | समय |
| item | Item | सामान |
| qty | Quantity | मात्रा |
| unit | Unit | इकाई |
| price | Price | दाम |
| total | Total | कुल |
| type | Type | प्रकार |
| today_total | Today's total | आज का कुल |
| correct | Correct | सही है |
| wrong | Wrong | गलत है |
| download | Download Excel | Excel डाउनलोड करें |

Unit labels: kg / किलो, litre / लीटर, piece / नग, dozen / दर्जन, packet / पैकेट, gram / ग्राम.

## 8. Understanding speech (extraction)

**Approach for MVP: deterministic rule-based parser** (no outside language model). It must be predictable and testable.

Supported spoken patterns (Hindi/Hinglish and English):

1. `<qty> <unit> <item> <price> rupaye [per unit]`
   - "50 kilo chawal 60 rupaye kilo"
   - "5 kg rice 60 rupees per kg"
2. `<item> <qty> <unit> <price> ...`
   - "chawal 50 kilo 60 rupaye kilo"
3. Count items: `<qty> <item> <price> rupaye [each]`
   - "12 sabun 30 rupaye ka ek"

Rules:

- Numbers can arrive as digits or words. Support Hindi and English number words, and the common fractions **dedh (1.5), dhai (2.5), sava (1.25), aadha (0.5)**, plus sau and hazaar. Check what Gnani STT actually returns (digits vs words, Devanagari vs Roman) and build the parser around real output.
- **Item = the leftover words** after numbers, units, currency words and filler words (becha, aaj, ka, ki, rupaye, per, each, etc.) are removed. This lets any item work without a fixed list.
- A small configurable filler-word list lives in `parser.py`.
- If the parser is not confident, it must **not guess silently**. It shows the confirmation card with the fields it did find and lets the user fix the rest.
- Arithmetic is always plain Python: `total = quantity * price`.

Optional later (P2): an LLM fallback for sentences the parser cannot read. **Only add this if the contest terms allow an outside model**, and name it in the submission. Not part of the MVP.

## 9. Data model

SQLite file `arthvani.db`, one table:

```sql
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,      -- ISO 8601, local time
    entry_type  TEXT DEFAULT 'sale',-- 'sale' or 'purchase'
    item        TEXT NOT NULL,      -- as spoken, original script
    quantity    REAL NOT NULL,
    unit        TEXT,
    price       REAL NOT NULL,      -- per unit
    total       REAL NOT NULL,      -- quantity * price, computed in code
    language    TEXT NOT NULL,      -- 'hi' or 'en'
    transcript  TEXT                -- raw speech-to-text result
);
```

Export columns: Date, Time, Type, Item, Quantity, Unit, Price, Total, Language (headings in the selected UI language).

## 10. Technical stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Fastest to build, Gnani examples are Python |
| UI | Streamlit | Mic, table, dropdown and download in one file |
| Speech APIs | Gnani Prisma (STT), Gnani Timbre (TTS) via `requests` | Required by the contest; direct calls are easy to debug |
| Parsing | Python `re`, word dictionaries, `rapidfuzz` | Deterministic, no outside model |
| Storage | SQLite + pandas | Zero setup, works offline, easy Excel export |
| Excel export | `openpyxl` | Writes .xlsx |
| Config | `python-dotenv` | Reads the API key from a local `.env` |
| Testing | `pytest`, `pydub` + `ffmpeg`, `numpy` | Accuracy tests with noise and 8 kHz phone simulation |

### Repository layout

```
arthvani/
├── PRD.md
├── README.md
├── app.py              # Streamlit UI
├── gnani.py            # stt() and tts() wrappers
├── parser.py           # numbers, units, filler words, parse()
├── db.py               # SQLite save/load/export
├── strings.py          # Hindi/English UI text
├── theme.css           # design system styles
├── .streamlit/config.toml
├── tests/
│   ├── test_parser.py
│   ├── sentences.csv   # 30 test sentences with expected results
│   └── noise_eval.py   # mixes noise, downsamples to 8 kHz, scores accuracy
├── .env                # GNANI_API_KEY=...   (never committed, never read by agents)
├── .gitignore
└── requirements.txt
```

## 11. Design system: "Royal Rose"

Inspired by a luxury fintech aesthetic meeting Indian boutique warmth. Built on rich plum, raspberry, rose pinks, pearl whites, and antique gold accents.

### Colour palette

| Role | Name | Hex | Use |
|---|---|---|---|
| Ink / Dark | Royal Plum | `#3A0F2E` → `#5B1A46` | Sidebar gradient, table header, dark panels, headings |
| Primary Action | Raspberry | `#B8336A` | Primary buttons, active nav pills, key highlights, total amount |
| Accent / Hover | Rose | `#E85D9A` | Waveforms, charts, hover accents, focus rings |
| Highlight / Tint | Blush & Petal | `#F8C8DC` / `#FDE8F1` | Card borders, subtle zebra striping, tags |
| Background | Pearl White | `#FFF7FB` / `#FFFFFF` | Page canvas, card surfaces |
| Premium Accent | Antique Gold | `#C9A227` | Badges, icons, logo accents, active language pill |
| Semantic Success | Emerald | `#2E9E73` | Sale pills, success toast, confirmed states |
| Semantic Danger | Crimson | `#D6334F` | Delete actions, error toasts |
| Semantic Warning | Marigold | `#E0A020` | Review needed alerts |

### Usage rules

- Main text is **`#2A1020` on pearl/white** (high contrast, ≥ 4.5:1).
- Secondary text is **`#7A5568`** for captions and helper labels.
- Keep body text at 16 px or larger, tap targets at least 48 px.
- 16–20 px corner radii on cards and modal dialogs.
- **Speak button:** 120 px circle with breathing ambient glow when idle, pulsing ripples and real-time frequency waveform when recording.
- Table: sticky plum header, petal zebra rows, bold raspberry totals.
- Fonts: **Playfair Display** (headings), **Poppins** (body), and **Noto Sans Devanagari** (Hindi text with 1.8 line height).
- Responsive layout: desktop collapsible sidebar (240 px) and mobile fixed bottom tab bar (≤ 640 px).

---

## 12. Non-functional requirements

- **Latency:** speak-to-confirmation under ~6 seconds on a normal connection.
- **Reliability:** an API failure must show a friendly message and keep the app usable.
- **Privacy:** audio is sent only to Gnani's API for transcription and is not stored on disk after the request. Only the confirmed entry and its transcript are stored locally.
- **Security:** the API key is read from `.env` (or an environment variable) only. Never hardcode it, print it, log it, or commit it. `.env` and `*.db` are in `.gitignore`.
- **Data:** use only synthetic or consented data. No real customer details, phone numbers, Aadhaar/PAN, or call recordings.
- **Accessibility:** large buttons, readable contrast, Hindi font rendering works on common phones.

## 13. Success metrics (reported in the demo and submission)

Measured on a 30-sentence test set (mix of Hindi and English, varied items, number words), recorded by the team and friends with their consent:

| Condition | Metric |
|---|---|
| Clean audio | Entries fully correct (item, qty, price, total) out of 30, per language |
| Medium background noise | Same |
| Loud background noise | Same |
| Phone-quality (8 kHz) + noise | Same |

Report honest numbers, including failures. Only claim languages and conditions that were actually tested.

## 14. Contest alignment

| Contest requirement | How ArthVani meets it |
|---|---|
| Built on Gnani AI models/APIs | Prisma (STT) and Timbre (TTS) are core to the flow |
| Working application | Streamlit app, runs locally and can be deployed |
| Public demo video | 60-second video, subtitles included |
| Public post | LinkedIn and/or X with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**, tagging Gnani AI, posted **before** submitting |
| Each member's contribution | Documented in submission and README |
| Authentic engagement only | No bought votes, bots, or engagement exchanges |
| Synthetic data only | Team voices and made-up transactions |

Target awards: **Real Deal** (practical problem for shopkeepers) and **Noise Canceller** (noisy and phone-quality audio results). Mention the city in the submission if the team's college is in a Tier 2/3 town (Small Town, Big Build). An entry can win only one award.

## 15. Demo plan (60 seconds)

1. **0–8 s:** the problem — a messy paper khata and a busy shopkeeper (one line of text on screen).
2. **8–30 s:** in Hindi, with market noise playing nearby, speak two entries; show the confirmation card and the spoken read-back.
3. **30–42 s:** switch to English and add one entry.
4. **42–52 s:** show the ledger table with dates and the Excel download.
5. **52–60 s:** show the accuracy numbers (clean vs noisy vs phone-quality) and end on the ArthVani logo and hashtags.

Add subtitles (most people watch muted). Show one honest limitation.

## 16. Build plan

| When | Work |
|---|---|
| Nov 7 | Register, create key, test STT and TTS, build full voice loop with parser and SQLite |
| Nov 8 | Streamlit UI and theme, language switch, export, test set and noise evaluation, record demo |
| Nov 9 | Post the demo early so engagement can build; finish submission text; submit |
| Nov 10 | Buffer only. Do not plan to submit at 11:59 PM |

## 17. Acceptance checklist

- [x] Sidebar + tabs (Dashboard, Speak, Ledger, Reports, Settings) work; mobile bottom tab bar works
- [x] Royal pink/white theme applied everywhere, no leftover cream/teal styling
- [x] Hindi voice entry → transcript → parsed → review → read-back audio → saved; English the same
- [x] Unreadable sentence → editable highlighted fields, no crash, no silent wrong entry
- [x] Save / Re-record / Discard / Undo all work; old Correct/Wrong and "Delete last entry" removed
- [x] Demo data is varied, realistic, non-duplicated, idempotent; Clear demo data works; real entries untouched
- [x] Ledger search/filter/sort/paginate/edit/delete all work and persist; totals always qty × price in Python
- [x] Dashboard + Reports numbers match the ledger exactly
- [x] Excel + CSV exports correct with Hindi intact (UTF-8 with BOM)
- [x] Language switch updates all UI text, STT code, TTS voice instantly
- [x] Friendly errors for every failure path; no key anywhere in code/logs/responses/git
- [x] Responsive layout across 390 px (mobile), 768 px (tablet), and 1440 px (desktop); zero console errors
- [x] pytest green (141 passed); accuracy numbers recorded honestly

## 18. Risks and mitigations

| Risk | Mitigation |
|---|---|
| STT output format or language code differs from assumptions | Print one real response first and build the parser around it; check Gnani docs for codes |
| Parser misses unusual phrasing | Editable confirmation card; list supported patterns in the README |
| Voice names/params for TTS differ | Check the Voice Options and TTS REST pages in Gnani's docs |
| Noise results are worse than hoped | Report them honestly; show the improvement from the confirmation step |
| Little time for engagement to build | Post by Nov 8–9, write a short human story, share organically |
| Streamlit Cloud resets the SQLite file | Seed demo entries before recording; call the database demo data |
| Contest rules on tools/models | Check the registration terms or ask on Gnani's Discord; disclose tools used honestly |

## 19. Open questions

1. What is the exact English language code and the best Hindi and English TTS voices in Gnani's docs?
2. Do the contest terms allow an outside language model (for the P2 fallback) and AI coding tools? If unclear, ask on Discord and disclose.
3. Does Gnani STT return digits or number words, and in which script, for Hindi?
