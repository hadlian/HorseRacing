#!/usr/bin/env python3
"""
r5_payoffs.py — Exotic payoff + finish-order ingestion from Equibase chart PDFs.

Session 2, Task 1. Populates race_payoffs and race_finish_order from the
full-card chart PDFs Harry downloads (e.g. Results/2026/20260529CDUSA0.pdf).
Equibase/HRN scraping is dead (Incapsula) — local PDF is the verified source
(Task 0). pdftotext -layout extraction; --txt accepts pre-extracted or pasted
chart text as the fallback path.

Usage:
    python3 Claude/r5_payoffs.py --track CDX --date 20260529              # full card, auto-find PDF
    python3 Claude/r5_payoffs.py --track CDX --date 20260529 --race 1
    python3 Claude/r5_payoffs.py --track SAR --date 20260703 --pdf path/to/chart.pdf
    python3 Claude/r5_payoffs.py --track SAR --date 20260703 --txt pasted_chart.txt

Conventions (SESSION2_BRIEF.md):
  - Idempotent: delete-then-insert per race. Re-running on the same race
    produces identical row counts.
  - Every payoff row carries its denomination. No naked payoffs.
  - finish_position is the chart's official order (charts print official
    order post-DQ). When a DQ is detected the race is flagged for manual
    across-the-wire review; official_position == finish_position as parsed.
  - Multi-race pools (DD, PK3): race_id = the ENDING leg.
  - Scratched horses: finish_position NULL, is_late_scratch=1.
  - Only races already logged in the races table are ingested (payoffs for
    unlogged races have no picks to settle against); skipped races reported.
"""

import argparse
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
from r5_paths import R5_DB_PATH as DB_PATH, CHART_DIRS

# Track code in our DB -> Equibase code used in chart PDF filenames
TRACK_TO_EQB = {
    "CDX": "CD", "DBY": "CD", "BAQ": "AQU", "LRL": "LRL",
    "SAX": "SA", "SAR": "SAR", "KEE": "KEE", "BEL": "BEL",
}

ORDINALS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
    "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14,
    "FIFTEENTH": 15, "SIXTEENTH": 16,
}

DENOMS = [
    (r"\$2(?:\.00)?",  2.0), (r"\$1(?:\.00)?", 1.0),
    (r"\$0?\.50",      0.5), (r"50\s*CENT",    0.5),
    (r"\$0?\.20",      0.2), (r"20\s*CENT",    0.2),
    (r"\$0?\.10",      0.1), (r"10\s*CENT",    0.1),
]

POOL_NAMES = {
    "EXACTA": "EX", "TRIFECTA": "TRI", "SUPERFECTA": "SUPER",
    "DAILY DOUBLE": "DD", "CONSOLATION DOUBLE": "DD",
    "PICK 3": "PK3", "PICK THREE": "PK3",
    "PICK 4": "PK4", "PICK 5": "PK5", "PICK 6": "PK6",
    "SUPER HIGH FIVE": "SH5", "HIGH FIVE": "SH5",
}

EXOTIC_RE = re.compile(
    r"(" + "|".join(d for d, _ in DENOMS) + r")\s+"
    r"(" + "|".join(re.escape(n) for n in POOL_NAMES) + r")\s*"
    r"\(([\dA-Z/\-]+)\)\s+(?:CORRECT\s+)?PAID\s+\$?([\d,]+\.\d{2})",
    re.IGNORECASE)

CARRYOVER_RE = re.compile(
    r"(" + "|".join(re.escape(n) for n in POOL_NAMES) + r")"
    r"[^\n$]*Carryover\s+(?:Pool\s+)?\$([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE)

# WPS rows always use a dotted leader: "3- OUTRAGEOUSLY . . . . 21.26 10.90 4.26"
# The winner's row can sit on the line ABOVE the "$2 Mutuel Prices:" marker,
# so the whole race block is scanned, not just lines after the marker.
# Dead-heated horses carry a marker glyph before the name (renders as ” or “)
WPS_RE = re.compile(
    r"^\s*(\d{1,2}[A-Z]?)\s*-\s+[”“\"*]?\s*([A-Z][A-Z'.\-() ]*?)\s*(?:\.\s*){2,}"
    r"((?:\d+\.\d{2}\s*){1,3})\s*$")


def _denom_value(text):
    for pat, val in DENOMS:
        if re.fullmatch(pat, text.strip(), re.IGNORECASE):
            return val
    return None


def _norm_name(s):
    """Uppercase letters only, for chart-vs-DRF horse-name matching (the two
    sources differ in case, spacing, and punctuation)."""
    return re.sub(r"[^A-Z]", "", s.upper())


# ── CHART TEXT PARSING ────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path):
    out = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    subprocess.run(["pdftotext", "-layout", str(pdf_path), out.name],
                   check=True, capture_output=True)
    return Path(out.name).read_text(errors="replace")


def split_races(text):
    """Split full-card chart text into per-race blocks keyed by race number."""
    blocks = {}
    starts = []
    for m in re.finditer(
            r"^\s*(" + "|".join(ORDINALS) + r")\s+RACE\b", text, re.MULTILINE):
        starts.append((m.start(), ORDINALS[m.group(1)]))
    for i, (pos, rnum) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        blocks[rnum] = text[pos:end]
    return blocks


def parse_finishers(block):
    """
    Parse the finish table. Rows are in official finish order.
    Returns list of {pgm, name, odds}. Uses the header line's column
    positions: name spans from '# Horse' col to 'M/Eqt.' col.
    """
    lines = block.splitlines()
    hdr_i = next((i for i, l in enumerate(lines)
                  if "Horse" in l and ("M/Eqt" in l or "Odds" in l)), None)
    if hdr_i is None:
        return []
    hdr      = lines[hdr_i]
    pgm_col  = hdr.index("#") if "#" in hdr else hdr.index("Horse") - 2
    name_end = hdr.index("M/Eqt") if "M/Eqt" in hdr else pgm_col + 40

    finishers = []
    for line in lines[hdr_i + 1:]:
        if re.search(r"OFF AT|^\s*Time\b|Mutuel Prices", line):
            break
        if not line.strip():
            continue
        seg = line[:name_end]
        # dead-heat co-winners carry a ” (or variant) glyph before the name
        m = re.search(r"(?:^|\s)(\d{1,2}A?)\s+[”“\"*]?\s*([A-Za-z][A-Za-z'.\- ()]*?)\s*$",
                      seg)
        if not m:
            continue
        # guard: the pgm token must sit near the '#' column, not be part of
        # the Last Raced date (e.g. '26Nov25' would never match: \s boundary)
        pgm, name = m.group(1), m.group(2).strip()
        if not name or len(name) < 2:
            continue
        toks = line.split()
        odds = None
        if toks:
            try:
                odds = float(toks[-1].replace(",", ""))
            except ValueError:
                odds = None
        finishers.append({"pgm": pgm, "name": name, "odds": odds})
    return finishers


def parse_mutuels(block):
    """Parse the $2 Mutuel Prices WPS block + exotics lines + carryovers."""
    wps, exotics, carryovers = [], [], []
    wps_row = 0
    for line in block.splitlines():
        if "Mutuel Prices" in line:
            line = re.sub(r"\$2\s*Mutuel Prices:", "", line)
        m = WPS_RE.match(line)
        if m:
            pgm   = m.group(1)
            nums  = [float(x) for x in m.group(3).split()]
            # A 3-value row is always a (co-)winner — dead heats for win list
            # two full WIN/PLACE/SHOW rows before the place/show-only rows.
            pools = (["WIN", "PLACE", "SHOW"] if len(nums) == 3
                     else ["WIN", "PLACE"][:len(nums)] if wps_row == 0
                     else ["PLACE", "SHOW"][-len(nums):] if len(nums) == 2
                     else ["SHOW"])
            for pool, val in zip(pools, nums):
                wps.append({"pool": pool, "pgm": pgm, "payoff": val,
                            "denom": 2.0})
            wps_row += 1
        for em in EXOTIC_RE.finditer(line):
            denom = _denom_value(em.group(1))
            pool  = POOL_NAMES[em.group(2).upper().replace("PICK THREE", "PICK 3")]
            combo = em.group(3).replace("/", "-")
            paid  = float(em.group(4).replace(",", ""))
            exotics.append({"pool": pool, "combo": combo, "payoff": paid,
                            "denom": denom})
    for cm in CARRYOVER_RE.finditer(block):
        carryovers.append({"pool": POOL_NAMES[cm.group(1).upper()],
                           "amount": float(cm.group(2).replace(",", ""))})
    return wps, exotics, carryovers


def parse_scratches(block):
    """Scratched- section: comma-separated names, each optionally trailed by a
    last-raced parenthetical like (11Jun26«Del¬) whose superscripts extract as
    non-ASCII glyphs; the list may wrap one line, splitting a name or its
    parenthetical across the break. Stops at any line carrying payoff/pool text
    (the multi-race exotics block follows immediately in some charts)."""
    m = re.search(r"Scratched-\s*([^\n]*(?:\n[^\n]*)?)", block)
    if not m:
        return []
    kept = []
    for raw_line in m.group(1).splitlines():
        if re.search(r"\$|Paid|Pool|Trainers-|Owners-|Breeders-", raw_line):
            break
        kept.append(raw_line)
    joined = " ".join(kept)                       # re-join a wrapped name/paren
    joined = re.sub(r"\([^)]*\)", "", joined)     # drop last-raced parentheticals
    joined = re.sub(r"[^\x20-\x7E]", "", joined)  # stray superscript glyphs
    names = []
    for part in re.split(r"[;,]", joined):
        name = re.sub(r"\s+", " ", part).strip().rstrip(".").strip()
        if name and re.fullmatch(r"[A-Za-z][A-Za-z'.\- ]{1,30}", name):
            names.append(name)
    return names


def parse_chart(text):
    """Full-card chart text -> {race_num: parsed race dict}."""
    races = {}
    for rnum, block in split_races(text).items():
        wps, exotics, carryovers = parse_mutuels(block)
        races[rnum] = {
            "finishers":  parse_finishers(block),
            "wps":        wps,
            "exotics":    exotics,
            "carryovers": carryovers,
            "scratches":  parse_scratches(block),
            "dead_heat":  bool(re.search(r"DEAD\s*HEAT", block, re.IGNORECASE)),
            "dq":         bool(re.search(r"isqualif", block)),
        }
    return races


# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS race_payoffs (
            id INTEGER PRIMARY KEY,
            race_id INTEGER REFERENCES races(id),
            pool TEXT NOT NULL,
            combination TEXT NOT NULL,
            payoff REAL NOT NULL,
            denomination REAL NOT NULL,
            is_dead_heat INTEGER DEFAULT 0,
            is_refund INTEGER DEFAULT 0,
            carryover_in REAL,
            carryover_out REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_id, pool, combination)
        );
        CREATE TABLE IF NOT EXISTS race_finish_order (
            id INTEGER PRIMARY KEY,
            race_id INTEGER REFERENCES races(id),
            finish_position INTEGER,
            horse_pgm TEXT NOT NULL,
            horse_name TEXT NOT NULL,
            final_tote_odds REAL,
            is_late_scratch INTEGER DEFAULT 0,
            is_dq INTEGER DEFAULT 0,
            official_position INTEGER,
            is_coupled INTEGER DEFAULT 0,
            coupled_program TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_id, horse_pgm)
        );
        CREATE TABLE IF NOT EXISTS exotic_tickets (
            id INTEGER PRIMARY KEY,
            race_id INTEGER REFERENCES races(id),
            ticket_type TEXT NOT NULL,
            combination TEXT NOT NULL,
            cost REAL NOT NULL,
            denomination REAL NOT NULL,
            is_paper INTEGER DEFAULT 1,
            actual_payoff REAL,
            profit REAL,
            race_shape TEXT,
            contender_set TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(races)")}
    if "field_size_post" not in cols:
        conn.execute("ALTER TABLE races ADD COLUMN field_size_post INTEGER")
    if "has_coupled_entry" not in cols:
        conn.execute("ALTER TABLE races ADD COLUMN has_coupled_entry INTEGER DEFAULT 0")
    conn.commit()


def find_chart_pdf(track, date_str):
    # chart files in hand use a mix of Equibase and BRIS track codes
    codes = {TRACK_TO_EQB.get(track.upper(), track.upper()), track.upper()}
    for d in CHART_DIRS:
        if not d.exists():
            continue
        for code in codes:
            for p in sorted(d.glob(f"{date_str}{code}USA0*.pdf")):
                return p
    return None


def reconcile_picks(conn, rid, finishers, scratches, wps, name_to_pgm):
    """Back-fill picks.finish_pos/won/sp_odds straight from the chart.

    This is the offline counterpart to r5_tracker --fetch: when the live results
    source (Equibase/HRN) is unreachable, --fetch fails and never populates the
    picks table, so r5_analyze (which reads picks.*) silently misses the card
    even though the finish order/payoffs are already in race_finish_order. The
    Equibase chart is authoritative, so we populate the same fields --fetch
    would. Only called when result_fetched=0 (no live fetch has claimed race).

    Dead heats for win: each co-winner has its own WIN payoff row (the chart
    lists the co-winners first), so every pick whose program matches a WIN row
    gets won=1, finish_pos=1, and its own payoff — not just the first-listed.

    Coupled entries: chart pgms may carry a letter suffix (1A) while the pick
    was logged under the base number; both runners of an entry then map to the
    same pick row, so settlement is grouped per target and the BEST finish
    wins — a later-finishing coupled mate must not overwrite the entry's win.

    Picks that are neither in the chart finish order nor a matched scratch are
    left finish_pos=NULL (not forced to a loss): they are unaccounted — a parse
    gap or a scratch whose chart name didn't match a logged horse_name. NULL is
    what r5_tracker --finalize keys on to mark them -1 (excluded from stats).
    Forcing them to finish_pos=5 would lock in a wrong 'loss' and hide them from
    --finalize. Returns the count of such unaccounted picks so the caller can
    warn.
    """
    conn.execute(
        "UPDATE picks SET finish_pos=NULL, won=0, sp_odds=NULL WHERE race_id=?",
        (rid,))
    pick_pgms = {str(r["pgm"]) for r in conn.execute(
        "SELECT pgm FROM picks WHERE race_id=?", (rid,))}

    def _base(pgm):
        return re.sub(r"[A-Z]$", "", pgm)

    # WIN payoff rows keyed by program; >1 row = dead heat for win. Mutuel
    # rows carry the betting-interest pgm (no coupled letter), so fall back to
    # the base pgm — but only the first n_win listed finishers are official
    # (co-)winners, which stops a later coupled mate matching its entry's row.
    win_rows = {w["pgm"]: w["payoff"] for w in wps if w["pool"] == "WIN"}
    n_win = max(len(win_rows), 1)

    settled = {}  # target pick pgm -> (finish_pos, won, win_payoff)
    for pos, f in enumerate(finishers, 1):
        pgm = f["pgm"]
        target = pgm if pgm in pick_pgms else _base(pgm)
        payoff = (win_rows.get(pgm, win_rows.get(_base(pgm)))
                  if pos <= n_win else None)
        won = 1 if (pos == 1 or payoff is not None) else 0
        eff_pos = 1 if won else pos
        cur = settled.get(target)
        if cur is None or eff_pos < cur[0]:
            settled[target] = (eff_pos, won, payoff)
    for target, (pos, won, payoff) in settled.items():
        conn.execute(
            "UPDATE picks SET finish_pos=?, won=? WHERE race_id=? AND pgm=?",
            (pos, won, rid, target))
        if won and payoff:
            conn.execute(
                "UPDATE picks SET sp_odds=? WHERE race_id=? AND pgm=?",
                (payoff, rid, target))
    # confirmed scratches -> finish_pos=-1 (excluded from model stats)
    for name in scratches:
        pgm = name_to_pgm.get(_norm_name(name))
        if pgm:
            conn.execute(
                "UPDATE picks SET finish_pos=-1 WHERE race_id=? AND pgm=?",
                (rid, pgm))
    # Unaccounted picks (not a finisher, not a matched scratch) stay NULL for
    # --finalize to resolve; count them for the caller's warning.
    unaccounted = conn.execute(
        "SELECT COUNT(*) FROM picks WHERE race_id=? AND finish_pos IS NULL",
        (rid,)).fetchone()[0]
    conn.execute("UPDATE races SET result_fetched=1 WHERE id=?", (rid,))
    return unaccounted


def ingest_race(conn, race_row, parsed):
    """Idempotent write of one race's payoffs + finish order."""
    rid = race_row["id"]
    conn.execute("DELETE FROM race_payoffs WHERE race_id=?", (rid,))
    conn.execute("DELETE FROM race_finish_order WHERE race_id=?", (rid,))

    # normalized name -> pgm map from picks, for scratch rows (charts list
    # names only)
    pick_pgms = {_norm_name(r["horse_name"]): r["pgm"] for r in conn.execute(
        "SELECT horse_name, pgm FROM picks WHERE race_id=?", (rid,))}

    finishers = parsed["finishers"]
    coupled   = any(re.search(r"[A-Z]$", f["pgm"]) for f in finishers)

    for pos, f in enumerate(finishers, 1):
        base = re.sub(r"[A-Z]$", "", f["pgm"])
        conn.execute("""
            INSERT INTO race_finish_order
            (race_id, finish_position, horse_pgm, horse_name, final_tote_odds,
             is_late_scratch, is_dq, official_position, is_coupled, coupled_program)
            VALUES (?,?,?,?,?,0,?,?,?,?)
        """, (rid, pos, f["pgm"], f["name"], f["odds"],
              1 if parsed["dq"] else 0, pos,
              1 if f["pgm"] != base else 0,
              base if f["pgm"] != base else None))

    for i, name in enumerate(parsed["scratches"], 1):
        pgm = pick_pgms.get(_norm_name(name), f"SCR{i}")
        try:
            conn.execute("""
                INSERT INTO race_finish_order
                (race_id, finish_position, horse_pgm, horse_name,
                 is_late_scratch, official_position)
                VALUES (?,NULL,?,?,1,NULL)
            """, (rid, pgm, name))
        except sqlite3.IntegrityError:
            pass  # scratch name collided with a runner pgm — runner row wins

    dh = 1 if parsed["dead_heat"] else 0
    n_win_rows = sum(1 for w in parsed["wps"] if w["pool"] == "WIN")
    for w in parsed["wps"]:
        conn.execute("""
            INSERT OR REPLACE INTO race_payoffs
            (race_id, pool, combination, payoff, denomination, is_dead_heat)
            VALUES (?,?,?,?,?,?)
        """, (rid, w["pool"], w["pgm"], w["payoff"], w["denom"],
              dh if n_win_rows > 1 or dh else 0))
    for e in parsed["exotics"]:
        conn.execute("""
            INSERT OR REPLACE INTO race_payoffs
            (race_id, pool, combination, payoff, denomination, is_dead_heat)
            VALUES (?,?,?,?,?,?)
        """, (rid, e["pool"], e["combo"], e["payoff"], e["denom"], dh))
    for c in parsed["carryovers"]:
        conn.execute("""
            INSERT OR REPLACE INTO race_payoffs
            (race_id, pool, combination, payoff, denomination, carryover_out)
            VALUES (?,?, 'CARRYOVER', 0, 1.0, ?)
        """, (rid, c["pool"], c["amount"]))

    conn.execute("UPDATE races SET field_size_post=?, has_coupled_entry=? WHERE id=?",
                 (len(finishers), 1 if coupled else 0, rid))

    win = next((w for w in parsed["wps"] if w["pool"] == "WIN"), None)

    # Safety net: if no live results fetch has populated picks (result_fetched=0),
    # back-fill picks.finish_pos/won/sp_odds from the chart so r5_analyze sees the
    # card. When --fetch succeeds first (result_fetched=1) we leave its data alone
    # and instead run the independent cross-check below.
    already_fetched = conn.execute(
        "SELECT result_fetched FROM races WHERE id=?", (rid,)).fetchone()[0]
    reconciled = False
    unaccounted = 0
    if not already_fetched:
        unaccounted = reconcile_picks(conn, rid, finishers, parsed["scratches"],
                                      parsed["wps"], pick_pgms)
        reconciled = True

    warn = None
    if reconciled:
        # unaccounted picks were left NULL for --finalize; surface so it's not
        # silent (a missed/misnamed scratch would otherwise count as a loss).
        if unaccounted:
            warn = (f"{unaccounted} pick(s) unaccounted (not in chart finish "
                    f"order or scratches) — run r5_tracker --finalize to resolve")
    elif win:
        # data-quality cross-check: chart WIN payoff vs an *independent* fetch's
        # sp_odds. Only meaningful when we did NOT reconcile from the same chart.
        row = conn.execute(
            "SELECT sp_odds FROM picks WHERE race_id=? AND won=1", (rid,)
        ).fetchone()
        if row and row["sp_odds"] and abs(row["sp_odds"] - win["payoff"]) > 0.02:
            warn = (f"WIN payoff mismatch: chart ${win['payoff']:.2f} vs "
                    f"logged sp_odds ${row['sp_odds']:.2f}")
    return warn, reconciled


def run_ingest(track, date_str, race_num=None, pdf=None, txt=None):
    conn = get_conn()
    init_schema(conn)

    if txt:
        text = Path(txt).read_text(errors="replace")
        src  = txt
    else:
        pdf_path = Path(pdf) if pdf else find_chart_pdf(track, date_str)
        if not pdf_path or not pdf_path.exists():
            print(f"  ⚠️  No chart PDF found for {track} {date_str}.")
            print(f"      Download the Equibase full-card chart PDF into Results/2026/")
            print(f"      (expected name: {date_str}{TRACK_TO_EQB.get(track.upper(), track)}USA0.pdf)")
            print(f"      or pass --pdf / --txt explicitly.")
            sys.exit(1)
        text = extract_pdf_text(pdf_path)
        src  = pdf_path.name

    chart = parse_chart(text)
    if not chart:
        print(f"  ⚠️  Could not parse any races from {src}")
        sys.exit(1)

    db_races = {r["race_num"]: r for r in conn.execute(
        "SELECT * FROM races WHERE track=? AND date=?", (track.upper(), date_str))}

    targets = ([str(race_num)] if race_num else sorted(db_races, key=lambda x: int(x)))
    print(f"\n📥 Ingesting {track} {date_str} from {src} "
          f"(chart races: {sorted(chart)}; DB races: {sorted(db_races, key=int)})")

    done, skipped, warns, reconciled_n = 0, [], [], 0
    for rn in targets:
        if rn not in db_races:
            skipped.append((rn, "not logged in races table"))
            continue
        if int(rn) not in chart:
            skipped.append((rn, "not found in chart"))
            continue
        parsed = chart[int(rn)]
        if not parsed["finishers"]:
            skipped.append((rn, "finish table parse failed"))
            continue
        warn, reconciled = ingest_race(conn, db_races[rn], parsed)
        np_, nf = (conn.execute(
            f"SELECT (SELECT COUNT(*) FROM race_payoffs WHERE race_id=?),"
            f"(SELECT COUNT(*) FROM race_finish_order WHERE race_id=?)",
            (db_races[rn]["id"], db_races[rn]["id"])).fetchone())
        flags = []
        if parsed["dq"]:        flags.append("DQ — verify across-wire order manually")
        if parsed["dead_heat"]: flags.append("DEAD HEAT")
        if reconciled:          flags.append("picks reconciled from chart")
        if warn:                flags.append(warn)
        print(f"  ✅ R{rn}: {nf} finishers, {np_} payoff rows"
              + (f"  ⚠️ {'; '.join(flags)}" if flags else ""))
        if warn:
            warns.append((rn, warn))
        if reconciled:
            reconciled_n += 1
        done += 1

    conn.commit()
    chart_only = [c for c in sorted(chart) if str(c) not in db_races]
    if chart_only:
        print(f"  ℹ️  Chart races not in DB (not analyzed, skipped): {chart_only}")
    for rn, why in skipped:
        print(f"  ⚠️  R{rn} skipped: {why}")
    print(f"\n✅ {done} race(s) ingested."
          + (f"  ({reconciled_n} reconciled from chart — no live fetch needed; "
             f"run r5_tracker --finalize to check late scratches)"
             if reconciled_n else ""))
    conn.close()
    return done


def main():
    ap = argparse.ArgumentParser(description="Exotic payoff/finish-order ingestion")
    ap.add_argument("--track", required=True)
    ap.add_argument("--date", required=True, help="YYYYMMDD")
    ap.add_argument("--race", type=int)
    ap.add_argument("--pdf", help="explicit chart PDF path")
    ap.add_argument("--txt", help="pre-extracted/pasted chart text file")
    args = ap.parse_args()
    run_ingest(args.track, args.date, args.race, args.pdf, args.txt)


if __name__ == "__main__":
    main()
