"""
CompareModels one-shot backfill runner.
Iterates the 63-race universe from r5_results.db (read-only) and scores each card.
"""

import csv
import hashlib
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

R5_DB = os.path.join(os.path.dirname(__file__), '..', 'results', 'r5_results.db')
FILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'files 2')
CM_CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv')

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comparemodels.drf_to_csv import convert_drf_to_csv, parse_ml
from comparemodels.comparemodels_engine import score_card
from comparemodels.comparemodels_tracker import (
    init_db, log_card_with_ml, pull_results, finalize, write_meta
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def get_cards_from_r5() -> list[tuple[str, str, int]]:
    """Return [(track, date, race_count), ...] for result_fetched=1 cards."""
    con = sqlite3.connect(f"file:{os.path.abspath(R5_DB)}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("""
        SELECT track, date, COUNT(*) as n
        FROM races
        WHERE result_fetched = 1
        GROUP BY track, date
        ORDER BY date, track
    """)
    rows = cur.fetchall()
    con.close()
    return rows


def build_ml_map(csv_path: str) -> dict:
    """Return {(race_int, pgm_str): ml_float} from a generated CM CSV."""
    ml_map = {}
    with open(csv_path, 'r') as f:
        data_lines = [l for l in f if not l.startswith('#')]
    reader = csv.DictReader(data_lines)
    for row in reader:
        try:
            race = int(str(row['race']).strip())
        except Exception:
            continue
        pgm = row['pgm'].strip()
        ml_raw = row.get('morning_line', '')
        ml = None
        if ml_raw and ml_raw.strip():
            try:
                ml = float(ml_raw.strip())
            except Exception:
                pass
        ml_map[(race, pgm)] = ml
    return ml_map


def run_backfill():
    print("=" * 60)
    print("COMPAREMODELS V1 BACKFILL")
    print("=" * 60)

    # Step 1 — Integrity check
    pre_hash = sha256_file(R5_DB)
    print(f"\nPre-backfill SHA-256 r5_results.db: {pre_hash}")

    r5_con = sqlite3.connect(f"file:{os.path.abspath(R5_DB)}?mode=ro", uri=True)
    r5_cur = r5_con.cursor()

    r5_cur.execute("SELECT COUNT(*) FROM races WHERE result_fetched = 1")
    race_count = r5_cur.fetchone()[0]
    print(f"Races with result_fetched=1: {race_count}")
    if race_count < 63:
        print(f"HALT: expected at least 63 races, got {race_count}")
        r5_con.close()
        sys.exit(1)

    # Print schema summaries
    print("\n=== r5_results.db schema ===")
    for tbl in ('races', 'picks'):
        r5_cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'")
        row = r5_cur.fetchone()
        if row:
            print(row[0][:200])

    # Distinct track/date pairs
    print("\n=== Track/date pairs (result_fetched=1) ===")
    r5_cur.execute("""
        SELECT track, date, COUNT(*) as n
        FROM races WHERE result_fetched=1
        GROUP BY track, date ORDER BY date, track
    """)
    for row in r5_cur.fetchall():
        print(f"  {row[0]} {row[1]}: {row[2]} races")

    # LRL0516.csv inspection
    lrl_csv = os.path.join(FILES_DIR, 'LRL0516.csv')
    print(f"\n=== LRL0516.csv inspection ===")
    if os.path.exists(lrl_csv):
        with open(lrl_csv, 'r', errors='replace') as f:
            lines = f.readlines()
        print(f"File exists — {len(lines)} lines. First row preview:")
        print(lines[0][:200] if lines else "(empty)")
        # Check if it's a BRIS Summary CSV (has CM column headers)
        first_row = lines[0] if lines else ''
        if 'avg_speed' in first_row.lower() or 'prime_power' in first_row.lower():
            print("Decision: BRIS Summary CSV format — usable directly as CM input.")
            lrl_direct = True
        else:
            print("Decision: Raw DRF comma-delimited format — NOT usable directly. Using LRL0516.DRF.")
            lrl_direct = False
    else:
        print("LRL0516.csv not found — will use LRL0516.DRF.")
        lrl_direct = False

    r5_con.close()

    # Step 2 — Init CM DB
    print("\n=== Initialising CompareModels DB ===")
    init_db()
    print(f"CM DB: {os.path.abspath(os.path.join(os.path.dirname(__file__), 'comparemodels_results.db'))}")

    # Step 3 — Process each card
    cards = get_cards_from_r5()
    not_found = []
    total_races = 0
    total_picks = 0
    total_matched = 0
    total_unmatched = 0
    cards_processed = 0

    print(f"\n=== Processing {len(cards)} cards ===\n")

    for track, race_date, n_races in cards:
        mmdd = race_date[4:8]
        drf_path = os.path.join(FILES_DIR, f"{track.upper()}{mmdd}.DRF")
        csv_out  = os.path.join(CM_CSV_DIR, f"{track}_{race_date}.csv")

        print(f"--- {track} {race_date} ({n_races} races) ---")

        # Check DRF file
        if not os.path.exists(drf_path):
            print(f"  HALT: DRF file not found: {drf_path}")
            not_found.append(drf_path)
            print(f"Stop condition: missing DRF file. Halting.")
            sys.exit(1)

        # a) Convert DRF → CSV
        rows_written = convert_drf_to_csv(drf_path, csv_out)
        print(f"  DRF → CSV: {rows_written} horse rows → {csv_out}")

        # b) Score card
        score_dict = score_card(csv_out)
        n_scored_races = len(score_dict)
        print(f"  Scored {n_scored_races} races")

        # c) Build ML map
        ml_map = build_ml_map(csv_out)

        # d) Log to DB (category_picks then picks)
        picks_w, cat_picks_w = log_card_with_ml(score_dict, track, race_date, ml_map)
        print(f"  DB: {picks_w} picks, {cat_picks_w} category_picks logged")

        # e) Pull results from r5_results.db
        matched, unmatched = pull_results(track, race_date)
        print(f"  Results joined: {matched} matched, {unmatched} unmatched pgms")

        # f) Finalize scratches
        finalize(track, race_date)

        total_races    += n_races   # from DB — authoritative 63-race universe
        total_picks    += picks_w
        total_matched  += matched
        total_unmatched += unmatched
        cards_processed += 1

    # Step 4 — Final summary
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"Cards processed:   {cards_processed}")
    print(f"Total races:       {total_races}")
    print(f"Total picks:       {total_picks}")
    print(f"Results matched:   {total_matched}")
    print(f"Results unmatched: {total_unmatched}")
    if not_found:
        print(f"DRF files not found: {not_found}")

    if total_races < 63:
        print(f"\nHALT: expected at least 63 races total, got {total_races}")
        sys.exit(1)

    print(f"\n✓ Race count check passed: {total_races} races")

    # Step 5 — Write meta
    now = datetime.now(timezone.utc).isoformat()
    write_meta({
        'cm_version':        '1.0',
        'backfill_complete': '1',
        'race_count':        str(total_races),
        'last_backfill_at':  now,
    })
    print(f"Meta written (last_backfill_at={now})")

    # Step 6 — Post-integrity check
    post_hash = sha256_file(R5_DB)
    print(f"\nPost-backfill SHA-256 r5_results.db: {post_hash}")
    if pre_hash == post_hash:
        print("r5_results.db integrity: MATCH ✓")
    else:
        print("r5_results.db integrity: MISMATCH ✗ — DB was modified!")
        sys.exit(1)


if __name__ == '__main__':
    run_backfill()
