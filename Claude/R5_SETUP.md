# R5 Racing System — Setup Guide
# Version: R5_v3.2-R4C

## What's in this package

| File | Purpose |
|------|---------|
| `r5_parser_v2.py` | Core parser — reads BRIS DRF files, calculates WS4/Trend/FCI/Composite |
| `r5_scout.py` | Daily scraper — pulls news from HRN, TDN, Blood-Horse |
| `run_r5.py` | Master runner — combines scout intel + parser into full analysis |
| `r5_tracker.py` | Results logger — stores picks and actuals in SQLite |
| `r5_analyze.py` | Performance analysis — outputs Excel workbook |
| `r5_parse_results.py` | Equibase PDF parser — auto-loads result charts into DB |
| `r5_pdf.py` | PDF generator — presentation-quality race card output |
| `R5_SETUP.md` | This file |

---

## One-time setup (Mac)

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install Python dependencies
pip install requests beautifulsoup4 lxml anthropic openpyxl reportlab

# 3. Install poppler for PDF result parsing
brew install poppler

# 4. Set your Anthropic API key (Claude extracts intel from articles)
export ANTHROPIC_API_KEY=your_key_here
# Add to ~/.zshrc to make permanent:
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc
```

---

## Daily workflow

### Step 1 — Download the BRIS DRF file
1. Go to brisnet.com → Data Files → PP Data Files (single)
2. Select track + date, download the .DRF zip
3. Unzip and place `.DRF` file in `files 2/`

### Step 2 — Run analysis
```bash
cd /Users/harryadalian/Documents/HorseRacing
source venv/bin/activate

# Full card — txt output + log picks to DB
python3 Claude/run_r5.py "files 2/CD0503.DRF" --save --track

# Single race
python3 Claude/run_r5.py "files 2/CD0503.DRF" --race 5

# With auto-scout
python3 Claude/run_r5.py "files 2/CD0503.DRF" --save --track --auto-scout

# PDF presentation (on request only)
python3 Claude/run_r5.py "files 2/CD0503.DRF" --pdf
```

### Step 3 — Load results (after racing)
```bash
# Drop Equibase result chart PDF into results/ and run:
python3 Claude/r5_parse_results.py results/ChurchillDowns0503.pdf CD 20260503

# Or enter manually:
python3 Claude/r5_tracker.py --manual CD 20260503 8 "3,11,5,7" 6.20
```

### Step 4 — Analyze performance (after 10+ races)
```bash
python3 Claude/r5_analyze.py
python3 Claude/r5_analyze.py --track CD   # single track
```

---

## R5 Scoring Formula — v3.2-R4C

### WS4 — Weighted Speed
Weighted average of last 4 BRIS speed figures on the **same surface**:

```
WS4 = 0.4×S1 + 0.3×S2 + 0.2×S3 + 0.1×S4
```

Where S1 = most recent, S4 = oldest. Figures on a different surface are excluded.
If fewer than 2 same-surface figures exist, WS4 = None.

### Trend — Continuous Form Direction
Measures whether the horse is improving or declining relative to its recent average:

```
Trend = round(clamp((S1 - Avg(S2..S4)) / 2.0, -5.0, +5.0), 1)
```

- `S1` = most recent BRIS speed figure (same surface)
- `Avg(S2..S4)` = average of the remaining available figures (same surface)
- Result is clamped to the range [−5.0, +5.0] and rounded to 1 decimal
- A horse improving by 10+ points gets the maximum +5.0
- A horse declining by 10+ points gets the minimum −5.0

### FCI — Form/Class Index
```
FCI = WS4 + Trend
```

### Composite Score (0–10)

| Component | Weight | Source |
|-----------|--------|--------|
| FCI (WS4 + Trend) | 25% | BRIS speed figures, same surface |
| Class vs Speed Par | 20% | Race class par vs WS4 |
| Bias / Pace Fit | 15% | Track post bias + pace scenario fit |
| Trainer / Jockey | 10% | Actual win % (min 20 starts), scaled |
| Form Angle | 10% | Recent race pattern |
| Pedigree | 10% | Distance/surface suitability |
| Value vs ML | 10% | Model rank vs morning line rank divergence |

### Pace Scenario
Determined by count of speed horses in the field:

| Speed Count | Scenario | Bias |
|-------------|----------|------|
| ≥ 5 | HOT | Favours closers |
| 2–4 | NORMAL | Neutral |
| ≤ 1 | SLOW | Favours stalkers/closers |

Pace fit score combines post position bias (50%) and pace scenario fit (50%).

### Value Score
```
Value = 5.0 + (ML_odds_rank - model_rank) × 0.7
```
Positive = horse is a bigger price than the model expects (overlay).
Capped to the range [1.0, 10.0].

---

## Confidence Tiers

| Score | Tier | Meaning |
|-------|------|---------|
| ≥ 8.5 | HIGH | Strong play, bet confidently |
| 7.5–8.4 | SOLID | Good play, normal stake |
| 6.5–7.4 | FAIR | Use in exotics, small win bet |
| < 6.5 | SPECULATIVE | Exotics only or pass |

---

## Scout Adjustment Scale

| Signal | Adjustment |
|--------|-----------|
| Positive trainer quote | +0.20 |
| Sharp money move | +0.15 |
| Bullet workout (last 7d) | +0.10 |
| First-time blinkers | +0.10 |
| Jockey upgrade to elite | +0.10 |
| Workout concern | −0.15 |
| Equipment removed | −0.05 |
| Negative trainer signal | −0.30 |
| Health concern | −0.30 |
| Scratch | Removed from field |

---

## Directory Layout

```
HorseRacing/
├── Claude/                  ← R5 scripts
│   ├── run_r5.py
│   ├── r5_parser_v2.py
│   ├── r5_scout.py
│   ├── r5_tracker.py
│   ├── r5_analyze.py
│   ├── r5_parse_results.py
│   ├── r5_pdf.py
│   └── R5_SETUP.md          ← this file
├── files 2/                 ← BRIS .DRF input (not in git)
├── results/                 ← SQLite DB, PDFs, Excel reports (not in git)
│   └── results_template.csv
├── scout/                   ← Scout JSON cache (not in git)
└── venv/                    ← Python virtual environment (not in git)
```
