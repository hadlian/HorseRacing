# R5 Handicapping System — Project TODO

> This file is the authoritative task list for the R5 project.
> It is updated after each work session and is the sync point for all collaborators.
>
> **Last updated:** 2026-05-10 (evening)
> **Current version:** R5 v3.4 (val_n floor fix — Issue 2 resolved)
> **Next planned session:** Thursday 2026-05-14 — CDX (Churchill Downs resumes Thu) + PIM load for Preakness Day (~Sat 2026-05-16)

---

## 🔴 v3.3 — Engine Fixes (Priority Order)

These must be resolved in order. Do not change TJ weights (Issue 3) until Issues 1 and 2 are fixed.

### ~~Issue 1 — Maiden / First-Time Starter Class Bug~~ `FIXED — v3.3`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** `class_n=0.0` for horses with no BRIS speed figures. `[DEBUT]` tag added to table row and field-level warning printed.
- **Commit:** be7bc04 — 2026-05-09

### ~~Issue 2 — Value Score Inversion~~ `FIXED — v3.4`
- **File:** `Claude/r5_parser_v2.py`
- **Fix applied:** One-sided floor fix. `diff = or_ - mr` direction preserved (overlay detection) but floor raised from `max(1.0, ...)` → `max(5.0, ...)`. Underlays now get val_n=5.0 (neutral) instead of being penalised down to 0.8. Overlays (high odds + model likes) still fire val_n up to 10.0. Market favourites the model ranks low no longer have their composite dragged down by a compounding val_n penalty.
- **De' Medici case:** Was val_n=1.5 → now val_n=5.0. The composite loss from this horse's val_n goes from −0.35 to 0.0.
- **Commit:** 2026-05-10 (evening)

### Issue 3 — T/J Weight Underperforming `MODERATE`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** At 10% weight, T/J cannot overcome FCI/Class even when winners have field-leading T/J scores. 3 of 8 winners in the CDX 05/07 audit had the highest or near-highest T/J in the field.
- **Proposed fix:** Raise T/J from 10% → 15%. Offset: Class 20% → 13%, Bias 15% → 10%, Ped 10% → 7%.
- **Status:** Candidate. Issues 1 & 2 now resolved — this is next in queue. Requires explicit approval before code change. Validate after Preakness week data collected.

### Issue 4 — Composite Score Ceiling `MODERATE`
- **File:** `Claude/r5_parser_v2.py`
- **Problem:** No race on CDX 05/07 reached SOLID tier (7.5). Best composite was 6.08. The `fci_n` normalisation (baseline=60, scale÷6) was calibrated for higher-class horses. Mid-week undercards with lower speed figures will always grade SPECULATIVE.
- **Proposed fix:** Card-quality tier adjustment or dynamic normalisation based on field average FCI.
- **Status:** Under discussion. No code change proposed yet.

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
- **Status:** Pending Saturday results. Not started.

---

## 🟡 v4.0 — UI Enhancements (Priority Order)

All UI work lives in `webapp/`. Do not modify `Claude/` scripts in UI sessions.

### ~~Multi-Track Batch ZIP Upload~~ `ALREADY BUILT`
The existing upload UI already handles multiple DRF files and ZIP archives containing multiple tracks in a single pass. No work needed here.

### ~~UI-1 — Mobile Responsive Design~~ `DONE — 2026-05-10`
- **File:** `webapp/templates/index.html`
- **What was built:** `@media (max-width: 639px)` block. Horse table hides columns 3–11 on mobile, showing only `#`, `Horse`, `Comp`, `Tier`. Each row has a `▶` tap-to-expand button that reveals a 3-column metrics grid (ML, WS4, Trend, FCI, vPar, Ped, T/J, Pce, Val). Race tabs scroll horizontally instead of wrapping. Summary table hides Purse/Pace/ML columns. Picks grid goes single-column. Reduced padding throughout. Desktop layout unchanged.

### UI-2 — Historical ROI Dashboard
- **Files:** `webapp/app.py`, `webapp/templates/index.html`
- **Problem:** Performance data is logged to SQLite via `r5_tracker.py` but only accessible via CLI or Excel export.
- **Proposed fix:** Add an "Analytics" tab in the web UI. Pull SQLite data via a new Flask route and display interactive ROI and hit-rate charts by confidence tier.
- **Status:** Not started. Requires sufficient logged races to be meaningful.

### UI-3 — Live Odds Divergence Alerts
- **Files:** `webapp/app.py`, `webapp/templates/index.html`
- **Problem:** No real-time comparison between morning line and live board prices.
- **Proposed fix:** UI layer that compares morning line against a live odds feed and flags "Strong Overlays" where board price significantly exceeds model rank.
- **Note:** Fix value score inversion (Issue 2) in the engine before building this — the UI alert is the display layer on top of a correct signal.
- **Status:** Not started. Depends on Issue 2 resolution and a reliable odds data source.

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

### Scout-1 — Horse Name Expansion
- **File:** `Claude/run_r5.py`, `Claude/r5_scout.py`
- **Problem:** Scout queries only use track keywords. DRF horse names are never passed to the scraper, so Claude extracts no horse-specific trainer quotes or workout notes.
- **Fix:** Pass top-ranked horse names from the parsed DRF to `gather_raw_intel()` at runtime via `--auto-scout`.
- **Status:** Not started. Do after first live scout card to confirm base extraction is working.

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
