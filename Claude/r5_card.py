#!/usr/bin/env python3
"""
r5_card.py — Full pre-race pipeline (one command)

Runs R5 analysis + CompareModels in one shot, logs both to DB.

Usage:
    python3 Claude/r5_card.py SAX0525.DRF
    python3 Claude/r5_card.py "files 2/SAX0525.DRF"

What it does:
    1. R5 analysis  (--auto-scout --save --track)
    2. CompareModels score
    3. CompareModels log to DB
    4. Double-consensus summary
"""

import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

HORSE_RACING_ROOT = Path("/Users/harryadalian/Documents/HorseRacing")
CLAUDE_DIR        = HORSE_RACING_ROOT / "Claude"
CM_CLI            = HORSE_RACING_ROOT / "comparemodels" / "comparemodels_cli.py"
R5_DB             = HORSE_RACING_ROOT / "results" / "r5_results.db"
CM_DB             = HORSE_RACING_ROOT / "comparemodels" / "comparemodels_results.db"


def _resolve_drf(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    # Try relative to files 2/
    p2 = HORSE_RACING_ROOT / "files 2" / arg
    if p2.exists():
        return p2
    # Try just the filename in files 2/
    p3 = HORSE_RACING_ROOT / "files 2" / Path(arg).name
    if p3.exists():
        return p3
    return p  # Return original so error message is clear


def _stem_to_track_date(stem: str) -> tuple:
    """SAX0525 → ('SAX', '20260525')"""
    stem = stem.upper()
    track = stem[:3]
    mmdd  = stem[3:7]
    year  = str(date.today().year)
    return track, year + mmdd


def _print_consensus(track: str, date_str: str):
    """Print double-consensus table: R5 vs CM top pick per race."""
    if not R5_DB.exists() or not CM_DB.exists():
        return

    # R5 top picks
    r5_picks = {}
    try:
        conn = sqlite3.connect(str(R5_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT r.race_num, p.pgm, p.horse_name, p.comp, p.tier, p.ml_odds
            FROM picks p JOIN races r ON p.race_id = r.id
            WHERE r.track = ? AND r.date = ? AND p.model_rank = 1
            ORDER BY CAST(r.race_num AS INT)
        """, (track, date_str)).fetchall()
        conn.close()
        for row in rows:
            r5_picks[str(row["race_num"])] = dict(row)
    except Exception:
        pass

    # CM top picks
    cm_picks = {}
    try:
        conn2 = sqlite3.connect(str(CM_DB))
        conn2.row_factory = sqlite3.Row
        rows2 = conn2.execute("""
            SELECT race_num, pgm, horse_name, composite, consensus_count
            FROM picks
            WHERE track = ? AND race_date = ? AND rank_in_race = 1
            ORDER BY CAST(race_num AS INT)
        """, (track, date_str)).fetchall()
        conn2.close()
        for row in rows2:
            cm_picks[str(row["race_num"])] = dict(row)
    except Exception:
        pass

    if not r5_picks:
        print("  (no R5 picks found in DB — was --track flag used?)")
        return

    consensus = []
    print(f"\n  {'R':<4} {'R5 Pick':<26} {'CM Pick':<26} {'Match'}")
    print(f"  {'-'*4} {'-'*26} {'-'*26} {'-'*5}")
    for rnum in sorted(r5_picks, key=lambda x: int(x)):
        r5  = r5_picks[rnum]
        cm  = cm_picks.get(rnum, {})
        r5s = f"#{r5['pgm']} {str(r5['horse_name'])[:20]}"
        cms = f"#{cm.get('pgm','?')} {str(cm.get('horse_name',''))[:20]}" if cm else "—"
        match = "✅" if cm and str(r5["pgm"]) == str(cm.get("pgm", "")) else "❌"
        if match == "✅":
            consensus.append(rnum)
        ml = r5.get("ml_odds") or ""
        ml_str = f" ({ml}-1 ML)" if ml else ""
        print(f"  R{rnum:<3} {r5s:<26} {cms:<26} {match}  {r5['tier']}{ml_str}")

    print()
    if consensus:
        races_str = ", R".join(consensus)
        print(f"  🎯 Double-consensus: R{races_str}")
        # Show CM consensus counts for flagged races
        for rnum in consensus:
            cm = cm_picks.get(rnum, {})
            cons = cm.get("consensus_count", "?")
            r5  = r5_picks[rnum]
            print(f"     R{rnum}: #{r5['pgm']} {r5['horse_name']}  "
                  f"R5={r5['comp']:.2f} {r5['tier']} | CM cons={cons}")
    else:
        print("  No double-consensus races this card")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 Claude/r5_card.py <DRFFILE>")
        print("  e.g. python3 Claude/r5_card.py SAX0525.DRF")
        sys.exit(1)

    drf_path = _resolve_drf(sys.argv[1])
    if not drf_path.exists():
        print(f"Error: {drf_path} not found")
        sys.exit(1)

    track, date_str = _stem_to_track_date(drf_path.stem)

    # API key check
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set — scout will run without AI extraction")
        print("   To enable: export ANTHROPIC_API_KEY=<your_key>")
        print()

    # ── STEP 1: R5 ────────────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 1/3 — R5 Analysis + Scout + Log to DB")
    print(f"  Card: {track} {date_str}  ({drf_path.name})")
    print(f"{'='*64}\n")

    r5_cmd = [
        sys.executable,
        str(CLAUDE_DIR / "run_r5.py"),
        str(drf_path),
        "--auto-scout",
        "--save",
        "--track",
    ]
    result = subprocess.run(r5_cmd, cwd=str(HORSE_RACING_ROOT))
    if result.returncode != 0:
        print(f"\n❌ R5 analysis failed (exit {result.returncode})")
        sys.exit(1)

    # ── STEP 2: CM score ──────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 2/3 — CompareModels Score")
    print(f"{'='*64}\n")

    subprocess.run([sys.executable, str(CM_CLI), "score", track, date_str],
                   cwd=str(HORSE_RACING_ROOT))

    # ── STEP 3: CM log to DB ──────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  STEP 3/3 — CompareModels Log to DB")
    print(f"{'='*64}\n")

    subprocess.run([sys.executable, str(CM_CLI), "log", track, date_str],
                   cwd=str(HORSE_RACING_ROOT))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  🔀 DOUBLE-CONSENSUS — {track} {date_str}")
    print(f"{'='*64}")
    _print_consensus(track, date_str)

    print(f"\n{'='*64}")
    print(f"  ✅ Pre-race pipeline complete — {track} {date_str}")
    print(f"  After races run, log results:")
    print(f"    python3 Claude/r5_results_cli.py {track} {date_str} <results.pdf>")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
