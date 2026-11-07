# ArthVani — आर्थवाणी

> **बोलिए, हिसाब हो जाएगा.**
> *Speak, and the ledger is done.*

ArthVani is a **voice-first ledger** built for Indian shopkeepers — kirana stores, vegetable vendors, and mandi traders — who think and speak in Hindi but shouldn't have to type. Say what you sold or bought; ArthVani hears it, parses it, and records it.

Built for the **Gnani AI Great Indian AI Internship Challenge 2026**.

---

## 📦 What It Is

ArthVani replaces the paper _bahi-khata_ with a voice interface. A shopkeeper speaks a transaction — item, quantity, rate — in natural Hindi or English. ArthVani:

1. Transcribes the audio using **Gnani AI Prisma** (STT).
2. Parses the transcript into structured fields (item · quantity · unit · rate · transaction type).
3. Reads the parsed entry back using **Gnani AI Timbre** (TTS) for confirmation.
4. Saves the confirmed entry to a local SQLite ledger.

No typing. No internet dependency for the ledger itself. No special training required from the shopkeeper.

---

## 👥 Who It's For

| User | Example |
|---|---|
| Kirana / general store owner | Tracks daily purchases and sales by voice |
| Vegetable / fruit vendor | Records mandi buys and retail sales on the go |
| Street food seller | Logs ingredient purchases without leaving the stove |

**Language:** Hindi-first (`hi-IN`). English (`en-IN`) also supported. Hinglish (Roman-script Hindi mixed with English) is partially handled.

---

## 🔊 Gnani AI Models

| Role | Model / Voice | Language |
|---|---|---|
| Speech-to-Text | Gnani AI **Prisma** | `hi-IN`, `en-IN` |
| Text-to-Speech | Gnani AI **Timbre** `timbre-v2.5` — voice **Nalini** | Hindi |
| Text-to-Speech | Gnani AI **Timbre** `timbre-v2.5` — voice **Kaveri** | English |

Prisma handles natural speech including number words, fraction words, and code-switching. Timbre reads back the parsed entry clearly so the shopkeeper can confirm before saving.

---

## ⚙️ Setup

```bash
# 1. Clone / download
git clone https://github.com/<your-org>/ArthVani.git
cd ArthVani

# 2. Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and set:
#   GNANI_API_KEY=your_key_here
# Get your key from: https://console.gnani.ai

# 5. (Optional) Install ffmpeg for noise evaluation
# Windows: winget install Gyan.FFmpeg
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
```

> **Note:** `.env` and `*.db` are listed in `.gitignore`. They will never be committed to version control.

---

## ▶️ Run

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

---

## 🧪 Run Tests

```bash
# Parser and DB unit tests — no API key required:
pytest tests/test_parser.py tests/test_db.py -v

# Full test suite:
pytest tests -v

# Noise evaluation — dry run (no API calls, checks setup only):
python tests/noise_eval.py --dry-run

# Noise evaluation — real run (uses API credits, requires recordings/):
python tests/noise_eval.py --yes
```

> The 30-row test set in `tests/sentences.csv` checks parser logic only. It is **not** a real-world accuracy measure — see [Accuracy Evaluation](#accuracy-evaluation) below.

---

## 🗣️ Supported Sentence Patterns

ArthVani uses a rule-based parser. It is designed to handle the natural, brief way shopkeepers actually speak — not full sentences.

### Hindi (Devanagari)

| What you say | What gets recorded |
|---|---|
| `50 किलो चावल ₹60 किलो` | Rice · 50 kg · ₹60/kg |
| `5 किलो आलू बीस रुपये किलो` | Potato · 5 kg · ₹20/kg |
| `डेढ़ किलो टमाटर चालीस रुपये किलो` | Tomato · 1.5 kg · ₹40/kg |
| `5 किलो साबुन kharida 30 रुपये किलो` | Soap · 5 kg · ₹30/kg · **purchase** |
| `50 किलो चावल कुल 3000` | Rice · 50 kg · ₹60/kg (derived: 3000 ÷ 50) |

### English

| What you say | What gets recorded |
|---|---|
| `50 kilo rice 60 kilo per kg` | Rice · 50 kg · ₹60/kg *(STT sometimes hears "kilo" for "rupees" — handled)* |
| `five kg sugar forty rupees per kg` | Sugar · 5 kg · ₹40/kg |
| `5 kg notebook bought 20 rupees each` | Notebook · 5 units · ₹20 each · **purchase** |

### Fraction words supported

| Word | Value | Script |
|---|---|---|
| aadha / आधा | 0.5 | Both |
| sava / सवा | 1.25 | Both |
| dedh / डेढ़ | 1.5 | Both |
| dhai / ढाई | 2.5 | Both |

---

## ⚠️ Honest Limitations

- **Rule-based parser, not an LLM.** Unusual or elaborate phrasing may not parse correctly. The parser is tuned for the short, telegraphic style shopkeepers actually use.
- **Hindi and English only.** Hinglish (Roman-script Hindi) is partially supported — results may vary.
- **Audio is sent to Gnani's API for transcription, then discarded.** It is not stored on disk by ArthVani. There is slight latency; this is not a real-time streaming pipeline.
- **English STT occasionally hears "rupees" as "kilo."** The parser detects and corrects this in common positions.
- **Local SQLite database only.** There is no cloud sync, no multi-device access, and no automatic backup.
- **Accuracy figures:** `[PLACEHOLDER — to be filled after running noise_eval.py on real recordings]`

---

## 📊 Accuracy Evaluation

Real accuracy figures are produced by running:

```bash
python tests/noise_eval.py --yes
```

This requires:
- Real audio recordings placed in `recordings/`
- A corresponding `recordings/labels.csv` file with the ground-truth transcriptions and expected parsed fields

The script sends each recording through Prisma STT, runs the parser, and computes field-level accuracy (item, quantity, unit, rate) against the labels.

> The numbers in this README will be updated once evaluation is run on a representative sample of real shopkeeper recordings. The 30-row `tests/sentences.csv` suite tests parser logic on clean text and does **not** measure STT accuracy or real-world noise robustness.

---

## 🔒 Privacy and Security

- Your API key is loaded from `.env` at runtime. It is **never hardcoded** in source files and **never logged**.
- Audio recorded in the app is sent to Gnani's API for transcription and is **not written to disk** by ArthVani.
- Only entries you explicitly confirm are saved — to a local `arthvani.db` SQLite file on your machine.
- `.env` and `*.db` are listed in `.gitignore` and will never be committed to version control.

---

## 🤝 Contributions

| Team Member | Role |
|---|---|
| [Team member 1] | [Role placeholder] |
| [Team member 2] | [Role placeholder] |
| *(Add more as needed)* | |

---

## 🏷️ Credits

| Component | Provider |
|---|---|
| Speech-to-Text | [Gnani AI Prisma](https://gnani.ai) (`hi-IN`, `en-IN`) |
| Text-to-Speech | [Gnani AI Timbre](https://gnani.ai) (`timbre-v2.5`, voices: Nalini · Kaveri) |
| Built for | Gnani AI Great Indian AI Internship Challenge 2026 |

---

*ArthVani is an open submission for the Gnani AI internship challenge. All API credentials are user-supplied and are not included in this repository.*
