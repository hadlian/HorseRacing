#!/usr/bin/env python3
"""
r5_results_cli.py — Full post-race results pipeline (one command)

Parses a BRIS results PDF and logs everything to both R5 and CompareModels DBs.

Usage:
    python3 Claude/r5_results_cli.py SAX 20260525 Results/2026/20260525SAXUSA0.pdf

What it does:
    1. Parse results PDF  → finish orders + win payouts per race
    2. Log to R5 DB       → apply_result() for each race
    3. Finalize R5        → mark any NULL positions as late scratches
    4. CM results         → pull results from R5 DB into CM DB
    5. CM finalize        → mark CM late scratches
    6. Print summary      → wins, ROI vs picks
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR        = HORSE_RACING_ROOT / "Claude"
CM_CLI            = HORSE_RACING_ROOT / "comparemodels" / "comparemodels_cli.py"


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 Claude/r5_results_cli.py TRACK YYYYMMDD results.pdf")
        print("  e.g. python3 Claude/r5_results_cli.py SAX 20260525 Results/2026/20260525SAXUSA0.pdf")
        sys.exit(1)

    track    = sys.argv[1].upper()
    date_str = sys.argv[2]
    pdf_arg  = sys.argv[3]

    # Resolve PDF path
    pdf_path = Path(pdf_arg)
    if not pdf_path.exists():
        pdf_path = HORSE_RACING_ROOT / pdf_arg
    if not pdf_path.exists():
        print(f"Error: PDF not found: {sys.argv[3]}")
        sys.exit(1)

    # Load shared modules
    pdf_parser = _load("r5_pdf_results", CLAUDE_DIR / "r5_pdf_results.py")
    tracker    = _load("r5_tracker",     CLAUDE_DIR / "r5_tracker.py")

    # ── STEP 1: Parse PDF ─────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 1/4 — Parse Results PDF")
    print(f"  {pdf_path.name}")
    print(f"{'='*64}\n")

    results = pdf_parser.parse_results_pdf(str(pdf_path))
    if not results:
        print("❌ No results extracted from PDF — check file format")
        sys.exit(1)

    print(f"  ✅ {len(results)} races parsed from PDF\n")
    for rnum in sorted(results):
        r = results[rnum]
        sp_str = f"  ${r['sp']:.2f}" if r["sp"] else ""
        fin4   = " → ".join(f"#{p}" for p in r["finish"][:4])
        print(f"  R{rnum:<2}  {fin4}{sp_str}")

    # ── STEP 2: Log to R5 DB ──────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 2/4 — Log Results to R5 DB")
    print(f"{'='*64}\n")

    logged = 0
    for race_num in sorted(results):
        r      = results[race_num]
        finish = r["finish"]
        sp     = r["sp"]
        ok     = tracker.apply_result(track, date_str, str(race_num), finish, sp)
        if ok:
            logged += 1

    print(f"\n  ✅ {logged}/{len(results)} races logged to R5 DB")

    # ── STEP 3: Finalize R5 ───────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 3/4 — Finalize R5 (detect late scratches)")
    print(f"{'='*64}\n")

    tracker.finalize_card(track, date_str)

    # ── STEP 4: CM results + finalize ─────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 4/4 — CompareModels Results + Finalize")
    print(f"{'='*64}\n")

    subprocess.run([sys.executable, str(CM_CLI), "results",  track, date_str],
                   cwd=str(HORSE_RACING_ROOT))
    subprocess.run([sys.executable, str(CM_CLI), "finalize", track, date_str],
                   cwd=str(HORSE_RACING_ROOT))

    # ── STEP 5: Settle paper trackers ─────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 5 — Settle paper trackers (rank3 + val_n)")
    print(f"{'='*64}\n")

    probability = _load("r5_probability", CLAUDE_DIR / "r5_probability.py")
    n_r3  = tracker.settle_rank3_bets()
    n_val = probability.settle_val_bets()
    print(f"  rank3_tracker: {n_r3} bets settled")
    print(f"  val_n_tracker: {n_val} bets settled")
    tracker.rank3_status()

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(track, date_str, results)


def _print_summary(track: str, date_str: str, pdf_results: dict):
    """Show how R5 top picks performed against the actual results."""
    import sqlite3
    r5_db = HORSE_RACING_ROOT / "results" / "r5_results.db"
    if not r5_db.exists():
        return

    print(f"\n{'='*64}")
    print(f"  📊 RESULTS SUMMARY — {track} {date_str}")
    print(f"{'='*64}\n")

    conn = sqlite3.connect(str(r5_db))
    conn.row_factory = sqlite3.Row

    wins = 0
    top3 = 0
    races = 0

    for race_num in sorted(pdf_results):
        r         = pdf_results[race_num]
        winner_pgm = r["finish"][0] if r["finish"] else None

        # Get R5 rank-1 pick for this race
        row = conn.execute("""
            SELECT p.pgm, p.horse_name, p.comp, p.tier, p.finish_pos, p.won
            FROM picks p JOIN races r ON p.race_id = r.id
            WHERE r.track = ? AND r.date = ? AND r.race_num = ? AND p.model_rank = 1
        """, (track, date_str, str(race_num))).fetchone()

        if not row:
            continue

        races += 1
        won   = row["finish_pos"] == 1
        in3   = row["finish_pos"] in (1, 2, 3)
        if won:
            wins += 1
        if in3:
            top3 += 1

        sp_str  = f"  ${r['sp']:.2f}" if r["sp"] else ""
        icon    = "🏆" if won else ("🥈" if row["finish_pos"] == 2 else ("🥉" if row["finish_pos"] == 3 else "  ")  )
        pos_str = f"#{row['finish_pos']}" if row["finish_pos"] and row["finish_pos"] > 0 else "—"
        print(f"  {icon} R{race_num:<2}  #{row['pgm']} {str(row['horse_name']):<22}  "
              f"{row['tier']:<5}  finished {pos_str}{sp_str}")

    conn.close()

    if races:
        print(f"\n  Wins:  {wins}/{races} ({wins/races*100:.0f}%)")
        print(f"  Top-3: {top3}/{races} ({top3/races*100:.0f}%)")

    print(f"\n{'='*64}")
    print(f"  ✅ Pipeline complete — {track} {date_str}")
    print(f"  Run analysis: python3 Claude/r5_analyze.py")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
