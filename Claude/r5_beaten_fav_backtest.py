#!/usr/bin/env python3
"""
r5_beaten_fav_backtest.py
Backtest the beaten-favorite signal (DRF fields 1126-1135) against the R5 results DB.

Methodology:
  - Parse every DRF file in `files 2/`
  - For each horse, extract favorite indicators (fields 1126-1135) and past
    finishes (fields 616-625) for their last 10 starts
  - Tag each horse: beaten_fav_1 (was favorite AND lost in last start only)
                    beaten_fav_2 (was favorite AND lost in either of last 2 starts)
  - Match to DB picks by filename-derived track code + DRF date + race + horse name
  - Compare win rate and ROI across three groups:
      A. Beaten favorite (either definition)
      B. Was favorite but WON last start (hot chalk — no recency penalty)
      C. Never favored in last 2 starts (baseline)
"""

import csv
import glob
import sqlite3
from pathlib import Path

DB_PATH  = Path(__file__).resolve().parent.parent / "results" / "r5_results.db"
DRF_GLOB = str(Path(__file__).resolve().parent.parent / "files 2" / "*.DRF")


def pf(row, idx):
    try:
        v = row[idx - 1]
        return v.strip() if v else ""
    except IndexError:
        return ""


def num(row, idx):
    try:
        v = pf(row, idx)
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def parse_fav_data(drf_path):
    """Extract horse-level beaten-favorite data from a DRF file."""
    track_code = Path(drf_path).stem[:3].upper()   # e.g. CDX, BAQ, LRL
    horses = []
    with open(drf_path) as f:
        for row in csv.reader(f):
            if not row or len(row) < 200:
                continue
            date     = pf(row, 2)   # YYYYMMDD
            race     = pf(row, 3).strip()
            name     = pf(row, 45)
            if not name:
                continue

            # Favorite indicators: fields 1126-1135 (1=was betting favorite, 0/blank=not)
            fav = [pf(row, 1126 + i) for i in range(10)]

            # Past finishes: fields 616-625
            finish = [num(row, 616 + i) for i in range(10)]

            def was_beaten_fav(start_idx):
                """True if horse was betting favorite AND finished 2nd or worse in that start."""
                f_ind = fav[start_idx] if start_idx < len(fav) else ''
                f_pos = finish[start_idx] if start_idx < len(finish) else None
                return f_ind == '1' and f_pos is not None and f_pos > 1

            def was_winning_fav(start_idx):
                """True if horse was betting favorite AND won that start."""
                f_ind = fav[start_idx] if start_idx < len(fav) else ''
                f_pos = finish[start_idx] if start_idx < len(finish) else None
                return f_ind == '1' and f_pos == 1.0

            beaten_fav_1 = was_beaten_fav(0)                      # last start only
            beaten_fav_2 = was_beaten_fav(0) or was_beaten_fav(1) # either of last 2
            winning_fav  = was_winning_fav(0)                     # won as fav last time

            horses.append({
                'track': track_code,
                'date':  date,
                'race':  race,
                'name':  name,
                'beaten_fav_1': beaten_fav_1,
                'beaten_fav_2': beaten_fav_2,
                'winning_fav':  winning_fav,
                'fav_last1':    fav[0] == '1',
                'fav_last2':    fav[0] == '1' or fav[1] == '1',
            })
    return horses


def main():
    conn = sqlite3.connect(DB_PATH)

    # Load all DB picks with outcomes
    db_picks = conn.execute('''
        SELECT r.track, r.date, r.race_num, p.horse_name,
               p.finish_pos, p.won, p.model_rank, p.comp, p.sp_odds, p.ml_odds
        FROM picks p
        JOIN races r ON p.race_id = r.id
        WHERE p.finish_pos IS NOT NULL AND p.finish_pos != -1
    ''').fetchall()

    # Index DB picks: (track, date, race, name) -> row
    db_index = {}
    for row in db_picks:
        key = (row[0].strip().upper(), str(row[1]).strip(),
               str(row[2]).strip(), row[3].strip().upper())
        db_index[key] = row

    # Parse all DRF files
    drf_files = sorted(glob.glob(DRF_GLOB))
    print(f"DRF files found: {len(drf_files)}")

    matched = 0
    unmatched = 0
    tagged = []

    for drf_path in drf_files:
        for h in parse_fav_data(drf_path):
            key = (h['track'], h['date'], h['race'], h['name'].upper())
            if key not in db_index:
                unmatched += 1
                continue
            matched += 1
            db_row = db_index[key]
            tagged.append({
                **h,
                'finish_pos':   db_row[4],
                'won':          db_row[5],
                'model_rank':   db_row[6],
                'comp':         db_row[7],
                'sp_odds':      db_row[8],
                'ml_odds':      db_row[9],
            })

    print(f"Matched: {matched}  |  Unmatched: {unmatched}\n")

    def stats(group, label):
        n = len(group)
        if n == 0:
            print(f"  {label}: no data")
            return
        wins  = sum(1 for h in group if h['won'])
        top3  = sum(1 for h in group if h['finish_pos'] and h['finish_pos'] <= 3)
        r1    = sum(1 for h in group if h['model_rank'] == 1)

        sp_group = [h for h in group if h['sp_odds'] and h['sp_odds'] > 0]
        if sp_group:
            returns = sum(h['sp_odds'] + 1 for h in sp_group if h['won'])
            roi = (returns - len(sp_group)) / len(sp_group) * 100
            roi_str = f"SP ROI {roi:+.1f}% (n={len(sp_group)})"
        else:
            roi_str = "SP ROI N/A"

        ml_group = [h for h in group if h['ml_odds'] and h['ml_odds'] > 0]
        if ml_group:
            ml_ret = sum(h['ml_odds'] + 1 for h in ml_group if h['won'])
            ml_roi = (ml_ret - len(ml_group)) / len(ml_group) * 100
            ml_str = f"ML ROI {ml_roi:+.1f}%"
        else:
            ml_str = ""

        print(f"  {label}")
        print(f"    n={n}  wins={wins} ({wins/n*100:.1f}%)  "
              f"top-3={top3} ({top3/n*100:.1f}%)  "
              f"model-R1={r1} ({r1/n*100:.1f}%)  "
              f"{roi_str}  {ml_str}")

    # ── MAIN RESULTS ──
    print("=" * 70)
    print("BEATEN-FAVORITE SIGNAL BACKTEST")
    print("=" * 70)

    print("\n--- Definition 1: beaten as favorite in LAST START ONLY ---")
    bf1_yes = [h for h in tagged if h['beaten_fav_1']]
    bf1_no  = [h for h in tagged if not h['beaten_fav_1'] and not h['winning_fav']]
    wf      = [h for h in tagged if h['winning_fav']]
    stats(bf1_yes, "BEATEN FAV last start")
    stats(wf,      "WON as fav last start  (hot chalk)")
    stats(bf1_no,  "Not favored last start (baseline)")

    print("\n--- Definition 2: beaten as favorite in EITHER of last 2 starts ---")
    bf2_yes = [h for h in tagged if h['beaten_fav_2']]
    bf2_no  = [h for h in tagged if not h['beaten_fav_2']]
    stats(bf2_yes, "BEATEN FAV last 1 or 2 starts")
    stats(bf2_no,  "Not beaten fav in last 2 (baseline)")

    print("\n--- Model Rank 1 picks only: does beaten-fav flag predict misses? ---")
    r1_all   = [h for h in tagged if h['model_rank'] == 1]
    r1_bf    = [h for h in r1_all if h['beaten_fav_1']]
    r1_nobf  = [h for h in r1_all if not h['beaten_fav_1']]
    stats(r1_bf,   "Model R1 + beaten fav last start")
    stats(r1_nobf, "Model R1 + NOT beaten fav last start")

    print("\n--- Surface split (beaten-fav-1 only) ---")
    conn2 = sqlite3.connect(DB_PATH)
    surf_map = {
        (row[0].strip().upper(), str(row[1]).strip(), str(row[2]).strip(),
         row[3].strip().upper()): row[4]
        for row in conn2.execute('''
            SELECT r.track, r.date, r.race_num, p.horse_name, r.surface
            FROM picks p JOIN races r ON p.race_id = r.id
        ''').fetchall()
    }
    for h in tagged:
        key = (h['track'], h['date'], h['race'], h['name'].upper())
        h['surface'] = surf_map.get(key, '')

    for surf in ['D', 'T', 'A']:
        bf_surf = [h for h in tagged if h['beaten_fav_1'] and h['surface'] == surf]
        base_surf = [h for h in tagged if not h['beaten_fav_1'] and h['surface'] == surf]
        if bf_surf:
            stats(bf_surf,   f"BEATEN FAV last start — {surf}")
            stats(base_surf, f"Not beaten fav last start — {surf}")

    print()


if __name__ == "__main__":
    main()
