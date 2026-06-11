# Session 2 — Week 1 Completion Report (2026-06-11)

Per `Prompts/SESSION2_BRIEF.md`. All four Week 1 tasks complete. Track B is
unblocked (Task 2 gate passed). One Harry ruling needed, one Harry action item.

## Task 0 — Chart source verdict: LOCAL PDF (verified working)

- Equibase scraping is dead: both chartEmbed and static-summary endpoints
  return Incapsula bot-challenge pages. HRN returns a JS shell with no payoff
  data. Neither is usable.
- **Verified source: the Equibase full-card chart PDFs Harry already downloads**
  (`Results/2026/<date><track>USA0.pdf`). `pdftotext -layout` extraction is
  clean and complete: official finish order, final tote odds per starter,
  full mutuel block with denominations, scratches, carryovers.
- `--txt` flag accepts pasted/pre-extracted chart text as the fallback path.
- **Harry action: download SAR chart PDFs** (none in hand — see coverage).

## Task 1 — Schema + ingestion: SHIPPED

Tables created: `race_payoffs` (UNIQUE(race_id,pool,combination), is_refund,
carryovers, denomination NOT NULL), `race_finish_order` (UNIQUE(race_id,
horse_pgm), nullable finish_position for scratches, coupled/DQ columns),
`exotic_tickets` (Week 3 consumer); `races` gained field_size_post,
has_coupled_entry. `Claude/r5_payoffs.py` ingests per race with
delete-then-insert.

Gates passed:
- **Idempotency: re-ingesting CDX 0529 left row counts identical (106/83).**
- WIN-payoff cross-check vs logged `picks.sp_odds`: zero mismatches across
  all ingested cards (after fixing two parser bugs: winner's WPS line sits
  above the "$2 Mutuel Prices:" marker; dead-heat marker glyph broke names).
- Dead heat verified on CDX 0530 R3 (both show payoffs captured, flagged).
- Scratch rows verified (NULL position, name→pgm mapped via picks; 15 of 44
  scratch names unmapped → stored as SCRn, they pre-date the DRF analysis).

**Backfill (Task 6B pulled forward): 125 of 179 DB races now carry full
payoffs + finish order + final odds** (1,432 payoff rows, 1,062 finish rows)
across CDX/BAQ/LRL/SAX including Derby day. Remaining: 49 SAR races (charts
not in hand), CDX 0502 R13–14, BAQ 0509 R11, LRL 0516 R14 (absent from PDFs).

Untested code paths (zero real instances in 125 races): coupled entries (1/1A),
DQ handling. Both flagged for first live occurrence.

## Task 2 — Tight-cluster reconstruction: GATE PASSED, FINDING REVERSED

- **Deduction status: still ACTIVE in live code** (`r5_parser_v2.py:453`)
  despite docs saying suspended → **[HARRY RULING] reconcile docs vs code.**
  Per brief, code untouched.
- Version coverage: no version column exists; empirical break is clean —
  607 picks ≤ 05/16 are pre-v3.5 (NULL pp_n/best_dist_n, no deduction
  possible), 1,140 picks ≥ 05/21 on the current formula.
- **Epsilon gate: 0 unexplained deltas** (1,048 clean / 59 equipment-adj /
  33 fired). equipment_adj is unlogged; delta classification separated it
  cleanly from the −0.40 deduction as designed.
- Spread test run on reconstructed pre-deduction comps (circularity handled);
  all 33 fired races passed structural verification.
- `pre_tight_comp` + `tight_cluster_severe` populated for all 1,747 picks.

**Exact re-validation REVERSES the approximate analysis** (which suggested
the deduction was backwards):

| In the 33 fired races | Bets | Wins | Win% | ROI |
|---|---|---|---|---|
| Bet POST-deduction top (what the rule produced) | 27 | 7 | 25.9% | **−1.3%** |
| Bet PRE-deduction top (the demoted horse) | 25 | 5 | 20.0% | −43.3% |
| Unfired races rank-1 baseline (same period) | 69 | 14 | 20.3% | −47.8% |

The deduction's rank-swap has been *helping*: fired-race post-deduction
rank-1 is the least-bad rank-1 environment in the post-0516 DB. n=33 — small,
but exact. The approximate analysis in SIGNAL_VALIDATION_20260611.md is
superseded on this point.

## Task 3 — Queries

**Query A — contender set union: GO.** R5 ranks 1–3 ∪ CM ranks 1–2 captures
the winner in **107/160 = 66.9%** vs R5-top-3-only 95/160 = 59.4% (exactly
reproducing the baseline figure — join validated). **+7.5 points clears the
≥3-point gate: CM legs stay in the contender set.** Mean union size 3.6 horses.

**Query B — W/P/S by rank** (n = 156/154/151):

| Rank | Win% | Top-2% | Top-3% |
|---|---|---|---|
| 1 | 23.1 | 40.4 | 56.4 |
| 2 | 15.6 | 34.4 | 42.9 |
| 3 | 23.2 | 35.1 | 47.7 |

Rank-3 beats rank-2 on every metric — supports rank-3 in both top and
underneath roles in Week 3 structure construction; rank-2 is the weakest leg.

## Blockers / rulings needed

1. **[HARRY RULING]** Tight-cluster deduction: docs say suspended, code is
   active, exact data now says it helps (−1.3% vs −47.8% baseline). Options:
   leave active + update docs (no code change), or disable (scoring change,
   version bump). Recommend: leave active, document in v3.10 spec refresh.
2. **[HARRY ACTION]** Download SAR chart PDFs (06/03–06/06, and ongoing) into
   `Results/2026/` so SAR backfill + Week 3 dry-run settlement can run.
3. Nothing blocks Week 2 (Track B): Task 2 gate passed; comp_ex_val backfill
   will cover the 1,140 current-formula picks (607 pre-v3.5 picks lack
   components — they'll be reported as non-backfillable, as the brief requires).
