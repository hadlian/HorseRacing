# R5 Handicapping System — Project State

> This document is the persistent context file for R5 development sessions.
> Update it after every meaningful session. It is the clean prompt source for Opus evaluations.
>
> **Last updated:** 2026-06-12 (pre-SAR instrumentation session — rank3/paper75 trackers, pace diagnostic, Issue 17, backtest audit)
> **Current version:** R5 v3.10 — **DEPLOYED / feature-frozen through Saratoga meet**
> **Weights:** frozen through Saratoga (Harry ruling 2026-06-11). Any change requires explicit approval + version bump.
> **Saratoga opens:** July 3, 2026
> **Primary AI collaborator:** Claude Code — all code implementation
> **Advisory:** Fable 5 (architecture decisions), Sonnet (session advisor)
>
> ⚠️ **TODO.md is the single source of truth for open tasks, in-meet checkpoints, and session-by-session notes.** This state file covers stable architecture, rulings, and key findings. When the two diverge, TODO.md wins.

---

## 🏗️ Architecture (v3.10)

```
files 2/TRACK_MMDD.DRF   ← BRIS DRF input (1,435 fields per record)
         │
  r5_parser_v2.py         ← Parse + 9-component composite score
         │                   + run style / Quirin / layoff / wet bundle (3A)
  r5_probability.py       ← Conditional logit P(win) layer (β=0.7674)
         │
  r5_exotics.py           ← Contender set + structure menu + ticket gen/settle
         │
  r5_scout.py             ← Pre-race intel via HRN/Blood-Horse/TDN + Claude API
         │
  run_r5.py               ← Master runner: --save --track --wet --live
         │
  r5_tracker.py           ← SQLite logger; val_n_tracker guardrails
         │
  r5_payoffs.py           ← Equibase chart PDF ingestion (pdftotext -layout)
         │
  r5_analyze.py           ← Performance analysis → Excel workbook
         │
  webapp/app.py            ← Flask UI (localhost:5050)
```

**DB:** `Results/r5_results.db` (SQLite)
**Stack:** Python 3.9+, Flask, SQLite, ReportLab, openpyxl, BeautifulSoup4, Anthropic API

---

## ⚖️ Composite Weights — v3.10 (FROZEN)

| Component | Weight | Field | Notes |
|-----------|--------|-------|-------|
| Class vs Speed Par | **20%** | class_n | Harry confirmed 2026-06-11; v3.5 docs said 13% (wrong) |
| FCI (WS4 + Trend) | 22% | fci_n | Par-anchored normalisation (v3.6) |
| Trainer / Jockey | 15% | tj_n | Min 20 meet starts; elite-name fallback |
| Form Angle | 10% | form_n | Recent pattern |
| Best @ Distance | 8% | best_dist_n | BRIS best speed @ today's distance/surface |
| Bias / Pace Fit | 8% | bias_n | Post bias + pace scenario fit |
| Pedigree | 7% | ped_n | Distance/surface suitability |
| Prime Power | 5% | pp_n | BRIS Prime Power (anchor 130, formula: (pp-100)/6) |
| Value vs ML | 5% | val_n | ML-rank divergence; excluded from P(win) calc |

**Tier ladder (HIGH/SOLID/FAIR/SPEC): RETIRED.** Tiers were zero-fires dead weight at the top and inverse-performance (FAIR was the worst bet). Output shows P(win) and fair_odds instead.

**comp_ex_val:** Market-free composite for P(win) = Σ(weight/0.95) over the 8 non-val components.

---

## 📊 Results Database Status (2026-06-12)

> **⚠️ ROI accounting corrected 2026-06-11.** All figures prior to that date were inflated
> by a unit bug ($2 payoffs vs $1 stakes). Convention: **$2 flat win bets, profit = payoff − 2**.
> Authoritative source: `Results/CORRECTED_BASELINE_2026-06.md` + `Results/SIGNAL_VALIDATION_20260611.md`.

| Metric | Value | Notes |
|--------|-------|-------|
| Clean baseline races | **160** | `result_fetched=1 AND is_backtest=0`; backtest cards tagged separately |
| Top pick win rate | 22.9% | SAR drag (9.4% in 32 races — new-track calibration gap) |
| Top-3 hit rate | 59.4% | |
| Top pick flat-bet ROI | **−18.5%** | ≈ takeout; no win-bet edge |
| **Rank-3 flat-bet ROI** | **+17.4%** | 35 wins / 151 bets — **⚠️ fragile**: ex-PURE MADNESS ($57.20), profit = −$2.64, ROI = −0.9%. Paper-tracked from day 1. |
| CM rank-1 ROI | −21.9% | CM wins more often; R5 loses less money |
| CM rank-2 ROI | **+3.6%** | Near-miss pattern mirrors R5 rank-3 |
| Final-odds overlay | −56.9% | 142 bets — **NOT AUTHORIZED** for live win betting |
| sp_odds convention | mutuel payout per $2 | e.g., sp_odds=8.7 → $8.70 returned; profit = sp_odds − 2.0 |

### By track
| Track | Races | Win% | Top-3% |
|-------|-------|------|--------|
| BAQ | 19 | 31.6% | 63.2% |
| SAX | 10 | 30.0% | 50.0% |
| CDX | 82 | 26.8% | 56.1% |
| LRL | 13 | 15.4% | 61.5% |
| SAR | 32 | 9.4% | 53.1% — 3 days, new track |

### Cards logged (through SAR 06/06)
| Card | Races | Status |
|------|-------|--------|
| CDX 20260502 | 14 | Results loaded (partial — 1 missing) |
| CDX 20260507–0531 | ~50 | Results loaded (multiple cards) |
| BAQ 20260509 | 11 | Results loaded (1 missing) |
| LRL 20260516 | 14 | Results loaded (1 missing) |
| SAX 20260525 | 10 | Results loaded |
| SAR 20260603–0606 | 45 | Results loaded; 06/06 payoffs backfilled |
| SAR 20260703–0704 | 22 | Opening weekend — results loaded, exotics settled, CM logged (both cards) |
| SAR 20260705 | 9 | Results loaded, 19 scratches recorded (MTO + late), exotics settled w/ refunds, CM logged. **Crossed n≥60 gate (63 SAR races).** |

**Payoff backfill:** 174/179 races carry full exotic payoffs + finish order + final tote odds.
**Remaining 5 races:** CDX 0502 R13–14, BAQ 0509 R11, LRL 0516 R14, +1 — chart PDFs lack these races.

---

## 🚫 Signals Retired (failed corrected-ROI testing)

| Signal | ROI | Verdict |
|--------|-----|---------|
| Play gate: spread(r1−r2) ≥ 0.5 | −40.3% | Strictly worse than complement |
| PLAY ≥ 6.0 verdict | −18.5% | Identical ROI to complement; win rate now inverted |
| HIGH tier | 0 fires | Dead weight — never fired |
| SOLID tier | 1 fire, lost | Dead weight |
| FAIR as confidence marker | −70.2% | "Higher confidence" was the worst bet |
| CM consensus ≥ 4 | −20.5% | Fires 91% of races — saturated, no discrimination |
| Agreement boost (R5+CM agree) | −22.9% | Chalk trap — highest win rate, loses most |
| val_n ≥ 7 | −8.2% | Threshold too loose |
| Overlay Watch (CM) | already retired | Stays retired |

---

## 👀 Signals on Watch (promising, not yet bettable)

| Signal | Wins | ROI | Status |
|--------|------|-----|--------|
| R5 rank-3 flat win bets | 35 / 151 bets | **+17.4%** | **Only positive slot at meaningful n** — ⚠️ fragile: ex-PURE MADNESS ($57.20 payout) ROI = −0.9%. Paper-tracked from day 1 via `rank3_tracker`. |
| CM rank-2 flat win bets | 33 / 147 bets | +3.6% | Mirrors rank-3 pattern |
| val_n ≥ 8 | 4 wins | +41.8% | Gradient right; n too small (gate: n≥120) |
| val_n ≥ 9 | 2 wins | +85.7% | Gradient right; n too small |
| PP underline standalone | 40 / 127 bets, 31.5% win | −9.6% | Best large-n win-rate signal; exotics anchor only, not a win bet |
| Divergence: bet R5 leg | 16 / 91 bets | −12.8% | Best relative leg; single-outlier sensitive |

---

## ⚙️ Probability Layer (P(win)) — v3.10

**Model:** Conditional logit, one-parameter softmax within race field.
`P(win)_i = exp(β · comp_ex_val_i) / Σ_j exp(β · comp_ex_val_j)`
`β = 0.7674` (fit by Newton's method on 97 races; `Results/logit_beta.json`).

**comp_ex_val:** market-free composite (excludes val_n; renormalised over 0.95 sum).
**val_n is permanently excluded from P(win).** val_n uses morning-line rank and would contaminate the probability estimate.

**Overlay rule:** P(win) × (final_odds + 1) ≥ 1.25 AND P ≥ 0.08.
**Live overlay win betting NOT AUTHORIZED** — retro-test returned −56.9% (142 bets, in-sample β + hindsight odds).
**Overlay flags are advisory/diagnostic only.** Revisit at n≥300 with decorrelated model, paper-first.

---

## 🎰 Exotics Module (r5_exotics.py) — v3.10

**Contender set:** R5 ranks 1–3 ∪ CM ranks 1–2. Captures winner in 66.9% of races vs 59.4% R5-only.
Exclusions: field ≤ 5 (PASS), debuts (flag only), PP-underline as underneath-only.

**Structure menu:**
- **TIGHT** (spread r1−r3 ≤ 0.5): EX box + TRI box + r3 key on top if ML≥6-1
- **STANDOUT** (spread r1−r2 ≥ 1.0): EX key r1/set + TRI key r1 over set
- **DEFAULT**: EX box r1+r2

**$12 cap** with trim priority: TRI third leg first → r3 key → primary EX never dropped.

**Paper-default / --live flag required for real money.** `is_paper=0` only when `--live` explicitly passed.

**SAR paper results (4 cards, 70 tickets):**
- TIGHT TRI box: +384.7%; TIGHT EX box: +86.6%; DEFAULT EX box: −35.1%; STANDOUT keys: −100% (0-for-10)
- Total: +52.2% (two TRI hits carry it — n=4 cards = anecdote; n≥40-race gate stands)

---

## 🔒 Harry Rulings (2026-06-11) — All BINDING

| Ruling | Decision |
|--------|----------|
| Weights | FROZEN through Saratoga meet; any change = explicit approval + version bump |
| Exotics | LIVE at $12 cap from opening day; --live flag enables real money |
| val_n ≥ 8 tracker | **DOWNGRADED to PAPER 2026-07-06** (was LIVE) — Harry ruling. val_n≥8 ROI +12.4% is −18.7% ex single top payout; val_n≥9 +49.7% is −4.8% ex-outlier (one payout, PURE-MADNESS signature). Stacked on the market-anchored gate NO-GO (no conditional edge over market), no live exposure justified. Re-decide at n≥120 with selection discount (require positive point AND bootstrap CI > ~−5%, ≥8 and ≥9 evaluated jointly). |
| Overlay win betting | NOT AUTHORIZED — advisory flags only |
| Tight-cluster deduction | ACTIVE + CONFIRMED (−0.40 to pre-deduction rank-1 when top-3 spread ≤0.5) |

---

## 📅 In-Meet Checkpoints

| Gate | Decision | Watches |
|------|----------|---------|
| SAR n≥40 payoff races | Structure menu ROI review | DEFAULT EX box (−35.1%), STANDOUT keys (0-for-10) |
| SAR n≥60 races | SAR-only β refit; tj_n year-stats fallback rerun | SAR win rate vs overall (9.4% drag) |
| SAR n≥100 races | CM merge-or-keep decision | CM legs: +7.5pp capture justifies inclusion until then |
| val_n n≥120 qualifying bets | val_n ≥8 re-decision (now PAPER) with selection discount | RECONCILED 2026-07-06: ≥8 +12.4%→−18.7% ex-outlier; ≥9 +49.7%→−4.8% ex-outlier. Outlier-only, not signal. |
| Mid-July 2026 | Live odds capture build (Issue 16) | Required for any future overlay reconsideration |
| n≥300 total races | Decorrelated probability layer upgrade; overlay reconsideration paper-first | One-parameter model overestimates longshots |

**tj_n year-stats fallback (3B research):** 84% of picks affected but SAR win rate unchanged at 9.4% — no pre-Saratoga change. Re-run at SAR n≥60 with `scripts/tj_fallback_backtest.py`.

---

## 🔑 Key Findings

1. **No win-bet edge exists yet.** Every signal tested — tiers, gates, consensus, agreement, stacking, model-vs-market overlays — fails corrected ROI. R5 rank-1 = ≈ takeout (−18.5%).

2. **The edge, if any, is in ranks 2–3 contention and exotics.** R5 rank-3 (+17.4%) and CM rank-2 (+3.6%) both win at near-rank-1 rates at better prices. The market prices the first choice efficiently; it does not price the third.

3. **Tight-cluster deduction is confirmed helpful.** Exact reconstruction (0 unexplained deltas) reversed the approximate analysis: post-deduction rank-1 in the 33 fired races = 25.9% win / −1.3% ROI vs demoted horse −43.3%. ACTIVE, CONFIRMED.

4. **SAR opener drag (9.4%) has unknown causes.** tj_n year-stats hypothesis tested: fallback changes 84% of picks but win rate unchanged. The drag is not meet-stats starvation. Re-examine at n≥60.

5. **Graded stakes = best model environment.** Peter Pan G2 and Ruffian G2 both had model winners in top 2. FCI + TJ most predictive in quality fields. Supports Saratoga target.

6. **Rank-3 structural dominance.** Rank-3 beats rank-2 on win%, top-2%, and top-3% (23.2/35.1/47.7 vs 15.6/34.4/42.9) — rank-2 is the weakest of the top-3 and should be treated as an underneath leg, not a key.

7. **BRIS run style + pace profile confirmed parseable** (fields 210/211). Lone-E with Q≥6 is the TIGHT-race candidate worth paper-tracking from opening day.

8. **No pace dynamic under engine pace_style.** Win-share ≈ starter-share in all HOT/NORMAL/SLOW scenarios. "HOT → closers win" angle is dead. BRIS field 210 shows a weak positive pattern (E types in NORMAL/SLOW) but engine-based `bias_n` does not capture it — see Issue 17. Do not structure tickets on pace scenario.

---

## 🔀 CompareModels v1.1 — Parallel System

Full state doc: `comparemodels/COMPAREMODELS_STATE.md`

**Head-to-head (152-race aligned universe, corrected 2026-06-11):**
- CM top pick: 25.7% win / −21.9% ROI
- R5 same races: 23.3% win / −16.8% ROI
- Neither beats takeout. CM wins more; R5 loses less.

**CM segment outperformance:** Non-graded Stakes (38.5% vs R5 15.4%), Dirt (30.0% vs 25.0%), CDX (33.3% vs 23.3%)

**Retained roles:**
- Divergence flag (disagreement = potential value zone; R5 leg −12.8% = best relative leg)
- Exotics contender-set generator (CM ranks 1–2 ∪ R5 ranks 1–3; CM rank-2 +3.6%)

**CM is NOT a confidence filter.** Every confirmation-style use is ROI-negative.

---

## 🔴 Open Issues — Engine

All weight changes require explicit approval + version bump per spec rules.

| Issue | Description | Status | Priority |
|-------|-------------|--------|----------|
| 7 | Surface-specific WS4 weights (dirt vs turf) | Post-SAR validation needed | MODERATE |
| 8 | Data scarcity confidence cap (< 2 starts) | Proposed | MODERATE |
| 16 | Live tote odds integration (val_n recomputation + overlay) | Mid-July build | HIGH — in-meet checkpoint |
| **17** | **bias_n source: engine pace_style vs BRIS field 210** — ~27% disagree; engine style shows no win-share lift; field 210 shows weak E-type lift in NORMAL/SLOW | Post-SAR | MODERATE |
| CM-1 | Overlay Watch definition broken | Post SAR-calibration | LOW |
| CM-3 | Trainer Rating signal weak | Re-evaluate post-SAR | LOW |
| CM-4 | BRIS Top Pick field not located | +2 bonus silently skipped | LOW |

**Deferred (requires post-SAR data):**
- No-odds val_n inflation fix (horses with missing ML get spurious overlay signal at 5% weight — low impact)
- pp_n neutral anchor adjustment (pending advisory on typical BRIS PP range by race type)
- Negative distance flag −0.3 (n≥60–80 needed on negative flag subset)
- Surface WS4 split weights (validate against 150+ race DB)

---

## 🟡 Open Issues — UI

| Issue | Description | Status |
|-------|-------------|--------|
| UI-3 | Live odds divergence alerts | Blocked on Issue 16 (live odds build) |
| UI-4 | BRIS Summary docx download (Dennis format) | Spec written 2026-05-29; not started |

---

## 🔵 Roadmap

| Phase | Version | Description | Gate |
|-------|---------|-------------|------|
| **Current** | **v3.10** | P(win) layer + exotics module + display fields; weights FROZEN | **Saratoga deploy July 3, 2026** |
| v3.11 | — | tj_n year-stats fallback (if SAR n≥60 shows separation) | SAR n≥60 |
| v3.x | — | Negative distance flag −0.3 | n≥60–80 on flag subset |
| v4.1 | — | Live odds capture; overlay reconsideration (paper-first) | Mid-July 2026 |
| v5.0 | — | Decorrelated P(win) upgrade; ML patterns | n≥300 total |

---

## 🤖 AI Collaborator Notes

- **Claude Code** — all actual code implementation
- **Fable 5** — architecture decisions (probability layer, exotics framework, roadmap). Use for major design questions with corrected, audited ROI data (not win rate)
- **Claude Sonnet** — session advisor; code snippets; research. Advisory only — never edits project files
- **Gemini / ChatGPT** — design ideas, pseudocode only. Do not write to repo

---

## 📋 Session Log

| Date | Session | Key Outcomes |
|------|---------|--------------|
| 2026-05-09 | Engine fixes | Issues 1, Scout fixes — v3.3 |
| 2026-05-10 | BAQ card + fixes | Issue 2 (val_n), Issue 5 (scratch), UI-1 (mobile) — v3.4 |
| 2026-05-12 | DB review | Issue 3a fixed. 34 races. Model frozen pre-Preakness |
| 2026-05-14 | CDX scout test | Scout and scratch report validated |
| 2026-05-15 | CDX0514 results | 4/8 wins (50%). Issue 13 (late scratch). PDF NameError fixed. 50 races. |
| 2026-05-16 | Preakness Day | LRL0516. HOT pace in Preakness. Memory + state synced. |
| 2026-05-21 | CDX0521 + CM v1.0 | CompareModels built. 63-race backfill. CM 25.4% vs R5 25.4% tied. |
| 2026-05-24 | v3.6 + CDX0524 | Par-anchored fci_n. Analytics tab (UI-2). 81 races. |
| 2026-05-28–31 | CDX live cards | CDX0528–0531. Best stretch: CDX0531 4/10 wins, 9/10 top-3. |
| 2026-06-03 | v3.9 + SAR opener | Code-review fixes. Scout-before-finalize. SAR 06/03: 0/10 wins. |
| 2026-06-05 | Results pipeline | SAR0603-05 + older cards loaded. DB: 157 races. |
| 2026-06-11 | **Session 2 (full)** | ROI audit corrected. Weeks 1–3 complete: payoff infrastructure (r5_payoffs.py), tight-cluster exact re-validation (ACTIVE/CONFIRMED), conditional logit P(win) β=0.7674, tier ladder DELETED, exotics module (r5_exotics.py) $12 cap, overlay retro-test −56.9% NOT AUTHORIZED, SAR 06/06 payoffs loaded (174/179 backfill), R5_SPEC v3.10. All 5 Harry rulings locked. DB: 174 races. |
| 2026-06-12 | **Session 3A + 3B** | Display-only: days_since_last (f224) + LAYOFF tags, BRIS run style/Quirin (f210/211) + pace-profile header + lone-E logger (paper), trainer angles for full contender set, wet-track bundle (f80-84 + best_off) via --wet. Backfill: 1,620/1,747 picks (TRACK_MAP fix). Webapp parser lockstep + pre-existing lowercase-surface bug fixed (3 races/card recovered). 3B research: tj_n year-stats — 84% picks affected, +2.4 ROI pts overall, SAR unchanged 9.4% → NO pre-SAR change, rerun at n≥60. Commit 72d72ca. **System feature-frozen for Saratoga.** |
| 2026-06-12 | **Pre-SAR instrumentation** | Backtest decontamination: is_backtest guardrail extended to r5_exotics generate/settle/report (commit b990cc7 gap closed). rank3_tracker added — auto-logs $2 paper bet on rank-3 pick every race (settle math: sp_odds = mutuel payout per $2, profit = sp − 2.0). val_n paper75 line added to val_n_tracker (line='paper75', ≥7.5 AND rank≤5); val_n lines auto-wired to run_r5.py --track (paper8 default, --live for live8). Pace diagnostic: no win-share lift under engine pace_style; BRIS field 210 shows weak E-type lift → Issue 17 opened. Rank-3 ROI corrected to +17.4% (was inflated 4× by wrong profit formula; ex-PURE MADNESS = −0.9%). Commits a00b099, af33df9. |
| 2026-07-06 | **MARKET-ANCHORED GATE → NO-GO (decisive)** | Ran the falsification gate (Fable round-2 spec, `scripts/market_anchor_gate.py`): per-race conditional logit, does comp_ex_val add win info orthogonal to CLOSING tote? n=120 (full-field closing odds + comp_ex_val join, no coupled, single winner). Result: β=+0.031 (LR 0.06, 90% CI [−0.16,+0.22] spans 0); **OOS mean ΔLL = −0.0164/race, 90% CI [−0.023,−0.010] excludes 0 NEGATIVE**; SAR fold −0.072. α=0.973 (market near-calibrated → machinery sound). **comp_ex_val carries NO conditional signal over the market; slightly hurts OOS.** Per pre-registered rule: NO-GO now, one confirmatory re-run at n≈300, else ABANDON. **This moots the n≥100 class/FCI reweight (β measures the information set, not the weights) — class work ON ICE pending the n≈300 confirm.** Reconciled the mirages: rank-3 non-SAR +24.4%→+1.7% ex-outlier / SAR −43.8%; val_n≥9 +49.7%→−4.8% ex-outlier → **val_n live authorization downgraded to PAPER.** Every positive number in the system is now accounted for as takeout-level or a single payout. |
| 2026-07-06 | **SAR 07-05 + n≥60 CHECKPOINT** | Card run (9 races) with pre-race official scratch check (0 confirmed pre-race; 10 MTO flagged). Results ingested; 19 scratches recorded (MTO + late scratches incl. R6 #1 and R9 key #11 — both inside contender sets → refunds fired correctly). Exotics settled **−14.3%** ($75 staked, −$10.72; R2 +$13.40 & R8 +$8.88 the only cashes). R5 set-capture 3/9, CM 1/9. **Crossed n≥60 → ran pre-registered model-vs-market test (n=63 SAR winners): mean model-rank of winner 4.40 vs market-rank 3.13 (Δ +1.27); model ranks winner BELOW market in 65% of races; winner in MODEL top-3 = 41% vs MARKET top-3 = 67%.** CONFIRMS the 07-04 hypothesis and quantifies the long-standing SAR win-rate drag: the model systematically under-ranks winners the market identifies. Feeds v3.11 β-refit — NOT a race-day weight change. SAR exotics meet-to-date +15.2% ($568 staked). |
| 2026-07-05 | **SAR opening weekend (07-03 + 07-04)** | Both cards run, results ingested, exotics settled, CM logged/finalized. **07-03:** brutal variance — R5 rank-1 1/11, set-capture 4/11, exotics **−89.4%** (four double-digit winners incl. 22-1/15-1; CM equally blind to all four — confirmed card variance, not model fault). **07-04:** set-capture 5/11 (R5 & CM), exotics corrected to **+10.7%** — R10 #9 Warp Nine (17.7-1) topped by BOTH models, EX box +$58. Found + fixed scratch-settlement distortion: chart-absent scratches (R2 #12, R6 #16 etc.) never written to race_finish_order → refund path never fired → boxes overcharged. Hand-corrected 07-04 in-DB (18 is_late_scratch rows + re-settle), −8.3% → +10.7%. Ingestion bug filed (reconcile_picks in r5_payoffs.py should record chart-absent entered horses as is_late_scratch=1). Model record/weights untouched. |

---

## 📋 Immediate Next Steps

> For the full task list and in-meet checkpoint details, see **TODO.md** (authoritative).

1. **SAR opening day July 3** — system is ready. Run `r5_card.py` → `r5_results_cli.py` daily. Paper trackers (rank3, val_n paper75, val_n paper8) auto-log from `--track`. Use `--live` only for authorized live val_n ≥8 bets.
2. **Monitor in-meet checkpoints** — SAR n≥40 (structure menu review), n≥60 (β refit + Issue 17 eval), n≥100 (CM decision), val_n n≥120 (threshold re-decision).
3. **No code changes before opening day** — system is feature-frozen. Any observation at Saratoga that suggests a change requires n≥threshold validation, not race-day adjustment.

*Update this file after each session. Keep the session log current. This is the handoff document for every new Claude conversation and for Fable 5 architecture sessions.*
