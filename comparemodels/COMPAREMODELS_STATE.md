# CompareModels v1 — System State

> Persistent context doc for CompareModels sessions.
>
> **Last updated:** 2026-05-21
> **Version:** CM v1.0
> **Status:** Backfill complete. 63-race comparison done. Analysis complete.

---

## System Overview

CompareModels is a fully isolated parallel handicapping system implementing the **BRIS Summary methodology** (category consensus scoring) alongside R5. It shares the same 63-race universe but scores from raw DRF data using an entirely separate algorithm. No R5 code is imported.

---

## Directory Layout

```
comparemodels/
├── __init__.py
├── drf_to_csv.py              DRF → CM CSV converter
├── comparemodels_engine.py    BRIS Summary scoring engine
├── comparemodels_tracker.py   DB logging + R5 result join
├── comparemodels_backfill.py  63-race backfill runner
├── comparemodels_compare.py   5-sheet Excel report generator
├── comparemodels_cli.py       CLI entry point
├── comparemodels_results.db   SQLite (auto-created)
├── COMPAREMODELS_STATE.md     This file
├── csv/                       Per-card CSVs (TRACK_YYYYMMDD.csv)
└── reports/                   Comparison Excel files
    └── comparemodels_vs_r5_63races_20260521_020626.xlsx  ← CURRENT
scripts/
└── recalc.py                  openpyxl formula validator
```

---

## Field Decisions (v1.0)

| CM CSV Column | Source | Decision |
|---|---|---|
| Avg Class | DRF field 12 (purse) | R5 confirmed not to use BRIS class rating fields |
| Early Pace | Mean of fields 766–775, inverted (999.0 − raw) | Raw fractional times; lower = faster → invert |
| Late Pace | Mean of fields 816–825, inverted (999.0 − raw) | Same inversion |
| BRIS Top Pick | NULL | Field not located; +2 bonus skipped throughout |
| LRL0516.csv | NOT used directly | Raw DRF comma-delimited format; LRL0516.DRF used instead |

**Track normalisation:** DRF field 1 returns internal BRIS code (`CD`). TRACK_MAP in `drf_to_csv.py` maps to DB codes (`CDX`). This has historically caused backfill failures — applied on parse.

---

## Scoring Weights (v1.0)

```python
CATEGORY_WEIGHTS = {
    "Avg Speed":      3,
    "Distance Speed": 2,
    "Best Speed":     2,
    "Prime Power":    3,
    "Avg Class":      2,
    "Jockey Rating":  1,
    "Trainer Rating": 1,
    "Earnings":       1,
}
```

- Top 3 per category by value (descending)
- Points: `max(weight − rank_idx, 0)` where rank_idx is 0-indexed
- Underline: ≥3 non-null values AND gap[0]−[2] ≥ 2.0
- Dominant: consensus ≥ 4 AND underlined in ≥ 1 category
- Overlay Watch: consensus ≥ 5 AND ML ≥ 6.0
- Tiers: A = rank 1, B = ranks 2–4, C = ranks 5–7

---

## Backfill Status

| Card | Races (DB) | DRF Rows | Matched | Unmatched |
|---|---|---|---|---|
| CDX 20260502 | 14 | 169 | 169 | 0 |
| DBY 20260502 | 1 | 24 | 24 | 0 |
| CDX 20260507 | 8 | 88 | 88 | 0 |
| BAQ 20260509 | 10 | 85 | 85 | 0 |
| BAQ 20260510 | 9 | 78 | 78 | 0 |
| CDX 20260514 | 8 | 86 | 66 | 20 |
| LRL 20260516 | 13 | 139 | 121 | 18 |
| **TOTAL** | **63** | **669** | **631** | **38** |

**Notes:**
- BAQ0509 DRF has 11 races; BAQ0510 DRF has 9 races — DB is authoritative at 63
- CDX0514 20 unmatched + LRL0516 18 unmatched = scratches/non-R5 horses
- DB integrity: SHA-256 pre/post match confirmed (`79554cd1a4c4bb756e2d5ce7cd22489ab198defce83a049a492c747115615928`)

---

## Head-to-Head Results (63 races, 2026-05-21)

| Metric | CompareModels | R5 |
|---|---|---|
| Top pick win rate | 25.4% (16/63) | 25.4% (16/63) |
| Top-3 hit rate | 47.6% (30/63) | 55.6% (35/63) |
| Agreement rate | 31.7% (20/63) | — |
| ROI on ML | −6.7% | −7.3% |
| ROI on SP | +50.6% | +93.0% |

**Agreement:** Only 20 of 63 races (31.7%) had both models select the same top pick. The systems are structurally different.

---

## Disagreement Analysis (43 disagreement races)

| Outcome | Count | Rate |
|---|---|---|
| R5 correct | 10 | 23.3% |
| CM correct | 10 | 23.3% |
| Neither correct | 23 | 53.5% |

**Exact dead heat at 10–10.** Neither system dominates in disagreements.

### CM-only wins (10 races)
| Date | Track | Race | CM | R5 | Winner | SP |
|---|---|---|---|---|---|---|
| 20260502 | CDX | 1 | 11 | 9 | POWERSHIFT | 4.14 |
| 20260502 | CDX | 9 | 4 | 8 | STARK CONTRAST | 4.40 |
| 20260502 | CDX | 14 | 6 | 9 | PRIZE PICK | 15.88 |
| 20260507 | CDX | 3 | 4 | 14 | GYPSY ART | 5.08 |
| 20260507 | CDX | 5 | 1 | 11 | LLAMP | 3.22 |
| 20260509 | BAQ | 1 | 4 | 6 | KARLEY B | 3.50 |
| 20260509 | BAQ | 7 | 6 | 3 | IRISH MAXIMA | 14.44 |
| 20260514 | CDX | 2 | 3 | 4 | GLOBAL SENSATION | 3.70 |
| 20260514 | CDX | 6 | 8 | 1 | CLASSIC CAR WASH | 8.82 |
| 20260516 | LRL | 4 | 1 | 2 | STRIKER HAS DIAL | 7.20 |

CM-only winner SP: min 3.22 / mean 7.04 / max 15.88. Stakes-heavy (4 Stakes + G1 + G2 = 6 of 10). Dirt-heavy (8 of 10). CDX-heavy (7 of 10).

### R5-only wins (10 races)
R5 mean SP 9.71 (inflated by SOLEIL VOLANT $52.06). Excluding that outlier: mean 4.56. Mid-range cluster (7 of 10 between 4.0–8.0 SP).

---

## CM Signal Analysis

| Signal | Fires | Wins | Win% | Notes |
|---|---|---|---|---|
| Consensus ≥ 4 | 39 | 12 | 30.8% | Actionable threshold |
| Consensus ≥ 4 (rank 1) | 39 | 12 | 30.8% | Key filter for R5 confirmation |
| Consensus level 7 | 4 | 2 | 50.0% | Best rate; too small a sample |
| Dominant flag | 96 | 20 | 20.8% | All ranks; context-dependent |
| A-tier (rank 1) | 63 | 16 | 25.4% | Baseline |
| Overlay Watch | 18 | 1 | 5.6% | **BROKEN** — definition needs revision |

### Per-category underline hit rate (rank=1 underlined)
| Category | Total | Wins | Win% |
|---|---|---|---|
| **Prime Power** | **57** | **19** | **33.3%** ← most reliable |
| Avg Speed | 47 | 10 | 21.3% |
| Best Speed | 52 | 10 | 19.2% |
| Distance Speed | 52 | 9 | 17.3% |
| Earnings | 62 | 10 | 16.1% |
| Jockey Rating | 38 | 3 | 7.9% |
| Trainer Rating | 12 | 0 | 0.0% |

---

## Segment Outperformance (CM > R5)

Segments where CM outperforms R5 by win rate (min 3 races):

| Segment | CM Win% | R5 Win% | Races | Note |
|---|---|---|---|---|
| **Non-graded Stakes** | **38.5%** | **15.4%** | 13 | Largest gap — clearest edge |
| CDX (Churchill) | 33.3% | 23.3% | 30 | Home-court advantage in sample |
| Dirt | 30.0% | 25.0% | 40 | Consistent across 40 races |
| G1 Stakes | 14.3% | 0.0% | 7 | Small sample |
| Field size 7–9 | 30.8% | 26.9% | 26 | Mid-sized fields |
| Field size 10+ | 25.8% | 22.6% | 31 | Large fields |

R5 outperforms CM on: Turf (15.8% vs 10.5%), BAQ/Aqueduct (31.6% vs 21.1%), Allowance/Opt-Clm races.

---

## Known Issues / v2 Candidates

### CM-1 — Overlay Watch definition broken
- Current: consensus ≥ 5 AND ML ≥ 6.0 → 18 fires, 5.6% win rate, −55.6% ROI
- Problem: Captures horses the market has correctly priced out; not genuine overlays
- Fix candidate: Raise consensus threshold to ≥ 6, or add pace/surface qualifier
- **Status:** Identified 2026-05-21. Do not use Overlay Watch signal as-is.

### CM-2 — Turf underperformance
- CM 10.5% on turf vs R5 15.8%. The category weights (speed-heavy) may not translate to turf.
- Fix candidate: Surface-specific weight sets (analogous to R5 Issue 7)
- **Status:** Proposed 2026-05-21.

### CM-3 — Trainer Rating near-zero signal
- 12 fires, 0 wins (0.0%). The `(wins/starts) × 100` formula with 5-start minimum is too raw.
- Fix candidate: Use BRIS trainer win% at the specific distance/surface/race-type combination
- **Status:** Proposed 2026-05-21.

### CM-4 — BRIS Top Pick field not located
- +2 bonus is silently skipped. If this field is found in future DRF inspection, adding it will change all scores.
- **Status:** Deferred. Find the field position before v2.

---

## CLI Reference

```bash
python comparemodels/comparemodels_cli.py score    <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py log      <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py results  <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py finalize <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py backfill
python comparemodels/comparemodels_cli.py compare
```

Isolation rules:
- r5_results.db: `sqlite3.connect("file:results/r5_results.db?mode=ro", uri=True)` — READ ONLY
- No imports from `Claude/` in `comparemodels/`
- All CM code lives in `comparemodels/` only

---

## Advisory Conclusion

CM and R5 tied on raw win rate (25.4% each). SP ROI diverges significantly: R5 +93.0% vs CM +50.6% — R5 finds better-priced winners. ML ROI is negative for both (−7.3% R5, −6.7% CM).

**Recommended deployment:** CM as a supplemental confidence filter on R5 selections.
- When R5 top pick also has CM consensus ≥ 4 → increased confidence, consider higher bet size
- When R5 top pick also has Prime Power underline → strongest CM confirmation signal (33.3%)
- When R5 and CM disagree AND CM consensus < 4 → lean R5
- Do NOT use CM as standalone replacement for R5
- Do NOT use Overlay Watch until definition is revised (CM-1)
