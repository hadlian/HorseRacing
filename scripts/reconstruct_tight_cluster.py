#!/usr/bin/env python3
"""
reconstruct_tight_cluster.py — Session 2, Task 2.

The v3.7 tight-cluster deduction (-0.40 to the pre-deduction top horse when
top-3 spread <= 0.5) was never persisted. This script reconstructs it exactly
from the logged component vectors and populates picks.pre_tight_comp /
picks.tight_cluster_severe, then reports corrected ROI in fired vs unfired races.

Comp construction in r5_parser_v2.py finalize_field:
    comp = round(weighted_sum, 2) + equipment_adj + scout_adj [- 0.40 if fired]
scout_adj is logged; equipment_adj (v3.8: +0.20 lasix, +0.10 blkOn, -0.05 blkOff)
is NOT logged. Delta classification separates them: equipment deltas are small
(-0.05 .. +0.30), the deduction is exactly -0.40, so a fired pick's delta lies
in {-0.45, -0.40, -0.30, -0.25, -0.20} (deduction +- equipment) — disjoint
from the equipment-only set.

Version coverage (no version column exists; empirically verified):
    dates <= 20260516 — pre-v3.5 scoring, pp_n/best_dist_n NULL: current
        formula does not apply; v3.7 did not exist; no deduction possible.
        pre_tight_comp = comp, tight_cluster_severe = 0.
    dates >= 20260521 — current 9-component formula.
    deduction only possible from v3.7 (shipped 2026-05-28).

Hard gate: every pick on the current formula must classify as clean /
equipment / fired. Any unexplained delta aborts the write.

Circularity handled: the spread <= 0.5 test runs on RECONSTRUCTED pre-deduction
comps (stored comps are post-deduction).

Usage: python3 scripts/reconstruct_tight_cluster.py [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Claude"))
from r5_paths import R5_DB_PATH as DB_PATH  # noqa: E402

WEIGHTS = {"fci_n": 0.22, "class_n": 0.20, "tj_n": 0.15, "best_dist_n": 0.08,
           "pp_n": 0.05, "form_n": 0.10, "ped_n": 0.07, "bias_n": 0.08,
           "val_n": 0.05}

EPS         = 0.015
EQUIP_SET   = (0.10, 0.20, 0.30, 0.15, -0.05)            # v3.8 combos
FIRED_SET   = tuple(-0.40 + e for e in (0.0,) + EQUIP_SET)  # -0.40 ± equip
PRE_V35_END = "20260516"   # last date scored on the old formula (NULL pp_n)
V37_START   = "20260528"   # tight-cluster deduction shipped


def in_set(delta, values):
    return any(abs(delta - v) <= EPS for v in values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = {r[1] for r in conn.execute("PRAGMA table_info(picks)")}
    if "pre_tight_comp" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN pre_tight_comp REAL")
    if "tight_cluster_severe" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN tight_cluster_severe INTEGER DEFAULT 0")

    # version coverage report
    n_old = conn.execute(
        "SELECT COUNT(*) FROM picks p JOIN races r ON r.id=p.race_id WHERE r.date<=?",
        (PRE_V35_END,)).fetchone()[0]
    n_new = conn.execute(
        "SELECT COUNT(*) FROM picks p JOIN races r ON r.id=p.race_id WHERE r.date>?",
        (PRE_V35_END,)).fetchone()[0]
    print(f"Version coverage: {n_old} picks pre-v3.5 (<= {PRE_V35_END}, "
          f"no deduction possible), {n_new} picks current formula")

    races = conn.execute(
        "SELECT id, track, date, race_num FROM races ORDER BY date, CAST(race_num AS INT)"
    ).fetchall()

    counts = {"clean": 0, "equip": 0, "fired": 0, "unexplained": 0}
    unexplained, fired_races, updates = [], [], []

    for race in races:
        picks = conn.execute(
            "SELECT * FROM picks WHERE race_id=? ORDER BY model_rank", (race["id"],)
        ).fetchall()
        if not picks:
            continue

        if race["date"] <= PRE_V35_END:
            for p in picks:
                updates.append((p["comp"], 0, p["id"]))
            continue

        deltas = {}
        for p in picks:
            if any(p[c] is None for c in WEIGHTS):
                deltas[p["id"]] = None
                continue
            base = round(sum(p[c] * w for c, w in WEIGHTS.items()), 2)
            base += p["scout_adj"] or 0.0
            deltas[p["id"]] = round(p["comp"] - base, 3)

        fired_pick = None
        for p in picks:
            d = deltas[p["id"]]
            if d is None:
                counts["unexplained"] += 1
                unexplained.append((race, p, "NULL component"))
            elif abs(d) <= EPS:
                counts["clean"] += 1
            elif in_set(d, EQUIP_SET):
                counts["equip"] += 1
            elif in_set(d, FIRED_SET) and race["date"] >= V37_START:
                if fired_pick is not None:
                    counts["unexplained"] += 1
                    unexplained.append((race, p, f"second fired-delta {d:+.2f}"))
                else:
                    fired_pick = p
                    counts["fired"] += 1
            else:
                counts["unexplained"] += 1
                unexplained.append((race, p, f"delta {d:+.2f}"))

        # structural verification + writes for this race
        if fired_pick is not None:
            pre = {p["id"]: (p["comp"] + 0.40 if p["id"] == fired_pick["id"]
                             else p["comp"]) for p in picks}
            top3 = sorted(pre.values(), reverse=True)[:3]
            spread = round(top3[0] - top3[2], 2) if len(top3) >= 3 else 99
            is_top = pre[fired_pick["id"]] == top3[0]
            if not is_top or spread > 0.5 + EPS:
                counts["unexplained"] += 1
                counts["fired"] -= 1
                unexplained.append((race, fired_pick,
                                    f"structural fail: top={is_top} spread={spread}"))
                fired_pick = None
            else:
                fired_races.append((race, fired_pick, spread))

        for p in picks:
            if fired_pick is not None and p["id"] == fired_pick["id"]:
                updates.append((round(p["comp"] + 0.40, 2), 1, p["id"]))
            else:
                updates.append((p["comp"], 0, p["id"]))

    print(f"\nDelta classification (current-formula picks):")
    print(f"  clean (|d|<=0.015):        {counts['clean']}")
    print(f"  equipment adj:             {counts['equip']}")
    print(f"  tight-cluster fired:       {counts['fired']}")
    print(f"  UNEXPLAINED:               {counts['unexplained']}")
    for race, p, why in unexplained[:20]:
        print(f"    {race['track']} {race['date']} R{race['race_num']} "
              f"#{p['pgm']} {p['horse_name']}: {why}")

    if counts["unexplained"]:
        print("\n❌ GATE FAILED — unexplained deltas; NOT writing. "
              "Weight-version mapping needs investigation.")
        conn.close()
        return 1

    print(f"\n✅ Gate passed: every pick classified. {len(fired_races)} races fired.")

    if not args.dry_run:
        conn.executemany(
            "UPDATE picks SET pre_tight_comp=?, tight_cluster_severe=? WHERE id=?",
            updates)
        conn.commit()
        print(f"   {len(updates)} picks updated (pre_tight_comp, tight_cluster_severe).")

    # ── ROI: fired vs unfired (corrected convention, $2 flat) ────────────────
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

    fired_ids = {race["id"] for race, _, _ in fired_races}
    print(f"\n── Exact re-validation (deduction fired in {len(fired_ids)} races) ──")

    if fired_ids:
        ph = ",".join("?" * len(fired_ids))
        # pre-deduction top = the demoted horse; post-deduction top = stored rank 1
        demoted = [conn.execute("SELECT * FROM picks WHERE id=?", (fp["id"],)).fetchone()
                   for _, fp, _ in fired_races]
        post_top = conn.execute(
            f"SELECT * FROM picks WHERE race_id IN ({ph}) AND model_rank=1",
            tuple(fired_ids)).fetchall()
        for label, rows in (("bet PRE-deduction top (demoted horse)", demoted),
                            ("bet POST-deduction top (stored rank-1)", post_top)):
            b, w, pf = roi(rows)
            if b:
                print(f"  {label}: {b} bets, {w} wins ({w/b*100:.1f}%), "
                      f"ROI {pf/(2*b)*100:+.1f}%")

    unfired = conn.execute(
        "SELECT p.* FROM picks p JOIN races r ON r.id=p.race_id "
        "WHERE p.model_rank=1 AND r.date > ? AND r.id NOT IN "
        f"({','.join('?'*len(fired_ids)) if fired_ids else 'NULL'})",
        (PRE_V35_END, *fired_ids)).fetchall()
    b, w, pf = roi(unfired)
    if b:
        print(f"  unfired races, rank-1 baseline: {b} bets, {w} wins "
              f"({w/b*100:.1f}%), ROI {pf/(2*b)*100:+.1f}%")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
