#!/usr/bin/env python3
"""
r5_probability.py — Conditional logit P(win) layer (Session 2, Task 5).

P(win)_i = exp(β·x_i) / Σ_j exp(β·x_j),  x = comp_ex_val (market-free,
val_n permanently excluded). One parameter, fit by MLE over races with a
known winner. Newton's method with analytic derivatives — the NLL is convex
in β, so this is exact; no scipy dependency (engine runs on stock python3;
deviation from the brief's scipy.optimize noted in the Week 2 report).

    LL(β)   = Σ_r [ β·x_w − log Σ_i exp(β·x_i) ]
    LL'(β)  = Σ_r [ x_w − E_r(x) ]
    LL''(β) = −Σ_r Var_r(x)

Overlay rule (Decision 1C): edge = P·(odds+1) − 1; OVERLAY iff edge ≥ +0.25
AND P ≥ 0.08. ML-based edges are ADVISORY ONLY (Harry ruling 4).

val_n ≥ 8 tracker (Harry ruling 3): flat $2, max 2/card, hard stop at
0 wins in 30 settled bets OR SUM(profit) < −60 — computed at decision time,
never stored as a running column. The gate is code in the logging path.

Usage:
    python3 Claude/r5_probability.py --fit          # fit β, serialize, score DB
    python3 Claude/r5_probability.py --calibrate    # write calibration report
    python3 Claude/r5_probability.py --val-status   # tracker + stop-state
"""

import argparse
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
from r5_paths import R5_DB_PATH as DB_PATH, BETA_PATH, RESULTS_DIR

OVERLAY_EDGE_MIN = 0.25
OVERLAY_P_MIN    = 0.08
VAL_N_THRESHOLD   = 8.0
VAL_N_PAPER75     = 7.5    # paper-only population for n≥120 re-decision
VAL_STOP_BETS     = 30      # 0 wins in this many settled bets -> stop
VAL_STOP_LOSS     = -60.0   # SUM(profit) floor
VAL_MAX_PER_CARD  = 2
VAL_BET_SIZE      = 2.0
VAL_MAX_RANK      = 5       # model_rank filter for both lines


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Guard: add is_backtest column if this DB predates 2026-06-12
    try:
        conn.execute("ALTER TABLE races ADD COLUMN is_backtest INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn


def ensure_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(picks)")}
    for col in ("p_win", "fair_odds", "ml_edge"):
        if col not in cols:
            conn.execute(f"ALTER TABLE picks ADD COLUMN {col} REAL")
    if "is_overlay" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN is_overlay INTEGER DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS val_n_tracker (
            id INTEGER PRIMARY KEY,
            pick_id INTEGER REFERENCES picks(id),
            val_n REAL NOT NULL,
            ml_odds REAL,
            bet_size REAL DEFAULT 2.0,
            is_paper INTEGER DEFAULT 1,
            line TEXT DEFAULT 'live8',
            result INTEGER,
            payoff REAL,
            profit REAL,
            stop_triggered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pick_id, line)
        )
    """)
    # Add line column to existing DBs that predate this change
    try:
        conn.execute("ALTER TABLE val_n_tracker ADD COLUMN line TEXT DEFAULT 'live8'")
    except sqlite3.OperationalError:
        pass
    conn.commit()


# ── FITTING ───────────────────────────────────────────────────────────────────

def _load_fit_races(conn):
    """Races with a winner whose comp_ex_val is known. Field = picks with
    comp_ex_val, scratches (finish_pos = -1 / NULL) excluded. Races whose
    winner lacks comp_ex_val are dropped and counted."""
    races, dropped = [], 0
    for race in conn.execute(
            "SELECT id FROM races WHERE result_fetched=1 AND is_backtest=0").fetchall():
        rows = conn.execute(
            "SELECT comp_ex_val x, won FROM picks WHERE race_id=? "
            "AND finish_pos IS NOT NULL AND finish_pos != -1", (race["id"],)
        ).fetchall()
        field  = [r["x"] for r in rows if r["x"] is not None]
        winner = [r["x"] for r in rows if r["won"] and r["x"] is not None]
        if not winner:
            if any(r["won"] for r in rows):
                dropped += 1   # winner exists but has no comp_ex_val
            continue
        if len(field) < 2:
            dropped += 1
            continue
        races.append((winner[0], field))
    return races, dropped


def _race_moments(beta, xs):
    mx = max(xs)
    ws = [math.exp(beta * (x - mx)) for x in xs]
    z  = sum(ws)
    ps = [w / z for w in ws]
    ex  = sum(p * x for p, x in zip(ps, xs))
    ex2 = sum(p * x * x for p, x in zip(ps, xs))
    logz = math.log(z) + beta * mx
    return ps, ex, ex2 - ex * ex, logz


def fit_logit(db_path=DB_PATH):
    conn = get_conn()
    ensure_schema(conn)
    races, dropped = _load_fit_races(conn)
    conn.close()

    beta = 0.5
    for _ in range(50):
        g = h = 0.0
        for xw, xs in races:
            _, ex, var, _ = _race_moments(beta, xs)
            g += xw - ex
            h += var
        step = g / h if h > 0 else 0.0
        beta += step
        if abs(step) < 1e-10:
            break

    ll = sum(beta * xw - _race_moments(beta, xs)[3] for xw, xs in races)
    meta = {
        "beta": round(beta, 6),
        "log_likelihood": round(ll, 2),
        "n_races": len(races),
        "n_dropped_missing_winner_vector": dropped,
        "input": "comp_ex_val (val_n excluded permanently)",
        "fitted_at": datetime.now().isoformat(timespec="seconds"),
    }
    BETA_PATH.write_text(json.dumps(meta, indent=2))
    return meta


def load_beta():
    return json.loads(BETA_PATH.read_text())["beta"]


# ── SCORING ───────────────────────────────────────────────────────────────────

def score_field(horses, beta):
    """horses: list of dicts with comp_ex_val (and optionally ml_odds).
    Mutates each: p_win, fair_odds, ml_edge, is_overlay. Horses lacking
    comp_ex_val get None across the board and are excluded from the
    normalization. Returns horses."""
    xs = [(i, h["comp_ex_val"]) for i, h in enumerate(horses)
          if h.get("comp_ex_val") is not None]
    if len(xs) < 2:
        for h in horses:
            h["p_win"] = h["fair_odds"] = h["ml_edge"] = None
            h["is_overlay"] = 0
        return horses
    ps, _, _, _ = _race_moments(beta, [x for _, x in xs])
    pmap = {i: p for (i, _), p in zip(xs, ps)}
    for i, h in enumerate(horses):
        p = pmap.get(i)
        if p is None:
            h["p_win"] = h["fair_odds"] = h["ml_edge"] = None
            h["is_overlay"] = 0
            continue
        h["p_win"]     = round(p, 4)
        h["fair_odds"] = round(1 / p - 1, 2)
        ml = h.get("ml_odds")
        if ml and ml > 0:
            edge = p * (ml + 1) - 1
            h["ml_edge"]    = round(edge, 4)
            h["is_overlay"] = 1 if (edge >= OVERLAY_EDGE_MIN
                                    and p >= OVERLAY_P_MIN) else 0
        else:
            h["ml_edge"]    = None
            h["is_overlay"] = 0
    return horses


def score_db(beta):
    """Populate p_win / fair_odds / ml_edge / is_overlay for every historical
    pick with comp_ex_val (race-normalized, runners only)."""
    conn = get_conn()
    ensure_schema(conn)
    n = 0
    for race in conn.execute("SELECT id FROM races").fetchall():
        rows = conn.execute(
            "SELECT id, comp_ex_val, ml_odds FROM picks WHERE race_id=? "
            "AND (finish_pos IS NULL OR finish_pos != -1)", (race["id"],)
        ).fetchall()
        horses = [dict(r) for r in rows]
        score_field(horses, beta)
        for h in horses:
            conn.execute(
                "UPDATE picks SET p_win=?, fair_odds=?, ml_edge=?, is_overlay=? "
                "WHERE id=?",
                (h["p_win"], h["fair_odds"], h["ml_edge"], h["is_overlay"], h["id"]))
            if h["p_win"] is not None:
                n += 1
    conn.commit()
    conn.close()
    return n


# ── CALIBRATION ───────────────────────────────────────────────────────────────

def calibration_report(db_path=DB_PATH):
    conn = get_conn()
    meta = json.loads(BETA_PATH.read_text())
    rows = conn.execute("""
        SELECT p.p_win, p.won, p.model_rank FROM picks p
        JOIN races r ON r.id=p.race_id
        WHERE r.result_fetched=1 AND r.is_backtest=0
          AND p.p_win IS NOT NULL
          AND p.finish_pos IS NOT NULL AND p.finish_pos != -1
    """).fetchall()

    srt = sorted(rows, key=lambda r: r["p_win"])
    n   = len(srt)
    lines = [
        f"# Calibration Report — {datetime.now().date()}",
        "",
        f"β = {meta['beta']:.4f} | LL = {meta['log_likelihood']} | "
        f"fit races = {meta['n_races']} | dropped (winner missing comp_ex_val) "
        f"= {meta['n_dropped_missing_winner_vector']}",
        "",
        f"In-sample picks scored: {n} (current-formula universe)",
        "",
        "| Decile | n | mean predicted P | observed win% |",
        "|---|---|---|---|",
    ]
    for d in range(10):
        chunk = srt[d * n // 10:(d + 1) * n // 10]
        if not chunk:
            continue
        mp = sum(r["p_win"] for r in chunk) / len(chunk)
        ow = sum(r["won"] for r in chunk) / len(chunk)
        lines.append(f"| {d+1} | {len(chunk)} | {mp*100:.1f}% | {ow*100:.1f}% |")

    lines += ["", "## Rank-3 diagnostic (Decision 1B mandatory check)", ""]
    r3 = [r for r in rows if r["model_rank"] == 3]
    if r3:
        mp3 = sum(r["p_win"] for r in r3) / len(r3)
        ow3 = sum(r["won"] for r in r3) / len(r3)
        lines += [
            f"- Rank-3 picks: {len(r3)} | mean predicted P = {mp3*100:.1f}% | "
            f"observed = {ow3*100:.1f}%",
            f"- Full-DB observed rank-3 reference (160-race baseline): 23.2%",
            "- If predicted is far below observed, β is over-discriminating "
            "tight clusters; report, do not tune.",
        ]
    for rank in (1, 2):
        rr = [r for r in rows if r["model_rank"] == rank]
        if rr:
            mp_ = sum(r["p_win"] for r in rr) / len(rr)
            ow_ = sum(r["won"] for r in rr) / len(rr)
            lines.append(f"- Rank-{rank}: n={len(rr)}, predicted "
                         f"{mp_*100:.1f}%, observed {ow_*100:.1f}%")

    out = RESULTS_DIR / f"CALIBRATION_REPORT_{datetime.now():%Y%m%d}.md"
    out.write_text("\n".join(lines) + "\n")
    conn.close()
    return out, lines


# ── val_n ≥ 8 TRACKER (Harry ruling 3 — gates are CODE, not comments) ────────

def val_gate_state(conn):
    """Evaluate the hard-stop conditions from settled live bets.
    Returns (stopped: bool, reason: str|None, settled, wins, total_profit)."""
    row = conn.execute("""
        SELECT COUNT(*) n, COALESCE(SUM(result),0) wins,
               COALESCE(SUM(profit),0) profit
        FROM val_n_tracker WHERE is_paper=0 AND result IS NOT NULL
    """).fetchone()
    settled, wins, profit = row["n"], row["wins"], row["profit"]
    if settled >= VAL_STOP_BETS and wins == 0:
        return True, f"0 wins in {settled} settled bets", settled, wins, profit
    if profit < VAL_STOP_LOSS:
        return True, f"cumulative profit ${profit:.2f} < {VAL_STOP_LOSS}", \
            settled, wins, profit
    return False, None, settled, wins, profit


def log_val_bet(pick_id, live=False):
    """Log a val_n >= 8 qualifier. live=True requests a live bet; every gate
    is checked here and a refused live bet is logged as paper instead.
    line is 'live8' for live bets, 'paper8' for paper (gate-blocked or default)."""
    conn = get_conn()
    ensure_schema(conn)
    p = conn.execute(
        "SELECT p.*, r.track, r.date FROM picks p JOIN races r ON r.id=p.race_id "
        "WHERE p.id=?", (pick_id,)).fetchone()
    if not p:
        conn.close()
        return None, "pick not found"
    if (p["val_n"] or 0) < VAL_N_THRESHOLD:
        conn.close()
        return None, f"val_n {p['val_n']} below threshold {VAL_N_THRESHOLD}"

    reason = None
    is_paper = 1
    line = "paper8"
    if live:
        stopped, why, *_ = val_gate_state(conn)
        card_count = conn.execute("""
            SELECT COUNT(*) FROM val_n_tracker v
            JOIN picks pp ON pp.id=v.pick_id JOIN races rr ON rr.id=pp.race_id
            WHERE v.is_paper=0 AND rr.track=? AND rr.date=?
        """, (p["track"], p["date"])).fetchone()[0]
        if stopped:
            reason = f"REFUSED LIVE — hard stop: {why}; logged as paper"
        elif card_count >= VAL_MAX_PER_CARD:
            reason = (f"REFUSED LIVE — {card_count} live bets already on "
                      f"{p['track']} {p['date']}; logged as paper")
        else:
            is_paper = 0
            line = "live8"
    conn.execute("""
        INSERT OR IGNORE INTO val_n_tracker
        (pick_id, val_n, ml_odds, bet_size, is_paper, line, stop_triggered)
        VALUES (?,?,?,?,?,?,?)
    """, (pick_id, p["val_n"], p["ml_odds"], VAL_BET_SIZE, is_paper, line,
          1 if (live and reason and "hard stop" in reason) else 0))
    conn.commit()
    conn.close()
    return is_paper, reason


def log_val_paper75(pick_id):
    """Log a val_n >= 7.5, rank <= 5 qualifier to the paper75 line.
    Always paper. If this pick also qualifies for live8/paper8, it is logged
    separately in that line — both rows are independent."""
    conn = get_conn()
    ensure_schema(conn)
    p = conn.execute(
        "SELECT p.*, r.track, r.date, r.is_backtest FROM picks p "
        "JOIN races r ON r.id=p.race_id WHERE p.id=?", (pick_id,)).fetchone()
    if not p:
        conn.close()
        return None, "pick not found"
    if (p["val_n"] or 0) < VAL_N_PAPER75:
        conn.close()
        return None, f"val_n {p['val_n']} below {VAL_N_PAPER75}"
    if (p["model_rank"] or 99) > VAL_MAX_RANK:
        conn.close()
        return None, f"model_rank {p['model_rank']} > {VAL_MAX_RANK}"
    if p["is_backtest"]:
        conn.close()
        return None, "backtest race — skipped"
    conn.execute("""
        INSERT OR IGNORE INTO val_n_tracker
        (pick_id, val_n, ml_odds, bet_size, is_paper, line, stop_triggered)
        VALUES (?,?,?,?,1,'paper75',0)
    """, (pick_id, p["val_n"], p["ml_odds"], VAL_BET_SIZE))
    conn.commit()
    conn.close()
    return 1, None


def auto_log_val_trackers_for_race(track, date, race_num, live=False):
    """Called automatically after log_race_picks.
    - live8/paper8 line: val_n >= 8, model_rank <= VAL_MAX_RANK
    - paper75 line:      val_n >= 7.5, model_rank <= VAL_MAX_RANK (always paper)
    live=True requests live bets for the live8 line (subject to gate checks)."""
    conn = get_conn()
    ensure_schema(conn)
    picks = conn.execute("""
        SELECT p.id, p.val_n, p.model_rank FROM picks p
        JOIN races r ON r.id = p.race_id
        WHERE r.track=? AND r.date=? AND r.race_num=?
          AND r.is_backtest=0
          AND p.model_rank <= ?
          AND (p.val_n IS NOT NULL AND p.val_n >= ?)
    """, (track, date, str(race_num), VAL_MAX_RANK, VAL_N_PAPER75)).fetchall()
    conn.close()

    logged8, logged75 = [], []
    for p in picks:
        val = p["val_n"]
        pid = p["id"]
        if val >= VAL_N_THRESHOLD:
            is_paper, reason = log_val_bet(pid, live=live)
            tag = "paper8" if is_paper else "live8"
            logged8.append((pid, val, tag, reason))
        # paper75 always logged for the complete >= 7.5 population
        log_val_paper75(pid)
        logged75.append((pid, val))

    if logged8:
        for pid, val, tag, reason in logged8:
            note = f" ({reason})" if reason else ""
            print(f"  💰 val_n {val:.1f} [{tag}] pick_id={pid}{note}")
    if logged75:
        print(f"  📝 paper75 logged: {len(logged75)} qualifier(s)")
    return logged8, logged75


def settle_val_bets():
    """Settle pending tracker rows from pick results (corrected convention:
    profit = payoff - 2 on a win, -2 on a loss, per $2 bet)."""
    conn = get_conn()
    ensure_schema(conn)
    n = 0
    for v in conn.execute("""
        SELECT v.id, p.won, p.sp_odds, p.finish_pos FROM val_n_tracker v
        JOIN picks p ON p.id=v.pick_id
        WHERE v.result IS NULL AND p.finish_pos IS NOT NULL
    """).fetchall():
        if v["finish_pos"] == -1:
            continue  # scratched — leave pending for manual void
        won    = 1 if v["won"] else 0
        payoff = v["sp_odds"] if (won and v["sp_odds"]) else None
        profit = (payoff - 2.0) if (won and payoff) else (0.0 if won else -2.0)
        conn.execute(
            "UPDATE val_n_tracker SET result=?, payoff=?, profit=? WHERE id=?",
            (won, payoff, profit, v["id"]))
        n += 1
    conn.commit()
    conn.close()
    return n


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="R5 conditional logit P(win) layer")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--val-status", action="store_true")
    args = ap.parse_args()

    if args.fit:
        meta = fit_logit()
        print(f"β = {meta['beta']:.4f}  LL = {meta['log_likelihood']}  "
              f"races = {meta['n_races']}  dropped = "
              f"{meta['n_dropped_missing_winner_vector']}")
        n = score_db(meta["beta"])
        print(f"{n} picks scored (p_win/fair_odds/ml_edge/is_overlay) → picks")
        print(f"β serialized → {BETA_PATH}")

    if args.calibrate:
        out, lines = calibration_report()
        print("\n".join(lines))
        print(f"\n→ {out}")

    if args.val_status:
        conn = get_conn()
        ensure_schema(conn)
        stopped, why, settled, wins, profit = val_gate_state(conn)
        total = conn.execute("SELECT COUNT(*) FROM val_n_tracker").fetchone()[0]
        print(f"val_n tracker: {total} logged | live/paper8 settled {settled}, "
              f"wins {wins}, profit ${profit:.2f}")
        print(f"hard stop: {'TRIGGERED — ' + why if stopped else 'clear'}")
        # paper75 line summary
        p75 = conn.execute("""
            SELECT COUNT(*) n, COALESCE(SUM(result),0) wins, COALESCE(SUM(profit),0) profit
            FROM val_n_tracker WHERE line='paper75' AND result IS NOT NULL
        """).fetchone()
        p75_total = conn.execute(
            "SELECT COUNT(*) FROM val_n_tracker WHERE line='paper75'"
        ).fetchone()[0]
        roi75 = p75["profit"] / (p75["n"] * 2) * 100 if p75["n"] else 0
        print(f"paper75 line: {p75_total} logged | settled {p75['n']} | "
              f"wins {p75['wins']} | profit ${p75['profit']:.2f} | ROI {roi75:.1f}%")
        conn.close()

    if not any([args.fit, args.calibrate, args.val_status]):
        ap.print_help()


if __name__ == "__main__":
    main()
