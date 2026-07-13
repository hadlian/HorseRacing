#!/usr/bin/env python3
"""
r5_tracker.py — R5 Results Tracker
Logs R5 picks to SQLite and records actual race results.

Usage:
    python3 r5_tracker.py --status                          # pending races
    python3 r5_tracker.py --fetch CD 20260502               # auto-fetch from Equibase/HRN
    python3 r5_tracker.py --fetch CD 20260502 --race 12     # specific race
    python3 r5_tracker.py --manual CD 20260502 12 "15,6,14,1" 18.40
    python3 r5_tracker.py --csv results/results.csv         # bulk load from CSV
    python3 r5_tracker.py --finalize CD 20260514            # mark NULLs as late scratches (run after full logging)

CSV format for --csv:
    track,date,race,finish,sp_winner
    DBY,20260502,12,"15,6,14,1",18.40
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
from r5_paths import R5_DB_PATH as DB_PATH

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

TRACK_NAMES_HRN = {
    "CD":  "Churchill_Downs", "DBY": "Churchill_Downs",
    "KEE": "Keeneland",       "SAR": "Saratoga",
    "AQU": "Aqueduct",        "BEL": "Belmont_Park",
    "DMR": "Del_Mar",         "GP":  "Gulfstream_Park",
    "OP":  "Oaklawn_Park",    "PIM": "Pimlico",
    "MTH": "Monmouth_Park",   "LRL": "Laurel_Park",
    "SAX": "Santa_Anita_Park",
}


# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.execute("ALTER TABLE races ADD COLUMN is_backtest INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS races (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            track          TEXT NOT NULL,
            date           TEXT NOT NULL,
            race_num       TEXT NOT NULL,
            surface        TEXT,
            dist_f         REAL,
            race_type      TEXT,
            purse          REAL,
            pace_scenario  TEXT,
            speed_count    INTEGER,
            logged_at      TEXT DEFAULT (datetime('now')),
            result_fetched INTEGER DEFAULT 0,
            is_backtest    INTEGER DEFAULT 0,
            UNIQUE(track, date, race_num)
        );

        CREATE TABLE IF NOT EXISTS picks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     INTEGER REFERENCES races(id) ON DELETE CASCADE,
            pgm         TEXT,
            horse_name  TEXT,
            ml_odds     REAL,
            sp_odds     REAL,
            model_rank  INTEGER,
            comp        REAL,
            tier        TEXT,
            fci_n       REAL,
            class_n     REAL,
            bias_n      REAL,
            tj_n        REAL,
            form_n      REAL,
            ped_n       REAL,
            val_n       REAL,
            pace_style  TEXT,
            pace_fit    REAL,
            scout_adj   REAL DEFAULT 0,
            prime_power  REAL,
            best_dist    REAL,
            best_dist_n  REAL,
            pp_n         REAL,
            finish_pos   INTEGER,
            won          INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS rank3_tracker (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_id    INTEGER UNIQUE NOT NULL REFERENCES picks(id),
            bet_size   REAL DEFAULT 2.0,
            result     INTEGER,
            sp_odds    REAL,
            payoff     REAL,
            profit     REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn


# ── LOGGING (called from run_r5.py) ──────────────────────────────────────────

def log_race_picks(horses, track, date, race_num, is_backtest=False):
    """
    Save R5 pick set for one race to the database.
    horses: finalized, scout-adjusted, scratch-removed list for this race.
    """
    if not horses:
        return

    conn = init_db()

    h0          = horses[0]
    speed_count = sum(1 for h in horses if h.get("pace_style") == "speed")
    if   speed_count >= 5: pace_scenario = "HOT"
    elif speed_count <= 1: pace_scenario = "SLOW"
    else:                  pace_scenario = "NORMAL"

    dist_f = round(h0.get("dist_y", 0) / 220, 1) if h0.get("dist_y") else None

    cur = conn.execute("""
        INSERT INTO races (track, date, race_num, surface, dist_f,
                           race_type, purse, pace_scenario, speed_count, is_backtest)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(track,date,race_num) DO UPDATE SET
            surface=excluded.surface, dist_f=excluded.dist_f,
            race_type=excluded.race_type, purse=excluded.purse,
            pace_scenario=excluded.pace_scenario, speed_count=excluded.speed_count,
            logged_at=datetime('now'), result_fetched=0,
            is_backtest=excluded.is_backtest
    """, (track, date, str(race_num),
          h0.get("surface"), dist_f, h0.get("race_type"),
          h0.get("purse"), pace_scenario, speed_count, 1 if is_backtest else 0))

    race_id = cur.lastrowid or conn.execute(
        "SELECT id FROM races WHERE track=? AND date=? AND race_num=?",
        (track, date, str(race_num))
    ).fetchone()[0]

    conn.execute("DELETE FROM picks WHERE race_id=?", (race_id,))

    cols = {r[1] for r in conn.execute("PRAGMA table_info(picks)")}
    for col, ddl in (("comp_ex_val", "REAL"), ("pre_tight_comp", "REAL"),
                     ("tight_cluster_severe", "INTEGER DEFAULT 0"),
                     # Session 3A display fields (never scored)
                     ("days_since_last", "INTEGER"),
                     ("bris_run_style", "TEXT"),
                     ("quirin_pts", "INTEGER"),
                     ("wet_starts", "INTEGER"),
                     ("wet_wins", "INTEGER"),
                     ("wet_off_speed", "INTEGER"),
                     ("trnr_stats", "TEXT")):
        if col not in cols:
            conn.execute(f"ALTER TABLE picks ADD COLUMN {col} {ddl}")

    ranked = sorted(horses, key=lambda h: h["comp"], reverse=True)
    for rank, h in enumerate(ranked, 1):
        conn.execute("""
            INSERT INTO picks
            (race_id, pgm, horse_name, ml_odds, model_rank, comp, tier,
             fci_n, class_n, bias_n, tj_n, form_n, ped_n, val_n,
             pace_style, pace_fit, scout_adj, prime_power, best_dist,
             best_dist_n, pp_n, comp_ex_val, pre_tight_comp, tight_cluster_severe,
             days_since_last, bris_run_style, quirin_pts,
             wet_starts, wet_wins, wet_off_speed, trnr_stats)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (race_id, h.get("pgm"), h.get("name"), h.get("ml_odds"),
              rank, h.get("comp"), h.get("tier"),
              h.get("fci_n"), h.get("class_n"), h.get("bias_n"),
              h.get("tj_n"), h.get("form_n"), h.get("ped_n"), h.get("val_n"),
              h.get("pace_style", "unknown"), h.get("pace_fit", 5.0),
              h.get("scout_adj", 0.0),
              h.get("prime_power"), h.get("best_dist"),
              h.get("best_dist_n"), h.get("pp_n"),
              h.get("comp_ex_val"),
              h.get("pre_tight_comp", h.get("comp")),
              1 if h.get("tight_cluster_severe") else 0,
              h.get("days_since_last"), h.get("bris_run_style"),
              h.get("quirin_pts"), h.get("wet_starts"), h.get("wet_wins"),
              int(h["best_off"]) if h.get("best_off") else None,
              json.dumps(h.get("trnr_stats")) if h.get("trnr_stats") else None))

    # Auto-log rank-3 paper bet ($2 flat)
    r3 = conn.execute(
        "SELECT id FROM picks WHERE race_id=? AND model_rank=3", (race_id,)
    ).fetchone()
    if r3 and not is_backtest:
        conn.execute(
            "INSERT OR IGNORE INTO rank3_tracker (pick_id) VALUES (?)", (r3[0],)
        )

    conn.commit()
    conn.close()
    print(f"  📋 Logged {len(ranked)} picks → {track} {date} Race {race_num} [{pace_scenario} PACE]")


def settle_rank3_bets():
    """Settle pending rank3_tracker rows from pick results."""
    conn = init_db()
    n = 0
    for row in conn.execute("""
        SELECT rt.id, p.won, p.sp_odds, p.finish_pos
        FROM rank3_tracker rt JOIN picks p ON p.id = rt.pick_id
        WHERE rt.result IS NULL AND p.finish_pos IS NOT NULL
    """).fetchall():
        if row["finish_pos"] == -1:
            continue
        won    = 1 if row["won"] else 0
        sp     = row["sp_odds"]
        payoff = sp if (won and sp) else None
        profit = (sp - 2.0) if (won and sp) else (-2.0)  # sp_odds = mutuel payout per $2
        conn.execute(
            "UPDATE rank3_tracker SET result=?, sp_odds=?, payoff=?, profit=? WHERE id=?",
            (won, sp, payoff, profit, row["id"]))
        n += 1
    conn.commit()
    conn.close()
    return n


def rank3_status():
    """Print rank3_tracker summary."""
    conn = init_db()
    row = conn.execute("""
        SELECT COUNT(*) n, COALESCE(SUM(result),0) wins,
               COALESCE(SUM(profit),0) profit
        FROM rank3_tracker WHERE result IS NOT NULL
    """).fetchone()
    total = conn.execute("SELECT COUNT(*) FROM rank3_tracker").fetchone()[0]
    conn.close()
    settled, wins, profit = row["n"], row["wins"], row["profit"]
    roi = profit / (settled * 2) * 100 if settled else 0
    print(f"rank3_tracker: {total} logged | settled {settled} | wins {wins} | "
          f"profit ${profit:.2f} | ROI {roi:.1f}%")


# ── RESULT FETCHING ───────────────────────────────────────────────────────────

def fetch_equibase(track, date_str, race_num=None):
    """Try Equibase results chart. Returns {pos: {pgm, horse, sp}} or None."""
    try:
        d        = datetime.strptime(date_str, "%Y%m%d")
        date_fmt = d.strftime("%m/%d/%Y")

        # Try several known Equibase URL patterns
        urls = [
            (f"https://www.equibase.com/premium/chartEmbed.cfm"
             f"?track={track}&raceDate={date_fmt}&country=USA&hosted=false"
             + (f"&race={race_num}" if race_num else "")),
            (f"https://www.equibase.com/static/chart/summary/"
             f"{track}{d.strftime('%m%d%Y')}.html"),
        ]

        for url in urls:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            results = _parse_equibase_table(soup)
            if results:
                return results
        return None
    except Exception as e:
        print(f"  Equibase fetch error: {e}")
        return None


def _parse_equibase_table(soup):
    results = {}
    for table in soup.select("table"):
        rows = table.select("tr")
        if len(rows) < 3:
            continue
        for row in rows[1:]:
            cells = row.select("td")
            if len(cells) < 3:
                continue
            try:
                pos   = int(cells[0].get_text(strip=True))
                pgm   = cells[1].get_text(strip=True)
                horse = cells[2].get_text(strip=True)
                sp    = None
                # look for odds in later cells
                for cell in cells[3:]:
                    txt = cell.get_text(strip=True).replace("$", "")
                    try:
                        sp = float(txt)
                        break
                    except:
                        pass
                results[pos] = {"pgm": pgm, "horse": horse, "sp": sp}
            except:
                continue
        if results:
            return results
    return None


def fetch_hrn(track, date_str, race_num=None):
    """Try Horse Racing Nation results. Returns {pos: {pgm, horse}} or None."""
    try:
        track_name = TRACK_NAMES_HRN.get(track.upper(), track)
        d          = datetime.strptime(date_str, "%Y%m%d")
        url        = (f"https://www.horseracingnation.com/results/"
                      f"{track_name}/{d.year}/{d.month:02d}/{d.day:02d}")

        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None

        soup    = BeautifulSoup(r.text, "html.parser")
        results = {}

        # HRN results are in race sections — find by race number
        race_sections = soup.select(".race-result, .result-race, section")
        for section in race_sections:
            header = section.select_one("h2, h3, .race-header")
            if race_num and header:
                if str(race_num) not in header.get_text():
                    continue
            rows = section.select("tr")
            for row in rows[1:]:
                cells = row.select("td")
                if len(cells) >= 2:
                    try:
                        pos   = int(cells[0].get_text(strip=True))
                        horse = cells[1].get_text(strip=True)
                        results[pos] = {"pgm": "?", "horse": horse, "sp": None}
                    except:
                        continue
            if results:
                return results
        return None
    except Exception as e:
        print(f"  HRN fetch error: {e}")
        return None


def auto_fetch_results(track, date_str, race_num=None):
    """Try all sources. Returns result dict or None."""
    print(f"  → Trying Equibase...", end=" ", flush=True)
    results = fetch_equibase(track, date_str, race_num)
    if results:
        print(f"found {len(results)} finishers")
        return results
    print("no data")

    print(f"  → Trying HRN...", end=" ", flush=True)
    results = fetch_hrn(track, date_str, race_num)
    if results:
        print(f"found {len(results)} finishers")
        return results
    print("no data")

    return None


# ── RESULT ENTRY ──────────────────────────────────────────────────────────────

def apply_result(track, date_str, race_num, finish_pgms, sp_winner=None):
    """
    Write finish positions to DB.
    finish_pgms: list of program numbers in finish order ["15","6","14","1"]
    """
    conn = init_db()
    row = conn.execute(
        "SELECT id FROM races WHERE track=? AND date=? AND race_num=?",
        (track, date_str, str(race_num))
    ).fetchone()

    if not row:
        print(f"  ⚠️  No logged picks for {track} {date_str} R{race_num}")
        print(f"      Run: python3 run_r5.py <file.DRF> --track  to log first")
        conn.close()
        return False

    race_id = row["id"]

    # Clear previous results
    conn.execute("UPDATE picks SET finish_pos=NULL, won=0, sp_odds=NULL WHERE race_id=?",
                 (race_id,))

    for pos, pgm in enumerate(finish_pgms, 1):
        pgm = pgm.strip()
        conn.execute(
            "UPDATE picks SET finish_pos=?, won=? WHERE race_id=? AND pgm=?",
            (pos, 1 if pos == 1 else 0, race_id, pgm)
        )
        if pos == 1 and sp_winner:
            conn.execute(
                "UPDATE picks SET sp_odds=? WHERE race_id=? AND pgm=?",
                (sp_winner, race_id, pgm)
            )

    # Any pick still NULL after the top-4 loop = ran but finished outside the
    # recorded positions.  Mark as finish_pos=5 so they count as losses in
    # stats (not excluded like confirmed scratches).
    # True late scratches (horse never left the gate) should be handled by the
    # scout scratch gate before logging, or corrected via --finalize afterwards.
    unplaced = conn.execute(
        "SELECT pgm, horse_name FROM picks WHERE race_id=? AND finish_pos IS NULL",
        (race_id,)
    ).fetchall()
    if unplaced:
        pgms = [u["pgm"] for u in unplaced]
        conn.execute(
            f"UPDATE picks SET finish_pos=5 WHERE race_id=? AND pgm IN ({','.join('?'*len(pgms))})",
            [race_id] + pgms
        )

    conn.execute("UPDATE races SET result_fetched=1 WHERE id=?", (race_id,))
    conn.commit()

    top = finish_pgms[0] if finish_pgms else "?"
    sec = finish_pgms[1] if len(finish_pgms) > 1 else "?"
    trd = finish_pgms[2] if len(finish_pgms) > 2 else "?"
    sp_str = f"  SP: {sp_winner:.2f}" if sp_winner else ""
    print(f"  ✅ {track} {date_str} R{race_num} — 1st:#{top}  2nd:#{sec}  3rd:#{trd}{sp_str}")
    conn.close()
    return True


def _norm_name(s):
    """Uppercase letters only — chart and DRF names differ in case, spacing,
    and punctuation (mirrors r5_payoffs._norm_name)."""
    return re.sub(r"[^A-Z]", "", s.upper())


def finalize_card(track, date_str):
    """
    Post-result cleanup for cards logged via direct SQL.
    Detects any picks still NULL and resolves each against the chart ingest
    (race_finish_order) when available: a pick the chart shows as a FINISHER
    is backfilled (parse gap, not a scratch); a confirmed chart scratch — or
    any NULL on a card with no chart rows — is marked finish_pos=-1 so it is
    excluded from model stats; a pick in neither list is left NULL for
    operator review (marking a real starter -1 would silently bias stats).

    IMPORTANT: Only run this after ALL finishers have been logged for every race.
    If a race shows many NULLs (>3), it likely means the card was not fully
    logged — running finalize on partially-logged cards will incorrectly mark
    valid runners as late scratches.
    """
    conn = init_db()
    races = conn.execute(
        "SELECT id, race_num FROM races WHERE track=? AND date=? AND result_fetched=1"
        " ORDER BY CAST(race_num AS INT)",
        (track.upper(), date_str)
    ).fetchall()

    if not races:
        print(f"  ⚠️  No result_fetched races found for {track} {date_str}")
        conn.close()
        return

    # Preview pass — check for suspicious NULL counts before committing
    suspicious = []
    for race in races:
        null_count = conn.execute(
            "SELECT COUNT(*) FROM picks WHERE race_id=? AND finish_pos IS NULL",
            (race["id"],)
        ).fetchone()[0]
        if null_count > 3:
            suspicious.append((race["race_num"], null_count))

    if suspicious:
        print(f"\n  ⚠️  WARNING: Some races have many NULL finish positions.")
        print(f"     This usually means the card was NOT fully logged (partial logging).")
        for rnum, cnt in suspicious:
            print(f"     R{rnum}: {cnt} NULL positions — looks like partial logging, not late scratches")
        print(f"\n  Aborting. Log all finish positions first, then re-run --finalize.")
        conn.close()
        return

    total_late, total_healed, total_ambiguous = 0, 0, 0
    for race in races:
        late = conn.execute(
            "SELECT pgm, horse_name FROM picks WHERE race_id=? AND finish_pos IS NULL",
            (race["id"],)
        ).fetchall()
        if not late:
            continue

        # Cross-check against the chart ingest (race_finish_order) before
        # assuming 'late scratch': a NULL pick can also be a runner the
        # reconcile step missed (pgm/name mismatch), and marking a real
        # starter -1 silently drops it from model stats and ROI.
        chart = conn.execute(
            "SELECT horse_pgm, horse_name, finish_position, is_late_scratch"
            " FROM race_finish_order WHERE race_id=?", (race["id"],)
        ).fetchall()
        finished, scratched = {}, set()
        for row in chart:
            for key in (str(row["horse_pgm"]), _norm_name(row["horse_name"])):
                if row["is_late_scratch"]:
                    scratched.add(key)
                elif row["finish_position"] is not None:
                    finished[key] = row["finish_position"]

        for ls in late:
            keys = [str(ls["pgm"]), _norm_name(ls["horse_name"])]
            hit = next((k for k in keys if k in finished), None)
            if hit is not None:
                # chart says it RAN — heal from the finish order, don't exclude
                pos = finished[hit]
                conn.execute(
                    "UPDATE picks SET finish_pos=?, won=? WHERE race_id=? AND pgm=?",
                    (pos, 1 if pos == 1 else 0, race["id"], ls["pgm"]))
                if pos == 1:
                    try:
                        wp = conn.execute(
                            "SELECT payoff FROM race_payoffs WHERE race_id=?"
                            " AND pool='WIN' AND combination IN (?,?)",
                            (race["id"], str(ls["pgm"]),
                             re.sub(r"[A-Z]$", "", str(ls["pgm"])))).fetchone()
                        if wp:
                            conn.execute(
                                "UPDATE picks SET sp_odds=? WHERE race_id=? AND pgm=?",
                                (wp["payoff"], race["id"], ls["pgm"]))
                    except sqlite3.OperationalError:
                        pass  # DB predates race_payoffs table
                print(f"  🔧 R{race['race_num']}: #{ls['pgm']} {ls['horse_name']}"
                      f" was NULL but the chart shows it finished {pos} —"
                      f" backfilled from race_finish_order (parse gap)")
                total_healed += 1
            elif not chart or any(k in scratched for k in keys):
                # confirmed chart scratch, or a card logged without chart
                # ingest (no race_finish_order rows — legacy manual path)
                conn.execute(
                    "UPDATE picks SET finish_pos=-1 WHERE race_id=? AND pgm=?",
                    (race["id"], ls["pgm"]))
                print(f"  ⚠️  R{race['race_num']}: Late scratch → "
                      f"#{ls['pgm']} {ls['horse_name']}")
                total_late += 1
            else:
                # chart data exists but this pick is in neither the finish
                # order nor the scratches — operator must decide, leave NULL
                print(f"  ❌ R{race['race_num']}: #{ls['pgm']} {ls['horse_name']}"
                      f" is in neither the chart finish order nor its scratches"
                      f" — left NULL. Verify against the chart PDF, then either"
                      f" set finish_pos manually or mark -1 if scratched.")
                total_ambiguous += 1

    conn.commit()
    conn.close()

    if total_late or total_healed:
        if total_late:
            print(f"\n  🔧 {total_late} late scratch(es) marked finish_pos=-1 — excluded from stats")
        if total_healed:
            print(f"  🔧 {total_healed} pick(s) backfilled from the chart finish order")
        print(f"  Regenerate workbook: python3 r5_analyze.py")
    elif not total_ambiguous:
        print(f"\n  ✅ {track} {date_str} — no NULL finish positions found. Card is clean.")
    if total_ambiguous:
        print(f"\n  ❌ {total_ambiguous} pick(s) left NULL — unresolvable against chart data, needs operator review")


def load_csv(csv_path):
    """Bulk load results from CSV file."""
    loaded = 0
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            finish = [p.strip() for p in row["finish"].split(",")]
            sp     = float(row.get("sp_winner") or 0) or None
            if apply_result(row["track"], row["date"], row["race"], finish, sp):
                loaded += 1

    # Safety net: ensure result_fetched=1 for any race where picks have
    # been given finish positions — catches direct-SQL updates that bypass
    # apply_result() and would otherwise be excluded from r5_analyze.py
    conn = init_db()
    fixed = conn.execute("""
        UPDATE races SET result_fetched=1
        WHERE id IN (
            SELECT DISTINCT race_id FROM picks
            WHERE finish_pos IS NOT NULL AND finish_pos != -1
        )
    """).rowcount
    conn.commit()
    conn.close()
    if fixed:
        print(f"  🔧 result_fetched flag set for {fixed} previously unlabelled race(s)")

    print(f"\n✅ Loaded {loaded} results from {csv_path}")


# ── STATUS ────────────────────────────────────────────────────────────────────

def show_status():
    conn = init_db()
    print("\n📊 R5 TRACKER STATUS")
    print("=" * 56)

    pending = conn.execute("""
        SELECT r.track, r.date, r.race_num, r.purse, r.pace_scenario,
               COUNT(p.id) as n
        FROM races r JOIN picks p ON p.race_id=r.id
        WHERE r.result_fetched=0 AND r.is_backtest=0
        GROUP BY r.id ORDER BY r.date DESC, CAST(r.race_num AS INT)
    """).fetchall()

    if pending:
        print(f"\n⏳ Pending results ({len(pending)} races):")
        for r in pending:
            print(f"  {r['track']:4} {r['date']}  R{r['race_num']:<3} "
                  f"${r['purse']:>10,.0f}  {r['pace_scenario']:6}  ({r['n']} horses)")
    else:
        print("\n  No pending results")

    done  = conn.execute("SELECT COUNT(*) FROM races WHERE result_fetched=1 AND is_backtest=0").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM races WHERE is_backtest=0").fetchone()[0]
    bt    = conn.execute("SELECT COUNT(*) FROM races WHERE is_backtest=1").fetchone()[0]
    print(f"\n✅ Completed: {done} / {total} live races logged" + (f"  ({bt} backtest excluded)" if bt else ""))

    if done >= 10:
        print(f"\n🟢 Ready for analysis — run: python3 r5_analyze.py")
    elif done > 0:
        print(f"\n⏳ {10-done} more results needed for meaningful analysis")

    conn.close()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="R5 Results Tracker")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--fetch", nargs=2, metavar=("TRACK","DATE"),
                        help="Auto-fetch results (e.g. CD 20260502)")
    parser.add_argument("--race", type=int, help="Race number for --fetch")
    parser.add_argument("--manual", nargs="+",
                        help="TRACK DATE RACE 'pgm1,pgm2,...' [SP_WINNER]")
    parser.add_argument("--csv", metavar="FILE",
                        help="Bulk load from CSV file")
    parser.add_argument("--finalize", nargs=2, metavar=("TRACK","DATE"),
                        help="Detect NULL finish positions and mark as late scratches (e.g. CD 20260514)")
    parser.add_argument("--backtest", action="store_true",
                        help="Tag logged races as backtest (is_backtest=1); excluded from analytics")
    args = parser.parse_args()

    if args.fetch:
        track, date = args.fetch
        print(f"\n🔍 Fetching {track} {date}" + (f" R{args.race}" if args.race else ""))
        results = auto_fetch_results(track, date, args.race)
        if results:
            pgms = [v["pgm"] for v in sorted(results.items())[:4]]
            print(f"\n  Top 4: {pgms}")
            sp   = results.get(1, {}).get("sp")
            apply_result(track, date, str(args.race or 1), pgms, sp)
        else:
            print("\n  ⚠️  Auto-fetch failed — use --manual:")
            print(f"  python3 r5_tracker.py --manual {track} {date} RACE '1st,2nd,3rd,4th' SP")

    elif args.manual:
        if len(args.manual) < 4:
            print("Usage: --manual TRACK DATE RACE 'pgm1,pgm2,...' [SP_WINNER]")
            sys.exit(1)
        track, date, race = args.manual[0], args.manual[1], args.manual[2]
        finish = [p.strip() for p in args.manual[3].split(",")]
        sp     = float(args.manual[4]) if len(args.manual) > 4 else None
        apply_result(track, date, race, finish, sp)

    elif args.csv:
        load_csv(args.csv)

    elif args.finalize:
        track, date = args.finalize
        print(f"\n🔍 Finalizing {track} {date} — checking for late scratches...")
        finalize_card(track, date)

    else:
        show_status()


if __name__ == "__main__":
    main()
