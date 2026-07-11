"""
CM1 pace/distance-fit probe (Cat-3) — reads BRIS DRF past-performance running lines
to detect Harry's "led to 5F then faded in a route → cut back to a sprint" angle, and
its mirror "closed late in a sprint → stretch out to a route".

Purpose: calibrate the Q3 thresholds (how many positions = "faded" / "closed", and
whether to restrict to same-surface past lines) against real PP data. No R5 imports.

PP field blocks (1-indexed schema; 10 slots each, most-recent first):
  today distance f6 (yards, neg = "about"), today surface f7
  316-325 past distance (yd)   326-335 past surface
  566-575 start pos  576-585 1st-call pos  586-595 2nd-call pos
  606-615 stretch pos  616-625 finish pos
  736-745 finish beaten lengths (winner's margin)

Usage:
  python3 comparemodels/cm1_pace_fit.py "files 2/SAR07"*.DRF          # scan + calibrate
  python3 comparemodels/cm1_pace_fit.py --show "files 2/SAR0710.DRF"  # per-horse detail
"""

import csv
import sys
import glob
from collections import Counter

F_TODAY_DIST = 6
F_TODAY_SURF = 7
PP = {
    "dist": 316, "surf": 326,
    "p_start": 566, "p_1c": 576, "p_2c": 586, "p_str": 606, "p_fin": 616,
    "btn_fin": 736,
}
N_PP = 10

# calibration defaults (the Q3 red-line knobs) — TIGHTENED after 8-card scan
FADE_POS   = 4     # lost >= this many positions (2-3 is drift/noise; 4+ = collapse)
CLOSE_POS  = 5     # gained >= this many positions (3-4 is ordinary closing style)
LED_MAX    = 2     # "showed early speed" = best early-call position <= this
BACK_MIN   = 5     # "off the pace" = early position >= this
DIST_GAP_F = 1.5   # today must differ from past by >= this many furlongs (1F = nudge)
SAME_SURFACE_ONLY = True   # pace shape doesn't transfer across dirt/turf


def _surf_class(s):
    s = (s or "").strip().upper()
    if s.startswith("D"):
        return "D"
    if s.startswith("T"):
        return "T"
    if s.startswith("A"):
        return "A"
    return s


def _pos(v):
    v = (v or "").strip()
    # positions are chars like "1", "10", sometimes with dead-heat marks; take leading int
    n = ""
    for ch in v:
        if ch.isdigit():
            n += ch
        elif n:
            break
    return int(n) if n else None


def _furlongs(yd):
    try:
        return abs(int(yd)) / 220.0
    except (ValueError, TypeError):
        return None


def extract(drf_path):
    """Yield (horse, today_f, today_surf, [pp_line,...]) per horse."""
    for r in csv.reader(open(drf_path, newline="")):
        if len(r) < 766:
            continue
        horse = r[44].strip()
        today_f = _furlongs(r[F_TODAY_DIST - 1])
        today_surf = r[F_TODAY_SURF - 1].strip()
        lines = []
        for i in range(N_PP):
            d = _furlongs(r[PP["dist"] - 1 + i])
            if not d:
                continue
            lines.append({
                "f": d,
                "surf": r[PP["surf"] - 1 + i].strip(),
                "start": _pos(r[PP["p_start"] - 1 + i]),
                "c1": _pos(r[PP["p_1c"] - 1 + i]),
                "c2": _pos(r[PP["p_2c"] - 1 + i]),
                "str": _pos(r[PP["p_str"] - 1 + i]),
                "fin": _pos(r[PP["p_fin"] - 1 + i]),
                "btn_fin": (r[PP["btn_fin"] - 1 + i] or "").strip(),
            })
        yield horse, today_f, today_surf, lines


def classify(line):
    """Return ('faded'|'closed'|'even'|None, magnitude) for one past line."""
    early = [p for p in (line["c1"], line["c2"]) if p]
    if not early or not line["fin"]:
        return None, 0
    best_early = min(early)
    fin = line["fin"]
    # faded from speed: led/pressed early, lost ground to the wire
    if best_early <= LED_MAX and (fin - best_early) >= FADE_POS:
        return "faded", fin - best_early
    # closed: off the pace early, gained to the wire
    start_or_c1 = line["start"] or line["c1"]
    if start_or_c1 and start_or_c1 >= BACK_MIN and (start_or_c1 - fin) >= CLOSE_POS:
        return "closed", start_or_c1 - fin
    return "even", 0


def scan(paths):
    faded_gaps, close_gaps = Counter(), Counter()
    cutback_fit = []   # faded in a race LONGER than today
    stretch_fit = []   # closed in a race SHORTER than today
    n_horses = 0
    for p in paths:
        for horse, tf, tsurf, lines in extract(p):
            n_horses += 1
            for ln in lines[:6]:               # recent 6 starts
                kind, mag = classify(ln)
                same_surf = _surf_class(ln["surf"]) == _surf_class(tsurf)
                surf_ok = same_surf or not SAME_SURFACE_ONLY
                if kind == "faded":
                    faded_gaps[mag] += 1
                    if tf and ln["f"] - tf >= DIST_GAP_F and surf_ok:
                        cutback_fit.append((horse, ln["f"], tf, mag,
                                            ln["surf"], tsurf))
                elif kind == "closed":
                    close_gaps[mag] += 1
                    if tf and tf - ln["f"] >= DIST_GAP_F and surf_ok:
                        stretch_fit.append((horse, ln["f"], tf, mag,
                                            ln["surf"], tsurf))

    print(f"Scanned {n_horses} horses / {len(paths)} cards\n")
    print("Fade magnitude (positions lost, led→wire):")
    for g in sorted(faded_gaps):
        print(f"  lost {g:>2} pos: {'#'*faded_gaps[g]} ({faded_gaps[g]})")
    print("\nClose magnitude (positions gained, back→wire):")
    for g in sorted(close_gaps):
        print(f"  gain {g:>2} pos: {'#'*close_gaps[g]} ({close_gaps[g]})")

    print(f"\n▼ CUT-BACK SPRINT FITS  (faded from speed in a race longer than today) "
          f"— {len(cutback_fit)} hits")
    for h, pf, tf, mag, ps, ts in cutback_fit[:20]:
        sm = "" if ps == ts else f"  [surf {ps}→{ts}]"
        print(f"   {h:<22} faded {mag}p @ {pf:.1f}F → today {tf:.1f}F{sm}")

    print(f"\n▲ STRETCH-OUT ROUTE FITS  (closed in a race shorter than today) "
          f"— {len(stretch_fit)} hits")
    for h, pf, tf, mag, ps, ts in stretch_fit[:20]:
        sm = "" if ps == ts else f"  [surf {ps}→{ts}]"
        print(f"   {h:<22} closed {mag}p @ {pf:.1f}F → today {tf:.1f}F{sm}")


def show(paths):
    for p in paths:
        for horse, tf, tsurf, lines in extract(p):
            tag = f"today {tf:.1f}F {tsurf}" if tf else "today ?"
            print(f"\n{horse}  ({tag})")
            for ln in lines[:6]:
                kind, mag = classify(ln)
                flag = {"faded": "▼faded", "closed": "▲closed"}.get(kind, "")
                print(f"   {ln['f']:>4.1f}F {ln['surf']:2} "
                      f"pos[{ln['start'] or '-':>2}/{ln['c1'] or '-':>2}/"
                      f"{ln['c2'] or '-':>2}/{ln['str'] or '-':>2}/{ln['fin'] or '-':>2}] "
                      f"btn {ln['btn_fin']:>5}  {flag}{(' '+str(mag)) if mag else ''}")


if __name__ == "__main__":
    args = sys.argv[1:]
    do_show = "--show" in args
    args = [a for a in args if a != "--show"]
    paths = []
    for a in args:
        paths.extend(glob.glob(a))
    if not paths:
        print("no DRF files matched", file=sys.stderr)
        sys.exit(1)
    (show if do_show else scan)(paths)
