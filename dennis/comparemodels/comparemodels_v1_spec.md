# CompareModels v1 — Build Spec

**Purpose:** Independent parallel handicapping system implementing the BRIS Summary methodology. Runs against the same 63-race universe as R5 v3.4. Head-to-head comparison after backfill.

**Status:** Parallel build, no R5 contact until 63-race comparison complete.

---

## 1. Isolation Guarantee

CompareModels is a fully separate system. The following rules are non-negotiable:

- All CompareModels code lives in `comparemodels/` at the repo root
- Separate SQLite DB: `comparemodels/comparemodels_results.db`
- **Read-only access** to:
  - `results/r5_results.db` (for joining finish positions and R5 picks)
  - `files 2/*.DRF` (for source data)
  - `Claude/r5_parser_v2.py` (reference for DRF field positions only — **do not import**)
  - `scripts/recalc.py` — shared LibreOffice utility, no R5 imports, permitted to call
- **Zero touches** to: `Claude/`, `webapp/`, `results/r5_results.db`, any DRF file
- Field positions referenced from `r5_parser_v2.py` are copied as **literal integers** into `comparemodels/drf_to_csv.py`, never imported

---

## 2. Directory Structure

```
comparemodels/
├── __init__.py              (empty)
├── comparemodels_engine.py         scoring engine
├── drf_to_csv.py            DRF → Dennis CSV converter
├── comparemodels_tracker.py        DB logging + result joining
├── comparemodels_backfill.py       one-shot backfill runner
├── comparemodels_compare.py        head-to-head report generator
├── comparemodels_cli.py            entry point
├── comparemodels_results.db        SQLite (auto-created)
├── csv/                     generated per-card CSVs
│   └── TRACK_YYYYMMDD.csv
└── reports/                 generated comparison Excel files
    └── comparemodels_vs_r5_NNraces_TIMESTAMP.xlsx
```

---

## 3. Database Schema (`comparemodels_results.db`)

```sql
CREATE TABLE picks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track           TEXT NOT NULL,
    race_date       TEXT NOT NULL,        -- YYYYMMDD
    race            INTEGER NOT NULL,
    horse_pgm       TEXT NOT NULL,        -- program number (TEXT to handle 1A)
    horse_name      TEXT NOT NULL,
    morning_line    REAL,                 -- decimal odds (e.g. 7.0 means 6/1)
    cm_rank     INTEGER NOT NULL,     -- 1..N within race
    composite_score INTEGER NOT NULL,
    tier            TEXT,                 -- A / B / C
    consensus_count INTEGER,              -- appearances in top-3 category lists (max 8)
    is_dominant     INTEGER DEFAULT 0,    -- consensus >=4 AND underlined in >=1 category
    is_bris_pick    INTEGER DEFAULT 0,    -- BRIS Top Pick flag (NULL=0 if field absent)
    is_overlay      INTEGER DEFAULT 0,    -- consensus_count >=5 AND ML >= 6.0
    is_early_pace_leader INTEGER DEFAULT 0,
    is_late_pace_leader  INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(track, race_date, race, horse_pgm)
);

CREATE TABLE results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track           TEXT NOT NULL,
    race_date       TEXT NOT NULL,
    race            INTEGER NOT NULL,
    horse_pgm       TEXT NOT NULL,
    finish_position INTEGER,              -- 1, 2, 3, ... or -1 for scratch
    sp_odds         REAL,                 -- post-time SP (winner row only from r5; NULL others)
    source          TEXT,                 -- 'r5_db_join'
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(track, race_date, race, horse_pgm)
);

CREATE TABLE category_picks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track           TEXT NOT NULL,
    race_date       TEXT NOT NULL,
    race            INTEGER NOT NULL,
    category        TEXT NOT NULL,        -- 'Avg Speed', 'Prime Power', etc.
    rank_in_cat     INTEGER NOT NULL,     -- 1, 2, or 3
    horse_pgm       TEXT NOT NULL,
    horse_name      TEXT NOT NULL,
    raw_value       REAL,
    underlined      INTEGER DEFAULT 0,    -- 1 if gap rule fires (rank 1 only)
    UNIQUE(track, race_date, race, category, rank_in_cat)
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Keys: cm_version, backfill_complete, race_count, last_backfill_at
```

---

## 4. R5 Results DB — Confirmed Schema

Confirmed columns in `r5_results.db` relevant to Dennis:

**`picks` table:**
- `model_rank` — R5 rank within race (1 = top pick)
- `comp` — R5 composite score (0–10 float)
- `tier` — R5 confidence tier (HIGH / SOLID / FAIR / SPEC)
- `finish_pos` — finish position (integer; -1 = late scratch)
- `won` — 0/1 flag
- `sp_odds` — post-time SP, stored on winner row only
- `ml_odds` — morning line (decimal, e.g. 6.0 = 6/1)
- `track`, `date` (YYYYMMDD), `race` (integer), `pgm` (TEXT)

**`races` table:**
- `track`, `date`, `race_num`, `surface`, `dist_f`, `race_type`
- `purse`, `pace_scenario` (HOT/NORMAL/SLOW), `speed_count`

Join key: `track + date + race_num + pgm` across both tables.

---

## 5. DRF Filename Convention

Files live in `files 2/`. Pattern: **`{TRACK}{MMDD}.DRF`** (uppercase track code).

Examples: `BAQ0509.DRF`, `CDX0502.DRF`, `CDX0507.DRF`, `CDX0514.DRF`, `DBY0502.DRF`, `LRL0516.DRF`

**Path construction in backfill:**
```python
mmdd = race_date[4:8]   # e.g. "20260509" → "0509"
drf_path = f"files 2/{track.upper()}{mmdd}.DRF"
```

**Known edge case:** `DEL0513.DRF` exists in `files 2/` but Delaware Park is not in `r5_results.db`. The backfill iterates from the DB, so DEL0513 will never be requested — no action needed.

**`LRL0516.csv` exists in `files 2/`.** Inspect this file at Step 1. If it is a BRIS Summary CSV (columns matching Dennis input format), it can be used directly for LRL0516 instead of running the DRF converter for that card. Log the decision either way.

---

## 6. DRF → Dennis CSV Field Mapping

Source: BRIS comma-delimited DRF (1496 fields per row, one row per horse). Field positions are **1-indexed**.

### Confirmed Positions (verified against `r5_parser_v2.py`)

| Dennis CSV Column | DRF Field(s) | Derivation | Direction |
|---|---|---|---|
| Race | 3 | Literal | — |
| Horse Number | 4 | Literal (pgm) | — |
| Horse Name | 45 | Literal | — |
| Morning Line | 44 | See ML parsing note below | higher = longer odds |
| Avg Speed | 846–855 | Mean of non-null BRIS Speed values (past 10) | higher = better ✓ |
| Distance Speed | 1181 | Literal (best lifetime at today's distance) | higher = better ✓ |
| Best Speed | 1328 | Literal (best lifetime speed) | higher = better ✓ |
| Prime Power | 251 | Literal | higher = better ✓ |
| Jockey Rating | 35, 36 | `(jockey_wins / jockey_starts) × 100`; NULL if starts < 5 | higher = better ✓ |
| Trainer Rating | 29, 30 | `(trainer_wins / trainer_starts) × 100`; NULL if starts < 5 | higher = better ✓ |
| Earnings | 101 | Literal (lifetime earnings) | higher = better ✓ |

### Fields Requiring Resolution at Build Time

| Dennis CSV Column | Expected Source | Fallback | Direction |
|---|---|---|---|
| Avg Class | BRIS Race Class Rating past 10 (fields ~826–835, **verify**) | Use `purse` (DRF field 12) — do NOT fall back to speed | higher = better ✓ |
| Early Pace | BRIS E1/E2 ratings (locate via BRIS docs) | Mean of `pace_2f` fields 766–775, **inverted** (see note) | **INVERT** raw times |
| Late Pace | BRIS LP rating (locate via BRIS docs) | Mean of `pace_late` fields 816–825, **inverted** (see note) | **INVERT** raw times |
| BRIS Top Pick | BRIS-designated pick flag (locate via BRIS docs) | Write NULL — skip +2 bonus. **Do NOT synthesize.** | — |

### ML Odds Parsing

DRF field 44 may be stored as a fraction string (`"6-1"`, `"9-2"`) or as a decimal. Parse defensively:

```python
def parse_ml(raw):
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if "-" in s:
        parts = s.split("-")
        try:
            return float(parts[0]) / float(parts[1]) + 1  # "6-1" → 7.0
        except:
            return None
    try:
        return float(s)
    except:
        return None
```

Store result as REAL (e.g., 6/1 → stored as 7.0 for payout math, where `profit = (ml * 2) - 2` on a $2 win bet).

### Pace Direction Note

`pace_2f` (fields 766–775) and `pace_late` (816–825) from DRF are **raw fractional times in fifths of a second — lower = faster**. The Dennis engine scores descending (higher = better). When using raw times as pace proxy, invert before scoring:

```python
# Invert raw time: faster horse gets higher score
pace_score = 999.0 - raw_time_value   # preserves relative ordering, inverts direction
# Use pace_score for ranking; store raw_time_value in raw_value column of category_picks
```

If BRIS pace ratings are found (they are normalized, higher = better), no inversion needed — use directly.

### Rules

- Print a one-line decision log at the top of each generated CSV for all "resolve at build" fields:
  ```
  # Avg Class: purse (field 12) used as fallback — BRIS class fields not confirmed
  # Early Pace: pace_2f mean (fields 766-775), inverted
  ```
- Output one CSV per card: `comparemodels/csv/TRACK_YYYYMMDD.csv`
- No imports from `r5_parser_v2.py`

---

## 7. Dennis Engine (`comparemodels_engine.py`)

Port of the BRIS Summary master code with the modifications below.

### Category Weights

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

### Scoring Rules

- Top 3 per category by value (descending after direction adjustment)
- Points use **0-indexed rank**: `max(weight - rank_idx, 0)` where `rank_idx` is 0, 1, 2
  - rank_idx=0 → weight pts, rank_idx=1 → weight−1, rank_idx=2 → weight−2
- BRIS Top Pick flag adds **+2** to composite (skip silently if NULL/0)
- **Underline rule:** top horse in category gets `underlined=1` if it has ≥ 3 valid values AND `sorted_values[0] − sorted_values[2] ≥ 2.0`. Skip silently if fewer than 3 valid (non-null, non-NaN) values exist for the category.
- **Consensus count:** number of distinct top-3 category lists a horse appears in (max 8)
- **Dominant flag:** `consensus_count ≥ 4 AND horse appears as underlined in ≥ 1 category`. Derived from in-memory score dict BEFORE any DB write.
- **Overlay Watch:** `consensus_count ≥ 5 AND morning_line ≥ 6.0` (i.e., 5/1 or longer)
- A tier = rank 1; B tier = ranks 2–4; C tier = ranks 5–7; unranked = no tier

### Write Order (Critical)

`category_picks` must be populated from the in-memory score dict **before** computing `is_dominant`. Both tables are written from the same in-memory dict in a single function call — do not write `picks` first.

### Public API

```python
def score_race(race_df: pd.DataFrame) -> dict:
    """
    Returns:
    {
        "race": int,
        "ranked_horses": [
            {"pgm": str, "name": str, "composite": int, "rank": int,
             "tier": str, "consensus_count": int, "is_dominant": bool,
             "is_bris_pick": bool, "is_overlay": bool,
             "is_early_pace_leader": bool, "is_late_pace_leader": bool}, ...
        ],
        "category_picks": {
            "Avg Speed": [
                {"pgm": str, "name": str, "raw_value": float,
                 "rank_in_cat": int, "underlined": bool}, ...  # top 3
            ], ...
        },
        "early_pace_leader": str,  # pgm
        "late_pace_leader": str,   # pgm
    }
    """

def score_card(csv_path: str) -> dict:
    """Returns {race_num: score_race_output, ...}"""
```

---

## 8. Tracker (`comparemodels_tracker.py`)

Functions:

- `log_card(score_dict, track, race_date)` — write `category_picks` then `picks` from in-memory score dict. Idempotent via `INSERT OR REPLACE`.
- `pull_results(track, race_date)` — read-only join from `r5_results.db`:
  - Open with `sqlite3.connect("file:results/r5_results.db?mode=ro", uri=True)`
  - Pull `finish_pos`, `sp_odds`, `won`, `ml_odds` from `picks` table
  - Join on `track + date + race + pgm`
  - Write to Dennis `results` table; mark `source='r5_db_join'`
  - `sp_odds` will be NULL for non-winners (winner-only in R5 DB) — store as-is
- `finalize(track, race_date)` — detect late scratches (pgm in Dennis picks but absent from R5 results) → set `finish_position=-1`

---

## 9. Backfill (`comparemodels_backfill.py`)

```
Step 1: Inspect r5_results.db (READ ONLY)
        - Print schema of picks and races tables
        - Enumerate distinct (track, date) pairs WHERE result_fetched = 1
        - Print count — must be 63 races total across all cards
        - Inspect files 2/LRL0516.csv — print first 3 rows, determine if usable as Dennis input

Step 2: For each (track, date) card:
        a. Construct DRF path: f"files 2/{track.upper()}{date[4:8]}.DRF"
        b. Verify file exists — halt with clear error if not
        c. Run drf_to_csv → comparemodels/csv/TRACK_YYYYMMDD.csv
           (Exception: if LRL0516.csv is confirmed BRIS Summary format, use it directly)
        d. Run comparemodels_engine.score_card(csv_path)
        e. Call tracker.log_card(score_dict, track, date)
        f. Call tracker.pull_results(track, date)
        g. Print: "Card {track}{date}: {n_races} races, {n_picks} picks logged"

Step 3: Print final summary
        - Cards processed: N
        - Total races: N  ← HALT if ≠ 63
        - Total picks logged: N
        - Results joined: N
        - Any DRF files not found: list them

Step 4: Write meta table
        - cm_version = "1.0"
        - backfill_complete = "1"
        - race_count = "63"
        - last_backfill_at = current timestamp
```

Idempotent: `INSERT OR REPLACE` on all tables. Safe to re-run.

---

## 10. Comparison Report (`comparemodels_compare.py`)

Output: `comparemodels/reports/comparemodels_vs_r5_{N}races_{TIMESTAMP}.xlsx`

### Data Sources

- CompareModels data: `comparemodels/comparemodels_results.db` (picks + results + category_picks tables)
- R5 data: `results/r5_results.db` (picks + races tables, read-only)
- Join key across systems: `track + date + race_num`

### Sheets

**Sheet 1 — Summary**

Side-by-side metrics (no hardcoded values — all Excel formulas referencing Sheet 2):

| Metric | Dennis | R5 |
|---|---|---|
| Top Pick Win Rate | formula | formula |
| Top-3 Hit Rate | formula | formula |
| Avg SP on Top Pick Wins | formula | formula |
| ROI on ML (top pick, $2 win) | formula | formula |
| ROI on SP (top pick, $2 win) | formula | formula |
| Agreement Rate | formula | — |
| Disagreement Winner Rate | Dennis / R5 / Tie | — |
| A-tier Hit Rate | formula | — |
| HIGH-tier Hit Rate | — | formula |

**Sheet 2 — Race by Race** (one row per race, 63 rows)

Columns: Date, Track, Race, Surface, Distance, Race Type, Pace Scenario (from R5), R5 Pick, R5 Tier, R5 Score (comp), CompareModels Pick, CompareModels Tier, CompareModels Composite, CompareModels Consensus Count, Agreement (Y/N), Winner Name, Winner R5 Rank, Winner CompareModels Rank, SP, R5 Top-Pick Win (0/1), Dennis Top-Pick Win (0/1), R5 ML, CompareModels ML, R5 ROI Cell, CompareModels ROI Cell

**Sheet 3 — Breakdowns**

Pivot-style tables. All values are SUMIF/COUNTIF formulas referencing Sheet 2:

- By Track (BAQ, CDX, DBY, LRL)
- By Surface (D / T)
- By Race Type (G1/G2/G3 / Allowance / Maiden / Claiming / Stakes)
- By R5 Pace Scenario (HOT / NORMAL / SLOW)
- By Field Size (≤7 / 8–10 / ≥11)

**Sheet 4 — CompareModels Signals**

Diagnostic: does each CompareModels-specific feature have predictive value?

- A-tier win rate (races won when horse was Dennis rank 1)
- Dominant flag hit rate (win rate when `is_dominant=1`)
- Consensus count vs win rate (counts 1–8, with race count and win rate per level)
- Overlay Watch win rate and ROI
- Per-category underline hit rate (when a category fires the underline, does that horse win?)

**Sheet 5 — Disagreement Cases**

One row per race where CompareModels Rank 1 ≠ R5 Rank 1:
- Date, Track, Race, R5 Pick, R5 Score, CompareModels Pick, CompareModels Composite, Winner, Who Was Right, SP

### ROI Formula

For both ML and SP variants, applied uniformly to both systems:

```
If top pick won:   profit = (odds × 2) − 2
If top pick lost:  profit = −2
ROI % = (SUM(profit) / (race_count × 2)) × 100
```

SP-based ROI: `sp_odds` is winner-only in R5 DB. When top pick wins, SP is available. When top pick loses, profit = −2 regardless of SP — no SP needed. Formula works correctly.

ML-based ROI: use `ml_odds` column (available for all horses).

Use Excel formulas throughout. Run `scripts/recalc.py comparemodels/reports/...xlsx` after generation and confirm zero formula errors before session ends.

---

## 11. CLI (`comparemodels_cli.py`)

```bash
python comparemodels/comparemodels_cli.py score <TRACK> <YYYYMMDD>     # score card to stdout, no DB write
python comparemodels/comparemodels_cli.py log <TRACK> <YYYYMMDD>       # score + write picks to DB
python comparemodels/comparemodels_cli.py results <TRACK> <YYYYMMDD>   # pull finish positions from r5 DB
python comparemodels/comparemodels_cli.py finalize <TRACK> <YYYYMMDD>  # mark late scratches
python comparemodels/comparemodels_cli.py backfill                     # one-shot 63-race backfill
python comparemodels/comparemodels_cli.py compare                      # generate comparison report
```

---

## 12. Acceptance Criteria (all must pass before session ends)

1. ✅ `comparemodels_results.db` contains **exactly 63 races** in results table
2. ✅ Finish positions joined for all 63 races; `finish_position` NULL count = 0
3. ✅ Comparison report generates without error
4. ✅ `scripts/recalc.py` on the report returns `"status": "success"` with zero formula errors
5. ✅ All 4 ROI numbers populated in Summary sheet (CompareModels ML, CompareModels SP, R5 ML, R5 SP)
6. ✅ `results/r5_results.db` pre/post SHA-256 checksums match (print both)
7. ✅ `git status` shows only `comparemodels/` files as new/modified
8. ✅ `grep -r "from Claude" comparemodels/` returns empty (no R5 imports)

---

## 13. Non-Goals (explicitly out of scope)

- Dennis live odds or scout integration
- Dennis UI / webapp
- Dennis pace scenario logic (HOT/COOL)
- Modifying R5 in any way
- Mixing Dennis signals into R5 composite
- Unit tests (v1 — acceptance criteria are sufficient)
- Handling DEL0513.DRF (not in R5 DB, not in scope)

---

*Spec version: v1.1 — 2026-05-20*
*Changes from v1.0: DRF filename pattern (Sec 5), R5 DB schema confirmed (Sec 4), ML parsing logic (Sec 6), pace direction inversion (Sec 6), Avg Class fallback → purse (Sec 6), underline edge case guards (Sec 7), dominant flag write order (Sec 7), overlay definition clarified to consensus_count ≥ 5 (Sec 7), rank_index 0-indexed explicit (Sec 7), recalc.py carve-out from isolation rule (Sec 1), LRL0516.csv note (Sec 5), DEL0513 note (Sec 5)*
