#!/usr/bin/env python3
"""
backfill_comp_ex_val.py — Session 2, Task 4.

Adds picks.comp_ex_val (the ONLY place this column is created) and backfills
it from logged component vectors via r5_parser_v2.compute_comp_ex_val.
Pre-v3.5 picks (NULL pp_n/best_dist_n) cannot be backfilled and are reported,
not guessed — they drop out of the logit fit and the count must be visible.

Usage: python3 scripts/backfill_comp_ex_val.py
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Claude"))
from r5_parser_v2 import compute_comp_ex_val  # noqa: E402

DB_PATH = ROOT / "Results" / "r5_results.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = {r[1] for r in conn.execute("PRAGMA table_info(picks)")}
    if "comp_ex_val" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN comp_ex_val REAL")

    done = skipped = 0
    for p in conn.execute("SELECT * FROM picks").fetchall():
        v = compute_comp_ex_val(p)
        if v is None:
            skipped += 1
            continue
        conn.execute("UPDATE picks SET comp_ex_val=? WHERE id=?", (v, p["id"]))
        done += 1
    conn.commit()

    sanity = conn.execute(
        "SELECT MIN(comp_ex_val), MAX(comp_ex_val), AVG(comp_ex_val) "
        "FROM picks WHERE comp_ex_val IS NOT NULL").fetchone()
    print(f"comp_ex_val backfill: {done} rows written, "
          f"{skipped} NOT backfillable (pre-v3.5, missing components)")
    print(f"range: {sanity[0]:.2f} .. {sanity[1]:.2f}, mean {sanity[2]:.2f}")
    conn.close()


if __name__ == "__main__":
    main()
