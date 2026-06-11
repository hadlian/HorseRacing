# Final-Odds Overlay Retro-Test — 2026-06-11 (Week 3 gate)

Rule tested: P(win) × (final_odds + 1) ≥ 1.25 AND P(win) ≥ 0.08, $2 flat win.
Universe: 758 scored runners with captured final tote odds, 115 races.
Both biases favor the signal (in-sample β; hindsight final odds).

| threshold | bets | wins | win% | ROI | avg odds |
|---|---|---|---|---|---|
| 1.10 | 167 | 13 | 7.8% | −53.0% | 15.6-1 |
| **1.25 (rule)** | **142** | **10** | **7.0%** | **−56.9%** | 17.1-1 |
| 1.40 | 122 | 8 | 6.6% | −57.8% | 18.7-1 |
| 1.60 | 92 | 5 | 5.4% | −64.7% | 21.2-1 |

Qualifiers by model rank: r1 18/2, r2 29/4, r3 18/2, **r4+ 77/2**.

## VERDICT: live overlay win betting NOT authorized for Saratoga.

Monotone deterioration with threshold = the selector is harvesting
favorite-longshot bias, not edge: a one-parameter logit on a flat-top-end
composite overestimates longshots exactly where the market knows better.
Consistent with every prior win-bet signal failure. The system's edge search
moves entirely to exotics structures (Task 7) per Decision 2.

Overlay flags stay in output as ADVISORY/diagnostic only. Revisit only after
(a) out-of-sample SAR data, (b) a calibration upgrade (n≥300 decorrelated
model per Decision 1A upgrade path) — and only ever paper-first.
