# Corrected Performance Baseline — 2026-06-11

> **This document supersedes every ROI claim in R5_PROJECT_STATE.md, TODO.md, and
> COMPAREMODELS_STATE.md prior to this date.** All earlier ROI figures were inflated by a
> unit bug ($2 mutuel payoffs credited against $1 stakes / treated as decimal odds).
> Convention everywhere below: **$2 flat win bets, profit = payoff − 2, ROI = profit / (2 × bets)**.
>
> DB state: R5 160 result-fetched races (Derby duplicate removed, 2 payoff rows chart-corrected,
> through SAR 06/05 with 3 races pending; SAR 06/06 results not yet loaded).
> CM: stale result joins refreshed, 55 scratch artifacts chart-audited (6 were runners,
> incl. 1 winner — IMMORTALIZE $4.88), SAR 06/03–05 loaded. Full detail:
> `results/SIGNAL_VALIDATION_20260611.md`.

## Top line

| | Bets | Wins | Win% | ROI ($2 flat) |
|---|---|---|---|---|
| **R5 top pick** (full DB) | 156 | 36 | 23.1% | **−18.5%** |
| **CM top pick** (aligned universe) | 152 | 39 | 25.7% | **−21.9%** |
| R5 top pick, identical races | 150 | 35 | 23.3% | −16.8% |
| R5 top-3 contains winner | — | — | 59.4% | — |

**Head-to-head delta:** CM wins slightly more often; R5 loses slightly less money.
Neither model beats takeout on flat win bets. The old claims of "+93.0% R5 / +50.6% CM
SP ROI" and "val_n ROI +172.9%" are artifacts of the accounting bug and are void.

## Signals retired (failed corrected-ROI testing)

- **Play/spread ≥ 0.5 gate** (−40.3%; its complement is −9.1%)
- **PLAY ≥ 6.0 verdict** as a betting gate (no ROI separation; win rate now inverted)
- **HIGH / SOLID tiers** (0 and 1 fires in 160 races — dead weight); FAIR as a confidence marker (−70.2%)
- **CM consensus ≥ 4** (fires 91%, −20.5%) and all higher levels (negative throughout)
- **Agreement boost** ("R5+CM agree → bet more"): 32.2% win, **−22.9%** — chalk trap
- **PP underline stacked on R5 pick** (−13.9%; stacking raises win%, lowers ROI)
- **val_n ≥ 7** (−8.2%)
- Overlay Watch (already retired; stays retired)

## Signals on watch (promising but unproven)

- **R5 rank-3 win bets: +17.4%** (35 wins / 151 bets, 23.2% — equals rank-1's win rate at better prices). The only positive-ROI slot at meaningful n in the project.
- **CM rank-2: +3.6%** — same near-miss pattern, weaker.
- **val_n ≥ 8 (+41.8%) / ≥ 9 (+85.7%)** — correct ROI gradient direction, but 4 and 2 wins respectively.
- **PP underline standalone** (31.5% win, −9.6%) — best win-rate signal; candidate exotics anchor, not a win bet.
- **Divergence, bet R5 leg** (−12.8%, single-outlier sensitive).

## Open items this baseline depends on

1. SAR 06/05 stragglers + SAR 06/06 results → re-run `results SAR <date>` for CM after R5 loads them.
2. Tight-cluster deduction re-validation blocked on persisting `tight_cluster_severe` / `pre_tight_comp` to the picks schema (current analysis is approximate; it suggests the −0.40 deduction may be backwards on ROI).
3. Class weight confirmed by Harry 2026-06-11 as **20%** (code is authoritative; v3.5's documented "13%" was never implemented). R5_SPEC.md refresh to v3.10 can proceed on that basis.
