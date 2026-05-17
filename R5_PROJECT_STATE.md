# R5 Handicapping System — Project State

> This document is the persistent context file for R5 development sessions.
> Update it after every meaningful session. It is the clean prompt source for Opus evaluations.
>
> **Last updated:** 2026-05-16 (Preakness Day)
> **Current version:** R5 v3.4
> **Primary AI collaborator:** Claude Code — all code implementation
> **Advisory:** Claude Sonnet (advisory only, no direct file edits), Opus (major arch decisions)

---

## 🎯 Project Goal

Build a data-driven handicapping engine for **premier thoroughbred racing**, with Saratoga 2026 as the first real-world deployment target. The system must perform well in graded stakes and high-class allowance fields — not calibrated for mid-week claiming cards.

---

## 📊 Results Database Status

| Metric | Value | Notes |
|--------|-------|-------|
| Races with results | 50 | Through CDX0514 |
| Total picks in DB | 64 | +14 LRL0516 awaiting results |
| Top pick win rate | 26.5% | Up from 18.2% at 34 races |
| Top-3 hit rate | 52.0% | Up from 45.5% at 34 races |
| TJ signal strength | +1.01 | Up from +0.86 — most predictive component |
| Value ROI | +172.9% | Correct metric for val_n (not win-rate differential) |
| val_n win diff | −0.31 | EXPECTED — overlays designed to pay more, not win more |

### Cards logged
| Card | Races | Status |
|------|-------|--------|
| CDX 20260502 | 14 | Results loaded |
| DBY 20260502 | 1 | Results loaded (Golden Tempo $48.24, our Rank 5) |
| CDX 20260507 | 8 | Results loaded |
| BAQ 20260509 | 11 | 10 results loaded (R11 still missing — non-critical) |
| CDX 20260514 | 8 | Results loaded — 4/8 wins (50%), best card to date |
| LRL 20260516 | 14 | **Picks logged — results PENDING post-Preakness** |

### 60-race threshold
**60+ races required before any composite weight adjustments.**
Met/nearly met after Preakness results logged. Issue 3 (TJ reweight) decision point imminent.

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

## ⚖️ Current Composite Weights (v3.4 — frozen)

| Component | Weight | Field | Notes |
|-----------|--------|-------|-------|
| FCI (WS4 + Trend) | 25% | fci_n | Most predictive in stakes fields |
| Class vs Speed Par | 20% | class_n | |
| Bias / Pace Fit | 15% | bias_n | Pace scenario validated |
| Trainer / Jockey | 10% | tj_n | Signal +1.01 — underweighted, 60-race gate met |
| Form Angle | 10% | form_n | |
| Pedigree | 10% | ped_n | Weakest signal on dirt sprints |
| Value vs ML | 10% | val_n | ROI +172.9% — working correctly |

**Proposed v3.5 weights (60-race gate met — pending explicit approval):**
T/J 10%→15%, Class 20%→13%, Bias 15%→10%, Ped 10%→7%

---

## 🤖 AI Collaborator Notes

- **Claude Code** — all actual code implementation happens here.
- **Claude Sonnet** — primary session advisor, code snippets, architecture recommendations. Advisory only — never edits project files directly.
- **Opus** — reserved for major architectural decisions and weight evaluation sessions. Use with a clean, focused prompt: current weights + component correlations + race type breakdown + Saratoga context.
- **Gemini / ChatGPT** — design ideas and pseudocode only. Do not write to repo.

### When to escalate to Opus
- Post-60-race DB weight evaluation (NOW READY)
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

---

## 📋 Immediate Next Steps

1. **Log LRL0516 results** — bring results PDF, log all finish positions, run `--finalize LRL 20260516`, regenerate Excel.
2. **Issue 3 decision** — with 60+ races confirmed, decide on TJ 10%→15% reweight. Requires explicit approval before code change.
3. **Issue 4 design session** — dynamic fci_n normalisation. No code proposed yet.
4. **Update this file** after LRL results logged and Issue 3 decided.

---

*Update this file after each session. Keep the session log current. This is the handoff document for every new Claude conversation and for Opus evaluation sessions.*
