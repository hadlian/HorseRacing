#!/usr/bin/env python3
"""
r5_ab.py — Post-scratch A/B harness (results-phase analysis).

For a SETTLED card, re-score R5 on the ACTUAL post-scratch field — a TRUE
re-score: finalize_field() recomputes pace scenario, pace-fit, value-vs-ML and
the tight-cluster deduction on the runners only (removing scratches BEFORE
scoring, not after). Then rebuild exotic tickets with the same production logic
(build_contender_set / select_structure) and settle against the same chart.
Finally compare to the logged entries-based tickets (pre-scratch scoring +
settle-time refunds).

ISOLATION / SAFETY:
  • Writes ONLY to the ab_tickets table. Never touches picks / exotic_tickets /
    races / race_finish_order. It does NOT go through run_r5's write path, so it
    cannot clobber a settled card.
  • Scratches are derived from the chart: a DRF entry that is not a finisher in
    race_finish_order is treated as scratched (legitimately known before post).
  • Value uses DRF morning-line odds (already in the file) — no tote look-ahead.

CAVEAT: R5 is truly re-scored; CM legs are re-SELECTED from survivors (CM is not
re-scored — out of scope). Flagged in the report.

Usage:
  python3 Claude/r5_ab.py --track SAR --date 20260709 --drf "files 2/SAR0709.DRF"
  python3 Claude/r5_ab.py --backfill-july-sar
"""
import argparse
import json
import sqlite3
from pathlib import Path
import importlib.util as _ilu
from collections import defaultdict

CLAUDE_DIR = Path(__file__).resolve().parent
ROOT       = CLAUDE_DIR.parent
R5_DB      = ROOT / "Results" / "r5_results.db"
CM_DB      = ROOT / "comparemodels" / "comparemodels_results.db"


def _load(name):
    spec = _ilu.spec_from_file_location(name, CLAUDE_DIR / f"{name}.py")
    mod  = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_parser  = _load("r5_parser_v2")
_exotics = _load("r5_exotics")
parse_drf           = _parser.parse_drf
finalize_field      = _parser.finalize_field
build_contender_set = _exotics.build_contender_set
select_structure    = _exotics.select_structure
expand_ticket       = _exotics.expand_ticket
base_pgm            = _exotics.base_pgm

AB_SCHEMA = """
CREATE TABLE IF NOT EXISTS ab_tickets (
  id            INTEGER PRIMARY KEY,
  race_id       INTEGER REFERENCES races(id),
  variant       TEXT DEFAULT 'post_scratch',
  ticket_type   TEXT NOT NULL,
  combination   TEXT NOT NULL,
  cost          REAL NOT NULL,
  denomination  REAL NOT NULL,
  actual_payoff REAL,
  profit        REAL,
  race_shape    TEXT,
  contender_set TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(race_id, variant, ticket_type, combination)
);
"""


def _build_paymap(conn, race_id):
    paymap = {}
    for p in conn.execute(
        "SELECT pool, combination, payoff, denomination FROM race_payoffs "
        "WHERE race_id=? AND is_refund=0 AND combination != 'CARRYOVER'",
        (race_id,)):
        key = (p["pool"], tuple(base_pgm(x) for x in p["combination"].split("-")))
        paymap.setdefault(key, []).append((p["payoff"], p["denomination"]))
    return paymap


def _settle(ticket, paymap, scratched):
    """Mirror r5_exotics.settle_race math for a single ticket dict."""
    pool   = "EX" if ticket["ticket_type"].startswith("EX") else "TRI"
    combos = [tuple(base_pgm(x) for x in c) for c in expand_ticket(ticket)]
    if ticket["combination"].startswith("KEY:"):
        key_horse = base_pgm(ticket["combination"][4:].split("/")[0])
        if key_horse in scratched:
            return 0.0, 0.0                      # full refund → net 0
    live   = [c for c in combos if not any(h in scratched for h in c)]
    refund = round((len(combos) - len(live)) * ticket["denomination"], 2)
    collected = 0.0
    for c in live:
        for quoted, pdenom in paymap.get((pool, c), []):
            collected += quoted * (ticket["denomination"] / pdenom)
    profit = round(collected + refund - ticket["cost"], 2)
    return round(collected, 2), profit


def process_card(track, date, drf_path):
    track = track.upper()
    conn = sqlite3.connect(R5_DB); conn.row_factory = sqlite3.Row
    conn.executescript(AB_SCHEMA)
    cm = sqlite3.connect(CM_DB); cm.row_factory = sqlite3.Row

    races = {r["race_num"]: r for r in conn.execute(
        "SELECT * FROM races WHERE track=? AND date=?", (track, date))}
    if not races:
        print(f"  ⚠️  No races in DB for {track} {date}"); return None

    field_by_race = defaultdict(list)
    for h in parse_drf(str(drf_path)):
        field_by_race[str(h["race"]).strip()].append(h)

    results = []
    for rnum, race in sorted(races.items(), key=lambda kv: int(kv[0])):
        rid   = race["id"]
        field = field_by_race.get(str(rnum), [])
        finishers = {base_pgm(r["horse_pgm"]) for r in conn.execute(
            "SELECT horse_pgm FROM race_finish_order "
            "WHERE race_id=? AND finish_position IS NOT NULL", (rid,))}
        if not field or not finishers:
            continue  # unparsed or unsettled race — skip

        survivors = [h for h in field if base_pgm(h["pgm"]) in finishers]
        n_scr     = len(field) - len(survivors)
        if len(survivors) < 3:
            results.append({"r": rnum, "note": "PASS(<3 runners)",
                            "cost": 0.0, "profit": 0.0, "n_scr": n_scr}); continue

        # ── TRUE RE-SCORE on survivors only ──────────────────────────────────
        survivors = finalize_field(survivors)
        survivors.sort(key=lambda h: h["comp"], reverse=True)
        for i, h in enumerate(survivors):
            h["model_rank"] = i + 1

        # CM legs: re-select surviving CM horses, re-rank 1..n
        cm_all = [dict(r) for r in cm.execute(
            "SELECT horse_pgm, cm_rank FROM picks WHERE track=? AND race_date=? "
            "AND race=?", (track, date, int(rnum)))]
        cm_surv = sorted((c for c in cm_all if base_pgm(c["horse_pgm"]) in finishers),
                         key=lambda c: c["cm_rank"])
        for i, c in enumerate(cm_surv):
            c["cm_rank"] = i + 1

        ppu_row = cm.execute(
            "SELECT horse_pgm FROM category_picks WHERE track=? AND race_date=? "
            "AND race=? AND category='Prime Power' AND rank_in_cat=1 AND underlined=1",
            (track, date, int(rnum))).fetchone()
        ppu = ppu_row["horse_pgm"] if ppu_row and base_pgm(
            ppu_row["horse_pgm"]) in finishers else None

        cset = build_contender_set(survivors, cm_surv, len(survivors), ppu)
        if cset is None:
            results.append({"r": rnum, "note": f"PASS(field {len(survivors)})",
                            "cost": 0.0, "profit": 0.0, "n_scr": n_scr}); continue

        s13  = round(survivors[0]["comp"] - survivors[2]["comp"], 2)
        s12  = round(survivors[0]["comp"] - survivors[1]["comp"], 2)
        r3ml = survivors[2]["ml_odds"]
        tickets = select_structure(cset, s13, s12, r3ml, len(survivors))
        if not tickets:
            results.append({"r": rnum, "note": "PASS(no tickets)",
                            "cost": 0.0, "profit": 0.0, "n_scr": n_scr}); continue

        conn.execute("DELETE FROM ab_tickets WHERE race_id=? AND variant='post_scratch'",
                     (rid,))
        paymap = _build_paymap(conn, rid)
        tcost = tprofit = 0.0
        descs = []
        for t in tickets:
            collected, profit = _settle(t, paymap, set())  # survivors: no scratched legs
            conn.execute(
                "INSERT OR REPLACE INTO ab_tickets (race_id, variant, ticket_type, "
                "combination, cost, denomination, actual_payoff, profit, race_shape, "
                "contender_set) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rid, "post_scratch", t["ticket_type"], t["combination"], t["cost"],
                 t["denomination"], collected, profit, t["race_shape"],
                 json.dumps(cset["all"])))
            tcost += t["cost"]; tprofit += profit
            descs.append(f"{t['ticket_type']} {t['combination']}")
        results.append({"r": rnum, "note": f"[{tickets[0]['race_shape']}] "
                        f"{cset['all']} → {'; '.join(descs)}",
                        "cost": round(tcost, 2), "profit": round(tprofit, 2),
                        "n_scr": n_scr})
    conn.commit()

    # ── comparison vs entries (exotic_tickets) ───────────────────────────────
    print(f"\n══════ {track} {date} — post-scratch A/B ══════")
    print(f"  {'R':<3} {'scr':<4} {'ENTRIES P/L':>11} {'POST-SCR P/L':>13}   post-scratch structure")
    ent_tot = ps_tot = ent_stake = ps_stake = 0.0
    for row in results:
        ent = conn.execute(
            "SELECT COALESCE(SUM(cost),0) c, COALESCE(SUM(profit),0) p "
            "FROM exotic_tickets e JOIN races r ON e.race_id=r.id "
            "WHERE r.track=? AND r.date=? AND r.race_num=? AND e.cost>0",
            (track, date, row["r"])).fetchone()
        ent_pl = round(ent["p"], 2)
        ent_tot += ent_pl; ps_tot += row["profit"]
        ent_stake += ent["c"]; ps_stake += row["cost"]
        flag = "" if row["cost"] > 0 else " (no bet)"
        print(f"  {row['r']:<3} {row['n_scr']:<4} {ent_pl:>+11.2f} "
              f"{row['profit']:>+13.2f}   {row['note']}{flag}")
    print(f"  {'─'*70}")
    er = f"{100*ent_tot/ent_stake:+.1f}%" if ent_stake else "n/a"
    pr = f"{100*ps_tot/ps_stake:+.1f}%" if ps_stake else "n/a"
    print(f"  ENTRIES:      net {ent_tot:+.2f} on ${ent_stake:.0f}  → ROI {er}")
    print(f"  POST-SCRATCH: net {ps_tot:+.2f} on ${ps_stake:.0f}  → ROI {pr}")
    conn.close(); cm.close()
    return {"track": track, "date": date, "ent_net": round(ent_tot, 2),
            "ent_stake": round(ent_stake, 2), "ps_net": round(ps_tot, 2),
            "ps_stake": round(ps_stake, 2)}


def resolve_drf(track, date):
    """Find the DRF for a card: files 2/<TRACK><MMDD>.DRF (YYYYMMDD → MMDD)."""
    mmdd = date[4:8]
    for cand in (ROOT / "files 2" / f"{track.upper()}{mmdd}.DRF",
                 ROOT / "files" / f"{track.upper()}{mmdd}.DRF"):
        if cand.exists():
            return cand
    return None


def run_for_card(track, date, drf=None):
    """Pipeline entry point: resolve DRF if needed, run the A/B comparison.
    Returns the summary dict, or None if the DRF can't be found."""
    drf_path = Path(drf) if drf else resolve_drf(track, date)
    if drf_path and not drf_path.is_absolute():
        drf_path = ROOT / drf_path
    if not drf_path or not drf_path.exists():
        print(f"  [A/B] DRF not found for {track} {date} — skipping A/B comparison")
        return None
    return process_card(track, date, drf_path)


JULY_SAR = [
    ("SAR", "20260703", "files 2/SAR0703.DRF"),
    ("SAR", "20260704", "files 2/SAR0704.DRF"),
    ("SAR", "20260705", "files 2/SAR0705.DRF"),
    ("SAR", "20260709", "files 2/SAR0709.DRF"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track"); ap.add_argument("--date"); ap.add_argument("--drf")
    ap.add_argument("--backfill-july-sar", action="store_true")
    a = ap.parse_args()

    if not a.backfill_july_sar and not (a.track and a.date):
        ap.error("need --track and --date (or --backfill-july-sar)")

    cards = JULY_SAR if a.backfill_july_sar else [(a.track, a.date, a.drf)]
    agg = []
    for track, date, drf in cards:
        r = run_for_card(track, date, drf)
        if r: agg.append(r)

    if len(agg) > 1:
        en = sum(r["ent_net"] for r in agg); es = sum(r["ent_stake"] for r in agg)
        pn = sum(r["ps_net"] for r in agg);  ps = sum(r["ps_stake"] for r in agg)
        print(f"\n══════ AGGREGATE ({len(agg)} cards) ══════")
        print(f"  ENTRIES:      net {en:+.2f} on ${es:.0f}  → ROI "
              f"{100*en/es:+.1f}%" if es else "  ENTRIES: n/a")
        print(f"  POST-SCRATCH: net {pn:+.2f} on ${ps:.0f}  → ROI "
              f"{100*pn/ps:+.1f}%" if ps else "  POST-SCRATCH: n/a")
        print("\n  Note: R5 truly re-scored on survivors; CM legs re-selected "
              "(not re-scored). Value uses DRF ML odds (no tote look-ahead).")


if __name__ == "__main__":
    main()
