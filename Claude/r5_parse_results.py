#!/usr/bin/env python3
"""
r5_parse_results.py — Equibase PDF Result Chart Parser

Reads an Equibase result chart PDF, extracts finish order and win
mutuel for every race, and loads them into the R5 tracker DB.

Usage:
    python3 r5_parse_results.py results/ChurchillDowns0502.pdf CD 20260502
    python3 r5_parse_results.py results/ChurchillDowns0502.pdf CD 20260502 --dry-run
    python3 r5_parse_results.py results/ChurchillDowns0502.pdf CD 20260502 --race 12
"""

import argparse
import importlib.util as ilu
import re
import subprocess
import sys
from pathlib import Path

HORSE_RACING_ROOT = Path("/Users/harryadalian/Documents/HorseRacing")

RACE_ORDER = [
    'FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'SEVENTH',
    'EIGHTH', 'NINTH', 'TENTH', 'ELEVENTH', 'TWELFTH', 'THIRTEENTH', 'FOURTEENTH'
]

POOL_NAMES = {
    'Daily Double', 'Super High Five', 'Trifecta', 'Exacta',
    'Superfecta', 'Pick', 'Odd', 'Even'
}


def pdf_to_text(pdf_path):
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(
            ['pdftotext', str(pdf_path), '-'],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: pdftotext not found. Install with: brew install poppler")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error reading PDF: {e}")
        sys.exit(1)


def parse_race(body):
    """
    Parse one race body block. Returns dict with:
        finish  — list of program numbers in finish order
        win_pgm — program number of winner
        win_pay — $2 win mutuel payout
        scratches — list of scratched horse names
    """
    # ── Finish order ──────────────────────────────────────────────────────────
    finish = []

    # Best source: SUPERFECTA (1-2-3-4)
    sup = re.search(r'SUPERFECTA \((\d+)-(\d+)-(\d+)-(\d+)\)', body)
    tri = re.search(r'(?:CENT |DOLLAR )?TRIFECTA \((\d+)-(\d+)-(\d+)\)', body)
    ex  = re.search(r'EXACTA \((\d+)-(\d+)\)', body)

    if sup:
        finish = [sup.group(1), sup.group(2), sup.group(3), sup.group(4)]
    elif tri:
        finish = [tri.group(1), tri.group(2), tri.group(3)]
    elif ex:
        finish = [ex.group(1), ex.group(2)]

    # ── Win payout ────────────────────────────────────────────────────────────
    # Format: '6- MAKE MY DAY . . . . . . 17.60 8.40 5.20'
    win_pgm, win_pay = None, None
    m = re.search(
        r'(\d+)-\s+[A-Z][A-Z\'\. /&-]+?[ .]{3,}\s*([\d]+\.[\d]+)\s+[\d]+\.[\d]+',
        body
    )
    if m:
        win_pgm = m.group(1)
        try:
            win_pay = float(m.group(2))
        except ValueError:
            pass

    # Fallback: if finish found but no payout parsed, use winner from finish
    if finish and not win_pgm:
        win_pgm = finish[0]

    # If we have win_pgm but finish list is empty/wrong, prepend it
    if win_pgm and finish and finish[0] != win_pgm:
        finish = [win_pgm] + [p for p in finish if p != win_pgm]
    elif win_pgm and not finish:
        finish = [win_pgm]

    # ── Scratches ─────────────────────────────────────────────────────────────
    scratches = []
    scr_match = re.search(r'Scratched-\s*(.+?)(?:\n\n|\Z)', body, re.DOTALL)
    if scr_match:
        candidates = re.findall(r'([A-Z][a-zA-Z \'-]+?)(?:\(|\,|\n)', scr_match.group(1))
        scratches = [
            n.strip() for n in candidates
            if n.strip() and n.strip() not in POOL_NAMES and len(n.strip()) > 2
        ]

    return {
        'finish':    finish,
        'win_pgm':   win_pgm,
        'win_pay':   win_pay,
        'scratches': scratches,
    }


def parse_pdf(pdf_path):
    """Parse all races from an Equibase result chart PDF."""
    text = pdf_to_text(pdf_path)

    # Find all race header positions
    pattern = (
        r'((?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH'
        r'|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH) RACE)'
    )
    matches = [(m.start(), m.group(1)) for m in re.finditer(pattern, text)]

    if not matches:
        print("No race headers found in PDF. Is this an Equibase result chart?")
        sys.exit(1)

    races = {}
    for idx, (pos, name) in enumerate(matches):
        end  = matches[idx + 1][0] if idx + 1 < len(matches) else len(text)
        body = text[pos:end]
        race_num = RACE_ORDER.index(name.split()[0]) + 1
        races[race_num] = parse_race(body)

    return races


def load_tracker():
    tracker_path = Path(__file__).parent / "r5_tracker.py"
    spec = ilu.spec_from_file_location("r5_tracker", tracker_path)
    mod  = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description="Parse Equibase PDF and load results into R5 DB")
    ap.add_argument("pdf",    help="Path to Equibase result chart PDF")
    ap.add_argument("track",  help="Track code (e.g. CD, SAR, KEE)")
    ap.add_argument("date",   help="Race date YYYYMMDD (e.g. 20260502)")
    ap.add_argument("--race",    type=int, help="Load single race only")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and print without writing to DB")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    print(f"\n📄 Parsing: {pdf_path.name}")
    races = parse_pdf(pdf_path)

    if args.race:
        if args.race not in races:
            print(f"Race {args.race} not found in PDF (found: {sorted(races.keys())})")
            sys.exit(1)
        races = {args.race: races[args.race]}

    print(f"   Found {len(races)} race(s)\n")

    # Print summary
    print(f"{'Race':<6} {'Finish':<20} {'Win Pay':<10} {'Scratches'}")
    print("-" * 70)
    for race_num in sorted(races.keys()):
        r = races[race_num]
        pgm_str = ','.join(r['finish']) if r['finish'] else '?'
        sp_str  = f"${r['win_pay']:.2f}" if r['win_pay'] else '?'
        scr_str = ', '.join(r['scratches'][:3]) if r['scratches'] else ''
        print(f"R{race_num:<5} {pgm_str:<20} {sp_str:<10} {scr_str}")

    if args.dry_run:
        print("\n[dry-run] Nothing written to DB.")
        return

    # Load into DB
    tracker = load_tracker()
    print(f"\n💾 Loading into DB: {args.track.upper()} {args.date}")
    ok = 0
    skipped = 0
    for race_num in sorted(races.keys()):
        r = races[race_num]
        if not r['finish']:
            print(f"  ⚠️  R{race_num}: no finish order parsed — skipping")
            skipped += 1
            continue
        if tracker.apply_result(
            args.track.upper(), args.date, str(race_num),
            r['finish'], r['win_pay']
        ):
            ok += 1
        else:
            skipped += 1

    print(f"\n✅ Loaded {ok} races  |  ⚠️  Skipped {skipped}")
    if skipped:
        print("   Skipped races have no logged picks — run with --track first")


if __name__ == "__main__":
    main()
