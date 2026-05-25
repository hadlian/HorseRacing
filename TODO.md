# R5 Handicapping System — Project TODO

> This file is the authoritative task list for the R5 project.
> It is updated after each work session and is the sync point for all collaborators.
>
> **Last updated:** 2026-05-24 (CDX0524 results logged; Scout-1 + Issue 14 fixed; Issue 15 (Wager Construction) added as RESEARCH; 81 races in DB)
> **Current version:** R5 v3.6 | CompareModels v1.0 (parallel system — see `comparemodels/`)
> **Next planned session:** Run more races this week. Continue v3.6 validation (Issues 6, 7, 8 pending). Log LRL0516 R14.

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

### Issue 6 — Crowded Room Penalty `PARTIAL — display flag live, deduction pending`
- **File:** `Claude/r5_parser_v2.py`
- **Display flag LIVE:** ⚠️ TIGHT CLUSTER warning prints when top-3 spread ≤1.5 pts. Shows individual composites and advises value alt. No score changes.
- **Remaining:** Score deduction / PLAY suppression — requires validation against results data before implementing. Do not add deduction until threshold is confirmed.
- **Status:** Flag implemented 2026-05-10. Deduction pending post-Preakness validation.

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
- **Validation needed:** Confirm BRIS field positions for best-at-distance in 1496-field format before coding. Validate signal strength against 60+ race DB.
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

### CM-1 — Overlay Watch definition broken `PROPOSED — post v3.6`
- Current: consensus ≥ 5 AND ML ≥ 6.0 → 5.6% win rate
- Fix: raise consensus threshold or add surface/pace qualifier
- **Do not use Overlay Watch until fixed.**

### CM-2 — Turf weight calibration `PROPOSED`
- CM 10.5% turf vs R5 15.8%. Speed-heavy weights don't translate to grass.
- Fix candidate: surface-specific weight sets

### CM-3 — Trainer Rating signal weak `PROPOSED`
- 0/12 wins with Trainer Rating underline. Raw win% × 100 too noisy.
- Fix candidate: BRIS trainer% by distance/surface/race-type

### CM-4 — BRIS Top Pick field not located `DEFERRED`
- +2 bonus silently skipped. Find field position in DRF before v2.

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

- DRF parser (`r5_parser_v2.py`) — 7-component scoring pipeline, 1496-field BRIS format
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
