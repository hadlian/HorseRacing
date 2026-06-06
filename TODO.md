# R5 Handicapping System — Project TODO

> This file is the authoritative task list for the R5 project.
> It is updated after each work session and is the sync point for all collaborators.
>
> **Last updated:** 2026-06-05 (Results pipeline complete — SAR 06/03-05 + CDX 05/02 + BAQ 05/09 + LRL 05/16 all loaded; 157 races in DB)
> **Current version:** R5 v3.10 | CompareModels v1.1 (field-extraction corrected — parallel system, see `comparemodels/`)
> **Current performance (157-race DB):** Top pick win 22.9% | Top-3 hit 56.1% | Play signal (spread ≥0.50) 29.5% win | Skip 18.0%
> **By track:** BAQ 31.6% | SAX 30.0% | CDX 26.8% | LRL 15.4% | SAR 9.4% (3 days — new track, calibration gap expected)
> **Recent cards:** SAR 06/03: 0/10 wins, 6/10 top-3. SAR 06/04: 1/11 wins. SAR 06/05: 2/11 wins (partial results).
> **Next planned session:** Accumulate SAR data. T/J combo at meet backtest when SAR is 2+ weeks in. Issue 15 (wager construction) gated on Saratoga calibration. FAIR tier inversion (13% vs SPEC 27%) — monitor, small sample.

---

## 🚨 URGENT — Fix before next live card

### ~~Scout-3 — `scratchIndicator='A'` (Also-Eligible) Incorrectly Treated as Scratch~~ `FIXED — 2026-05-28`
- **File:** `Claude/r5_scout.py`, `Claude/run_r5.py`, `Claude/r5_parser_v2.py`
- **Bug:** Old code: `if runner.get("scratchIndicator", "N") != "N":` — treated any non-"N" value as a scratch. The DRF API uses `"A"` for Also-Eligible horses (on the wait list, draw in when scratches occur). They are NOT scratched.
- **Live incident:** CDX 2026-05-28 R7. #13 OUR STARRY NIGHT had `scratchIndicator='A'`. Scout marked it scratched. R5 dropped it from the field. 6 other R7 horses actually scratched → AE drew in → #13 finished 2nd at $8.04 place. Exacta #3-#13 paid $133.60. Trifecta $260.50. R5 missed it entirely because the horse wasn't even scored.
- **Fix applied (multi-file):**
  1. `r5_scout.py` `fetch_official_scratches()` — now returns `(scratches, also_eligibles)` tuple. Only `'Y'` = scratch. `'A'` = AE (recorded separately). Unknown indicators logged but kept in field.
  2. `r5_scout.py` `main()` — AEs written to scout JSON under new `also_eligibles[]` key (parallel structure to `scratches[]`).
  3. `run_r5.py` `apply_scout_adjustments()` — AE horses get `h["also_eligible"] = True`, are scored normally (not removed from field).
  4. `r5_parser_v2.py` `report()` — table row prints `[AE]` tag after tier; race block prints `⏳ ALSO-ELIGIBLE: #N HORSE — on wait list; will only run if a regular entrant scratches. Confirm gate status at MTP before betting.` warning.
- **End-to-end test:** Re-ran scout on CDX0528. R7 now shows 6 scratches + 1 AE (#13 OUR STARRY NIGHT). Re-ran R5 R7. Field disclosure: "13 entries → 7 starters (6 removed)". #13 scored at rank 7, comp 4.41 SPEC, tagged `[AE]`, ALSO-ELIGIBLE warning printed.

### ~~Scout-4 — Name-Match Bug~~ `NOT A BUG — 2026-05-28`
- **Initial suspicion:** CDX 5/28 R7: scout JSON listed #5 SWEET DANI BOY as scratched but R5 output still showed it in the field.
- **Root cause:** Stale JSON. Original R5 analysis was saved at 17:29; scout JSON was re-fetched at 19:49 with an updated scratch list. The 17:29 R5 run loaded an *earlier* scout JSON that didn't yet include #5. Re-running R5 with the current JSON correctly removes #5.
- **Lesson:** Scout JSON timestamps matter. Field-disclosure line (above) will surface scratch deltas at run time. Consider stamping the loaded scout JSON's mtime into the R5 report header so it's clear which intel version was applied.

### ~~R5 Report — Field Count Disclosure Line~~ `FIXED — 2026-05-28`
- **File:** `Claude/run_r5.py`
- **Fix applied:** When any horse is removed by scout, the race report now prints:
  ```
  🐎  R7 FIELD: 13 entries → 7 starters  (6 removed by scout: #1, #5, #7, #9, #11, #12, #13)
       ⚠️  Verify against official track program — scout may include Also-Eligible (AE)
           horses that draw in if scratches occur.
  ```
  This makes the entry-vs-starter gap visible at race time, so AE/name-match bugs can't hide. Cosmetic transparency — does not fix Scout-3/Scout-4, just exposes them.

---

## 🔴 v3.x — Engine Fixes (Priority Order)

### ~~Issue 1 — Maiden / First-Time Starter Class Bug~~ `FIXED — v3.3`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** `class_n=0.0` for horses with no BRIS speed figures. `[DEBUT]` tag added to table row and field-level warning printed.
- **Commit:** be7bc04 — 2026-05-09

### ~~Issue 2 — Value Score Inversion~~ `FIXED — v3.4`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** One-sided floor fix. `diff = or_ - mr` direction preserved (overlay detection) but floor raised from `max(1.0, ...)` → `max(5.0, ...)`. Underlays now get val_n=5.0 (neutral) instead of being penalised down to 0.8. Overlays (high odds + model likes) still fire val_n up to 10.0. Market favourites the model ranks low no longer have their composite dragged down by a compounding val_n penalty.
- **De' Medici case:** Was val_n=1.5 → now val_n=5.0. The composite loss from this horse's val_n goes from −0.35 to 0.0.
- **Commit:** 2026-05-10 (evening)

### ~~Issue 3 — T/J Weight Underperforming~~ `FIXED — v3.5 (2026-05-16)`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** T/J raised 10% → 15%. Best @ Distance (8%) and Prime Power (5%) added as new components. Offsets: FCI 25→22%, Bias 15→8%, Val 10→5%, Ped 10→7%, Class 20→13%. Now a 9-component composite.

### ~~Issue 3a — result_fetched Flag Not Set on Direct SQL Logging~~ `FIXED — 2026-05-12`
- **File:** `Claude/r5_tracker.py`
- **Fix applied:** Safety net UPDATE added to `load_csv()` after the bulk loop. Sets `result_fetched=1` for any race with `finish_pos` populated, regardless of how results were written. `apply_result()` was already correct on all code paths. Commit `2dfc3c2`.

### ~~Issue 4 — Composite Score Ceiling~~ `FIXED — v3.6 (2026-05-24, commit 5c103ff)`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** `fci_n` and `best_dist_n` replaced with par-relative formula: `5.0 + (fci − par_eff) / 5.0` where `par_eff = clamp(par, 70, 105)`. Debut/no figures: `fci_n = 4.0`. Race header prints Par value. Mid-week allowance cards lift ~+1.0 pt.

### ~~Auto-Scout Path Bug~~ `FIXED — run_r5.py (2026-05-24)`
- **Fix applied:** `subprocess.run` was looking for `r5_scout.py` in CWD. Fixed to use `_scout_path` (absolute path). API key env-var still requires manual pre-run of scout.

### ~~Issue 5 — No Scratch Gate~~ `FIXED — v3.3`
- **File:** `Claude/run_r5.py`
- **Fix applied:** Per-race scratch notice prints when any scratched horse held pre-scratch Rank 1-3. Shows scratched horse name, pre-scratch rank, and revised top pick with composite and tier. Scratched horses excluded from DB logging. Scout JSON scratches feed this automatically.
- **Note:** Scout must be run race-morning to catch day-of scratches reported in articles. Manual cross-check against official scratch list still recommended for high-stakes races.

### ~~Issue 6 — Crowded Room Penalty~~ `FIXED — v3.7 (2026-05-28)`
- **File:** `Claude/r5_parser_v2.py`
- **Two-tier implementation:**
  - **MODERATE** (spread 0.5–1.5): existing ⚠️ TIGHT CLUSTER advisory print, no score change.
  - **SEVERE** (spread ≤0.5): 🚨 VERY TIGHT CLUSTER. -0.40 deduction applied to top horse's composite (typically slips one tier and frequently swaps Rank 1 ↔ Rank 2). Strong recommendation to SKIP win bet and build EX box / TRI key around top 3.
- **Threshold validation against 99-race DB:**
  - spread ≤0.5: Rank 1 wins **17.1%** vs Rank 2 wins **25.7%** (n=35) — Rank 2 beats Rank 1
  - spread 0.5–1.5: Rank 1 wins ~25% (n=54) — normal, no penalty needed
  - spread >1.5: Rank 1 wins **50.0%** (n=10) — high conviction zone
  - Old 1.5 threshold fired in 90% of races → diluted; new 0.5 threshold fires in ~36% of races (meaningful).
- **Backtest result (99 races):** +3.0 pts overall win rate (26.3% → 29.3%); +8.3 pts on severe-cluster subset (16.7% → 25.0%). 35/36 severe races see Rank 1↔Rank 2 swap; 9 swaps caught true Rank 2 winners.
- **Today (CDX0528) example:** Severe fired on R1, R3, R4, R5, R8. Net result on today's card was -1 (R5 gained AWESOME RUTA win, R1+R8 lost). Sample-size noise — long-run signal is positive.
- **Persistence:** Deduction is applied in `finalize_field()` so all downstream consumers (CLI report, DB picks table, webapp PLAY/NEAR/SKIP, CompareModels comparison) see the lower comp. Flag `tight_cluster_severe=True` stamped on the original Rank 1; `tight_cluster_flag=True` on all top-3. `pre_tight_comp` preserves the original score for transparency.

### ~~v3.8 Stage 1 — DRF Field Additions~~ `SHIPPED — 2026-05-29`
- **File:** `Claude/r5_parser_v2.py`
- **Fields added:** 41 (AE/MTO from DRF), 58 (program post post-scratch), 62 (medication/1st-time Lasix), 64 (equipment change), 1179 (best BRIS speed — turf)
- **Scoring changes:**
  - 1st-time Lasix (field 62 = 4 or 5): +0.20 to comp
  - Blinkers ON (field 64 = 1): +0.10 to comp
  - Blinkers OFF (field 64 = 2): −0.05 to comp
  - Turf races: `best_dist_n` now uses `best_turf` (field 1179) instead of `best_dist` (field 1181) — surface-accurate
  - Post bias scoring: uses `program_post` (field 58, post-scratch update) when available, falls back to field 4
  - AE flag now set from DRF field 41 directly — no scout dependency
- **Display:** `[1stLasix]`, `[BlkON]`, `[BlkOFF]` tags in horse row; top pick shows "Best BRIS Turf" on turf races; ⚡/🔧 lines in top pick detail block

### ~~v3.9 — Code Review Bug Fixes~~ `SHIPPED — 2026-06-03`
- **Trigger:** First structured code review of `r5_parser_v2.py` + callers. 8 findings, 5 fixed immediately, 2 deferred for advisory input, 1 deferred as low-priority.
- **Fixes shipped:**
  1. **Stale tier after scout adj** (`run_r5.py`) — `apply_scout_adjustments` now calls `tier()` after updating `h['comp']`. Previously, report, scratch notices, and DB all showed pre-scout tier even when scout adj crossed a tier boundary.
  2. **Scout-before-finalize architecture** (`run_r5.py`, `r5_parser_v2.py`) — Scout intel loading and `apply_scout_adjustments` now run BEFORE `finalize_field()`. `finalize_field` re-applies stored `h['scout_adj']` after the component composite, before the tight-cluster deduction. Tight-cluster spread now computed on scout-aware composites. `pre_comp` synced to post-scout value so val_n rank divergence also reflects scout order.
  3. **Purse crash on None** (`r5_parser_v2.py`) — `horses[0]['purse']:,.0f` now guarded; prints "N/A" when DRF field 12 is blank.
  4. **ml_odds crash on top pick** (`r5_parser_v2.py`) — `top['ml_odds']:.0f` in TOP WIN PICK header now guarded; prints "[N/A ML]" when no morning line set.
  5. **EXOTICS IndexError on <3 starters** (`r5_parser_v2.py`) — TRIFECTA/SUPERFECTA lines wrapped in `len(ranked) >= 3` guard; EXACTA wrapped in `len(ranked) >= 2`.
- **Deferred — pending advisory input:**
  - **pp_n neutral anchor** — formula `(pp-100)/6` anchors neutral at pp=130. If typical claimer PP is 100–115, most horses with data score below neutral while debut horses score 5.0 (neutral fallback). Need Gemini/ChatGPT input on typical BRIS Prime Power range by race type before changing anchor. Query to validate: `SELECT median(prime_power) FROM picks WHERE prime_power > 0`.
  - **Scout adj ordering vs tight cluster** — fully resolved by fix #2 above (scout-before-finalize). No further action needed.
- **Deferred — low priority:**
  - **No-odds val_n inflation** — horses with missing ML odds get default `odds_rank = n//2+1`, giving them a spurious overlay signal. Formula already floors at 5.0 so they can't be penalized, but they can score up to 8.5. Low impact at 5% composite weight. Fix: set `val_n = 5.0` for any horse with `ml_odds=None`. Hold until after Saratoga calibration.

### ~~v3.8 Stage 2 — Beaten-Favorite & Distance W% Backtests~~ `RESEARCH COMPLETE — 2026-06-03`

**Beaten-favorite signal (fields 1126–1135) — KILLED**
- Backtest: 923 matched horses, 16 DRF files, 129-race DB.
- Result: beaten favorites win at **26.2%** vs 12.2% baseline — outperform, not underperform.
- Model R1 + beaten fav: **33.3%** win (n=15, noise) vs 29.9% non-beaten-fav R1.
- Root cause: self-selection for quality. Recently-favored horses are better horses. The crowd under-bets beaten favorites (positive ML ROI +16.5%), creating overlay — not penalty territory.
- **Decision: −0.10 deduction killed. Do not implement as a comp adjustment.**
- **Re-routed to Issue 16:** beaten-favorite at long odds = overlay buy signal for live tote integration.

**Distance win% signal (fields 65–74) — POSITIVE KILLED, NEGATIVE DEFERRED**
- Backtest: 923 matched horses across all flags.
- Positive flag (≥3 starts, >25% dist W%): wins at **13.3%** vs 16.7% baseline. Model R1+positive: 22.2% vs 34.0% baseline R1. ML ROI −15.8%.
- Root cause: double-counting. Distance credentials are already in form_n (recent speed figs) and class_n (par performance). The market also over-bets distance specialists → they become underlays. +0.5 nudge would actively hurt model and return edge to crowd.
- Negative flag (≥5 starts, <10% dist W%): wins at **7.1%** vs 16.7% baseline — strong directional signal (ML ROI −23.2%). But n=28 (3% of field) — too thin to hardcode.
- **Decision: +0.5 positive killed. −0.3 negative deferred to post-Saratoga (need n≥60–80).**
- **Re-routed to Issue 16:** positive distance specialist = market-bias underlay indicator for live tote integration. Same pattern as beaten-favorite: where the crowd overreacts, there is overlay.
- **Backtest script:** `Claude/r5_beaten_fav_backtest.py` (also contains distance W% logic — rename if reused).

**T/J Combo at current meet (fields 1413–1417) — NOT YET TESTED**
- Still open. Validation needed: confirm meet stats populate consistently (may be thin early in meet). Test when Saratoga is 2+ weeks in.

**Per-race speed pars for last 10 starts (fields 1167–1176) — NOT YET TESTED**
- Complex scope. Hold until T/J meet combo and surface WS4 are resolved first.

### Issue 7 — Surface-Specific WS4 Weighting `PROPOSED`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** Current WS4 uses uniform weights (0.4 / 0.3 / 0.2 / 0.1) regardless of surface. Turf and dirt performance drivers differ meaningfully.
- **Proposed fix:**
  - Dirt: weight last 2 starts more heavily — recent form drives dirt results
  - Turf: shift toward Trend and FCI over raw speed — class and trajectory matter more on grass
- **Validation needed:** Specific split weights must be validated against results data before hardcoding.
- **Status:** Proposed (Gemini advisory, 2026-05-08). Not started.

### Issue 8 — Data Scarcity Confidence Cap `PROPOSED`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** In fields where >30% of horses have fewer than 2 lifetime starts, the model produces normal-looking scores despite very low information quality. A per-horse approach is preferred — reduce comp for individual low-data horses rather than capping the whole field.
- **Proposed fix:**
  - Per-horse: if horse has < 2 lifetime starts, apply a confidence reduction to its individual comp score
  - Field flag: if > 30% of field is low-data, add a `LOW INFO FIELD` warning to the race header
  - Do NOT apply a hard 5.0 field-wide cap — too blunt, penalises well-qualified horses in the same race
- **Note:** Resolve Issue 1 (maiden class bug) first — that fix may already address much of this problem.
- **Status:** Proposed (Gemini advisory, 2026-05-08). Refined 2026-05-08. Not started.

### Issue 9 — Tight Cluster UI Flag `PROPOSED`
- **Files:** `Claude/r5_parser_v2.py`, `webapp/templates/index.html`
- **Problem:** Issue 6 adds a `TIGHT CLUSTER` penalty to the engine score, but the UI currently has no way to display *why* a race was flagged. A user seeing a NEAR or SKIP verdict with no explanation will not know the cluster was the reason.
- **Proposed fix:** Engine passes a `tight_cluster: true` flag in the race output. UI displays "Tight Speed Cluster" as an explicit bullet in the Bet Recommendation "Against" reasons box.
- **Note:** This is a two-part task — engine side (Issue 6) must be built first, then UI side here.
- **Status:** Proposed (Gemini advisory, 2026-05-08). Not started.

### Issue 10 — Post-Saturday Surface Weighting Validation `VALIDATION TASK`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** Issue 7 proposes surface-specific WS4 weights (heavier recent-form weighting for dirt; Trend/FCI-heavy for turf) but specific values are unvalidated hypotheses, not confirmed fixes.
- **Validation task:** After Saturday 2026-05-10 results are logged, compare actual winners against current uniform WS4 rankings on dirt vs turf races separately. Only implement split weighting if the data supports it.
- **Do not implement Issue 7 before this validation is complete.**
- **Status:** BAQ0510 results now logged (2026-05-10). Ready for validation post-Preakness with 60+ race DB.

### Issue 11 — Distance-Specific Speed Floor `PROPOSED`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** WS4 uses a weighted average of last 4 starts regardless of distance. A horse with a 95 at 6f but only 82 at a mile gets the same WS4 treatment whether today's race is a sprint or route. BRIS carries best-speed-at-distance figures which are currently unused.
- **Proposed fix:** Incorporate BRIS best-at-distance figure as a secondary check on FCI — e.g. flag or discount horses where best-at-distance is meaningfully below WS4, particularly in routes.
- **Validation needed:** Confirm BRIS field positions for best-at-distance in 1435-field format before coding. Validate signal strength against 60+ race DB.
- **Do not implement before Preakness.** Post-Preakness priority, after Issue 3 (TJ weight).
- **Status:** Proposed 2026-05-11. Not started.

### ~~Issue 13 — Late Scratch Detection at Result Logging~~ `FIXED — v3.4 (2026-05-15)`
- **Files:** `Claude/r5_tracker.py`, `Claude/r5_analyze.py`
- **Fix applied (two parts):**
  1. **`apply_result()` auto-detection:** After assigning all finish positions, any pick still NULL = late scratch. Auto-sets `finish_pos=-1` and prints `⚠️ LATE SCRATCH` notice.
  2. **New `--finalize TRACK DATE` command:** For cards logged via direct SQL, scans for NULL positions and marks them -1. Safety guard aborts if any race shows >3 NULLs (= partial logging, not late scratches).
  3. **`r5_analyze.py` exclusion (two-tier):** `calc_summary()` excludes `finish_pos=-1` only (keeps NULL for old partial-logging cards). Component correlations and scout impact exclude both -1 and NULL (need confirmed finish data). Late-scratched top picks no longer inflate the loss denominator.
- **Real example confirmed:** CDX0514 R8 — #5 VIVIANITE (Rank 8, DEBUT) was the actual late scratch (not SPUN TIGHT R1, which ran and finished 4th). Correctly logged as -1.
- **Workflow:** After full result logging, run `python3 Claude/r5_tracker.py --finalize CD 20260514` to catch any missed late scratches before regenerating Excel.

### Issue 16 — Live Tote Odds Integration `PROPOSED`
- **Files:** `Claude/r5_scout.py` (new function) or new `Claude/r5_live_odds.py`, integrated via `run_r5.py`
- **Problem:** Report and `val_n` calculation use ML (morning line) odds from the .DRF file. ML is the program's guess at fair odds and rarely matches the actual board. Live tote odds are the only basis for real overlay/underlay decisions at post time.
- **Proposed scope:**
  1. **New scraper module** — fetch live odds snapshot for a given track/race close to post time.
  2. **Source candidates:**
     - DRF live odds widget (no API but visible on entries/results page near MTP)
     - TwinSpires / AmWager public odds pages
     - Equibase live odds (paid)
     - Track's own tote feed (Churchill/NYRA/etc publish JSON for some cards)
  3. **Snapshot strategy:** decide whether to capture odds at MTP-10, MTP-5, MTP-2, or rolling. Trade-off: earlier = more time to bet but odds may move; later = accurate but no time to act.
  4. **Report integration:** add `Live` column next to `ML` in the race table, showing current odds. Highlight horses where `Live >> ML` (overlay forming) or `Live << ML` (sharp money).
  5. **val_n recomputation:** optionally recompute `val_n` using live odds rank instead of ML rank — would substantially improve overlay detection. Keep ML version as fallback when live odds unavailable.
- **Pre-work questions:**
  - What's a reliable, scrape-safe source that survives DRF page redesigns?
  - Should this run continuously (background polling) or one-shot at user trigger?
  - Does the webapp need a "refresh live odds" button, or does CLI cover the workflow?
- **Validation:** compare ML overlay calls vs live overlay calls on 20+ races. If live-odds val_n materially outperforms ML val_n on ROI, promote to default.
- **Status:** Proposed 2026-05-28 (per CDX0528 R7 audit — user asked for live odds in report alongside the field-disclosure fix). Not started.

### Issue 12 — Career Average Class (Ever Avg. Class) `LOW PRIORITY`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** `class_n` uses active last-4-start capability. Career average class is not captured — useful for identifying dropdowns (high historical class now running lower) vs horses at their ceiling.
- **Proposed fix:** Secondary flag only — not a composite weight. Flag horses where career avg class significantly exceeds recent class (dropdown angle) or falls below (ceiling horse). Display as a table annotation rather than affecting score.
- **Note:** Raw earnings normalisation is poor across age/track/era — do not use money earned as a direct signal. Career class via par comparison is cleaner.
- **Status:** Proposed 2026-05-11. Low priority — do not start until Issues 3 and 11 are evaluated.

### ~~Issue 14 — Tracker Non-Top-4 Finisher Bug~~ `FIXED — 2026-05-24 (commit 81ce32d)`
- **File:** `Claude/r5_tracker.py`
- **Problem:** `apply_result()` was auto-marking any horse not in the provided top-4 finish list as `finish_pos=-1` (excluded from stats, treated like a scratch). Legitimate 5th–9th finishers silently inflated win rate by not counting as losses.
- **Fix applied:** Non-top-4 horses now get `finish_pos=5` (runs but unplaced) and correctly count in the denominator as losses. True pre-race scratches (handled by scout gate) and late scratches (handled by `--finalize`) correctly remain at `-1`.
- **DB retroactive correction (CDX0524):** 43 horses corrected `-1 → 5`; 16 kept at `-1` (confirmed pre-race scratches from PDF cross-check).
- **Corrected stats baseline:** 81 races, 636 horses, 24.3% top-pick win rate (was 25.7% pre-fix), val_n ROI +140.1% (was +163.8%). More accurate going forward.

---

## 🟣 v4.1 — Wager Construction (Research, POST-SARATOGA)

### Issue 15 — Wager Construction Module `RESEARCH`
- **Philosophy / framing:** R5 is a *handicapping* system, not a *wagering* system. The composite score identifies solid contenders ranked by quality — it does not pick single winners. The current PLAY/NEAR/SKIP bet recommendation is single-horse, win-focused, which throws away the model's actual edge when Rank 2 and Rank 3 hit the board (as they frequently do at a ~24% top-pick win rate). A real-world example: a recent race where R5's #1 and #3 finished 1st-3rd and the exacta paid $200 — the model worked; the wagering structure didn't capture it.
- **Goal:** Translate ranked composite output into appropriate exotic wagering structures (EX box, EX key, TRI key, DD/P3 keys, WIN-only) instead of forcing single-horse win bets. The Wager Construction Module is the missing layer that honors the "solid contenders, not winners" philosophy.
- **Sequencing — do NOT build before:**
  1. Issue 4 (composite ceiling fix → v3.6) is implemented and validated over ~20 races
  2. Issue 3 (TJ weight → v3.7) is approved and validated
  3. Saratoga 2026 calibration confirms the handicapping signal is sound

  Rationale: building wagering logic on a miscalibrated composite amplifies bad picks into bad bets with real money. Handicapping has to be right first.
- **First milestone (research, no engine code change):** Write a backtest script against the existing race DB (currently 81 races, will be larger post-Saratoga) that computes ROI for several wagering structures applied uniformly to every logged race:
  - EX box Rank 1 + Rank 2
  - EX key Rank 1 over Rank 2-4
  - TRI key Rank 1 with Rank 2-5
  - TRI box Rank 1-3
  - WIN-only on Rank 1 (baseline for comparison)
- **Output:** ROI per structure, hit rate per structure, distribution of which Ranks actually finished 1-2-3. This either validates the wagering-layer thesis cheaply or kills it before any production build.
- **Priority:** Medium (gated on v3.6/v3.7 calibration validation at Saratoga)
- **Target version:** v4.1 (post-Saratoga, post-calibration)
- **Status:** RESEARCH — Not started 2026-05-24

---

## 🟡 v4.0 — UI Enhancements (Priority Order)

All UI work lives in `webapp/`. Do not modify `Claude/` scripts in UI sessions.

### ~~Multi-Track Batch ZIP Upload~~ `ALREADY BUILT`
The existing upload UI already handles multiple DRF files and ZIP archives containing multiple tracks in a single pass. No work needed here.

### ~~UI-1 — Mobile Responsive Design~~ `DONE — 2026-05-10`
- **File:** `webapp/templates/index.html`
- **What was built:** `@media (max-width: 639px)` block. Horse table hides columns 3–11 on mobile, showing only `#`, `Horse`, `Comp`, `Tier`. Each row has a `▶` tap-to-expand button that reveals a 3-column metrics grid (ML, WS4, Trend, FCI, vPar, Ped, T/J, Pce, Val). Race tabs scroll horizontally instead of wrapping. Summary table hides Purse/Pace/ML columns. Picks grid goes single-column. Reduced padding throughout. Desktop layout unchanged.

### ~~UI-2 — Historical ROI Dashboard~~ `DONE — 2026-05-24 (commit 872db8b)`
- **Files:** `webapp/app.py`, `webapp/templates/index.html`
- **What was built:** Chart.js 4.4.1 Analytics tab integrated as a 3rd view toggle (alongside Overview / Race Detail). `/api/analytics` Flask endpoint added. Four charts: tier hit rates (horizontal bar), value ROI curve (line), score distribution + win% (grouped bar + dual y-axis), track/surface splits (grouped bar). Data cached via `analyticsLoaded` flag. Empty state for < 10 races or no DB. Mobile-responsive via matchMedia.

### UI-3 — Live Odds Divergence Alerts
- **Files:** `webapp/app.py`, `webapp/templates/index.html`
- **Problem:** No real-time comparison between morning line and live board prices.
- **Proposed fix:** UI layer that compares morning line against a live odds feed and flags "Strong Overlays" where board price significantly exceeds model rank.
- **Note:** Fix value score inversion (Issue 2) in the engine before building this — the UI alert is the display layer on top of a correct signal.
- **Status:** Not started. Depends on Issue 2 resolution and a reliable odds data source.

### ✅ UI-4 — BRIS Summary Report Download (for Dennis) `COMPLETE — 2026-05-29 · commit 4d78624`
- **Files:** `webapp/app.py` (new route + import), `webapp/templates/index.html` (new button), `webapp/requirements.txt` (add `python-docx`), possibly new `comparemodels/bris_summary_docx.py` (renderer).
- **Goal:** A button on the webapp main page that takes the uploaded DRF, runs the existing CM engine in-memory, and downloads a `.docx` matching Dennis's BRIS Summary Handicap Report format. This is for Dennis's own use — not a CM/R5 integration, not a bet-rec change.
- **Reference output:** `Dennis compare /extracted/CDX0529_BRIS_Summary_Report.docx` (the format we received from Dennis). Per-race blocks of Top 3 per category, Consensus Leaders, Dominant, Pace, Overlay Watch, A/B/C tiers, Composite Scores. Plus end-of-card "HORSES WITH 3+ POSITIVE FACTORS" rollup tables.
- **Reference output (text version):** `Dennis compare /extracted/CDX0529_summary_output_schema.txt` — same content, plain text. Useful as a layout cheat sheet.
- **Engine reuse:** Call `comparemodels.drf_to_csv.convert_drf_to_csv` to produce a temp CSV, then `comparemodels.comparemodels_engine.score_card` to get the score dict (already returns `category_picks`, `ranked_horses`, etc. — every line of Dennis's format is in there). No engine changes needed. Do NOT log to `comparemodels_results.db` from this route — it's a read-only render.
- **Positive Factors rollup:** Just `consensus_count` from `ranked_horses`. Group by race, filter `consensus_count >= 3`, sort desc. No new computation.
- **Format:** `.docx` via `python-docx` library. Underline rendering should match Dennis's spec — top horse in a category gets actual underline formatting when the underline rule fires (top − 3rd ≥ 2.0). The plain text uses `__1__` markers; the docx should render as actual underline.
- **Filename:** `<TRACK><MMDD>_BRIS_Summary_Report.docx` (matches Dennis's naming, e.g. `CDX0529_BRIS_Summary_Report.docx`).
- **Button placement:** Next to the existing "Generate Report" R5 analyze button (per UI-2 pattern). Label suggestion: "BRIS Summary (Dennis format)". Gray out / hide if upload was CSV not DRF — CM only runs from DRF.
- **Trigger model:** Independent of R5. User can upload DRF and click the BRIS Summary button without waiting for or needing R5 output. Backend route: `POST /api/bris-summary` returning the .docx as attachment.
- **Dependencies:** Add `python-docx` (~MB) to `webapp/requirements.txt`. Already used in some Python tooling on this machine but not in this project.
- **Out of scope:**
  - CM badges / strip on R5 output (a separate UI feature — see project-comparemodels memory if revived)
  - Any change to R5 PLAY/NEAR/SKIP verdict
  - Writes to `comparemodels_results.db`
  - PDF or plain-text alternative output (start with docx only)
- **Status:** Spec written 2026-05-29 by engine session. Build in a webapp session.

---

## 🔀 CompareModels v1.0 — Parallel BRIS Summary System

> See `comparemodels/COMPAREMODELS_STATE.md` for full spec and results.
> All CM code in `comparemodels/`. Read-only access to `results/r5_results.db` and `files 2/*.DRF`.

### ✅ CM v1.0 — CDX0524 live card `COMPLETE — 2026-05-24`
- R5 v3.6 and CM both run on CDX0524 (10 races). Results pending.
- Double-consensus (R5 + CM agree): 2 of 10 races.
- Best double-consensus play: R9 LAZLO (8-1 ML, R5 6.87 FAIR, CM cons=8) — strongest single play on card.
- R5 logged to DB; CDX0524_R5_analysis.txt saved to repo.

### ✅ CM v1.0 — Build + 63-race backfill + analysis + CDX0521 live `COMPLETE — 2026-05-21`

**Build complete.** Backfill: 7 cards, 63 races, 669 picks, 631 results joined.
Report: `comparemodels/reports/comparemodels_vs_r5_63races_20260521_020626.xlsx`

**Head-to-head (63 races):**
- CM win rate: 25.4% (16/63) — tied with R5
- R5 win rate: 25.4% (16/63)
- CM top-3 rate: 47.6% vs R5 55.6%
- CM ROI (SP): +50.6% vs R5 ROI (SP): +93.0%
- Agreement rate: 31.7% (only 20/63 races)

**Disagreement breakdown (43 races):** R5 correct 10 / CM correct 10 / Neither 23 — exact dead heat.

**CM segment outperformance (actionable):**
- Non-graded Stakes: CM 38.5% vs R5 15.4% (13 races — largest gap)
- Dirt surface: CM 30.0% vs R5 25.0% (40 races)
- CDX (Churchill): CM 33.3% vs R5 23.3% (30 races)

**CM signal quality:**
- Consensus ≥ 4 → 30.8% win rate (39 races) — key threshold
- Prime Power underline → 33.3% win rate (57 fires) — best single signal
- Overlay Watch → 5.6% win rate (18 fires) — **BROKEN, do not use**

**Advisory:** CM is a supplemental confidence filter for R5, not a replacement. When R5 top pick has CM consensus ≥ 4 and/or Prime Power underline, increase confidence. When disagreement + CM consensus < 4, lean R5.

**CDX0521 live validation (first card):**
- R5: 2/8 wins, CM: 2/8 wins — tied again, consistent with 25.4% backfill baseline
- R3 SHINING MOMENT: both agree, CM cons=7 DOM + 5-cat underline → won at $3.96 ✓ (key signal validated live)
- R2 SASSY PRINCESS: CM edge (cons=7 DOM, $5.14) — CDX disagreement pattern held ✓
- R1 LACK OF RIESLING: R5 edge at $8.00, CM liked 3-1 fav
- Massive scratch counts (R1: 7, R3: 8, R8: 9) — both models affected
- Workflow confirmed: score → log → results → finalize → daily xlsx each race day

### ✅ CM v1.1 — Field-extraction corrected + engine bug patched `COMPLETE — 2026-05-29`
- **Trigger:** Dennis delivered BRIS_Workflow_Package.zip with his BRIS Summary parser and CDX0529 reference CSV.
- **Findings:** Engine methodology was already identical to Dennis's spec (same weights, composite math, dominant/overlay/tier rules). But 3 of 8 input fields were emitting wrong values:
  - Avg Class: was today's purse (col 11), now mean of cols 1166-1175 (BRIS Class Rating per-PP)
  - Early Pace: was `999 − mean(cols 765-774)` inversion noise, now max of cols 765-784 (real BRIS pace)
  - Late Pace: was `999 − mean(cols 815-824)` inversion noise, now max of cols 815-824 (real BRIS late pace)
- **Engine bug also fixed:** BRIS Top Pick +2 bonus was inside the per-category loop in `comparemodels_engine.py:102` — would have fired +16 the moment CM-4 was wired up. Moved outside the loop.
- **Verification:** 752/752 field comparisons against Dennis's CDX0529 CSV match exactly. R5 DB integrity SHA-256 unchanged across re-backfill.
- **Re-backfill result (95-race universe):**
  - Top-pick win rate: 23.2% → 25.3% (+2.1 pp)
  - Turf win rate: 13.3% → **20.0%** (+6.7 pp, ~50% relative)
  - BAQ: 21.1% → 26.3% (+5.2 pp); LRL: 15.4% → 23.1% (+7.7 pp); CDX/Dirt unchanged
- **Files touched:** `comparemodels/comparemodels_engine.py`, `comparemodels/drf_to_csv.py`, `comparemodels/comparemodels_backfill.py` (race-count check relaxed from `==63` to `>=63`), `comparemodels/COMPAREMODELS_STATE.md`.
- **Pre-fix DB preserved:** `comparemodels/comparemodels_results.db.pre_fieldfix`

### CM-1 — Overlay Watch definition broken `PROPOSED — post v3.6`
- Current: consensus ≥ 5 AND ML ≥ 6.0 → 5.6% win rate
- Fix: raise consensus threshold or add surface/pace qualifier
- **Do not use Overlay Watch until fixed.**

### ~~CM-2 — Turf weight calibration~~ `RESOLVED 2026-05-29`
- **Original diagnosis (wrong):** Speed-heavy weights don't translate to grass.
- **Actual root cause:** Pace extraction was broken inversion noise; turf was over-weighted on speed because pace was effectively zero signal.
- **Result post-fix:** Turf win rate 13.3% → 20.0% with **no weight changes**. See CM v1.1 entry above.

### CM-3 — Trainer Rating signal weak `PROPOSED`
- 0/12 wins with Trainer Rating underline (pre-fix data).
- Re-evaluate against post-fix DB before fixing — Trainer Rating extraction itself was correct; signal weakness may persist.
- Fix candidate: BRIS trainer% by distance/surface/race-type

### CM-4 — BRIS Top Pick field not located `DEFERRED`
- +2 bonus silently skipped. Find field position in DRF before v2.
- **Note:** Engine bug that would have applied +16 instead of +2 was patched 2026-05-29. Safe to wire up the field whenever it's located.

---

## 🔵 v5.0 — Intelligence Layer (Future)

- ML-powered pattern recognition and lap time prediction
- Anomaly detection for workout and form angle outliers
- Optional LLM coaching summaries per race

---

## ✅ Completed (v3.4)

- **Issue 2 — Value score inversion fix** — One-sided floor: `max(1.0)` → `max(5.0)`. Underlays get val_n=5.0 (neutral) instead of being penalised. Overlays still rewarded up to 10.0. De' Medici case: val_n 1.5 → 5.0, composite drag eliminated. (2026-05-10)

## ✅ Completed (v3.3)

- **Issue 1 — Maiden/Firster class_n fix** — `class_n=0.0` for no-speed-figure horses; `[DEBUT]` flag in output (commit be7bc04, 2026-05-09)
- **Scout — API model fix** — `claude-sonnet-4-20250514` → `claude-sonnet-4-6`; was silently falling back to empty intel on every run (commit b2451df, 2026-05-09)
- **Scout — Track keyword expansion** — Added `CDX` and `BAQ` to `TRACK_KEYWORDS`; was using generic fallback terms (commit b2451df, 2026-05-09)
- **Scout — Auto-scout track matching** — `--auto-scout` now matches JSON by track prefix from DRF filename instead of loading most-recent-by-mtime (commit b2451df, 2026-05-09)
- **Scout — Stacking cap** — Total scout adjustment per horse capped at ±0.40; prevents qualitative signals from overriding speed/class metrics (2026-05-09)
- **Issue 5 — Scratch Gate** — Per-race scratch notice when pre-scratch top-3 horse is scratched; revised top pick printed; scratched horses excluded from DB (2026-05-10). **Live validation 2026-05-10 Race 7:** #4 FORT NELSON (pre-scratch Rank 3) scratched. Engine correctly promoted #5 I'M READY TO GO (Comp 6.41) as revised top pick, updated exotics (WIN #5 / EX #5-#1 / TRI #5-#1-#3), shifted value alt to #3 FIDDLING FELIX (12-1, Comp 5.46). Tight Cluster flag also fired (spread 0.95 pts).
- **UI — Scratch Notice Display** — `parse_output` in `webapp/app.py` now pre-scans full engine text for scratch notices keyed by race number (`R7:` etc.) before splitting into race blocks. Notices are injected into the correct race after parsing. Previously notices appeared between blocks and were associated with the wrong race. Fixed 2026-05-10.
- **Issue 6 partial — Tight Cluster display flag** — ⚠️ TIGHT CLUSTER warning when top-3 spread ≤1.5 pts; display only, no score change (2026-05-10)
- **Scout — LRL track keywords** — Laurel Park added to TRACK_KEYWORDS for Preakness week training intel (2026-05-10)
- **34-race results DB** — CDX0502 (14), DBY0502 (1 Derby), CDX0507 (8), BAQ0509 (11). 18.2% top-pick win rate, 45.5% top-3 hit rate, TJ signal +0.86.
- **Audit reports** — CDX0507 and BAQ0509 audit TXTs saved in `Results/2026/`. Peter Pan G2 and Ruffian G2 wins validated graded-stakes model strength.

## 🟠 Scout — Remaining Improvements (post-Preakness)

### ~~Scout-0 — Official Scratch List~~ `FIXED — v3.3 (2026-05-10)`
- **Fix:** `fetch_official_scratches(track, date)` in `Claude/r5_scout.py`. Queries DRF entries page, parses embedded race JSON, extracts `scratchIndicator != "N"` runners with race/pgm/name. Merges into scout JSON `scratches[]`. Runs automatically when `--track` is specified. Deduplicates against Claude-extracted scratches.
- **Validated:** BAQ 2026-05-10 — 13 scratches found including #4 FORT NELSON R7.
- **DRF URL:** `https://www.drf.com/entries/entryDetails/id/{TRACK}/country/USA/date/{MM-DD-YYYY}`

### ~~Scout-1 — Horse Name Expansion~~ `FIXED — run_r5.py (2026-05-24, commit 8c49d4d)`
- **File:** `Claude/run_r5.py`
- **Fix applied:** `parse_drf()` now runs BEFORE the scout subprocess in `--auto-scout` mode. Top 3 horses per race (sorted by WS4) are collected and passed as `--horses` to `r5_scout.py`. Also passes `--date` so scout targets the correct race day. Names capped at 30 (10 races × 3), deduplicated, min length 4 chars. Scout already had `--horses` support — this wires it from `run_r5.py`.
- **Effect:** Scout now extracts horse-specific trainer quotes, workout notes, and equipment changes in addition to track-level articles.

### Scout-2 — Sentiment Confidence Score
- **File:** `Claude/r5_scout.py`
- **Problem:** Extraction prompt asks for `positive|neutral|negative` with no confidence weighting. Ambiguous quotes (e.g. "needs a race") can be misclassified.
- **Fix:** Add `confidence` field (0.0–1.0) to extraction prompt; discard signals with confidence < 0.7 before applying adjustment.
- **Status:** Not started. Evaluate raw scout output on 2–3 cards first.

## ✅ Completed (v3.2-R4C)

- DRF parser (`r5_parser_v2.py`) — 7-component scoring pipeline, 1435-field BRIS format
- WS4™ speed formula — weighted 4-race figure with continuous trend, surface-matched
- Pace scenario engine — HOT / NML / PRESS classification with speed/closer fit
- Web scout (`r5_scout.py`) — live intel via HRN, Blood-Horse, TDN + Claude API extraction
- Results tracker (`r5_tracker.py`) — SQLite logger, manual/CSV/auto-fetch
- Performance analyzer (`r5_analyze.py`) — Excel workbook, 5 sheets
- Web frontend (`webapp/`) — Flask upload UI, structured race cards, colour-coded table
- Bet Recommendation — PLAY / NEAR / SKIP verdict (comp ≥ 6.0 / 5.5–5.99 / < 5.5)
- Overview toggle — 📋 card-level summary + 🏇 full tabbed race detail
- PDF download — ReportLab via `--pdf` flag or web UI checkbox
- README — badges, authorship, roadmap, contributors, trademark notice (R5™, R5 Composite Score™, WS4™)

---

## Notes for Collaborators

- **Implementation:** All code changes are made in the Claude Code session (this repo's primary implementation environment). Verify actual file contents before proposing changes — do not assume column positions, variable names, or weights without reading the source.
- **Advisory:** Gemini is used for design ideas, pseudocode, and architectural recommendations only. It does not write to this repo.
- **Engine vs UI:** Engine work (`Claude/`) and UI work (`webapp/`) are handled in separate sessions. Do not mix.
