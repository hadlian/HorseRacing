# Calibration Report — 2026-06-11

β = 0.7674 | LL = -192.08 | fit races = 97 | dropped (winner missing comp_ex_val) = 62

In-sample picks scored: 891 (current-formula universe)

| Decile | n | mean predicted P | observed win% |
|---|---|---|---|
| 1 | 89 | 2.5% | 0.0% |
| 2 | 89 | 4.0% | 2.2% |
| 3 | 89 | 5.3% | 7.9% |
| 4 | 89 | 6.5% | 7.9% |
| 5 | 89 | 8.1% | 12.4% |
| 6 | 89 | 10.0% | 5.6% |
| 7 | 89 | 11.9% | 9.0% |
| 8 | 89 | 14.4% | 18.0% |
| 9 | 89 | 18.2% | 21.3% |
| 10 | 90 | 28.8% | 24.4% |

## Rank-3 diagnostic (Decision 1B mandatory check)

- Rank-3 picks: 92 | mean predicted P = 14.4% | observed = 22.8%
- Full-DB observed rank-3 reference (160-race baseline): 23.2%
- If predicted is far below observed, β is over-discriminating tight clusters; report, do not tune.
- Rank-1: n=96, predicted 25.1%, observed 21.9%
- Rank-2: n=97, predicted 17.7%, observed 19.6%
