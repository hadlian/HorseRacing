# R5 Handicapping System — Project TODO

> This file is the authoritative task list for the R5 project.
> It is updated after each work session and is the sync point for all collaborators.
>
> **Last updated:** 2026-06-12 (Session 3A complete; system feature-frozen for Saratoga)
> **Current version:** R5 v3.10 | CompareModels v1.1
> **Deployment target:** Saratoga 2026 — opens July 3, 2026
>
> **Current performance (174-race DB, corrected 2026-06-11):**
> Top pick win 23.1% | ROI **−18.5%** | Rank-3 ROI **+17.4%** (only positive slot)
> Play/spread gate RETIRED | Tier ladder RETIRED | Overlay live win betting NOT AUTHORIZED
>
> **In-meet key numbers to watch:**
> STANDOUT keys 0-for-10 (−100%); DEFAULT EX box −35.1%; TIGHT TRI box +384.7% (2 hits in 4 cards)

---

## 🟢 IN-MEET CHECKPOINTS — Saratoga 2026 (all start July 3)

### ⏳ SAR n≥40 payoff races — Structure menu ROI review
- **Decision:** Which shapes stay in the menu; what gets gated or removed
- **Watches:** DEFAULT EX box (−35.1% on 4 SAR cards — is this track-specific or structural?); STANDOUT keys (0-for-10 — thin contender set when spread is wide?)
- **Script:** Paper tickets are logging automatically from day 1 via `r5_exotics.py` (paper mode default)
- **No changes before this gate.**

### ⏳ SAR n≥60 races — SAR β refit + tj_n fallback rerun
- **β refit:** Fit a SAR-only conditional logit and compare to global β=0.7674. If SAR β diverges materially, flag for Harry ruling on whether to use track-specific β.
- **tj_n fallback:** Rerun `scripts/tj_fallback_backtest.py`. At n≥60 SAR races, meet-stat starvation is worst (exactly the cases the year-stats chain would fix). If SAR win rate improves under year-stats, bring to ruling as v3.11.
- **Note:** 3B research found SAR win rate unchanged (9.4% either way) on existing data — drag has other causes. This is the right test set.

### ⏳ SAR n≥100 races — CM merge-or-keep decision
- **Decision:** Is CM still earning its place in the contender set (+7.5pp capture)?
- **If CM capture degrades below +3pp:** propose removing CM legs (reduces set size, simplifies exotics)
- **If CM capture holds:** keep as is

### ⏳ val_n n≥120 qualifying bets — val_n ≥8 re-decision
- **Current state:** val_n ≥8 +41.8% on 4 wins (n too small); ≥9 +85.7% on 2 wins
- **Decision:** Is the threshold right? Adjust to ≥8 or ≥9? Or widen rank filter?
- **Guardrails in place from day 1** (flat $2, max 2/card, hard stop: 0 wins in 30 bets OR SUM(profit) < −$60)
- **Script:** `r5_probability.py` `log_val_bet()` + `val_n_tracker` table in DB

### ⏳ Mid-July 2026 — Live odds capture build (Issue 16)
- **Scope:** Fetch live tote odds snapshot near post time; add Live column to report; optionally recompute val_n using live odds rank
- **Required for:** Any future overlay reconsideration (overlay retro-test used hindsight final odds — live odds at MTP-5 may differ)
- **Source candidates:** DRF live odds widget, TwinSpires/AmWager public odds, track tote feeds
- **Decision needed:** One-shot at user trigger vs background polling; MTP-10 vs MTP-5 snapshot
- **Status:** Not started. Proposed 2026-05-28.

### ⏳ n≥300 total races — Decorrelated P(win) upgrade + overlay reconsideration
- **Current model:** One-parameter logit on comp_ex_val. Overestimates longshots where market knows better.
- **Upgrade path:** Multi-parameter (speed cluster, pace shape, surface, class) with out-of-sample validation
- **Overlay:** Only reconsider live overlay betting after this upgrade, paper-first
- **Gate is hard:** n=300 minimum; no shortcuts

---

## 🔴 OPEN ENGINE ISSUES (v3.x)

### Issue 7 — Surface-Specific WS4 Weighting `PROPOSED`
- **Problem:** Uniform WS4 weights (0.4/0.3/0.2/0.1) across dirt and turf. Turf performance drivers differ.
- **Proposed:** Dirt: weight recent starts more. Turf: lean Trend/FCI over raw speed.
- **Status:** Post-SAR validation. Need 150+ race DB with surface split.

### Issue 8 — Data Scarcity Confidence Cap `PROPOSED`
- **Problem:** Horses with < 2 lifetime starts produce normal-looking scores.
- **Proposed:** Per-horse confidence reduction; `LOW INFO FIELD` header warning if > 30% field is low-data.
- **Status:** Proposed. Low priority pre-Saratoga.

### Issue 16 — Live Tote Odds Integration `ACTIVE — MID-JULY`
- See in-meet checkpoint above.

### Scout-2 — Sentiment Confidence Score `PROPOSED`
- Add `confidence` field (0.0–1.0) to extraction prompt; discard signals < 0.7.
- **Status:** Not started.

### pp_n Neutral Anchor `DEFERRED`
- Formula `(pp-100)/6` anchors neutral at pp=130. May be too high for claiming fields.
- **Status:** Pending advisory input. Query: `SELECT median(prime_power) FROM picks WHERE prime_power > 0`.
- **Hold until:** Post-SAR.

### No-Odds val_n Inflation `DEFERRED`
- Horses with no ML get default odds rank → spurious overlay signal.
- **Fix:** Set `val_n = 5.0` for `ml_odds=None`.
- **Impact:** Low (5% weight). Hold until after SAR calibration.

### Negative Distance Flag `DEFERRED`
- Horses ≥5 starts, <10% dist W%: wins at 7.1% vs 16.7% baseline. Strong signal, n=28.
- **Fix:** −0.3 to comp for this subset.
- **Status:** Deferred. Need n≥60–80.

---

## 🟡 OPEN UI ISSUES

### UI-3 — Live Odds Divergence Alerts `NOT STARTED`
- Blocked on Issue 16 (live odds capture build, mid-July).
- Display layer comparing ML vs live board; "Strong Overlay" flags.

### UI-4 — BRIS Summary docx (Dennis format) `SPEC WRITTEN`
- Button on webapp → generates `.docx` matching Dennis's BRIS Summary Handicap Report format.
- Spec: `TODO.md` (below, preserved) and `comparemodels/COMPAREMODELS_STATE.md`.
- **Status:** Spec written 2026-05-29. Not started. Post-Saratoga priority.

---

## 🔀 CompareModels Open Items

### CM-1 — Overlay Watch definition broken `POST-SAR`
- Current: consensus ≥ 5 AND ML ≥ 6.0 → 5.6% win rate
- Fix: raise threshold or add qualifier

### CM-3 — Trainer Rating signal weak `POST-SAR`
- Re-evaluate against SAR data (Trainer Rating extraction is correct; signal may just be weak)

### CM-4 — BRIS Top Pick field not located `DEFERRED`
- +2 bonus silently skipped. Engine bug (would have been +16) patched 2026-05-29.

---

## ✅ COMPLETED — Session 3A (2026-06-12, commit 72d72ca)

- **3A-1: days_since_last (field 224)** — parsed, logged, LAYOFF tags [45+/90+/180+], exotics LAYOFF notes ≥90 days
- **3A-2: BRIS run style + Quirin (fields 210/211)** — appended to name in report, Q column, pace-profile header, lone-E paper-track LONE_E_NOTE logger (zero-cost; paper track only; structure unchanged)
- **3A-3: Trainer angles for full contender set** — all R5 ranks 1–3 (was top-pick-only); LAYOFF MATCH and DEBUT MATCH highlights
- **3A-4: Wet-track bundle (fields 80–84 + 1180)** — parsed, logged, displayed via --wet flag (condition is race-day input, not in DRF)
- **3A backfill:** 1,620/1,747 historical picks carry 3A display data (TRACK_MAP fix: CD→CDX, AQU→BAQ, SA→SAX)
- **Webapp parser lockstep** + pre-existing lowercase-surface bug fixed (inner turf 't', all-weather 'A' silently dropped → recovered 3 races/card)
- **3B research: tj_n year-stats fallback** — 84% picks affected, +2.4 ROI pts, SAR unchanged 9.4% → NO pre-SAR change; rerun at n≥60 via `scripts/tj_fallback_backtest.py`

## ✅ COMPLETED — Session 2 (2026-06-11, commits 4e1f6ca/c1197e3/99b0e89)

- **Week 1: Payoff infrastructure** — `r5_payoffs.py` parses Equibase chart PDFs via pdftotext. 174/179 races backfilled.
- **Week 1: Tight-cluster exact re-validation** — ACTIVE/CONFIRMED (Harry ruling). 0 unexplained deltas. Deduction helps.
- **Week 1: Contender set union** — R5 1–3 ∪ CM 1–2 = 66.9% capture vs 59.4% R5-only (+7.5pp, gate passed).
- **Week 2: P(win) layer** — Conditional logit β=0.7674 (97 races, Newton MLE). comp_ex_val backfill 1,140 picks.
- **Week 2: Output revamp** — Tier ladder deleted (engine + webapp). P(win)/fair_odds in output. Analytics ROI bug fixed.
- **Week 2: val_n guardrails** — Coded with 3 stop conditions; refusal demonstrated.
- **Week 3: Final-odds overlay retro-test** — −56.9% ROI (142 bets). **LIVE OVERLAY WIN BETTING NOT AUTHORIZED.**
- **Week 3: Exotics module** — `r5_exotics.py` with structure menu, $12 cap, settlement self-test gate, paper-default/--live-explicit. 70 settled SAR paper tickets.
- **Week 3: R5_SPEC v3.10** — Full rewrite with all Harry rulings locked.
- **Week 3: Dry run clean** — SAR 06/06 end-to-end (run_r5 → tickets → ingest → settle). Feature freeze available.

## ✅ COMPLETED — Engine (v3.3 through v3.9)

All v3.x engine fixes are closed. See `R5_PROJECT_STATE.md` issue history for full detail.

---

## 🔵 FUTURE — v5.0 Intelligence Layer

- ML-powered pattern recognition and lap time prediction
- Anomaly detection for workout and form angle outliers
- Optional LLM coaching summaries per race

---

## Notes for Collaborators

- **Implementation:** All code changes in Claude Code session. Verify actual file contents before proposing changes.
- **Advisory:** Fable 5 for architecture decisions (use corrected ROI data, not win rate). Sonnet for session advisor. Gemini/ChatGPT for design ideas only — do not write to this repo.
- **Engine vs UI:** Engine work (`Claude/`) and UI work (`webapp/`) handled in separate sessions.
- **Feature freeze:** System is frozen for Saratoga. Observations at the track generate data, not immediate code changes. All changes require n≥threshold validation.
