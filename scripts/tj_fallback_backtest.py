#!/usr/bin/env python3
"""
tj_fallback_backtest.py — Session 3B RESEARCH ONLY. No live-engine changes.

Question: tj_n (the strongest component, +0.80 winner-diff, 15% weight) uses
CURRENT-MEET trainer/jockey stats (fields 29/30, 35/36) gated on starts >= 20,
falling back to a hard-coded elite-name list. At a meet opening those stats
are near zero, so tj_n degrades to name-matching — plausibly part of the
9.4% SAR opener drag. Fields 1147/1148 (trainer year) and 1157/1158 (jockey
year) carry full current-year records.

Method:
  - Reparse every DRF on disk; map horses to picks by (track, date, race, pgm).
  - Recompute tj_n under the PROPOSED chain: meet stats if >= 20 starts,
    else YEAR stats if >= 20 starts, else elite-name fallback.
  - delta_comp = 0.15 x (tj_proposed - stored tj_n); re-rank each race by
    comp + delta (tj enters the composite linearly, so the swap is exact up
    to rounding).
  - Corrected ROI ($2 flat, profit = sp_odds - 2 / -2) for rank-1 under the
    stored vs proposed ranking; overall and SAR-only.

Usage: python3 scripts/tj_fallback_backtest.py
"""

import csv
import glob
import sqlite3
import sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "Results" / "r5_results.db"
DRF_DIRS = [ROOT / "files 2", ROOT / "TXT_Files", ROOT / "database"]
TRACK_MAP = {"CD": "CDX", "DBY": "CDX", "AQU": "BAQ", "SA": "SAX"}

# replicated from r5_parser_v2.parse_drf (research copy — do not import live)
ELITE_T = ['PLETCHER', 'BAFFERT', 'ASMUSSEN', 'BROWN', 'COX', 'MCPEEK',
           'MOTT', 'WALSH', 'MOTION', 'ATTFIELD', 'SADLER', 'SHIRREFFS']
ELITE_J = ['ORTIZ', 'VELAZQUEZ', 'SAEZ', 'FRANCO', 'CASTELLANO',
           'ROSARIO', 'GAFFALIONE', 'GEROUX', 'PRAT', 'ESPINOZA',
           'GUTIERREZ', 'HERNANDEZ', 'TALAMO']
TJ_WEIGHT = 0.15
MIN_STARTS = 20


def fnum(row, i):
    try:
        v = row[i - 1].strip().replace(",", "")
        return float(v) if v else None
    except (IndexError, ValueError):
        return None


def fstr(row, i):
    try:
        return row[i - 1].strip()
    except IndexError:
        return ""


def tj_block(starts, wins, name, elite, year_starts, year_wins, proposed):
    """One leg (trainer or jockey) of tj_n under current or proposed chain."""
    if starts and starts >= MIN_STARTS:
        return min(3.5, (wins / starts) * 12)
    if proposed and year_starts and year_starts >= MIN_STARTS:
        return min(3.5, ((year_wins or 0) / year_starts) * 12)
    if any(e in name.upper() for e in elite):
        return 2.5
    return 0.0


def tj_n_calc(h, proposed):
    tj = 3.0
    tj += tj_block(h["t_meet_sts"], h["t_meet_w"], h["trainer"], ELITE_T,
                   h["t_yr_sts"], h["t_yr_w"], proposed)
    tj += tj_block(h["j_meet_sts"], h["j_meet_w"], h["jockey"], ELITE_J,
                   h["j_yr_sts"], h["j_yr_w"], proposed)
    if (h["tj_sts"] or 0) >= 5 and (h["tj_w"] or 0) / max(h["tj_sts"], 1) > 0.2:
        tj = min(tj + 0.5, 10.0)
    return min(tj, 10.0)


def load_drf_horses():
    horses = {}
    for d in DRF_DIRS:
        for fp in glob.glob(str(d / "*.DRF")):
            for row in csv.reader(open(fp)):
                if not row or len(row) < 1160:
                    continue
                trk = TRACK_MAP.get(fstr(row, 1), fstr(row, 1))
                key = (trk, fstr(row, 2), fstr(row, 3), fstr(row, 4))
                horses[key] = {
                    "trainer": fstr(row, 28), "jockey": fstr(row, 33),
                    "t_meet_sts": fnum(row, 29) or 0, "t_meet_w": fnum(row, 30) or 0,
                    "j_meet_sts": fnum(row, 35) or 0, "j_meet_w": fnum(row, 36) or 0,
                    "tj_sts": fnum(row, 219) or 0, "tj_w": fnum(row, 220) or 0,
                    "t_yr_sts": fnum(row, 1147), "t_yr_w": fnum(row, 1148),
                    "j_yr_sts": fnum(row, 1157), "j_yr_w": fnum(row, 1158),
                }
    return horses


def roi(rows):
    bets = wins = 0
    profit = 0.0
    for r in rows:
        if r["finish_pos"] is None or r["finish_pos"] == -1:
            continue
        bets += 1
        if r["won"]:
            wins += 1
            profit += (r["sp_odds"] - 2) if r["sp_odds"] else 0.0
        else:
            profit -= 2
    return bets, wins, profit


def main():
    drf = load_drf_horses()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    races = conn.execute(
        "SELECT * FROM races WHERE result_fetched=1 AND is_backtest=0 ORDER BY date").fetchall()

    n_matched = n_changed = 0
    deltas = []
    old_r1, new_r1 = [], []
    old_r1_sar, new_r1_sar = [], []
    fallback_counts = {"meet": 0, "year": 0, "elite_or_floor": 0}
    rank1_changed_races = 0

    for race in races:
        picks = conn.execute(
            "SELECT * FROM picks WHERE race_id=? AND "
            "(finish_pos IS NULL OR finish_pos != -1)", (race["id"],)).fetchall()
        scored = []
        race_matched = True
        for p in picks:
            key = (race["track"], race["date"], race["race_num"], p["pgm"])
            h = drf.get(key)
            if h is None or p["tj_n"] is None or p["comp"] is None:
                race_matched = False
                break
            n_matched += 1
            # fallback-tier census (proposed chain, trainer leg)
            if h["t_meet_sts"] >= MIN_STARTS:
                fallback_counts["meet"] += 1
            elif (h["t_yr_sts"] or 0) >= MIN_STARTS:
                fallback_counts["year"] += 1
            else:
                fallback_counts["elite_or_floor"] += 1

            tj_new = tj_n_calc(h, proposed=True)
            delta = round(TJ_WEIGHT * (tj_new - p["tj_n"]), 3)
            if abs(delta) > 0.005:
                n_changed += 1
                deltas.append(delta)
            scored.append((p, p["comp"] + delta))
        if not race_matched or len(scored) < 2:
            continue

        old_top = min(scored, key=lambda x: x[0]["model_rank"])[0]
        new_top = max(scored, key=lambda x: x[1])[0]
        if new_top["id"] != old_top["id"]:
            rank1_changed_races += 1
        old_r1.append(old_top)
        new_r1.append(new_top)
        if race["track"] == "SAR":
            old_r1_sar.append(old_top)
            new_r1_sar.append(new_top)

    print(f"Matched picks: {n_matched} | tj_n changed: {n_changed} "
          f"({n_changed/max(n_matched,1)*100:.0f}%)")
    if deltas:
        import statistics
        print(f"comp delta when changed: mean {statistics.mean(deltas):+.3f}, "
              f"min {min(deltas):+.3f}, max {max(deltas):+.3f}")
    print(f"Trainer-leg stat source under proposed chain: {fallback_counts}")
    print(f"Races where rank-1 flips: {rank1_changed_races} / {len(old_r1)}")

    print(f"\n{'universe':<22} | {'bets':>4} | {'wins':>4} | {'win%':>5} | {'ROI%':>7}")
    print("-" * 56)
    for label, rows in (("ALL stored rank-1", old_r1),
                        ("ALL proposed rank-1", new_r1),
                        ("SAR stored rank-1", old_r1_sar),
                        ("SAR proposed rank-1", new_r1_sar)):
        b, w, pf = roi(rows)
        if b:
            print(f"{label:<22} | {b:>4} | {w:>4} | {w/b*100:>4.1f}% | "
                  f"{pf/(2*b)*100:>+6.1f}%")
    conn.close()


if __name__ == "__main__":
    main()
