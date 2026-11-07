"""
tests/conftest.py — Pytest session hooks for ArthVani.

Loads automatically by pytest (no import needed in test files).

Summary printed at end of run:
  - Per-language breakdown: total rows, passed, failed
  - Needs-review rows: how many expected and how many correctly flagged
  - Real vs synthetic source breakdown
  - Any failing rows listed with expected vs actual values

NOTE: These tests check parser *logic* on hand-crafted or real-STT-only
inputs.  They are NOT a measure of real-world end-to-end accuracy.
Real accuracy numbers come from actual recordings sent through the live
Gnani STT — that is a separate evaluation (noise_eval.py / field tests).
"""

import csv
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from parser import parse

CSV_PATH = pathlib.Path(__file__).parent / "sentences.csv"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_rows() -> list[dict]:
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _float_or_none(s: str):
    s = s.strip()
    return float(s) if s else None


def _str_or_none(s: str):
    s = s.strip()
    return s if s else None


def _is_incomplete(row: dict) -> bool:
    """A row is 'incomplete' (needs_review expected) if qty or price is empty."""
    return not row["quantity"].strip() or not row["price"].strip()


def _row_label(i: int, row: dict) -> str:
    return f"row_{i+1} [{row['language']}] transcript={row['transcript']!r}"


def _check_row(row: dict) -> tuple[bool, list[str]]:
    """
    Run parse() on the row and check all expected fields.
    Returns (ok: bool, failures: list[str-descriptions]).
    """
    stt  = {"transcript": row["transcript"], "literal": row["literal"]}
    lang = row["language"].strip()
    try:
        r = parse(stt, lang)
    except Exception as exc:
        return False, [f"parse() raised {exc!r}"]

    failures = []
    exp_item  = _str_or_none(row["item"])
    exp_qty   = _float_or_none(row["quantity"])
    exp_price = _float_or_none(row["price"])
    exp_total = _float_or_none(row["total"])
    exp_type  = row["entry_type"].strip() or "sale"

    if exp_item and r.get("item", "").strip() != exp_item:
        failures.append(f"item: expected {exp_item!r}, got {r.get('item')!r}")
    if exp_qty is not None and not math.isclose(r.get("quantity") or 0.0, exp_qty, rel_tol=1e-4):
        failures.append(f"quantity: expected {exp_qty}, got {r.get('quantity')}")
    if exp_price is not None and not math.isclose(r.get("price") or 0.0, exp_price, rel_tol=1e-4):
        failures.append(f"price: expected {exp_price}, got {r.get('price')}")
    if exp_total is not None and r.get("total") is not None:
        if not math.isclose(r["total"], exp_total, rel_tol=1e-4):
            failures.append(f"total: expected {exp_total}, got {r['total']}")
    if r.get("entry_type") != exp_type:
        failures.append(f"entry_type: expected {exp_type!r}, got {r.get('entry_type')!r}")

    return len(failures) == 0, failures


# ── pytest hook ───────────────────────────────────────────────────────────────

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a full, honest accuracy summary after the test run."""
    rows = _load_rows()

    # ── categorise every row ──────────────────────────────────────────────────
    # Buckets keyed by (language, source)
    # incomplete = rows where needs_review is *expected* (empty qty or price)
    stats: dict = {}          # (lang, source) -> {"pass": 0, "fail": 0, "fail_details": []}
    review_rows: list[dict]   = []   # incomplete rows
    review_correct: int       = 0    # incomplete rows that correctly set needs_review=True
    review_missed: list[str]  = []   # incomplete rows that did NOT set needs_review

    for i, row in enumerate(rows):
        lang   = row["language"].strip()
        source = row.get("source", "synthetic").strip()
        key    = (lang, source)
        if key not in stats:
            stats[key] = {"pass": 0, "fail": 0, "fail_details": []}

        if _is_incomplete(row):
            review_rows.append(row)
            stt  = {"transcript": row["transcript"], "literal": row["literal"]}
            try:
                r = parse(stt, lang)
                if r.get("needs_review"):
                    review_correct += 1
                else:
                    review_missed.append(_row_label(i, row))
            except Exception as exc:
                review_missed.append(f"{_row_label(i, row)} — parse() raised {exc!r}")
        else:
            ok, failures = _check_row(row)
            if ok:
                stats[key]["pass"] += 1
            else:
                stats[key]["fail"] += 1
                stats[key]["fail_details"].append(
                    (_row_label(i, row), failures)
                )

    # ── build per-language totals ─────────────────────────────────────────────
    lang_totals: dict = {}   # lang -> {"pass": 0, "fail": 0, "fail_details": []}
    for (lang, src), s in stats.items():
        if lang not in lang_totals:
            lang_totals[lang] = {"pass": 0, "fail": 0, "fail_details": []}
        lang_totals[lang]["pass"] += s["pass"]
        lang_totals[lang]["fail"] += s["fail"]
        lang_totals[lang]["fail_details"].extend(s["fail_details"])

    # Assign incomplete rows to their language bucket for the total row count
    review_by_lang: dict = {}
    for row in review_rows:
        lang = row["language"].strip()
        review_by_lang[lang] = review_by_lang.get(lang, 0) + 1

    # ── print ─────────────────────────────────────────────────────────────────
    W = terminalreporter.write_line
    terminalreporter.write_sep("═", "Parser test summary (Phase 2)")

    # Overall row accounting
    total_data     = sum(1 for r in rows if not _is_incomplete(r))
    total_complete = sum(s["pass"] + s["fail"] for s in lang_totals.values())
    total_pass     = sum(s["pass"] for s in lang_totals.values())
    total_fail     = sum(s["fail"] for s in lang_totals.values())
    total_review   = len(review_rows)
    total_rows     = len(rows)

    W(f"  Total rows in sentences.csv : {total_rows}")
    W(f"    Complete (item+qty+price)  : {total_data}"
      f"  →  {total_pass} passed, {total_fail} failed")
    W(f"    Needs-review (incomplete)  : {total_review}"
      f"  →  {review_correct} correctly flagged"
      + (f", {len(review_missed)} MISSED" if review_missed else "  ✓ all correct"))

    # Per-language breakdown
    W("")
    W("  By language (complete rows only):")
    for lang in sorted(lang_totals):
        s      = lang_totals[lang]
        n_rev  = review_by_lang.get(lang, 0)
        n_all  = s["pass"] + s["fail"] + n_rev
        label  = "Hindi  " if lang == "hi" else "English"
        W(f"    {label}  total={n_all:2d}"
          f"  complete={s['pass']+s['fail']:2d} ({s['pass']} passed, {s['fail']} failed)"
          f"  needs-review={n_rev}")

    # Per-source breakdown (real vs synthetic)
    W("")
    W("  By source:")
    source_totals: dict = {}
    for (lang, src), s in stats.items():
        if src not in source_totals:
            source_totals[src] = {"pass": 0, "fail": 0}
        source_totals[src]["pass"] += s["pass"]
        source_totals[src]["fail"] += s["fail"]
    for src in ("real", "synthetic"):
        if src in source_totals:
            s = source_totals[src]
            note = " ← actual Gnani STT output" if src == "real" else " ← hand-crafted"
            W(f"    {src:10s}  {s['pass']} passed, {s['fail']} failed{note}")

    # Flagged needs-review detail
    W("")
    W(f"  Needs-review rows ({total_review} expected, {review_correct} correctly flagged):")
    for row in review_rows:
        flag = "✓" if review_correct else "✗"
        W(f"    {flag}  [{row['language']}] {row['transcript']!r}")
    if review_missed:
        W("  !! The following incomplete rows were NOT flagged for review:")
        for lbl in review_missed:
            W(f"     {lbl}")

    # Failing rows detail
    if total_fail:
        W("")
        W(f"  Failing rows ({total_fail}):")
        for lang in sorted(lang_totals):
            for lbl, failures in lang_totals[lang]["fail_details"]:
                W(f"    ✗ {lbl}")
                for f in failures:
                    W(f"        {f}")
    else:
        W("")
        W("  No failing rows. ✓")

    W("")
    W("  NOTE: These results measure parser logic on synthetic/lab inputs.")
    W("  Real-world accuracy will be measured separately via noise_eval.py")
    W("  using actual recordings sent through the live Gnani STT API.")
    terminalreporter.write_sep("═", "")
