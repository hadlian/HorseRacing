# Session 3B Research — tj_n Year-Stats Fallback Backtest (2026-06-12)

**Research only. No live-engine changes. For Harry's ruling.**

Question: tj_n (strongest component, +0.80 winner-diff, 15% weight) uses
current-MEET trainer/jockey stats gated at ≥20 starts, then falls back to a
hard-coded elite-name list. At meet openings the meet stats are empty —
does substituting current-YEAR stats (DRF fields 1147/48, 1157/58) fix the
9.4% SAR opener drag?

Method: reparse all DRFs on disk (1,449 picks matched of 1,747), recompute
tj_n under the proposed chain (meet ≥20 → year ≥20 → elite), shift comp by
0.15 × Δtj_n (tj enters linearly — exact up to rounding), re-rank, corrected
ROI. Script: `scripts/tj_fallback_backtest.py`.

## The starvation is real

- **84% of picks** (1,222/1,449) get a different tj_n under the proposed chain.
- Trainer-leg stat source under the proposed chain: meet 277, **year 1,065
  (73%)**, elite-list/floor 107. Today, those 1,065 all run on name-matching.
- Mean comp shift when changed: **+0.288** (range −0.285 to +0.891) — the
  elite-list fallback systematically under-credits competent non-elite
  connections.
- Rank-1 flips in **32 of 160 races (20%)**.

## The outcome does NOT support a pre-Saratoga change

| universe | bets | wins | win% | ROI |
|---|---|---|---|---|
| ALL stored rank-1 | 159 | 38 | 23.9% | −16.7% |
| ALL proposed rank-1 | 158 | 38 | 24.1% | **−14.3%** |
| SAR stored rank-1 | 32 | 3 | 9.4% | −73.3% |
| SAR proposed rank-1 | 32 | 3 | **9.4%** | −56.4% |

- Overall: +2.4 ROI points, win rate flat. Real but small, and well inside
  noise at n=160.
- **SAR: the win rate does not move.** Same 3 winners under both rankings.
  The proposed rank-1s lose less (−56.4% vs −73.3%) only because the flipped
  picks lose at slightly better prices. **The year-stats hypothesis does NOT
  explain the SAR opener drag.** The drag has other causes (class of
  competition, surface, small n — 3/32 is itself a wide interval).

## Recommendation for Harry

**Do not change tj_n before Saratoga.** The mechanism is real and the fix is
directionally positive, but +2.4 ROI points at n=160 with zero SAR win-rate
improvement does not clear the bar for a scoring change + version bump days
before deployment — and the project's history says win-adjacent tweaks
validated on thin samples die on re-test.

**Re-run this exact script at SAR n≥60** (it's one command; the DRFs accrue
as cards are analyzed). Meet-stats starvation is worst precisely in the
meet's first weeks, so the live SAR races now accruing are the correct test
set. If the year-stats chain shows a SAR win-rate or ROI separation there,
bring it to a ruling as v3.11 alongside the n≥300 probability-layer upgrade.
