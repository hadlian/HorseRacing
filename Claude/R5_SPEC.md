# R5 Model Specification

**Version:** R5_v3.10
**Current executable implementation:** `r5_parser_v2.py` (+ `r5_probability.py`, `r5_exotics.py`)
**Weight status: FROZEN through the Saratoga 2026 meet (Harry ruling, 2026-06-11).**

---

## Model Integrity Rules

1. `R5_SPEC.md` defines the approved model version.
2. `r5_parser_v2.py` is the current executable implementation of R5_v3.10.
3. If this document and the code disagree, treat it as a model-control conflict. Do not proceed with changes until the human steward resolves it.
4. No scoring logic (WS4, Trend, FCI, Composite weights) may be changed without an explicit version bump and approval.
5. Documentation updates do not require a version bump. Logic changes do.
6. The version string in this file must be updated whenever scoring behavior changes.

---

## WS4 — Weighted Speed Figure

Weighted average of the last 4 BRIS speed figures on the **same surface as today's race**.

```
WS4 = 0.4×S1 + 0.3×S2 + 0.2×S3 + 0.1×S4
```

- Weights re-normalised if fewer than 4 figures are available.
- If fewer than 2 same-surface figures exist, falls back to valid BRIS figures regardless of surface.

## Trend — Continuous Form Direction

```
Trend = round(clamp((S1 - Avg(S2..S4)) / 2.0, -5.0, +5.0), 1)
```

## FCI — Form/Class Index

```
FCI   = WS4 + Trend
fci_n = par-anchored normalization to 0–10 (v3.6)
```

---

## Composite Score — v3.10 weights (code is authoritative; `COMP_WEIGHTS` in r5_parser_v2.py)

| Component | Weight | Field | Notes |
|-----------|--------|-------|-------|
| FCI | 22% | `fci_n` | |
| Class vs Speed Par | **20%** | `class_n` | Harry-confirmed 2026-06-11 (v3.5's documented "13%" was never implemented; code rules) |
| Trainer/Jockey | 15% | `tj_n` | shipped v3.5 |
| Form Angle | 10% | `form_n` | |
| Bias / Pace Fit | 8% | `bias_n` | 50/50 post score / pace fit |
| Best Distance Speed | 8% | `best_dist_n` | turf uses best_turf (v3.6) |
| Pedigree | 7% | `ped_n` | |
| Prime Power | 5% | `pp_n` | anchor 125, debut fallback 4.0 (v3.10) |
| Value vs ML | 5% | `val_n` | rank divergence, floored at 5.0 |

Post-composite adjustments, in order: equipment (v3.8: +0.20 1st Lasix,
+0.10 blinkers on, −0.05 blinkers off) → scout (±0.40 cap) → tight-cluster
deduction (below).

### Tight-Cluster Deduction — ACTIVE, CONFIRMED (Harry ruling 2026-06-11)

When the top-3 composite spread ≤ 0.5, the pre-deduction top horse takes
−0.40 (often swapping Rank 1↔2). Exact reconstruction from logged component
vectors (0 unexplained deltas / 1,747 picks) validated it on corrected ROI:
post-deduction rank-1 = 25.9% win / −1.3% ROI in 33 fired races vs the
demoted horse's 20.0% / −43.3%. Fired state persists per pick
(`pre_tight_comp`, `tight_cluster_severe`).

---

## P(win) Layer (Session 2, Decision 1 — `r5_probability.py`)

```
comp_ex_val = Σ (component × weight/0.95) over the 8 non-val components
P(win)_i    = exp(β·comp_ex_val_i) / Σ_j exp(β·comp_ex_val_j)   per race
fair_odds   = 1/P − 1
edge        = P × (ML + 1) − 1
```

- **val_n is PERMANENTLY BANNED from P(win)** — it is market-relative;
  market information lives only on the odds side of the overlay comparison.
- comp_ex_val also excludes scout/equipment adjustments and the deduction
  by construction (pure component recomputation).
- One parameter (β), conditional-logit MLE over races with known winners.
  Current fit: β = 0.7674 on 97 races (`Results/logit_beta.json`).
  Refit cadence: SAR-only β comparison at n≥60 SAR races.
- **OVERLAY flag** (edge ≥ +25% AND P ≥ 8%) is **ADVISORY ONLY**: the
  final-odds retro-test (2026-06-11) returned −56.9% ROI on 142 qualifying
  bets — live overlay win betting is NOT authorized
  (`Results/OVERLAY_RETROTEST_20260611.md`).

## Confidence Tiers — RETIRED (2026-06-11)

The HIGH/SOLID/FAIR/SPEC ladder is removed from all output (HIGH fired 0
times in 160 races; FAIR rank-1 ran −70.2% ROI). The user-facing confidence
display is P(win) / fair odds / edge plus the per-race header
(top-3 cumulative P(win), spread, race shape). The PLAY/NEAR/SKIP verdict
is deleted, not relabeled.

## val_n ≥ 8 Tracker (Harry ruling 3)

Live with coded guardrails: flat $2, max 2 live bets per card, hard stop at
0 wins in 30 settled bets OR cumulative SUM(profit) < −$60, evaluated at
decision time in the bet-logging path (`val_n_tracker` table; refused live
bets are logged as paper). Re-decision gate: n≥120 qualifying bets.

---

## Exotics Module (Session 2, Decision 2 — `r5_exotics.py`)

- **Contender set:** R5 ranks 1–3 ∪ CM ranks 1–2 (winner capture 66.9% vs
  59.4% R5-only), capped at 5; PP-underline horse added underneath-only.
  Triggers: field ≤5 post-scratch → PASS; ≥2 debuts in set → exacta-only;
  oversize → CM legs trimmed first.
- **Structure menu** (spread on final comp): TIGHT (r1−r3 ≤ 0.5) → $1 EX box
  + $0.50 TRI box + $1 EX key r3-over-r1,r2 when r3 ML ≥ 6-1; STANDOUT
  (r1−r2 ≥ 1.0) → $1 EX key r1/set + $0.50 TRI key r1/set/set+PP; else $1 EX
  box. Superfecta: categorical PASS until payoff-validated.
- **$12/race cap** (Harry ruling 2); trim drop order: TRI legs → rank-3 key;
  the primary EX is never dropped.
- **Paper by default, always.** Live only via explicit per-session `--live`
  flag (Harry controls); never inferred. Settlement is gated on a
  hand-computed self-test vs real chart payoffs and uses explicit
  denomination scaling: `collected = quoted × (ticket_denom / payoff_denom)`.
- Structure-menu ROI review gate: **n≥40 SAR races with payoffs**.

## Data Capture (`r5_payoffs.py`)

Equibase chart PDFs (local, `Results/2026/`) → `race_payoffs` (all pools,
denominations, dead heats, refunds, carryovers) + `race_finish_order`
(official order, final tote odds, scratches, coupled entries). Idempotent
per-race delete-then-insert. Multi-race pools keyed to the ending leg.

---

## Version History

| Version | Change |
|---------|--------|
| R5_v3.10 | pp_n anchor 130→125, debut fallback 5.0→4.0; Session 2: P(win) layer, tier retirement, exotics module, payoff capture (no scoring change) |
| R5_v3.9 | Code-review fixes + scout-before-finalize architecture |
| R5_v3.8 | 1st-Lasix/equipment adjustments |
| R5_v3.7 | Tight-cluster deduction (ACTIVE, confirmed 2026-06-11); Scout-3 AE fix |
| R5_v3.6 | Par-anchored fci_n; surface-aware best_dist_n |
| R5_v3.5 | pp_n + best_dist_n components; TJ 15%; weight vector above |
| R5_v3.3 | Maiden/firster class fix: class_n=0.0 + [DEBUT] flag |
| R5_v3.2-R4C | Continuous Trend formalised |
| R5_v3.1 | Two-pass finalize_field(); pace scenario; value as rank divergence |
| R5_v3.0 | Initial r5_parser_v2.py |
