#!/usr/bin/env python3
"""
Settlement regression tests for the results pipeline (r5_payoffs, r5_tracker).

Deterministic, stdlib-only (unittest + in-memory/tmp sqlite) — no fixtures on
disk, no network, never touches Results/r5_results.db.

Run:  python3 -m unittest discover tests
"""

import contextlib
import io
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Claude"))

import r5_payoffs
import r5_tracker


# ── parse_scratches ───────────────────────────────────────────────────────────

class TestParseScratches(unittest.TestCase):
    def test_comma_separated_with_parentheticals(self):
        # real SAR 20260712 R9 line: PP parentheticals with superscript glyphs
        block = ("Scratched- True Adirondacker(01Jan26\xadAqu\xad), "
                 "Thirsted(11Jun26\xabDel\xac), Down the Field, "
                 "Speightful Storm(26Jun26\xabBaq\xaa)\n"
                 "$1 Daily Double (6-7) Paid $106.35")
        self.assertEqual(
            r5_payoffs.parse_scratches(block),
            ["True Adirondacker", "Thirsted", "Down the Field",
             "Speightful Storm"])

    def test_wrapped_line_rejoins_split_name(self):
        # 'Little Finch' wraps across the line break — must not emit 'Finch'
        block = ("Scratched- Athena's Fury(16May26\xafBaq\xaa), Little\n"
                 " Finch(08May26\xafBaq\xad)\n"
                 "$1 Daily Double (4-2) Paid $56.11")
        self.assertEqual(r5_payoffs.parse_scratches(block),
                         ["Athena's Fury", "Little Finch"])

    def test_stops_at_pool_line(self):
        block = ("Scratched- Showa\n"
                 "$1 Pick 3 (2-4-2) Paid $361.00; Pick 3 Pool $82,230.")
        self.assertEqual(r5_payoffs.parse_scratches(block), ["Showa"])

    def test_semicolon_separator_still_works(self):
        block = "Scratched- First Horse; Second Horse\nTrainers- x"
        self.assertEqual(r5_payoffs.parse_scratches(block),
                         ["First Horse", "Second Horse"])

    def test_no_scratch_section(self):
        self.assertEqual(r5_payoffs.parse_scratches("no scratches here"), [])


# ── reconcile_picks ───────────────────────────────────────────────────────────

def _picks_conn(picks):
    """In-memory DB with just the columns reconcile_picks touches."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE picks (race_id INT, pgm TEXT,
                    horse_name TEXT, finish_pos INT, won INT DEFAULT 0,
                    sp_odds REAL)""")
    conn.execute("""CREATE TABLE races (id INT PRIMARY KEY,
                    result_fetched INT DEFAULT 0)""")
    conn.execute("INSERT INTO races (id) VALUES (1)")
    for pgm, name in picks:
        conn.execute(
            "INSERT INTO picks (race_id, pgm, horse_name) VALUES (1,?,?)",
            (pgm, name))
    return conn


def _pick_rows(conn):
    return {r["pgm"]: (r["finish_pos"], r["won"], r["sp_odds"])
            for r in conn.execute(
                "SELECT pgm, finish_pos, won, sp_odds FROM picks")}


def _norm_map(conn):
    return {r5_payoffs._norm_name(r["horse_name"]): r["pgm"]
            for r in conn.execute("SELECT horse_name, pgm FROM picks")}


class TestReconcilePicks(unittest.TestCase):
    def test_clean_card(self):
        conn = _picks_conn([("1", "ALPHA"), ("2", "BRAVO"), ("3", "CHARLIE"),
                            ("4", "DELTA")])
        finishers = [{"pgm": "2", "name": "Bravo", "odds": 3.5},
                     {"pgm": "1", "name": "Alpha", "odds": 2.0},
                     {"pgm": "3", "name": "Charlie", "odds": 9.0}]
        wps = [{"pool": "WIN", "pgm": "2", "payoff": 9.0, "denom": 2.0}]
        unacc = r5_payoffs.reconcile_picks(
            conn, 1, finishers, ["Delta"], wps, _norm_map(conn))
        self.assertEqual(unacc, 0)
        self.assertEqual(_pick_rows(conn), {
            "2": (1, 1, 9.0), "1": (2, 0, None), "3": (3, 0, None),
            "4": (-1, 0, None)})

    def test_unaccounted_pick_stays_null(self):
        conn = _picks_conn([("1", "ALPHA"), ("2", "BRAVO")])
        finishers = [{"pgm": "1", "name": "Alpha", "odds": 2.0}]
        wps = [{"pool": "WIN", "pgm": "1", "payoff": 6.0, "denom": 2.0}]
        unacc = r5_payoffs.reconcile_picks(
            conn, 1, finishers, [], wps, _norm_map(conn))
        self.assertEqual(unacc, 1)
        self.assertEqual(_pick_rows(conn)["2"], (None, 0, None))

    def test_dead_heat_settles_both_cowinners(self):
        conn = _picks_conn([("5", "ECHO"), ("7", "FOXTROT"), ("2", "GOLF")])
        finishers = [{"pgm": "5", "name": "Echo", "odds": 2.0},
                     {"pgm": "7", "name": "Foxtrot", "odds": 4.0},
                     {"pgm": "2", "name": "Golf", "odds": 8.0}]
        wps = [{"pool": "WIN", "pgm": "5", "payoff": 3.1, "denom": 2.0},
               {"pool": "WIN", "pgm": "7", "payoff": 5.4, "denom": 2.0}]
        r5_payoffs.reconcile_picks(conn, 1, finishers, [], wps,
                                   _norm_map(conn))
        rows = _pick_rows(conn)
        self.assertEqual(rows["5"], (1, 1, 3.1))
        self.assertEqual(rows["7"], (1, 1, 5.4))   # co-winner, own payoff
        self.assertEqual(rows["2"], (3, 0, None))  # officially 3rd

    def test_coupled_mate_does_not_overwrite_entry_win(self):
        # entry logged as base '1'; 1A wins, 1 finishes last — the later
        # UPDATE for the mate must not clobber the entry's win
        conn = _picks_conn([("1", "HOTEL"), ("2", "INDIA")])
        finishers = [{"pgm": "1A", "name": "Hotel Two", "odds": 2.0},
                     {"pgm": "2", "name": "India", "odds": 3.0},
                     {"pgm": "1", "name": "Hotel", "odds": 2.0}]
        wps = [{"pool": "WIN", "pgm": "1", "payoff": 6.0, "denom": 2.0}]
        r5_payoffs.reconcile_picks(conn, 1, finishers, [], wps,
                                   _norm_map(conn))
        rows = _pick_rows(conn)
        self.assertEqual(rows["1"], (1, 1, 6.0))
        self.assertEqual(rows["2"], (2, 0, None))

    def test_coupled_mate_after_base_winner(self):
        # base '1' wins, mate 1A finishes 3rd of 3 — win must survive
        conn = _picks_conn([("1", "HOTEL"), ("2", "INDIA")])
        finishers = [{"pgm": "1", "name": "Hotel", "odds": 2.0},
                     {"pgm": "2", "name": "India", "odds": 3.0},
                     {"pgm": "1A", "name": "Hotel Two", "odds": 2.0}]
        wps = [{"pool": "WIN", "pgm": "1", "payoff": 6.0, "denom": 2.0}]
        r5_payoffs.reconcile_picks(conn, 1, finishers, [], wps,
                                   _norm_map(conn))
        self.assertEqual(_pick_rows(conn)["1"], (1, 1, 6.0))

    def test_coupled_mate_does_not_become_second_winner(self):
        # picks logged separately as 1 and 1A; interest 1 wins via runner 1;
        # runner 1A finishing 4th must NOT match the entry's WIN row
        conn = _picks_conn([("1", "HOTEL"), ("1A", "HOTEL TWO"),
                            ("2", "INDIA"), ("3", "JULIET")])
        finishers = [{"pgm": "1", "name": "Hotel", "odds": 2.0},
                     {"pgm": "2", "name": "India", "odds": 3.0},
                     {"pgm": "3", "name": "Juliet", "odds": 5.0},
                     {"pgm": "1A", "name": "Hotel Two", "odds": 2.0}]
        wps = [{"pool": "WIN", "pgm": "1", "payoff": 6.0, "denom": 2.0}]
        r5_payoffs.reconcile_picks(conn, 1, finishers, [], wps,
                                   _norm_map(conn))
        rows = _pick_rows(conn)
        self.assertEqual(rows["1"], (1, 1, 6.0))
        self.assertEqual(rows["1A"], (4, 0, None))

    def test_no_win_payoff_row_still_marks_winner(self):
        conn = _picks_conn([("1", "ALPHA"), ("2", "BRAVO")])
        finishers = [{"pgm": "2", "name": "Bravo", "odds": 3.5},
                     {"pgm": "1", "name": "Alpha", "odds": 2.0}]
        r5_payoffs.reconcile_picks(conn, 1, finishers, [], [],
                                   _norm_map(conn))
        rows = _pick_rows(conn)
        self.assertEqual(rows["2"], (1, 1, None))
        self.assertEqual(rows["1"], (2, 0, None))

    def test_reingest_is_idempotent(self):
        conn = _picks_conn([("1", "ALPHA"), ("2", "BRAVO"), ("3", "CHARLIE")])
        finishers = [{"pgm": "2", "name": "Bravo", "odds": 3.5},
                     {"pgm": "1", "name": "Alpha", "odds": 2.0}]
        wps = [{"pool": "WIN", "pgm": "2", "payoff": 9.0, "denom": 2.0}]
        args = (conn, 1, finishers, ["Charlie"], wps, _norm_map(conn))
        r5_payoffs.reconcile_picks(*args)
        first = _pick_rows(conn)
        r5_payoffs.reconcile_picks(*args)
        self.assertEqual(_pick_rows(conn), first)


# ── finalize_card cross-check ─────────────────────────────────────────────────

class TestFinalizeCard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = r5_tracker.DB_PATH
        r5_tracker.DB_PATH = Path(self._tmp.name)
        conn = r5_tracker.init_db()
        r5_payoffs.init_schema(conn)   # race_finish_order / race_payoffs
        conn.close()

    def tearDown(self):
        r5_tracker.DB_PATH = self._orig_db
        Path(self._tmp.name).unlink(missing_ok=True)

    def _conn(self):
        conn = sqlite3.connect(self._tmp.name)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed_race(self, conn, picks, chart_rows=(), rn="1"):
        cur = conn.execute(
            "INSERT INTO races (track, date, race_num, result_fetched)"
            " VALUES ('SAR','20260101',?,1)", (rn,))
        rid = cur.lastrowid
        for pgm, name, pos in picks:
            conn.execute(
                "INSERT INTO picks (race_id, pgm, horse_name, finish_pos)"
                " VALUES (?,?,?,?)", (rid, pgm, name, pos))
        for pgm, name, pos, scr in chart_rows:
            conn.execute(
                "INSERT INTO race_finish_order (race_id, horse_pgm,"
                " horse_name, finish_position, is_late_scratch)"
                " VALUES (?,?,?,?,?)", (rid, pgm, name, pos, scr))
        conn.commit()
        return rid

    def _finalize(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            r5_tracker.finalize_card("SAR", "20260101")
        return out.getvalue()

    def _pos(self, conn, rid, pgm):
        return conn.execute(
            "SELECT finish_pos FROM picks WHERE race_id=? AND pgm=?",
            (rid, pgm)).fetchone()[0]

    def test_null_runner_healed_from_chart(self):
        conn = self._conn()
        rid = self._seed_race(
            conn,
            picks=[("1", "ALPHA", 1), ("2", "BRAVO", None)],
            chart_rows=[("1", "Alpha", 1, 0), ("2", "Bravo", 3, 0)])
        out = self._finalize()
        self.assertEqual(self._pos(self._conn(), rid, "2"), 3)
        self.assertIn("backfilled", out)

    def test_confirmed_chart_scratch_marked(self):
        conn = self._conn()
        rid = self._seed_race(
            conn,
            picks=[("1", "ALPHA", 1), ("2", "BRAVO", None)],
            chart_rows=[("1", "Alpha", 1, 0), ("2", "Bravo", None, 1)])
        self._finalize()
        self.assertEqual(self._pos(self._conn(), rid, "2"), -1)

    def test_ambiguous_pick_left_null(self):
        # chart rows exist but the NULL pick is in neither list
        conn = self._conn()
        rid = self._seed_race(
            conn,
            picks=[("1", "ALPHA", 1), ("2", "BRAVO", None)],
            chart_rows=[("1", "Alpha", 1, 0)])
        out = self._finalize()
        self.assertIsNone(self._pos(self._conn(), rid, "2"))
        self.assertIn("operator review", out)

    def test_legacy_card_without_chart_marks_scratch(self):
        conn = self._conn()
        rid = self._seed_race(
            conn, picks=[("1", "ALPHA", 1), ("2", "BRAVO", None)])
        self._finalize()
        self.assertEqual(self._pos(self._conn(), rid, "2"), -1)

    def test_more_than_three_nulls_aborts(self):
        conn = self._conn()
        rid = self._seed_race(
            conn,
            picks=[("1", "A", None), ("2", "B", None), ("3", "C", None),
                   ("4", "D", None), ("5", "E", 1)])
        out = self._finalize()
        c = self._conn()
        for pgm in "1234":
            self.assertIsNone(self._pos(c, rid, pgm))
        self.assertIn("Aborting", out)


if __name__ == "__main__":
    unittest.main()
