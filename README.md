# ArthVani — अर्थवाणी

> **बोलिए, हिसाब हो जाएगा.**  
> *Speak, and the ledger is done.*

ArthVani is a **voice-first ledger application** designed specifically for Indian micro-merchants — kirana stores, vegetable vendors, mandi traders, and street food stalls. Instead of tedious manual bookkeeping or paper *bahi-khata*, shopkeepers simply speak transactions naturally in Hindi or English. ArthVani transcribes the voice, deterministically parses transaction fields, reads back the entry for auditory confirmation, and maintains a clean local ledger with financial reports and Excel exports.

Built for the **Gnani AI Great Indian AI Internship Challenge 2026**.

---

## 📸 Architecture & Design

ArthVani features a modern, ultra-responsive Single Page Application (SPA) architecture styled with the bespoke **Royal Rose** design system (Royal Plum `#3A0F2E`, Raspberry `#B8336A`, Rose `#E85D9A`, Pearl `#FFF7FB`, and Antique Gold `#C9A227`).

```
┌─────────────────────────────────────────────────────────────┐
│                     ArthVani Frontend (SPA)                 │
│      Vanilla JS (ES Modules) · HTML5 · Custom CSS           │
│   Dashboard · Voice Entry (Mic/Waveform) · Ledger · Reports  │
└──────────────────────────────┬──────────────────────────────┘
                               │ JSON / Audio Blobs
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (run.py)                  │
│       Endpoints: /api/transcribe, /api/entries, etc.        │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      Gnani AI Services       │ │     Local SQLite DB        │
│  Prisma STT (hi-IN, en-IN)   │ │  Parameterized SQL queries │
│  Timbre TTS (Nalini, Kaveri) │ │  is_demo tracking, exports │
└──────────────────────────────┘ └────────────────────────────┘
```

---

## ✨ Key Features

1. **Voice-First Workflow with Stepper**:
   - Tap-to-record or press `Spacebar` to speak.
   - Real-time Web Audio API frequency waveform visualizer.
   - 4-stage pipeline stepper: *Listening → Understanding → Reading back → Saved*.
   - Live editable **Review Card** with instant server-backed total recalculation.
   - Audio read-back automatically played via Gnani Timbre TTS with instant replay.
   - 5-second **Undo** toast for safe transaction logging.

2. **Royal Rose Design System**:
   - Elegant Indian boutique aesthetic blending luxury fintech with shopkeeper simplicity.
   - Typography: *Playfair Display* serif headings, *Poppins* body, and *Noto Sans Devanagari* for authentic Hindi script rendering.
   - Accessible contrast (≥ 4.5:1), responsive layout with desktop sidebar and mobile bottom tab bar (≤ 640px).

3. **Complete Financial Ledger (बही-खाता)**:
   - Full search, filter by transaction type (Sale / Purchase), date range presets (Today, 7 days, 30 days, custom).
   - In-place row editing with modal dialog and safe deletion.
   - Instant one-click **Excel (.xlsx)** and **CSV (with UTF-8 BOM for Microsoft Excel)** exports.

4. **Dynamic Reports & Analytics**:
   - 14-day interactive sales vs. purchases chart.
   - Top-selling items bar breakdown and basket metrics.
   - Net profit / cash-flow summary.

5. **Realistic Demo Data System**:
   - 1-click idempotent loader generating ~92 realistic transactions spread over 30 days across genuine Indian shop items (चावल, आटा, दाल, तेल, दूध, पनीर, मसाले, साबुन, बिस्किट).
   - Dedicated `is_demo` tracking allows clearing demo entries anytime without touching real data.

---

## 🔊 Gnani AI Models & Configuration

| Service | Model / Engine | Language Code | Voice |
|---|---|---|---|
| **Speech-to-Text (STT)** | Gnani AI **Prisma** | `hi-IN` (Hindi), `en-IN` (English) | — |
| **Text-to-Speech (TTS)** | Gnani AI **Timbre v2.5** | `hi-IN` | **Nalini** |
| **Text-to-Speech (TTS)** | Gnani AI **Timbre v2.5** | `en-IN` | **Kaveri** |

---

## 🚀 Quickstart & One-Command Run

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/yogita-singh-9/ArthVani.git
cd ArthVani

# Python 3.10+ (tested on Python 3.14)
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Key

Copy `.env.example` to `.env` and insert your Gnani API key:

```bash
cp .env.example .env
```

Ensure `.env` contains:
```ini
GNANI_API_KEY=your_gnani_key_here
```

### 4. Launch Application

```bash
python run.py
```

Open your browser at **http://localhost:8000**!

---

## 📡 REST API Reference

The FastAPI backend exposes the following clean JSON and streaming endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the single-page application (`static/index.html`) |
| `GET` | `/api/health` | Healthcheck and API key configuration status |
| `GET` | `/api/i18n/{lang}` | Bilingual string table and unit configuration |
| `POST` | `/api/transcribe` | Multipart audio upload → Gnani Prisma STT → parser → readback |
| `POST` | `/api/parse-text` | Parse typed text fallback using the deterministic rule parser |
| `POST` | `/api/tts` | Convert read-back text into WAV audio bytes via Gnani Timbre |
| `GET` | `/api/entries` | List transactions with filters (`search`, `filter`, `limit`, `offset`, `sort`, `date_from`, `date_to`) |
| `POST` | `/api/entries` | Save confirmed transaction to SQLite |
| `PUT` | `/api/entries/{id}` | Update transaction fields (total recalculated in Python) |
| `DELETE` | `/api/entries/{id}` | Delete transaction by ID |
| `GET` | `/api/summary` | Today/week stats, 14-day time series, top items, and recent rows |
| `GET` | `/api/export.xlsx` | Download ledger as formatted Excel sheet |
| `GET` | `/api/export.csv` | Download ledger as Excel-compatible CSV (UTF-8 with BOM) |
| `POST` | `/api/demo/load` | Idempotently seed ~92 realistic 30-day demo transactions |
| `POST` | `/api/demo/clear` | Remove only demo transactions (`is_demo=1`) |

---

## 🗣️ Supported Sentence Patterns

ArthVani uses a deterministic, rule-based parser that handles numbers, fractions, colloquial units, Hindi Devanagari, English, and Hinglish.

### Hindi Examples
- `50 किलो चावल ₹60 किलो` → Item: चावल, Qty: 50, Unit: kg, Price: ₹60, Total: ₹3,000 (Sale)
- `दो लीटर दूध पचपन रुपये लीटर` → Item: दूध, Qty: 2, Unit: litre, Price: ₹55, Total: ₹110 (Sale)
- `डेढ़ किलो पनीर 300 रुपये` → Item: पनीर, Qty: 1.5, Unit: kg, Price: ₹300, Total: ₹450 (Sale)
- `पचास किलो आटा अड़तीस रुपये किलो खरीदा` → Item: आटा, Qty: 50, Unit: kg, Price: ₹38, Total: ₹1,900 (Purchase)
- `50 किलो चावल कुल 3000` → Item: चावल, Qty: 50, Unit: kg, Derived Rate: ₹60, Total: ₹3,000

### English / Hinglish Examples
- `50 kilo rice 60 rupees per kilo` → Item: rice, Qty: 50, Unit: kg, Price: ₹60, Total: ₹3,000
- `two dozen banana sixty rupees per dozen` → Item: banana, Qty: 2, Unit: dozen, Price: ₹60, Total: ₹120
- `twelve pieces soap thirty rupees each` → Item: soap, Qty: 12, Unit: piece, Price: ₹30, Total: ₹360
- `20 kg sugar 44 rupees bought` → Item: sugar, Qty: 20, Unit: kg, Price: ₹44, Total: ₹880 (Purchase)

### Fractions & Scale Words
- `aadha` / `आधा` / `half` → `0.5`
- `sava` / `सवा` / `quarter` → `1.25`
- `dedh` / `डेढ़` → `1.5`
- `dhai` / `ढाई` → `2.5`
- `sau` / `हज़ार` / `lakh` / `hundred` / `thousand`

---

## 🧪 Testing & Verification

The test suite includes unit, database, parser, and API integration tests:

```bash
# Run the complete test suite (141 tests)
python -m pytest tests -v --tb=short
```

### Test Breakdown
- `tests/test_api.py` (24 tests): FastAPI endpoints, validation, export formats, error handling.
- `tests/test_db.py` (39 tests): CRUD operations, pagination, auto-migration, `is_demo` tracking, idempotency, date-sorted ordering.
- `tests/test_gnani.py` (15 tests): Gnani wrapper error paths, HTTP 401/429/500, timeouts, retries, number-to-words.
- `tests/test_parser.py` (47 tests): 42 parametrized sentences across Hindi and English + unit tests for fractions and readback.
- `tests/test_app_logic.py` (16 tests): Pure mathematical helpers, INR formatting, audio hash generation.

### Accuracy Evaluation

| Evaluation Dataset | Scope | Accuracy / Status |
|---|---|---|
| **Synthetic Sentences (`tests/sentences.csv`)** | 42 sentences (Hindi, English, Hinglish, incomplete) | **100% logic pass** (39 complete correct, 3 flagged for review) |
| **Real Gnani STT Transcripts (Clean)** | Verified against live Prisma STT outputs | **100% item, qty, unit, price match** |
| **Noise Evaluation (`tests/noise_eval.py`)** | Multi-SNR (clean, 15 dB, 5 dB, 0 dB, 8 kHz telephony) | Automated harness included; requires `ffmpeg` installed for local audio synthesis. |

> *Note: To run `tests/noise_eval.py` locally with synthetic audio, install `ffmpeg` (`winget install Gyan.FFmpeg` on Windows, or `brew install ffmpeg` on macOS).*

---

## 🔒 Security & Privacy

- **Zero Secret Leaks**: The Gnani API key resides strictly in `.env`. It is never returned in API responses, printed in console logs, rendered in UI error messages, or committed to Git.
- **In-Memory Audio Processing**: Voice data received from the browser `MediaRecorder` is processed entirely in RAM, forwarded directly to Gnani Prisma, and discarded immediately. No shopkeeper audio files are ever written to disk.
- **Local SQLite Storage**: Transaction data is stored locally in `arthvani.db` on the shopkeeper's machine — no unauthorized cloud database leaks.
- **Safe SQL**: 100% of database interactions use parameterized SQL statements to eliminate SQL injection vulnerabilities.

---

## 👥 Credits & Hackathon Submission

- **Author**: ArthVani Engineering Team
- **Challenge**: Gnani AI Great Indian AI Internship Challenge 2026
- **Voice Infrastructure**: [Gnani.ai](https://gnani.ai) Prisma Speech-to-Text & Timbre Text-to-Speech APIs
