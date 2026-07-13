"""
CM1 engine — the author's (Frank's) model as an EQUAL-WEIGHT FLAG COUNT.

Frank's morning-homework note is a human checklist, not a weighted scorer: it assigns no
points and no category weights. So CM1 v0 renders each of his nine signals as a binary FLAG
and ranks a horse by HOW MANY fire (every flag = 1, equal weight). The display shows which
flags fired. Weighting is a later, optional choice — never invented here.

    CM1_score = count of fired flags (0..9);  rank desc; ties broken by best speed.

Flag status (2026-07-12): LIVE = workout, class_drop, jockey_surf, speed, trainer_surf.
DEFERRED (score 0 until infra lands) = pace_fit (classifier wiring), jockey_hot +
trainer_hot (results tables), breeding (legendary lists).

Consumes cm1_reader dicts; read-only; no R5/CM imports.

Usage:
    python3 comparemodels/cm1_engine.py "files 2/SAR0712.DRF"
    python3 comparemodels/cm1_engine.py --race 4 "files 2/SAR0712.DRF"
"""

import os
import sqlite3
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cm1_reader import extract_card   # noqa: E402
import cm1_stats_db as stats          # noqa: E402

_STATS_CONN, _STATS_OK = None, None


def _stats():
    """Lazy read-only handle to cm1_stats.db; None if not seeded yet (flags → False)."""
    global _STATS_CONN, _STATS_OK
    if _STATS_OK is None:
        p = os.path.join(os.path.dirname(__file__), "cm1_stats.db")
        try:
            _STATS_CONN = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            _STATS_CONN.execute("SELECT 1 FROM perf_event LIMIT 1")
            _STATS_OK = True
        except Exception:
            _STATS_OK = False
    return _STATS_CONN if _STATS_OK else None

# ── Cat-7 validated race-type → class tier (derived from f9→f11 across 24 DRFs) ──
CLASS_TIER = {
    "G1": 9, "G2": 8, "G3": 7, "N": 6, "A": 5, "AO": 5, "R": 4,
    "C": 3, "CO": 3, "S": 2, "M": 1, "MO": 1,   # S = Maiden Special Weight, NOT stakes
}
CLASS_TIER_NEUTRAL = {"T", "HR", "HO", ""}
CLAIMING_CODES = {"C", "CO", "AO", "M", "MO"}

# angle gates (Q2 resolution)
STARTS_FLOOR = 30
TRN_WIN_MIN = 20.0
JKY_WIN_MIN = 18.0
SURFACE_ANGLES = {
    "D": {"Dirt starts", "Turf to Dirt"},
    "T": {"Turf starts", "Dirt to Turf", "1st on grass"},
    "A": {"Dirt starts"},
}

# Frank's workout clocks (seconds), by furlong
WORK_CLOCK = {3: 36.0, 4: 48.0, 5: 60.0}


def class_tier(code):
    code = (code or "").strip().upper()
    if code in CLASS_TIER_NEUTRAL:
        return None
    if code not in CLASS_TIER:
        raise ValueError(f"unmapped race-type code {code!r} — Gate-0 must map it")
    return CLASS_TIER[code]


def _most_recent_pp(horse):
    for p in horse["pp"]:
        try:
            if class_tier(p["race_type"]) is not None:
                return p
        except ValueError:
            continue
    return None


def class_move(horse):
    """+2 drop, +1 lateral, 0 step-up/debut (Cat-7). Returns (points, flag_text)."""
    t_today = class_tier(horse["today_type"])
    if t_today is None:
        return 0, None
    pp = _most_recent_pp(horse)
    if pp is None:
        return 0, "debut"
    t_recent = class_tier(pp["race_type"])
    if t_today < t_recent:
        return 2, "drop"
    if t_today > t_recent:
        return 0, "step-up"
    # same tier — claiming price is the real move
    if horse["today_type"].upper() in CLAIMING_CODES:
        ct, cr = horse["today_low_claim"], pp["race_low_claim"]
        if ct is not None and cr is not None:
            if ct < cr:
                return 2, "claim-drop"
            if ct > cr:
                return 0, "claim step-up"
    return 1, "lateral"


def _best_speed(h):
    return h["best_turf"] if (h["today_surf"] or "").upper() == "T" else h["best_dist"]


# ── the nine flags (all take (h, field); ignore field where unused) ──────────
def flag_workout(h, field):
    """Any published work meets Frank's clock for its distance (3F<36/4F<48/5F<60)."""
    for w in h["works"]:
        if w["dist_y"] is None:
            continue
        fl_exact = w["dist_y"] / 220.0
        fl = round(fl_exact)
        if fl not in WORK_CLOCK or abs(fl_exact - fl) > 0.15:   # skip half-furlong works
            continue
        t = (w["time"] or "").lstrip("-").strip()               # '-' = bullet
        try:
            if float(t) < WORK_CLOCK[fl]:
                return True
        except ValueError:
            continue
    return False


def flag_class_drop(h, field):
    pts, _ = class_move(h)
    return pts == 2


def flag_jockey_surf(h, field):
    """Jockey's turf/distance context stat (f1367-1372) is strong. BRIS pre-selects
    the context, so no label match needed — just qualify it."""
    j = h["jky"]
    if (j["starts"] or 0) >= STARTS_FLOOR and j["wins"] and j["roi"] is not None \
            and j["roi"] >= 0.0:
        return 100.0 * j["wins"] / j["starts"] >= JKY_WIN_MIN
    return False


def flag_trainer_surf(h, field):
    labels = SURFACE_ANGLES.get((h["today_surf"] or "").upper(), set())
    for a in h["trn_angles"]:
        if a["label"] in labels and (a["starts"] or 0) >= STARTS_FLOOR \
                and a["roi"] is not None and a["roi"] >= 0.0 \
                and a["win_pct"] is not None and a["win_pct"] >= TRN_WIN_MIN:
            return True
    return False


def flag_speed(h, field):
    """Interim: best speed figure ranks top-3 in the field (surface-aware)."""
    ranked = sorted((x for x in field if _best_speed(x) is not None),
                    key=_best_speed, reverse=True)
    return h["pgm"] in {x["pgm"] for x in ranked[:3]}


# pace-fit thresholds (cm1_pace_fit resolution, validated on 8-card scan)
LED_MAX, FADE_POS, BACK_MIN, CLOSE_POS, DIST_GAP_F = 2, 4, 5, 5, 1.5


def _surf_class(s):
    s = (s or "").strip().upper()
    if s.startswith("D"):
        return "D"
    if s.startswith("T"):
        return "T"
    if s.startswith("A"):
        return "A"
    return s


def flag_pace_fit(h, field):
    """Frank's cut-back angle: faded from speed in a race ≥1.5F LONGER than today
    (same surface) → suited dropping back. Plus the stretch-out mirror (closed in a
    race ≥1.5F shorter). Recent 6 lines."""
    tf = (h["today_dist_y"] or 0) / 220.0
    tsurf = _surf_class(h["today_surf"])
    for p in h["pp"][:6]:
        if _surf_class(p["surface"]) != tsurf:
            continue
        fin = p["finish_pos"]
        pf = (p["dist_y"] or 0) / 220.0
        if fin is None or not tf or not pf:
            continue
        early = [x for x in (p["call1_pos"], p["call2_pos"]) if x]
        if early:
            be = min(early)
            if be <= LED_MAX and (fin - be) >= FADE_POS and (pf - tf) >= DIST_GAP_F:
                return True                       # faded in a longer race → cut-back fit
        soc = p["start_pos"] or p["call1_pos"]
        if soc and soc >= BACK_MIN and (soc - fin) >= CLOSE_POS and (tf - pf) >= DIST_GAP_F:
            return True                           # closed in a shorter race → stretch-out fit
    return False


# ── table-backed flags (point-in-time by card date; False if DB not seeded) ──
def flag_jockey_hot(h, field):
    c = _stats()
    return bool(c) and stats.is_hot_tj(c, "jockey", h["jockey"], h["date"])


def flag_trainer_hot(h, field):
    c = _stats()
    return bool(c) and stats.is_hot_tj(c, "trainer", h["trainer"], h["date"])


def flag_breeding(h, field):
    # INTERIM: broodmare-sire positive ROI (ex-outlier) as a data-derived stand-in
    # for Frank's "legendary" list until that list is supplied. Thin until BMS table matures.
    c = _stats()
    return bool(c) and stats.is_bms_positive(c, h["dam_sire"], h["date"])


FLAGS = [
    ("workout",      flag_workout),
    ("pace_fit",     flag_pace_fit),
    ("class_drop",   flag_class_drop),
    ("jockey_hot",   flag_jockey_hot),
    ("jockey_surf",  flag_jockey_surf),
    ("speed",        flag_speed),
    ("trainer_hot",  flag_trainer_hot),
    ("trainer_surf", flag_trainer_surf),
    ("breeding",     flag_breeding),
]
# all nine now compute; speed + breeding are interim proxies (see notes)
LIVE_FLAGS = {"workout", "pace_fit", "class_drop", "jockey_hot", "jockey_surf",
              "speed", "trainer_hot", "trainer_surf", "breeding"}


def score_horse(h, field):
    fired = {name: fn(h, field) for name, fn in FLAGS}
    return {
        "pgm": h["pgm"], "name": h["name"],
        "flags": fired,
        "count": sum(1 for v in fired.values() if v),
        "_speed": _best_speed(h) or -1,   # tie-break key
    }


def score_race(horses):
    scored = [score_horse(h, horses) for h in horses]
    scored.sort(key=lambda s: (s["count"], s["_speed"]), reverse=True)
    for i, s in enumerate(scored, 1):
        s["cm1_rank"] = i
    return scored


def _run(path, only_race=None):
    live = [n for n, _ in FLAGS if n in LIVE_FLAGS]
    for rn, horses in extract_card(path).items():
        if only_race and rn != str(only_race):
            continue
        print(f"\n=== R{rn} — CM1 flag count (LIVE flags: {', '.join(live)}) ===")
        for s in score_race(horses):
            on = [n for n, v in s["flags"].items() if v]
            print(f"  {s['cm1_rank']:>2}. #{s['pgm']:>2} {s['name']:<20} "
                  f"[{s['count']}]  {', '.join(on)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--race":
        _run(args[2], args[1])
    elif args:
        for p in args:
            _run(p)
    else:
        print(__doc__)
