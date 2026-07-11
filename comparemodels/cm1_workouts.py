"""
CM1 workout probe — extracts published workout lines from BRIS single-file DRF
and reports the time distribution by distance / surface / track, so we can decide
whether Harry's sharp-work thresholds (3F<36, 4F<48, 5F<1:00) are UNIVERSAL or
must be SURFACE/TRACK-RELATIVE.

This is the Category-1 (Workout Sharpness) data foundation for CM1_SPEC_DRAFT.md,
plus a standalone diagnostic. No R5 imports; read-only on DRF files.

Usage:
    python3 comparemodels/cm1_workouts.py "files 2/SAR07"*.DRF
    python3 comparemodels/cm1_workouts.py --dump "files 2/SAR0710.DRF"   # per-work rows
"""

import csv
import sys
import glob
import statistics as st
from collections import defaultdict

# --- BRIS single-file workout field blocks (1-indexed schema → 0-indexed here) ---
# 12 workout slots per horse.
WKO_DATE  = 102   # f102-113
WKO_TIME  = 114   # f114-125  seconds; leading '-' == bullet (best of day at dist)
WKO_TRACK = 126   # f126-137
WKO_DIST  = 138   # f138-149  yards
WKO_COND  = 150   # f150-161  ft/fm/gd/sf/my/sy/sl/hy/wf
WKO_DESC  = 162   # f162-173  1st char B=breeze/H=handily; 'g'=from gate; 'D'=dogs up
WKO_TIND  = 174   # f174-185  MT-main dirt IM-inner dirt TT-training T-main turf IT-inner turf
N_SLOTS   = 12

# Harry's checklist thresholds (dirt/fast-track breeze standard), seconds
SHARP = {3: 36.0, 4: 48.0, 5: 60.0}

TURF_INDS = {"T", "IT", "TN"}   # main/inner turf (TN = observed variant)
TURF_CONDS = {"fm", "sf", "yl"}          # firm / soft / yielding = turf
OFF_CONDS = {"gd", "my", "sy", "sl", "hy", "wf"}  # not-fast


def _yards_to_furlongs(yds):
    try:
        return round(int(yds) / 220.0)
    except (ValueError, TypeError):
        return None


def _parse_time(raw):
    """Return (seconds:float|None, bullet:bool). BRIS uses plain seconds even >60."""
    s = (raw or "").strip()
    if not s:
        return None, False
    bullet = s.startswith("-")
    s = s.lstrip("-")
    try:
        return float(s), bullet
    except ValueError:
        return None, False


def _surface(tind, cond):
    if tind in TURF_INDS or cond in TURF_CONDS:
        return "turf"
    if tind == "TT":
        return "training"          # main-track training oval (dirt), separate clock
    return "dirt"                  # MT / main


def extract_works(drf_path):
    """Yield one dict per published work across all horses in a card."""
    for row in csv.reader(open(drf_path, newline="")):
        if len(row) < WKO_TIND + N_SLOTS - 1:
            continue
        try:
            horse = row[44].strip()   # 0-idx col 44 = horse name; label only
        except IndexError:
            horse = ""
        for i in range(N_SLOTS):
            secs, bullet = _parse_time(row[WKO_TIME - 1 + i])
            if secs is None:
                continue
            furl = _yards_to_furlongs(row[WKO_DIST - 1 + i])
            cond = row[WKO_COND - 1 + i].strip()
            tind = row[WKO_TIND - 1 + i].strip()
            desc = row[WKO_DESC - 1 + i].strip()
            yield {
                "horse": horse,
                "date": row[WKO_DATE - 1 + i].strip(),
                "track": row[WKO_TRACK - 1 + i].strip(),
                "furlongs": furl,
                "secs": secs,
                "bullet": bullet,
                "cond": cond,
                "tind": tind,
                "desc": desc,
                "gate": "g" in desc,
                "handily": desc.startswith("H"),
                "surface": _surface(tind, cond),
                "fast": cond == "ft",
            }


def _pctile(vals, q):
    if not vals:
        return None
    vals = sorted(vals)
    k = (len(vals) - 1) * q
    lo = int(k)
    return vals[lo] if lo == len(vals) - 1 else vals[lo] + (k - lo) * (vals[lo + 1] - vals[lo])


def report(paths):
    works = []
    for p in paths:
        works.extend(extract_works(p))
    print(f"Parsed {len(works)} workouts from {len(paths)} card(s)\n")

    # Bucket by (furlongs, surface, fast/off) — only the distances Harry watches + neighbors
    buckets = defaultdict(list)
    for w in works:
        if w["furlongs"] in (3, 4, 5, 6):
            key = (w["furlongs"], w["surface"], "fast" if w["fast"] else "off")
            buckets[key].append(w["secs"])

    print(f"{'Dist':>4} {'Surface':<9} {'Cond':<5} {'N':>4} "
          f"{'min':>6} {'p10':>6} {'p25':>6} {'med':>6} "
          f"{'thresh':>7} {'%<thr':>7}")
    print("-" * 68)
    for key in sorted(buckets):
        furl, surf, cond = key
        v = buckets[key]
        thr = SHARP.get(furl)
        pct_under = 100 * sum(1 for x in v if thr and x < thr) / len(v) if thr else None
        print(f"{furl:>3}F {surf:<9} {cond:<5} {len(v):>4} "
              f"{min(v):>6.1f} {_pctile(v,.10):>6.1f} {_pctile(v,.25):>6.1f} "
              f"{st.median(v):>6.1f} "
              f"{('<'+str(thr)) if thr else '   -':>7} "
              f"{(f'{pct_under:.0f}%') if pct_under is not None else '  -':>7}")

    # Q1 verdict: compare fast-dirt vs turf vs training median at each watched distance
    print("\nQ1 — is one threshold universal? median seconds by surface:")
    for furl in (3, 4, 5):
        row = {s: buckets.get((furl, s, "fast")) or buckets.get((furl, s, "off"))
               for s in ("dirt", "turf", "training")}
        meds = {s: (st.median(v) if v else None) for s, v in row.items()}
        parts = "  ".join(f"{s}={meds[s]:.1f}" if meds[s] else f"{s}=--"
                          for s in ("dirt", "turf", "training"))
        print(f"  {furl}F (thr {SHARP[furl]}):  {parts}")


def dump(paths):
    for p in paths:
        for w in extract_works(p):
            flag = "★" if w["bullet"] else " "
            print(f"{flag} {w['date']} {w['track']} {w['furlongs']}F "
                  f"{w['secs']:6.1f} {w['cond']:<3} {w['tind']:<3} {w['desc']:<4} "
                  f"{w['surface']:<9} {w['horse']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    do_dump = "--dump" in args
    args = [a for a in args if a != "--dump"]
    paths = []
    for a in args:
        paths.extend(glob.glob(a))
    if not paths:
        print("no DRF files matched", file=sys.stderr)
        sys.exit(1)
    (dump if do_dump else report)(paths)
