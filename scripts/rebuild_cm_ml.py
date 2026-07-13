"""One-off (2026-06-11): rebuild comparemodels picks.morning_line in odds-to-1
units after the _parse_ml fix. Old rows mixed decimal (fractional MLs) with
odds-to-1 (plain floats). Re-parses each card's DRF and updates in place.
"""

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Claude'))

from comparemodels.drf_reader import parse_drf
from r5_paths import DRF_DIR  # noqa: E402

CM_DB = os.path.join(ROOT, 'comparemodels', 'comparemodels_results.db')
FILES_DIR = str(DRF_DIR)


def main():
    con = sqlite3.connect(CM_DB)
    cur = con.cursor()
    cards = cur.execute(
        "SELECT DISTINCT track, race_date FROM picks ORDER BY race_date, track"
    ).fetchall()

    missing, total_updated = [], 0
    for track, race_date in cards:
        drf = os.path.join(FILES_DIR, f"{track}{race_date[4:]}.DRF")
        if not os.path.exists(drf):
            missing.append((track, race_date))
            continue
        updated = 0
        for h in parse_drf(drf):
            ml = h['morning_line']
            ml_val = float(ml) if ml else None
            try:
                race = int(str(h['race']).strip())
            except ValueError:
                continue
            cur.execute(
                "UPDATE picks SET morning_line=? WHERE track=? AND race_date=? AND race=? AND horse_pgm=?",
                (ml_val, track, race_date, race, h['pgm'].strip()),
            )
            updated += cur.rowcount
        total_updated += updated
        print(f"  {track} {race_date}: {updated} morning_line values rebuilt")

    if missing:
        # No DRF found — NULL out rather than leave mixed units
        for track, race_date in missing:
            cur.execute(
                "UPDATE picks SET morning_line=NULL WHERE track=? AND race_date=?",
                (track, race_date),
            )
            print(f"  ⚠️  {track} {race_date}: DRF not found — morning_line set NULL")

    con.commit()
    n_null = cur.execute(
        "SELECT COUNT(*) FROM picks WHERE morning_line IS NULL").fetchone()[0]
    n_all = cur.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    con.close()
    print(f"\nDone. {total_updated} rows updated; {n_null}/{n_all} NULL morning_line.")


if __name__ == '__main__':
    main()
