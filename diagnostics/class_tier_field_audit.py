#!/usr/bin/env python3
"""
class_tier_field_audit.py  —  READ-ONLY diagnostic.

Sizes the messiness of the BRIS DRF past_race_type block (fields 1086-1095)
ahead of any "class tier parser" design work for the Speed-Trend Reliability
Layer (Bounce Risk + Progression Confirmation) issue.

Does NOT touch r5_parser_v2.py or any scoring logic. It reads DRF files the
exact same way the parser does (csv.reader, 1-indexed field access with the
parser's pf() semantics) and only counts values — no parsing, no mapping,
no scoring.

Usage:
    python3 diagnostics/class_tier_field_audit.py
    python3 diagnostics/class_tier_field_audit.py "/path/to/drf_dir"

Default scan dir: the "files 2" archive the working DRF set lives in.
Output: two sibling files next to this script:
    class_tier_field_audit.txt   (human-readable report)
    class_tier_field_audit.csv   (count,value  — full frequency table)
"""

import csv
import sys
import glob
import os
from collections import Counter

# past_race_type block: BRIS fields 1086..1095 (10 past performance lines)
FIELD_START = 1086
FIELD_COUNT = 10

# Mirror r5_parser_v2.pf(): 1-indexed access, strip, blank on missing/empty.
def pf(row, idx):
    try:
        v = row[idx - 1]
        return v.strip() if v else ""
    except IndexError:
        return ""


def find_drf_files(scan_dir):
    # Case-insensitive .DRF match, non-recursive within the archive dir.
    files = sorted(
        p for p in glob.glob(os.path.join(scan_dir, "*"))
        if p.lower().endswith(".drf")
    )
    return files


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    sys.path.insert(0, os.path.join(project_root, "Claude"))
    from r5_paths import DRF_DIR
    default_dir = str(DRF_DIR)
    scan_dir = sys.argv[1] if len(sys.argv) > 1 else default_dir

    files = find_drf_files(scan_dir)
    if not files:
        print(f"No .DRF files found in: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    counts = Counter()          # non-blank value -> occurrences
    blank_occurrences = 0
    total_slots = 0             # every horse-row * 10 fields examined
    horse_rows = 0
    per_file = {}               # filename -> (rows, non_blank)

    for path in files:
        f_rows = 0
        f_nonblank = 0
        with open(path, newline="") as fh:
            for row in csv.reader(fh):
                if not row:
                    continue
                horse_rows += 1
                f_rows += 1
                for i in range(FIELD_COUNT):
                    total_slots += 1
                    v = pf(row, FIELD_START + i)
                    if v == "":
                        blank_occurrences += 1
                    else:
                        counts[v] += 1
                        f_nonblank += 1
        per_file[os.path.basename(path)] = (f_rows, f_nonblank)

    non_blank_total = sum(counts.values())
    distinct = len(counts)

    ranked = counts.most_common()          # count desc, then insertion order
    top20 = ranked[:20]
    top20_sum = sum(c for _, c in top20)
    top20_pct = (100.0 * top20_sum / non_blank_total) if non_blank_total else 0.0

    # ---- CSV: full frequency table (count,value) ----
    csv_path = os.path.join(here, "class_tier_field_audit.csv")
    with open(csv_path, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["count", "value"])
        for val, c in ranked:
            w.writerow([c, val])

    # ---- TXT: human-readable report ----
    txt_path = os.path.join(here, "class_tier_field_audit.txt")
    lines = []
    lines.append("=" * 68)
    lines.append("past_race_type field audit  (BRIS fields 1086-1095)")
    lines.append("READ-ONLY diagnostic — no parsing/scoring, sizing only")
    lines.append("=" * 68)
    lines.append(f"Scan dir            : {scan_dir}")
    lines.append(f"DRF files scanned   : {len(files)}")
    lines.append(f"Horse rows scanned  : {horse_rows:,}")
    lines.append(f"Field slots examined: {total_slots:,}  (rows x {FIELD_COUNT})")
    lines.append(f"Non-blank occurrences: {non_blank_total:,}")
    lines.append(f"Blank occurrences    : {blank_occurrences:,}"
                 f"  ({100.0*blank_occurrences/total_slots:.1f}% of slots)")
    lines.append(f"Distinct values      : {distinct}")
    lines.append(f"Top-20 coverage      : {top20_sum:,} / {non_blank_total:,}"
                 f"  = {top20_pct:.1f}% of non-blank occurrences")
    lines.append("")
    lines.append("-" * 68)
    lines.append(f"{'count':>10}  {'pct':>6}  value")
    lines.append("-" * 68)
    for val, c in ranked:
        pct = 100.0 * c / non_blank_total if non_blank_total else 0.0
        shown = repr(val) if (val != val.strip() or " " in val) else val
        lines.append(f"{c:>10}  {pct:>5.1f}%  {shown}")
    lines.append("-" * 68)
    lines.append("")
    lines.append("Per-file (rows, non-blank past_race_type values):")
    for name in sorted(per_file):
        r, nb = per_file[name]
        lines.append(f"  {name:<20} rows={r:>5}  non-blank={nb:>6}")

    report = "\n".join(lines)
    with open(txt_path, "w") as out:
        out.write(report + "\n")

    print(report)
    print()
    print(f"[written] {txt_path}")
    print(f"[written] {csv_path}")


if __name__ == "__main__":
    main()
