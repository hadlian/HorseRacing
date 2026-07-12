#!/usr/bin/env python3
"""
run_r5.py — Master R5 Runner
Combines Scout intel + DRF file parsing into a full race analysis.

Usage:
    python3 run_r5.py DBY0502.DRF
    python3 run_r5.py DBY0502.DRF --scout scout_CD_20260502_r5.txt
    python3 run_r5.py DBY0502.DRF --auto-scout   # runs scout first automatically
    python3 run_r5.py DBY0502.DRF --race 5       # single race only
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HORSE_RACING_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR        = HORSE_RACING_ROOT / "Claude"

import importlib.util as _ilu
from collections import defaultdict as _dd

# ── Load parser ───────────────────────────────────────────────────────────────
_parser_path = Path(__file__).parent / "r5_parser_v2.py"
if not _parser_path.exists():
    _parser_path = CLAUDE_DIR / "r5_parser_v2.py"
_pspec = _ilu.spec_from_file_location("r5_parser_v2", _parser_path)
_pmod  = _ilu.module_from_spec(_pspec)
_pspec.loader.exec_module(_pmod)
parse_drf       = _pmod.parse_drf
finalize_field  = _pmod.finalize_field
report          = _pmod.report
tier            = _pmod.tier

# ── Load scout ────────────────────────────────────────────────────────────────
_scout_path = Path(__file__).parent / "r5_scout.py"
_sspec = _ilu.spec_from_file_location("r5_scout", _scout_path)
_smod  = _ilu.module_from_spec(_sspec)
_sspec.loader.exec_module(_smod)
format_for_r5 = _smod.format_for_r5


def load_scout_intel(scout_path):
    """Load scout intel text block from file"""
    if not scout_path or not Path(scout_path).exists():
        return None
    with open(scout_path) as f:
        return f.read()


def load_scout_json(json_path):
    """Load scout JSON and apply adjustments to horses"""
    if not json_path or not Path(json_path).exists():
        return {}
    with open(json_path) as f:
        return json.load(f)


def apply_scout_adjustments(horses, intel):
    """
    Apply scout intel to R5 composite scores.
    Returns modified horse list + adjustment log.
    """
    if not intel:
        return horses, []

    import re as _re
    def _strip_country(n):
        """Strip country-of-origin suffixes like (IRE), (GB), (FR), (AUS), (CHI) etc."""
        return _re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', n.strip().upper())

    log = []
    scratch_list = {_strip_country(s["horse"]) for s in intel.get("scratches", [])}
    # Also-Eligibles (Scout-3 fix, 2026-05-28): horses on the wait list — NOT scratched.
    # Tag them so report() can annotate; do NOT skip scoring.
    ae_list = {_strip_country(ae["horse"]) for ae in intel.get("also_eligibles", [])}

    for h in horses:
        name = _strip_country(h["name"])

        # Remove scratches
        if name in scratch_list:
            h["scratched"] = True
            log.append(f"  ✗ SCRATCH: {h['name']}")
            continue

        # Flag Also-Eligibles — scored normally, annotated in report
        if name in ae_list:
            h["also_eligible"] = True
            log.append(f"  ⏳ AE: {h['name']} (also-eligible — will run only if a scratch occurs)")

        adj = 0.0

        # Trainer sentiment
        for q in intel.get("trainer_quotes", []):
            if h["name"].lower() in q["horse"].lower():
                if q.get("sentiment") == "positive":
                    adj += 0.2
                    log.append(f"  ✅ {h['name']}: +0.2 (positive trainer quote)")
                elif q.get("sentiment") == "negative":
                    adj -= 0.3
                    log.append(f"  ⚠️  {h['name']}: -0.3 (negative trainer signal)")

        # Health concerns
        for hc in intel.get("health_concerns", []):
            if h["name"].lower() in hc["horse"].lower():
                adj -= 0.3
                log.append(f"  🏥 {h['name']}: -0.3 ({hc.get('concern','')})")

        # Sharp money
        for sm in intel.get("sharp_money", []):
            if h["name"].lower() in sm["horse"].lower():
                adj += 0.15
                log.append(f"  💰 {h['name']}: +0.15 (sharp money)")

        # Bullet workout
        for wk in intel.get("workout_notes", []):
            if h["name"].lower() in wk["horse"].lower():
                if "bullet" in wk.get("note", "").lower():
                    adj += 0.1
                    log.append(f"  🏃 {h['name']}: +0.1 (bullet workout)")
                elif wk.get("concern"):
                    adj -= 0.15
                    log.append(f"  ⚠️  {h['name']}: -0.15 (workout concern)")

        # Equipment
        for eq in intel.get("equipment_changes", []):
            if h["name"].lower() in eq["horse"].lower():
                change = eq.get("change", "").lower()
                if "blinkers" in change and "first time" in change:
                    adj += 0.1
                    log.append(f"  🔧 {h['name']}: +0.1 (first-time blinkers)")
                elif "remove" in change or "off" in change:
                    adj -= 0.05

        # Jockey switch
        for js in intel.get("jockey_switches", []):
            if h["name"].lower() in js["horse"].lower():
                # Upgrade if to elite jockey
                new_jky = js.get("new_jockey", "").upper()
                elite = ["ORTIZ", "VELAZQUEZ", "SAEZ", "GAFFALIONE", "PRAT",
                         "CASTELLANO", "FRANCO", "ROSARIO", "ESPINOZA"]
                if any(e in new_jky for e in elite):
                    adj += 0.1
                    log.append(f"  🏇 {h['name']}: +0.1 (upgrade to elite jockey {js['new_jockey']})")

        if adj != 0:
            SCOUT_CAP = 0.40
            if abs(adj) > SCOUT_CAP:
                capped = round(SCOUT_CAP * (1 if adj > 0 else -1), 2)
                log.append(f"  ⚡ {h['name']}: scout adj capped {adj:+.2f} → {capped:+.2f} (±{SCOUT_CAP} max)")
                adj = capped
            h["comp"] = round(h["comp"] + adj, 2)
            h["tier"] = tier(h["comp"])
            h["pre_comp"] = h["comp"]   # keep pre_comp in sync so finalize val_n sort sees scout order
            h["scout_adj"] = round(adj, 2)

    return horses, log


def main():
    parser = argparse.ArgumentParser(description="R5 Race Analyzer")
    parser.add_argument("drf_file", help="BRIS DRF file to analyze")
    parser.add_argument("--scout", help="Scout intel text file (.txt)")
    parser.add_argument("--scout-json", help="Scout intel JSON file (.json)")
    parser.add_argument("--auto-scout", action="store_true",
                        help="Auto-run r5_scout.py before analysis")
    parser.add_argument("--race", type=int, help="Analyze single race number only")
    parser.add_argument("--save", action="store_true", help="Save output to txt file")
    parser.add_argument("--pdf",  action="store_true", help="Save output to PDF (one page per race)")
    parser.add_argument("--track", action="store_true",
                        help="Log picks to SQLite results DB (opt-in)")
    parser.add_argument("--wet", action="store_true",
                        help="Today's track is OFF (muddy/sloppy/soft/yielding/good) — "
                             "show wet-form lines for contenders. Track condition is a "
                             "race-day input; the DRF cannot carry it.")
    parser.add_argument("--year", type=int, default=None,
                        help="Override the race year (e.g. --year 2025 for backfill cards). "
                             "Default: current calendar year.")
    parser.add_argument("--backtest", action="store_true",
                        help="Tag these races as backtest (is_backtest=1); excluded from live analytics")
    parser.add_argument("--live", action="store_true",
                        help="Request live val_n >=8 bets (subject to gate checks); default is paper")
    parser.add_argument("--force", action="store_true",
                        help="Override the settled-card refuse guard (re-log a card whose "
                             "races are already settled). Un-settles them — recover with --finalize.")
    args = parser.parse_args()

    drf_path = args.drf_file
    if not Path(drf_path).exists():
        print(f"Error: {drf_path} not found")
        sys.exit(1)

    # Parse DRF first — needed before scout so we can pass horse names
    print(f"\n📂 Parsing: {drf_path}")
    horses = parse_drf(drf_path)

    # Auto-run scout if requested — pass top horse names for targeted scraping
    if args.auto_scout:
        track   = Path(drf_path).stem[:3].upper()
        mmdd    = Path(drf_path).stem[3:7]
        from datetime import date as _date_cls
        date_str = str(args.year or _date_cls.today().year) + mmdd

        # Collect top 3 horses per race by raw WS4 (pre-finalize best proxy)
        _by_race_raw = _dd(list)
        for h in horses:
            _by_race_raw[h["race"]].append(h)

        seen_names, top_names = set(), []
        for rnum in sorted(_by_race_raw.keys(), key=lambda x: int(x)):
            ranked = sorted(
                _by_race_raw[rnum],
                key=lambda h: h.get("ws4") or h.get("prime_power") or 0,
                reverse=True,
            )
            for h in ranked[:3]:
                key = h["name"].upper()
                # Skip very short names (single word < 4 chars) to avoid noisy keywords
                if key not in seen_names and len(h["name"].strip()) >= 4:
                    seen_names.add(key)
                    top_names.append(h["name"].strip())

        top_names = top_names[:30]           # cap: 10-race card × 3 = 30 max
        horses_arg = ",".join(top_names)

        print(f"🔍 Running R5 Scout — track: {track}  date: {date_str}  horses: {len(top_names)}")
        print(f"   Top horses: {', '.join(top_names[:8])}{'...' if len(top_names) > 8 else ''}")
        subprocess.run([
            sys.executable, str(_scout_path),
            "--track",  track,
            "--date",   date_str,
            "--horses", horses_arg,
        ])

    # Load scout intel and apply adjustments BEFORE finalize so tight-cluster
    # deduction (inside finalize_field) operates on scout-aware composites.
    intel = {}
    if args.scout_json:
        intel = load_scout_json(args.scout_json)
    elif args.auto_scout:
        scout_dir = HORSE_RACING_ROOT / "scout"
        drf_track = Path(drf_path).stem[:3].upper()
        drf_date  = Path(drf_path).stem[3:7]
        candidates = sorted(scout_dir.glob(f"scout_{drf_track}_*.json"), key=os.path.getmtime)
        date_match = [f for f in candidates if drf_date in f.stem]
        chosen = date_match[-1] if date_match else (candidates[-1] if candidates else None)
        if chosen:
            intel = load_scout_json(chosen)
            print(f"📋 Using scout: {chosen.name}")
        else:
            print(f"⚠️  No scout JSON found for track {drf_track} — skipping scout adjustments")

    horses, adj_log = apply_scout_adjustments(horses, intel)

    # Finalize each race independently — pace fit, value, scout re-application,
    # and tight-cluster deduction all need full-field context with scout-aware comps.
    by_race = _dd(list)
    for h in horses:
        by_race[h['race']].append(h)
    horses = []
    for race_horses in by_race.values():
        horses.extend(finalize_field(race_horses))

    if args.race:
        horses = [h for h in horses if str(h["race"]).strip() == str(args.race)]
        if not horses:
            print(f"No horses found for Race {args.race}")
            sys.exit(1)

    # Print scout intel block if available
    scout_text = load_scout_intel(args.scout)
    if scout_text:
        print(scout_text)
    elif intel:
        from io import StringIO
        # Rebuild text from JSON
        block = format_for_r5(intel)
        print(block)

    # Print adjustment log
    if adj_log:
        print("\n📊 SCOUT ADJUSTMENTS APPLIED:")
        for line in adj_log:
            print(line)
        print()

    # Remove scratches from field — with per-race scratch notices
    def run_report_with_scratch_notice(race_horses):
        ranked_full  = sorted(race_horses, key=lambda h: h["comp"], reverse=True)
        scratched    = [h for h in ranked_full if h.get("scratched")]
        active_field = [h for h in ranked_full if not h.get("scratched")]
        if not active_field:
            return

        # Print scratch notice when any scratched horse was in pre-scratch top 3
        for s in scratched:
            pre_rank = ranked_full.index(s) + 1
            if pre_rank <= 3:
                new_top = active_field[0]
                print(f"🚨  SCRATCH NOTICE — R{s['race']}: "
                      f"#{s['pgm']} {s['name']} (pre-scratch Rank {pre_rank}) scratched.")
                pw = (f"  P(win) {new_top['p_win']*100:.0f}%"
                      if new_top.get('p_win') else "")
                print(f"    REVISED TOP PICK: #{new_top['pgm']} {new_top['name']}  "
                      f"Composite {new_top['comp']}{pw}")
                print()

        # FIELD COUNT DISCLOSURE — always print when scratches present so user can verify
        # entry count vs gate count against the official track program.
        if scratched:
            def _pgm_sort_key(h):
                p = str(h.get("pgm", ""))
                return (int(p) if p.isdigit() else 99, p)
            scr_list = ", ".join(f"#{s['pgm']}" for s in sorted(scratched, key=_pgm_sort_key))
            race_num = active_field[0]['race']
            print(f"🐎  R{race_num} FIELD: {len(ranked_full)} entries → "
                  f"{len(active_field)} starters  ({len(scratched)} removed by scout: {scr_list})")
            print("    ⚠️   Verify against official track program — scout may include "
                  "Also-Eligible (AE) horses that draw in if scratches occur.")
            print()

        report(active_field, wet=args.wet)

    if args.race:
        run_report_with_scratch_notice(horses)
    else:
        by_race = _dd(list)
        for h in horses:
            by_race[h["race"]].append(h)
        for race_num in sorted(by_race.keys(), key=lambda x: int(x)):
            run_report_with_scratch_notice(by_race[race_num])

    # Log picks to DB if --track flag used
    if args.track:
        _tracker_path = Path(__file__).parent / "r5_tracker.py"
        _tspec = _ilu.spec_from_file_location("r5_tracker", _tracker_path)
        _tmod  = _ilu.module_from_spec(_tspec)
        _tspec.loader.exec_module(_tmod)

        track_code = Path(drf_path).stem[:3].upper()
        drf_date   = Path(drf_path).stem[3:7]
        # Derive date: stem is e.g. DBY0502 → track=DBY, mmdd=0502, year from today or --year
        from datetime import date as _date
        mmdd       = Path(drf_path).stem[3:7]
        year       = str(args.year or _date.today().year)
        date_str   = year + mmdd  # e.g. 20260502

        active_for_db = [h for h in horses if not h.get("scratched")]
        db_by_race = _dd(list)
        for h in active_for_db:
            db_by_race[h["race"]].append(h)

        # ── write-path guardrails (added after the 2026-07-12 phantom-card
        #    incident: a 2025 DRF run without --year/--backtest landed a LIVE
        #    card under a future date; a later 9-race real card then overwrote
        #    R1-9 and orphaned R10-12). Warn loudly before we overwrite —
        #    operator decides. See project_rerun_clobber memory.
        from datetime import date as _date2, timedelta as _td
        _warns = []
        try:
            _derived = _date2(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
            _days_ahead = (_derived - _date2.today()).days
            if _days_ahead > 2:      # day-before / race-morning runs won't trip this
                _warns.append(
                    f"date {date_str} is {_days_ahead} days in the FUTURE — did you "
                    f"forget --year? (year defaulted to {year} from the filename)")
        except ValueError:
            pass
        _gconn = _tmod.init_db()
        _existing = _gconn.execute(
            "SELECT r.race_num, r.is_backtest, r.result_fetched, "
            "(SELECT COUNT(*) FROM picks p WHERE p.race_id=r.id) "
            "FROM races r WHERE r.track=? AND r.date=?",
            (track_code, date_str)).fetchall()
        _gconn.close()
        _ex_races = {str(row[0]) for row in _existing if row[3]}
        _new_races = {str(k) for k in db_by_race}
        _settled = []
        if _ex_races:
            _settled = sorted((str(row[0]) for row in _existing if row[2]), key=int)
            _orphans = sorted(_ex_races - _new_races, key=int)
            _bt = any(row[1] for row in _existing)
            _warns.append(
                f"{len(_ex_races)} race(s) already logged for {track_code} {date_str}"
                + (" [is_backtest=1]" if _bt else "")
                + " — their picks will be OVERWRITTEN.")
            if _orphans:
                _warns.append(
                    f"races {_orphans} exist for this date but are NOT in this card — "
                    f"they will be left as ORPHANS under {date_str}.")
        # HARD REFUSE on settled-card clobber (unless --force): re-logging wipes
        # real results. This is the destructive case the warnings can't undo.
        if _settled and not args.force:
            print(f"\n  ⛔ REFUSING to log: races {_settled} for {track_code} "
                  f"{date_str} are already SETTLED (result_fetched=1).")
            print(f"     Re-logging would un-settle them and wipe their results "
                  f"(clobber). Nothing was written.")
            print(f"     • If this card genuinely needs re-running, recover with "
                  f"`r5_tracker --finalize {track_code} {date_str}` first,")
            print(f"       or purge the date, then re-run. Pass --force to override "
                  f"and clobber deliberately.\n")
            sys.exit(1)
        if _warns:
            print("\n  ⚠️  WRITE-PATH WARNING(S) before logging to DB:")
            for _w in _warns:
                print(f"     • {_w}")
            if _settled:   # only reachable with --force
                print(f"     • --force set: SETTLED races {_settled} will be "
                      f"CLOBBERED (un-settled). Recover with --finalize.")
            print("     Proceeding. Pass --year / --backtest, or purge the "
                  "stale date first, if this is not what you intend.\n")

        print("\n📋 Logging picks to DB...")
        for race_num, race_horses in sorted(db_by_race.items(), key=lambda x: int(x[0])):
            _tmod.log_race_picks(race_horses, track_code, date_str, race_num,
                                 is_backtest=args.backtest)

        if not args.backtest:
            import importlib.util as _ilu2
            _ppath = Path(__file__).parent / "r5_probability.py"
            _pspec = _ilu2.spec_from_file_location("r5_probability", _ppath)
            _pmod  = _ilu2.module_from_spec(_pspec)
            _pspec.loader.exec_module(_pmod)
            print("\n📝 Auto-logging val_n paper trackers...")
            for race_num in sorted(db_by_race.keys(), key=lambda x: int(x)):
                _pmod.auto_log_val_trackers_for_race(
                    track_code, date_str, race_num, live=getattr(args, "live", False))

            # Auto-generate exotic tickets (paper) so the settle step always has
            # an entries-basis ticket set. Prevents the standalone race-morning
            # generate step from being silently skipped (SAR 2026-07-11 gap).
            # Live exotics remain gated exclusively to r5_exotics.py --live.
            _epath = Path(__file__).parent / "r5_exotics.py"
            _espec = _ilu.spec_from_file_location("r5_exotics", _epath)
            _emod  = _ilu.module_from_spec(_espec)
            _espec.loader.exec_module(_emod)
            print("\n🎟️  Auto-generating exotic tickets (paper)...")
            try:
                _emod.generate_card(track_code, date_str,
                                    race_num=args.race, live_mode=False)
            except Exception as _ee:
                print(f"  ⚠️  Exotics generation skipped (non-fatal): {_ee}")

    # Save if requested
    if args.save:
        out = Path(drf_path).stem + "_R5_analysis.txt"
        import io, sys as _sys
        old_stdout = _sys.stdout
        _sys.stdout = buffer = io.StringIO()
        if args.race:
            run_report_with_scratch_notice(horses)
        else:
            save_by_race = _dd(list)
            for h in horses:
                save_by_race[h["race"]].append(h)
            for race_num in sorted(save_by_race.keys(), key=lambda x: int(x)):
                run_report_with_scratch_notice(save_by_race[race_num])
        _sys.stdout = old_stdout
        with open(out, "w") as f:
            f.write(buffer.getvalue())
        print(f"\n💾 Saved: {out}")

    # Generate PDF if requested
    if args.pdf:
        _pdf_path = Path(__file__).parent / "r5_pdf.py"
        _pdfspec = _ilu.spec_from_file_location("r5_pdf", _pdf_path)
        _pdfmod  = _ilu.module_from_spec(_pdfspec)
        _pdfspec.loader.exec_module(_pdfmod)

        pdf_by_race = _dd(list)
        for h in horses:
            if not h.get("scratched"):
                pdf_by_race[h["race"]].append(h)

        track_code = Path(drf_path).stem[:3].upper()
        mmdd       = Path(drf_path).stem[3:7]
        pdf_out    = Path(drf_path).stem + "_R5.pdf"

        from datetime import date as _date
        year     = str(args.year or _date.today().year)
        date_str = year + mmdd

        _pdfmod.generate_pdf(
            pdf_by_race,
            out_path   = pdf_out,
            track      = track_code,
            race_date  = date_str,
        )
        print(f"\n📄 PDF saved: {pdf_out}")


if __name__ == "__main__":
    main()
