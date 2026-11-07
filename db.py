"""
db.py — SQLite persistence layer for ArthVani.

Public API
----------
  init_db(path)              Create the DB and table if they don't exist.
  save_entry(entry, lang, transcript, path) -> int   Insert a confirmed entry.
  list_entries(path)         -> list[dict]  All rows, newest first.
  today_total(path)          -> float       Sum of sale totals for today (IST).
  update_entry(id, fields, path)            Update editable fields; recomputes total.
  delete_entry(id, path)                   Delete one row by id.
  delete_last_entry(path)   -> bool         Delete the most recent row; False if empty.
  entries_dataframe(lang, path) -> pd.DataFrame  Display-ready table with translated headings.
  export_xlsx(lang, path)   -> bytes         .xlsx file content.
  export_csv(lang, path)    -> bytes         UTF-8-sig CSV content.
  seed_demo_entries(path)                   Insert 5 synthetic demo entries.

Design rules
------------
  - Parameterized queries only — no string interpolation in SQL.
  - Every public function takes `path` defaulting to DB_PATH so tests use
    a tmp file and never touch the production database.
  - total is ALWAYS recomputed as round(quantity * price, 2) on insert/update.
  - Timestamps stored as ISO 8601 local IST strings (YYYY-MM-DDTHH:MM:SS).
  - No network calls, no API key, no .env access.
"""

from __future__ import annotations

import io
import pathlib
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

import pandas as pd

# ── Defaults ──────────────────────────────────────────────────────────────────

_PROJECT_ROOT = pathlib.Path(__file__).parent
DB_PATH = str(_PROJECT_ROOT / "arthvani.db")

# IST = UTC+5:30
_IST = timezone(timedelta(hours=5, minutes=30))

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,                   -- ISO 8601 local IST
    entry_type  TEXT    NOT NULL DEFAULT 'sale',    -- 'sale' or 'purchase'
    item        TEXT    NOT NULL,                   -- as spoken, original script
    quantity    REAL    NOT NULL,
    unit        TEXT,                               -- kg / g / litre / dozen / packet / piece
    price       REAL    NOT NULL,                   -- per unit
    total       REAL    NOT NULL,                   -- round(qty*price,2), always computed here
    language    TEXT    NOT NULL,                   -- 'hi' or 'en'
    transcript  TEXT    DEFAULT ''                  -- raw STT text, for transparency
);
"""


# ════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════

def _connect(path: str | None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists."""
    p = path or DB_PATH
    conn = sqlite3.connect(p, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(_DDL)
    conn.commit()
    return conn


def _now_ist() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%dT%H:%M:%S")


def _today_ist() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


# ════════════════════════════════════════════════════════════
# 1. INIT
# ════════════════════════════════════════════════════════════

def init_db(path: str | None = None) -> None:
    """Create the database and table if they don't exist. Safe to call repeatedly."""
    conn = _connect(path)
    conn.close()


# ════════════════════════════════════════════════════════════
# 2. INSERT
# ════════════════════════════════════════════════════════════

def save_entry(
    entry: dict,
    language: str,
    transcript: str = "",
    path: str | None = None,
) -> int:
    """
    Persist a confirmed parser entry to SQLite.

    Parameters
    ----------
    entry      : dict with keys item, quantity, unit, price, entry_type
    language   : "hi" or "en"
    transcript : raw STT text (stored for transparency only)
    path       : DB file path; defaults to arthvani.db

    Returns
    -------
    int — the auto-assigned row id

    Raises
    ------
    ValueError if item, quantity, or price is missing.
    """
    item       = entry.get("item")
    quantity   = entry.get("quantity")
    price      = entry.get("price")
    unit       = entry.get("unit")
    entry_type = (entry.get("entry_type") or "sale").strip().lower()
    if entry_type not in ("sale", "purchase"):
        entry_type = "sale"

    if not item:
        raise ValueError("item is required")
    if quantity is None:
        raise ValueError("quantity is required")
    if price is None:
        raise ValueError("price is required")

    total = round(float(quantity) * float(price), 2)

    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            INSERT INTO entries
              (created_at, entry_type, item, quantity, unit, price, total, language, transcript)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_ist(), entry_type, str(item),
                float(quantity), unit,
                float(price), total,
                language, transcript or "",
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# 3. QUERY
# ════════════════════════════════════════════════════════════

def list_entries(path: str | None = None) -> list[dict]:
    """Return all entries as a list of dicts, newest first."""
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def today_total(path: str | None = None) -> float:
    """
    Return the sum of `total` for all *sale* entries recorded today (IST date).
    Returns 0.0 if there are no entries today.
    """
    today = _today_ist()
    conn  = _connect(path)
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(total), 0.0) AS day_total
              FROM entries
             WHERE entry_type = 'sale'
               AND created_at LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()
        return float(row["day_total"])
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# 4. UPDATE / DELETE
# ════════════════════════════════════════════════════════════

def update_entry(
    row_id: int,
    fields: dict[str, Any],
    path: str | None = None,
) -> None:
    """
    Update editable fields of an existing entry.

    Only columns in `fields` are changed. If quantity or price changes,
    total is recomputed automatically. id, created_at, language are immutable.
    """
    _editable = {"entry_type", "item", "quantity", "unit", "price", "transcript"}
    updates = {k: v for k, v in fields.items() if k in _editable}
    if not updates:
        return

    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT quantity, price FROM entries WHERE id = ?", (int(row_id),)
        ).fetchone()
        if row is None:
            return

        qty   = float(updates.get("quantity", row["quantity"]))
        price = float(updates.get("price",    row["price"]))
        updates["quantity"] = qty
        updates["price"]    = price
        updates["total"]    = round(qty * price, 2)

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values     = list(updates.values()) + [int(row_id)]
        conn.execute(f"UPDATE entries SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_entry(row_id: int, path: str | None = None) -> None:
    """Delete one entry by id. Silently does nothing if id doesn't exist."""
    conn = _connect(path)
    try:
        conn.execute("DELETE FROM entries WHERE id = ?", (int(row_id),))
        conn.commit()
    finally:
        conn.close()


def delete_last_entry(path: str | None = None) -> bool:
    """
    Delete the most recently inserted entry.
    Returns True if a row was deleted, False if the table was empty.
    """
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT id FROM entries ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM entries WHERE id = ?", (row["id"],))
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# 5. DISPLAY DATAFRAME
# ════════════════════════════════════════════════════════════

# Column order for the user-facing table
_DISPLAY_COLS = [
    "created_at", "entry_type", "item", "quantity", "unit", "price", "total",
]

# Column headings per language (matches strings.py keys)
_COL_HEADS: dict[str, dict[str, str]] = {
    "created_at":  {"en": "Date",      "hi": "तारीख"},
    "time_col":    {"en": "Time",      "hi": "समय"},
    "entry_type":  {"en": "Type",      "hi": "प्रकार"},
    "item":        {"en": "Item",      "hi": "सामान"},
    "quantity":    {"en": "Quantity",  "hi": "मात्रा"},
    "unit":        {"en": "Unit",      "hi": "इकाई"},
    "price":       {"en": "Price (₹)", "hi": "दाम (₹)"},
    "total":       {"en": "Total (₹)", "hi": "कुल (₹)"},
}

# Translated entry_type labels
_TYPE_LABELS: dict[str, dict[str, str]] = {
    "sale":     {"en": "Sale",     "hi": "बिक्री"},
    "purchase": {"en": "Purchase", "hi": "खरीद"},
}

# Translated unit labels (matches strings.UNIT_LABELS)
_UNIT_LABELS: dict[str, dict[str, str]] = {
    "kg":     {"en": "kg",     "hi": "किलो"},
    "g":      {"en": "g",      "hi": "ग्राम"},
    "litre":  {"en": "litre",  "hi": "लीटर"},
    "dozen":  {"en": "dozen",  "hi": "दर्जन"},
    "packet": {"en": "packet", "hi": "पैकेट"},
    "piece":  {"en": "piece",  "hi": "नग"},
}


def entries_dataframe(lang: str = "en", path: str | None = None) -> pd.DataFrame:
    """
    Return a display-ready DataFrame with translated headings.

    - Date column: DD-MM-YYYY
    - Time column: HH:MM  (split from created_at)
    - Type and Unit columns: translated to `lang`
    - Item: left exactly as stored (original script)

    Parameters
    ----------
    lang : "hi" or "en" — controls column headings, type/unit labels
    path : DB file; defaults to arthvani.db
    """
    rows = list_entries(path)
    if not rows:
        # Return empty DataFrame with correct translated headings
        heads = {
            _COL_HEADS["created_at"][lang]: [],
            _COL_HEADS["time_col"][lang]:   [],
            _COL_HEADS["entry_type"][lang]: [],
            _COL_HEADS["item"][lang]:       [],
            _COL_HEADS["quantity"][lang]:   [],
            _COL_HEADS["unit"][lang]:       [],
            _COL_HEADS["price"][lang]:      [],
            _COL_HEADS["total"][lang]:      [],
        }
        return pd.DataFrame(heads)

    df = pd.DataFrame(rows)

    # Split timestamp into Date and Time
    df["_date"] = df["created_at"].str[:10].apply(
        lambda s: f"{s[8:10]}-{s[5:7]}-{s[:4]}" if len(s) >= 10 else s
    )
    df["_time"] = df["created_at"].str[11:16]

    # Translate entry_type
    df["entry_type"] = df["entry_type"].apply(
        lambda v: _TYPE_LABELS.get(str(v), {}).get(lang, v)
    )

    # Translate unit
    df["unit"] = df["unit"].apply(
        lambda v: _UNIT_LABELS.get(str(v), {}).get(lang, v) if v else ""
    )

    # Build output with translated column names
    out = pd.DataFrame({
        _COL_HEADS["created_at"][lang]: df["_date"],
        _COL_HEADS["time_col"][lang]:   df["_time"],
        _COL_HEADS["entry_type"][lang]: df["entry_type"],
        _COL_HEADS["item"][lang]:       df["item"],
        _COL_HEADS["quantity"][lang]:   df["quantity"],
        _COL_HEADS["unit"][lang]:       df["unit"],
        _COL_HEADS["price"][lang]:      df["price"],
        _COL_HEADS["total"][lang]:      df["total"],
    })
    return out


# ════════════════════════════════════════════════════════════
# 6. EXPORT
# ════════════════════════════════════════════════════════════

def export_xlsx(lang: str = "en", path: str | None = None) -> bytes:
    """
    Return the ledger as a .xlsx file (bytes), with translated headings
    and sensible column widths. Suitable for st.download_button().
    """
    df  = entries_dataframe(lang, path)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ArthVani")
        ws = writer.sheets["ArthVani"]
        # Auto-width columns: max of header or content width + padding
        for col_cells in ws.columns:
            max_len = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)
    return buf.getvalue()


def export_csv(lang: str = "en", path: str | None = None) -> bytes:
    """
    Return the ledger as a UTF-8-sig CSV (bytes).
    The BOM ensures Hindi text opens correctly in Microsoft Excel.
    """
    df = entries_dataframe(lang, path)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# ════════════════════════════════════════════════════════════
# 7. DEMO DATA
# ════════════════════════════════════════════════════════════

_DEMO_ENTRIES: list[tuple] = [
    # (entry_dict, language, transcript)
    (
        {"item": "चावल",  "quantity": 50.0, "unit": "kg",    "price": 60.0,  "entry_type": "sale"},
        "hi", "50 किलो चावल 60 रुपये किलो",
    ),
    (
        {"item": "आलू",   "quantity": 5.0,  "unit": "kg",    "price": 20.0,  "entry_type": "sale"},
        "hi", "पाँच किलो आलू बीस रुपये किलो",
    ),
    (
        {"item": "rice",  "quantity": 10.0, "unit": "kg",    "price": 55.0,  "entry_type": "sale"},
        "en", "ten kilo rice fifty five rupees per kilo",
    ),
    (
        {"item": "soap",  "quantity": 12.0, "unit": "piece", "price": 30.0,  "entry_type": "purchase"},
        "en", "twelve pieces soap thirty rupees each bought",
    ),
    (
        {"item": "दूध",   "quantity": 2.0,  "unit": "litre", "price": 55.0,  "entry_type": "sale"},
        "hi", "दो लीटर दूध पचपन रुपये लीटर",
    ),
]


def seed_demo_entries(path: str | None = None) -> None:
    """
    Insert 5 clearly synthetic demo entries (mixed Hindi and English).
    Safe to call repeatedly — always adds fresh entries with current timestamps.
    These are labelled as demo/synthetic data and do not represent real transactions.
    """
    for entry, lang, transcript in _DEMO_ENTRIES:
        save_entry(entry, lang, transcript, path)
