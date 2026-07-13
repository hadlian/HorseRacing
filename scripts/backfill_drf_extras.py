#!/usr/bin/env python3
"""
backfill_drf_extras.py — Session 3A: backfill the new display-only columns
(days_since_last, bris_run_style, quirin_pts, wet_starts, wet_wins,
wet_off_speed, trnr_stats) for historical picks from the DRF files on disk.

Display data only — comp, p_win, and every scored field are untouched.
Picks whose DRF file is missing stay NULL (allowed by the brief).

Usage: python3 scripts/backfill_drf_extras.py
"""

import glob
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Claude"))
from r5_parser_v2 import parse_drf  # noqa: E402
from r5_paths import R5_DB_PATH as DB_PATH, DRF_DIRS  # noqa: E402

COLS = ("days_since_last", "bris_run_style", "quirin_pts",
        "wet_starts", "wet_wins", "wet_off_speed", "trnr_stats")

# DRF field 1 uses Equibase codes; the results DB uses BRIS-style codes
TRACK_MAP = {"CD": "CDX", "DBY": "CDX", "AQU": "BAQ", "SA": "SAX"}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    existing = {r[1] for r in conn.execute("PRAGMA table_info(picks)")}
    ddl = {"bris_run_style": "TEXT", "trnr_stats": "TEXT"}
    for c in COLS:
        if c not in existing:
            conn.execute(f"ALTER TABLE picks ADD COLUMN {c} {ddl.get(c, 'INTEGER')}")

    drf_files = []
    for d in DRF_DIRS:
        drf_files += glob.glob(str(d / "*.DRF"))

    updated = files_used = 0
    for fp in sorted(set(drf_files)):
        try:
            horses = parse_drf(fp)
        except Exception as e:
            print(f"  ⚠️  {Path(fp).name}: parse failed ({e})")
            continue
        n_before = updated
        for h in horses:
            cur = conn.execute("""
                UPDATE picks SET days_since_last=?, bris_run_style=?,
                       quirin_pts=?, wet_starts=?, wet_wins=?,
                       wet_off_speed=?, trnr_stats=?
                WHERE race_id = (SELECT id FROM races WHERE track=? AND
                                 date=? AND race_num=?)
                  AND pgm = ?
            """, (h.get("days_since_last"), h.get("bris_run_style"),
                  h.get("quirin_pts"), h.get("wet_starts"), h.get("wet_wins"),
                  int(h["best_off"]) if h.get("best_off") else None,
                  json.dumps(h["trnr_stats"]) if h.get("trnr_stats") else None,
                  TRACK_MAP.get(h["track"], h["track"]), h["date"],
                  str(h["race"]), h["pgm"]))
            updated += cur.rowcount
        if updated > n_before:
            files_used += 1
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    filled = conn.execute(
        "SELECT COUNT(*) FROM picks WHERE bris_run_style IS NOT NULL "
        "OR days_since_last IS NOT NULL").fetchone()[0]
    print(f"Backfilled {updated} pick rows from {files_used} DRF files "
          f"({filled}/{total} picks now carry 3A display data)")
    conn.close()


if __name__ == "__main__":
    main()
