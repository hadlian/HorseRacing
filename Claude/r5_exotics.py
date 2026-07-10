#!/usr/bin/env python3
"""
r5_exotics.py — Exotics module v1 (Session 2, Task 7 / Decision 2).

Contender set:   R5 ranks 1–3 ∪ CM ranks 1–2 (validated +7.5pts winner
                 capture), PP-underline horse underneath-only.
Structure menu:  spread-driven (TIGHT / STANDOUT / DEFAULT), superfecta
                 categorically passed until payoff-validated.
Cap:             $12/race (Harry ruling 2). Trim drop order: TRI legs first,
                 then the rank-3 EX key. The primary EX structure is never
                 dropped.
Tickets:         is_paper=1 ALWAYS by default. Live only via explicit
                 --live flag per session (Harry controls). Never inferred.
Settlement:      combos enumerated by the same code that priced the ticket;
                 denomination scaling is explicit:
                     collected = quoted × (ticket_denom / payoff_denom)
                 Coupled entries matched on base number. Dead heats sum all
                 matched rows. Scratched box leg → combos refunded at cost;
                 scratched key → full refund.
Self-test:       hand-computed gate vs REAL ingested CDX 0529 R1 payoffs.
                 Settlement refuses to run on the live DB until it passes.

Usage:
    python3 Claude/r5_exotics.py --selftest
    python3 Claude/r5_exotics.py --generate --track SAR --date 20260605 [--race 5] [--live]
    python3 Claude/r5_exotics.py --settle   --track SAR --date 20260605 [--race 5]
    python3 Claude/r5_exotics.py --report
"""

import argparse
import importlib.util
import json
import re
import sqlite3
import sys
from itertools import permutations
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
R5_DB   = ROOT / "Results" / "r5_results.db"
CM_DB   = ROOT / "comparemodels" / "comparemodels_results.db"

TICKET_COST_CAP = 12.0   # Harry ruling 2
EX_DENOM        = 1.0
TRI_DENOM       = 0.5


def base_pgm(pgm):
    """Coupled entries bet/pay on the base number: '1A' -> '1'."""
    return re.sub(r"[A-Z]$", "", str(pgm).strip())


# ── CONTENDER SET ─────────────────────────────────────────────────────────────

def build_contender_set(r5_horses, cm_horses, field_size_post,
                        pp_underline_pgm=None):
    """
    r5_horses: rank-ordered post-scratch dicts with pgm, model_rank, comp,
               ml_odds, class_n (class_n == 0.0 is the documented debut marker).
    cm_horses: dicts with horse_pgm, cm_rank.
    Returns None (pass race) or dict with top/underneath/all/flag.
    """
    if field_size_post is not None and field_size_post <= 5:
        return None  # pass: exotic prices collapse in short fields

    r5_top3 = [h for h in r5_horses if h["model_rank"] <= 3]
    if len(r5_top3) < 3:
        return None

    seen = {base_pgm(h["pgm"]) for h in r5_top3}
    cm_legs = []
    for ch in sorted(cm_horses, key=lambda c: c["cm_rank"]):
        if ch["cm_rank"] <= 2 and base_pgm(ch["horse_pgm"]) not in seen:
            cm_legs.append(base_pgm(ch["horse_pgm"]))
            seen.add(base_pgm(ch["horse_pgm"]))

    # trim CM-only legs first (rank-2 before rank-1 — i.e. pop the weakest)
    while len(r5_top3) + len(cm_legs) > 5 and cm_legs:
        cm_legs.pop()

    debuts = sum(1 for h in r5_top3 if (h.get("class_n") or 1) == 0.0)
    flag   = "EX_ONLY" if debuts >= 2 else None

    top        = [base_pgm(h["pgm"]) for h in r5_top3]
    underneath = list(cm_legs)
    pp = base_pgm(pp_underline_pgm) if pp_underline_pgm else None
    if pp and pp not in top and pp not in underneath:
        underneath.append(pp)   # underneath-only, never on top

    return {"top": top, "underneath": underneath,
            "all": top + underneath, "flag": flag,
            "pp_underline": pp}


# ── TICKETS ───────────────────────────────────────────────────────────────────

def expand_ticket(ticket):
    """Enumerate ordered combos. Single source of truth for cost AND
    settlement."""
    t = ticket["combination"]
    if t.startswith("BOX:"):
        horses = t[4:].split(",")
        k = 2 if ticket["ticket_type"].startswith("EX") else 3
        return list(permutations(horses, k))
    if t.startswith("KEY:"):
        legs = [leg.split(",") for leg in t[4:].split("/")]
        combos = []
        if len(legs) == 2:        # EX key: key / others
            for b in legs[1]:
                if b != legs[0][0]:
                    combos.append((legs[0][0], b))
        else:                     # TRI key: key / leg2 / leg3
            for b in legs[1]:
                for c in legs[2]:
                    if len({legs[0][0], b, c}) == 3:
                        combos.append((legs[0][0], b, c))
        return combos
    raise ValueError(f"unknown combination format: {t}")


def make_ticket(ttype, combination, denom, shape, cset):
    t = {"ticket_type": ttype, "combination": combination,
         "denomination": denom, "race_shape": shape,
         "contender_set": json.dumps(cset["all"])}
    t["cost"] = round(len(expand_ticket(t)) * denom, 2)
    return t


def select_structure(cset, spread_r1_r3, spread_r1_r2, rank3_ml_odds,
                     field_size_post):
    """Decision 2B menu + $12 cap with trim priority."""
    if cset is None:
        return []
    r1, r2, r3 = cset["top"]
    others     = [p for p in cset["all"] if p != r1]
    under_all  = sorted(set(others))           # set legs + PP underline

    tickets = []
    if spread_r1_r3 is not None and spread_r1_r3 <= 0.5:
        shape = "TIGHT"
        tickets.append(make_ticket("EX_BOX", f"BOX:{r1},{r2},{r3}",
                                   EX_DENOM, shape, cset))
        if cset["flag"] != "EX_ONLY":
            tickets.append(make_ticket("TRI_BOX", f"BOX:{r1},{r2},{r3}",
                                       TRI_DENOM, shape, cset))
        if rank3_ml_odds is not None and rank3_ml_odds >= 6.0:
            tickets.append(make_ticket("EX_KEY", f"KEY:{r3}/{r1},{r2}",
                                       EX_DENOM, shape, cset))
    elif spread_r1_r2 is not None and spread_r1_r2 >= 1.0:
        shape = "STANDOUT"
        tickets.append(make_ticket("EX_KEY", f"KEY:{r1}/{','.join(under_all)}",
                                   EX_DENOM, shape, cset))
        if cset["flag"] != "EX_ONLY":
            legs = ",".join(under_all)
            tickets.append(make_ticket("TRI_KEY", f"KEY:{r1}/{legs}/{legs}",
                                       TRI_DENOM, shape, cset))
    else:
        shape = "DEFAULT"
        tickets.append(make_ticket("EX_BOX", f"BOX:{r1},{r2},{r3}",
                                   EX_DENOM, shape, cset))

    # ── $12 cap, trim priority: shrink/drop TRI first, then r3 EX key. ──────
    def total(ts):
        return round(sum(t["cost"] for t in ts), 2)

    while total(tickets) > TICKET_COST_CAP:
        tri = next((t for t in tickets if t["ticket_type"].startswith("TRI")), None)
        if tri and tri["ticket_type"] == "TRI_KEY":
            # shrink third leg before dropping the TRI entirely
            legs = tri["combination"][4:].split("/")
            third = legs[2].split(",")
            if len(third) > 2:
                third.pop()       # drop the last (weakest) underneath leg
                legs[2] = ",".join(third)
                tri["combination"] = "KEY:" + "/".join(legs)
                tri["cost"] = round(len(expand_ticket(tri)) * tri["denomination"], 2)
                continue
            tickets.remove(tri)
            continue
        if tri:
            tickets.remove(tri)
            continue
        r3key = next((t for t in tickets if t["ticket_type"] == "EX_KEY"
                      and t["combination"].startswith(f"KEY:{r3}/")), None)
        if r3key:
            tickets.remove(r3key)
            continue
        break  # only the primary EX remains — never dropped

    return tickets


# ── LOGGING ───────────────────────────────────────────────────────────────────

def log_tickets(conn, race_id, tickets, live_mode=False):
    """is_paper=1 ALWAYS unless live_mode explicitly True (per-session Harry
    flag — never inferred from config or environment). Idempotent for paper:
    re-generation replaces unsettled paper tickets."""
    conn.execute("DELETE FROM exotic_tickets WHERE race_id=? AND is_paper=1 "
                 "AND actual_payoff IS NULL", (race_id,))
    for t in tickets:
        conn.execute("""
            INSERT INTO exotic_tickets
            (race_id, ticket_type, combination, cost, denomination,
             is_paper, race_shape, contender_set)
            VALUES (?,?,?,?,?,?,?,?)
        """, (race_id, t["ticket_type"], t["combination"], t["cost"],
              t["denomination"], 0 if live_mode else 1,
              t["race_shape"], t["contender_set"]))


# ── SETTLEMENT ────────────────────────────────────────────────────────────────

def settle_race(conn, race_id):
    """Settle all unsettled tickets for one race. Returns count settled."""
    payoffs = conn.execute(
        "SELECT pool, combination, payoff, denomination FROM race_payoffs "
        "WHERE race_id=? AND is_refund=0 AND combination != 'CARRYOVER'",
        (race_id,)).fetchall()
    if not payoffs:
        return 0
    paymap = {}
    for p in payoffs:
        key = (p["pool"], tuple(base_pgm(x) for x in p["combination"].split("-")))
        paymap.setdefault(key, []).append((p["payoff"], p["denomination"]))

    scratched = {base_pgm(r["horse_pgm"]) for r in conn.execute(
        "SELECT horse_pgm FROM race_finish_order WHERE race_id=? "
        "AND is_late_scratch=1", (race_id,))}

    n = 0
    for t in conn.execute("SELECT * FROM exotic_tickets WHERE race_id=? "
                          "AND actual_payoff IS NULL "
                          "AND ticket_type NOT LIKE '%NOTE%'",
                          (race_id,)).fetchall():
        ticket = dict(t)
        pool   = "EX" if t["ticket_type"].startswith("EX") else "TRI"
        combos = [tuple(base_pgm(x) for x in c) for c in expand_ticket(ticket)]

        # scratched KEY horse → full refund
        if t["combination"].startswith("KEY:"):
            key_horse = base_pgm(t["combination"][4:].split("/")[0])
            if key_horse in scratched:
                conn.execute("UPDATE exotic_tickets SET actual_payoff=0, "
                             "profit=0 WHERE id=?", (t["id"],))
                n += 1
                continue

        live_combos = [c for c in combos
                       if not any(h in scratched for h in c)]
        refund = round((len(combos) - len(live_combos)) * t["denomination"], 2)

        collected = 0.0
        for c in live_combos:
            for quoted, pdenom in paymap.get((pool, c), []):
                collected += quoted * (t["denomination"] / pdenom)

        profit = round(collected + refund - t["cost"], 2)
        conn.execute("UPDATE exotic_tickets SET actual_payoff=?, profit=? "
                     "WHERE id=?", (round(collected, 2), profit, t["id"]))
        n += 1
    return n


# ── SELF-TEST (hard gate before settlement on live data) ─────────────────────

def selftest():
    """Hand-computed expectations vs REAL ingested CDX 0529 R1 payoffs:
    $2 EXACTA (3-5) paid $189.86 ; $0.50 TRIFECTA (3-5-1) paid $253.42.

    Ticket A: $1 EX box {3,5,1} — 6 combos, cost $6.
        collected = 189.86 × (1.0/2.0) = 94.93 ; profit = 88.93
    Ticket B: $0.50 TRI key 3/5,1/5,1 — 2 combos, cost $1.
        collected = 253.42 × (0.5/0.5) = 253.42 ; profit = 252.42
    """
    conn = sqlite3.connect(R5_DB)
    conn.row_factory = sqlite3.Row
    rid = conn.execute("SELECT id FROM races WHERE track='CDX' AND "
                       "date='20260529' AND race_num='1'").fetchone()
    if not rid:
        print("selftest: CDX 20260529 R1 not in DB"); return False
    rid = rid[0]

    conn.execute("DELETE FROM exotic_tickets WHERE race_id=? AND "
                 "race_shape='SELFTEST'", (rid,))
    for ttype, combo, denom in (("EX_BOX", "BOX:3,5,1", 1.0),
                                ("TRI_KEY", "KEY:3/5,1/5,1", 0.5)):
        t = {"ticket_type": ttype, "combination": combo,
             "denomination": denom, "race_shape": "SELFTEST",
             "contender_set": "[]"}
        t["cost"] = round(len(expand_ticket(t)) * denom, 2)
        conn.execute("""INSERT INTO exotic_tickets (race_id, ticket_type,
            combination, cost, denomination, is_paper, race_shape,
            contender_set) VALUES (?,?,?,?,?,1,'SELFTEST','[]')""",
            (rid, t["ticket_type"], t["combination"], t["cost"],
             t["denomination"]))
    settle_race(conn, rid)

    rows = conn.execute("SELECT ticket_type, cost, actual_payoff, profit "
                        "FROM exotic_tickets WHERE race_id=? AND "
                        "race_shape='SELFTEST'", (rid,)).fetchall()
    expected = {"EX_BOX": (6.0, 94.93, 88.93), "TRI_KEY": (1.0, 253.42, 252.42)}
    ok = True
    for r in rows:
        exp = expected[r["ticket_type"]]
        got = (r["cost"], r["actual_payoff"], r["profit"])
        match = all(abs(a - b) < 0.005 for a, b in zip(exp, got))
        print(f"  {r['ticket_type']}: cost/collected/profit = {got} "
              f"{'✅' if match else f'❌ expected {exp}'}")
        ok &= match
    conn.execute("DELETE FROM exotic_tickets WHERE race_id=? AND "
                 "race_shape='SELFTEST'", (rid,))
    conn.commit()
    conn.close()
    print(f"  SELFTEST {'PASSED' if ok else 'FAILED'}")
    return ok


def settlement_gate_ok():
    """Settlement must not run on live data until the self-test passes."""
    return selftest()


# ── DB-DRIVEN GENERATION (dry run / per-card use) ────────────────────────────

def generate_card(track, date, race_num=None, live_mode=False):
    conn = sqlite3.connect(R5_DB)
    conn.row_factory = sqlite3.Row
    cm = sqlite3.connect(CM_DB)
    cm.row_factory = sqlite3.Row

    races = conn.execute(
        "SELECT * FROM races WHERE track=? AND date=? AND is_backtest=0" +
        (" AND race_num=?" if race_num else ""),
        (track.upper(), date) + ((str(race_num),) if race_num else ())
    ).fetchall()

    made = 0
    for race in races:
        picks = [dict(r) for r in conn.execute(
            "SELECT * FROM picks WHERE race_id=? AND "
            "(finish_pos IS NULL OR finish_pos != -1) ORDER BY model_rank",
            (race["id"],))]
        if len(picks) < 3:
            continue
        cm_rows = [dict(r) for r in cm.execute(
            "SELECT horse_pgm, cm_rank FROM picks WHERE track=? AND "
            "race_date=? AND race=?",
            (race["track"], race["date"], int(race["race_num"])))]
        ppu = cm.execute(
            "SELECT horse_pgm FROM category_picks WHERE track=? AND "
            "race_date=? AND race=? AND category='Prime Power' AND "
            "rank_in_cat=1 AND underlined=1",
            (race["track"], race["date"], int(race["race_num"]))).fetchone()

        cset = build_contender_set(
            picks, cm_rows, race["field_size_post"] or len(picks),
            ppu["horse_pgm"] if ppu else None)
        if cset is None:
            print(f"  R{race['race_num']}: PASS "
                  f"(field {race['field_size_post'] or len(picks)})")
            continue

        ranked = sorted(picks, key=lambda p: p["model_rank"])
        s13 = round(ranked[0]["comp"] - ranked[2]["comp"], 2)
        s12 = round(ranked[0]["comp"] - ranked[1]["comp"], 2)
        r3ml = ranked[2]["ml_odds"]

        tickets = select_structure(cset, s13, s12, r3ml,
                                   race["field_size_post"] or len(picks))
        if not tickets:
            continue
        log_tickets(conn, race["id"], tickets, live_mode)
        cost = sum(t["cost"] for t in tickets)
        desc = "; ".join(f"{t['ticket_type']} {t['combination']} "
                         f"${t['cost']:.2f}" for t in tickets)
        mode = "LIVE" if live_mode else "paper"
        print(f"  R{race['race_num']} [{tickets[0]['race_shape']}] "
              f"set={cset['all']} → {desc}  (total ${cost:.2f}, {mode})")

        # ── Session 3A display notes (no structure changes) ─────────────────
        set_picks = [p for p in picks
                     if base_pgm(p["pgm"]) in set(cset["all"])]

        # Task 1: layoff flags on contender-set horses
        for p in set_picks:
            dsl = p["days_since_last"] if "days_since_last" in p.keys() else None
            if dsl is not None and dsl >= 90:
                print(f"      ⚠️  LAYOFF: #{p['pgm']} {p['horse_name']} — "
                      f"{dsl} days since last race")

        # Task 2: lone-E key candidate — PAPER-TRACK DATA ONLY (post-Saratoga
        # evaluation). Logged as a zero-cost note row; never alters structure.
        if tickets[0]["race_shape"] == "TIGHT":
            styles = {p["pgm"]: (p["bris_run_style"]
                                 if "bris_run_style" in p.keys() else None)
                      for p in picks}
            e_horses = [pgm for pgm, s in styles.items() if s == "E"]
            for p in sorted(set_picks, key=lambda x: x["model_rank"])[:2]:
                q = p["quirin_pts"] if "quirin_pts" in p.keys() else None
                if (len(e_horses) == 1 and p["pgm"] == e_horses[0]
                        and (q or 0) >= 6):
                    conn.execute("""
                        INSERT INTO exotic_tickets (race_id, ticket_type,
                            combination, cost, denomination, is_paper,
                            race_shape, contender_set)
                        VALUES (?, 'LONE_E_NOTE', ?, 0, 0, 1, 'NOTE', ?)
                    """, (race["id"],
                          f"LONE-E KEY CANDIDATE #{p['pgm']} Q{q} — paper track only",
                          json.dumps(cset["all"])))
                    print(f"      📝 LONE-E KEY CANDIDATE: #{p['pgm']} "
                          f"{p['horse_name']} (rank {p['model_rank']}, Q{q}) "
                          f"— paper track only")

        # Task 3: trainer situational angles for the contender set
        for p in set_picks:
            raw = p["trnr_stats"] if "trnr_stats" in p.keys() else None
            if not raw:
                continue
            stats = [ts for ts in json.loads(raw)
                     if (ts.get("starts") or 0) > 0 or ts.get("roi")]
            if not stats:
                continue
            dsl = p["days_since_last"] if "days_since_last" in p.keys() else None
            for ts in stats:
                cat_l = ts["cat"].lower()
                mark = (" ← LAYOFF MATCH" if dsl is not None and dsl >= 45
                        and ("daysaway" in cat_l or "days away" in cat_l)
                        else "")
                wp = f"{ts['win_pct']:.0f}%" if ts.get("win_pct") else "?"
                roi = (f"${ts['roi']:.2f}" if ts.get("roi") is not None else "?")
                print(f"      📋 #{p['pgm']} {ts['cat']}: "
                      f"{ts['starts']:.0f} sts {wp} ROI {roi}{mark}")
        made += 1

    conn.commit()
    conn.close(); cm.close()
    return made


def settle_card(track, date, race_num=None):
    if not settlement_gate_ok():
        print("❌ settlement gate failed — refusing to settle live data")
        return 0
    conn = sqlite3.connect(R5_DB)
    conn.row_factory = sqlite3.Row
    races = conn.execute(
        "SELECT * FROM races WHERE track=? AND date=? AND is_backtest=0" +
        (" AND race_num=?" if race_num else ""),
        (track.upper(), date) + ((str(race_num),) if race_num else ())
    ).fetchall()
    total = 0
    for race in races:
        n = settle_race(conn, race["id"])
        if n:
            rows = conn.execute(
                "SELECT ticket_type, combination, cost, actual_payoff, profit "
                "FROM exotic_tickets WHERE race_id=? AND profit IS NOT NULL",
                (race["id"],)).fetchall()
            for r in rows:
                tag = "💰" if r["profit"] > 0 else "  "
                print(f"  {tag} R{race['race_num']} {r['ticket_type']} "
                      f"{r['combination']}: cost ${r['cost']:.2f} → "
                      f"collected ${r['actual_payoff']:.2f} "
                      f"(P/L {r['profit']:+.2f})")
            total += n
    conn.commit(); conn.close()
    return total


def report():
    conn = sqlite3.connect(R5_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT COUNT(*) n, SUM(et.cost) cost, SUM(et.actual_payoff) coll,
               SUM(et.profit) pl, SUM(et.profit > 0) winners
        FROM exotic_tickets et JOIN races r ON r.id=et.race_id
        WHERE et.profit IS NOT NULL AND r.is_backtest=0
          AND et.race_shape NOT IN ('SELFTEST', 'NOTE')
    """).fetchone()
    if not row["n"]:
        print("no settled tickets"); return
    print(f"Settled tickets: {row['n']} | hit: {row['winners']} | "
          f"staked ${row['cost']:.2f} | collected ${row['coll']:.2f} | "
          f"P/L {row['pl']:+.2f} | ROI {row['pl']/row['cost']*100:+.1f}%")
    for r in conn.execute("""
        SELECT et.race_shape, et.ticket_type, COUNT(*) n, SUM(et.cost) c,
               SUM(et.profit) pl FROM exotic_tickets et
        JOIN races r ON r.id=et.race_id
        WHERE et.profit IS NOT NULL AND r.is_backtest=0
          AND et.race_shape NOT IN ('SELFTEST', 'NOTE')
        GROUP BY et.race_shape, et.ticket_type"""):
        print(f"  {r['race_shape']:<9} {r['ticket_type']:<8} n={r['n']:<3} "
              f"staked ${r['c']:<7.2f} P/L {r['pl']:+.2f} "
              f"({r['pl']/r['c']*100:+.1f}%)")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="R5 exotics module v1")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--settle", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--track")
    ap.add_argument("--date")
    ap.add_argument("--race", type=int)
    ap.add_argument("--live", action="store_true",
                    help="EXPLICIT live mode (Harry only) — default is paper")
    ap.add_argument("--no-ab", action="store_true",
                    help="skip the passive post-scratch A/B comparison after --settle")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.generate:
        if not (args.track and args.date):
            ap.error("--generate needs --track and --date")
        generate_card(args.track, args.date, args.race, args.live)
    if args.settle:
        if not (args.track and args.date):
            ap.error("--settle needs --track and --date")
        settle_card(args.track, args.date, args.race)
        # ── passive A/B monitor (non-fatal, ISOLATED to ab_tickets) ─────────
        # Post-scratch re-score vs entries+refund. Analysis-only: it NEVER
        # alters the logged tickets or the frozen record. NO-GO finding
        # (2026-07-10): entries+refund beat post-scratch across July SAR, so we
        # do NOT bet the re-score — this just accrues the comparison so we'd
        # catch a regime change. Skips single-race settles and --no-ab.
        if not args.race and not args.no_ab:
            try:
                _abp  = Path(__file__).resolve().parent / "r5_ab.py"
                _abs  = importlib.util.spec_from_file_location("r5_ab", _abp)
                _abm  = importlib.util.module_from_spec(_abs)
                _abs.loader.exec_module(_abm)
                _abm.run_for_card(args.track, args.date)
            except Exception as _e:
                print(f"  [A/B] skipped (non-fatal): {_e}")
    if args.report:
        report()
    if not any([args.selftest, args.generate, args.settle, args.report]):
        ap.print_help()


if __name__ == "__main__":
    main()
