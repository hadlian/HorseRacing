# R5 Handicapping System — Project State

> This document is the persistent context file for R5 development sessions.
> Update it after every meaningful session. It is the clean prompt source for Opus evaluations.
>
> **Last updated:** 2026-05-24 (CDX0524 results logged — 0 wins, sloppy track, 3 top-3 hits)
> **Current version:** R5 v3.6
> **Primary AI collaborator:** Claude Code — all code implementation
> **Advisory:** Claude Sonnet (advisory only, no direct file edits), Opus (major arch decisions)

---

## 🎯 Project Goal

Build a data-driven handicapping engine for **premier thoroughbred racing**, with Saratoga 2026 as the first real-world deployment target. The system must perform well in graded stakes and high-class allowance fields — not calibrated for mid-week claiming cards.

---

## 📊 Results Database Status

| Metric | Value | Notes |
|--------|-------|-------|
| Races with results | 81 | Through CDX0524 (10 races added) |
| Top pick win rate | 24.3% | Issue 14 fix applied — 5th+ finishers now counted as losses |
| Top-3 hit rate | 54.3% | ~44/81 races |
| TJ signal strength | +0.70 | Class +0.67, FCI +0.66 — all three leading |
| Value ROI | +140.1% | Correct metric for val_n (not win-rate differential) |
| val_n win diff | −0.31 | EXPECTED — overlays designed to pay more, not win more |

### Cards logged
| Card | Races | Status |
|------|-------|--------|
| CDX 20260502 | 14 | Results loaded |
| DBY 20260502 | 1 | Results loaded (Golden Tempo $48.24, our Rank 5) |
| CDX 20260507 | 8 | Results loaded |
| BAQ 20260509 | 11 | 10 results loaded (R11 still missing — non-critical) |
| CDX 20260514 | 8 | Results loaded — 4/8 wins (50%), best card to date |
| LRL 20260516 | 14 | R1–R13 results logged; R14 pending |
| CDX 20260521 | 8 | Results loaded — 2/8 wins. First v3.5 live card post-backfill. CM run in parallel. |
| CDX 20260524 | 10 | Results loaded. 0 wins, 3 top-3 hits (R1/R8/R10 all 2nd). Sloppy track. R7 $73.32 + R10 $42.70 upsets. R3/R7 top picks scratched. LAZLO R9 (FAIR/double-consensus best play) finished 7th. |

### 60-race threshold
**60-race gate MET (71 races). Issue 3 (TJ reweight) implemented in v3.5.**

---

## 🔑 Key Findings to Date

1. **Graded stakes = best model environment.** Both G2 races on BAQ0509 (Peter Pan, Ruffian) had model winners inside Rank 2. FCI and TJ are most predictive in quality fields. Supports Saratoga target.

2. **Pace scenario validated.** HOT pace flag correctly identified closer-favoured setup in BAQ R6. Durante (Rank 5, closer) won at $16.50. Preakness 2026: 8 speed horses declared → HOT pace, MID/CLOSER styles favored, Ocelli (CLOSER) flagged as value alt.

3. **Rank 5 upsets (pattern).** Roman Grace, Durante, Arkhipov all won from Rank 5 on BAQ. Common pattern: one strong component (TJ or Trend) overwhelmed by FCI/Class drag. Supports TJ underweight thesis.

4. **Composite score ceiling problem.** No mid-week CDX race reaches SOLID tier (7.5). fci_n normalisation (baseline 60, ÷6) calibrated too high for lower-class fields. Dynamic normalisation needed — Issue 4.

5. **Value signal working correctly.** ROI +172.9% at 50 races. SOLEIL VOLANT (CDX0514 R5): 20-1 ML, val_n=10.0, won $52.06 — overlay signal validated live. val_n win-rate differential being negative is EXPECTED behavior, not a bug. ROI is the correct metric.

6. **CDX0514 best card to date.** 4/8 top-pick wins (50%). Late scratch VIVIANITE (R8, #5, Rank 8) correctly caught by new --finalize command and set to finish_pos=-1.

7. **Preakness v3.5 retroactive test.** TAJ MAHAL ranked 1st (6.88 FAIR — only FAIR in the 14-horse field) with TJ=10.0, max Trend +5.0, PP=144.6. Scratched on race day. NAPOLEON SOLO (actual winner, $17.80) ranked 10th — low TJ (3.0) dragged it down despite PP=143.7 (3rd in field). HOT PACE (8 speed) correctly flagged; OCELLI (CLOSER, 6-1) was value alt — the correct closer angle. Model logic sound; outcome was a scratch event, not a miss.

8. **Scratch gate confirmed working** (via `run_r5.py --auto-scout`). When a Rank 1–3 horse is in the scout scratch list, the report prints `🚨 SCRATCH NOTICE` with the revised top pick and passes only active horses to `report()`. Running `r5_parser_v2.py` directly bypasses this (no scout data). Gap: scratches of Rank 4+ are silently removed with no notice.

---

## 🔀 CompareModels v1.0 — Parallel System (2026-05-21)

Full state doc: `comparemodels/COMPAREMODELS_STATE.md`
Report: `comparemodels/reports/comparemodels_vs_r5_63races_20260521_020626.xlsx`

**BRIS Summary methodology** — 8-category consensus scoring (Prime Power, Avg Speed, Best Speed, Distance Speed, Avg Class, Jockey Rating, Trainer Rating, Earnings). Scored independently from raw DRF data. No R5 code imported.

### 63-race head-to-head

| Metric | CM | R5 |
|---|---|---|
| Top pick win rate | 25.4% | 25.4% |
| Top-3 hit rate | 47.6% | 55.6% |
| ROI (ML) | −6.7% | −7.3% |
| ROI (SP) | +50.6% | +93.0% |
| Agreement rate | 31.7% | — |

Disagreements (43 races): R5 right 10 / CM right 10 / Neither 23 — dead heat.

### CM segment outperformance
- **Non-graded Stakes:** CM 38.5% vs R5 15.4% (13 races) — strongest signal
- **Dirt:** CM 30.0% vs R5 25.0% (40 races)
- **CDX:** CM 33.3% vs R5 23.3% (30 races)

R5 outperforms CM on: Turf, BAQ, Allowance/Opt-Clm races.

### Actionable CM signals
- **Consensus ≥ 4:** 30.8% win rate (39 races) — primary filter
- **Prime Power underline:** 33.3% win rate (57 fires) — most reliable single signal
- **Overlay Watch:** 5.6% win rate — **broken, do not use until CM-1 fixed**

### Advisory integration
CM is a supplemental confidence filter on R5 — not a replacement. When R5 top pick also has CM consensus ≥ 4 or Prime Power underline → elevated confidence. When R5/CM disagree and CM consensus < 4 → lean R5.

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
| **Current** | **v3.6** | Par-anchored fci_n + best_dist_n; Issue 4 fix; 9-component composite | **Live — 2026-05-24** |
| Next | v3.7 | Surface-specific WS4 (Issue 7); Crowded Room deduction (Issue 6) | After v3.6 validated (~20 races) |
| Future | v4.x | Live odds divergence alerts (UI-3) | After v3.7 validated |
| Future | v5.0 | ML pattern recognition, anomaly detection, LLM coaching summaries | Long term |
| Target | — | Saratoga 2026 deployment | Summer 2026 |

---

## 🏗️ Architecture

```
files 2/TRACK_MMDD.DRF   ← BRIS DRF input (1496 fields per record)
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

---

## 📋 Immediate Next Steps

1. **Log LRL0516 R14** — card had 14 races; R14 picks are in DB but result not yet logged.
2. **v3.6 validation in progress** — CDX0524 is card 1 under v3.6. 0 wins on a sloppy-track day. Continue running future cards; watch if par-anchored normalisation lifts tier distribution.
3. **Run CM on every new card** — established parallel workflow: score → log → results → finalize → daily xlsx. Repeat each race day.
4. **Issue 6 validation** — Crowded Room score deduction pending results data. CDX0524 had multiple TIGHT CLUSTER flags. Monitor.
5. **Issue 7 (surface WS4)** — gate lifted. Needs structured validation session comparing dirt vs turf top-pick rates from the 81-race DB.
6. ~~**Issue 14 — Tracker 5th+ finisher bug**~~ **FIXED** — apply_result() now marks non-top-4 as finish_pos=5 (loss, counted) not -1 (excluded). CDX0524 retroactively corrected. Commit 81ce32d.
7. **pgm-number mismatch** — R2 and R5 on LRL0516 had DRF pgm ≠ official chart pgm. Monitor for pattern on future cards.

---

*Update this file after each session. Keep the session log current. This is the handoff document for every new Claude conversation and for Opus evaluation sessions.*
