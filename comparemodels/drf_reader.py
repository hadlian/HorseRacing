"""
comparemodels/drf_reader.py — Direct DRF parser for CompareModels.

Replaces the DRF → CSV → engine two-step with a single pass.
Returns horse dicts in the same format score_race() expects.

Field positions are 1-indexed per BRIS spec; accessed as parts[N-1].
All verified against June 2026 BRIS schema and Dennis's CDX0529 CSV.

Entry point:
    parse_drf(drf_path: str) -> list[dict]
"""

import statistics

# ── Track code normalisation ──────────────────────────────────────────────────
TRACK_MAP = {'CD': 'CDX', 'AP': 'APX', 'SA': 'SAX'}

def _normalise_track(raw: str) -> str:
    return TRACK_MAP.get(raw.strip().strip('"').upper(),
                         raw.strip().strip('"').upper())


# ── Field helpers ─────────────────────────────────────────────────────────────
def _f(parts, field_1indexed):
    """Return raw string at 1-indexed field position, or '' if out of range."""
    idx = field_1indexed - 1
    return parts[idx].strip().strip('"') if idx < len(parts) else ''


def _float(parts, field_1indexed):
    """Return float at 1-indexed field, or None."""
    s = _f(parts, field_1indexed)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _mean(parts, fields_1indexed):
    """Mean of 1-indexed fields, ignoring zeros and missing."""
    vals = [v for f in fields_1indexed
            if (v := _float(parts, f)) is not None and v > 0]
    return statistics.mean(vals) if vals else None


def _max(parts, fields_1indexed):
    """Max of 1-indexed fields, ignoring zeros and missing."""
    vals = [v for f in fields_1indexed
            if (v := _float(parts, f)) is not None and v > 0]
    return max(vals) if vals else None


def _parse_ml(parts, field_1indexed) -> float | None:
    s = _f(parts, field_1indexed)
    if not s:
        return None
    if '-' in s:
        try:
            a, b = s.split('-')
            return float(a) / float(b) + 1
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None


# ── Main parser ───────────────────────────────────────────────────────────────
def parse_drf(drf_path: str) -> list[dict]:
    """
    Parse a BRIS DRF file and return a list of horse dicts, one per line.

    Each dict contains:
        track, race_date, race, pgm, horse_name, morning_line,
        avg_speed, distance_speed, best_speed,
        prime_power, avg_class,
        jockey_rating, trainer_rating,
        earnings, early_pace, late_pace,
        bris_top_pick,
        _missing_fields  ← set of category keys with no data (for report notes)
    """
    horses = []

    with open(drf_path, 'r', errors='replace') as fh:
        for raw_line in fh:
            line = raw_line.rstrip('\n')
            if not line.strip():
                continue

            parts = line.split(',')

            # ── Identity ──────────────────────────────────────────────────────
            track      = _normalise_track(parts[0] if parts else '')
            race_date  = _f(parts, 2)
            race       = _f(parts, 3)
            pgm        = _f(parts, 4)
            horse_name = _f(parts, 45)   # field 45 (0-indexed: 44)
            morning_line = _parse_ml(parts, 44)  # field 44 (0-indexed: 43)

            # ── Speed metrics ─────────────────────────────────────────────────
            # Avg Speed: mean of BRIS speed figs per PP, fields 846-855
            avg_speed = _mean(parts, range(846, 856))

            # Distance Speed: field 1181
            distance_speed = _float(parts, 1181)
            if distance_speed is not None and distance_speed <= 0:
                distance_speed = None

            # Best Speed: field 1328 (Best BRIS Speed: Life)
            best_speed = _float(parts, 1328)
            if best_speed is not None and best_speed <= 0:
                best_speed = None

            # Prime Power: field 251
            prime_power = _float(parts, 251)
            if prime_power is not None and prime_power <= 0:
                prime_power = None

            # ── Class ─────────────────────────────────────────────────────────
            # Avg Class: mean of BRIS Class Rating per PP, fields 1167-1176
            avg_class = _mean(parts, range(1167, 1177))

            # ── Jockey Rating ────────────────────────────────────────────────
            # Primary: Current Year  field 1157=starts, 1158=wins
            # Fallback: Current Meet field   35=starts,   36=wins
            jockey_rating = None
            js_yr = _float(parts, 1157)
            jw_yr = _float(parts, 1158)
            if jw_yr is not None and js_yr is not None and js_yr >= 10:
                jockey_rating = (jw_yr / js_yr) * 100
            if jockey_rating is None:
                js_mt = _float(parts, 35)
                jw_mt = _float(parts, 36)
                if jw_mt is not None and js_mt is not None and js_mt >= 5:
                    jockey_rating = (jw_mt / js_mt) * 100

            # ── Trainer Rating ────────────────────────────────────────────────
            # Primary: Current Year  field 1147=starts, 1148=wins
            # Fallback: Current Meet field   29=starts,   30=wins
            trainer_rating = None
            ts_yr = _float(parts, 1147)
            tw_yr = _float(parts, 1148)
            if tw_yr is not None and ts_yr is not None and ts_yr >= 10:
                trainer_rating = (tw_yr / ts_yr) * 100
            if trainer_rating is None:
                ts_mt = _float(parts, 29)
                tw_mt = _float(parts, 30)
                if tw_mt is not None and ts_mt is not None and ts_mt >= 5:
                    trainer_rating = (tw_mt / ts_mt) * 100

            # ── Earnings ─────────────────────────────────────────────────────
            earnings = _float(parts, 101)
            if earnings is not None and earnings <= 0:
                earnings = None

            # ── Pace ──────────────────────────────────────────────────────────
            # Early Pace: max of BRIS Early Pace per PP, fields 766-785
            early_pace = _max(parts, range(766, 786))
            # Late Pace:  max of BRIS Late Pace per PP,  fields 816-825
            late_pace  = _max(parts, range(816, 826))

            # ── BRIS Top Pick: field not confirmed — skip bonus ───────────────
            bris_top_pick = None

            # ── Note which categories have no data ───────────────────────────
            missing = set()
            if avg_speed      is None: missing.add('Avg Speed')
            if distance_speed is None: missing.add('Distance Speed')
            if best_speed     is None: missing.add('Best Speed')
            if prime_power    is None: missing.add('Prime Power')
            if avg_class      is None: missing.add('Avg Class')
            if jockey_rating  is None: missing.add('Jockey Rating')
            if trainer_rating is None: missing.add('Trainer Rating')
            if earnings       is None: missing.add('Earnings')

            horses.append({
                'track':          track,
                'race_date':      race_date,
                'race':           race,
                'pgm':            pgm,
                'horse_name':     horse_name,
                'morning_line':   str(morning_line) if morning_line else '',
                'avg_speed':      str(avg_speed)      if avg_speed      is not None else '',
                'distance_speed': str(distance_speed) if distance_speed is not None else '',
                'best_speed':     str(best_speed)     if best_speed     is not None else '',
                'prime_power':    str(prime_power)    if prime_power    is not None else '',
                'avg_class':      str(avg_class)      if avg_class      is not None else '',
                'jockey_rating':  str(jockey_rating)  if jockey_rating  is not None else '',
                'trainer_rating': str(trainer_rating) if trainer_rating is not None else '',
                'earnings':       str(earnings)       if earnings       is not None else '',
                'early_pace':     str(early_pace)     if early_pace     is not None else '',
                'late_pace':      str(late_pace)      if late_pace      is not None else '',
                'bris_top_pick':  '',
                '_missing':       missing,
            })

    return horses
