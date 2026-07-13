#!/usr/bin/env python3
"""
r5_results_cli.py — Full post-race results pipeline (one command)

Ingests an Equibase chart PDF and settles everything: R5 picks, payoffs,
exotics (+ post-scratch A/B), CompareModels, and the paper trackers.

Usage:
    python3 Claude/r5_results_cli.py Results/2026/20260712SARUSA0.pdf
    python3 Claude/r5_results_cli.py Results/2026/20260712SARUSA0.pdf --no-docs
    python3 Claude/r5_results_cli.py SAR 20260712 Results/2026/20260712SARUSA0.pdf  # explicit form

Track/date are derived from the Equibase filename (YYYYMMDDTRACKUSA0.pdf);
pass them explicitly if the filename is non-standard.

What it does:
    1. Payoffs ingest      → race_payoffs + race_finish_order + reconcile picks
                             (r5_payoffs.py; auto-fills picks when result_fetched=0)
    2. Finalize R5         → mark remaining NULL positions as late scratches
                             (aborts any race with >3 NULLs — verify vs the PDF
                              scratch lines, mark those picks finish_pos=-1, re-run)
    3. Settle exotics      → paper tickets P/L; auto-runs post-scratch A/B monitor
    4. CM results          → pull results from R5 DB into CM DB + finalize
    5. Settle paper trackers → rank3_tracker + val_n_tracker
    6. Summary             → R5 rank-1 per race, wins, top-3
    7. Docs (skip: --no-docs) → cm1_compare card report + r5_analyze workbook

CM1 needs no settle step — cm1_compare reads winners from r5_results.db.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR        = HORSE_RACING_ROOT / "Claude"
from r5_paths import R5_DB_PATH, find_chart_pdf_by_name
CM_CLI            = HORSE_RACING_ROOT / "comparemodels" / "comparemodels_cli.py"
CM1_COMPARE       = HORSE_RACING_ROOT / "comparemodels" / "cm1_compare.py"


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _step(n, total, title):
    print(f"\n{'='*64}")
    print(f"  STEP {n}/{total} — {title}")
    print(f"{'='*64}\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run_docs = "--no-docs" not in sys.argv

    if len(args) == 1:
        # Just the PDF — derive track/date from the Equibase filename convention
        import re
        pdf_arg = args[0]
        m = re.match(r"(\d{8})([A-Za-z]+?)(?:USA)?\d*\.pdf$", Path(pdf_arg).name, re.IGNORECASE)
        if not m:
            print(f"Can't parse DATE+TRACK from filename: {Path(pdf_arg).name}")
            print("Expected e.g. 20260712SARUSA0.pdf — or pass them explicitly:")
            print("  python3 Claude/r5_results_cli.py TRACK YYYYMMDD results.pdf")
            sys.exit(1)
        date_str = m.group(1)
        track    = m.group(2).upper()
        print(f"  (derived from filename: track={track} date={date_str})")
    elif len(args) >= 3:
        track    = args[0].upper()
        date_str = args[1]
        pdf_arg  = args[2]
    else:
        print("Usage: python3 Claude/r5_results_cli.py results.pdf [--no-docs]")
        print("   or: python3 Claude/r5_results_cli.py TRACK YYYYMMDD results.pdf [--no-docs]")
        print("  e.g. python3 Claude/r5_results_cli.py Results/2026/20260712SARUSA0.pdf")
        sys.exit(1)

    pdf_path = Path(pdf_arg)
    if not pdf_path.exists():
        pdf_path = HORSE_RACING_ROOT / pdf_arg
    if not pdf_path.exists():
        alt = find_chart_pdf_by_name(Path(pdf_arg).name)
        if alt:
            pdf_path = alt
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_arg}")
        sys.exit(1)

    total = 7 if run_docs else 6

    # ── STEP 1: Payoffs ingest (+ pick reconcile) ─────────────────────────────
    _step(1, total, f"Payoffs ingest — {pdf_path.name}")
    rc = subprocess.run(
        [sys.executable, str(CLAUDE_DIR / "r5_payoffs.py"),
         "--track", track, "--date", date_str, "--pdf", str(pdf_path)],
        cwd=str(HORSE_RACING_ROOT)).returncode
    if rc != 0:
        print("❌ Payoffs ingest failed — aborting (nothing downstream can settle)")
        sys.exit(1)

    # ── STEP 2: Finalize R5 (late scratches) ──────────────────────────────────
    _step(2, total, "Finalize R5 (detect late scratches)")
    tracker = _load("r5_tracker", CLAUDE_DIR / "r5_tracker.py")
    tracker.finalize_card(track, date_str)

    # ── STEP 3: Settle exotics (+ post-scratch A/B) ───────────────────────────
    _step(3, total, "Settle exotics tickets (+ post-scratch A/B)")
    subprocess.run(
        [sys.executable, str(CLAUDE_DIR / "r5_exotics.py"),
         "--settle", "--track", track, "--date", date_str],
        cwd=str(HORSE_RACING_ROOT))

    # ── STEP 4: CM results + finalize ─────────────────────────────────────────
    _step(4, total, "CompareModels Results + Finalize")
    subprocess.run([sys.executable, str(CM_CLI), "results",  track, date_str],
                   cwd=str(HORSE_RACING_ROOT))
    subprocess.run([sys.executable, str(CM_CLI), "finalize", track, date_str],
                   cwd=str(HORSE_RACING_ROOT))

    # ── STEP 5: Settle paper trackers ─────────────────────────────────────────
    _step(5, total, "Settle paper trackers (rank3 + val_n)")
    probability = _load("r5_probability", CLAUDE_DIR / "r5_probability.py")
    n_r3  = tracker.settle_rank3_bets()
    n_val = probability.settle_val_bets()
    print(f"  rank3_tracker: {n_r3} bets settled")
    print(f"  val_n_tracker: {n_val} bets settled")
    tracker.rank3_status()

    # ── STEP 6: Summary ───────────────────────────────────────────────────────
    _step(6, total, f"📊 RESULTS SUMMARY — {track} {date_str}")
    _print_summary(track, date_str)

    # ── STEP 7: Docs ──────────────────────────────────────────────────────────
    if run_docs:
        _step(7, total, "Docs — CM1 compare report + analysis workbook")
        subprocess.run([sys.executable, str(CM1_COMPARE), track, "--from", date_str],
                       cwd=str(HORSE_RACING_ROOT))
        subprocess.run([sys.executable, str(CLAUDE_DIR / "r5_analyze.py")],
                       cwd=str(HORSE_RACING_ROOT))

    print(f"\n{'='*64}")
    print(f"  ✅ Pipeline complete — {track} {date_str}")
    if not run_docs:
        print(f"  Docs skipped: python3 comparemodels/cm1_compare.py {track} --from {date_str}")
        print(f"                python3 Claude/r5_analyze.py")
    print(f"{'='*64}\n")


def _print_summary(track: str, date_str: str):
    """Show how R5 rank-1 picks performed against the chart."""
    import sqlite3
    r5_db = R5_DB_PATH
    if not r5_db.exists():
        return

    conn = sqlite3.connect(str(r5_db))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT r.race_num, p.pgm, p.horse_name, p.tier, p.finish_pos, p.sp_odds
        FROM picks p JOIN races r ON p.race_id = r.id
        WHERE r.track = ? AND r.date = ? AND p.model_rank = 1
        ORDER BY CAST(r.race_num AS INT)
    """, (track, date_str)).fetchall()
    conn.close()

    wins = top3 = races = 0
    for row in rows:
        pos = row["finish_pos"]
        if pos is None:
            pos_str, icon = "?", "  "
        elif pos == -1:
            pos_str, icon = "SCR", "  "
        else:
            races += 1
            if pos == 1:
                wins += 1
            if pos in (1, 2, 3):
                top3 += 1
            pos_str = f"#{pos}"
            icon = {1: "🏆", 2: "🥈", 3: "🥉"}.get(pos, "  ")
        sp_str = f"  ${row['sp_odds']:.2f}" if row["sp_odds"] else ""
        print(f"  {icon} R{row['race_num']:<2}  #{row['pgm']} {str(row['horse_name']):<22}  "
              f"{str(row['tier']):<5}  finished {pos_str}{sp_str}")

    if races:
        print(f"\n  Wins:  {wins}/{races} ({wins/races*100:.0f}%)")
        print(f"  Top-3: {top3}/{races} ({top3/races*100:.0f}%)")


if __name__ == "__main__":
    main()
