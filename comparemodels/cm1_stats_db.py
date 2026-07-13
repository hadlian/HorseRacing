"""
CM1 stats DB — the "doing well" results tables (Harry ruling: build from results, not
hardcoded lists). One event-sourced store for three connection kinds:

    kind ∈ {trainer, jockey, bms}   (bms = broodmare-sire / dam's sire, f55)

Every settled starter emits one event per kind: (kind, key, surface, date, won, ret),
staked = $2 flat. Aggregates are computed POINT-IN-TIME (date < the scored card's date), so
a backfill can never leak future results. Own DB (cm1_stats.db); reads r5_results.db and the
retained DRFs read-only; never writes them.

Thresholds ("doing well" cutoffs) are DEFAULTS pending Frank/Harry — flagged, not final.

Usage:
    python3 comparemodels/cm1_stats_db.py --seed      # (re)build from history
    python3 comparemodels/cm1_stats_db.py --top trainer   # top keys by ROI
"""

import os
import sqlite3
import sys
import glob
import re

sys.path.insert(0, os.path.dirname(__file__))
from cm1_reader import extract_card   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R5_DB = os.path.join(ROOT, "Results", "r5_results.db")          # correct case
STATS_DB = os.path.join(os.path.dirname(__file__), "cm1_stats.db")
FILES_DIR = os.path.join(ROOT, "files 2")

# "doing well" defaults (TUNABLE — pending Frank/Harry)
TJ_FLOOR = 20          # trainer/jockey min starts before "hot" can fire
TJ_WIN_MIN = 15.0      # win% cutoff for "doing well"
BMS_FLOOR = 30         # broodmare-sire min starts before it scores
STAKE = 2.0


def _surf(s):
    s = (s or "").strip().upper()
    return s[0] if s else "?"


def init_db(path=STATS_DB):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS perf_event (
        kind TEXT, key TEXT, surface TEXT, date TEXT,
        won INTEGER, ret REAL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_perf ON perf_event(kind, key, surface, date)")
    conn.commit()
    return conn


def _results_for_race(r5, track, date, race):
    """{pgm: (won, final_odds)} for actual runners (finish_position >= 1)."""
    rows = r5.execute(
        "SELECT fo.horse_pgm, fo.finish_position, fo.final_tote_odds "
        "FROM race_finish_order fo JOIN races r ON fo.race_id=r.id "
        "WHERE r.track=? AND r.date=? AND r.race_num=? AND fo.finish_position>=1",
        (track, date, str(race))).fetchall()
    out = {}
    for pgm, fin, odds in rows:
        out[re.sub(r"[A-Za-z]$", "", str(pgm))] = (1 if fin == 1 else 0, odds)
    return out


def seed_from_history(verbose=True):
    """Rebuild the event store from every result-fetched card that still has its DRF."""
    if os.path.exists(STATS_DB):
        os.remove(STATS_DB)
    conn = init_db()
    r5 = sqlite3.connect(f"file:{R5_DB}?mode=ro", uri=True)
    cards = r5.execute(
        "SELECT DISTINCT track, date FROM races WHERE result_fetched=1 ORDER BY date"
    ).fetchall()
    drfs = {}
    for f in os.listdir(FILES_DIR):
        m = re.match(r"([A-Za-z]{3})(\d{4})\.DRF$", f, re.I)
        if m:
            drfs[(m.group(1).upper(), m.group(2))] = os.path.join(FILES_DIR, f)

    events, no_drf, cards_used = [], 0, 0
    for track, date in cards:
        path = drfs.get((track.upper(), date[4:8]))
        if not path:
            no_drf += 1
            continue
        cards_used += 1
        card = extract_card(path)
        for race, horses in card.items():
            res = _results_for_race(r5, track, date, race)
            for h in horses:
                pgm = re.sub(r"[A-Za-z]$", "", h["pgm"])
                if pgm not in res:
                    continue                          # scratched / not a runner
                won, odds = res[pgm]
                ret = STAKE * (odds + 1) if (won and odds is not None) else 0.0
                surf = _surf(h["today_surf"])
                for kind, key in (("trainer", h["trainer"]),
                                  ("jockey", h["jockey"]),
                                  ("bms", h["dam_sire"])):
                    if key:
                        events.append((kind, key.strip().upper(), surf, date, won, ret))
    conn.executemany("INSERT INTO perf_event VALUES (?,?,?,?,?,?)", events)
    conn.commit()
    r5.close()
    if verbose:
        print(f"seeded {len(events)} events from {cards_used} cards "
              f"({no_drf} cards skipped — no DRF)")
        for kind in ("trainer", "jockey", "bms"):
            nk = conn.execute("SELECT COUNT(DISTINCT key) FROM perf_event WHERE kind=?",
                              (kind,)).fetchone()[0]
            print(f"   {kind:<8} {nk} distinct keys")
    conn.close()


def record(conn, kind, key, date, surface=None):
    """Point-in-time aggregate for a key strictly BEFORE `date`.
    surface=None → all surfaces. Returns dict(starts,wins,roi,largest)."""
    q = ("SELECT COUNT(*), COALESCE(SUM(won),0), COALESCE(SUM(ret),0), "
         "COALESCE(MAX(ret),0) FROM perf_event WHERE kind=? AND key=? AND date<?")
    args = [kind, (key or "").strip().upper(), date]
    if surface:
        q += " AND surface=?"
        args.append(surface)
    starts, wins, ret, largest = conn.execute(q, args).fetchone()
    staked = STAKE * starts
    return {"starts": starts, "wins": wins,
            "win_pct": (100.0 * wins / starts) if starts else 0.0,
            "roi": ((ret - staked) / staked) if staked else 0.0,
            "largest": largest}


def is_hot_tj(conn, kind, key, date):
    """Trainer/jockey 'doing well' = Frank's criterion: WIN RATE (hot at the meet),
    n≥floor. NO ROI gate — Frank's hot jockeys (Prat 29%, Ortiz 23%) are bet down to
    ROI≈0; gating on ROI would exclude the exact names he lists. ROI discipline lives
    at the outer promotion gate (does CM1's flag-count beat the market), not here."""
    r = record(conn, kind, key, date)
    return r["starts"] >= TJ_FLOOR and r["win_pct"] >= TJ_WIN_MIN


def is_bms_positive(conn, key, date, surface=None):
    """Broodmare-sire scores only at n≥floor AND ROI>0 AND ROI still >0 ex-largest."""
    r = record(conn, "bms", key, date, surface)
    if r["starts"] < BMS_FLOOR or r["roi"] <= 0:
        return False
    staked = STAKE * r["starts"]
    ex = (staked * (1 + r["roi"]) - r["largest"] - (staked - STAKE)) / (staked - STAKE) \
        if r["starts"] > 1 else -1
    return ex > 0                          # ex-largest-payout robustness gate


def _top(kind, n=15):
    conn = init_db()
    rows = conn.execute(
        "SELECT key, COUNT(*) s, SUM(won) w, SUM(ret) r FROM perf_event "
        "WHERE kind=? GROUP BY key HAVING s>=? ORDER BY (SUM(ret)-2.0*COUNT(*)) DESC LIMIT ?",
        (kind, TJ_FLOOR if kind != "bms" else BMS_FLOOR, n)).fetchall()
    print(f"top {kind} by net (n≥floor):")
    for key, s, w, r in rows:
        print(f"   {key:<24} n={s:<4} w={w:<3} win%={100*w/s:4.0f} roi={(r-2*s)/(2*s):+.2f}")
    conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--seed" in args:
        seed_from_history()
    elif "--top" in args:
        _top(args[args.index("--top") + 1] if len(args) > args.index("--top") + 1 else "trainer")
    else:
        print(__doc__)
