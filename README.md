# R5 Horse Racing Handicapping System

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-3.10-gold)]()
[![Status](https://img.shields.io/badge/status-Saratoga%20Ready-brightgreen)]()
[![License](https://img.shields.io/badge/license-Proprietary-blue)](#-license)

**Version:** 3.10 — deployed, weights frozen through Saratoga meet
**Saratoga opens:** July 3, 2026
**Operations guide:** [SARATOGA_OPERATIONS.md](SARATOGA_OPERATIONS.md)

A data-driven handicapping engine built on BRIS DRF files. Combines speed figures, pace analysis, trainer/jockey stats, pedigree, and probabilistic ranking into a composite score that ranks every horse in a field, generates a probability of winning for each, and produces exotic wager recommendations.

> ⚠️ **For personal use only.** This system is a research and analysis tool. All wagering decisions are the sole responsibility of the user.

---

## Project Origin & Authorship

The **R5 Handicapping System™** and the **R5 Composite Score™** were created by **Harry Adalian**.

All original algorithms, scoring formulas, pace analysis methods, and handicapping logic are the intellectual property of Harry Adalian. This project is actively developed and shared for collaboration and evaluation purposes.

© 2026–Present Harry Adalian. All rights reserved.

---

## Architecture

```
RacingData/files 2/TRACK_MMDD.DRF   ← BRIS DRF input (1,435 fields per record)
         │
  r5_parser_v2.py         ← Parse + 9-component composite + display fields
         │
  r5_probability.py       ← Conditional logit P(win) layer (β=0.7674)
         │
  r5_exotics.py           ← Contender set + structure menu + ticket gen/settle
         │
  r5_scout.py             ← Pre-race intel: trainer quotes, scratches, sharp money
         │
  run_r5.py               ← Master runner (--save --track --wet --live)
         │
  r5_tracker.py           ← SQLite logger; val_n tracker with guardrails
         │
  r5_payoffs.py           ← Chart PDF payoff ingestion (pdftotext -layout)
         │
  r5_analyze.py           ← Performance analysis → Excel workbook
         │
  webapp/app.py            ← Flask UI (localhost:5050)
```

**DB:** `Results/r5_results.db` (SQLite)

---

## R5 Composite Score (0–10) — v3.10

| Component | Weight | Source |
|-----------|--------|--------|
| Class vs Speed Par | **20%** | Race class vs pace pars |
| FCI (Speed + Trend) | 22% | BRIS speed figs, par-anchored normalisation |
| Trainer / Jockey | 15% | Actual win % (min 20 meet starts; elite-name fallback) |
| Form Angle | 10% | Recent race pattern |
| Best @ Distance | 8% | BRIS best speed at today's distance/surface |
| Bias / Pace Fit | 8% | Post bias + pace scenario fit |
| Pedigree | 7% | Distance/surface suitability |
| Value vs ML | 5% | Model-rank divergence from morning line |
| Prime Power | 5% | BRIS Prime Power figure |

**Weights are frozen through the Saratoga meet.** Any change requires Harry ruling + version bump.

**Confidence tiers (HIGH/SOLID/FAIR/SPEC) are retired** — they were zero-fires dead weight or inverse-performing. Output now shows P(win) and fair odds.

### WS4 (Weighted Speed)
```
WS4 = 0.4×S1 + 0.3×S2 + 0.2×S3 + 0.1×S4   (last 4 BRIS figs, same surface)
Trend = +5 if improving ≥4 pts, −5 if declining ≥4 pts, else 0
FCI = WS4 + Trend

fci_n = 5.0 + (fci − par_eff) / 5.0   where par_eff = clamp(par, 70, 105)
Debut / no figures: fci_n = 4.0
```

### P(win) Layer
```
comp_ex_val = Σ(weight/0.95) over the 8 non-val components  (market-free)
P(win)_i = exp(0.7674 × comp_ex_val_i) / Σ_j exp(0.7674 × comp_ex_val_j)
fair_odds = (1 − P) / P    (implied fair price)
edge = P × (final_odds + 1) − 1  (overlay when ≥ 0.25 AND P ≥ 0.08)
```

**OVERLAY flags are advisory only.** Live overlay win betting is NOT authorized (retro-test: −56.9% ROI on 142 bets).

---

## Quick Start — Race Card

```bash
# Activate your virtual environment
source venv/bin/activate   # or: source webapp/.venv/bin/activate

# Run a full card and save output
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --save --track

# With auto scouting (requires ANTHROPIC_API_KEY)
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --auto-scout --save --track

# Off-track day (surfaces may be muddy/wet)
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --wet --save --track

# Single race only
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --race 5

# Via web UI (easiest)
cd webapp && python app.py
# → open http://localhost:5050, drag-drop DRF file
```

---

## Exotics Module

```bash
# Generate paper tickets for a card (default — no real money)
python3 Claude/r5_exotics.py --track SAR --date 20260703

# Settle paper tickets after results are in
python3 Claude/r5_exotics.py --settle SAR 20260703

# Go live at $12 cap (Harry ruling required each card)
python3 Claude/r5_exotics.py --track SAR --date 20260703 --live

# View ticket summary
python3 Claude/r5_exotics.py --report SAR 20260703
```

**Structure menu:**
- **TIGHT** (top-3 spread ≤ 0.5): EX box + TRI box + r3 key (if ML ≥ 6-1)
- **STANDOUT** (r1−r2 spread ≥ 1.0): EX key r1/set + TRI key r1 over set
- **DEFAULT**: EX box r1+r2

**$12 cap per race.** Trim order: TRI third leg → rank-3 key → primary EX never dropped.

---

## Loading Results and Settling Tickets

```bash
# Step 1: Download chart PDF from Equibase → Results/2026/YYYYMMDDTRACKUSA0.pdf

# Step 2: Ingest chart payoffs
python3 Claude/r5_payoffs.py Results/2026/20260703SARUSA0.pdf

# Step 3: Load race results into picks DB
python3 Claude/r5_tracker.py --fetch SAR 20260703
# or manually:
python3 Claude/r5_tracker.py --manual SAR 20260703 5 "3,11,5,7" 6.20

# Step 4: Finalize late scratches
python3 Claude/r5_tracker.py --finalize SAR 20260703

# Step 5: Settle tickets
python3 Claude/r5_exotics.py --settle SAR 20260703

# Step 6: Generate analysis workbook
python3 Claude/r5_analyze.py
```

---

## Wet Track Workflow

The DRF does not contain today's track condition — it's generated before race day. Supply the condition at run time:

```bash
# When track is muddy, sloppy, or wet
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --wet --save --track
```

With `--wet`, the report prints a wet-track block for the top 3 contenders:
```
WET: #4 INCENTIVE PAY — 0-for-1 wet, best off-track BRIS 95
WET: #8 SENIOR OFFICER — no wet starts (first off-track)
```

Wet stats (fields 80–84: starts/wins/places/shows on off-tracks; field 1180: best off-track speed) are always parsed and logged — the `--wet` flag controls display only.

---

## Output — What to Look For

### Race header
```
SAR R5  1m Turf  $85k Allowance  10 starters  Par 113
pace profile 3E/EP vs 6P/S
```

### Horse table columns
`# | Horse (style) | ML | Q | WS4 | Trnd | FCI | vPar | Ped | T/J | Pce | Val | Comp | P(win)`

- **Q**: Quirin speed points (0–8); higher = more early pace
- **style**: run style appended to name — E (early), E/P, P (presser), S (closer)
- **P(win)**: probability of winning this race (conditional logit)
- **LAYOFF** tags: `[LAYOFF 45+]`, `[LAYOFF 90+]`, `[LAYOFF 180+]` in name cell

### Top-pick block
```
P(WIN): 31.2%  |  FAIR ODDS: 2.2-1  |  ML: 5-2  |  EDGE: +0.08
OVERLAY: ⚠️ P(win) × (final+1) = 1.29 ≥ 1.25 — ADVISORY ONLY (not authorized)
```

### val_n watch signal
```
VAL WATCH: val_n=8.4 — flag for guardrail tracker (flat $2 only, max 2/card)
```

### TRAINER ANGLES section
Firing categories for R5 ranks 1–3. `← LAYOFF MATCH` when horse is ≥45 days out and trainer fires in that spot.

---

## val_n Guardrail Rules

Flat $2 win bet, max 2 per card, evaluated before each live log:

| Stop condition | Rule |
|----------------|------|
| Win drought | 0 wins in last 30 settled bets |
| Loss limit | SUM(profit) < −$60 |
| Card limit | Already 2 val_n bets logged this card |

When any condition is met, `log_val_bet()` prints a refusal and does not log. No running total is stored — conditions are re-evaluated from the DB each time.

---

## Key Files

| File | Purpose |
|------|---------|
| `Claude/run_r5.py` | Master runner — start here |
| `Claude/r5_parser_v2.py` | DRF parser + composite scorer |
| `Claude/r5_probability.py` | P(win) layer, val_n tracker |
| `Claude/r5_exotics.py` | Exotic ticket generator + settler |
| `Claude/r5_payoffs.py` | Chart PDF payoff ingestion |
| `Claude/r5_tracker.py` | Results DB logger |
| `Claude/r5_analyze.py` | Performance analysis → Excel |
| `Claude/r5_scout.py` | Pre-race web intel (optional) |
| `Claude/R5_SPEC.md` | Full specification v3.10 |
| `R5_PROJECT_STATE.md` | Current system state (dev handoff) |
| `SARATOGA_OPERATIONS.md` | Opening-day operations guide |
| `TODO.md` | Task list + in-meet checkpoints |
| `Results/r5_results.db` | SQLite DB (picks, payoffs, tickets) |
| `Results/logit_beta.json` | β=0.7674 serialized |
| `Results/CORRECTED_BASELINE_2026-06.md` | Authoritative ROI baseline |
| `comparemodels/` | CompareModels v1.1 parallel system |

---

## Setup

```bash
# Python 3.9+
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 anthropic openpyxl reportlab

# Set Anthropic API key (for r5_scout.py only)
export ANTHROPIC_API_KEY="sk-ant-..."

# pdftotext is required for chart ingestion
# macOS: brew install poppler
```

Place BRIS DRF files in `~/Documents/RacingData/files 2/` (unzipped `.DRF`). Chart PDFs go in `~/Documents/RacingData/Results/2026/`. Both roots are configured in `Claude/r5_paths.py` (override via repo-root `.env` — see `.env.example`).

### Web UI

```bash
cd webapp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
# → open http://localhost:5050
```

---

## Roadmap

### Current: v3.10 (June 2026) — Saratoga Deploy
- ✅ 9-component composite (FCI, Class, TJ, Form, BestDist, Bias, Ped, PP, Val)
- ✅ Conditional logit P(win) layer (β=0.7674, comp_ex_val, val_n excluded)
- ✅ Exotics module: TIGHT/STANDOUT/DEFAULT menu, $12 cap, settlement self-test gated
- ✅ val_n tracker with guardrails (flat $2, max 2/card, hard stops)
- ✅ Payoff infrastructure: Equibase chart PDF ingestion, 174/179 races backfilled
- ✅ Display fields: run style/Quirin, LAYOFF tags, pace-profile header, wet-track bundle
- ✅ Trainer angles for full contender set (R5 ranks 1–3)
- ✅ Tier ladder retired; OVERLAY advisory only (−56.9% retro-test)
- ✅ CompareModels v1.1 (field-extraction corrected)
- ✅ Web frontend: P(win) badges, run-style display, corrected analytics

### In-Meet: v3.x (during Saratoga 2026)
- ⏳ Structure menu review (n≥40 SAR payoff races)
- ⏳ SAR-only β refit + tj_n year-stats fallback (n≥60 SAR races)
- ⏳ CM merge-or-keep (n≥100 SAR races)
- ⏳ val_n ≥8 re-decision (n≥120 qualifying bets)

### Mid-July 2026: v4.x
- 🔲 Live tote odds capture (Issue 16) — required for overlay reconsideration
- 🔲 Live odds divergence alerts in webapp (UI-3)

### Long-term: v5.0
- 🔲 Decorrelated P(win) upgrade (n≥300); overlay reconsideration paper-first
- 🔲 ML pattern recognition; anomaly detection; LLM coaching summaries

---

## Acknowledgments

### Contributors
- **Dennis Jersey** — Technical advisor — handicapping domain expertise, race analysis methodology, and real-world validation
- **[Claude AI](https://claude.ai)** (Anthropic) — AI development collaborator — code implementation, architecture, documentation
- **[ChatGPT](https://chat.openai.com)** (OpenAI) — AI research collaborator
- **[Gemini](https://gemini.google.com)** (Google) — AI research collaborator

### Built With
- **Flask** — Web framework
- **requests / BeautifulSoup4** — Scout web scraping
- **Anthropic Claude API** — Scout intel extraction
- **openpyxl** — Excel workbook generation
- **ReportLab** — PDF report generation
- **poppler / pdftotext** — Chart PDF extraction

---

## License

© 2026–Present Harry Adalian. All rights reserved.

This project is proprietary software. The R5 Composite Score™ algorithms, WS4™ speed formula, pace analysis methods, and handicapping logic are original intellectual property and may not be redistributed without explicit written permission.

## Trademark Notice

R5 Handicapping System™, R5 Composite Score™, and WS4™ are trademarks of Harry Adalian.

---

**Created and maintained by Harry Adalian** | **R5 Handicapping System™** | **R5 Composite Score™** | 🏇
