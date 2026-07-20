#!/usr/bin/env python3
"""
r5_pdf_results.py — BRIS chart PDF parser

Extracts finish order and win payouts from BRIS results chart PDFs.
Works with the standard BRIS/Equibase chart format.

Returns:
    {race_num (int): {"finish": ["pgm1", "pgm2", ...], "sp": float_or_None, "winner_name": str_or_None}}

Usage (standalone test):
    python3 Claude/r5_pdf_results.py Results/2026/20260525SAXUSA0.pdf
"""

import re
import sys
from pathlib import Path

# Ordinal → integer for race header ("FIRST RACE", "SECOND RACE", ...)
ORDINAL_MAP = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
    "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14,
    "FIFTEENTH": 15,
}


def parse_results_pdf(pdf_path: str) -> dict:
    """
    Parse a BRIS results chart PDF.

    Returns:
        dict: {race_num (int): {"finish": [pgm_str, ...], "sp": float|None, "winner_name": str|None}}
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed — run: pip install pdfplumber")

    results: dict = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            race_num = _extract_race_num(text)
            if race_num is None:
                continue

            # Multi-page races: if we already have a result for this race number,
            # it means a big field spilled onto an extra page — skip.
            if race_num in results:
                continue

            finish_pgms = _extract_finish_order(text)
            if not finish_pgms:
                continue

            sp, winner_name = _extract_win_payout(text)

            results[race_num] = {
                "finish":      finish_pgms,
                "sp":          sp,
                "winner_name": winner_name,
            }

    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_race_num(text: str) -> int | None:
    """Extract race number from the first few lines of a page."""
    for line in text.splitlines()[:6]:
        upper = line.upper()
        # "FIRST RACE", "SECOND RACE", ...
        for word, num in ORDINAL_MAP.items():
            if f"{word} RACE" in upper:
                return num
        # Fallback: "RACE 1", "RACE 2", ...
        m = re.search(r"\bRACE\s+(\d{1,2})\b", upper)
        if m:
            return int(m.group(1))
    return None


def _extract_finish_order(text: str) -> list:
    """
    Extract program numbers in finish order from the running lines table.

    BRIS chart format:
      Header:  "Last Raced  # Horse  M/Eqt.A/S  Wt  PP  St  ¼  ½  Str  Fin  Jockey  ..."
      Rows:    "18Feb26 TP  6  Warm Up the Bus  L 3F 118  6  9  6²  5¨  3¨  1  Sheehy D  ..."
               (rows listed in finish order — 1st place horse first)
    """
    lines = text.splitlines()

    # Find the column header line
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r"#\s+Horse.*Wt.*Fin", line, re.IGNORECASE):
            header_idx = i
            break

    if header_idx is None:
        # Fallback: look for "Last Raced" header
        for i, line in enumerate(lines):
            if "Last Raced" in line and "Horse" in line:
                header_idx = i
                break

    start = (header_idx + 1) if header_idx is not None else 0

    pgms = []
    for line in lines[start:]:
        stripped = line.strip()
        # Stop at end-of-running-lines markers
        if not stripped:
            # Allow one blank (multi-column header sometimes has blank separator)
            if pgms:  # already collected some — real end of table
                break
            continue
        if stripped.startswith("OFF AT") or stripped.startswith("Time "):
            break
        if stripped.startswith("$2 Mutuel") or stripped.startswith("$1 "):
            break

        # Match a running line — starts with:
        #   {date}{non-digits}{track}{non-digits}  {pgm}  {Name}  {medication}
        #   e.g. "18Feb26®TP® 6 Warm Up the Bus L 3F"
        # or for first-time starters (no last-raced date), leading spaces + pgm
        # Anchor the name's end on the A/S + 3-digit-weight columns ("6G 155"),
        # not the M/Eqt token — equipment is optional (absent, or v/h on jump
        # races) and letters like the L in "Doctor Love" false-match it.
        m = re.match(
            r"^\s*(?:\d{2}[A-Za-z]{3}\d{2}[^\d]+)?(\d{1,2}[A-Z]?)\s+[”“\"*]?\s*"
            r"([A-Z][A-Za-z\'\s\-().]+?)\s+(?:[A-Za-z]{1,3}\s+){0,2}\d{1,2}[A-Z]{1,2}\s+\d{3}\b",
            line,
        )
        if m:
            pgms.append(m.group(1))

    return pgms


def _extract_win_payout(text: str) -> tuple:
    """
    Extract $2 win payout and winner name.

    BRIS format places the winner's mutuel line BEFORE "$2 Mutuel Prices:":
        "6-WARM UP THE BUS . . . . 11.22  5.86  3.98"
        "$2 Mutuel Prices:"
        "5-GLADLY . . . . . . . . . . . . . . . . 7.70  4.78"
        "4-SWEETBITTERS . . . . . . . . . . . . . 6.80"
    """
    lines = text.splitlines()

    mutuel_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\$2 Mutuel Prices", line, re.IGNORECASE):
            mutuel_idx = i
            break

    if mutuel_idx is None:
        return None, None

    # Look backwards (up to 5 lines) for the winner's payout line
    for i in range(mutuel_idx - 1, max(mutuel_idx - 6, -1), -1):
        line = lines[i]
        # Winner line has 3 payouts: win, place, show
        m = re.search(r"([\d]+\.[\d]+)\s+([\d]+\.[\d]+)\s+([\d]+\.[\d]+)\s*$", line)
        if m:
            # Extract winner name: "{pgm}-{NAME} . . ."
            name_m = re.match(r"^\s*\d+[A-Za-z]?-[”“\"*]?\s*([A-Z][A-Z\s\'\-\.()]+?)\s*[\.\s]{3,}", line)
            winner_name = name_m.group(1).strip() if name_m else None
            try:
                return float(m.group(1)), winner_name
            except ValueError:
                pass

    return None, None


# ── CLI entry for testing ─────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 Claude/r5_pdf_results.py <results.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    print(f"\n📄 Parsing: {pdf_path}\n")
    results = parse_results_pdf(pdf_path)

    if not results:
        print("⚠️  No race results extracted — check PDF format")
        sys.exit(1)

    for race_num in sorted(results):
        r = results[race_num]
        sp_str = f"  SP: ${r['sp']:.2f}" if r["sp"] else ""
        winner = r["winner_name"] or r["finish"][0] if r["finish"] else "?"
        finish_str = " → ".join(f"#{p}" for p in r["finish"][:4])
        print(f"  R{race_num:<2}  {finish_str:<40}  Winner: {winner}{sp_str}")

    print(f"\n✅ {len(results)} races parsed")


if __name__ == "__main__":
    main()
