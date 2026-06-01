"""
CompareModels CLI entry point.
Usage:
  python comparemodels/comparemodels_cli.py score    <TRACK> <YYYYMMDD>
  python comparemodels/comparemodels_cli.py log      <TRACK> <YYYYMMDD>
  python comparemodels/comparemodels_cli.py results  <TRACK> <YYYYMMDD>
  python comparemodels/comparemodels_cli.py finalize <TRACK> <YYYYMMDD>
  python comparemodels/comparemodels_cli.py backfill
  python comparemodels/comparemodels_cli.py compare
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comparemodels.comparemodels_engine import score_card
from comparemodels.comparemodels_tracker import (
    init_db, log_card_with_ml, pull_results, finalize
)
from comparemodels.comparemodels_compare import generate_report
from comparemodels.comparemodels_backfill import run_backfill, build_ml_map

FILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'files 2')


def _require_args(args, n, usage):
    if len(args) < n:
        print(f"Usage: {usage}")
        sys.exit(1)


def _drf_path(track: str, date: str) -> str:
    mmdd = date[4:8]
    return os.path.join(FILES_DIR, f"{track.upper()}{mmdd}.DRF")


def cmd_score(track: str, date: str):
    drf = _drf_path(track, date)
    if not os.path.exists(drf):
        print(f"DRF not found: {drf}")
        sys.exit(1)
    score = score_card(drf)
    for race_num, result in sorted(score.items()):
        top = result['ranked_horses'][0]
        notes = result.get('missing_notes', [])
        note_str = f"  ⚠ {'; '.join(notes)}" if notes else ""
        print(f"  Race {race_num}: {top['name']} (pgm {top['pgm']}) "
              f"comp={top['composite']} tier={top['tier']}{note_str}")


def cmd_log(track: str, date: str):
    drf = _drf_path(track, date)
    if not os.path.exists(drf):
        print(f"DRF not found: {drf}")
        sys.exit(1)
    init_db()
    score = score_card(drf)
    ml_map = build_ml_map(drf)
    picks, cat_picks = log_card_with_ml(score, track, date, ml_map)
    print(f"Logged: {picks} picks, {cat_picks} category picks for {track} {date}")


def cmd_results(track: str, date: str):
    matched, unmatched = pull_results(track, date)
    print(f"Results joined: {matched} matched, {unmatched} unmatched for {track} {date}")


def cmd_finalize(track: str, date: str):
    finalize(track, date)
    print(f"Finalized scratches for {track} {date}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == 'score':
        _require_args(args, 3, 'score <TRACK> <YYYYMMDD>')
        cmd_score(args[1], args[2])

    elif cmd == 'log':
        _require_args(args, 3, 'log <TRACK> <YYYYMMDD>')
        cmd_log(args[1], args[2])

    elif cmd == 'results':
        _require_args(args, 3, 'results <TRACK> <YYYYMMDD>')
        cmd_results(args[1], args[2])

    elif cmd == 'finalize':
        _require_args(args, 3, 'finalize <TRACK> <YYYYMMDD>')
        cmd_finalize(args[1], args[2])

    elif cmd == 'backfill':
        run_backfill()

    elif cmd == 'compare':
        path = generate_report()
        print(f"\nReport: {path}")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
