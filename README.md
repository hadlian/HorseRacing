# R5 Horse Racing Handicapping System

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-3.3-gold)]()
[![Status](https://img.shields.io/badge/status-Active%20Development-brightgreen)]()
[![License](https://img.shields.io/badge/license-Proprietary-blue)](#-license)

**Version:** 3.3

**Status:** Active Development

A data-driven handicapping engine built on BRIS DRF files. Combines speed figures, pace analysis, trainer/jockey stats, pedigree, and live scouting into a single composite score that ranks every horse in a field.

> ⚠️ **For personal use only.** This system is a research and analysis tool. All wagering decisions are the sole responsibility of the user.

---

## Project Origin & Authorship

The **R5 Handicapping System™** and the **R5 Composite Score™** were created by **Harry Adalian** ([@hadlian](https://github.com/hadlian)).

All original algorithms, scoring formulas, pace analysis methods, and handicapping logic are the intellectual property of Harry Adalian. This project is actively developed and shared for collaboration and evaluation purposes.

© 2026–Present Harry Adalian. All rights reserved.

---

## System Overview

```
files 2/TRACK_MMDD.DRF   ← BRIS DRF input
         │
         ▼
  r5_parser_v2.py         ← Parse + score every horse
         │
  r5_scout.py             ← Scrape trainer quotes, scratches, sharp money
         │
  run_r5.py               ← Combine + print race card rankings
         │
  r5_tracker.py           ← Log picks to SQLite (opt-in)
         │
  r5_analyze.py           ← Performance analysis → Excel workbook
```

---

## R5 Composite Score (0–10)

| Component        | Weight | Source |
|------------------|--------|--------|
| FCI (Speed+Trend)| 25%    | BRIS speed figs, same surface |
| Class vs Par     | 20%    | Race class vs pace pars |
| Bias/Pace Fit    | 15%    | Track post bias + pace scenario fit |
| Trainer/Jockey   | 10%    | Actual win % (min 20 starts) |
| Form Angle       | 10%    | Recent race pattern |
| Pedigree         | 10%    | Distance/surface suitability |
| Value vs ML      | 10%    | Model rank divergence from morning line |

**Confidence Tiers:** `HIGH ≥8.5` | `SOLID 7.5–8.4` | `FAIR 6.5–7.4` | `SPECULATIVE <6.5`

### WS4 (Weighted Speed)
```
WS4 = 0.4×S1 + 0.3×S2 + 0.2×S3 + 0.1×S4   (last 4 BRIS figs, same surface)
Trend = continuous: (S1 − avg_rest) / 2.0, capped ±5
FCI = WS4 + Trend
```

---

## Scripts

### `Claude/r5_parser_v2.py`
Core DRF parser and scoring engine.
- Parses BRIS `.DRF` fixed-format CSV (1496 fields per record)
- `parse_drf(path)` → list of horse dicts with all 7 component scores
- `finalize_field(horses)` → two-pass field context: pace scenario + value scores
- `report(horses)` → prints ranked race card to stdout
- `tier(score)` → confidence tier label

### `Claude/r5_scout.py`
Web scraper for live pre-race intel.
- Sources: Horse Racing Nation, Blood-Horse, TDN
- Searches by track-specific keywords (e.g. "Kentucky Derby", "Churchill")
- Claude API (claude-haiku) extracts structured JSON: scratches, trainer quotes, sharp money, workout notes, equipment changes, jockey switches
- `format_for_r5(intel)` → formatted text block for report header

### `Claude/run_r5.py`
Master runner — combines parser + scout.

```bash
# Basic analysis
python3 Claude/run_r5.py "files 2/DBY0502.DRF"

# With auto scouting
python3 Claude/run_r5.py "files 2/DBY0502.DRF" --auto-scout

# Single race only
python3 Claude/run_r5.py "files 2/DBY0502.DRF" --race 12

# Save output to file
python3 Claude/run_r5.py "files 2/DBY0502.DRF" --save

# Log picks to results DB (opt-in)
python3 Claude/run_r5.py "files 2/DBY0502.DRF" --track

# Full pipeline
python3 Claude/run_r5.py "files 2/DBY0502.DRF" --auto-scout --save --track
```

### `Claude/r5_tracker.py`
SQLite-backed results logger. Stores picks and records actual finishes.

```bash
# View pending races (no results yet)
python3 Claude/r5_tracker.py --status

# Auto-fetch results from Equibase / HRN
python3 Claude/r5_tracker.py --fetch CD 20260502

# Enter results manually: track date race "1st,2nd,3rd,4th" [SP_winner]
python3 Claude/r5_tracker.py --manual DBY 20260502 12 "15,6,14,1" 18.40

# Bulk load from CSV
python3 Claude/r5_tracker.py --csv results/results_template.csv
```

**CSV format:**
```csv
track,date,race,finish,sp_winner
DBY,20260502,12,"15,6,14,1",18.40
```

### `Claude/r5_analyze.py`
Performance analysis — reads SQLite DB, outputs Excel workbook.

```bash
python3 Claude/r5_analyze.py                 # all tracks
python3 Claude/r5_analyze.py --track CD      # single track
python3 Claude/r5_analyze.py --out my.xlsx   # custom filename
```

**Excel sheets:**
- **Summary** — top pick %, top-3 hit rate, value ROI, HIGH tier hit rate
- **Race by Race** — every race logged with winner rank and SP
- **Component Correlations** — which of the 7 components best predicts winners
- **Value ROI** — ROI curve across val_n thresholds (6.0–10.0)
- **Scout Impact** — horses with scout adjustments vs without

---

## Web Frontend

A browser-based UI for running analyses without touching the command line.

```bash
cd webapp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
# → open http://localhost:5050
```

| Feature | Detail |
|---------|--------|
| Upload | Drag-drop or browse — `.DRF` or `.ZIP`, multiple files OK |
| Overview toggle | 📋 Overview: one-row-per-race card summary; 🏇 Race Detail: full tabbed view |
| Race tabs | One tab per race, instant switching; click Overview row to jump |
| Horse table | WS4, Trend, FCI, vPar, Ped, T/J, Pace, Val, Comp, Tier — colour-coded |
| Pick boxes | Top Win Pick (green) and Value Alt (gold) |
| Bet Recommendation | PLAY (comp ≥ 6.0) / NEAR (5.5–5.99) / SKIP (<5.5) with For/Against bullets |
| Exotics | Win / Exacta / Trifecta / Superfecta |
| Raw text | Full formatted output in collapsible block |
| Downloads | TXT (always) + PDF (tick "Generate PDF" before uploading) |

See [`webapp/README.md`](webapp/README.md) for full options and troubleshooting.

---

## Setup (CLI)

```bash
# Python 3.9+
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 anthropic openpyxl

# Set Anthropic API key (for r5_scout.py)
export ANTHROPIC_API_KEY="sk-ant-..."
```

Place BRIS DRF files in `files 2/` (unzipped `.DRF`).

---

## Directory Layout

```
HorseRacing/
├── Claude/                  ← R5 scripts (this repo)
│   ├── run_r5.py
│   ├── r5_parser_v2.py
│   ├── r5_scout.py
│   ├── r5_tracker.py
│   ├── r5_analyze.py
│   └── R5_SETUP.md
├── webapp/                  ← Web frontend (Flask)
│   ├── app.py               ← Flask server + output parser
│   ├── requirements.txt     ← Flask only
│   ├── README.md            ← Setup + usage for the web UI
│   └── templates/
│       └── index.html       ← Single-page UI
├── files 2/                 ← BRIS .DRF input files (not in git)
├── results/                 ← SQLite DB + Excel reports (not in git)
│   └── results_template.csv ← CSV template for manual result entry
├── scout/                   ← Scout JSON cache (not in git)
└── venv/                    ← Python virtual environment (not in git)
```

---

## Typical Workflow

### Via Web UI (easiest)
```bash
cd webapp && source .venv/bin/activate
python app.py
# Drop DRF or ZIP onto http://localhost:5050, click Analyze
```

### Via CLI
```bash
source venv/bin/activate

# Morning of race day
python3 Claude/run_r5.py "files 2/CD0503.DRF" --auto-scout --save --track

# After races run
python3 Claude/r5_tracker.py --manual CD 20260503 8 "3,11,5,7" 6.20

# Weekly review (after 10+ races)
python3 Claude/r5_analyze.py
open results/r5_analysis_20260503_*.xlsx
```

---

## Scout Adjustments

Applied to composite score before final ranking:

| Signal | Adjustment |
|--------|-----------|
| Positive trainer quote | +0.20 |
| Sharp money | +0.15 |
| Bullet workout | +0.10 |
| First-time blinkers | +0.10 |
| Elite jockey switch | +0.10 |
| Workout concern | −0.15 |
| Negative trainer signal | −0.30 |
| Health concern | −0.30 |
| Scratch | Removed from field |

---

## 🗺️ Roadmap

### Current Version: v3.3 (May 2026)
- ✅ **DRF Parser** — Fixed-format BRIS DRF parsing (1496 fields per record), full 7-component scoring pipeline
- ✅ **WS4™ Speed Formula** — Weighted 4-race speed figure with continuous trend, surface-matched
- ✅ **Pace Scenario Engine** — HOT / NML / PRESS classification; speed horse vs closer fit scoring
- ✅ **Web Scout** — Live pre-race intel from Horse Racing Nation, Blood-Horse, TDN via Claude API
- ✅ **Results Tracker** — SQLite-backed logger with manual entry, CSV bulk load, and auto-fetch from Equibase/HRN
- ✅ **Performance Analyzer** — Excel workbook with 5 sheets: Summary, Race by Race, Component Correlations, Value ROI, Scout Impact
- ✅ **Web Frontend** — Flask upload UI with structured race cards, colour-coded horse table, pick boxes, and exotic suggestions
- ✅ **Bet Recommendation** — PLAY / NEAR / SKIP verdict driven by R5 Composite Score™ with For/Against rationale bullets
- ✅ **Overview Toggle** — Card-level summary table (📋 Overview) alongside full tabbed race detail (🏇 Race Detail)
- ✅ **PDF Download** — ReportLab-generated PDF reports via `--pdf` flag or web UI checkbox
- ✅ **Maiden/Firster Class Fix** — First-time starters with no BRIS speed figures now receive `class_n=0.0`; `[DEBUT]` flag surfaced in report output

### Upcoming: v3.4 — Remaining Engine Fixes
- 🔲 **Value Score Inversion** — Formula direction inverted; ML-favoured horses the model ranks low receive suppressed value scores instead of elevated ones
- 🔲 **T/J Weight Recalibration** — Raise T/J from 10% → 15%; offset via Class, Bias, Ped reductions (pending value fix first)
- 🔲 **Composite Ceiling** — Scores rarely exceed 8.5; `fci_n` normalisation calibrated for higher-class horses than typical mid-week undercards
- 🔲 **Scratch Gate** — No automatic fallback to next active ranked horse when top pick scratches
- 🔲 **Crowded Room Penalty** — Top-3 within ≤1.5 comp points gets no low-conviction flag; validate threshold against results data before implementing
- 🔲 **Data Scarcity Cap** — Per-horse confidence reduction when horse has < 2 lifetime starts; field-level `LOW INFO` warning when >30% of field is low-data

### Upcoming: v4.0 — UI Enhancements
- 🔲 **Mobile Refinement** — Responsive CSS for the horse table; readable on phone at the track
- 🔲 **Historical ROI Dashboard** — Pull logged races from `r5_tracker.py` SQLite DB and display interactive ROI and hit-rate charts directly in the web UI
- 🔲 **Live Odds Integration** — Compare morning line prices against a live odds feed; surface divergence alerts when the board moves significantly off the R5 model rank

### Upcoming: v5.0 — Intelligence Layer
- 🔲 ML-powered lap time prediction and pattern recognition
- 🔲 Anomaly detection for workout and form angle outliers
- 🔲 Optional LLM coaching summaries per race

---

## 🙏 Acknowledgments

### Contributors
- **Dennis Jersey** — Technical advisor — handicapping domain expertise, race analysis methodology, and real-world validation
- **[Claude AI](https://claude.ai)** (Anthropic) — AI development collaborator — code implementation, architecture, documentation, and scoring system design
- **[ChatGPT](https://chat.openai.com)** (OpenAI) — AI research and development collaborator
- **[Gemini](https://gemini.google.com)** (Google) — AI research and development collaborator

### Built With
- **Flask** — Web framework
- **requests / BeautifulSoup4** — Scout web scraping
- **Anthropic Claude API** — Scout intel extraction
- **openpyxl** — Excel workbook generation
- **ReportLab** — PDF report generation

---

## 📝 License

© 2026–Present Harry Adalian. All rights reserved.

This project is proprietary software created by Harry Adalian.

The source code is shared for collaboration and evaluation purposes. The R5 Composite Score™ algorithms, WS4™ speed formula, pace analysis methods, and handicapping logic are original intellectual property and may not be redistributed or republished without explicit written permission from the author.

Third-party dependencies used in this project (Flask, requests, BeautifulSoup4, openpyxl, ReportLab, etc.) retain their respective open-source licenses.

---

## 📞 Contact & Support

- **Author:** Harry Adalian ([@hadlian](https://github.com/hadlian))
- **Repository:** [github.com/hadlian/HorseRacing](https://github.com/hadlian/HorseRacing)
- **Issues & Support:** [GitHub Issues](https://github.com/hadlian/HorseRacing/issues)

## Trademark Notice

R5 Handicapping System™, R5 Composite Score™, and WS4™ are trademarks of Harry Adalian.
The R5 name, WS4 formula, and associated branding are not licensed under the software license of this project and may not be used without explicit written permission from the author.

---

**Created and maintained by Harry Adalian** | **R5 Handicapping System™** | **R5 Composite Score™** | 🏇
