# R5 Handicapping System — Project TODO

> This file is the authoritative task list for the R5 project.
> It is updated after each work session and is the sync point for all collaborators.
>
> **Last updated:** 2026-07-19 (n≥100 gate rulings: CM KEEP +9.0pp, CM1 locked v0, TIGHT EX key retired; CM1 wired into webapp pre-race logging — webapp cards 0716–0718 were missing CM1, now back-logged; webapp CM import guard split so missing python-docx can't disable CM logging; SAR results settled through 07/18)
> **Current version:** R5 v3.10 | CompareModels v1.1
> **Deployment target:** Saratoga 2026 — opens July 3, 2026
>
> **Canonical baseline denominator:** `races WHERE result_fetched=1 AND is_backtest=0` = **160 resolved live races** (as of 2026-06-12). Backtest cards (SAR 2025 Jul 12/23, Aug 2) live in production DB tagged `is_backtest=1`; log future historical cards with `--backtest` flag (CLI) or Year override field (webapp). All analytics, β fit, and calibration exclude backtest rows automatically.
>
> **Current performance (246-race corrected canonical, 2026-07-19 — see WIN-PAYOFF REPAIR section below):**
> Top pick win **23.6%** | ROI **−10.3%** | Rank-3 ROI **+5.3%** on 234 (but ex-Professor-Plum ≈ −2.5% — single-payout, retirement stands)
> ⚠️ The old 160-race −18.5% / rank-3 +17.4% numbers were corrupted by the WPS parser bug (PURE MADNESS never won). Do not quote them.
> Play/spread gate RETIRED | Tier ladder RETIRED | Overlay live win betting NOT AUTHORIZED
>
> **Pace diagnostic (2026-06-12):** No actionable pace dynamic under R5 engine `pace_style`. HOT-scenario "closers win" angle is dead — win-share ≈ starter-share in all three scenarios. BRIS field 210 shows a weak pattern (see Issue 17), but `bias_n` uses engine style, not field 210. Do NOT structure tickets on pace scenario.
>
> **Rank-3 caveat (corrected 2026-07-19):** now +5.3% ROI on 234, BUT ex-Professor-Plum ($38.44) ≈ −2.5%. The entire margin is still one longshot — retirement stands. ⚠️ The old "+17.4% ex-PURE MADNESS" framing is VOID: PURE MADNESS never won; the $57.20 was THE OLD NINE's (WPS parser bug, see repair section). Paper-tracked via `rank3_tracker` (meet: 102 settled, 18 wins, −7.9%).
>
> **Paper trackers running from day 1 (auto-logged by run_r5.py --track):**
> - `rank3_tracker`: $2 flat paper bet on every rank-3 pick, every race
> - `val_n_tracker` line=paper75: $2 flat paper bet on val_n ≥7.5, model_rank ≤5 (complete population for n≥120 re-decision)
> - `val_n_tracker` line=paper8/live8: val_n ≥8 under guardrails (unchanged); live requires `--live` flag
>
> **In-meet key numbers to watch:**
> STANDOUT keys 0-for-10 (−100%); DEFAULT EX box −35.1%; TIGHT TRI box +384.7% (2 hits in 4 cards)
>
> **In-meet key numbers — updated 2026-07-12 (SAR live meet, 70 resolved races through 07/12):**
> R5 rank-1: 13/66 = 19.7%, ROI −2.1% (settled picks; near-flat only because of longshot winners)
> Exotics by shape (settled paper tickets): DEFAULT EX box −20.8% (32) | STANDOUT −27.8% (4) | **TIGHT −51.6% (86)**; TIGHT TRI box has collapsed to **−77.1%** (early +384.7% was the usual 2-hit mirage)
> Paper trackers: rank3 61 settled, 10 wins, −2.1% | val_n paper75 22 bets −$5.56 | val_n paper8 36 bets +$38.50 (2 wins — single-payout caveat applies)
> 07/12 card: R5 rank-1 0-for-8 (R3 top pick scratched); winner in R5 top-3 in 2/9; exotics −$87/$87 (0 collected). Post-scratch A/B: post-scratch −77.6% vs entries −100% (monitor only, NO method change)

---

## 🔧 2026-07-19 — WIN-PAYOFF PARSER BUG + FULL DATA REPAIR (supersedes all performance numbers below)

**Bug (Harry's find):** `r5_payoffs.py` WPS_RE rejected parentheses in horse names, so foreign-bred **winners** — "(IRE)/(GB)/(FR)" — dropped their Win/Place/Show line; every following pool shifted up one (PLACE→WIN), storing the runner-up's price as the WIN payoff. 13 races hit (Harry's 11 + SAR 0605 R11, 0606 R5 found in the full audit). Two more parser gaps fixed in the same pass: dead-heat co-winner rows (the `”` glyph blocked both the finish-table and mutuel parsers — SAR 0705 R6 now carries both WIN rows, $3.66 + $8.40) and pool assignment for co-winner lines. Separately, CDX 0502 R1's finish table was missing actual winner #11 Powershift entirely (payoffs/picks were right; table rebuilt from the SH5 combination).

**Blast radius + repair:** the buggy WIN rows had flowed into `picks.won/sp_odds` via reconcile — several races credited the **second-place horse as winner**. Full-DB repair synced all 2,546 chart-matched picks to official finish order (676 corrected), dead-heat aware; all trackers reset + re-settled from production settle logic. Verification: every official winner now has a matching WIN row and populated sp_odds; zero false `won` flags (3 checks, whole DB).

**💥 PURE MADNESS never won.** The $57.20 that anchored rank-3's "+17.4% only-positive-slot" story belonged to THE OLD NINE (IRE), who beat Pure Madness (2nd, "lacked the needed final kick" — chart verbatim) at 27-1 in SAX 0525 R1. The legendary payout was a results-entry error. Similarly OBLITERATION (20250802 R3 backtest) ran 2nd, not 1st.

**Corrected canonical numbers (246 live resolved races, 2026-07-19) — THIS IS THE BASELINE:**
- Rank-1: **23.6% win, ROI −10.3%** (better than the old −18.5% — the bug had been *understating* winner payoffs, e.g. Kensington Lane $48.66 stored as $5.04)
- Rank-3: 21.8% win, **+5.3%** on 234 — but ex-Professor-Plum ($38.44) ≈ −2.5%: the single-payout pattern persists, **retirement stands**
- rank3_tracker (meet): 102 settled, 18 wins, −7.9%
- Backtest caveat: 2025 SAR0712 R9 pick/chart name mismatch (Classic Creation vs Gilded Craken, same pgm) — backtest card alignment is suspect; excluded from analytics as always.

**Correction does NOT change the model.** β is a monotonic softmax temperature on comp_ex_val — it rescales P(win) magnitude but cannot reorder ranks, so R5's picks are byte-identical pre/post repair. Refit on clean data moved β 0.7674→0.7661 (−0.0012, negligible; NOT redeployed — no rank effect, only feeds retired OVERLAY/paper val_n). Freeze safe.

**`signal_validation.py` was also contaminated (fixed 2026-07-19, commit 79d30ab).** It filtered no races, so backtest cards + clobbered SAR 0605/0606 (result_fetched=0, stale finish data) leaked in — inflating rank-1 to 301 races/−17.8%. Added `LIVE_R5` predicate (`result_fetched=1 AND is_backtest=0`); now matches canonical 246/−10.3% exactly. Every prior signal_validation number was ~7pp pessimistic on rank-1.

**Market-anchor gate — corrected-data PREVIEW (not the pre-registered test):** re-ran `scripts/market_anchor_gate.py` on the repaired DB. At **n=199** joined races: β=+0.029 (LR 0.09, NS, 90% CI [−0.11,+0.18] spans 0); OOS mean ΔLL **−0.0071/race** (90% CI [−0.0102,−0.0043], excludes 0 negative); SAR fold −0.048. **Verdict unchanged: NO-GO.** The correction halved the OOS drag (was −0.0164 at n=120 on corrupted labels) but did not flip sign or verdict — cleaning the data did not rescue the fundamental score. This is a preview at n=199; the **pre-registered confirmatory re-run is still at n≈300** (~4 cards out at 262 total resolved) and will decide ABANDON vs keep-open on clean data.

---

## 📋 2026-07-19 — n≥100 GATE RULINGS (Harry)

At n=111 resolved live SAR races, three rulings recorded:

1. **CM: KEEP** — contender-set capture add measured at **+9.0pp** (10 CM-only winners across 8 cards) vs the +3pp retention threshold. No change to CM legs.
2. **CM1: LOCKED as v0** (equal-weight 9-flag count, best-speed tiebreak) — permanent third model, **contender-set + compare report role ONLY**. Flag definitions frozen: Frank's pending red-lines (legendary sire/dam list, doing-well cutoffs, speed method) land as a **v0.1 version bump**, never a silent edit. No betting role. Any future promotion requires clean pre-post provenance from 07/16 onward (07/03–07/12 backfilled; 07/17–07/19 logged post-result, deterministic from DRF). Meet contribution: +3.6pp on top of R5∪CM (4 CM1-only winners).
3. **TIGHT EX key: RETIRED** — −79.2% ROI on 24 tickets, and structurally unsound (keying inside a tight cluster concentrates stake on the lowest-priced combos). Removed from `select_structure()` in `r5_exotics.py` (results-pipeline side, outside the v3.10 freeze); settlement selftest passes; all other shapes continue as paper data collection. Do not restore without a ruling.

Not acted on: class/FCI stays ON ICE per the 07-06 NO-GO (n≈300 confirmatory re-run is ~3–4 cards away at 260 total resolved races); val_n paper75 re-decision waits for n≥120 bets (at 36); rank-3's 5-win card on 07/19 gets zero decision weight (retired slot, variance).

---

## 🚨 2026-07-06 — MARKET-ANCHORED GATE: NO-GO (supersedes several items below)

Ran the falsification gate (`scripts/market_anchor_gate.py`, Fable round-2 spec): does `comp_ex_val` add win info orthogonal to the CLOSING market? **n=120, OOS mean ΔLL = −0.0164/race (90% CI [−0.023,−0.010], excludes 0 negative); β=+0.031 (LR 0.06, NS); SAR fold −0.072.** α=0.973 confirms the market anchor is calibrated and the test had power. **Verdict: NO-GO** — the fundamental score carries no conditional signal over the market and slightly hurts OOS. Pre-registered rule: one confirmatory re-run at n≈300, else ABANDON the market-anchored win-overlay program.

**Consequences (all freeze-safe):**
- **rank-3 / CM rank-2 RETIRED as "positive slots."** Reconciled: rank-3 non-SAR +24.4%→**+1.7% ex-outlier** / SAR −43.8%; CM rank-2 flipped negative. Every headline is one payout. `rank3_tracker` also has NULL profits on all rows — do not quote numbers from it.
- **val_n ≥8 DOWNGRADED to PAPER** (Harry ruling): ≥8 +12.4%→−18.7% ex-outlier; ≥9 +49.7%→−4.8% ex-outlier — the next PURE-MADNESS mirage. Re-decide at n≥120 with selection discount (≥8 and ≥9 jointly; require positive point + bootstrap CI > ~−5%).
- **Class/FCI n≥100 investigation ON ICE** — β measures the information set, not the weights; reweighting can't extract signal that isn't conditionally there. Formal abandonment pending the n≈300 gate re-run.
- **Honest position:** no positive-ROI signal exists anywhere (rank-1 ≈ −takeout, overlay −56.9%, rank-3 outlier-only, val_n outlier-only, gate NO-GO). System's durable value = parsing, scratch/refund reconciliation, structured exotics, bankroll discipline. Pending n≈300 confirm, reclassify R5 as analysis/construction, not a win-betting edge.

---

## 🟢 IN-MEET CHECKPOINTS — Saratoga 2026 (all start July 3)

### ✅ SAR n≥40 payoff races — Structure menu ROI review `RESOLVED 2026-07-19 (see gate rulings above)`
- **Ruling:** TIGHT EX key RETIRED (−79.2% on 24; structurally unsound). All other shapes stay as paper data collection.
- **Meet numbers at ruling (n=111):** DEFAULT EX box −13.6% (49) | TIGHT EX box −27.3% (57) | TIGHT TRI box −52.1% (57) | STANDOUT keys −27.8%/−50% (n=8, too thin to rule on)
- **Early watches resolved:** DEFAULT EX box recovered from −35.1% to −13.6% (was small-sample noise); TIGHT TRI's early +384.7% fully collapsed (the standard 2-hit mirage).

### 🔵 SAR n≥60 races — SAR β refit + tj_n fallback rerun `GATE REACHED 2026-07-06 (n=63)`
- **β refit:** Fit a SAR-only conditional logit and compare to global β=0.7674. If SAR β diverges materially, flag for Harry ruling on whether to use track-specific β.
- **tj_n fallback:** Rerun `scripts/tj_fallback_backtest.py`. At n≥60 SAR races, meet-stat starvation is worst (exactly the cases the year-stats chain would fix). If SAR win rate improves under year-stats, bring to ruling as v3.11.
- **Note:** 3B research found SAR win rate unchanged (9.4% either way) on existing data — drag has other causes. This is the right test set.
- **✅ Pre-registered model-vs-market test RUN (n=63): CONFIRMED.** Mean model-rank of winner 4.40 vs market-rank 3.13 (Δ +1.27); model under-ranks winner in 65% of races; winner in MODEL top-3 = 41% vs MARKET top-3 = 67%. This is the mechanism behind the SAR drag. **β-refit constraint:** close the winner-rank gap WITHOUT killing the value-divergence edge (rank-3 +17.4% overlay came from diverging FROM the market, not matching it). Requires Harry ruling + version bump before any weight change — NOT a race-day fix.

### ✅ SAR n≥100 races — CM merge-or-keep decision `GATE REACHED 2026-07-19 (n=111) — RULING: KEEP`
- **Measured at n=111:** R5 top-3 alone 53/111 = 47.7%; CM ranks 1–2 add **10 winners → +9.0pp** (56.8% combined) — 3× the +3pp retention threshold, adds spread across 8 cards. CM keeps its contender-set legs unchanged. (CM1 adds a further +3.6pp → 60.4% three-model capture.)

### ⏳ SAR n≥100 races — v3.11 class/FCI over-ranking investigation `QUEUED 2026-07-06 (Option-2 diagnosis at n=63)`
- **Finding (n=63/41):** model systematically under-ranks SAR winners vs market (top-3 41% vs 67%). Attribution: **Class vs Par (37%) + FCI/speed (27%) = 64% of the mis-ranking** — model's losing picks beat actual winners by +2.13 class / +1.43 FCI on avg. Model over-trusts paper class + speed-figure superiority at SAR.
- **At n≥100, disambiguate the two hypotheses:** (1) **Weighting** — class/FCI over-weighted for deep SAR fields; test lower-class/FCI SAR-only β/weights vs capture + ROI. (2) **Metric calibration** — class-vs-par mis-reads SAR (pars, ship-ins, foreign form); audit par values + class scoring on the under-ranked winners.
- **HARD CONSTRAINT:** Class (+0.75) & FCI (+0.55) are the best winner/loser separators globally — do NOT cut weights globally. Any change must be SAR-scoped AND must not kill the value-divergence edge (rank-3 +17.4%). Harry ruling + version bump required.
- **HOLD until n≥100 (Harry directive 2026-07-06). No further model analysis before then.**

### ⏳ val_n n≥120 qualifying bets — val_n ≥8 re-decision
- **Current state:** val_n ≥8 +41.8% on 4 wins (n too small); ≥9 +85.7% on 2 wins
- **Decision:** Is the threshold right? Adjust to ≥8 or ≥9? Or widen rank filter?
- **Guardrails in place from day 1** (flat $2, max 2/card, hard stop: 0 wins in 30 bets OR SUM(profit) < −$60)
- **Script:** `r5_probability.py` `log_val_bet()` + `val_n_tracker` table in DB
- **paper75 line running from day 1:** complete ≥7.5 population logged as `line='paper75'` for n≥120 comparison. Use `python3 Claude/r5_probability.py --val-status` for both-line status.

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

### Issue 17 — bias_n Source Evaluation (BRIS field 210 vs engine pace_style) `POST-SAR`
- **Finding (2026-06-12):** The two pace classifiers disagree on ~27% of starters (e.g., 46 R5-"speed" horses are BRIS-S; 15 R5-"closer" horses are BRIS-E). Engine `pace_style` (which feeds `pace_scenario` + `bias_n`) shows win-share ≈ starter-share across all three scenarios — no actionable lift. BRIS field 210 shows the classic pattern in NORMAL and SLOW (E types +9.6pp and +10.4pp win-share lift) but with small n (especially SLOW n=18).
- **Hypothesis:** `bias_n` (component weight 8%, correlation ~0.06) is built on the weaker classifier. R5 pace_style uses raw fractional time differentials; BRIS field 210 is their proprietary style assignment and may capture pace-context better. Rebuilding pace_fit on field 210 could improve bias_n signal quality.
- **Data:** `bris_run_style` (field 210) logged per pick from day 1 (3A-2); sample grows passively at SAR. `LONE_E_NOTE` paper track covers the extreme lone-E case.
- **Gate:** Revisit with SAR n≥60 data, post-meet. No pre-meet change. All weight changes require explicit approval + version bump.

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
- Note: key-normalization defensive fix shipped 2026-06-14 (see CM-2 below). Signal logic is a separate issue.

### CM-2 — Key normalization hardened `COMPLETE 2026-06-14`
- Added `canon(hn)` helper; `format_top_three()` returns 3-tuple `(line, keys, underlined_key)`.
- All horse-number keys now flow through `canon()` — `appearances`, `composite`, `underlined_horses`, `ml_lookup`.
- Removed fragile `line.count("__")` underline detection; `ukey is not None` replaces it.
- **Verified:** for clean integer horse numbers, old and new output is bit-identical (bug was never active on standard cards).
- **Actual divergence:** coupled entries (`"1A"`) caused a hard crash in old code; new code handles them cleanly.

### CM-3 — Trainer Rating signal weak `POST-SAR`
- Re-evaluate against SAR data (Trainer Rating extraction is correct; signal may just be weak)

### CM-4 — BRIS Top Pick field not located `DEFERRED`
- +2 bonus silently skipped. Engine bug (would have been +16) patched 2026-05-29.
- **UPDATE (2026-07-08): Root cause confirmed — NOT a parser bug.** Full field-by-field review of `June2026Schema.txt` (all 1,435 DRF fields) confirms "BRIS Top Pick" / "Tip" / "Consensus" / "Best Bet" / "Analyst" do not exist anywhere in the DRF Ultimate PP schema. Cannot be fixed by remapping fields.
- **Confirmed in `BRIS_Summary_Handicap_System_Code.docx`:** `get_bris_top_pick()` expects a "BRIS Top Pick" column to already exist in the input CSV (TRUE/YES/Y/1/TOP flag per horse). Since the DRF has no such field, that column is never populated → the function returns "BRIS Top Pick: NA" silently and the composite +2 bonus never fires.
- **Origin:** Master spec doc's "Preferred future input: BRIS Summary screenshots" suggests the original workflow assumed manual/OCR transcription of BRIS's own printed Condensed Data Summary sheet (a separate proprietary BRIS product, not the DRF).
- **DECISION NEEDED (pending Dennis):** either (a) source "BRIS Top Pick" externally — manual entry per card or OCR off the BRIS Summary sheet — or (b) retire the "BRIS Top Pick" category and +2 bonus from CM scoring entirely, since it's LOW priority and post-Saratoga anyway.
- **Status:** Diagnosis closed. Sourcing decision remains open, still pending Dennis.

---

## 🆕 CM1 — Third comparison model `IN DESIGN` (contributor: **Frank**)

> New model to run head-to-head against R5 and CM (Dennis). Built from Harry's morning-homework
> checklist, deliberately scoped to signals R5/CM do **not** use. Spec: `comparemodels/CM1_SPEC_DRAFT.md`.
> Probes: `comparemodels/cm1_workouts.py`, `comparemodels/cm1_pace_fit.py`.

**Key finding (2026-07-11):** every CM1 signal is already inside the BRIS DRF — **no external
stat feed needed**. Data plan has no blockers; only human input outstanding is a legendary
dam/broodmare-sire list for the pedigree category (Cat-5).

**Three design questions resolved against data (8 SAR July cards, 777 horses) — awaiting Frank's red-line confirm:**
- **Q1 Workouts (Cat-1):** DRF f102-185. Harry's `36/48/60` bars = top-10% of works; rate is
  track-relative (training-track premium, turf discount). RESOLVED as percentile-relative per
  distance+surface. *Confirm: top-decile bar right? bullet bonus?*
- **Q2 Connections (Cat-2):** meet win% (f29/30, 35/36) already used by R5/CM → not net-new;
  CM1's edge = situational trainer angles (f1337-1366) + jockey turf/dist stat (f1367-1372),
  scored on **win% + $2 ROI**. Watch-list dropped. Cat-4 (surface) folded in. *Confirm: ROI gate
  ≥0 vs ≥+0.05? win% floors 20%/18%?*
- **Q3 Pace/distance fit (Cat-3):** per-PP running lines (f316-745). Calibrated: faded = led early
  + lost ≥4 pos; closed = back + gained ≥5 pos; ≥1.5F gap; same-surface only. *Confirm: collapse
  bars and same-surface rule.*

**Next:** Frank confirms Q1-Q3 red-lines → build CM1 on the `comparemodels/` harness (engine →
tracker → backfill → compare) so it drops into the existing ROI-vs-R5-vs-CM report. Q5 (pedigree)
and Q6 (weights) still open; Harry to supply the dam list.

---

## ✅ COMPLETED — Session pre-SAR instrumentation (2026-06-12)

- **Pace lift diagnostic:** E/EP win-share ≈ starter-share in all three scenarios (HOT/NORMAL/SLOW). Conclusion: pace scenario was measuring field composition, not a true pace dynamic. No action needed.
- **Rank-3 paper logger:** `rank3_tracker` table; auto-logged via `log_race_picks` (runs every card). Settled via `r5_results_cli.py` STEP 5. Status: `r5_tracker.rank3_status()`.
- **val_n ≥7.5 paper line:** `val_n_tracker` `line='paper75'` for val_n ≥7.5 AND model_rank ≤5. Auto-logged via `run_r5.py --track`. Status: `python3 Claude/r5_probability.py --val-status`.
- **val_n ≥8 wired to card workflow:** Auto-logs as `paper8` from `run_r5.py --track`; use `--live` flag for live bets (subject to gate). Both lines share `val_n_tracker`, distinguished by `line` column.
- **Backtest audit (b990cc7 gap):** `r5_exotics.py generate_card` and `settle_card` now filter `is_backtest=0`. `report()` query joins to races. `val_n_tracker` entries = 0 backtest rows (clean). `exotic_tickets` = 0 backtest rows (clean).

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
