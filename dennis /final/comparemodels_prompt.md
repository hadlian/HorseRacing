# Claude Code Prompt — CompareModels v1 Build

**Paste this into a fresh Claude Code session. Companion document: `comparemodels_v1_spec.md` (v1.3).**

---

You are building **CompareModels v1**, a parallel handicapping system implementing the BRIS Summary methodology alongside R5 for head-to-head comparison on the same 63-race universe. One session — build everything in `comparemodels/`, run the backfill, produce the comparison report.

Read `comparemodels_v1_spec.md` in full before writing any code.

---

## Critical isolation rules — non-negotiable

1. All code lives in `comparemodels/` at the repo root. Nothing else is created or modified.
2. **Read-only access only** to:
   - `results/r5_results.db` — open as `sqlite3.connect("file:results/r5_results.db?mode=ro", uri=True)`
   - `files 2/*.DRF`
   - `Claude/r5_parser_v2.py` — field position reference only, **DO NOT IMPORT**
   - `scripts/recalc.py` — shared utility, permitted to call
3. **No imports from R5 modules** anywhere in `comparemodels/`
4. Do not touch `Claude/`, `webapp/`, `results/r5_results.db`, or any DRF file

---

## Build steps — execute in order

### Step 1 — Inspect before writing any code

```
a. SHA-256 checksum of results/r5_results.db  ← record this

b. Open r5_results.db READ ONLY:
   - Print full schema of picks and races tables
   - COUNT races WHERE result_fetched = 1  ← must be 63; HALT if not
   - Print distinct (track, date) pairs with counts
   - Confirm column names: model_rank, comp, tier, finish_pos, won,
     sp_odds, ml_odds, pgm, race_id

c. Inspect files 2/LRL0516.csv — print first 5 rows.
   Determine: usable as CM input directly, or must convert from DRF?
   Log your decision.

d. List all .DRF files in files 2/ and confirm they cover all
   (track, date) pairs in r5_results.db (DEL0513 will be extra — expected).

Print all findings before writing any code.
```

### Step 2 — Create `comparemodels/` directory and stub files

Per spec Section 2.

### Step 3 — Build `comparemodels/drf_to_csv.py`

- Field mapping per spec Section 6
- **Apply TRACK_MAP normalisation** (spec Section 5) to DRF field 1 — `'CD'` → `'CDX'` etc. This has caused backfill failures before.
- ML parsing function per spec (handles fraction strings and decimals)
- Avg Class: use purse (field 12) directly — R5 confirmed to not use BRIS class rating fields, so no extended search needed. Log this in CSV header.
- Pace fields: if using raw times, apply `999.0 - raw` inversion
- BRIS Top Pick: NULL if not located — do NOT synthesize
- Test on one DRF file, print first 3 rows before processing all cards

### Step 4 — Build `comparemodels/comparemodels_engine.py`

- Weights, scoring, underline, dominant, overlay per spec Section 7
- rank_idx is **0-indexed**
- Derive `is_dominant` from in-memory dict before any DB write
- Underline: only fire if ≥ 3 non-null values

### Step 5 — Build `comparemodels/comparemodels_tracker.py`

- Schema per spec Section 3
- `pull_results` uses the exact SQL join from spec Section 4:
  ```sql
  SELECT p.pgm, p.finish_pos, p.sp_odds, p.won, p.ml_odds
  FROM picks p
  JOIN races r ON p.race_id = r.id
  WHERE r.track = ? AND r.date = ? AND r.race_num = ?
  ```
- Write order: `category_picks` then `picks`
- `INSERT OR REPLACE` throughout (idempotent)

### Step 6 — Build `comparemodels/comparemodels_backfill.py`

- Per spec Section 9
- DRF path: `f"files 2/{track.upper()}{date[4:8]}.DRF"`
- Print progress per card
- HALT if total race count ≠ 63
- Log unmatched pgms (CM horse not in R5 DB) — do not fail on them

### Step 7 — Run the backfill

```bash
python comparemodels/comparemodels_backfill.py
```

Print full output. Halt and report if anything fails.

### Step 8 — Build `comparemodels/comparemodels_compare.py`

- 5 sheets per spec Section 10
- All Sheet 1 values: Excel formulas referencing Sheet 2 — no hardcoded numbers
- All Sheet 3 breakdowns: SUMIF/COUNTIF formulas
- 4 ROI numbers: CM ML, CM SP, R5 ML, R5 SP
- Run `scripts/recalc.py` on output — **HALT if formula errors**

### Step 9 — Build `comparemodels/comparemodels_cli.py`

Subcommands per spec Section 11.

### Step 10 — Final verification

```bash
sha256sum results/r5_results.db        # must match Step 1 checksum
git status                             # only comparemodels/ files
grep -r "from Claude" comparemodels/   # must be empty
grep -r "import r5" comparemodels/     # must be empty
```

---

## Stop conditions — halt and ask Harry

- Race count in r5_results.db ≠ 63
- Any DRF file not found (excluding DEL0513)
- Backfill race count ≠ 63
- recalc.py returns formula errors
- SHA-256 mismatch on r5_results.db

---

## Session-end summary (print when complete)

```
=== COMPAREMODELS V1 BUILD COMPLETE ===

Field decisions:
  Avg Class:      purse (field 12) — confirmed per spec
  Early Pace:     [field used, inversion Y/N]
  Late Pace:      [field used, inversion Y/N]
  BRIS Top Pick:  [found Y/N]
  LRL0516.csv:    [used directly Y/N]

Backfill:
  Cards processed:       N
  Races scored:          N  (must be 63)
  Picks logged:          N
  Results joined:        N
  Unmatched pgms:        N

Comparison headline metrics:
  CM top pick win rate:    X.X%
  R5 top pick win rate:    X.X%  (expect ~26.7%)
  CM top-3 hit rate:       X.X%
  R5 top-3 hit rate:       X.X%  (expect ~55.6%)
  Agreement rate:          X.X%
  CM ROI (ML):             X.X%
  CM ROI (SP):             X.X%
  R5 ROI (ML):             X.X%
  R5 ROI (SP):             X.X%

Report: comparemodels/reports/comparemodels_vs_r5_63races_TIMESTAMP.xlsx

Integrity:
  r5_results.db pre:   [hash]
  r5_results.db post:  [hash]
  Match:               YES / NO
  git status:          [output]
  Import check:        CLEAN / [violations]
```
