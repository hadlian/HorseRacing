#!/usr/bin/env python3
"""
overlay_retrotest.py — Final-odds overlay retro-test (Week 3, Harry-ordered).

Tests the Decision 1C overlay rule against CAPTURED FINAL TOTE ODDS (not the
stale morning line): bet $2 to win on every horse where

    P(win) × (final_odds + 1) ≥ THRESHOLD   and   P(win) ≥ 0.08

Corrected ROI convention: profit = payoff − 2 on a win, −2 on a loss.
Payoff = race_payoffs WIN row when present, else 2 × (final_odds + 1).

Caveats stated up front (also in output):
  - IN-SAMPLE: β was fit on these same races.
  - Final odds are not fully knowable at bet time (last-cycle drift).
Both biases FAVOR the signal — a negative result here is decisive,
a positive one is necessary-but-not-sufficient.

This result gates live overlay win betting at Saratoga.

Usage: python3 scripts/overlay_retrotest.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "Results" / "r5_results.db"

P_MIN = 0.08
THRESHOLDS = (1.10, 1.25, 1.40, 1.60)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT p.race_id, p.pgm, p.p_win, p.won, p.finish_pos, p.sp_odds,
               p.model_rank, f.final_tote_odds,
               (SELECT payoff FROM race_payoffs w
                 WHERE w.race_id = p.race_id AND w.pool='WIN'
                   AND w.combination = CAST(CAST(p.pgm AS INT) AS TEXT)) AS win_payoff
        FROM picks p
        JOIN races r ON r.id = p.race_id
        JOIN race_finish_order f
          ON f.race_id = p.race_id AND f.horse_pgm = p.pgm
        WHERE r.result_fetched = 1
          AND p.p_win IS NOT NULL
          AND p.finish_pos IS NOT NULL AND p.finish_pos != -1
          AND f.final_tote_odds IS NOT NULL
          AND f.is_late_scratch = 0
    """).fetchall()

    n_races = conn.execute("""
        SELECT COUNT(DISTINCT p.race_id) FROM picks p
        JOIN race_finish_order f ON f.race_id=p.race_id AND f.horse_pgm=p.pgm
        WHERE p.p_win IS NOT NULL AND f.final_tote_odds IS NOT NULL
    """).fetchone()[0]

    print(f"Universe: {len(rows)} scored runners with final tote odds "
          f"across {n_races} races (in-sample; β fit on this data — "
          f"biases favor the signal; negative = decisive)\n")

    print(f"{'threshold':>9} | {'bets':>5} | {'wins':>4} | {'win%':>5} | "
          f"{'ROI%':>7} | {'avg odds':>8}")
    print("-" * 55)

    decision_line = None
    for th in THRESHOLDS:
        bets = [r for r in rows
                if r["p_win"] >= P_MIN
                and r["p_win"] * (r["final_tote_odds"] + 1) >= th]
        n = len(bets)
        wins = sum(r["won"] for r in bets)
        profit = 0.0
        for r in bets:
            if r["won"]:
                pay = (r["win_payoff"] or r["sp_odds"]
                       or 2 * (r["final_tote_odds"] + 1))
                profit += pay - 2
            else:
                profit -= 2
        roi = profit / (2 * n) * 100 if n else 0.0
        avg_o = sum(r["final_tote_odds"] for r in bets) / n if n else 0
        marker = "  ← RULE" if th == 1.25 else ""
        print(f"{th:>9} | {n:>5} | {wins:>4} | "
              f"{wins/n*100 if n else 0:>4.1f}% | {roi:>+6.1f}% | "
              f"{avg_o:>7.1f}-1{marker}")
        if th == 1.25:
            decision_line = (n, wins, roi)

    # rank composition of the rule's bets
    bets = [r for r in rows if r["p_win"] >= P_MIN
            and r["p_win"] * (r["final_tote_odds"] + 1) >= 1.25]
    by_rank = {}
    for r in bets:
        by_rank.setdefault(min(r["model_rank"], 4), [0, 0])
        by_rank[min(r["model_rank"], 4)][0] += 1
        by_rank[min(r["model_rank"], 4)][1] += r["won"]
    print("\nRule-qualifying bets by model rank (rank: bets/wins):",
          {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_rank.items())})

    n, wins, roi = decision_line
    print(f"\n{'='*55}")
    if roi > 10 and wins >= 8:
        print(f"VERDICT: positive at threshold 1.25 ({roi:+.1f}%, {wins} wins) "
              f"— but in-sample + hindsight-odds. Recommend paper-first at SAR "
              f"with live authorization only after out-of-sample confirmation.")
    elif roi > 0:
        print(f"VERDICT: marginally positive ({roi:+.1f}%, {wins} wins) — "
              f"NOT sufficient to authorize live overlay betting "
              f"(in-sample, hindsight odds). Paper-track at SAR.")
    else:
        print(f"VERDICT: NEGATIVE ({roi:+.1f}% on {n} bets) despite both "
              f"biases favoring the signal — live overlay win betting is "
              f"NOT authorized. Overlay flags remain advisory/paper.")
    conn.close()


if __name__ == "__main__":
    main()
