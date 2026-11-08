"""
db.py — SQLite persistence layer for ArthVani.

Public API
----------
  init_db(path)              Create the DB and table if they don't exist.
  save_entry(entry, lang, transcript, path) -> int   Insert a confirmed entry.
  list_entries(path, filter, search, limit, offset, sort) -> list[dict]
  today_total(path)          -> float
  today_stats(path)          -> dict
  summary_stats(path)        -> dict  (today + week + 14-day series + top items)
  update_entry(id, fields, path)
  delete_entry(id, path)
  delete_last_entry(path)   -> bool
  entries_dataframe(lang, path) -> pd.DataFrame
  export_xlsx(lang, path)   -> bytes
  export_csv(lang, path)    -> bytes
  seed_demo_entries(path)   -> int   (returns count inserted; idempotent)
  clear_demo_entries(path)  -> int   (returns count deleted)

Design rules
------------
  - Parameterized queries only — no string interpolation in SQL.
  - Every public function takes `path` defaulting to DB_PATH so tests use
    a tmp file and never touch the production database.
  - total is ALWAYS recomputed as round(quantity * price, 2) on insert/update.
  - Timestamps stored as ISO 8601 local IST strings (YYYY-MM-DDTHH:MM:SS).
  - No network calls, no API key, no .env access.
  - is_demo column: 1 for seeded demo rows, 0 for real entries.
"""

from __future__ import annotations

import io
import pathlib
import random
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
    transcript  TEXT    DEFAULT '',                 -- raw STT text, for transparency
    is_demo     INTEGER NOT NULL DEFAULT 0          -- 1 = seeded demo row
);
"""

_MIGRATION_IS_DEMO = "ALTER TABLE entries ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0"


# ════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════

def _connect(path: str | None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists, with auto-migration."""
    p = path or DB_PATH
    conn = sqlite3.connect(p, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(_DDL)
    conn.commit()
    # Auto-migration: add is_demo column if missing
    try:
        conn.execute(_MIGRATION_IS_DEMO)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
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
    is_demo: int = 0,
) -> int:
    """
    Persist a confirmed parser entry to SQLite.

    Parameters
    ----------
    entry      : dict with keys item, quantity, unit, price, entry_type
    language   : "hi" or "en"
    transcript : raw STT text (stored for transparency only)
    path       : DB file path; defaults to arthvani.db
    is_demo    : 1 if this is a demo/synthetic row

    Returns
    -------
    int — the auto-assigned row id
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
              (created_at, entry_type, item, quantity, unit, price, total, language, transcript, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_ist(), entry_type, str(item),
                float(quantity), unit,
                float(price), total,
                language, transcript or "",
                int(is_demo),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _save_entry_at(
    entry: dict,
    language: str,
    transcript: str,
    created_at: str,
    path: str | None = None,
    is_demo: int = 1,
) -> int:
    """Internal: insert with an explicit timestamp (used by seeder)."""
    item       = entry.get("item")
    quantity   = entry.get("quantity")
    price      = entry.get("price")
    unit       = entry.get("unit")
    entry_type = (entry.get("entry_type") or "sale").strip().lower()
    total      = round(float(quantity) * float(price), 2)

    conn = _connect(path)
    try:
        cur = conn.execute(
            """
            INSERT INTO entries
              (created_at, entry_type, item, quantity, unit, price, total, language, transcript, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (created_at, entry_type, str(item), float(quantity), unit,
             float(price), total, language, transcript or "", int(is_demo)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# 3. QUERY
# ════════════════════════════════════════════════════════════

def list_entries(
    path: str | None = None,
    filter_type: str | None = None,   # "sale" | "purchase" | None
    search: str | None = None,
    limit: int = 500,
    offset: int = 0,
    sort: str = "created_at DESC",
    date_from: str | None = None,     # YYYY-MM-DD
    date_to: str | None = None,
) -> list[dict]:
    """Return entries as a list of dicts with optional filter/search/sort/pagination."""
    allowed_sorts = {
        "created_at DESC", "created_at ASC",
        "total DESC", "total ASC",
        "item ASC", "item DESC",
    }
    if sort not in allowed_sorts:
        sort = "created_at DESC"

    sort_sql = sort
    if sort == "created_at DESC":
        sort_sql = "created_at DESC, id DESC"
    elif sort == "created_at ASC":
        sort_sql = "created_at ASC, id ASC"

    clauses: list[str] = []
    params: list[Any]  = []

    if filter_type in ("sale", "purchase"):
        clauses.append("entry_type = ?")
        params.append(filter_type)

    if search:
        clauses.append("item LIKE ?")
        params.append(f"%{search}%")

    if date_from:
        clauses.append("created_at >= ?")
        params.append(f"{date_from}T00:00:00")

    if date_to:
        clauses.append("created_at <= ?")
        params.append(f"{date_to}T23:59:59")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql   = f"SELECT * FROM entries {where} ORDER BY {sort_sql} LIMIT ? OFFSET ?"
    params += [limit, offset]

    conn = _connect(path)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_entries(
    path: str | None = None,
    filter_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    """Return total count matching filters (for pagination)."""
    clauses: list[str] = []
    params: list[Any]  = []

    if filter_type in ("sale", "purchase"):
        clauses.append("entry_type = ?")
        params.append(filter_type)
    if search:
        clauses.append("item LIKE ?")
        params.append(f"%{search}%")
    if date_from:
        clauses.append("created_at >= ?")
        params.append(f"{date_from}T00:00:00")
    if date_to:
        clauses.append("created_at <= ?")
        params.append(f"{date_to}T23:59:59")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql   = f"SELECT COUNT(*) FROM entries {where}"

    conn = _connect(path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def today_stats(path: str | None = None) -> dict:
    """Return {sales, purchases, net, count} for today (IST)."""
    today = _today_ist()
    conn  = _connect(path)
    try:
        rows = conn.execute(
            """
            SELECT entry_type, SUM(total) AS total, COUNT(*) AS cnt
              FROM entries
             WHERE created_at LIKE ?
             GROUP BY entry_type
            """,
            (f"{today}%",),
        ).fetchall()
        sales = purchases = 0.0
        count = 0
        for r in rows:
            if r["entry_type"] == "sale":
                sales = float(r["total"])
                count += r["cnt"]
            elif r["entry_type"] == "purchase":
                purchases = float(r["total"])
                count += r["cnt"]
        return {"sales": sales, "purchases": purchases, "net": round(sales - purchases, 2), "count": count}
    finally:
        conn.close()


def summary_stats(path: str | None = None) -> dict:
    """Return full summary: today, week, 14-day series, top 5 items."""
    ist_now = datetime.now(_IST)
    today   = ist_now.strftime("%Y-%m-%d")

    conn = _connect(path)
    try:
        # 14-day series
        series = []
        for d in range(13, -1, -1):
            day = (ist_now - timedelta(days=d)).strftime("%Y-%m-%d")
            row = conn.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN entry_type='sale' THEN total ELSE 0 END), 0) AS sales,
                  COALESCE(SUM(CASE WHEN entry_type='purchase' THEN total ELSE 0 END), 0) AS purchases
                FROM entries WHERE created_at LIKE ?
                """,
                (f"{day}%",),
            ).fetchone()
            series.append({
                "date":      day,
                "sales":     round(float(row["sales"]), 2),
                "purchases": round(float(row["purchases"]), 2),
            })

        # Today totals
        today_row = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN entry_type='sale' THEN total ELSE 0 END), 0) AS sales,
              COALESCE(SUM(CASE WHEN entry_type='purchase' THEN total ELSE 0 END), 0) AS purchases,
              COUNT(*) AS cnt
            FROM entries WHERE created_at LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()
        t_sales = round(float(today_row["sales"]), 2)
        t_purch = round(float(today_row["purchases"]), 2)

        # Week totals (last 7 days)
        week_start = (ist_now - timedelta(days=6)).strftime("%Y-%m-%d")
        week_row   = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN entry_type='sale' THEN total ELSE 0 END), 0) AS sales,
              COALESCE(SUM(CASE WHEN entry_type='purchase' THEN total ELSE 0 END), 0) AS purchases,
              COUNT(*) AS cnt
            FROM entries WHERE created_at >= ?
            """,
            (f"{week_start}T00:00:00",),
        ).fetchone()

        # Top 5 items by total sales value
        top_items = conn.execute(
            """
            SELECT item, SUM(total) AS total_val, COUNT(*) AS cnt
              FROM entries
             WHERE entry_type='sale'
             GROUP BY item
             ORDER BY total_val DESC
             LIMIT 5
            """,
        ).fetchall()

        # Recent 5 entries
        recent = conn.execute(
            "SELECT * FROM entries ORDER BY created_at DESC, id DESC LIMIT 5"
        ).fetchall()

        return {
            "today": {
                "sales":     t_sales,
                "purchases": t_purch,
                "net":       round(t_sales - t_purch, 2),
                "count":     today_row["cnt"],
            },
            "week": {
                "sales":     round(float(week_row["sales"]), 2),
                "purchases": round(float(week_row["purchases"]), 2),
                "net":       round(float(week_row["sales"]) - float(week_row["purchases"]), 2),
                "count":     week_row["cnt"],
            },
            "series_14d": series,
            "top_items":  [{"item": r["item"], "total": round(float(r["total_val"]), 2), "count": r["cnt"]} for r in top_items],
            "recent":     [dict(r) for r in recent],
        }
    finally:
        conn.close()


def today_total(path: str | None = None) -> float:
    return today_stats(path)["sales"]


# ════════════════════════════════════════════════════════════
# 4. UPDATE / DELETE
# ════════════════════════════════════════════════════════════

def update_entry(
    row_id: int,
    fields: dict[str, Any],
    path: str | None = None,
) -> dict | None:
    """
    Update editable fields of an existing entry.
    Returns the updated row dict, or None if not found.
    """
    _editable = {"entry_type", "item", "quantity", "unit", "price", "transcript"}
    updates = {k: v for k, v in fields.items() if k in _editable}
    if not updates:
        return None

    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (int(row_id),)
        ).fetchone()
        if row is None:
            return None

        qty   = float(updates.get("quantity", row["quantity"]))
        price = float(updates.get("price",    row["price"]))
        updates["quantity"] = qty
        updates["price"]    = price
        updates["total"]    = round(qty * price, 2)

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values     = list(updates.values()) + [int(row_id)]
        conn.execute(f"UPDATE entries SET {set_clause} WHERE id = ?", values)
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (int(row_id),)
        ).fetchone()
        return dict(updated) if updated else None
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
    """Delete the most recently inserted entry. Returns True if deleted."""
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

_DISPLAY_COLS = [
    "created_at", "entry_type", "item", "quantity", "unit", "price", "total",
]

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

_TYPE_LABELS: dict[str, dict[str, str]] = {
    "sale":     {"en": "Sale",     "hi": "बिक्री"},
    "purchase": {"en": "Purchase", "hi": "खरीद"},
}

_UNIT_LABELS: dict[str, dict[str, str]] = {
    "kg":     {"en": "kg",     "hi": "किलो"},
    "g":      {"en": "g",      "hi": "ग्राम"},
    "litre":  {"en": "litre",  "hi": "लीटर"},
    "dozen":  {"en": "dozen",  "hi": "दर्जन"},
    "packet": {"en": "packet", "hi": "पैकेट"},
    "piece":  {"en": "piece",  "hi": "नग"},
}


def entries_dataframe(lang: str = "en", path: str | None = None) -> pd.DataFrame:
    """Return a display-ready DataFrame with translated headings."""
    rows = list_entries(path)
    if not rows:
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
    df["_date"] = df["created_at"].str[:10].apply(
        lambda s: f"{s[8:10]}-{s[5:7]}-{s[:4]}" if len(s) >= 10 else s
    )
    df["_time"] = df["created_at"].str[11:16]
    df["entry_type"] = df["entry_type"].apply(
        lambda v: _TYPE_LABELS.get(str(v), {}).get(lang, v)
    )
    df["unit"] = df["unit"].apply(
        lambda v: _UNIT_LABELS.get(str(v), {}).get(lang, v) if v else ""
    )
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
    """Return the ledger as a .xlsx file (bytes), with translated headings."""
    df  = entries_dataframe(lang, path)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ArthVani")
        ws = writer.sheets["ArthVani"]
        for col_cells in ws.columns:
            max_len = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)
    return buf.getvalue()


def export_csv(lang: str = "en", path: str | None = None) -> bytes:
    """Return the ledger as a UTF-8-sig CSV (bytes) — Excel-safe for Hindi."""
    df = entries_dataframe(lang, path)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# ════════════════════════════════════════════════════════════
# 7. DEMO DATA  (60-80 realistic, varied entries)
# ════════════════════════════════════════════════════════════

def _demo_rows() -> list[tuple]:
    """
    Generate 70 realistic demo entries spread over the last 30 days.
    ~75% sales, ~25% purchases. Mixed Hindi/English. Varied items/units/prices.
    Returns list of (entry_dict, language, transcript, created_at_str).
    """
    ist_now = datetime.now(_IST)

    # Item catalogue: (item_hi, item_en, unit, sale_price_range, purchase_price_range, qty_range)
    catalogue = [
        # grains / staples
        ("चावल",       "rice",       "kg",     (58, 70),  (45, 55),  (5, 50)),
        ("आटा",        "wheat flour","kg",      (40, 48),  (32, 38),  (5, 50)),
        ("दाल",        "dal",        "kg",      (100, 130),(80, 100), (2, 20)),
        ("चीनी",       "sugar",      "kg",      (42, 50),  (35, 42),  (2, 25)),
        ("नमक",        "salt",       "kg",      (18, 22),  (14, 18),  (1, 10)),
        ("तेल",        "oil",        "litre",   (120, 145),(100, 120),(1, 10)),
        # dairy
        ("दूध",        "milk",       "litre",   (52, 60),  (45, 52),  (1, 10)),
        ("दही",        "curd",       "kg",      (55, 65),  (45, 55),  (1, 5)),
        ("पनीर",       "paneer",     "kg",      (280, 340),(240, 280),(0.5, 3)),
        # vegetables
        ("आलू",        "potato",     "kg",      (18, 28),  (14, 20),  (2, 20)),
        ("प्याज",      "onion",      "kg",      (25, 40),  (18, 30),  (2, 20)),
        ("टमाटर",      "tomato",     "kg",      (20, 55),  (15, 40),  (1, 10)),
        # fruits
        ("केला",       "banana",     "dozen",   (40, 60),  (32, 48),  (1, 5)),
        ("सेब",        "apple",      "kg",      (120, 180),(100, 140),(1, 5)),
        # packaged
        ("साबुन",      "soap",       "piece",   (28, 40),  (22, 30),  (6, 24)),
        ("बिस्किट",    "biscuit",    "packet",  (10, 20),  (8, 15),   (10, 50)),
        ("चाय पत्ती",  "tea",        "g",       (350, 500),(280, 380),(250, 1000)),
        ("मैगी",       "maggi",      "packet",  (14, 18),  (10, 13),  (12, 60)),
        ("अंडे",       "eggs",       "dozen",   (65, 80),  (55, 68),  (1, 5)),
    ]

    rng = random.Random(42)  # fixed seed → deterministic

    rows = []
    for day_offset in range(30, 0, -1):
        ist_day = ist_now - timedelta(days=day_offset)
        date_str = ist_day.strftime("%Y-%m-%d")

        # 2–4 entries per day; more on weekends
        weekday = ist_day.weekday()  # 0=Mon, 6=Sun
        n_entries = rng.choice([2, 2, 3, 3, 3, 4, 4] if weekday >= 4 else [2, 2, 3])

        used_times = set()
        for _ in range(n_entries):
            # Shop hours: 08:00–21:30, busier 09–11 and 17–20
            bucket = rng.choices(
                ["morning", "afternoon", "evening"],
                weights=[35, 25, 40],
            )[0]
            if bucket == "morning":
                h = rng.randint(8, 11)
            elif bucket == "afternoon":
                h = rng.randint(12, 16)
            else:
                h = rng.randint(17, 21)
            m = rng.randint(0, 59)
            s = rng.randint(0, 59)
            # Avoid duplicate timestamps
            ts = h * 3600 + m * 60 + s
            while ts in used_times:
                s = (s + 7) % 60
                ts = h * 3600 + m * 60 + s
            used_times.add(ts)
            created_at = f"{date_str}T{h:02d}:{m:02d}:{s:02d}"

            # ~75% sale, ~25% purchase
            is_sale = rng.random() < 0.75
            entry_type = "sale" if is_sale else "purchase"

            # Pick item
            item_hi, item_en, unit, sale_range, purch_range, qty_range = rng.choice(catalogue)

            # Language: ~55% Hindi, ~45% English
            lang = rng.choice(["hi"] * 55 + ["en"] * 45)
            item = item_hi if lang == "hi" else item_en

            price_range = sale_range if is_sale else purch_range
            # Round qty sensibly
            qty_min, qty_max = qty_range
            if unit == "g":
                qty = rng.choice([250, 500, 750, 1000])
                qty = max(qty_min, min(qty_max, qty))
            elif unit in ("piece", "packet", "dozen"):
                qty = float(rng.randint(int(qty_min), int(qty_max)))
            else:
                qty = round(rng.uniform(qty_min, qty_max), 1)
                # Snap to half/quarter if small
                if qty < 5:
                    qty = round(qty * 2) / 2

            price = float(rng.randint(price_range[0], price_range[1]))

            entry = {
                "item":       item,
                "quantity":   qty,
                "unit":       unit,
                "price":      price,
                "entry_type": entry_type,
            }
            transcript = ""  # demo rows have no real transcript
            rows.append((entry, lang, transcript, created_at))

    # Always include today with a couple of entries so dashboard isn't empty
    today_str = ist_now.strftime("%Y-%m-%d")
    today_entries = [
        ({"item": "चावल", "quantity": 25.0, "unit": "kg",    "price": 62.0, "entry_type": "sale"},
         "hi", "25 किलो चावल 62 रुपये किलो", f"{today_str}T09:30:00"),
        ({"item": "milk",  "quantity": 5.0,  "unit": "litre", "price": 55.0, "entry_type": "sale"},
         "en", "5 litre milk 55 rupees", f"{today_str}T11:15:00"),
        ({"item": "आटा",  "quantity": 50.0, "unit": "kg",    "price": 38.0, "entry_type": "purchase"},
         "hi", "50 किलो आटा 38 रुपये किलो", f"{today_str}T08:45:00"),
        ({"item": "sugar", "quantity": 20.0, "unit": "kg",    "price": 44.0, "entry_type": "sale"},
         "en", "20 kg sugar 44 rupees", f"{today_str}T17:20:00"),
    ]
    rows.extend(today_entries)

    return rows


def seed_demo_entries(path: str | None = None) -> int:
    """
    Insert ~70 realistic demo entries spread over the last 30 days.
    Idempotent: if demo rows already exist, returns 0 without inserting.
    Returns count of rows inserted.
    """
    conn = _connect(path)
    try:
        existing = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE is_demo=1"
        ).fetchone()[0]
    finally:
        conn.close()

    if existing > 0:
        return 0  # already seeded

    rows = _demo_rows()
    inserted = 0
    for entry, lang, transcript, created_at in rows:
        _save_entry_at(entry, lang, transcript, created_at, path=path, is_demo=1)
        inserted += 1

    return inserted


def clear_demo_entries(path: str | None = None) -> int:
    """
    Delete all demo entries (is_demo=1). Real entries are never touched.
    Returns count of rows deleted.
    """
    conn = _connect(path)
    try:
        cur = conn.execute("DELETE FROM entries WHERE is_demo=1")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
