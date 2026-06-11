# Session 2 — Week 3 Completion Report (2026-06-11)

All Week 3 tasks complete, plus the two Harry-ordered additions. The full
pipeline is live end-to-end **19 days ahead of the June 30 freeze**. One
major ruling outcome below.

## Harry addition 1 — Final-odds overlay retro-test: **LIVE OVERLAY BETTING NOT AUTHORIZED**

Rule P(win) × (final_odds+1) ≥ 1.25 AND P ≥ 0.08, tested on 758 scored
runners with captured final tote odds (115 races):

| threshold | bets | wins | win% | ROI |
|---|---|---|---|---|
| 1.10 | 167 | 13 | 7.8% | −53.0% |
| **1.25 (rule)** | **142** | **10** | **7.0%** | **−56.9%** |
| 1.40 | 122 | 8 | 6.6% | −57.8% |
| 1.60 | 92 | 5 | 5.4% | −64.7% |

Monotone deterioration with threshold; 77 of 142 qualifiers are rank-4+
horses at avg 17-1. The selector harvests favorite-longshot bias, not edge —
and this is *with* in-sample β and hindsight odds favoring it. **Verdict:
overlay flags stay advisory/diagnostic; no live overlay win bets at
Saratoga.** Full doc: `Results/OVERLAY_RETROTEST_20260611.md`. Revisit only
after the n≥300 decorrelated calibration upgrade, paper-first.

This closes the loop on the project's central lesson: every win-bet angle —
tiers, gates, consensus, agreement, stacking, and now model-vs-market
overlays — fails corrected ROI. The edge search lives entirely in exotics
structure, which is where the rest of Week 3 went.

## Harry addition 2 — SAR 06/06 ingested

14 races. **Backfill coverage final: 174/179** (remaining 5 races absent
from their chart PDFs: CDX 0502 R13–14, BAQ 0509 R11, LRL 0516 R14, +1).

## Task 7 — Exotics module: SHIPPED (`Claude/r5_exotics.py`)

- **Settlement self-test gate PASSED** — hand-computed expectations vs real
  ingested CDX 0529 R1 payoffs ($1 EX box: collected $94.93 = $189.86 × 1/2;
  $0.50 TRI key: $253.42 at matching denomination). Settlement refuses to
  run until this passes, every time.
- **STANDOUT cap test PASSED** — forced 5-horse-underneath case prices at
  $15 pre-trim, trims the TRI third leg to land at $11 ≤ $12. Trim order:
  TRI legs → rank-3 key; primary EX never dropped.
- Contender set with all 2A triggers (field ≤5 PASS fired on SAR 0605
  R10/R12; CM-leg trim; PP-underline underneath-only; class_n=0.0 as the
  debut proxy for DB-driven generation).
- `--live` is the only path to is_paper=0; paper always default; paper
  regeneration idempotent (unsettled paper tickets replaced).
- Scratch/refund rules verified on real data: partial box refunds, full
  TRI-box refund when a box horse scratches, key-scratch full refund.
- One combo enumerator prices tickets AND settles them — cost and
  settlement cannot disagree.

### Paper results, 4 SAR cards (70 settled tickets)

| shape · type | n | staked | P/L | ROI |
|---|---|---|---|---|
| TIGHT TRI box | 15 | $45 | +$173.10 | +384.7% |
| TIGHT EX box | 15 | $90 | +$77.91 | +86.6% |
| DEFAULT EX box | 27 | $162 | −$56.90 | −35.1% |
| STANDOUT EX/TRI key | 10 | $21 | −$21.00 | −100% |
| TIGHT EX key (r3) | 3 | $6 | −$4.00 | −66.7% |
| **Total** | **70** | **$324** | **+$169.11** | **+52.2%** |

Read with discipline: positive total is carried by two TRI hits ($160.78,
$51.32); STANDOUT keys are 0-for-10. Directionally consistent with the
tight-cluster finding (box tight races), but **n=4 cards is anecdote — the
n≥40-race structure review gate stands** before anything graduates beyond
the $12 paper/live-token regime.

## Task 8 — R5_SPEC v3.10: COMMITTED

Full rewrite: v3.10 weights (class 20% per ruling), post-composite
adjustment order, tight-cluster ACTIVE/CONFIRMED, P(win) layer + val_n ban,
tier retirement, overlay non-authorization, exotics menu + $12 cap + trim
order, val_n tracker guardrails, payoff capture, weight freeze, version
history.

## Task 9 — Dry run: CLEAN

SAR 0606 end-to-end: run_r5 full card (0 errors, new format throughout) →
ticket generation (all three shapes, TIGHT triple-menu at $11 under cap) →
ingestion → settlement (hits, misses, and mixed refund cases all correct).
Feature freeze available from today; June 30 freeze date now has 19 days
of slack for SAR June paper accumulation.

## Open items / in-meet checkpoints (handed off)

1. **SAR-only β refit comparison at n≥60 SAR races** (~2 weeks into meet).
2. **Structure-menu ROI review at n≥40 SAR races with payoffs** — decides
   what stays in the menu; watch DEFAULT EX box (−35.1%) and STANDOUT keys
   (0-for-10) specifically.
3. **val_n ≥8 re-decision at n≥120 qualifying bets** (tracker live with
   guardrails from day 1).
4. **CM merge-or-keep decision at n≥100 SAR races** (CM legs currently
   earn their place: +7.5pts capture).
5. **Live odds capture build (mid-July)** — required for any future overlay
   reconsideration and for live-tote exotics pricing.
6. Overlay reconsideration: blocked on calibration upgrade (n≥300,
   decorrelated speed cluster) + out-of-sample evidence; paper-first.
7. 5 unbackfilled races (chart PDFs lack those races) — ignore or source
   alternate charts.
8. Coupled-entry and DQ ingestion paths: written, zero real instances yet —
   verify on first live occurrence at SAR.

## Final delivery state vs brief

- ✅ All schema migrated + verified (idempotency, epsilon, selftest gates)
- ✅ P(win) layer live in report + webapp + DB
- ✅ Exotics paper-tracking live from day 1; live mode Harry-flag-gated
- ✅ val_n ≥8 tracker active, guardrails enforced in code
- ✅ R5_SPEC.md at v3.10
- ✅ Dry run clean on SAR cards
- ✅ Overlay retro-test run → live win-bet overlay NOT authorized
