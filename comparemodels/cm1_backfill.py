"""
CM1 Gate-0 backfill — score every result-fetched race point-in-time and test the core
question: does a higher flag count actually pick more winners (and at what ROI)?

Point-in-time throughout: each card is scored using only connection history dated strictly
before it (cm1_stats_db record(date<D)); workout/class/pace flags use only the DRF. Reads
r5_results.db + retained DRFs read-only; writes nothing. Seed the stats DB first
(cm1_stats_db --seed).

Usage:  python3 comparemodels/cm1_backfill.py
"""

import os
import re
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from cm1_reader import extract_card
from cm1_engine import score_race

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R5_DB = os.path.join(ROOT, "Results", "r5_results.db")
FILES_DIR = os.path.join(ROOT, "files 2")
STAKE = 2.0


def _base_pgm(p):
    return re.sub(r"[A-Za-z]$", "", str(p))


def _results(r5, track, date, race):
    rows = r5.execute(
        "SELECT fo.horse_pgm, fo.finish_position, fo.final_tote_odds "
        "FROM race_finish_order fo JOIN races r ON fo.race_id=r.id "
        "WHERE r.track=? AND r.date=? AND r.race_num=? AND fo.finish_position>=1",
        (track, date, str(race))).fetchall()
    return {_base_pgm(p): (1 if f == 1 else 0, o) for p, f, o in rows}


def run():
    r5 = sqlite3.connect(f"file:{R5_DB}?mode=ro", uri=True)
    drfs = {}
    for f in os.listdir(FILES_DIR):
        m = re.match(r"([A-Za-z]{3})(\d{4})\.DRF$", f, re.I)
        if m:
            drfs[(m.group(1).upper(), m.group(2))] = os.path.join(FILES_DIR, f)
    cards = r5.execute(
        "SELECT DISTINCT track, date FROM races WHERE result_fetched=1 ORDER BY date"
    ).fetchall()

    by_count = defaultdict(lambda: [0, 0])          # flag_count → [runners, wins]
    rank1 = {"n": 0, "w": 0, "staked": 0.0, "ret": 0.0, "payoffs": []}
    setcap = {"n": 0, "hit": 0}                      # winner in CM1 top-3?
    races_scored = 0

    for track, date in cards:
        path = drfs.get((track.upper(), date[4:8]))
        if not path:
            continue
        card = extract_card(path)
        for race, horses in card.items():
            res = _results(r5, track, date, race)
            if not res:
                continue
            scored = score_race(horses)
            runners = [s for s in scored if _base_pgm(s["pgm"]) in res]
            if not runners:
                continue
            races_scored += 1
            # win rate by flag count
            for s in runners:
                won, _ = res[_base_pgm(s["pgm"])]
                by_count[s["count"]][0] += 1
                by_count[s["count"]][1] += won
            # CM1 rank-1 ROI (best available runner by rank)
            top = min(runners, key=lambda s: s["cm1_rank"])
            won, odds = res[_base_pgm(top["pgm"])]
            rank1["n"] += 1
            rank1["w"] += won
            rank1["staked"] += STAKE
            if won and odds is not None:
                ret = STAKE * (odds + 1)
                rank1["ret"] += ret
                rank1["payoffs"].append(ret)
            # set-capture: is the actual winner in CM1's top 3?
            top3 = {_base_pgm(s["pgm"]) for s in sorted(runners, key=lambda s: s["cm1_rank"])[:3]}
            winner = [p for p, (w, _) in res.items() if w]
            if winner:
                setcap["n"] += 1
                setcap["hit"] += 1 if winner[0] in top3 else 0

    print(f"CM1 Gate-0 backfill — {races_scored} races scored point-in-time\n")
    print("Win rate by flag count (does more flags = more winners?):")
    print(f"  {'flags':>5} {'runners':>8} {'wins':>5} {'win%':>6}")
    for c in sorted(by_count):
        n, w = by_count[c]
        print(f"  {c:>5} {n:>8} {w:>5} {100*w/n:>5.1f}%")

    roi = (rank1["ret"] - rank1["staked"]) / rank1["staked"] if rank1["staked"] else 0
    ex = rank1["ret"] - (max(rank1["payoffs"]) if rank1["payoffs"] else 0)
    roi_ex = (ex - rank1["staked"]) / rank1["staked"] if rank1["staked"] else 0
    print(f"\nCM1 rank-1 (flat $2 win):")
    print(f"  n={rank1['n']}  wins={rank1['w']} ({100*rank1['w']/rank1['n']:.1f}%)  "
          f"ROI {roi:+.1%}   ex-top-payout {roi_ex:+.1%}")
    print(f"CM1 top-3 set-capture: {setcap['hit']}/{setcap['n']} "
          f"({100*setcap['hit']/setcap['n']:.1f}%)")
    r5.close()


if __name__ == "__main__":
    run()
