"""
CM1 engine — scores the six categories per horse, assembles the composite, and ranks
the field. Consumes cm1_reader horse dicts; read-only; no R5/CM imports.

Category status (2026-07-12):
  Cat-1 Workouts (5)      — TODO scorer (extractor exists in cm1_workouts.py)
  Cat-2 Connections (6)   — TODO scorer (rules settled: ROI-gated +3/+2 only)
  Cat-3 Pace/dist fit (4) — TODO scorer (classifier exists in cm1_pace_fit.py)
  Cat-5 Pedigree (v0 ≤2)  — TODO scorer (reduced: turf/mud ped + debut-carries)
  Cat-6 Speed (tie-break) — TODO scorer (demoted backbone)
  Cat-7 Class move (2)    — ✅ IMPLEMENTED below (validated tier map)

Usage:
    python3 comparemodels/cm1_engine.py "files 2/SAR0712.DRF"          # Cat-7 per horse
    python3 comparemodels/cm1_engine.py --race 4 "files 2/SAR0712.DRF"
"""

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cm1_reader import extract_card   # noqa: E402

# ── Cat-7 validated race-type → class tier (derived from f9→f11 across 24 DRFs) ──
CLASS_TIER = {
    "G1": 9, "G2": 8, "G3": 7,
    "N": 6,                 # listed / nongraded stakes
    "A": 5,                 # allowance
    "AO": 5,                # allowance optional claiming (refine by claim)
    "R": 4,                 # restricted / statebred allowance
    "C": 3, "CO": 3,        # claiming / optional claiming (refine by claim)
    "S": 2,                 # MAIDEN SPECIAL WEIGHT (not stakes)
    "M": 1, "MO": 1,        # maiden claiming / maiden optional claiming
}
# codes deliberately excluded from the class-move baseline (non-flat / other)
CLASS_TIER_NEUTRAL = {"T", "HR", "HO", ""}
CLAIMING_CODES = {"C", "CO", "AO", "M", "MO"}   # tiers where claim price refines the move


def class_tier(code):
    """Return integer tier, None for neutral/excluded codes, or raise on unknown."""
    code = (code or "").strip().upper()
    if code in CLASS_TIER_NEUTRAL:
        return None
    if code not in CLASS_TIER:
        raise ValueError(f"unmapped race-type code {code!r} — Gate-0 must map it, "
                         f"not silently tier-0")
    return CLASS_TIER[code]


def _most_recent_pp(horse):
    """First PP line whose race type maps to a real tier (skips T/HR/HO)."""
    for p in horse["pp"]:
        try:
            if class_tier(p["race_type"]) is not None:
                return p
        except ValueError:
            continue          # unmapped past code — skip as a baseline, don't crash
    return None


def score_cat7(horse):
    """Class MOVE (max 2): today's tier vs the most-recent start's tier.
    Drop +2 (ask-why flag), same/lateral +1, step-up 0. Debut = 0 (no baseline)."""
    detail = {"points": 0, "flag": None, "today_tier": None, "recent_tier": None}
    t_today = class_tier(horse["today_type"])
    if t_today is None:
        return 0, detail                      # today's race not on the flat ladder
    detail["today_tier"] = t_today
    pp = _most_recent_pp(horse)
    if pp is None:
        detail["flag"] = "debut/no-baseline"
        return 0, detail                      # first-timer: no class move to score
    t_recent = class_tier(pp["race_type"])
    detail["recent_tier"] = t_recent

    if t_today < t_recent:
        detail.update(points=2, flag="drop (ask why)")
    elif t_today > t_recent:
        detail.update(points=0, flag="step-up")
    else:
        # same tier — for claiming-type races, the claim price is the real move
        if horse["today_type"].upper() in CLAIMING_CODES:
            c_today = horse["today_low_claim"]
            c_recent = pp["race_low_claim"]
            if c_today is not None and c_recent is not None:
                if c_today < c_recent:
                    detail.update(points=2, flag="claim-drop (ask why)")
                elif c_today > c_recent:
                    detail.update(points=0, flag="claim step-up")
                else:
                    detail.update(points=1, flag="lateral")
            else:
                detail.update(points=1, flag="lateral")
        else:
            detail.update(points=1, flag="lateral")
    return detail["points"], detail


# ── category stubs (return 0 until implemented) ──────────────────────────────
def score_cat1(horse, pool=None): return 0, {}          # Workouts
def score_cat2(horse):            return 0, {}          # Connections
def score_cat3(horse):            return 0, {}          # Pace/distance fit
def score_cat5(horse):            return 0, {}          # Pedigree v0
def score_cat6(horse, field):     return 0, {}          # Speed backbone (tie-break)


def score_horse(horse, field):
    """Per-horse category scores + composite. field = all horses in the race."""
    c1, d1 = score_cat1(horse)
    c2, d2 = score_cat2(horse)
    c3, d3 = score_cat3(horse)
    c5, d5 = score_cat5(horse)
    c6, d6 = score_cat6(horse, field)
    c7, d7 = score_cat7(horse)
    return {
        "pgm": horse["pgm"], "name": horse["name"],
        "cat1": c1, "cat2": c2, "cat3": c3, "cat5": c5, "cat6": c6, "cat7": c7,
        "composite": c1 + c2 + c3 + c5 + c7,   # cat6 is tie-break only, not summed
        "cat6_tiebreak": c6,
        "detail": {"cat7": d7},
    }


def score_race(horses):
    """Score every horse and rank descending by composite (cat6 breaks ties)."""
    scored = [score_horse(h, horses) for h in horses]
    scored.sort(key=lambda s: (s["composite"], s["cat6_tiebreak"]), reverse=True)
    for i, s in enumerate(scored, 1):
        s["cm1_rank"] = i
    return scored


def _run(path, only_race=None):
    for rn, horses in extract_card(path).items():
        if only_race and rn != str(only_race):
            continue
        print(f"\n=== R{rn} — Cat-7 class move ===")
        for h in horses:
            pts, d = score_cat7(h)
            print(f"  #{h['pgm']:>2} {h['name']:<20} {h['today_type']:>3} "
                  f"tier {str(d['today_tier']):>4} vs recent {str(d['recent_tier']):>4} "
                  f"→ Cat7 +{pts}  {d['flag'] or ''}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--race":
        _run(args[2], args[1])
    elif args:
        for p in args:
            _run(p)
    else:
        print(__doc__)
