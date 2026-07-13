"""
CM1 three-model compare report — R5 | CM | CM1 side by side, race-by-race + meet stats.

For each result-fetched race it shows the winner's RANK in each model, CM1's flag count,
and rolls up per-model stats (rank-1 win%, top-3 capture, mean winner-rank, rank-1 ROI) plus
the contender-set capture uplift CM1 adds to R5₁₋₃ ∪ CM₁₋₂ (the Gate-3 number). CM1 is scored
point-in-time from the DRF; R5/CM read from their DBs read-only.

Usage:
    python3 comparemodels/cm1_compare.py SAR                 # all result-fetched SAR cards
    python3 comparemodels/cm1_compare.py SAR --from 20260703 # from a date onward
"""

import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cm1_reader import extract_card
from cm1_engine import score_race

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Claude"))
from r5_paths import DRF_DIR, R5_DB_PATH  # noqa: E402
R5_DB = str(R5_DB_PATH)
CM_DB = os.path.join(os.path.dirname(__file__), "comparemodels_results.db")
FILES_DIR = str(DRF_DIR)
STAKE = 2.0


def base(p):
    return re.sub(r"[A-Za-z]$", "", str(p))


def _drf_for(track, date):
    p = os.path.join(FILES_DIR, f"{track}{date[4:8]}.DRF")
    return p if os.path.exists(p) else None


def report(track, date_from=None):
    r5 = sqlite3.connect(f"file:{R5_DB}?mode=ro", uri=True); r5.row_factory = sqlite3.Row
    cm = sqlite3.connect(f"file:{CM_DB}?mode=ro", uri=True); cm.row_factory = sqlite3.Row
    track = track.upper()
    q = ("SELECT DISTINCT date FROM races WHERE track=? AND result_fetched=1"
         + (" AND date>=?" if date_from else "") + " ORDER BY date")
    dates = [r[0] for r in r5.execute(q, (track, date_from) if date_from else (track,))]

    agg = {m: dict(r1w=0, cap=0, wrank=0, n=0, staked=0.0, ret=0.0, pays=[])
           for m in ("R5", "CM", "CM1")}
    cap_r5cm = cap_all = cm1_only = union_n = 0

    for d in dates:
        drf = _drf_for(track, d)
        if not drf:
            continue
        cm1_by_race = {rn: score_race(hs) for rn, hs in extract_card(drf).items()}
        print(f"\n{'='*64}\n{track} {d[4:6]}/{d[6:8]}   (winner's rank per model; ·=unranked)\n{'='*64}")
        print(f"{'R':>2} {'Winner (odds)':<24}{'R5':>4}{'CM':>4}{'CM1':>5}{'flags':>7}")
        for rc in r5.execute("SELECT id,race_num FROM races WHERE track=? AND date=? "
                             "AND result_fetched=1 ORDER BY CAST(race_num AS INT)", (track, d)):
            rid, rn = rc["id"], rc["race_num"]
            w = r5.execute("SELECT horse_pgm,horse_name,final_tote_odds FROM race_finish_order "
                           "WHERE race_id=? AND finish_position=1", (rid,)).fetchone()
            if not w:
                continue
            wp, od = base(w["horse_pgm"]), w["final_tote_odds"]
            r5r = {base(p["pgm"]): p["model_rank"] for p in
                   r5.execute("SELECT pgm,model_rank FROM picks WHERE race_id=?", (rid,))}
            cmr = {base(x["horse_pgm"]): x["cm_rank"] for x in
                   cm.execute("SELECT horse_pgm,cm_rank FROM picks WHERE track=? AND "
                              "race_date=? AND race=?", (track, d, int(rn)))}
            c1 = {base(s["pgm"]): (s["cm1_rank"], s["count"]) for s in cm1_by_race.get(rn, [])}
            wr5, wcm = r5r.get(wp), cmr.get(wp)
            wc1 = c1.get(wp, (None, None))
            od_s = f"{od:.1f}" if od is not None else "?"
            print(f"{rn:>2} {w['horse_pgm']+' '+w['horse_name'][:17]+' ('+od_s+')':<24}"
                  f"{str(wr5 or '·'):>4}{str(wcm or '·'):>4}{str(wc1[0] or '·'):>5}"
                  f"{('['+str(wc1[1])+']') if wc1[1] is not None else '':>7}")
            # per-model aggregate
            for m, rk, rows in (("R5", wr5, r5r), ("CM", wcm, cmr),
                                ("CM1", wc1[0], {k: v[0] for k, v in c1.items()})):
                if not rows:
                    continue
                a = agg[m]; a["n"] += 1
                a["r1w"] += 1 if rk == 1 else 0
                a["cap"] += 1 if (rk and rk <= 3) else 0
                a["wrank"] += rk if rk else max(rows.values()) + 1
                top = [p for p, r in rows.items() if r == 1]
                if top:
                    a["staked"] += STAKE
                    if top[0] == wp and od is not None:
                        ret = STAKE * (od + 1); a["ret"] += ret; a["pays"].append(ret)
            # union capture
            if r5r and cmr and c1:
                union_n += 1
                r5t3 = {p for p, r in r5r.items() if r <= 3}
                cmt2 = {p for p, r in cmr.items() if r <= 2}
                c1t2 = {p for p, (rk, _) in c1.items() if rk <= 2}
                in2 = wp in r5t3 or wp in cmt2
                cap_r5cm += 1 if in2 else 0
                cap_all += 1 if (in2 or wp in c1t2) else 0
                cm1_only += 1 if (wp in c1t2 and not in2) else 0

    print(f"\n{'='*64}\nMEET STATS — {track} {dates[0] if dates else ''}..{dates[-1] if dates else ''}\n{'='*64}")
    print(f"{'model':<6}{'rank-1 win%':>12}{'top-3 cap%':>12}{'mean w-rank':>13}"
          f"{'r1 ROI':>9}{'ex-out':>9}")
    for m in ("R5", "CM", "CM1"):
        a = agg[m]; n = a["n"] or 1
        roi = (a["ret"] - a["staked"]) / a["staked"] if a["staked"] else 0
        exr = ((a["ret"] - (max(a["pays"]) if a["pays"] else 0)) - a["staked"]) / a["staked"] \
            if a["staked"] else 0
        print(f"{m:<6}{100*a['r1w']/n:>11.1f}%{100*a['cap']/n:>11.1f}%{a['wrank']/n:>13.2f}"
              f"{roi:>8.1%}{exr:>8.1%}")
    if union_n:
        print(f"\nContender-set capture ({union_n} races):")
        print(f"  R5(1-3) ∪ CM(1-2)      : {cap_r5cm}/{union_n} = {100*cap_r5cm/union_n:.1f}%")
        print(f"  + CM1(1-2) → 3-model   : {cap_all}/{union_n} = {100*cap_all/union_n:.1f}%  "
              f"(+{100*(cap_all-cap_r5cm)/union_n:.1f}pp, {cm1_only} CM1-only)")
    r5.close(); cm.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="R5|CM|CM1 compare report")
    ap.add_argument("track")
    ap.add_argument("--from", dest="date_from")
    a = ap.parse_args()
    report(a.track, a.date_from)
