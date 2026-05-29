"""
CompareModels scoring engine — BRIS Summary methodology.
No imports from R5 modules.
"""

import csv
from collections import defaultdict

CATEGORY_WEIGHTS = {
    "Avg Speed":      3,
    "Distance Speed": 2,
    "Best Speed":     2,
    "Prime Power":    3,
    "Avg Class":      2,
    "Jockey Rating":  1,
    "Trainer Rating": 1,
    "Earnings":       1,
}

# CSV column → category name
COLUMN_MAP = {
    "avg_speed":      "Avg Speed",
    "distance_speed": "Distance Speed",
    "best_speed":     "Best Speed",
    "prime_power":    "Prime Power",
    "avg_class":      "Avg Class",
    "jockey_rating":  "Jockey Rating",
    "trainer_rating": "Trainer Rating",
    "earnings":       "Earnings",
}

EARLY_PACE_COL = "early_pace"
LATE_PACE_COL  = "late_pace"


def _safe_float(val):
    if val is None or str(val).strip() == '':
        return None
    try:
        f = float(val)
        # treat 0.0 from distance_speed/best_speed as missing
        return f if f != 0.0 else None
    except Exception:
        return None


def score_race(race_df: list[dict]) -> dict:
    """
    race_df: list of horse dicts (one per horse in the race).
    Returns scoring dict per spec Section 7.
    """
    # composite scores and per-horse metadata
    composite = defaultdict(int)          # pgm → composite int
    consensus = defaultdict(int)          # pgm → count of top-3 cat appearances
    underlined_cats = defaultdict(set)    # pgm → set of categories where underlined

    category_picks = {}   # cat_name → [{"pgm", "name", "raw_value", "rank_in_cat", "underlined"}, ...]

    horses = {h['pgm'].strip(): h for h in race_df}

    # --- Score each category ---
    for col, cat in COLUMN_MAP.items():
        weight = CATEGORY_WEIGHTS[cat]

        # Build (pgm, value) pairs skipping nulls
        pairs = []
        for h in race_df:
            v = _safe_float(h.get(col))
            if v is not None:
                pairs.append((h['pgm'].strip(), v))

        if not pairs:
            category_picks[cat] = []
            continue

        # Sort descending (higher = better for all categories)
        pairs.sort(key=lambda x: x[1], reverse=True)
        sorted_values = [p[1] for p in pairs]
        top3 = pairs[:3]

        # Underline rule: ≥3 non-null values AND gap[0]−[2] ≥ 2.0
        underline_pgm = None
        if len(sorted_values) >= 3 and (sorted_values[0] - sorted_values[2]) >= 2.0:
            underline_pgm = top3[0][0]

        cat_result = []
        for rank_idx, (pgm, val) in enumerate(top3):
            pts = max(weight - rank_idx, 0)
            composite[pgm] += pts
            consensus[pgm] += 1
            underlined = (pgm == underline_pgm)
            if underlined:
                underlined_cats[pgm].add(cat)
            cat_result.append({
                "pgm": pgm,
                "name": horses[pgm]['horse_name'].strip() if pgm in horses else pgm,
                "raw_value": val,
                "rank_in_cat": rank_idx + 1,
                "underlined": underlined,
            })

        category_picks[cat] = cat_result

    # BRIS Top Pick bonus (+2) — applied once, after category loop
    for h in race_df:
        tp = _safe_float(h.get('bris_top_pick'))
        if tp:
            composite[h['pgm'].strip()] += 2

    # --- Pace leaders ---
    pace_pairs_e = [(h['pgm'].strip(), _safe_float(h.get(EARLY_PACE_COL)))
                    for h in race_df if _safe_float(h.get(EARLY_PACE_COL)) is not None]
    pace_pairs_l = [(h['pgm'].strip(), _safe_float(h.get(LATE_PACE_COL)))
                    for h in race_df if _safe_float(h.get(LATE_PACE_COL)) is not None]

    early_pace_leader = max(pace_pairs_e, key=lambda x: x[1])[0] if pace_pairs_e else None
    late_pace_leader  = max(pace_pairs_l, key=lambda x: x[1])[0] if pace_pairs_l else None

    # --- Derive dominant flag (in-memory, before any DB write) ---
    dominant_pgms = {
        pgm for pgm in consensus
        if consensus[pgm] >= 4 and len(underlined_cats[pgm]) >= 1
    }

    # --- Rank horses by composite descending ---
    all_pgms = list(horses.keys())
    # ensure every horse appears even if score=0
    for pgm in all_pgms:
        if pgm not in composite:
            composite[pgm] = 0

    ranked = sorted(all_pgms, key=lambda p: composite[p], reverse=True)

    ranked_horses = []
    for rank_idx, pgm in enumerate(ranked):
        rank = rank_idx + 1
        comp = composite[pgm]
        cons = consensus[pgm]
        ml = _safe_float(horses[pgm].get('morning_line'))

        # Tier
        if rank == 1:
            tier = 'A'
        elif rank <= 4:
            tier = 'B'
        elif rank <= 7:
            tier = 'C'
        else:
            tier = 'C'

        is_dominant = pgm in dominant_pgms
        is_bris_pick = bool(_safe_float(horses[pgm].get('bris_top_pick')))
        is_overlay = cons >= 5 and ml is not None and ml >= 6.0
        is_early_pace_leader = pgm == early_pace_leader
        is_late_pace_leader  = pgm == late_pace_leader

        ranked_horses.append({
            "pgm":                   pgm,
            "name":                  horses[pgm]['horse_name'].strip(),
            "composite":             comp,
            "rank":                  rank,
            "tier":                  tier,
            "consensus_count":       cons,
            "is_dominant":           is_dominant,
            "is_bris_pick":          is_bris_pick,
            "is_overlay":            is_overlay,
            "is_early_pace_leader":  is_early_pace_leader,
            "is_late_pace_leader":   is_late_pace_leader,
        })

    race_num = int(str(race_df[0]['race']).strip()) if race_df else 0

    return {
        "race":             race_num,
        "ranked_horses":    ranked_horses,
        "category_picks":   category_picks,
        "early_pace_leader": early_pace_leader,
        "late_pace_leader":  late_pace_leader,
    }


def score_card(csv_path: str) -> dict:
    """
    Load a CompareModels CSV (with # comment header lines) and score each race.
    Returns {race_num: score_race_output, ...}
    """
    rows = []
    with open(csv_path, 'r') as f:
        # skip comment lines
        data_lines = [l for l in f if not l.startswith('#')]
    reader = csv.DictReader(data_lines)
    for row in reader:
        rows.append(row)

    # Group by race number
    races = defaultdict(list)
    for row in rows:
        rn = int(str(row['race']).strip())
        races[rn].append(row)

    results = {}
    for race_num in sorted(races.keys()):
        results[race_num] = score_race(races[race_num])

    return results
