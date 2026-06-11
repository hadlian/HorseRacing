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
DB_PATH           = HORSE_RACING_ROOT / "Results" / "r5_results.db"
CHART_DIRS        = [HORSE_RACING_ROOT / "Results" / "2026",
                     HORSE_RACING_ROOT / "Results"]

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
    r"^\s*(\d{1,2}[A-Z]?)\s*-\s+[”“\"*]?\s*([A-Z][A-Z'.\- ]*?)\s*(?:\.\s*){2,}"
    r"((?:\d+\.\d{2}\s*){1,3})\s*$")


def _denom_value(text):
    for pat, val in DENOMS:
        if re.fullmatch(pat, text.strip(), re.IGNORECASE):
            return val
    return None


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
        m = re.search(r"(?:^|\s)(\d{1,2}A?)\s+([A-Za-z][A-Za-z'.\- ()]*?)\s*$",
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
            pools = (["WIN", "PLACE", "SHOW"][:len(nums)] if wps_row == 0
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
    """Scratched- section: names only, possibly wrapping one line. Stops at
    any line carrying payoff/pool text (the multi-race exotics block follows
    immediately in some charts)."""
    m = re.search(r"Scratched-\s*([^\n]*(?:\n[^\n]*)?)", block)
    if not m:
        return []
    names = []
    for raw_line in m.group(1).splitlines():
        if re.search(r"\$|Paid|Pool|Trainers-|Owners-|Breeders-", raw_line):
            break
        for part in raw_line.split(";"):
            name = re.sub(r"\([^)]*\)", "", part).strip().rstrip(".").strip()
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


def ingest_race(conn, race_row, parsed):
    """Idempotent write of one race's payoffs + finish order."""
    rid = race_row["id"]
    conn.execute("DELETE FROM race_payoffs WHERE race_id=?", (rid,))
    conn.execute("DELETE FROM race_finish_order WHERE race_id=?", (rid,))

    # name -> pgm map from picks, for scratch rows (charts list names only)
    pick_pgms = {r["horse_name"].upper(): r["pgm"] for r in conn.execute(
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
        pgm = pick_pgms.get(name.upper(), f"SCR{i}")
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

    # data-quality cross-check: chart WIN payoff vs logged winner sp_odds
    warn = None
    win = next((w for w in parsed["wps"] if w["pool"] == "WIN"), None)
    if win:
        row = conn.execute(
            "SELECT sp_odds FROM picks WHERE race_id=? AND won=1", (rid,)
        ).fetchone()
        if row and row["sp_odds"] and abs(row["sp_odds"] - win["payoff"]) > 0.02:
            warn = (f"WIN payoff mismatch: chart ${win['payoff']:.2f} vs "
                    f"logged sp_odds ${row['sp_odds']:.2f}")
    return warn


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

    done, skipped, warns = 0, [], []
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
        warn = ingest_race(conn, db_races[rn], parsed)
        np_, nf = (conn.execute(
            f"SELECT (SELECT COUNT(*) FROM race_payoffs WHERE race_id=?),"
            f"(SELECT COUNT(*) FROM race_finish_order WHERE race_id=?)",
            (db_races[rn]["id"], db_races[rn]["id"])).fetchone())
        flags = []
        if parsed["dq"]:        flags.append("DQ — verify across-wire order manually")
        if parsed["dead_heat"]: flags.append("DEAD HEAT")
        if warn:                flags.append(warn)
        print(f"  ✅ R{rn}: {nf} finishers, {np_} payoff rows"
              + (f"  ⚠️ {'; '.join(flags)}" if flags else ""))
        if warn:
            warns.append((rn, warn))
        done += 1

    conn.commit()
    chart_only = [c for c in sorted(chart) if str(c) not in db_races]
    if chart_only:
        print(f"  ℹ️  Chart races not in DB (not analyzed, skipped): {chart_only}")
    for rn, why in skipped:
        print(f"  ⚠️  R{rn} skipped: {why}")
    print(f"\n✅ {done} race(s) ingested.")
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
