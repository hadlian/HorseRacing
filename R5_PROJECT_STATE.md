# R5 Handicapping System — Project State

> This document is the persistent context file for R5 development sessions.
> Update it after every meaningful session. It is the clean prompt source for Opus evaluations.
>
> **Last updated:** 2026-05-16 (v3.5 live — weight rebalance + best_dist_n + pp_n)
> **Current version:** R5 v3.5
> **Primary AI collaborator:** Claude Code — all code implementation
> **Advisory:** Claude Sonnet (advisory only, no direct file edits), Opus (major arch decisions)

---

## 🎯 Project Goal

Build a data-driven handicapping engine for **premier thoroughbred racing**, with Saratoga 2026 as the first real-world deployment target. The system must perform well in graded stakes and high-class allowance fields — not calibrated for mid-week claiming cards.

---

## 📊 Results Database Status

| Metric | Value | Notes |
|--------|-------|-------|
| Races with results | 63 | Through LRL0516 (13 races logged) |
| Total picks in DB | 65 | R14 LRL0516 still pending |
| Top pick win rate | 26.7% | Up from 26.5% at 50 races |
| Top-3 hit rate | 55.6% | Up from 52.0% at 50 races |
| TJ signal strength | +0.83 | Class vs Par rising (+0.73), FCI +0.68 |
| Value ROI | +165.2% | Correct metric for val_n (not win-rate differential) |
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

### 60-race threshold
**60-race gate MET (63 races). Issue 3 (TJ reweight) awaiting explicit approval.**

---

## 🔑 Key Findings to Date

1. **Graded stakes = best model environment.** Both G2 races on BAQ0509 (Peter Pan, Ruffian) had model winners inside Rank 2. FCI and TJ are most predictive in quality fields. Supports Saratoga target.

2. **Pace scenario validated.** HOT pace flag correctly identified closer-favoured setup in BAQ R6. Durante (Rank 5, closer) won at $16.50. Preakness 2026: 8 speed horses declared → HOT pace, MID/CLOSER styles favored, Ocelli (CLOSER) flagged as value alt.

3. **Rank 5 upsets (pattern).** Roman Grace, Durante, Arkhipov all won from Rank 5 on BAQ. Common pattern: one strong component (TJ or Trend) overwhelmed by FCI/Class drag. Supports TJ underweight thesis.

4. **Composite score ceiling problem.** No mid-week CDX race reaches SOLID tier (7.5). fci_n normalisation (baseline 60, ÷6) calibrated too high for lower-class fields. Dynamic normalisation needed — Issue 4.

5. **Value signal working correctly.** ROI +172.9% at 50 races. SOLEIL VOLANT (CDX0514 R5): 20-1 ML, val_n=10.0, won $52.06 — overlay signal validated live. val_n win-rate differential being negative is EXPECTED behavior, not a bug. ROI is the correct metric.

6. **CDX0514 best card to date.** 4/8 top-pick wins (50%). Late scratch VIVIANITE (R8, #5, Rank 8) correctly caught by new --finalize command and set to finish_pos=-1.

---

## 🔴 Open Issues — Engine (Priority Order)

All weight changes require explicit approval + version bump per spec rules.

| Issue | Description | Status | Priority |
|-------|-------------|--------|----------|
| 3 | T/J weight 10% → 15% (offset via Class/Bias/Ped) | **60-race gate NOW MET — awaiting approval** | HIGH |
| 4 | Composite score ceiling — dynamic fci_n normalisation | Under discussion | HIGH |
| 6 | Crowded Room Penalty — score deduction (flag is live) | Pending post-Preakness validation | MODERATE |
| 7 | Surface-specific WS4 weights (dirt vs turf) | Gate lifted post-Preakness | MODERATE |
| 8 | Data scarcity confidence cap (per-horse, < 2 starts) | Proposed | MODERATE |
| 9 | Tight cluster UI flag (engine side of Issue 6) | Proposed | LOW |
| 10 | Surface weighting validation task | Gate lifted post-Preakness | VALIDATION |
| 11 | Distance-specific speed floor (best-at-distance) | Gate lifted post-Preakness | LOW |
| 12 | Career average class flag (dropdown angle) | Proposed | LOW |

### Known path bug
`--auto-scout` in run_r5.py calls `subprocess.run([sys.executable, "r5_scout.py", ...])` — looks in CWD, not in Claude/. Workaround: run scout manually first, then --auto-scout picks up saved JSON. Fix pending.

---

## ✅ Completed Issues

| Issue | Fix | Version | Date |
|-------|-----|---------|------|
| 1 | Maiden/firster class_n=0.0 + [DEBUT] flag | v3.3 | 2026-05-09 |
| 2 | Value score inversion — floor raised max(1.0)→max(5.0) | v3.4 | 2026-05-10 |
| 3a | result_fetched flag not set on direct SQL logging | v3.4 | 2026-05-12 |
| 5 | Scratch gate — revised top pick when Rank 1-3 scratched | v3.3 | 2026-05-10 |
| 6-display | TIGHT CLUSTER warning flag (display only, no deduction yet) | v3.4 | 2026-05-10 |
| 13 | Late scratch detection — auto-detect in apply_result(), --finalize command, two-tier analyze filter | v3.4 | 2026-05-15 |
| PDF-bug | NameError: `active` undefined in PDF block → replaced with filtered horses loop | v3.4 | 2026-05-15 |
| Scout | API model fix, track keyword expansion, auto-scout matching, stacking cap | v3.3 | 2026-05-09 |
| UI-1 | Mobile responsive design | v4.0 | 2026-05-10 |
| UI-webapp | PDF error surfacing, scratch notice regex fix, scratch-map pre-collection | v4.0 | 2026-05-16 |

---

## 🟡 Open Issues — UI (Priority Order)

All UI work in `webapp/`. Do not modify `Claude/` scripts in UI sessions.

| Issue | Description | Status |
|-------|-------------|--------|
| UI-2 | Historical ROI Dashboard (Analytics tab in web UI) | 60-race gate now met — ready to start |
| UI-3 | Live odds divergence alerts | Ready (Issue 2 resolved) |

---

## 🔵 Roadmap

| Phase | Version | Description | Gate |
|-------|---------|-------------|------|
| Current | v3.4 | Engine fixes, val_n floor, scratch gate, Issue 13 | Live |
| Next | v3.5 | T/J reweight (Issue 3), composite ceiling fix (Issue 4) | **Gate met — need approval** |
| Future | v4.0+ | ROI Dashboard, live odds alerts | After v3.5 validated |
| Future | v5.0 | ML pattern recognition, anomaly detection, LLM coaching summaries | Long term |
| Target | — | Saratoga 2026 deployment | Summer 2026 |

---

## 🏗️ Architecture

```
files 2/TRACK_MMDD.DRF   ← BRIS DRF input (1496 fields per record)
         │
  r5_parser_v2.py        ← Parse + score (7-component composite)
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

## ⚖️ Current Composite Weights (v3.5 — LIVE 2026-05-16)

| Component | Weight | Field | Winner Diff | Change from v3.4 |
|-----------|--------|-------|-------------|------------------|
| FCI (WS4 + Trend) | 22% | fci_n | +0.681 | 25% → 22% |
| Class vs Speed Par | 20% | class_n | +0.723 | unchanged |
| Trainer / Jockey | 15% | tj_n | +0.832 | **10% → 15%** |
| Best @ Distance | 8% | best_dist_n | +4.89 raw | **NEW** |
| Bias / Pace Fit | 8% | bias_n | −0.106 | 15% → 8% |
| Form Angle | 10% | form_n | +0.364 | unchanged |
| Pedigree | 7% | ped_n | +0.217 | 10% → 7% |
| Prime Power | 5% | pp_n | +5.48 raw | **NEW** |
| Value vs ML | 5% | val_n | −0.262 | 10% → 5% |

**Normalization for new components:**
- `best_dist_n` = clamp((best_dist − 60) / 6, 0, 10) — fallback: fci_n if missing
- `pp_n` = clamp((prime_power − 100) / 6, 0, 10) — fallback: 5.0 (neutral) if missing

**Weight sum: 1.00 verified. Commit: 5678ff6**

**Signal ranking (all 63 races, winner diff):**
tj_n +0.832 > class_n +0.723 > fci_n +0.681 > form_n +0.364 > ped_n +0.217 > bias_n −0.106 > val_n −0.262

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
| 2026-05-16 | Signal analysis + v3.5 | 63-race correlation analysis: prime_power, best_dist, best_life, best_fast, life_earn evaluated. best_fast eliminated (negative signal). Approved v3.5 weight rebalance: TJ 10→15%, best_dist_n NEW 8%, pp_n NEW 5%, bias 15→8%, val 10→5%, ped 10→7%, fci 25→22%. Commit 5678ff6. |

---

## 📋 Immediate Next Steps

1. **Log LRL0516 R14** — card had 14 races; R14 picks are in DB but result not yet logged.
2. **v3.5 first-card validation** — run next card under v3.5, compare top-pick win rate and rank distribution vs v3.4 baseline (26.7% / 55.6%).
3. **Issue 4 design session** — dynamic fci_n normalisation. No code proposed yet.
4. **pgm-number mismatch** — R2 and R5 on LRL0516 had DRF pgm ≠ official chart pgm. Monitor for pattern on future cards.
5. **best_dist_n / pp_n backfill** — historical picks in DB have raw prime_power and best_dist but best_dist_n and pp_n columns are NULL for pre-v3.5 rows. Backfill when needed for longitudinal analysis.
6. **UI-2 ROI Dashboard** — 63 races now in DB, ready to build Analytics tab.

---

*Update this file after each session. Keep the session log current. This is the handoff document for every new Claude conversation and for Opus evaluation sessions.*
