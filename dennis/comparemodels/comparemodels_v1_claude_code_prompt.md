# Claude Code Prompt — CompareModels v1 Build

**Paste this into a fresh Claude Code session. Companion document: `comparemodels_v1_spec.md` (v1.1).**

---

You are building **Dennis v1**, a parallel handicapping system that runs alongside R5 v3.4 for head-to-head comparison on the same 63-race universe. This is one focused session — build everything in `comparemodels/`, run the backfill, and produce the comparison report.

Read `comparemodels_v1_spec.md` in full before writing any code. It is the authoritative source.

---

## Critical isolation rules — non-negotiable

1. All CompareModels code lives in `comparemodels/` at the repo root. Nothing else is created or modified.
2. **Read-only access only** to:
   - `results/r5_results.db` — open as `sqlite3.connect("file:results/r5_results.db?mode=ro", uri=True)`
   - `files 2/*.DRF`
   - `Claude/r5_parser_v2.py` — reference for field positions only, **DO NOT IMPORT**
   - `scripts/recalc.py` — shared utility, permitted to call
3. **No imports from R5 modules** anywhere in `comparemodels/`. Copy field positions as literal integers.
4. Do not touch `Claude/`, `webapp/`, `results/r5_results.db`, or any DRF file.

---

## Build steps — execute in order

### Step 1 — Inspect and confirm before writing any code

```
a. Print SHA-256 checksum of results/r5_results.db  ← save this, you'll verify it at the end

b. Open results/r5_results.db (READ ONLY). Print:
   - Full schema of: picks, races tables
   - COUNT(*) from races WHERE result_fetched = 1  ← must be 63
   - Distinct (track, date) pairs with result counts
   - Confirm column names: model_rank, comp, tier, finish_pos, won, sp_odds, ml_odds, pgm

c. Inspect files 2/LRL0516.csv — print first 5 rows.
   Determine: is this a BRIS Summary CSV usable as Dennis input?
   Log your decision: use directly OR convert from DRF.

d. List all .DRF files in files 2/ and confirm they match the
   (track, date) pairs in r5_results.db (excluding DEL0513 which is expected to be absent).

HALT if race count ≠ 63. Do not proceed.
Print all Step 1 findings before writing any code.
```

### Step 2 — Create `comparemodels/` directory structure

Per spec Section 2. Create all files (empty stubs are fine at this stage).

### Step 3 — Build `comparemodels/drf_to_csv.py`

- Field mapping per spec Section 6
- ML parsing function per spec (fraction string → decimal)
- Pace inversion: if using raw pace_2f / pace_late times, apply `999.0 - raw` before scoring
- Avg Class fallback: use purse (field 12) if BRIS class fields cannot be confirmed — do NOT fall back to speed fields
- BRIS Top Pick: write NULL if field cannot be located with confidence — do NOT synthesize
- Write decision log as comments at top of each output CSV
- Test on one DRF file and print the first 3 rows of output before processing all cards

### Step 4 — Build `comparemodels/comparemodels_engine.py`

- Category weights per spec Section 7
- Points formula: `max(weight - rank_idx, 0)` where rank_idx is 0-indexed (0=first, 1=second, 2=third)
- Underline rule: only fire if ≥ 3 non-null values exist; `sorted_values[0] - sorted_values[2] >= 2.0`
- Dominant flag: derive from in-memory dict BEFORE any DB write. Do not query DB to compute it.
- Overlay: `consensus_count >= 5 AND morning_line >= 6.0`
- Return structured dict per spec public API

### Step 5 — Build `comparemodels/comparemodels_tracker.py`

- Schema per spec Section 3
- Write order: `category_picks` then `picks` — both from same in-memory dict
- `pull_results`: read-only join on r5 picks table using `track + date + race + pgm`
- `sp_odds` from R5 is winner-only — store as NULL for non-winners, that's correct
- `INSERT OR REPLACE` on all writes (idempotent)

### Step 6 — Build `comparemodels/comparemodels_backfill.py`

- Enumerate (track, date) pairs from r5_results.db races table
- DRF path: `f"files 2/{track.upper()}{date[4:8]}.DRF"`
- Per-card: convert → score → log_card → pull_results
- Print progress per card
- **HALT if total race count ≠ 63 after backfill**
- Print final summary with all counts

### Step 7 — Run the backfill

```bash
python comparemodels/comparemodels_backfill.py
```

Print the full output. If anything halts, report clearly and stop.

### Step 8 — Build `comparemodels/comparemodels_compare.py`

- 5 sheets per spec Section 10
- All metric values in Sheet 1 are Excel formulas referencing Sheet 2 — no hardcoded numbers
- All breakdown values in Sheet 3 are SUMIF/COUNTIF formulas
- ROI formula: win profit = `(odds * 2) - 2`; loss = `-2`; ROI = `(sum / (n*2)) * 100`
- Generate 4 ROI numbers: CompareModels ML, CompareModels SP, R5 ML, R5 SP
- Run `scripts/recalc.py` on output file
- **HALT if recalc returns any formula errors**

### Step 9 — Build `comparemodels/comparemodels_cli.py`

Subcommands per spec Section 11.

### Step 10 — Final verification

Run all acceptance criteria from spec Section 12:

```bash
# Criterion 6: verify r5_results.db unchanged
sha256sum results/r5_results.db   # must match Step 1 checksum

# Criterion 7: verify only comparemodels/ files modified
git status

# Criterion 8: verify no R5 imports
grep -r "from Claude" comparemodels/
grep -r "import r5" comparemodels/
```

Print results of all checks.

---

## Stop conditions — halt and ask Harry before proceeding

- Race count in r5_results.db is not 63
- Any DRF file in r5_results.db cannot be found in `files 2/`
- Avg Class or pace fields cannot be resolved with reasonable confidence AND purse fallback also fails
- Backfill produces race count ≠ 63
- recalc.py returns formula errors
- SHA-256 checksum of r5_results.db does not match pre/post

---

## Session-end summary (print when complete)

```
=== COMPAREMODELS V1 BUILD COMPLETE ===

Field mapping decisions:
  Avg Class:   [field used and confidence level]
  Early Pace:  [field used, inversion applied Y/N]
  Late Pace:   [field used, inversion applied Y/N]
  BRIS Top Pick: [field found Y/N; bonus applied Y/N]
  LRL0516.csv: [used directly Y/N]

Backfill counts:
  Cards processed:    N
  Races scored:       N  (must be 63)
  Picks logged:       N
  Results joined:     N

Comparison report headline metrics:
  CompareModels top pick win rate:  X.X%
  R5 top pick win rate:      X.X%  (should match 26.7% from r5_analysis)
  CompareModels top-3 hit rate:     X.X%
  R5 top-3 hit rate:         X.X%  (should match 55.6%)
  Agreement rate:            X.X%
  CompareModels ROI (ML):           X.X%
  CompareModels ROI (SP):           X.X%
  R5 ROI (ML):               X.X%
  R5 ROI (SP):               X.X%

Report path: comparemodels/reports/comparemodels_vs_r5_63races_TIMESTAMP.xlsx

Integrity checks:
  r5_results.db pre-checksum:  [hash]
  r5_results.db post-checksum: [hash]
  Match: YES / NO
  git status: [output]
  R5 import check: CLEAN / [violations]
```
