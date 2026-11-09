"""
main.py — ArthVani FastAPI backend.

Endpoints
---------
  GET  /                        → serve static/index.html
  GET  /api/health              → {status, api_key_configured, version}
  GET  /api/i18n/{lang}         → full strings dict for the UI
  POST /api/transcribe          → multipart(audio_file, language) → parsed entry
  POST /api/parse-text          → JSON{text, language} → parsed entry
  POST /api/tts                 → JSON{text, language} → audio/wav
  GET  /api/entries             → list (filter/search/sort/paginate)
  POST /api/entries             → save new entry → {id, ...}
  PUT  /api/entries/{id}        → update entry
  DELETE /api/entries/{id}      → delete entry
  GET  /api/summary             → stats + 14-day series + top items
  GET  /api/export.xlsx         → Excel download
  GET  /api/export.csv          → CSV download
  POST /api/demo/load           → seed demo entries (idempotent)
  POST /api/demo/clear          → clear demo entries

Security
--------
  - API key read only from GNANI_API_KEY in .env / environment.
  - Key is NEVER returned in any response, error message, or log.
  - Audio bytes are processed in-memory and never written to disk.
"""

from __future__ import annotations

import io
import os
import pathlib
import sys

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(override=False)

# Ensure project root is on path
_ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db as _db
import gnani as _gnani
from parser import parse as _parse
from speech_text import build_readback, build_short_readback, build_query_response
from strings import _STRINGS, UNIT_LABELS, UNIT_OPTIONS, t
from voice_commands import classify as _classify_command, requires_explicit_confirmation

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="ArthVani", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DB_PATH = str(_ROOT / "arthvani.db")
_STATIC  = _ROOT / "static"
_BRAND   = _ROOT / "brand"

# Initialise DB on startup
_db.init_db(_DB_PATH)

# Mount static and brand asset files
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
if _BRAND.exists():
    app.mount("/brand", StaticFiles(directory=str(_BRAND)), name="brand")


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    index = _STATIC / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "ArthVani API running. Static files not found."})


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    key_ok = bool(os.environ.get("GNANI_API_KEY", "").strip())
    return {"status": "ok", "api_key_configured": key_ok, "version": "2.0.0"}


# ── i18n ──────────────────────────────────────────────────────────────────────

@app.get("/api/i18n/{lang}")
async def i18n(lang: str):
    if lang not in ("hi", "en"):
        raise HTTPException(400, "lang must be 'hi' or 'en'")
    result = {k: v.get(lang, v.get("en", "")) for k, v in _STRINGS.items()}
    result["_unit_labels"] = {k: v.get(lang, v.get("en", k)) for k, v in UNIT_LABELS.items()}
    result["_unit_options"] = UNIT_OPTIONS
    return result


# ── Transcribe (STT → parse) ──────────────────────────────────────────────────

@app.post("/api/transcribe")
async def transcribe(
    audio_file: UploadFile = File(...),
    language:   str        = Form("hi"),
):
    if language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(400, _safe_err("error_no_audio", language))

    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, _safe_err("error_audio_too_long", language))

    # Convert to 16-kHz mono WAV if pydub + ffmpeg available
    audio_bytes = _ensure_wav(audio_bytes)

    lang_code = "hi-IN" if language == "hi" else "en-IN"
    try:
        stt_result = _gnani.stt(audio_bytes, lang_code)
    except EnvironmentError as exc:
        raise HTTPException(503, _safe_err("error_no_key", language)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, _safe_err("error_stt", language, str(exc))) from exc

    parsed = _parse(stt_result, language)
    readback = build_readback(parsed, language)

    return {
        "transcript": stt_result.get("transcript", ""),
        "literal":    stt_result.get("literal", ""),
        "parsed":     parsed,
        "readback":   readback,
    }


# ── Parse text ────────────────────────────────────────────────────────────────

class ParseTextRequest(BaseModel):
    text:     str
    language: str = "hi"


@app.post("/api/parse-text")
async def parse_text(req: ParseTextRequest):
    if req.language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")
    stt_result = {"transcript": req.text, "literal": req.text}
    parsed   = _parse(stt_result, req.language)
    readback = build_readback(parsed, req.language)
    return {"parsed": parsed, "readback": readback}


# ── TTS ───────────────────────────────────────────────────────────────────────

class TtsRequest(BaseModel):
    text:     str
    language: str = "hi"


@app.post("/api/tts")
async def tts(req: TtsRequest):
    if req.language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")
    try:
        audio_bytes = _gnani.tts(req.text, req.language)
    except EnvironmentError as exc:
        raise HTTPException(503, _safe_err("error_no_key", req.language)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, _safe_err("error_tts", req.language, str(exc))) from exc
    return Response(content=audio_bytes, media_type="audio/wav")


# ── Entries CRUD ──────────────────────────────────────────────────────────────

@app.get("/api/entries")
async def get_entries(
    filter: str | None  = Query(None),
    search: str | None  = Query(None),
    limit:  int         = Query(20, ge=1, le=1000),
    offset: int         = Query(0, ge=0),
    sort:   str         = Query("created_at DESC"),
    date_from: str | None = Query(None),
    date_to:   str | None = Query(None),
):
    rows  = _db.list_entries(
        _DB_PATH, filter_type=filter, search=search,
        limit=limit, offset=offset, sort=sort,
        date_from=date_from, date_to=date_to,
    )
    total = _db.count_entries(
        _DB_PATH, filter_type=filter, search=search,
        date_from=date_from, date_to=date_to,
    )
    return {"entries": rows, "total": total, "limit": limit, "offset": offset}


class EntryIn(BaseModel):
    item:       str
    quantity:   float
    unit:       str | None = None
    price:      float
    entry_type: str = "sale"
    language:   str = "hi"
    transcript: str = ""


@app.post("/api/entries", status_code=201)
async def create_entry(entry: EntryIn):
    try:
        row_id = _db.save_entry(
            entry.model_dump(exclude={"language", "transcript"}),
            entry.language,
            entry.transcript,
            _DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    rows = _db.list_entries(_DB_PATH, limit=1, offset=0)
    # Return the actual saved row
    conn_rows = _db.list_entries(_DB_PATH, limit=500, offset=0)
    saved = next((r for r in conn_rows if r["id"] == row_id), None)
    return saved or {"id": row_id}


class EntryUpdate(BaseModel):
    item:       str | None  = None
    quantity:   float | None = None
    unit:       str | None  = None
    price:      float | None = None
    entry_type: str | None  = None


@app.put("/api/entries/{row_id}")
async def update_entry(row_id: int, upd: EntryUpdate):
    fields = {k: v for k, v in upd.model_dump().items() if v is not None}
    updated = _db.update_entry(row_id, fields, _DB_PATH)
    if updated is None:
        raise HTTPException(404, f"Entry {row_id} not found")
    return updated


@app.delete("/api/entries/{row_id}", status_code=204)
async def delete_entry(row_id: int):
    _db.delete_entry(row_id, _DB_PATH)
    return Response(status_code=204)


# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/api/summary")
async def summary():
    return _db.summary_stats(_DB_PATH)


# ── Exports ───────────────────────────────────────────────────────────────────

@app.get("/api/export.xlsx")
async def export_xlsx(lang: str = Query("en")):
    if lang not in ("hi", "en"):
        lang = "en"
    data = _db.export_xlsx(lang, _DB_PATH)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=arthvani.xlsx"},
    )


@app.get("/api/export.csv")
async def export_csv(lang: str = Query("en")):
    if lang not in ("hi", "en"):
        lang = "en"
    data = _db.export_csv(lang, _DB_PATH)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=arthvani.csv"},
    )


# ── Demo data ─────────────────────────────────────────────────────────────────

@app.post("/api/demo/load")
async def demo_load():
    inserted = _db.seed_demo_entries(_DB_PATH)
    return {"inserted": inserted, "message": f"{inserted} demo entries added." if inserted else "Demo data already loaded."}


@app.post("/api/demo/clear")
async def demo_clear():
    deleted = _db.clear_demo_entries(_DB_PATH)
    return {"deleted": deleted, "message": f"{deleted} demo entries removed."}


# ── Voice Mode: Command Classification ────────────────────────────────────────

class ClassifyRequest(BaseModel):
    text:     str
    language: str = "hi"


@app.post("/api/voice/classify")
async def voice_classify(req: ClassifyRequest):
    """Classify a voice utterance as an intent (command vs entry)."""
    if req.language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")
    intent = _classify_command(req.text, req.language)
    return intent


# ── Voice Mode: Price Memory ───────────────────────────────────────────────────

@app.get("/api/voice/last-price")
async def voice_last_price(
    item: str = Query(...),
    unit: str | None = Query(None),
):
    """Return the last known price for an item (fuzzy match)."""
    price = _db.last_price(item, unit, _DB_PATH)
    return {"item": item, "unit": unit, "last_price": price}


# ── Voice Mode: Day Summary ────────────────────────────────────────────────────

@app.get("/api/voice/day-summary")
async def voice_day_summary(lang: str = Query("hi")):
    """Return today's summary and a TTS-ready spoken sentence."""
    if lang not in ("hi", "en"):
        lang = "hi"
    data = _db.day_summary(_DB_PATH)
    spoken = build_query_response("daily_summary", data, lang)
    return {"data": data, "spoken": spoken}


# ── Voice Mode: Query Response ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query_type: str   # "today_total" | "week_total" | "daily_summary" | "last_entry" | "item_total"
    language:   str = "hi"
    item:       str | None = None   # for item_total only


@app.post("/api/voice/query")
async def voice_query(req: QueryRequest):
    """Answer a voice query and return a TTS-ready spoken sentence."""
    if req.language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")

    qt = req.query_type
    if qt == "today_total":
        data = _db.day_summary(_DB_PATH)
        spoken = build_query_response("today_total", data, req.language)
        return {"spoken": spoken, "data": data}

    if qt == "week_total":
        data = _db.summary_stats(_DB_PATH)
        spoken = build_query_response("week_total", data, req.language)
        return {"spoken": spoken, "data": data}

    if qt == "daily_summary":
        data = _db.day_summary(_DB_PATH)
        spoken = build_query_response("daily_summary", data, req.language)
        return {"spoken": spoken, "data": data}

    if qt == "last_entry":
        data = _db.summary_stats(_DB_PATH)
        spoken = build_query_response("last_entry", data, req.language)
        return {"spoken": spoken, "data": data}

    if qt == "item_total":
        item = req.item or ""
        # Sum today's sales for this item (fuzzy not needed here — exact name from STT)
        rows = _db.list_entries(
            _DB_PATH, filter_type="sale",
            search=item, date_from=None, date_to=None,
            limit=500, offset=0
        )
        import datetime as _dt
        today = _dt.date.today().isoformat()
        total = sum(r["total"] for r in rows if r.get("created_at", "").startswith(today))
        idata = {"item": item, "total": round(total, 2)}
        spoken = build_query_response("item_total", idata, req.language)
        return {"spoken": spoken, "data": idata}

    raise HTTPException(400, f"Unknown query_type: {qt!r}")


# ── Voice Mode: Short Transcribe (returns short readback + price-memory fill) ──

@app.post("/api/voice/transcribe")
async def voice_transcribe(
    audio_file: UploadFile = File(...),
    language:   str        = Form("hi"),
    mode:       str        = Form("quick"),    # quick | strict
    high_value: float      = Form(10_000.0),
):
    """
    Voice-mode transcribe: STT → parse → price-memory fill → short readback.
    Returns parsed entry, short readback text, explicit_required flag, timeout.
    """
    if language not in ("hi", "en"):
        raise HTTPException(400, "language must be 'hi' or 'en'")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(400, _safe_err("error_no_audio", language))
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, _safe_err("error_audio_too_long", language))

    audio_bytes = _ensure_wav(audio_bytes)

    lang_code = "hi-IN" if language == "hi" else "en-IN"
    try:
        stt_result = _gnani.stt(audio_bytes, lang_code)
    except EnvironmentError as exc:
        raise HTTPException(503, _safe_err("error_no_key", language)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, _safe_err("error_stt", language, str(exc))) from exc

    parsed = _parse(stt_result, language)

    # Price memory: fill missing price from last known
    filled_from_memory = False
    if parsed.get("item") and parsed.get("quantity") is not None and parsed.get("price") is None:
        last_p = _db.last_price(parsed["item"], parsed.get("unit"), _DB_PATH)
        if last_p is not None:
            parsed["price"] = last_p
            if parsed.get("quantity") is not None:
                parsed["total"] = round(float(parsed["quantity"]) * last_p, 2)
            filled_from_memory = True

    # Explicit confirmation needed?
    last_known = _db.last_price(parsed.get("item", ""), parsed.get("unit"), _DB_PATH) if parsed.get("item") else None
    explicit_required = requires_explicit_confirmation(
        parsed, mode=mode,
        high_value_threshold=high_value,
        last_known_price=last_known,
    )

    short_readback  = build_short_readback(parsed, language, filled_from_memory)
    full_readback   = build_readback(parsed, language)
    timeout_secs    = 3 if (mode == "quick" and not explicit_required) else 8

    return {
        "transcript":        stt_result.get("transcript", ""),
        "parsed":            parsed,
        "readback":          full_readback,
        "short_readback":    short_readback,
        "filled_from_memory": filled_from_memory,
        "explicit_required": explicit_required,
        "timeout_secs":      timeout_secs,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_err(key: str, lang: str, detail: str = "") -> str:
    """Return a bilingual error message; never includes the API key."""
    try:
        msg = t(key, lang)
    except KeyError:
        msg = t("error_generic", lang)
    if "{detail}" in msg and detail:
        # Sanitise: remove any key-like strings from detail
        detail = _redact(detail)
        msg = msg.replace("{detail}", detail)
    return msg


def _redact(text: str) -> str:
    """Remove API key patterns from text before returning to client."""
    import re
    return re.sub(r"vach_[A-Za-z0-9_]{20,}", "[REDACTED]", text)


# ── Diagnostics ───────────────────────────────────────────────────────────────

@app.get("/api/diagnostics")
async def diagnostics():
    """
    Check system dependencies. Never returns the actual API key — only a boolean.
    """
    import subprocess
    import httpx

    result: dict = {
        "api_key_configured": bool(os.environ.get("GNANI_API_KEY", "").strip()),
        "ffmpeg_available":   False,
        "stt_reachable":      False,
        "tts_reachable":      False,
    }

    # ffmpeg check
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3, check=False)
        result["ffmpeg_available"] = True
    except Exception:
        pass

    # Probe STT endpoint reachability (HEAD-like GET; a 400/401/405 means it's reachable)
    key = os.environ.get("GNANI_API_KEY", "")
    if key:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    "https://api.vachana.ai/stt/v3",
                    headers={"X-API-Key-ID": key},
                )
            result["stt_reachable"] = r.status_code not in (000, 503, 504)
        except Exception:
            pass

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    "https://api.vachana.ai/api/v1/tts/inference",
                    headers={"X-API-Key-ID": key},
                )
            result["tts_reachable"] = r.status_code not in (000, 503, 504)
        except Exception:
            pass

    return result


def _ensure_wav(audio_bytes: bytes) -> bytes:
    """
    Ensure audio is in WAV format suitable for Gnani STT (16 kHz, mono, PCM).
    If the client already sent a valid RIFF/WAV blob (from client-side conversion),
    return it unchanged.  Otherwise try pydub/ffmpeg as a server-side fallback.
    Audio is processed in-memory only — never written to disk.
    """
    # Already WAV: RIFF header present → pass through
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF':
        return audio_bytes
    # Try pydub/ffmpeg conversion
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
        seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        buf = io.BytesIO()
        seg.export(buf, format="wav")
        return buf.getvalue()
    except Exception:
        return audio_bytes  # pass through; Gnani may accept it anyway

