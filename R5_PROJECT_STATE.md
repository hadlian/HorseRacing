# R5 Handicapping System — Project State

> This document is the persistent context file for R5 development sessions.
> Update it after every meaningful session. It is the clean prompt source for Opus evaluations.
>
> **Last updated:** 2026-06-05 (Results pipeline complete — SAR 06/03-05 + older partials loaded; 157 races in DB)
> **Current version:** R5 v3.10
> **Primary AI collaborator:** Claude Code — all code implementation
> **Advisory:** Claude Sonnet (advisory only, no direct file edits), Opus (major arch decisions)

---

## 🆕 v3.8 — Stage 1 DRF Field Additions — 2026-05-29

- **Fields added:** 41 (AE/MTO from DRF), 58 (program post), 62 (medication/1st-time Lasix), 64 (equipment/blinkers), 1179 (best BRIS speed turf)
- **Scoring:** 1st-time Lasix +0.20; blinkers ON +0.10; blinkers OFF −0.05; turf `best_dist_n` uses best_turf; post bias uses updated program post when available
- **Display:** `[1stLasix]`, `[BlkON]`, `[BlkOFF]` row tags; "Best BRIS Turf" in top pick on turf; AE flag now available without scout
- **Stage 2 pending:** distance record into val_n, beaten-favorite signal, T/J meet blend, per-race class pars — all require 91-race backtest + val_n weight resolution first

## v3.7 — Tight Cluster Deduction (Issue 6) + Scout-3 AE Fix — 2026-05-28

- **Issue 6:** When top-3 composite spread ≤ 0.5 pts, apply -0.40 deduction to top horse (slips one tier, often swaps Rank 1↔Rank 2). Validated against 99-race DB: severe-cluster Rank 1 wins 17.1% vs Rank 2 wins 25.7%. Backtest delta: +3.0 pts overall win rate, +8.3 pts on severe subset.
- **Scout-3:** Fixed `scratchIndicator='A'` (Also-Eligible) being treated as scratch. AEs now scored and tagged `[AE]` in report. CDX0528 R7 #13 OUR STARRY NIGHT was the trigger case — drew in, finished 2nd at $8.04, missed entirely under old logic.
- **Report enhancements:** Field disclosure line (entries → starters); ALSO-ELIGIBLE warning; VERY TIGHT CLUSTER advisory with Rank 2 promotion notice.
- **Pending investigation:** val_n component winners avg -0.23 lower than losers across 99 races → chalk-heavy bias. Consider weight reduction or formula reformulation. Issue 16 (live odds) is the upstream fix.
- **2026-06-11 — STATUS: ACTIVE, CONFIRMED (Harry ruling).** Exact reconstruction
  (`scripts/reconstruct_tight_cluster.py`, 0 unexplained deltas / 1,747 picks)
  reversed the approximate corrected-ROI analysis: in the 33 fired races, the
  post-deduction rank-1 ran 25.9% win / −1.3% ROI vs the demoted horse's
  20.0% / −43.3% and the unfired rank-1 baseline of −47.8%. The deduction stays
  active; `pre_tight_comp` / `tight_cluster_severe` now persist to picks so all
  future validation is exact.

---

## 🎯 Project Goal

Build a data-driven handicapping engine for **premier thoroughbred racing**, with Saratoga 2026 as the first real-world deployment target. The system must perform well in graded stakes and high-class allowance fields — not calibrated for mid-week claiming cards.

---

## 📊 Results Database Status

> **⚠️ 2026-06-11 — ROI accounting corrected.** All ROI figures published before this date
> were inflated by a unit bug ($2 payoffs credited against $1 stakes). Authoritative numbers:
> `results/CORRECTED_BASELINE_2026-06.md` and `results/SIGNAL_VALIDATION_20260611.md`.
> Derby duplicate (DBY/CDX 0502 R12) removed; 2 payoff rows chart-corrected.

| Metric | Value | Notes |
|--------|-------|-------|
| Races with results | 160 | Post-dedupe, through SAR0605 (3 races pending; SAR0606 not loaded) |
| Top pick win rate | 23.1% | SAR new-track drag (9.4% in 32 races) pulling overall down |
| Top-3 hit rate | 59.4% | |
| Top pick flat-bet ROI | **−18.5%** | ≈ takeout — no win-bet edge yet. Corrected formula |
| Rank-3 flat-bet ROI | **+17.4%** | Only positive-ROI slot (23.2% win, 151 bets) — see signal validation |
| Play signal (spread ≥0.50) | **RETIRED** | Corrected ROI −40.3% vs −9.1% complement — selects chalk |
| FAIR tier rank-1 | 12.5% win, −70.2% ROI | HIGH: 0 fires ever; SOLID: 1 fire ever — tier ladder dead above FAIR |
| val_n ≥7 ROI | −8.2% | ≥8: +41.8% (4 wins), ≥9: +85.7% (2 wins) — gradient right, n too small |

### By track
| Track | Races | Win% | Top-3% |
|-------|-------|------|--------|
| BAQ | 19 | 31.6% | 63.2% |
| SAX | 10 | 30.0% | 50.0% |
| CDX | 82 | 26.8% | 56.1% |
| LRL | 13 | 15.4% | 61.5% |
| SAR | 32 | 9.4% | 53.1% — 3 days, new track |

### Cards logged
| Card | Races | Status |
|------|-------|--------|
| CDX 20260502 | 14 | Results loaded (partial — 1 missing) |
| DBY 20260502 | 1 | Results loaded (Golden Tempo $48.24, our Rank 5) |
| CDX 20260507 | 8 | Results loaded |
| BAQ 20260509 | 11 | Results loaded (1 missing) |
| CDX 20260514 | 8 | Results loaded — 4/8 wins (50%), best card to date |
| LRL 20260516 | 14 | Results loaded (1 missing) |
| CDX 20260521 | 8 | Results loaded — 2/8 wins |
| CDX 20260524 | 10 | Results loaded. 0 wins, 3 top-3. Sloppy track. |
| SAX 20260525 | 10 | Results loaded — 3/10 wins (30%) |
| CDX 20260528 | 8 | Results loaded |
| CDX 20260529 | 9 | Results loaded — 3/9 wins (33%) |
| CDX 20260530 | 11 | Results loaded — 5/11 wins (45%) |
| CDX 20260531 | 10 | Results loaded — 4/10 wins (40%), 9/10 top-3 (best board day) |
| SAR 20260603 | 10 | Results loaded — 0/10 wins, 6/10 top-3. R1 was hurdle race (skip). 5 second-place finishes. |
| SAR 20260604 | 11 | Results loaded — 1/11 wins. Scout fired on Corruption (+0.2). |
| SAR 20260605 | 14 | Results loaded (3 missing). 2/11 wins. |

### 60-race threshold
**60-race gate MET (157 races). Weight changes require explicit Harry approval + version bump.**

---

## 🔑 Key Findings to Date

1. **Graded stakes = best model environment.** Both G2 races on BAQ0509 (Peter Pan, Ruffian) had model winners inside Rank 2. FCI and TJ are most predictive in quality fields. Supports Saratoga target.

2. **Pace scenario validated.** HOT pace flag correctly identified closer-favoured setup in BAQ R6. Durante (Rank 5, closer) won at $16.50. Preakness 2026: 8 speed horses declared → HOT pace, MID/CLOSER styles favored, Ocelli (CLOSER) flagged as value alt.

3. **Rank 5 upsets (pattern).** Roman Grace, Durante, Arkhipov all won from Rank 5 on BAQ. Common pattern: one strong component (TJ or Trend) overwhelmed by FCI/Class drag. Supports TJ underweight thesis.

4. **Composite score ceiling problem.** No mid-week CDX race reaches SOLID tier (7.5). fci_n normalisation (baseline 60, ÷6) calibrated too high for lower-class fields. Dynamic normalisation needed — Issue 4.

5. **Value signal — CORRECTED 2026-06-11.** The "+172.9% ROI" was an accounting artifact ($2 payoffs vs $1 stakes) plus a double-counted Derby winner. Corrected: val_n≥7 = **−8.2%**; val_n≥8 = +41.8% and ≥9 = +85.7% but on 4 and 2 wins respectively — gradient direction is right, sample is not yet bettable. SOLEIL VOLANT ($52.06, val_n=10.0) remains the proof-of-concept catch. ROI is still the correct metric for this component; the corrected baseline is the reference.

6. **CDX0514 best card to date.** 4/8 top-pick wins (50%). Late scratch VIVIANITE (R8, #5, Rank 8) correctly caught by new --finalize command and set to finish_pos=-1.

7. **Preakness v3.5 retroactive test.** TAJ MAHAL ranked 1st (6.88 FAIR — only FAIR in the 14-horse field) with TJ=10.0, max Trend +5.0, PP=144.6. Scratched on race day. NAPOLEON SOLO (actual winner, $17.80) ranked 10th — low TJ (3.0) dragged it down despite PP=143.7 (3rd in field). HOT PACE (8 speed) correctly flagged; OCELLI (CLOSER, 6-1) was value alt — the correct closer angle. Model logic sound; outcome was a scratch event, not a miss.

8. **Scratch gate confirmed working** (via `run_r5.py --auto-scout`). When a Rank 1–3 horse is in the scout scratch list, the report prints `🚨 SCRATCH NOTICE` with the revised top pick and passes only active horses to `report()`. Running `r5_parser_v2.py` directly bypasses this (no scout data). Gap: scratches of Rank 4+ are silently removed with no notice.

---

## 🔀 CompareModels v1.0 — Parallel System (2026-05-21)

Full state doc: `comparemodels/COMPAREMODELS_STATE.md`
Report: `comparemodels/reports/comparemodels_vs_r5_63races_20260521_020626.xlsx`

**BRIS Summary methodology** — 8-category consensus scoring (Prime Power, Avg Speed, Best Speed, Distance Speed, Avg Class, Jockey Rating, Trainer Rating, Earnings). Scored independently from raw DRF data. No R5 code imported.

### Head-to-head — CORRECTED 2026-06-11 (152-race aligned universe, SAR-inclusive)

| Metric | CM | R5 (same races) |
|---|---|---|
| Top pick win rate | 25.7% | 23.3% |
| Flat-bet ROI ($2, corrected) | **−21.9%** | **−16.8%** |

The old "+50.6% / +93.0% SP ROI" figures were accounting artifacts — void. Neither model
beats takeout on flat win bets. CM wins slightly more, R5's winners pay more.
Full corrected signal table: `results/SIGNAL_VALIDATION_20260611.md`.

### CM segment outperformance
- **Non-graded Stakes:** CM 38.5% vs R5 15.4% (13 races) — strongest signal
- **Dirt:** CM 30.0% vs R5 25.0% (40 races)
- **CDX:** CM 33.3% vs R5 23.3% (30 races)

R5 outperforms CM on: Turf, BAQ, Allowance/Opt-Clm races.

### CM signals — CORRECTED 2026-06-11 (all confirmation filters failed ROI testing)
- **Consensus ≥ 4: RETIRED** — fires on 91% of races post field-fix (saturated), ROI −20.5%; negative at every level ≥5/≥6/≥7
- **Prime Power underline:** 31.5% win / **−9.6% ROI** standalone — best win-rate signal in the project but still loses flat-betting; stacked on R5 top pick it gets *worse* (−13.9%). Candidate exotics anchor only.
- **Agreement (R5+CM same pick): 32.2% win / −22.9% ROI** — chalk trap, do not increase bet size on agreement
- **Overlay Watch:** still broken, still retired

### Advisory integration — REVISED 2026-06-11
CM is **not** a confidence filter — every confirmation-style use is ROI-negative. Retained roles:
divergence flag (disagreement = potential value zone, R5 leg −12.8% = best relative leg, unproven),
and exotics contender-set generator (CM ranks 1–2 ∪ R5 ranks 1–3; CM rank-2 is +3.6% ROI,
R5 rank-3 is +17.4%). See `results/SIGNAL_VALIDATION_20260611.md`.

---

## 🔴 Open Issues — Engine (Priority Order)

All weight changes require explicit approval + version bump per spec rules.

| Issue | Description | Status | Priority |
|-------|-------------|--------|----------|
| 4 | Composite score ceiling — par-anchored fci_n + best_dist_n | **FIXED — v3.6, 2026-05-24** | ✅ |
| 6 | Crowded Room Penalty — score deduction (flag is live) | Pending post-Preakness validation | MODERATE |
| 7 | Surface-specific WS4 weights (dirt vs turf) | Gate lifted post-Preakness | MODERATE |
| 8 | Data scarcity confidence cap (per-horse, < 2 starts) | Proposed | MODERATE |
| 9 | Tight cluster UI flag (engine side of Issue 6) | Proposed | LOW |
| 10 | Surface weighting validation task | Gate lifted post-Preakness | VALIDATION |
| 11 | Distance-specific speed floor (best-at-distance) | Gate lifted post-Preakness | LOW |
| 12 | Career average class flag (dropdown angle) | Proposed | LOW |

**Note:** --auto-scout path bug fixed in v3.6 (uses `_scout_path`). API key env-var passthrough still requires manual pre-run of scout before --auto-scout.

---

## ✅ Completed Issues

| Issue | Fix | Version | Date |
|-------|-----|---------|------|
| 1 | Maiden/firster class_n=0.0 + [DEBUT] flag | v3.3 | 2026-05-09 |
| 2 | Value score inversion — floor raised max(1.0)→max(5.0) | v3.4 | 2026-05-10 |
| 3 | TJ weight 10%→15%; best_dist_n 8% + pp_n 5% added; bias 15→8%, val 10→5%, ped 10→7%, fci 25→22% | v3.5 | 2026-05-16 |
| 3a | result_fetched flag not set on direct SQL logging | v3.4 | 2026-05-12 |
| 5 | Scratch gate — revised top pick when Rank 1-3 scratched | v3.3 | 2026-05-10 |
| 6-display | TIGHT CLUSTER warning flag (display only, no deduction yet) | v3.4 | 2026-05-10 |
| 13 | Late scratch detection — auto-detect in apply_result(), --finalize command, two-tier analyze filter | v3.4 | 2026-05-15 |
| PDF-bug | NameError: `active` undefined in PDF block → replaced with filtered horses loop | v3.4 | 2026-05-15 |
| Scout | API model fix, track keyword expansion, auto-scout matching, stacking cap | v3.3 | 2026-05-09 |
| UI-1 | Mobile responsive design | v4.0 | 2026-05-10 |
| UI-webapp | PDF error surfacing, scratch notice regex fix, scratch-map pre-collection | v4.0 | 2026-05-16 |
| UI-2 | Analytics tab — Chart.js dashboard (4 charts: tier hits, val ROI, score dist, track/surface splits) | v4.0 | 2026-05-24 |
| 4 | Composite ceiling — par-anchored fci_n + best_dist_n; race header shows Par value | v3.6 | 2026-05-24 |
| auto-scout | --auto-scout path bug fixed (subprocess now uses _scout_path, not CWD) | v3.6 | 2026-05-24 |

---

## 🟡 Open Issues — UI (Priority Order)

All UI work in `webapp/`. Do not modify `Claude/` scripts in UI sessions.

| Issue | Description | Status |
|-------|-------------|--------|
| UI-2 | Analytics tab — Chart.js dashboard (tier hits, val ROI, score dist, track splits) | **COMPLETE — commit 872db8b** |
| UI-3 | Live odds divergence alerts | Not started |

---

## 🔵 Roadmap

| Phase | Version | Description | Gate |
|-------|---------|-------------|------|
| **Current** | **v3.10** | pp_n calibration (anchor 130→125); scout-before-finalize architecture; code-review fixes | **Live — 2026-06-03** |
| Next | v3.11+ | T/J meet combo signal; negative distance flag (−0.3 for <10% dist W%); pp_n anchor advisory | After 30+ SAR races |
| Future | v4.1 | Wager construction module (EX/TRI backtest) | After SAR calibration confirmed |
| Future | v4.x | Live odds divergence alerts (UI-3, Issue 16) | After v3.x validated |
| Future | v5.0 | ML pattern recognition, anomaly detection, LLM coaching summaries | Long term |
| Target | — | Saratoga 2026 deployment | **IN PROGRESS — Summer 2026** |

---

## 🏗️ Architecture

```
files 2/TRACK_MMDD.DRF   ← BRIS DRF input (1435 fields per record)
         │
  r5_parser_v2.py        ← Parse + score (9-component composite — v3.5)
         │
  r5_scout.py            ← Live intel via HRN, Blood-Horse, TDN + Claude API extraction
         │
  run_r5.py              ← Combine + print race card rankings
         │
  r5_tracker.py          ← Log picks to SQLite; --finalize for late scratch detection
         │
  r5_analyze.py          ← Performance analysis → Excel workbook (5 sheets)
         │
  webapp/app.py           ← Flask UI (localhost:5050)
```

**DB:** `results/r5_results.db` (SQLite)
**Stack:** Python 3.9+, Flask, SQLite, ReportLab, openpyxl, BeautifulSoup4, Anthropic API

---

## ⚖️ Current Composite Weights (v3.6 — LIVE 2026-05-24)

| Component | Weight | Field | Winner Diff (81 races) | Change from v3.4 |
|-----------|--------|-------|------------------------|------------------|
| FCI (WS4 + Trend) | 22% | fci_n | +0.61 | 25% → 22% |
| Class vs Speed Par | 13% | class_n | +0.59 | 20% → 13% |
| Trainer / Jockey | 15% | tj_n | +0.63 | **10% → 15%** |
| Best @ Distance | 8% | best_dist_n | — | **NEW v3.5** |
| Bias / Pace Fit | 8% | bias_n | −0.02 | 15% → 8% |
| Form Angle | 10% | form_n | +0.26 | unchanged |
| Pedigree | 7% | ped_n | +0.13 | 10% → 7% |
| Prime Power | 5% | pp_n | — | **NEW v3.5** |
| Value vs ML | 5% | val_n | −0.19 | 10% → 5% |

**v3.6 par-anchored normalisation:**
- `fci_n` = 5.0 + (fci − par_eff) / 5.0  where par_eff = clamp(par, 70, 105)
- `best_dist_n` = same formula applied to best-at-distance figure
- Debut / no figures: fci_n = 4.0 (slight negative vs neutral 5.0)
- Race header prints "Par {val}" for live validation

**Signal ranking (81 races, winner diff):**
tj_n +0.63 > fci_n +0.61 > class_n +0.59 > form_n +0.26 > ped_n +0.13 > bias_n −0.02 > val_n −0.19

---

## 🤖 AI Collaborator Notes

- **Claude Code** — all actual code implementation happens here.
- **Claude Sonnet** — primary session advisor, code snippets, architecture recommendations. Advisory only — never edits project files directly.
- **Opus** — reserved for major architectural decisions and weight evaluation sessions. Use with a clean, focused prompt: current weights + component correlations + race type breakdown + Saratoga context.
- **Gemini / ChatGPT** — design ideas and pseudocode only. Do not write to repo.

### When to escalate to Opus
- Post-v3.5 validation (next card, ~20 races) — did weight shift improve top-pick win rate?
- Phase 2 architectural planning (betting model, Kelly sizing)
- Saratoga-specific calibration session

---

## 📋 Session Log

| Date | Session | Key Outcomes |
|------|---------|--------------|
| 2026-05-09 | Engine fixes | Issues 1, Scout fixes resolved — v3.3 |
| 2026-05-10 | BAQ card + fixes | Issue 2 (val_n), Issue 5 (scratch), UI-1 (mobile) — v3.4. BAQ audit: graded stakes validated |
| 2026-05-12 | DB review | Issue 3a fixed. 34 races logged. Model frozen pre-Preakness |
| 2026-05-14 | CDX scout test | Scout and scratch report validated before CDX card |
| 2026-05-15 | CDX0514 results + Issue 13 | 4/8 wins (50%). Issue 13 built (late scratch detection, --finalize, two-tier filter). PDF NameError fixed. 50 races in DB. |
| 2026-05-16 | Preakness Day | LRL0516 scout + analysis run (14 races). HOT pace in Preakness. Memory + state files synced. Results pending. |
| 2026-05-16 | LRL0516 Results | R1–R13 logged. 2 wins (R7 OBLITERATION rank 1 $3.40, R9 TURF STAR rank 1 $10.40, R2 WICKEDDIVINE rank 1 $5.20). Preakness: NAPOLEON SOLO (rank 11) won $17.80. Rank-3 horses won R1/R3/R4/R6/R10/R11/R12. pgm-number mismatch noted on R2 and R5 (DRF vs official chart). 63 races in DB. |
| 2026-05-21 | CDX0521 live card | First v3.5 live card post-backfill. R5 2/8 wins, CM 2/8 wins (tied). Both agree on R3 SHINING MOMENT (cons=7 DOM, 5-cat underline, won at $3.96). CM edge: R2 SASSY PRINCESS (cons=7 DOM, $5.14). R5 edge: R1 LACK OF RIESLING ($8.00). Massive scratches (R1 had 7 scratches). Results loaded to r5_results.db + CM DB. Daily xlsx: `comparemodels/reports/CDX_20260521_daily.xlsx`. R5 analysis xlsx: `results/r5_analysis_20260521_2156.xlsx`. |
| 2026-05-21 | CompareModels v1.0 | Built full BRIS Summary parallel system in `comparemodels/`. Backfill: 63 races, 7 cards, 669 picks, 631 results joined. Head-to-head: CM 25.4% vs R5 25.4% (tied). SP ROI: CM +50.6% vs R5 +93.0%. Disagreements: 43 races, 10-10-23 (R5/CM/Neither). CM outperforms on non-graded Stakes (38.5% vs 15.4%) and Dirt (30.0% vs 25.0%). Key CM signals: consensus ≥4 (30.8%), Prime Power underline (33.3%). Overlay Watch broken (5.6% win rate). Advisory: CM as supplemental confidence filter on R5. |
| 2026-05-16 | Signal analysis + v3.5 | 63-race correlation analysis: prime_power, best_dist, best_life, best_fast, life_earn evaluated. best_fast eliminated (negative signal). Approved v3.5 weight rebalance: TJ 10→15%, best_dist_n NEW 8%, pp_n NEW 5%, bias 15→8%, val 10→5%, ped 10→7%, fci 25→22%. Commit 5678ff6. |
| 2026-05-16 | Preakness v3.5 test + scratch audit | Ran v3.5 retroactively on LRL R13 (Preakness). TAJ MAHAL Rank 1 (6.88 FAIR, TJ=10.0, PP=144.6) — scratched race day. NAPOLEON SOLO (winner $17.80) Rank 10 — low TJ dragged score despite strong PP. HOT pace + CLOSER value alt correctly flagged. Scratch gate confirmed working via run_r5.py --auto-scout; gap noted: Rank 4+ scratches silent. |
| 2026-05-24 | v3.6 + CDX0524 | Issue 4 fixed: par-anchored fci_n + best_dist_n (commit 5c103ff). auto-scout path bug fixed. UI-2 Analytics tab (Chart.js 4 charts) shipped (commit 872db8b). CDX0524 ran as first v3.6 live card (10 races). Results: 0 wins, 3 top-3 (R1 GLADLY 2nd, R8 BEING MYSELF 2nd, R10 SOLAIA 2nd). Sloppy track. R3/R7 top picks scratched. LAZLO R9 (FAIR/double-consensus) finished 7th. README + TODO brought current to v3.6. DB: 81 races. |
| 2026-05-28–31 | CDX live cards | CDX0528–0531 all run on v3.10. Best stretch of season. CDX0531: 4/10 wins, 9/10 top-3. CDX0530: 5/11 wins (45%). |
| 2026-06-03 | v3.10 + SAR opener | pp_n calibration complete (anchor 130→125). Scout-before-finalize architecture confirmed working. SAR0603 first Saratoga card: 0/10 wins, 6/10 top-3. R1 was hurdle race (skip). 5 second-place finishes. New-track calibration gap expected. |
| 2026-06-04 | SAR0604 | 11-race card. 1/11 wins (R6 Careless Whisper). Scout fired on Corruption (+0.2 trainer quote). R10 Corruption (FAIR) won Belmont Gold Cup G2T. |
| 2026-06-05 | Results pipeline | SAR0603-05 + CDX0502 + BAQ0509 + LRL0516 results all loaded. DB: 157 races. Memory + TODO + PROJECT_STATE all updated. |

---

## 📋 Immediate Next Steps

1. **Accumulate SAR data** — 3 days in, 9.4% win rate. Do not draw conclusions or adjust weights until 30+ SAR races. Speed winning NORMAL pace at SAR is worth tracking — may reflect track bias not yet captured.
2. **Hurdle/jump race skip rule** — R1 SAR 06/03 was a hurdle race (2 3/8M turf, all debut flags, Par N/A, 0 speed). Recognize and skip manually. No code change needed.
3. **FAIR tier inversion** — 13.0% win rate vs SPEC 27.2%. Small sample (23 races). Monitor through Saratoga before acting.
4. **T/J combo at SAR meet** — backtest when 2+ weeks of SAR data accumulated.
5. **Issue 15 (wager construction)** — gated on Saratoga calibration. Not before 60+ SAR races.
6. **Negative distance flag** — deferred post-Saratoga (need n≥60–80 on the negative flag subset).
7. **pp_n anchor advisory** — neutral anchor at pp=130 may be too high for lower-class fields. Get Gemini/ChatGPT input. Query: `SELECT median(prime_power) FROM picks WHERE prime_power > 0`.

---

*Update this file after each session. Keep the session log current. This is the handoff document for every new Claude conversation and for Opus evaluation sessions.*
