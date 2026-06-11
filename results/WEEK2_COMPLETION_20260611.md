# Session 2 — Week 2 Completion Report (2026-06-11)

Per `Prompts/SESSION2_BRIEF.md`. Tasks 4, 5, 6, 6B complete. Probability layer
is live in output and DB. One ruling already applied (tight-cluster docs),
one new calibration finding for Harry's attention, one chart still missing.

## Task 6B — SAR backfill + tight-cluster docs: DONE

- SAR 06/03–05 ingested: 35 races. **Coverage now 160/179 DB races** with
  full payoffs, finish order, final tote odds.
- `20260607SARUSA0.pdf` is genuinely June 7 (card not yet analyzed — will
  auto-ingest once logged). **The 06/06 chart is the one missing** (14 DB
  races) → **[HARRY ACTION] download `20260606SARUSA0.pdf`.**
- Tight-cluster ruling applied: R5_PROJECT_STATE.md, R5_SPEC.md, and
  CORRECTED_BASELINE updated to ACTIVE/CONFIRMED with the exact numbers.
  No code change.

## Task 4 — comp_ex_val: DONE

- `compute_comp_ex_val()` in r5_parser_v2.py; weights renormalized by exact
  division by 0.95 from the new `COMP_WEIGHTS` single source of truth.
  Excludes val_n, scout/equipment adjustments, and the deduction by
  construction.
- **Backfilled: 1,140 rows. NOT backfillable: 607** (pre-v3.5, missing
  pp_n/best_dist_n — these drop out of the fit, counted as required).
- Range sane: 1.85–8.26, mean 4.34.
- Runtime: finalize_field computes it; log_race_picks persists it (plus
  pre_tight_comp / tight_cluster_severe) for all future races.

## Task 5 — Conditional logit P(win): DONE

- **β = 0.7674** | LL = −192.08 | **97 fit races** | 62 dropped (winner
  lacks comp_ex_val — the pre-v3.5 universe).
- **Deviation from brief:** scipy is not installed and the engine deliberately
  has minimal deps; the MLE is solved by Newton's method with analytic
  gradient/Hessian (the NLL is convex in β — identical optimum, convergence
  to |step| < 1e-10). scipy can be swapped in later if preferred.
- 1,072 historical picks scored (p_win/fair_odds/ml_edge/is_overlay).
- β serialized to `Results/logit_beta.json` with metadata.

### Calibration (Results/CALIBRATION_REPORT_20260611.md)

Deciles broadly monotone (2.5%→0.0% at the bottom, 28.8%→24.4% at the top).
Mid-deciles noisy at n=89/bin, as expected at this sample size.

**Rank-3 diagnostic (the mandatory 1B check): predicted 14.4% vs observed
22.8%.** Exactly the tension Decision 1B predicted — comp under-separates
the top-3 while the market prices rank-3 long. Reported, not tuned, per spec.
Rank-1: predicted 25.1% vs observed 21.9% (mild overprediction).

### ⚠️ Calibration anomaly for Harry

**The overlay rule applied retroactively to ML odds loses badly: 133 flags,
16 wins, −46.3% ROI in-sample.** The ▲OVERLAY flag as currently computed
(vs stale morning line) is a money-loser — this is empirical confirmation
that ruling 4 (advisory-only) is correct and that no overlay betting should
be considered until the final-odds retro-test runs (P × (final_odds+1) ≥ 1.25
against the 160 races of captured final tote odds — now possible, scheduled
in-meet per the brief; can be pulled into Week 3 if desired).

### val_n_tracker: DONE, gates demonstrated

- Table created (UNIQUE(pick_id), no cumulative column — stop state computed
  from SUM(profit) at decision time).
- Enforcement is code in the logging path. Demonstrated live: two live bets
  accepted on SAR 06/05, third **REFUSED — "2 live bets already on SAR
  20260605; logged as paper"** (test rows then removed). Hard-stop conditions
  (0-in-30, −$60) use the same gate.
- `settle_val_bets()` settles from pick results on the corrected convention.

## Task 6 — Output revamp: DONE (engine + webapp in lockstep)

Sample (SAR 06/05 R5, live output):

```
  🏇  R5 v3.10 — SAR  Race 5  |  20260605  |  5.5f  T  |  Purse $120,000  |  Par 87  |  HOT PACE (11 speed)
  R5 | top-3 cum P(win) 47% | spread(r1−r3) 0.85 DEFAULT
====================================================================
#    Horse              ML   ...   Val   Comp  P(win)    Fair    Edge
7    DI NATALE         2-1   ...   5.0   6.22     22%   3.5-1    -33%
15   SHEER WILL        2-1   ...   5.0   5.69     15%   5.9-1    -49%
...
🏆  TOP WIN PICK:  #7 DI NATALE  [2-1 ML]  |  Composite 6.22  |  P(win) 22%  |  fair 3.5-1  |  edge -33%
```

- Tier ladder deleted from: report table, TOP WIN PICK, VALUE ALT,
  CONFIDENCE TIERS section (removed), scratch notices, webapp badges,
  webapp analytics. PLAY/NEAR/SKIP verdict deleted, not relabeled — the
  webapp's `calcBetRec` (tier points + comp≥6.0 gate + CM agreement boost,
  all retired signals) replaced by a P(win)/fair/edge card with context notes.
- ▲OVERLAY only at edge ≥ +25% AND P ≥ 8%, always footnoted
  "vs morning line — advisory until live odds".
- ◆ VAL WATCH on val_n ≥ 8 horses with the guardrail footnote.
- Webapp parser updated to the new fixed-width columns (positions verified
  programmatically) + new race-header line; parse test passed on a full
  SAR 06/05 card (11 races, all fields populated).
- **Bonus fix:** webapp analytics still used the pre-remediation ROI formula
  ($2 payoffs vs $1 stakes — the exact audited bug, live in the val_roi
  panel). Corrected to the $2-flat convention; tier panel replaced by
  Win%/ROI-by-rank (corrected) chart.

## Items for Harry

1. **[ACTION]** Download `20260606SARUSA0.pdf` → Results/2026/ (14 races,
   last backfill gap).
2. **[FYI]** Overlay-vs-ML retro result above — supports keeping ruling 4
   strict. Final-odds overlay retro-test can run any time now that final
   odds are captured; recommend pulling it into Week 3.
3. **[FYI]** scipy deviation in Task 5 (Newton MLE, mathematically identical).

## Week 3 readiness

- Track A: settlement test data ready (160 races with payoffs).
- Track B: complete. Exotics module (Task 7) has everything it needs:
  contender set queries validated (66.9% union), structure shape already
  computed in the header, P(win) live, exotic_tickets table exists.
