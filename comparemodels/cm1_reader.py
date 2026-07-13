"""
CM1 reader — single-pass extraction of every field CM1's six categories need from a
BRIS single-file DRF. Read-only; no R5/CM imports; no writes.

One `extract_card()` call returns per-horse dicts grouped by race, each carrying the raw
blocks the scorers consume (workouts, trainer/jockey angles, PP running lines, pedigree,
class). Field numbers are 1-indexed per Schema/June2026Schema.txt; DRF rows are 0-indexed,
so field N lives at row[N-1]. Program number = f4, horse name = f45 (matches r5_parser_v2
and drf_reader).

Usage:
    python3 comparemodels/cm1_reader.py "files 2/SAR0712.DRF"          # summary
    python3 comparemodels/cm1_reader.py --horse 1 "files 2/SAR0712.DRF"  # dump race 1
"""

import csv
import sys

# ── identity ────────────────────────────────────────────────────────────────
F_TRACK, F_DATE, F_RACE, F_PGM = 1, 2, 3, 4
F_AE, F_ML, F_NAME, F_SEX, F_PROG_POST = 41, 44, 45, 49, 58

# ── today's race (Cat-7 class + Cat-3 distance/surface) ──────────────────────
F_TODAY_TYPE, F_TODAY_CLASS, F_TODAY_PURSE = 9, 11, 12
F_TODAY_DIST_Y, F_TODAY_SURF = 6, 7
F_TODAY_LOW_CLAIM = 238          # today's low claiming price (NOT f1202 — that's past)

# ── pedigree (Cat-5) ─────────────────────────────────────────────────────────
F_SIRE, F_SIRE_SIRE, F_DAM, F_DAM_SIRE = 52, 53, 54, 55
F_PED_DIRT, F_PED_MUD, F_PED_TURF, F_PED_DIST = 1264, 1265, 1266, 1267

# ── workouts (Cat-1): 12 slots ───────────────────────────────────────────────
F_WKO_DATE, F_WKO_TIME, F_WKO_TRACK = 102, 114, 126
F_WKO_DIST, F_WKO_COND, F_WKO_DESC, F_WKO_TIND = 138, 150, 162, 174
N_WKO = 12

# ── connections (Cat-2) ──────────────────────────────────────────────────────
F_TRN_ANGLE_BASE = 1337          # 6 angles × 5 fields: label,starts,win%,itm%,$2roi
N_TRN_ANGLES, TRN_STRIDE = 6, 5
F_JKY_BASE = 1367                # label,starts,W,P,S,$2roi (6 fields)

# ── past performance running lines (Cat-3 / Cat-7): 10 slots ─────────────────
F_PP_DIST, F_PP_SURF = 316, 326
F_PP_START_POS, F_PP_1C_POS, F_PP_2C_POS = 566, 576, 586
F_PP_STRETCH_POS, F_PP_FINISH_POS = 606, 616
F_PP_FIN_BEATEN = 736
F_PP_RACE_CLASS, F_PP_HORSE_CLAIM, F_PP_PURSE = 536, 546, 556
F_PP_RACE_TYPE = 1086            # past race type code (see f9)
F_PP_RACE_LOWCLAIM, F_PP_RACE_HIGHCLAIM = 1202, 1212  # race band (per-PP, 10 slots)
N_PP = 10

# ── speed backbone (Cat-6) ───────────────────────────────────────────────────
F_BRIS_SPEED = 846               # last-10 BRIS speed (10 slots)
F_BEST_TURF, F_BEST_DIST = 1179, 1181


def _s(row, f):
    """Stripped string at 1-indexed field f, or '' if absent."""
    try:
        return (row[f - 1] or "").strip()
    except IndexError:
        return ""


def _num(row, f):
    """Float at field f, or None. Strips commas AND a trailing '*' (BRIS ped
    ratings like '115*' would otherwise silently None-out)."""
    v = _s(row, f).replace(",", "").rstrip("*")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _block_s(row, base, n):
    return [_s(row, base + i) for i in range(n)]


def _block_num(row, base, n):
    return [_num(row, base + i) for i in range(n)]


def extract_horse(row):
    """One raw dict per horse row. Scorers consume these blocks; no scoring here."""
    if len(row) < F_PED_DIST:            # too short to be a full DRF line
        return None
    pgm = _s(row, F_PGM)
    if not pgm:
        return None

    # trainer angles: 6 × {label,starts,win%,itm%,roi}
    trn_angles = []
    for i in range(N_TRN_ANGLES):
        b = F_TRN_ANGLE_BASE + i * TRN_STRIDE
        label = _s(row, b)
        if not label:
            continue
        trn_angles.append({
            "label":   label,
            "starts":  _num(row, b + 1),
            "win_pct": _num(row, b + 2),
            "itm_pct": _num(row, b + 3),
            "roi":     _num(row, b + 4),   # $2 ROI = net profit per $2 (−2.00 = total loss)
        })
    jky = {
        "label":  _s(row, F_JKY_BASE),
        "starts": _num(row, F_JKY_BASE + 1),
        "wins":   _num(row, F_JKY_BASE + 2),
        "places": _num(row, F_JKY_BASE + 3),
        "shows":  _num(row, F_JKY_BASE + 4),
        "roi":    _num(row, F_JKY_BASE + 5),
    }

    # workouts: 12 slots (only populated ones)
    works = []
    for i in range(N_WKO):
        t = _s(row, F_WKO_TIME + i)
        if not t:
            continue
        works.append({
            "date":  _s(row, F_WKO_DATE + i),
            "time":  t,                     # leading '-' = bullet; parse in scorer
            "track": _s(row, F_WKO_TRACK + i),
            "dist_y": _num(row, F_WKO_DIST + i),
            "cond":  _s(row, F_WKO_COND + i),
            "desc":  _s(row, F_WKO_DESC + i),
            "tind":  _s(row, F_WKO_TIND + i),
        })

    # past performance lines: 10 slots
    pp = []
    for i in range(N_PP):
        rtype = _s(row, F_PP_RACE_TYPE + i)
        dist  = _num(row, F_PP_DIST + i)
        if not rtype and dist is None:
            continue
        pp.append({
            "race_type":  rtype,
            "class_text": _s(row, F_PP_RACE_CLASS + i),
            "race_low_claim":  _num(row, F_PP_RACE_LOWCLAIM + i),
            "race_high_claim": _num(row, F_PP_RACE_HIGHCLAIM + i),
            "horse_claim": _num(row, F_PP_HORSE_CLAIM + i),
            "purse":      _num(row, F_PP_PURSE + i),
            "dist_y":     dist,
            "surface":    _s(row, F_PP_SURF + i),
            "start_pos":  _num(row, F_PP_START_POS + i),
            "call1_pos":  _num(row, F_PP_1C_POS + i),
            "call2_pos":  _num(row, F_PP_2C_POS + i),
            "stretch_pos": _num(row, F_PP_STRETCH_POS + i),
            "finish_pos": _num(row, F_PP_FINISH_POS + i),
            "fin_beaten": _num(row, F_PP_FIN_BEATEN + i),
        })

    return {
        # identity
        "track": _s(row, F_TRACK), "date": _s(row, F_DATE),
        "race":  _s(row, F_RACE),  "pgm": pgm,
        "name":  _s(row, F_NAME),  "sex": _s(row, F_SEX),
        "ml_odds": _num(row, F_ML), "ae": _s(row, F_AE),
        "program_post": _s(row, F_PROG_POST),
        "trainer": _s(row, 28), "jockey": _s(row, 33),   # today's connections
        # today's race
        "today_type": _s(row, F_TODAY_TYPE),
        "today_class": _s(row, F_TODAY_CLASS),
        "today_purse": _num(row, F_TODAY_PURSE),
        "today_low_claim": _num(row, F_TODAY_LOW_CLAIM),
        "today_dist_y": _num(row, F_TODAY_DIST_Y),
        "today_surf": _s(row, F_TODAY_SURF),
        # pedigree (Cat-5)
        "sire": _s(row, F_SIRE), "sire_sire": _s(row, F_SIRE_SIRE),
        "dam": _s(row, F_DAM),   "dam_sire": _s(row, F_DAM_SIRE),
        "ped_dirt": _num(row, F_PED_DIRT), "ped_mud": _num(row, F_PED_MUD),
        "ped_turf": _num(row, F_PED_TURF), "ped_dist": _num(row, F_PED_DIST),
        # blocks
        "trn_angles": trn_angles, "jky": jky, "works": works, "pp": pp,
        # speed (Cat-6)
        "bris_speed": _block_num(row, F_BRIS_SPEED, N_PP),
        "best_turf": _num(row, F_BEST_TURF), "best_dist": _num(row, F_BEST_DIST),
    }


def extract_card(drf_path, include_scratched=False):
    """Return {race_num: [horse dict, ...]} for one DRF file."""
    races = {}
    with open(drf_path, newline="") as fh:
        for row in csv.reader(fh):
            h = extract_horse(row)
            if h is None:
                continue
            if not include_scratched and h["ae"] in ("A",):   # also-eligible; keep MTO
                pass
            races.setdefault(h["race"], []).append(h)
    return dict(sorted(races.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))


def _summary(path):
    card = extract_card(path)
    nh = sum(len(v) for v in card.values())
    print(f"{path}\n  races: {len(card)}  horses: {nh}")
    for rn, hs in card.items():
        wk = sum(len(h["works"]) for h in hs)
        ang = sum(len(h["trn_angles"]) for h in hs)
        print(f"  R{rn:>2}: {len(hs):>2} horses | {wk:>3} works | {ang:>3} trn-angles")


def _dump_race(path, rnum):
    card = extract_card(path)
    for h in card.get(str(rnum), []):
        print(f"\n#{h['pgm']:>2} {h['name']:<20} ML {h['ml_odds']}")
        print(f"   today: {h['today_type']} '{h['today_class']}' purse {h['today_purse']} "
              f"lowclaim {h['today_low_claim']} {h['today_dist_y']}y {h['today_surf']}")
        print(f"   ped: sire={h['sire']} damsire={h['dam_sire']} dam={h['dam']} "
              f"| dirt {h['ped_dirt']} turf {h['ped_turf']} mud {h['ped_mud']} dist {h['ped_dist']}")
        print(f"   works={len(h['works'])} angles={len(h['trn_angles'])} pp={len(h['pp'])} "
              f"jky={h['jky']['label']} roi={h['jky']['roi']}")
        if h["pp"]:
            p = h["pp"][0]
            print(f"   last PP: {p['race_type']} '{p['class_text']}' {p['dist_y']}y {p['surface']} "
                  f"fin {p['finish_pos']} (start {p['start_pos']})")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--horse":
        _dump_race(args[2], args[1])
    elif args:
        for p in args:
            _summary(p)
    else:
        print(__doc__)
