"""
CM1 tracker — logs CM1's per-race flag counts and ranks to its OWN database so the model
runs beside R5 and CM. Writes only cm1_results.db; reads DRFs read-only; never touches
r5_results.db or the CM tables (A/B-monitor isolation).

Guards built in from day one (the run_r5 clobber lesson): carries is_backtest, and REFUSES
to overwrite an already-logged card unless --force.

Usage:
    python3 comparemodels/cm1_tracker.py --log "files 2/SAR0712.DRF"
    python3 comparemodels/cm1_tracker.py --log "files 2/SAR0723.DRF" --year 2025 --backtest
    python3 comparemodels/cm1_tracker.py --show SAR 20260712
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from cm1_reader import extract_card
from cm1_engine import score_race, LIVE_FLAGS

CM1_DB = os.path.join(os.path.dirname(__file__), "cm1_results.db")


def canon(pgm):
    return re.sub(r"[A-Za-z]$", "", str(pgm))


def init_db(path=CM1_DB):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS cm1_picks (
        track TEXT, date TEXT, race TEXT, pgm TEXT, base_pgm TEXT, name TEXT,
        flag_count INTEGER, flags TEXT, cm1_rank INTEGER, is_backtest INTEGER DEFAULT 0,
        logged_at TEXT DEFAULT (datetime('now')),
        UNIQUE(track, date, race, pgm))""")
    conn.commit()
    return conn


def log_card(drf_path, year=None, is_backtest=False, force=False):
    stem = os.path.basename(drf_path)
    track = stem[:3].upper()
    date_str = str(year or date.today().year) + stem[3:7]
    conn = init_db()

    existing = conn.execute("SELECT COUNT(*) FROM cm1_picks WHERE track=? AND date=?",
                            (track, date_str)).fetchone()[0]
    if existing and not force:
        print(f"⛔ REFUSING: {track} {date_str} already has {existing} CM1 rows. "
              f"Pass --force to overwrite. Nothing written.")
        conn.close()
        return
    if existing:
        conn.execute("DELETE FROM cm1_picks WHERE track=? AND date=?", (track, date_str))

    card = extract_card(drf_path)
    rows, nraces = [], 0
    for race, horses in card.items():
        nraces += 1
        for s in score_race(horses):
            fired = ",".join(n for n, v in s["flags"].items() if v)
            rows.append((track, date_str, race, s["pgm"], canon(s["pgm"]), s["name"],
                         s["count"], fired, s["cm1_rank"], 1 if is_backtest else 0))
    conn.executemany(
        "INSERT INTO cm1_picks (track,date,race,pgm,base_pgm,name,flag_count,flags,"
        "cm1_rank,is_backtest) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    live = ", ".join(sorted(LIVE_FLAGS))
    print(f"✅ logged {track} {date_str}: {nraces} races, {len(rows)} picks "
          f"({'BACKTEST' if is_backtest else 'live'})")
    print(f"   flags: {live}")
    conn.close()


def show(track, date_str):
    conn = init_db()
    for race in conn.execute("SELECT DISTINCT race FROM cm1_picks WHERE track=? AND date=? "
                             "ORDER BY CAST(race AS INT)", (track.upper(), date_str)):
        rn = race[0]
        print(f"\nR{rn}:")
        for r in conn.execute(
                "SELECT cm1_rank, pgm, name, flag_count, flags FROM cm1_picks "
                "WHERE track=? AND date=? AND race=? ORDER BY cm1_rank",
                (track.upper(), date_str, rn)):
            print(f"  {r[0]:>2}. #{r[1]:>2} {r[2]:<20} [{r[3]}] {r[4]}")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="CM1 tracker")
    ap.add_argument("--log", metavar="DRF")
    ap.add_argument("--year", type=int)
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--show", nargs=2, metavar=("TRACK", "DATE"))
    a = ap.parse_args()
    if a.log:
        log_card(a.log, a.year, a.backtest, a.force)
    elif a.show:
        show(a.show[0], a.show[1])
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
