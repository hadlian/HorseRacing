#!/usr/bin/env python3
"""
r5_card_cli.py — Full pre-race card pipeline (one command)

Runs all three models on a DRF card: R5 analysis (+ save + pick logging +
exotics), CompareModels (CM) logging, and CM1 logging.

Usage:
    python3 Claude/r5_card_cli.py "files 2/SAR0713.DRF"
    python3 Claude/r5_card_cli.py "files 2/SAR0713.DRF" --wet
    python3 Claude/r5_card_cli.py "files 2/SAR0712.DRF" --year 2025 --backtest

What it does:
    1. R5    → run_r5.py DRF --save --track  (+ any pass-through flags)
               Aborts the chain if run_r5 refuses (e.g. settled-card guard).
    2. CM    → comparemodels_cli.py log TRACK YYYYMMDD
               (CM locates the DRF itself under "files 2/" — keep cards there)
    3. CM1   → cm1_tracker.py --log DRF (+ --year/--backtest)

Pass-through flags: --wet --live --auto-scout --pdf --force
Historical cards REQUIRE --year/--backtest (else: live phantom card).

Post-race counterpart: r5_results_cli.py TRACK YYYYMMDD chart.pdf
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR        = HORSE_RACING_ROOT / "Claude"
from r5_paths import DRF_DIR, RESULTS_DIR
CM_CLI            = HORSE_RACING_ROOT / "comparemodels" / "comparemodels_cli.py"
CM1_TRACKER       = HORSE_RACING_ROOT / "comparemodels" / "cm1_tracker.py"


def _step(n, title):
    print(f"\n{'='*64}\n  STEP {n}/3 — {title}\n{'='*64}\n", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Pre-race pipeline: R5 + CM + CM1 on one DRF")
    ap.add_argument("drf", help='DRF file, e.g. "files 2/SAR0713.DRF"')
    ap.add_argument("--wet",        action="store_true", help="pass --wet to run_r5")
    ap.add_argument("--live",       action="store_true", help="pass --live to run_r5")
    ap.add_argument("--auto-scout", action="store_true", help="pass --auto-scout to run_r5")
    ap.add_argument("--pdf",        action="store_true", help="also save R5 output as PDF")
    ap.add_argument("--force",      action="store_true", help="pass --force to run_r5/cm1 (override guards)")
    ap.add_argument("--year",     type=int, help="historical card year (REQUIRED for old DRFs)")
    ap.add_argument("--backtest", action="store_true", help="tag as backtest (REQUIRED for old DRFs)")
    a = ap.parse_args()

    drf_path = Path(a.drf)
    if not drf_path.exists():
        drf_path = HORSE_RACING_ROOT / a.drf
    if not drf_path.exists():
        drf_path = DRF_DIR / Path(a.drf).name
    if not drf_path.exists():
        print(f'Error: DRF not found: {a.drf} (also looked in "files 2/")')
        sys.exit(1)

    m = re.match(r"([A-Za-z]+)(\d{4})\.DRF$", drf_path.name, re.IGNORECASE)
    if not m:
        print(f"Error: can't parse TRACK+MMDD from filename: {drf_path.name} (expected e.g. SAR0713.DRF)")
        sys.exit(1)
    track    = m.group(1).upper()
    date_str = str(a.year or date.today().year) + m.group(2)

    # ── STEP 1: R5 ────────────────────────────────────────────────────────────
    _step(1, f"R5 — {drf_path.name} (--save --track)")
    cmd = [sys.executable, str(CLAUDE_DIR / "run_r5.py"), str(drf_path), "--save", "--track"]
    for flag in ("wet", "live", "pdf", "force"):
        if getattr(a, flag):
            cmd.append(f"--{flag}")
    if a.auto_scout:
        cmd.append("--auto-scout")
    if a.year:
        cmd += ["--year", str(a.year)]
    if a.backtest:
        cmd.append("--backtest")
    rc = subprocess.run(cmd, cwd=str(HORSE_RACING_ROOT)).returncode
    if rc != 0:
        print("❌ run_r5 refused/failed — stopping (CM/CM1 not logged, keeps models in sync)")
        sys.exit(rc)

    # ── STEP 2: CM ────────────────────────────────────────────────────────────
    _step(2, f"CompareModels — log {track} {date_str}")
    subprocess.run([sys.executable, str(CM_CLI), "log", track, date_str],
                   cwd=str(HORSE_RACING_ROOT))

    # ── STEP 3: CM1 ───────────────────────────────────────────────────────────
    _step(3, f"CM1 — log {drf_path.name}")
    cmd = [sys.executable, str(CM1_TRACKER), "--log", str(drf_path)]
    if a.year:
        cmd += ["--year", str(a.year)]
    if a.backtest:
        cmd.append("--backtest")
    if a.force:
        cmd.append("--force")
    subprocess.run(cmd, cwd=str(HORSE_RACING_ROOT))

    print(f"\n{'='*64}")
    print(f"  ✅ Card pipeline complete — {track} {date_str} (R5 + CM + CM1 logged)")
    print(f"  After the races: python3 Claude/r5_results_cli.py "
          f"{RESULTS_DIR / date_str[:4] / f'{date_str}{track}USA0.pdf'}")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
