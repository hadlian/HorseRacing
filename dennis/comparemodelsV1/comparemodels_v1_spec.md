# CompareModels v1 — Build Spec

**Purpose:** Independent parallel handicapping system implementing the BRIS Summary methodology. Runs against the same 63-race universe as R5 (v3.4/v3.5). Head-to-head comparison after backfill.

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
├── __init__.py                    (empty)
├── comparemodels_engine.py        scoring engine
├── drf_to_csv.py                  DRF → CompareModels CSV converter
├── comparemodels_tracker.py       DB logging + result joining
├── comparemodels_backfill.py      one-shot backfill runner
├── comparemodels_compare.py       head-to-head report generator
├── comparemodels_cli.py           entry point
├── comparemodels_results.db       SQLite (auto-created)
├── csv/                           generated per-card CSVs
│   └── TRACK_YYYYMMDD.csv
└── reports/                       generated comparison Excel files
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
    cm_rank         INTEGER NOT NULL,     -- 1..N within race
    composite_score INTEGER NOT NULL,
    tier            TEXT,                 -- A / B / C
    consensus_count INTEGER,              -- appearances in top-3 category lists (max 8)
    is_dominant     INTEGER DEFAULT 0,    -- consensus >=4 AND underlined in >=1 category
    is_bris_pick    INTEGER DEFAULT 0,    -- BRIS Top Pick flag (0 if field absent)
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

Confirmed columns in `r5_results.db` relevant to CompareModels:

**`picks` table:**
- `race_id` — foreign key to `races.id`
- `pgm` — program number (TEXT)
- `model_rank` — R5 rank within race (1 = top pick)
- `comp` — R5 composite score (float)
- `tier` — R5 confidence tier (HIGH / SOLID / FAIR / SPEC)
- `finish_pos` — finish position (integer; -1 = late scratch)
- `won` — 0/1 flag
- `sp_odds` — post-time SP, stored on **winner row only**
- `ml_odds` — morning line (decimal, e.g. 6.0 = 6/1)

**`races` table:**
- `id` — primary key (joined from picks.race_id)
- `track`, `date` (YYYYMMDD), `race_num` (integer)
- `surface`, `dist_f`, `race_type`
- `purse`, `pace_scenario` (HOT/NORMAL/SLOW), `speed_count`

**Join path for `pull_results`:**
```sql
SELECT p.pgm, p.finish_pos, p.sp_odds, p.won, p.ml_odds, p.model_rank, p.comp, p.tier
FROM picks p
JOIN races r ON p.race_id = r.id
WHERE r.track = ? AND r.date = ? AND r.race_num = ?
```

---

## 5. DRF Filename Convention + Track Code Normalisation

Files live in `files 2/`. Pattern: **`{TRACK}{MMDD}.DRF`** (uppercase DB track code).

Examples: `BAQ0509.DRF`, `CDX0502.DRF`, `CDX0507.DRF`, `CDX0514.DRF`, `DBY0502.DRF`, `LRL0516.DRF`

**Path construction in backfill:**
```python
mmdd = race_date[4:8]   # e.g. "20260509" → "0509"
drf_path = f"files 2/{track.upper()}{mmdd}.DRF"
```

**Track code normalisation — CRITICAL:**
DRF field 1 returns the internal BRIS track code (e.g., `'CD'`), which differs from the DB track code (`'CDX'`). This mismatch has caused backfill failures before. Always use the DB track code as the authoritative join key, and normalise on parse:

```python
TRACK_MAP = {
    'CD':  'CDX',
    'AP':  'APX',
    'SA':  'SAX',
    # extend as needed
}

def normalise_track(raw: str) -> str:
    t = raw.strip().upper()
    return TRACK_MAP.get(t, t)
```

Apply `normalise_track()` to DRF field 1 when writing the CSV — use the normalised code as the track key throughout.

**Known edge case:** `DEL0513.DRF` exists in `files 2/` but Delaware Park is not in `r5_results.db`. The backfill iterates from the DB, so DEL0513 will never be requested — no action needed.

**`LRL0516.csv` exists in `files 2/`.** Inspect this file at Step 1. If it is a BRIS Summary CSV (columns matching CompareModels input format), it can be used directly for LRL0516 instead of running the DRF converter for that card. Log the decision either way.

---

## 6. DRF → CompareModels CSV Field Mapping

Source: BRIS comma-delimited DRF (1496 fields per row, one row per horse). Field positions are **1-indexed**.

### Confirmed Positions (verified against `r5_parser_v2.py`)

| CM CSV Column | DRF Field(s) | Derivation | Direction |
|---|---|---|---|
| Race | 3 | Literal | — |
| Horse Number | 4 | Literal (pgm) | — |
| Horse Name | 45 | Literal | — |
| Morning Line | 44 | See ML parsing note below | — |
| Avg Speed | 846–855 | Mean of non-null BRIS Speed values (past 10) | higher = better ✓ |
| Distance Speed | 1181 | Literal (best lifetime at today's distance) | higher = better ✓ |
| Best Speed | 1328 | Literal (best lifetime speed) | higher = better ✓ |
| Prime Power | 251 | Literal | higher = better ✓ |
| Jockey Rating | 35, 36 | `(jockey_wins / jockey_starts) × 100`; NULL if starts < 5 | higher = better ✓ |
| Trainer Rating | 29, 30 | `(trainer_wins / trainer_starts) × 100`; NULL if starts < 5 | higher = better ✓ |
| Earnings | 101 | Literal (lifetime earnings) | higher = better ✓ |

### Fields Requiring Resolution at Build Time

| CM CSV Column | Expected Source | Fallback | Direction |
|---|---|---|---|
| Avg Class | BRIS Race Class Rating past 10 (fields ~826–835) | **Use `purse` (DRF field 12).** R5 confirmed to not use BRIS class rating fields — it uses `speed_par` (field 217) instead. Agent should default to purse without extended search. | higher = better ✓ |
| Early Pace | BRIS E1/E2 ratings (locate via BRIS docs) | Mean of `pace_2f` fields 766–775, **inverted** (see note) | **INVERT** raw times |
| Late Pace | BRIS LP rating (locate via BRIS docs) | Mean of `pace_late` fields 816–825, **inverted** (see note) | **INVERT** raw times |
| BRIS Top Pick | BRIS-designated pick flag | Write NULL — skip +2 bonus. **Do NOT synthesize.** | — |

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

Store result as REAL. Payout math: `profit = (ml * 2) - 2` on a $2 win bet (e.g., 6/1 stored as 7.0 → profit = $12).

### Pace Direction Note

`pace_2f` (fields 766–775) and `pace_late` (816–825) from DRF are **raw fractional times — lower = faster**. The engine scores descending (higher = better). Invert before scoring:

```python
pace_score = 999.0 - raw_time_value   # faster horse gets higher score
# Store raw_time_value in raw_value column of category_picks
```

If BRIS pace ratings are located (normalized, higher = better), use directly with no inversion.

### Rules

- Print a one-line decision log at the top of each generated CSV for all resolved fields:
  ```
  # Avg Class: purse (field 12) — R5 confirmed not to use BRIS class rating fields
  # Early Pace: pace_2f mean (fields 766-775), inverted
  ```
- Output one CSV per card: `comparemodels/csv/TRACK_YYYYMMDD.csv`
- No imports from `r5_parser_v2.py`

---

## 7. CompareModels Engine (`comparemodels_engine.py`)

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
- BRIS Top Pick adds **+2** to composite (skip silently if NULL/0)
- **Underline rule:** only fire if ≥ 3 non-null values AND `sorted_values[0] − sorted_values[2] ≥ 2.0`
- **Consensus count:** distinct top-3 category lists a horse appears in (max 8)
- **Dominant flag:** `consensus_count ≥ 4 AND underlined in ≥ 1 category`. Derived from in-memory dict **before** any DB write.
- **Overlay Watch:** `consensus_count ≥ 5 AND morning_line ≥ 6.0`
- A tier = rank 1; B tier = ranks 2–4; C tier = ranks 5–7

### Write Order (Critical)

Derive `is_dominant` from the in-memory score dict. Write `category_picks` then `picks` — both from the same in-memory dict in a single function call.

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
        "early_pace_leader": str,   # pgm
        "late_pace_leader": str,    # pgm
    }
    """

def score_card(csv_path: str) -> dict:
    """Returns {race_num: score_race_output, ...}"""
```

---

## 8. Tracker (`comparemodels_tracker.py`)

Functions:

- `log_card(score_dict, track, race_date)` — write `category_picks` then `picks`. Idempotent via `INSERT OR REPLACE`.
- `pull_results(track, race_date)` — read-only join from `r5_results.db`:
  - Open with `sqlite3.connect("file:results/r5_results.db?mode=ro", uri=True)`
  - Use the confirmed join path (Section 4):
    ```sql
    SELECT p.pgm, p.finish_pos, p.sp_odds, p.won, p.ml_odds
    FROM picks p
    JOIN races r ON p.race_id = r.id
    WHERE r.track = ? AND r.date = ? AND r.race_num = ?
    ```
  - Write to CompareModels `results` table; mark `source='r5_db_join'`
  - `sp_odds` will be NULL for non-winners — store as-is, this is correct
- `finalize(track, race_date)` — detect late scratches (pgm in CM picks absent from R5 results) → set `finish_position=-1`

---

## 9. Backfill (`comparemodels_backfill.py`)

```
Step 1: Inspect r5_results.db (READ ONLY)
        - Print SHA-256 checksum of results/r5_results.db  ← save this
        - Print full schema of picks and races tables
        - COUNT(*) from races WHERE result_fetched = 1  ← must be 63
        - Print distinct (track, date) pairs with race counts
        - Inspect files 2/LRL0516.csv — print first 5 rows;
          determine if usable as CM input; log decision

        HALT if race count ≠ 63.

Step 2: For each (track, date) card:
        a. Construct DRF path: f"files 2/{track.upper()}{date[4:8]}.DRF"
        b. Verify file exists — halt with clear error if not
        c. Run drf_to_csv → comparemodels/csv/TRACK_YYYYMMDD.csv
           (Exception: if LRL0516.csv confirmed BRIS Summary format, use directly)
        d. Run comparemodels_engine.score_card(csv_path)
        e. Call tracker.log_card(score_dict, track, date)
        f. Call tracker.pull_results(track, date)
        g. Print: "Card {track}{date}: {n_races} races, {n_picks} picks logged"

Step 3: Print final summary
        - Cards processed: N
        - Total races: N  ← HALT if ≠ 63
        - Total picks logged: N
        - Results joined (matched pgm): N
        - Results unmatched (CM horse not in R5 DB): N  ← log, do not fail
        - Any DRF files not found: list them
```

Idempotent: `INSERT OR REPLACE` on all tables. Safe to re-run.

---

## 10. Comparison Report (`comparemodels_compare.py`)

Output: `comparemodels/reports/comparemodels_vs_r5_{N}races_{TIMESTAMP}.xlsx`

### Data Sources

- CM data: `comparemodels/comparemodels_results.db`
- R5 data: `results/r5_results.db` (read-only, join via picks → races on race_id)
- Alignment key: `track + date + race_num`

### Sheets

**Sheet 1 — Summary** (all values are Excel formulas referencing Sheet 2)

| Metric | CompareModels | R5 |
|---|---|---|
| Top Pick Win Rate | formula | formula |
| Top-3 Hit Rate | formula | formula |
| Avg SP on Top Pick Wins | formula | formula |
| ROI on ML (top pick, $2 win) | formula | formula |
| ROI on SP (top pick, $2 win) | formula | formula |
| Agreement Rate | formula | — |
| Disagreement Winner Rate | CM / R5 / Tie | — |
| A-tier Hit Rate | formula | — |
| HIGH-tier Hit Rate | — | formula |

**Sheet 2 — Race by Race** (63 rows)

Columns: Date, Track, Race, Surface, Distance, Race Type, Pace Scenario (from R5), R5 Pick, R5 Tier, R5 Score, CM Pick, CM Tier, CM Composite, CM Consensus Count, Agreement (Y/N), Winner Name, Winner R5 Rank, Winner CM Rank, SP, R5 Win (0/1), CM Win (0/1), R5 ML, CM ML, R5 ROI, CM ROI

**Sheet 3 — Breakdowns** (SUMIF/COUNTIF formulas referencing Sheet 2)

Split by: Track / Surface / Race Type / R5 Pace Scenario / Field Size

**Sheet 4 — CM Signals**

- A-tier win rate
- Dominant flag hit rate
- Consensus count vs win rate (levels 1–8)
- Overlay Watch win rate and ROI
- Per-category underline hit rate

**Sheet 5 — Disagreement Cases**

One row per race where CM Rank 1 ≠ R5 Rank 1: Date, Track, Race, R5 Pick, R5 Score, CM Pick, CM Composite, Winner, Who Was Right, SP

### ROI Formula

```
Win:  profit = (odds × 2) − 2
Loss: profit = −2
ROI % = (SUM(profit) / (race_count × 2)) × 100
```

Four ROI numbers: CM ML, CM SP, R5 ML, R5 SP. SP-based: when top pick wins, sp_odds is available; when it loses, profit = −2 regardless — formula is correct.

Run `scripts/recalc.py comparemodels/reports/...xlsx` after generation. **HALT if any formula errors.**

---

## 11. CLI (`comparemodels_cli.py`)

```bash
python comparemodels/comparemodels_cli.py score <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py log <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py results <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py finalize <TRACK> <YYYYMMDD>
python comparemodels/comparemodels_cli.py backfill
python comparemodels/comparemodels_cli.py compare
```

---

## 12. Acceptance Criteria (all must pass before session ends)

1. ✅ `comparemodels_results.db` contains **exactly 63 races** in results table
2. ✅ Finish positions joined for all horses where R5 has a matching pgm entry; unmatched horses logged but do not fail this criterion
3. ✅ Comparison report generates without error
4. ✅ `scripts/recalc.py` returns `"status": "success"` with zero formula errors
5. ✅ All 4 ROI numbers populated in Summary sheet (CM ML, CM SP, R5 ML, R5 SP)
6. ✅ `results/r5_results.db` pre/post SHA-256 checksums match
7. ✅ `git status` shows only `comparemodels/` files as new/modified
8. ✅ `grep -r "from Claude" comparemodels/` returns empty

---

## 13. Non-Goals

- Live odds or scout integration
- UI / webapp
- Pace scenario logic (HOT/COOL)
- Modifying R5 in any way
- Mixing CM signals into R5 composite
- Unit tests (acceptance criteria sufficient for v1)
- Handling DEL0513.DRF

---

*Spec version: v1.2 — 2026-05-20*
*Changes from v1.1: version tag updated to R5 v3.4/v3.5 (Issue 1); TRACK_MAP normalisation added Section 5 (Issue 2 — prior backfill bug); pull_results SQL join path specified Section 8 (Issue 5); Acceptance criterion 2 softened for unmatched pgm (Issue 3); Avg Class confirmed to use purse fallback — R5 does not use BRIS class rating fields (Issue 4 resolved definitively from parser inspection)*
