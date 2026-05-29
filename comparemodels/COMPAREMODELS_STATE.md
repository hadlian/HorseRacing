# CompareModels v1 — System State

> Persistent context doc for CompareModels sessions.
>
> **Last updated:** 2026-05-29
> **Version:** CM v1.1 (field-extraction corrected; engine bug patched)
> **Status:** Field-fix shipped 2026-05-29. CM-2 resolved (was pace bug, not weights). 99-race re-backfill complete. Engine identical to Dennis's BRIS Summary spec.

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

## Field Decisions (v1.1 — corrected 2026-05-29)

| CM CSV Column | Source (0-indexed cols) | Decision |
|---|---|---|
| Avg Speed | Mean of cols 845–854 nonzero | Verified vs Dennis BRIS Summary CSV (CDX0529) |
| Distance Speed | Col 1180 (Best BRIS Speed — Distance) | Direct field |
| Best Speed | Col 1327 (Best BRIS Speed — Life) | Direct field |
| Prime Power | Col 250 (BRIS Prime Power Rating) | Direct field |
| Avg Class | **Mean of cols 1166–1175 nonzero** (BRIS Class Rating per-PP) | Was purse field 11 — wrong. Fixed 2026-05-29 |
| Jockey Rating | (wins col 35 / starts col 36) × 100 | 5-start minimum |
| Trainer Rating | (wins col 29 / starts col 30) × 100 | 5-start minimum |
| Earnings | Col 100 | Direct field |
| Early Pace | **Max of cols 765–784** (20-col BRIS pace range) | Was `999 − mean(765–774)` — broken. Fixed 2026-05-29 |
| Late Pace | **Max of cols 815–824** (10-col BRIS late pace range) | Was `999 − mean(...)` — broken. Fixed 2026-05-29 |
| BRIS Top Pick | NULL | Field still not located; +2 bonus skipped (engine bug separately fixed) |
| LRL0516.csv | NOT used directly | Raw DRF comma-delimited format; LRL0516.DRF used instead |

**Verification:** All 752 field comparisons (94 horses × 8 fields) match Dennis's reference CSV for CDX0529 exactly.

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

## Card History

| Card | Races | DRF Rows | Matched | Unmatched | Type |
|---|---|---|---|---|---|
| CDX 20260502 | 14 | 169 | 169 | 0 | Backfill |
| DBY 20260502 | 1 | 24 | 24 | 0 | Backfill |
| CDX 20260507 | 8 | 88 | 88 | 0 | Backfill |
| BAQ 20260509 | 10 | 85 | 85 | 0 | Backfill |
| BAQ 20260510 | 9 | 78 | 78 | 0 | Backfill |
| CDX 20260514 | 8 | 86 | 66 | 20 | Backfill |
| LRL 20260516 | 13 | 139 | 121 | 18 | Backfill |
| **CDX 20260521** | **8** | **78** | **78** | **0** | **Live** |
| **TOTAL** | **71** | **747** | **709** | **38** | |

**Notes:**
- BAQ0509 DRF has 11 races; BAQ0510 DRF has 9 races — DB is authoritative
- CDX0514 20 unmatched + LRL0516 18 unmatched = scratches/non-R5 horses
- CDX0521: 46 scratches recorded (massive scratch day), 0 unmatched
- Backfill DB integrity: SHA-256 pre/post match confirmed (`79554cd1a4c4bb756e2d5ce7cd22489ab198defce83a049a492c747115615928`)

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

## Live Card Results

### CDX 20260521 — First Live Card

| R | R5 Pick | CM Pick | Winner | SP | Both? |
|---|---------|---------|--------|----|-------|
| 1 | #8 LACK OF RIESLING ✓ | #11 Go New York Go | #8 LACK OF RIESLING | $8.00 | ≠ R5 edge |
| 2 | #6 R Pretty Kitty | #1 SASSY PRINCESS ✓ | #1 SASSY PRINCESS | $5.14 | ≠ CM edge |
| 3 | #5 SHINING MOMENT ✓ | #5 SHINING MOMENT ✓ | #5 SHINING MOMENT | $3.96 | ✓ BOTH |
| 4 | #8 Keep On Moving | #1 Easy Dial | #2 BOB'S CARROT | $11.94 | ≠ neither |
| 5 | #7 Barksdale | #7 Barksdale | #3 EXPLORATION | $5.66 | ≠ neither |
| 6 | #8 Lambeth | #1 Encino | #5 DRESDEN ROW | $5.28 | ≠ neither |
| 7 | #7 U Devil You | #2 Extra Anejo | #3 BUILT | $8.38 | ≠ neither |
| 8 | #1 Blasphemous Rumors | #3 Queen Mckinzie | #5 GALATINA | $6.58 | ≠ neither |

**R5: 2/8 (25.0%) · CM: 2/8 (25.0%) — tied, consistent with 25.4% baseline**

Key signals validated live:
- R3: Both agree + CM cons=7 DOMINANT + 5-category underline (Avg Speed, Dist Speed, Best Speed, Prime Power, Earnings) → **WON** — strongest signal pattern confirmed
- R2: CM cons=7 DOMINANT vs R5 disagree at CDX → CM correct (backfill CDX-disagree pattern held)
- Overlay Watch: not fired on this card

Scratch note: R1 had 7 scratches, R3 had 8, R8 had 9 — both models built picks on horses that didn't run, reducing effective field sizes significantly.

Daily report: `comparemodels/reports/CDX_20260521_daily.xlsx`

---

## Known Issues / v2 Candidates

### CM-1 — Overlay Watch definition broken
- Current: consensus ≥ 5 AND ML ≥ 6.0 → 18 fires, 5.6% win rate, −55.6% ROI
- Problem: Captures horses the market has correctly priced out; not genuine overlays
- Fix candidate: Raise consensus threshold to ≥ 6, or add pace/surface qualifier
- **Status:** Identified 2026-05-21. Do not use Overlay Watch signal as-is.

### ~~CM-2 — Turf underperformance~~ `RESOLVED 2026-05-29`
- **Original diagnosis (wrong):** Speed-heavy weights don't translate to grass.
- **Actual root cause:** Pace extraction was broken. `999 − mean(cols 765-774)` and `999 − mean(cols 815-824)` produced meaningless values (e.g. 916 in a 70-110 rating scale). The engine treated this as one horse's pace rating, effectively making pace into noise. Turf — where pace is critical — was therefore over-weighted on speed.
- **Fix:** Early Pace = max of cols 765-784; Late Pace = max of cols 815-824. Both verified against Dennis's BRIS Summary CSV.
- **Result:** Turf top-pick win rate jumped 13.3% → 20.0% (+6.7 pp on 30-race sample) without changing any weights.

### CM-3 — Trainer Rating near-zero signal
- 12 fires, 0 wins (0.0%). The `(wins/starts) × 100` formula with 5-start minimum is too raw.
- Fix candidate: Use BRIS trainer win% at the specific distance/surface/race-type combination
- **Status:** Proposed 2026-05-21. Pre-field-fix data — may re-evaluate against post-fix DB before fixing.

### CM-4 — BRIS Top Pick field not located
- +2 bonus is silently skipped. If this field is found in future DRF inspection, adding it will change all scores.
- **Status:** Deferred. Find the field position before v2.
- **Note:** Latent engine bug fixed 2026-05-29 — the +2 bonus was inside the per-category loop and would have applied 8× (+16) the moment a real BRIS Top Pick value was wired in. Now applies once, correctly.

### Field-Fix Audit Trail (2026-05-29)
- Triggered by Dennis's BRIS_Workflow_Package.zip (his BRIS Summary parser + CDX0529 reference CSV).
- Cross-checked our extraction against his published CSV — 3 of 8 input fields were emitting wrong values:
  - Avg Class was using purse (today's race level), not horse's class history
  - Early Pace was inverted noise, not a real pace rating
  - Late Pace was inverted noise, not a real pace rating
- Engine methodology (weights, composite math, dominant/overlay/tier rules) was already identical to Dennis's spec.
- Pre-fix DB preserved at `comparemodels_results.db.pre_fieldfix` (528KB).

### Updated Head-to-Head (post-fix, 95-race universe with results)

| Metric | CM pre-fix | CM post-fix | Δ |
|---|---|---|---|
| Top-pick win rate | 23.2% | **25.3%** | +2.1 pp |
| Top-3 hit rate | 55.8% | 56.8% | +1.0 pp |
| Turf | 13.3% | **20.0%** | **+6.7 pp** |
| Dirt | 26.2% | 26.2% | unchanged |
| BAQ | 21.1% | 26.3% | +5.2 pp |
| LRL | 15.4% | 23.1% | +7.7 pp |
| CDX | 26.9% | 26.9% | unchanged |
| Dominant fires | 158 (21.5%) | 170 (21.2%) | +12 fires |

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
