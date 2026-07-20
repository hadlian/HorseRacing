# HorseRacing — R5 Handicapping System

BRIS DRF-based handicapping: R5 composite engine (v3.10, **feature-frozen through the Saratoga 2026 meet**) plus two comparison models (CM = Dennis, CM1 = Frank). Paper tracking only — live win betting is NOT authorized.

## Read first
- **[TODO.md](TODO.md)** — authoritative task list, in-meet checkpoints, current performance numbers. When docs disagree, TODO.md wins.
- [R5_PROJECT_STATE.md](R5_PROJECT_STATE.md) — stable architecture + rulings.
- [SARATOGA_OPERATIONS.md](SARATOGA_OPERATIONS.md) — race-day runbook (stops, guardrails, troubleshooting).
- [comparemodels/COMPAREMODELS_STATE.md](comparemodels/COMPAREMODELS_STATE.md) — CM/CM1 state.

## Layout
| Where | What |
|---|---|
| `Claude/` | R5 engine + pipeline (`run_r5.py`, `r5_parser_v2.py`, `r5_probability.py`, `r5_exotics.py`, `r5_payoffs.py`, `r5_tracker.py`, `r5_results_cli.py`, `r5_analyze.py`) |
| `comparemodels/` | CM (`comparemodels_cli.py`) and CM1 (`cm1_tracker.py`, `cm1_compare.py`) + their gitignored DBs |
| `scripts/` | diagnostics (`signal_validation.py`, backtests, gates) |
| `webapp/` | web frontend (separate chat owns UI work) |
| `~/Documents/RacingData/files 2/` | DRF input files (`TRACK_MMDD.DRF`) — **read-only**, shared |
| `~/Documents/RacingData/Results/` | `r5_results.db` (authoritative R5 DB — this project is the **sole writer**), chart PDFs in `Results/2026/`, analysis workbooks |
| `Claude/r5_paths.py` | **single source of truth** for the two data roots (override via repo-root `.env`; see `.env.example`) |
| `venv/` | Python env — `source venv/bin/activate` for PDF/analysis deps |

## Race-day commands

**Pre-race** (one command — runs R5 `--save --track` + CM log + CM1 log; DRF must live in `RacingData/files 2/` — the CLI also resolves a bare filename there):
```bash
python3 Claude/r5_card_cli.py "files 2/SAR0713.DRF"          # add --wet / --auto-scout as needed
```
`--save` txt is the default deliverable; `--pdf` only on request. Historical/backtest DRFs REQUIRE `--year`/`--backtest` or they create live phantom cards under wrong dates. `run_r5` hard-refuses re-runs on settled cards and the wrapper stops the whole chain when it does (`--force` overrides — don't, without checking why).

The **webapp** card-run logs the same three models when "log picks" is on (CM1 wired in 2026-07-19; webapp cards before that are missing CM1 unless back-logged). To verify a card is fully pre-raced, all three should have rows for the date: R5 `picks` (r5_results.db), CM `picks` (comparemodels_results.db), `cm1_picks` (cm1_results.db).

**Post-race** (one command; PDF chart from Equibase into `Results/2026/`; track/date derived from the filename):
```bash
python3 Claude/r5_results_cli.py Results/2026/20260712SARUSA0.pdf
```
Runs everything: payoffs ingest + pick reconcile → finalize scratches → settle exotics (+ post-scratch A/B) → CM results/finalize → paper trackers (rank3, val_n) → summary → docs (CM1 compare + `r5_analyze` workbook; skip with `--no-docs`). Idempotent — safe to re-run. CM1 needs no settle step (reads winners from the R5 DB).

**If finalize aborts with ">3 NULL positions"** in a race: verify those picks against the PDF's `Scratched-` lines; if genuine scratches, set `picks.finish_pos=-1` for them via SQL and re-run the pipeline. Never force past it without checking the PDF — it also catches partially-logged cards.

## Standing rulings (do not relitigate)
- v3.10 weights frozen; any model change needs Harry's ruling + version bump. Results-pipeline code is outside the freeze.
- No positive-ROI signal confirmed anywhere (every "positive slot" was a single-payout mirage). Gates/tiers/consensus/agreement filters all retired. val_n is PAPER only.
- Overlay flag ≠ bet signal (retro-tested −56.9%).
- Post-scratch re-scoring: NO-GO; A/B monitor only.
