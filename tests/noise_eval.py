"""
tests/noise_eval.py — ArthVani Noise Evaluation Script
========================================================
Evaluates the full STT + parser pipeline on real audio files under multiple
audio conditions (clean, various SNR levels, phone-band simulation).

Usage:
    python tests/noise_eval.py [OPTIONS]

    --recordings-dir DIR   path to recordings/ folder  (default: recordings/)
    --labels      CSV      path to labels CSV          (default: recordings/labels.csv)
    --results-dir DIR      output directory             (default: results/)
    --max-calls   N        abort if plan exceeds N API calls (default: 60)
    --yes                  actually run API calls (without this, dry-run only)
    --dry-run              print the plan and audio variants, then exit
    --noise-file  PATH     optional real noise WAV      (default: noise/market.wav if exists)
"""

import sys
import os
import pathlib
import argparse
import csv
import math
import time
import datetime
import io

import numpy as np

# ---------------------------------------------------------------------------
# Make the project root (ArthVani/) importable so we can reach gnani & parser
# ---------------------------------------------------------------------------
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from pydub import AudioSegment
except ImportError:
    print(
        "[ERROR] pydub is not installed. Install it with:\n"
        "        pip install pydub\n"
        "        You may also need ffmpeg on your PATH for m4a/mp3 support."
    )
    sys.exit(1)

import gnani   # ArthVani STT wrapper
import parser  # ArthVani transaction parser


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE_PHONE = 8_000          # Hz — typical telephony sample rate
PHONE_BANDPASS_LOW = 300           # Hz — telephony low-cut
PHONE_BANDPASS_HIGH = 3_400        # Hz — telephony high-cut
API_PAUSE_SECONDS = 1              # polite pause between API calls

# The six conditions evaluated for every input file
CONDITIONS = [
    "clean",
    "noise_15dB",
    "noise_5dB",
    "noise_0dB",
    "phone_clean",
    "phone_noise_5dB",
]


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _seg_to_numpy(seg: AudioSegment) -> np.ndarray:
    """Convert a pydub AudioSegment to a normalised float32 numpy array."""
    raw = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32)
    # For stereo, reshape to (samples, channels)
    if seg.channels > 1:
        raw = raw.reshape(-1, seg.channels)
    return raw


def _numpy_to_seg(arr: np.ndarray, frame_rate: int, channels: int) -> AudioSegment:
    """Convert a float32 numpy array back to a pydub AudioSegment (int16)."""
    clipped = np.clip(arr, -32768, 32767).astype(np.int16)
    return AudioSegment(
        clipped.tobytes(),
        frame_rate=frame_rate,
        sample_width=2,          # 16-bit
        channels=channels,
    )


def _mix_noise(seg: AudioSegment, noise_arr: np.ndarray, snr_db: float) -> AudioSegment:
    """
    Mix `seg` with noise at a given SNR (dB).

    SNR = 10 * log10(P_signal / P_noise)  →  scale noise so it matches the
    desired ratio relative to the signal power.
    """
    sig = _seg_to_numpy(seg)

    # Flatten for power calculation if multi-channel
    sig_flat = sig.flatten()
    p_signal = np.mean(sig_flat ** 2) + 1e-12   # avoid div-by-zero

    # Tile or trim noise to match signal length
    n_needed = sig_flat.size
    if noise_arr.size < n_needed:
        repeats = math.ceil(n_needed / noise_arr.size)
        noise_arr = np.tile(noise_arr, repeats)
    noise_chunk = noise_arr[:n_needed]

    p_noise_raw = np.mean(noise_chunk ** 2) + 1e-12
    # Desired noise power
    p_noise_target = p_signal / (10 ** (snr_db / 10))
    scale = math.sqrt(p_noise_target / p_noise_raw)
    noise_scaled = noise_chunk * scale

    # Reshape noise if original signal was multi-channel
    if sig.ndim == 2:
        noise_scaled = noise_scaled.reshape(sig.shape)

    mixed = sig + noise_scaled
    return _numpy_to_seg(mixed, seg.frame_rate, seg.channels)


def _apply_phone_band(seg: AudioSegment) -> AudioSegment:
    """
    Simulate a telephone channel:
      1. Downsample to 8 kHz
      2. Apply a 300–3400 Hz bandpass filter
    pydub's high_pass_filter / low_pass_filter are single-pole Butterworth.
    """
    phone = seg.set_frame_rate(SAMPLE_RATE_PHONE)
    phone = phone.high_pass_filter(PHONE_BANDPASS_LOW)
    phone = phone.low_pass_filter(PHONE_BANDPASS_HIGH)
    return phone


def _seg_to_wav_bytes(seg: AudioSegment) -> bytes:
    """Export an AudioSegment to WAV bytes (in-memory)."""
    buf = io.BytesIO()
    seg.export(buf, format="wav")
    buf.seek(0)
    return buf.read()


def build_audio_variants(
    seg: AudioSegment,
    noise_arr: np.ndarray,
) -> dict[str, AudioSegment]:
    """
    Given a source AudioSegment and a noise numpy array, return a dict
    mapping condition name → AudioSegment for all six conditions.
    """
    phone = _apply_phone_band(seg)
    return {
        "clean":          seg,
        "noise_15dB":     _mix_noise(seg,   noise_arr, snr_db=15),
        "noise_5dB":      _mix_noise(seg,   noise_arr, snr_db=5),
        "noise_0dB":      _mix_noise(seg,   noise_arr, snr_db=0),
        "phone_clean":    phone,
        "phone_noise_5dB": _mix_noise(phone, noise_arr, snr_db=5),
    }


# ---------------------------------------------------------------------------
# Noise source loading
# ---------------------------------------------------------------------------

def load_noise(noise_path: pathlib.Path) -> tuple[np.ndarray, str]:
    """
    Load or generate the noise array.

    Returns:
        (noise_arr, source_description)
    The description is used verbatim in the report — it MUST accurately
    reflect whether the noise is real or synthetic.
    """
    if noise_path.exists():
        noise_seg = AudioSegment.from_wav(str(noise_path))
        noise_mono = noise_seg.set_channels(1)
        arr = _seg_to_numpy(noise_mono).flatten().astype(np.float32)
        description = f"recorded market noise ({noise_path})"
        print(f"[noise] Using real noise file: {noise_path}")
    else:
        # Generate 10 seconds of white noise at 16 kHz
        rng = np.random.default_rng(seed=42)
        arr = rng.standard_normal(16_000 * 10).astype(np.float32)
        description = "simulated white noise"
        print(
            f"[noise] {noise_path} not found — using simulated white noise.\n"
            "        Results WILL differ from real-world noisy environments."
        )
    return arr, description


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _parse_float(value) -> float | None:
    """Try to convert value to float; return None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare(label: dict, parsed: dict) -> dict:
    """
    Compare a parsed transaction against the ground-truth label.

    Fields compared:
      item     — case-insensitive strip match
      quantity — math.isclose(rel_tol=1e-2)
      unit     — exact match
      price    — math.isclose(rel_tol=1e-2)

    Returns a dict with individual field booleans and an overall 'correct' flag.
    """
    item_ok = str(label.get("item", "")).strip().lower() == \
              str(parsed.get("item", "")).strip().lower()

    qty_label = _parse_float(label.get("quantity"))
    qty_parsed = _parse_float(parsed.get("quantity"))
    if qty_label is not None and qty_parsed is not None:
        qty_ok = math.isclose(qty_label, qty_parsed, rel_tol=1e-2)
    else:
        qty_ok = False

    unit_ok = str(label.get("unit", "")).strip() == \
              str(parsed.get("unit", "")).strip()

    price_label = _parse_float(label.get("price"))
    price_parsed = _parse_float(parsed.get("price"))
    if price_label is not None and price_parsed is not None:
        price_ok = math.isclose(price_label, price_parsed, rel_tol=1e-2)
    else:
        price_ok = False

    return {
        "item_ok":     item_ok,
        "qty_ok":      qty_ok,
        "unit_ok":     unit_ok,
        "price_ok":    price_ok,
        "correct":     item_ok and qty_ok and unit_ok and price_ok,
    }


# ---------------------------------------------------------------------------
# CSV / Markdown report helpers
# ---------------------------------------------------------------------------

def _accuracy_pct(correct: int, total: int) -> str:
    if total == 0:
        return "N/A"
    return f"{100 * correct / total:.1f}%"


def save_csv(results: list[dict], out_path: pathlib.Path) -> None:
    """Write per-row results to a CSV file."""
    if not results:
        return
    fieldnames = list(results[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"[output] CSV saved → {out_path}")


def save_summary_md(
    results: list[dict],
    noise_description: str,
    out_path: pathlib.Path,
) -> None:
    """Generate and write the Markdown summary report."""
    today = datetime.date.today().isoformat()
    files_tested = len({r["file"] for r in results})
    total_calls = len(results)

    # --- By condition ---
    cond_stats: dict[str, dict] = {}
    for r in results:
        c = r["condition"]
        if c not in cond_stats:
            cond_stats[c] = {"correct": 0, "total": 0}
        cond_stats[c]["total"] += 1
        if r["correct"]:
            cond_stats[c]["correct"] += 1

    # --- By language ---
    lang_stats: dict[str, dict] = {}
    for r in results:
        lang = r["language"]
        if lang not in lang_stats:
            lang_stats[lang] = {"correct": 0, "total": 0}
        lang_stats[lang]["total"] += 1
        if r["correct"]:
            lang_stats[lang]["correct"] += 1

    # --- Failures ---
    failures = [r for r in results if not r["correct"]]

    lines = [
        "# ArthVani Noise Evaluation",
        "",
        f"**Date:** {today}  ",
        f"**Noise source:** {noise_description}  ",
        f"**Files tested:** {files_tested}  ",
        f"**Total API calls:** {total_calls}  ",
        "",
        "## Results by condition",
        "",
        "| Condition | Correct | Total | Accuracy |",
        "|-----------|---------|-------|----------|",
    ]
    for cond in CONDITIONS:
        if cond in cond_stats:
            s = cond_stats[cond]
            lines.append(
                f"| {cond} | {s['correct']} | {s['total']} "
                f"| {_accuracy_pct(s['correct'], s['total'])} |"
            )

    lines += [
        "",
        "## Results by language",
        "",
        "| Language | Correct | Total | Accuracy |",
        "|----------|---------|-------|----------|",
    ]
    for lang, s in sorted(lang_stats.items()):
        lines.append(
            f"| {lang} | {s['correct']} | {s['total']} "
            f"| {_accuracy_pct(s['correct'], s['total'])} |"
        )

    lines += [
        "",
        "## Failures",
        "",
        "| File | Condition | Expected | Got | Transcript |",
        "|------|-----------|----------|-----|------------|",
    ]
    if failures:
        for r in failures:
            expected = (
                f"item={r['label_item']} qty={r['label_quantity']} "
                f"unit={r['label_unit']} price={r['label_price']}"
            )
            got = (
                f"item={r['parsed_item']} qty={r['parsed_quantity']} "
                f"unit={r['parsed_unit']} price={r['parsed_price']}"
            )
            # Sanitise transcript for Markdown table (strip newlines/pipes)
            transcript = str(r.get("transcript", "")).replace("|", "｜").replace("\n", " ")
            lines.append(
                f"| {r['file']} | {r['condition']} | {expected} | {got} | {transcript} |"
            )
    else:
        lines.append("| — | — | — | — | — |")

    lines += [
        "",
        "*Only conditions actually run are shown. "
        "No accuracy claims beyond these numbers.*",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[output] Summary saved → {out_path}")


# ---------------------------------------------------------------------------
# Core evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(
    label_rows: list[dict],
    recordings_dir: pathlib.Path,
    noise_arr: np.ndarray,
    noise_description: str,
    results_dir: pathlib.Path,
) -> None:
    """
    For every (file, condition) pair:
      1. Build the audio variant
      2. Call gnani.stt() with the WAV bytes
      3. Call parser.parse() on the transcript
      4. Compare against the ground-truth label
    Then save results/noise_results.csv and results/noise_summary.md.
    """
    all_results: list[dict] = []

    for row in label_rows:
        filename = row["filename"]
        language = row["language"]
        audio_path = recordings_dir / filename

        if not audio_path.exists():
            print(f"[WARN]  {audio_path} not found — skipping.")
            continue

        print(f"\n[file]  {filename} (lang={language})")

        # Load source audio once
        try:
            source_seg = AudioSegment.from_file(str(audio_path))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Could not load {audio_path}: {exc} — skipping.")
            continue

        # Build all six variants
        variants = build_audio_variants(source_seg, noise_arr)

        for condition, variant_seg in variants.items():
            print(f"  [{condition}]", end=" ", flush=True)

            # Encode variant to WAV bytes for the STT call
            wav_bytes = _seg_to_wav_bytes(variant_seg)

            transcript = ""
            parsed: dict = {}
            error_msg = ""

            try:
                transcript = gnani.stt(wav_bytes, language=language)
                parsed = parser.parse(transcript, language=language)
            except Exception as exc:  # noqa: BLE001
                error_msg = str(exc)
                print(f"ERROR ({error_msg})", end="")

            # Comparison
            cmp = compare(row, parsed)
            status = "✓" if cmp["correct"] else "✗"
            print(status)

            all_results.append(
                {
                    "file":           filename,
                    "language":       language,
                    "condition":      condition,
                    # Ground truth
                    "label_item":     row.get("item", ""),
                    "label_quantity": row.get("quantity", ""),
                    "label_unit":     row.get("unit", ""),
                    "label_price":    row.get("price", ""),
                    # Parser output
                    "parsed_item":     parsed.get("item", ""),
                    "parsed_quantity": parsed.get("quantity", ""),
                    "parsed_unit":     parsed.get("unit", ""),
                    "parsed_price":    parsed.get("price", ""),
                    # Result
                    "item_ok":    cmp["item_ok"],
                    "qty_ok":     cmp["qty_ok"],
                    "unit_ok":    cmp["unit_ok"],
                    "price_ok":   cmp["price_ok"],
                    "correct":    cmp["correct"],
                    "transcript": transcript,
                    "error":      error_msg,
                }
            )

            # Polite pause between API calls
            time.sleep(API_PAUSE_SECONDS)

    # Persist outputs
    save_csv(all_results, results_dir / "noise_results.csv")
    save_summary_md(all_results, noise_description, results_dir / "noise_summary.md")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser_cli = argparse.ArgumentParser(
        description="ArthVani noise evaluation — tests STT+parser on audio variants",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_cli.add_argument(
        "--recordings-dir",
        default="recordings/",
        metavar="DIR",
        help="Directory containing audio recordings",
    )
    parser_cli.add_argument(
        "--labels",
        default="recordings/labels.csv",
        metavar="CSV",
        help="Ground-truth labels CSV file",
    )
    parser_cli.add_argument(
        "--results-dir",
        default="results/",
        metavar="DIR",
        help="Output directory for CSV and Markdown results",
    )
    parser_cli.add_argument(
        "--max-calls",
        type=int,
        default=60,
        metavar="N",
        help="Abort if the planned API call count exceeds this limit",
    )
    parser_cli.add_argument(
        "--yes",
        action="store_true",
        help="Actually execute API calls (omit for dry-run)",
    )
    parser_cli.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan and audio variants, then exit (same as omitting --yes)",
    )
    parser_cli.add_argument(
        "--noise-file",
        default=None,
        metavar="PATH",
        help="Path to a real noise WAV file (default: noise/market.wav if it exists)",
    )
    return parser_cli.parse_args()


def main() -> None:
    args = parse_args()

    # Resolve paths relative to the current working directory
    recordings_dir = pathlib.Path(args.recordings_dir).resolve()
    labels_path    = pathlib.Path(args.labels).resolve()
    results_dir    = pathlib.Path(args.results_dir).resolve()

    # Noise file: explicit flag > default location
    if args.noise_file:
        noise_path = pathlib.Path(args.noise_file).resolve()
    else:
        noise_path = (_PROJECT_ROOT / "noise" / "market.wav").resolve()

    # ------------------------------------------------------------------
    # 1. Load labels.csv
    # ------------------------------------------------------------------
    if not labels_path.exists():
        print(f"[ERROR] Labels file not found: {labels_path}")
        sys.exit(1)

    label_rows: list[dict] = []
    with open(labels_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only include rows whose audio file exists in recordings_dir
            audio_path = recordings_dir / row["filename"]
            if not audio_path.exists():
                print(f"[WARN]  {row['filename']} listed in labels but not found in "
                      f"{recordings_dir} — will be skipped during evaluation.")
            label_rows.append(row)

    n_files = len(label_rows)
    n_conditions = len(CONDITIONS)
    total_calls = n_files * n_conditions

    # ------------------------------------------------------------------
    # 2. Print the plan
    # ------------------------------------------------------------------
    print("=" * 60)
    print("ArthVani Noise Evaluation — Plan")
    print("=" * 60)
    print(f"  Recordings dir : {recordings_dir}")
    print(f"  Labels CSV     : {labels_path}")
    print(f"  Results dir    : {results_dir}")
    print(f"  Noise file     : {noise_path} "
          f"({'found' if noise_path.exists() else 'NOT found — will synthesise'})")
    print(f"  Files in CSV   : {n_files}")
    print(f"  Conditions     : {n_conditions} ({', '.join(CONDITIONS)})")
    print(f"  Total API calls: {total_calls}")
    print("-" * 60)

    # List files and their conditions
    for row in label_rows:
        print(f"  {row['filename']} ({row['language']})")
        for cond in CONDITIONS:
            print(f"      → {cond}")

    print("=" * 60)

    # ------------------------------------------------------------------
    # 3. Guard: too many API calls
    # ------------------------------------------------------------------
    if total_calls > args.max_calls:
        print(
            f"\n[ABORT] Planned API calls ({total_calls}) exceed "
            f"--max-calls ({args.max_calls}).\n"
            "        Increase --max-calls or reduce the number of recordings."
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Dry-run guard
    # ------------------------------------------------------------------
    if args.dry_run or not args.yes:
        print("\nDry-run mode — no API calls were made.")
        print("Add --yes to run for real.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # 5. Load noise and run evaluation
    # ------------------------------------------------------------------
    noise_arr, noise_description = load_noise(noise_path)

    print(f"\n[start] Running evaluation ({total_calls} API calls, "
          f"{API_PAUSE_SECONDS}s pause between each)…\n")

    run_evaluation(
        label_rows=label_rows,
        recordings_dir=recordings_dir,
        noise_arr=noise_arr,
        noise_description=noise_description,
        results_dir=results_dir,
    )

    print("\n[done]  Evaluation complete.")


if __name__ == "__main__":
    main()
