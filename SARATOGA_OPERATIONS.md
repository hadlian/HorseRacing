# Saratoga 2026 — Operations Guide

> **R5 v3.10 — Feature-frozen for the meet**
> Saratoga opens July 3, 2026. This guide covers every step from race-morning DRF download
> through post-race settlement. Keep this file at the top level; refer to it on opening day.

---

## Pre-Race Workflow (Race Morning)

### 1. Download the DRF
- Place the unzipped `.DRF` file in `~/Documents/RacingData/files 2/` (e.g. `RacingData/files 2/SAR0703.DRF`) — the shared read-only input folder
- Naming convention: `SAR` + `MMDD` + `.DRF`
- The CLI resolves a bare filename (e.g. `SAR0703.DRF`) against that folder via `Claude/r5_paths.py`

### 2. Run all three models (one command)

```bash
source venv/bin/activate
python3 Claude/r5_card_cli.py "files 2/SAR0703.DRF"
```

Runs R5 (`--save --track`), then CM `log`, then CM1 `--log` — all three models on the
card in one shot. Pass-through flags: `--wet`, `--auto-scout`, `--pdf`, `--live`;
historical cards need `--year`/`--backtest`. If run_r5 refuses (settled-card guard),
the chain stops so the three model DBs never drift out of sync.
The individual commands below remain for debugging one stage.

**R5 only, normal track:**
```bash
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --save --track
```

**Off-track day (muddy, sloppy, wet):**
```bash
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --wet --save --track
```

**With pre-race intel (optional; requires ANTHROPIC_API_KEY):**
```bash
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --auto-scout --save --track
```

Output is saved to `Results/TXT_Files/SAR0703_R5.txt` (use `--save`). Picks are logged to the DB (use `--track`). Both flags should be standard on every card.

### 3. Generate exotics (paper mode — default)
```bash
python3 Claude/r5_exotics.py --track SAR --date 20260703
```

Paper mode is the default. No real money is committed. Review the ticket printout before deciding whether to go live.

### 4. Go live (Harry discretion — $12 cap)
```bash
python3 Claude/r5_exotics.py --track SAR --date 20260703 --live
```

The `--live` flag is the only path to `is_paper=0`. This cannot be triggered accidentally. Hard cap is $12 per race regardless of structure; trim order: TRI third leg → rank-3 key; primary EX never dropped.

---

## How to Read the Output

### Race header
```
SAR R5  1m Turf  $85k Allowance  10 starters  Par 113
pace profile 3E/EP vs 6P/S    TIGHT SPEED CLUSTER
```
- **Par:** expected BRIS figure for a winner at this class/distance. Horses below par are at a disadvantage.
- **pace profile:** count of early (E/EP) vs late (P/S) runners by run style. E-heavy fields favour closers; S-heavy fields favour early.
- **TIGHT SPEED CLUSTER:** top-3 spread ≤ 0.5 pts. −0.40 deduction applied to the pre-deduction leader. Box the top 3 for exotics.

### Horse table
```
# | Horse (style)              | ML   | Q | WS4 | Trnd | FCI | vPar | Ped | T/J | Pce | Val | Comp | P(win)
```

| Column | Meaning |
|--------|---------|
| `style` | Run style in parentheses: E (early speed), E/P (pressing speed), P (presser), S (closer) |
| `ML` | Morning line odds |
| `Q` | Quirin speed points 0–8 (higher = more early acceleration) |
| `Comp` | R5 composite score (0–10) |
| `P(win)` | Probability of winning this race (%) |
| `[LAYOFF 45+]` | Horse hasn't run in 45–89 days |
| `[LAYOFF 90+]` | 90–179 days off |
| `[LAYOFF 180+]` | 6+ months off — note for trainer angles |

### Top-pick block
```
━━━ TOP WIN PICK ━━━
#4 INCENTIVE PAY   Comp 6.84   P(WIN): 31.2%   FAIR ODDS: 2.2-1   ML: 5-2
EDGE: +0.08   ← advisory only (not authorized for live win betting)
```

- **P(win):** Model's probability the horse wins this race.
- **fair_odds:** The price you'd need to break even at this probability.
- **EDGE:** `P(win) × (final_odds + 1) − 1`. Positive = model thinks the horse is underbet.
- **OVERLAY advisory:** If edge ≥ 0.25 AND P ≥ 0.08, an OVERLAY flag prints. This is diagnostic only — see OVERLAY section below.

### VAL WATCH
```
VAL WATCH: #8 SENIOR OFFICER — val_n=8.4   (flat $2 only, max 2/card, guardrails apply)
```
val_n ≥ 8 is on watch as a potential live bet signal (+41.8% ROI on 4 wins — gradient is right but sample is thin). Run under guardrails: flat $2, max 2 per card, hard stops at 0-for-30 or −$60 SUM. See guardrail rules below.

### TRAINER ANGLES section
```
TRAINER ANGLES — R5 contenders (ranks 1-3)
#4 INCENTIVE PAY (rank 1, 176d off)
   ↻ Trainer off layoff (45-179d): 3-for-12 (25%)   ← LAYOFF MATCH
#8 SENIOR OFFICER (rank 2)
   ↻ Trainer w/ dirt sprinters: 8-for-31 (26%)
```

`← LAYOFF MATCH` fires when a horse is ≥45 days off and the trainer has a named category for that situation. `← DEBUT MATCH` fires on first-time starters with a trainer who fires in maiden debuts.

---

## Exotics Workflow

### Contender set (auto-built)
R5 ranks 1–3 ∪ CM ranks 1–2. Captures winner in 66.9% of races. CM adds ~7.5pp to capture rate. Set is printed in the exotics output.

### Structure call
| Shape | Trigger | Tickets |
|-------|---------|---------|
| **TIGHT** | Top-3 spread ≤ 0.5 | EX box (r1+r2+r3) + TRI box (r1+r2+r3) + r3 key on top if ML ≥ 6-1 |
| **STANDOUT** | r1−r2 spread ≥ 1.0 | EX key (r1 over set) + TRI key (r1 over set) |
| **DEFAULT** | All other cases | EX box (r1+r2) |

**TIGHT is the best-performing shape** (4 SAR cards: EX box +86.6%, TRI box +384.7%). STANDOUT keys are 0-for-10 on the same data — watch carefully. DEFAULT EX box is −35.1%.

### Ticket cost
```
python3 Claude/r5_exotics.py --track SAR --date 20260703
```
The output prints each ticket with its cost. If any single race would exceed $12, trim fires automatically (TRI third leg reduced before any other cut).

### LONE_E_NOTE (data collection only)
When rank-1 or rank-2 is the sole E-style horse with Q≥6 in a TIGHT race, a zero-cost LONE_E_NOTE row is logged. This does **not** generate a ticket or cost money. It tracks whether lone early speed wins in tight races at Saratoga — useful for the n≥40 structure review.

---

## Wet Track Workflow

```bash
python3 Claude/run_r5.py "files 2/SAR0703.DRF" --wet --save --track
```

With `--wet`, the report adds a wet-track block after the standard output:

```
── OFF-TRACK CONDITIONS ──────────────────────────────────────
#4 INCENTIVE PAY   WET: 2-for-5 (40%), best off-track 101
#8 SENIOR OFFICER   WET: 0-for-1, best off-track 95
#1 TIDAL FORCE   WET: no wet starts (first off-track)
```

Track condition is NOT in the DRF — always supply `--wet` based on race-day track condition reported by the track (Saratoga's track superintendent posts updates before first post).

Wet stats are always parsed and logged regardless of the flag; `--wet` only controls whether the block prints.

---

## val_n Guardrail Rules

val_n ≥ 8 is approved as a live tracker signal with hard stops. Rules apply at the moment of logging — there is no running total stored between sessions. The DB is re-evaluated each time.

| Rule | Threshold |
|------|-----------|
| Flat bet | $2 WIN only (no size-up) |
| Card limit | Max 2 val_n bets per card |
| Win drought stop | 0 wins in last 30 settled val_n bets |
| Loss limit stop | SUM(profit) < −$60 on all settled val_n bets |

When any stop condition is met, `log_val_bet()` refuses and prints the reason. Do not override manually. Re-evaluate at n≥120 qualifying bets.

Current state: 4 wins at ≥8 (n too small to assess). The gradient is correct (≥8 > ≥7 > ≥6 at every level). Bet if the guardrails allow it.

---

## Post-Race Workflow

### 1. Download chart PDF
From Equibase, download the full-card chart for the race day:
`Results/2026/20260703SARUSA0.pdf`

### 2. Run the full pipeline (one command)
```bash
python3 Claude/r5_results_cli.py Results/2026/20260703SARUSA0.pdf
```
Track/date are derived from the Equibase filename; pass `TRACK YYYYMMDD` before the
PDF only if the filename is non-standard.

This runs everything below (steps 2–6) in order: payoffs ingest + pick reconcile,
finalize scratches, settle exotics (+ post-scratch A/B), CM results/finalize,
paper trackers, summary, and docs (CM1 compare + analysis workbook; `--no-docs` skips).
Idempotent — safe to re-run. The individual steps below remain for debugging one stage.

### 2a. Ingest payoffs (manual fallback)
```bash
python3 Claude/r5_payoffs.py --track SAR --date 20260703 --pdf Results/2026/20260703SARUSA0.pdf
```

This is idempotent — safe to re-run. Populates `race_payoffs`, `race_finish_order`. Final tote odds per starter are captured here.

### 3. Load results
```bash
# Auto-fetch (if available):
python3 Claude/r5_tracker.py --fetch SAR 20260703

# Manual:
python3 Claude/r5_tracker.py --manual SAR 20260703 5 "3,11,5,7" 6.20
```

### 4. Finalize late scratches
```bash
python3 Claude/r5_tracker.py --finalize SAR 20260703
```

Any pick still NULL after result entry = late scratch → auto-set to `finish_pos=-1`.

### 5. Settle tickets
```bash
python3 Claude/r5_exotics.py --settle SAR 20260703
```

Prints settled P/L per race and total card. Settlement is gated on the self-test passing (verifies against real CDX 0529 R1 payoffs — runs automatically).

### 6. Weekly analysis
```bash
python3 Claude/r5_analyze.py
```

Excel workbook in `Results/`. Includes P/L by structure shape at n≥40 for the checkpoint review.

---

## OVERLAY Advisory — What It Means

The OVERLAY flag fires when `P(win) × (final_odds + 1) ≥ 1.25 AND P ≥ 0.08`.

**OVERLAY does NOT mean bet the horse.** Live overlay win betting was retro-tested on 142 qualifying bets (in-sample β + hindsight final odds): −56.9% ROI. The one-parameter logit overestimates longshots where the market knows better — 77 of the 142 qualifiers were rank-4+ horses at avg 17-1.

**Use the OVERLAY flag for:**
- Understanding why the model diverges from the market
- Exotic structure consideration (not a win bet trigger)
- Data collection for the n≥300 calibration upgrade

**Do not place live win bets on OVERLAY horses.** This ruling holds until the decorrelated P(win) model is built (n≥300) and tested paper-first.

---

## CM Divergence Flag — What It Means

When R5 and CM disagree (pick different horses), the R5 leg at −12.8% ROI is the best relative leg in the divergence set — not positive, but less bad. The CM leg in disagreements is −21.3%.

**Divergence ≠ bet signal.** Use it as:
- A note that the market may be pricing something R5 is missing (investigate the CM horse)
- Context for contender set construction (both horses stay in the exotic set)
- A flag that the race is contested (CM disagreement = R5 may have less information)

**Agreement is NOT a confidence booster.** R5+CM agreement has the highest win rate (32.2%) and the worst ROI (−22.9%) of any filter tested — it's a chalk trap. Don't increase bet size on agreement.

---

## In-Meet Checkpoint Schedule

All checkpoints are data-driven — no changes before the gate, no exceptions.

| Gate | Date (approx) | Decision |
|------|--------------|----------|
| SAR n≥40 payoff races | ~mid-July | Structure menu ROI review. Watches: DEFAULT EX box (−35.1%), STANDOUT keys (0-for-10). Retire a shape if it's still deeply negative at n=40. |
| SAR n≥60 races | ~late July | β refit (SAR-only conditional logit). tj_n year-stats fallback rerun (`scripts/tj_fallback_backtest.py`). If SAR win rate improves under year-stats: bring to ruling as v3.11. |
| SAR n≥100 races | ~mid-August | CM merge-or-keep. If CM legs add <+3pp capture: propose removing them. If still +7pp: keep. |
| val_n n≥120 bets | ~August | val_n ≥8 re-decision. Adjust threshold? Widen rank filter? Assess guardrail performance. |
| Mid-July | Specific date TBD | Live odds capture build (Issue 16). Required before any overlay reconsideration. |
| n≥300 total races | End of meet or 2027 | Decorrelated P(win) upgrade. Overlay reconsideration paper-first. |

---

## Emergency Reference

| Problem | Fix |
|---------|-----|
| DRF won't parse | Check file is unzipped `.DRF`; verify it's in `files 2/`; check track code |
| val_n guardrail fires | Do not override — it means a stop condition was hit. Check DB for reason. |
| Exotics ticket cost over $12 | Trim fires automatically — review which ticket was trimmed before logging |
| Settlement self-test fails | DO NOT settle. Report to Harry. Check if CDX 0529 payoffs were corrupted in DB. |
| Coupled entry in exotics | First Saratoga occurrence — verify pgm normalization (base_pgm strips letter suffix) |
| DQ in results | Flag `is_dq=1` in race_finish_order; DQ horse goes to last, payoffs from official chart |
| Chart PDF missing races | 5 races in current DB have no chart data. These are unresolvable — mark manually. |

---

## File Quick Reference

| Need | File |
|------|------|
| Run a card | `Claude/run_r5.py` |
| Generate exotics | `Claude/r5_exotics.py` |
| Ingest a chart PDF | `Claude/r5_payoffs.py` |
| Load results | `Claude/r5_tracker.py` |
| View analytics | `Claude/r5_analyze.py` → Excel |
| Web UI | `webapp/app.py` → localhost:5050 |
| Full spec | `Claude/R5_SPEC.md` |
| Current system state | `R5_PROJECT_STATE.md` |
| Open tasks | `TODO.md` |
| Checkpoint scripts | `scripts/tj_fallback_backtest.py`, `scripts/signal_validation.py` |
| Baseline ROI doc | `Results/CORRECTED_BASELINE_2026-06.md` |
| DB | `Results/r5_results.db` |

---

*This guide covers the Saratoga 2026 meet. Update after any mid-meet code change or ruling.*
*Last updated: 2026-06-12 (post-Session-3A feature freeze)*
