"""
DRF → CompareModels CSV converter.
Field positions are 1-indexed per BRIS spec; accessed as parts[N-1].
NO imports from r5_parser_v2.py — positions are literal integers below.
"""

import csv
import os
import statistics

# Field position decisions (logged in CSV header):
#   Avg Class:   purse (field 12) — R5 confirmed not to use BRIS class rating fields
#   Early Pace:  pace_2f mean (fields 766-775), inverted (999.0 - raw)
#   Late Pace:   pace_late mean (fields 816-825), inverted (999.0 - raw)
#   BRIS Top Pick: NULL — field not confirmed; do NOT synthesize

TRACK_MAP = {
    'CD':  'CDX',
    'AP':  'APX',
    'SA':  'SAX',
}


def normalise_track(raw: str) -> str:
    t = raw.strip().strip('"').strip().upper()
    return TRACK_MAP.get(t, t)


def parse_ml(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip().strip('"')
    if not s:
        return None
    if '-' in s:
        parts = s.split('-')
        try:
            return float(parts[0]) / float(parts[1]) + 1
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None


def _safe_float(val, negate=False) -> float | None:
    if val is None:
        return None
    s = str(val).strip().strip('"')
    if not s:
        return None
    try:
        f = float(s)
        return -f if negate else f
    except Exception:
        return None


def _mean_fields(parts, indices) -> float | None:
    """Mean of 1-indexed DRF field positions (parts is 0-indexed list)."""
    vals = []
    for idx in indices:
        v = _safe_float(parts[idx - 1]) if idx - 1 < len(parts) else None
        if v is not None and v > 0:
            vals.append(v)
    if not vals:
        return None
    return statistics.mean(vals)


def _max_fields(parts, indices) -> float | None:
    """Max of 1-indexed DRF field positions (parts is 0-indexed list)."""
    vals = []
    for idx in indices:
        v = _safe_float(parts[idx - 1]) if idx - 1 < len(parts) else None
        if v is not None and v > 0:
            vals.append(v)
    if not vals:
        return None
    return max(vals)





def convert_drf_to_csv(drf_path: str, out_path: str) -> int:
    """
    Convert a BRIS DRF file to a CompareModels CSV.
    Returns the number of horse rows written.
    """
    field_notes = [
        "# Avg Class: mean of BRIS Class Rating per-PP fields 1166-1175 nonzero (verified vs Dennis CSV)",
        "# Early Pace: max of BRIS per-PP fields, 0-indexed cols 765-784 (verified vs Dennis CSV)",
        "# Late Pace: max of BRIS per-PP fields, 0-indexed cols 815-824 (verified vs Dennis CSV)",
        "# BRIS Top Pick: NULL — field not confirmed; +2 bonus skipped",
        "# LRL0516.csv: NOT used directly — raw DRF format; LRL0516.DRF used instead",
    ]

    COLUMNS = [
        'track', 'race_date', 'race', 'pgm', 'horse_name',
        'morning_line',
        'avg_speed', 'distance_speed', 'best_speed',
        'prime_power', 'avg_class',
        'jockey_rating', 'trainer_rating',
        'earnings',
        'early_pace', 'late_pace',
        'bris_top_pick',
    ]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    rows_written = 0
    with open(drf_path, 'r', errors='replace') as fin, \
         open(out_path, 'w', newline='') as fout:

        for note in field_notes:
            fout.write(note + '\n')

        writer = csv.DictWriter(fout, fieldnames=COLUMNS)
        writer.writeheader()

        for line in fin:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split(',')

            track = normalise_track(parts[0])
            race_date = parts[1].strip().strip('"')
            race = parts[2].strip()
            pgm = parts[3].strip()
            horse_name = parts[44].strip().strip('"') if len(parts) > 44 else ''

            morning_line = parse_ml(parts[43]) if len(parts) > 43 else None

            # Avg Speed: mean of fields 846-855 (0-indexed: 845-854)
            avg_speed = _mean_fields(parts, list(range(846, 856)))

            # Distance Speed: field 1181 (0-indexed: 1180)
            distance_speed = _safe_float(parts[1180]) if len(parts) > 1180 else None

            # Best Speed: field 1328 (0-indexed: 1327)
            best_speed = _safe_float(parts[1327]) if len(parts) > 1327 else None

            # Prime Power: field 251 (0-indexed: 250)
            prime_power = _safe_float(parts[250]) if len(parts) > 250 else None

            # Avg Class: mean of BRIS Class Rating per-PP, 0-indexed cols 1166-1175 nonzero
            avg_class = _mean_fields(parts, list(range(1167, 1177)))

            # Jockey Rating: wins=field 35, starts=field 36 (0-indexed: 34, 35)
            jockey_rating = None
            if len(parts) > 35:
                jw = _safe_float(parts[34])
                js = _safe_float(parts[35])
                if jw is not None and js is not None and js >= 5:
                    jockey_rating = (jw / js) * 100

            # Trainer Rating: wins=field 29, starts=field 30 (0-indexed: 28, 29)
            trainer_rating = None
            if len(parts) > 29:
                tw = _safe_float(parts[28])
                ts = _safe_float(parts[29])
                if tw is not None and ts is not None and ts >= 5:
                    trainer_rating = (tw / ts) * 100

            # Earnings: field 101 (0-indexed: 100)
            earnings = _safe_float(parts[100]) if len(parts) > 100 else None

            # Early Pace: max of BRIS Early Pace per-PP, 0-indexed cols 765-784
            early_pace = _max_fields(parts, list(range(766, 786)))

            # Late Pace: max of BRIS Late Pace per-PP, 0-indexed cols 815-824
            late_pace = _max_fields(parts, list(range(816, 826)))

            # BRIS Top Pick: NULL
            bris_top_pick = None

            writer.writerow({
                'track': track,
                'race_date': race_date,
                'race': race,
                'pgm': pgm,
                'horse_name': horse_name,
                'morning_line': morning_line,
                'avg_speed': avg_speed,
                'distance_speed': distance_speed,
                'best_speed': best_speed,
                'prime_power': prime_power,
                'avg_class': avg_class,
                'jockey_rating': jockey_rating,
                'trainer_rating': trainer_rating,
                'earnings': earnings,
                'early_pace': early_pace,
                'late_pace': late_pace,
                'bris_top_pick': bris_top_pick,
            })
            rows_written += 1

    return rows_written


def test_one_file(drf_path: str, out_path: str):
    """Quick test: convert one file and print first 3 rows."""
    n = convert_drf_to_csv(drf_path, out_path)
    print(f"Converted {n} rows → {out_path}")
    print("\nFirst 3 data rows:")
    with open(out_path, 'r') as f:
        lines = f.readlines()
    # skip comment lines
    data_lines = [l for l in lines if not l.startswith('#')]
    for l in data_lines[:4]:  # header + 3 rows
        print(l.rstrip())


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3:
        test_one_file(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python drf_to_csv.py <input.DRF> <output.csv>")
