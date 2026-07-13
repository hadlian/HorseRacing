"""
CompareModels tracker — DB logging and result joining.
Writes to comparemodels/comparemodels_results.db (auto-created).
Reads r5_results.db READ-ONLY.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Claude'))
from r5_paths import R5_DB_PATH  # noqa: E402

CM_DB = os.path.join(os.path.dirname(__file__), 'comparemodels_results.db')
R5_DB = str(R5_DB_PATH)


def get_cm_conn():
    return sqlite3.connect(CM_DB)


def init_db():
    con = get_cm_conn()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS picks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        track           TEXT NOT NULL,
        race_date       TEXT NOT NULL,
        race            INTEGER NOT NULL,
        horse_pgm       TEXT NOT NULL,
        horse_name      TEXT NOT NULL,
        morning_line    REAL,
        cm_rank         INTEGER NOT NULL,
        composite_score INTEGER NOT NULL,
        tier            TEXT,
        consensus_count INTEGER,
        is_dominant     INTEGER DEFAULT 0,
        is_bris_pick    INTEGER DEFAULT 0,
        is_overlay      INTEGER DEFAULT 0,
        is_early_pace_leader INTEGER DEFAULT 0,
        is_late_pace_leader  INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(track, race_date, race, horse_pgm)
    );

    CREATE TABLE IF NOT EXISTS results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        track           TEXT NOT NULL,
        race_date       TEXT NOT NULL,
        race            INTEGER NOT NULL,
        horse_pgm       TEXT NOT NULL,
        finish_position INTEGER,
        sp_odds         REAL,
        source          TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(track, race_date, race, horse_pgm)
    );

    CREATE TABLE IF NOT EXISTS category_picks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        track           TEXT NOT NULL,
        race_date       TEXT NOT NULL,
        race            INTEGER NOT NULL,
        category        TEXT NOT NULL,
        rank_in_cat     INTEGER NOT NULL,
        horse_pgm       TEXT NOT NULL,
        horse_name      TEXT NOT NULL,
        raw_value       REAL,
        underlined      INTEGER DEFAULT 0,
        UNIQUE(track, race_date, race, category, rank_in_cat)
    );

    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    con.commit()
    con.close()


def log_card(score_dict: dict, track: str, race_date: str) -> tuple[int, int]:
    """
    Write category_picks then picks for an entire card.
    Returns (picks_written, cat_picks_written).
    """
    con = get_cm_conn()
    cur = con.cursor()

    picks_written = 0
    cat_picks_written = 0

    for race_num, race_result in score_dict.items():
        # 1) Write category_picks first
        for cat, cp_list in race_result['category_picks'].items():
            for cp in cp_list:
                cur.execute("""
                    INSERT OR REPLACE INTO category_picks
                    (track, race_date, race, category, rank_in_cat,
                     horse_pgm, horse_name, raw_value, underlined)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track, race_date, race_num, cat, cp['rank_in_cat'],
                    cp['pgm'], cp['name'], cp['raw_value'],
                    1 if cp['underlined'] else 0,
                ))
                cat_picks_written += 1

        # 2) Write picks
        for h in race_result['ranked_horses']:
            cur.execute("""
                INSERT OR REPLACE INTO picks
                (track, race_date, race, horse_pgm, horse_name,
                 morning_line, cm_rank, composite_score, tier,
                 consensus_count, is_dominant, is_bris_pick, is_overlay,
                 is_early_pace_leader, is_late_pace_leader)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track, race_date, race_num,
                h['pgm'], h['name'],
                None,  # morning_line pulled from CSV separately below
                h['rank'], h['composite'], h['tier'],
                h['consensus_count'],
                1 if h['is_dominant'] else 0,
                1 if h['is_bris_pick'] else 0,
                1 if h['is_overlay'] else 0,
                1 if h['is_early_pace_leader'] else 0,
                1 if h['is_late_pace_leader'] else 0,
            ))
            picks_written += 1

    con.commit()
    con.close()
    return picks_written, cat_picks_written


def log_card_with_ml(score_dict: dict, track: str, race_date: str,
                     ml_map: dict) -> tuple[int, int]:
    """
    Like log_card but also writes morning_line from ml_map = {(race, pgm): ml}.
    """
    con = get_cm_conn()
    cur = con.cursor()

    picks_written = 0
    cat_picks_written = 0

    for race_num, race_result in score_dict.items():
        # 1) Write category_picks first
        for cat, cp_list in race_result['category_picks'].items():
            for cp in cp_list:
                cur.execute("""
                    INSERT OR REPLACE INTO category_picks
                    (track, race_date, race, category, rank_in_cat,
                     horse_pgm, horse_name, raw_value, underlined)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track, race_date, race_num, cat, cp['rank_in_cat'],
                    cp['pgm'], cp['name'], cp['raw_value'],
                    1 if cp['underlined'] else 0,
                ))
                cat_picks_written += 1

        # 2) Write picks with ML
        for h in race_result['ranked_horses']:
            ml = ml_map.get((race_num, h['pgm']))
            cur.execute("""
                INSERT OR REPLACE INTO picks
                (track, race_date, race, horse_pgm, horse_name,
                 morning_line, cm_rank, composite_score, tier,
                 consensus_count, is_dominant, is_bris_pick, is_overlay,
                 is_early_pace_leader, is_late_pace_leader)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track, race_date, race_num,
                h['pgm'], h['name'],
                ml,
                h['rank'], h['composite'], h['tier'],
                h['consensus_count'],
                1 if h['is_dominant'] else 0,
                1 if h['is_bris_pick'] else 0,
                1 if h['is_overlay'] else 0,
                1 if h['is_early_pace_leader'] else 0,
                1 if h['is_late_pace_leader'] else 0,
            ))
            picks_written += 1

    con.commit()
    con.close()
    return picks_written, cat_picks_written


def pull_results(track: str, race_date: str) -> tuple[int, int]:
    """
    Join finish results from r5_results.db (read-only) into CM results table.
    Returns (matched, unmatched) pgm counts.
    """
    r5_con = sqlite3.connect(f"file:{os.path.abspath(R5_DB)}?mode=ro", uri=True)
    r5_cur = r5_con.cursor()

    cm_con = get_cm_conn()
    cm_cur = cm_con.cursor()

    # Get all races for this card from CM DB
    cm_cur.execute(
        "SELECT DISTINCT race FROM picks WHERE track=? AND race_date=?",
        (track, race_date)
    )
    races = [row[0] for row in cm_cur.fetchall()]

    matched = 0
    unmatched = 0

    for race_num in races:
        r5_cur.execute("""
            SELECT p.pgm, p.finish_pos, p.sp_odds, p.won, p.ml_odds
            FROM picks p
            JOIN races r ON p.race_id = r.id
            WHERE r.track = ? AND r.date = ? AND r.race_num = ?
        """, (track, race_date, str(race_num)))
        r5_rows = r5_cur.fetchall()
        r5_pgm_map = {row[0]: row for row in r5_rows}

        # Get CM horses for this race
        cm_cur.execute(
            "SELECT horse_pgm FROM picks WHERE track=? AND race_date=? AND race=?",
            (track, race_date, race_num)
        )
        cm_pgms = [row[0] for row in cm_cur.fetchall()]

        for pgm in cm_pgms:
            if pgm in r5_pgm_map:
                row = r5_pgm_map[pgm]
                cm_cur.execute("""
                    INSERT OR REPLACE INTO results
                    (track, race_date, race, horse_pgm, finish_position, sp_odds, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (track, race_date, race_num, pgm, row[1], row[2], 'r5_db_join'))
                matched += 1
            else:
                unmatched += 1

    cm_con.commit()
    r5_con.close()
    cm_con.close()
    return matched, unmatched


def finalize(track: str, race_date: str):
    """
    Mark late scratches: CM picks missing from R5 results get finish_position=-1.
    """
    cm_con = get_cm_conn()
    cm_cur = cm_con.cursor()

    cm_cur.execute(
        "SELECT DISTINCT race FROM picks WHERE track=? AND race_date=?",
        (track, race_date)
    )
    races = [row[0] for row in cm_cur.fetchall()]

    for race_num in races:
        cm_cur.execute(
            "SELECT horse_pgm FROM picks WHERE track=? AND race_date=? AND race=?",
            (track, race_date, race_num)
        )
        cm_pgms = {row[0] for row in cm_cur.fetchall()}

        cm_cur.execute(
            "SELECT horse_pgm FROM results WHERE track=? AND race_date=? AND race=?",
            (track, race_date, race_num)
        )
        result_pgms = {row[0] for row in cm_cur.fetchall()}

        for pgm in cm_pgms - result_pgms:
            cm_cur.execute("""
                INSERT OR REPLACE INTO results
                (track, race_date, race, horse_pgm, finish_position, source)
                VALUES (?, ?, ?, ?, -1, 'scratch')
            """, (track, race_date, race_num, pgm))

    cm_con.commit()
    cm_con.close()


def write_meta(kv: dict):
    con = get_cm_conn()
    cur = con.cursor()
    for k, v in kv.items():
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (k, v))
    con.commit()
    con.close()
