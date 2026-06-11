"""Signal validation vs corrected $2-flat-bet ROI (2026-06-11, Phase 1B).

Read-only against results/r5_results.db and comparemodels/comparemodels_results.db.
Prints every documented signal with: bets, wins, win%, ROI%.
ROI convention: profit = payoff - 2 on a win (0 if payoff unrecorded), -2 on a loss;
ROI% = sum(profit) / (2 * bets) * 100. Picks with finish NULL or -1 are excluded.
"""

import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R5_DB = os.path.join(ROOT, 'results', 'r5_results.db')
CM_DB = os.path.join(ROOT, 'comparemodels', 'comparemodels_results.db')

ROI_EXPR = ("SUM(CASE WHEN {w}=1 AND {sp} IS NOT NULL THEN {sp}-2 "
            "WHEN {w}=1 THEN 0 ELSE -2 END)/(2.0*COUNT(*))*100")


def row(cur, label, sql, params=()):
    n, wins, roi = cur.execute(sql, params).fetchone()
    n = n or 0
    wins = wins or 0
    winp = round(100.0 * wins / n, 1) if n else 0.0
    roi = round(roi, 1) if roi is not None else 0.0
    print(f"{label:<46}|{n:>5} |{wins:>5} |{winp:>6} |{roi:>7}")
    return n, wins, winp, roi


def main():
    r5 = sqlite3.connect(f"file:{R5_DB}?mode=ro", uri=True)
    rc = r5.cursor()
    roi_r5 = ROI_EXPR.format(w='won', sp='sp_odds')
    base = ("FROM picks WHERE model_rank=1 AND finish_pos IS NOT NULL "
            "AND finish_pos != -1")

    print(f"{'signal':<46}| bets | wins |  win% |   roi%")
    print('-' * 78)

    # ── R5 side ──────────────────────────────────────────────────────────
    row(rc, 'R5 rank-1 baseline',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base}")

    # spread gate: rank1 comp - rank2 comp
    spread_cond = ("""(SELECT p1.comp - p2.comp FROM picks p1, picks p2
        WHERE p1.race_id=picks.race_id AND p1.model_rank=1
          AND p2.race_id=picks.race_id AND p2.model_rank=2) {op} 0.5""")
    row(rc, 'Play gate: spread(r1-r2) >= 0.5',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND " + spread_cond.format(op='>='))
    row(rc, 'Skip side: spread(r1-r2) < 0.5',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND " + spread_cond.format(op='<'))

    row(rc, 'PLAY verdict: comp >= 6.0',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND comp >= 6.0")
    row(rc, 'comp < 6.0 (NEAR/SKIP)',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND comp < 6.0")

    # tiers (rank-1 picks)
    row(rc, 'HIGH tier: comp >= 8.5',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND comp >= 8.5")
    row(rc, 'SOLID tier: comp >= 7.5',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND comp >= 7.5")
    row(rc, 'FAIR tier: 6.5 <= comp < 7.5',
        f"SELECT COUNT(*), SUM(won), {roi_r5} {base} AND comp >= 6.5 AND comp < 7.5")
    # all-horse tier fire rates (any rank)
    for t in ('HIGH', 'SOLID'):
        n = rc.execute(
            "SELECT COUNT(*) FROM picks WHERE tier=? AND finish_pos IS NOT NULL AND finish_pos!=-1",
            (t,)).fetchone()[0]
        print(f"{'  (' + t + ' fires, any rank)':<46}|{n:>5} |      |       |")

    # val_n thresholds
    for thr in (7, 8, 9):
        row(rc, f'val_n >= {thr}, rank <= 5',
            f"SELECT COUNT(*), SUM(won), {roi_r5} FROM picks "
            f"WHERE val_n >= {thr} AND model_rank <= 5 "
            "AND finish_pos IS NOT NULL AND finish_pos != -1")
        row(rc, f'val_n >= {thr}, all ranks',
            f"SELECT COUNT(*), SUM(won), {roi_r5} FROM picks "
            f"WHERE val_n >= {thr} "
            "AND finish_pos IS NOT NULL AND finish_pos != -1")

    # tight-cluster approximation: top1-top3 spread bands (post-deduction comp)
    band = ("""(SELECT p1.comp - p3.comp FROM picks p1, picks p3
        WHERE p1.race_id=picks.race_id AND p1.model_rank=1
          AND p3.race_id=picks.race_id AND p3.model_rank=3)""")
    for rk in (1, 2):
        row(rc, f'cluster<=0.5 (approx): bet rank {rk}',
            f"SELECT COUNT(*), SUM(won), {roi_r5} FROM picks "
            f"WHERE model_rank={rk} AND finish_pos IS NOT NULL AND finish_pos != -1 "
            f"AND {band} <= 0.5")
        row(rc, f'cluster 0.5-1.5 (approx): bet rank {rk}',
            f"SELECT COUNT(*), SUM(won), {roi_r5} FROM picks "
            f"WHERE model_rank={rk} AND finish_pos IS NOT NULL AND finish_pos != -1 "
            f"AND {band} > 0.5 AND {band} <= 1.5")

    # rank-win distribution R5
    print('\nR5 winners by rank (rank | bets | wins | win% | roi%)')
    for r in range(1, 9):
        row(rc, f'  R5 rank {r}',
            f"SELECT COUNT(*), SUM(won), {roi_r5} FROM picks "
            f"WHERE model_rank={r} AND finish_pos IS NOT NULL AND finish_pos != -1")
    r5.close()

    # ── CM side + head-to-head ───────────────────────────────────────────
    cm = sqlite3.connect(f"file:{CM_DB}?mode=ro", uri=True)
    cm.execute(f"ATTACH '{R5_DB}' AS r5")
    cc = cm.cursor()
    cc.execute("""
    CREATE TEMP TABLE h2h AS
    SELECT cm.track, cm.race_date, cm.race, cm.horse_pgm AS cm_pgm,
           cm.consensus_count AS cons, cm.is_dominant AS dom,
           r5p.pgm AS r5_pgm, r5p.finish_pos AS r5_finish, r5p.won AS r5_won,
           wsp.sp_odds AS winner_sp,
           CASE WHEN cmres.finish_position=1 THEN 1 ELSE 0 END AS cm_won,
           CASE WHEN cmres.finish_position=1 THEN COALESCE(cmres.sp_odds, wsp.sp_odds) END AS cm_win_sp
    FROM picks cm
    JOIN results cmres ON cmres.track=cm.track AND cmres.race_date=cm.race_date
      AND cmres.race=cm.race AND cmres.horse_pgm=cm.horse_pgm
    JOIN r5.races r ON r.track=cm.track AND r.date=cm.race_date
      AND CAST(r.race_num AS INT)=cm.race AND r.result_fetched=1
    JOIN r5.picks r5p ON r5p.race_id=r.id AND r5p.model_rank=1
    LEFT JOIN r5.picks wsp ON wsp.race_id=r.id AND wsp.won=1
    WHERE cm.cm_rank=1 AND cmres.finish_position IS NOT NULL
      AND cmres.finish_position != -1""")

    roi_cm = ROI_EXPR.format(w='cm_won', sp='cm_win_sp')
    roi_r5h = ROI_EXPR.format(w='r5_won', sp='winner_sp')
    n_univ = cc.execute("SELECT COUNT(*) FROM h2h").fetchone()[0]
    print(f'\nCM / head-to-head (aligned universe: {n_univ} races)')
    print('-' * 78)
    row(cc, 'CM rank-1 baseline', f"SELECT COUNT(*), SUM(cm_won), {roi_cm} FROM h2h")
    for thr in (4, 5, 6, 7):
        n, w, wp, ro = row(cc, f'CM consensus >= {thr}',
            f"SELECT COUNT(*), SUM(cm_won), {roi_cm} FROM h2h WHERE cons >= {thr}")
        print(f"{'  (fire rate)':<46}|{round(100.0*n/n_univ,1):>5}%|      |       |")
    row(cc, 'CM Dominant flag (rank 1)',
        f"SELECT COUNT(*), SUM(cm_won), {roi_cm} FROM h2h WHERE dom=1")
    row(cc, 'Agreement (same pick): bet it',
        f"SELECT COUNT(*), SUM(cm_won), {roi_cm} FROM h2h WHERE cm_pgm = r5_pgm")
    row(cc, 'Divergence: bet CM pick',
        f"SELECT COUNT(*), SUM(cm_won), {roi_cm} FROM h2h WHERE cm_pgm != r5_pgm")
    row(cc, 'Divergence: bet R5 pick',
        f"SELECT COUNT(*), SUM(r5_won), {roi_r5h} FROM h2h "
        "WHERE cm_pgm != r5_pgm AND r5_finish IS NOT NULL AND r5_finish != -1")
    # outlier sensitivity: exclude single largest winning payoff from div-R5
    top = cc.execute("""SELECT MAX(winner_sp) FROM h2h
        WHERE cm_pgm != r5_pgm AND r5_won=1""").fetchone()[0]
    row(cc, f'Divergence: bet R5 ex top payoff (${top})',
        f"SELECT COUNT(*), SUM(r5_won), {roi_r5h} FROM h2h "
        "WHERE cm_pgm != r5_pgm AND r5_finish IS NOT NULL AND r5_finish != -1 "
        "AND (r5_won=0 OR winner_sp < ?)", (top,))

    # PP underline
    pp_base = """FROM category_picks cp
    JOIN results res ON res.track=cp.track AND res.race_date=cp.race_date
      AND res.race=cp.race AND res.horse_pgm=cp.horse_pgm
    WHERE cp.category='Prime Power' AND cp.underlined=1 AND cp.rank_in_cat=1
      AND res.finish_position IS NOT NULL AND res.finish_position != -1"""
    roi_pp = ROI_EXPR.format(
        w='(CASE WHEN res.finish_position=1 THEN 1 ELSE 0 END)', sp='res.sp_odds')
    row(cc, 'PP underline standalone',
        f"SELECT COUNT(*), SUM(CASE WHEN res.finish_position=1 THEN 1 ELSE 0 END), {roi_pp} {pp_base}")
    row(cc, 'PP underline AND horse = R5 rank-1',
        f"SELECT COUNT(*), SUM(CASE WHEN res.finish_position=1 THEN 1 ELSE 0 END), {roi_pp} {pp_base} "
        "AND EXISTS (SELECT 1 FROM r5.races rr JOIN r5.picks rp ON rp.race_id=rr.id "
        "WHERE rr.track=cp.track AND rr.date=cp.race_date "
        "AND CAST(rr.race_num AS INT)=cp.race AND rp.model_rank=1 AND rp.pgm=cp.horse_pgm)")

    # rank-win distribution CM
    print('\nCM winners by rank (rank | bets | wins | win% | roi%)')
    roi_cmr = ROI_EXPR.format(
        w='(CASE WHEN res.finish_position=1 THEN 1 ELSE 0 END)', sp='res.sp_odds')
    for r in range(1, 9):
        row(cc, f'  CM rank {r}',
            f"SELECT COUNT(*), SUM(CASE WHEN res.finish_position=1 THEN 1 ELSE 0 END), {roi_cmr} "
            "FROM picks p JOIN results res ON res.track=p.track AND res.race_date=p.race_date "
            "AND res.race=p.race AND res.horse_pgm=p.horse_pgm "
            f"WHERE p.cm_rank={r} AND res.finish_position IS NOT NULL AND res.finish_position != -1")
    cm.close()


if __name__ == '__main__':
    main()
