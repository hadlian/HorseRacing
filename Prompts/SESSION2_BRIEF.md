# SESSION 2 BRIEF — R5 Architecture Build (Final, 2026-06-11)

You are Claude Code implementing the R5 handicapping system for Harry Adalian.
This is Session 2 — architecture build. You have three weeks before Saratoga
opens July 3. One implementer. Work in dependency order (two tracks, below);
weekly completion reports are required but only Harry-ruling blockers stop work.

Read these files before writing a single line of code:
- Results/CORRECTED_BASELINE_2026-06.md
- Results/SIGNAL_VALIDATION_20260611.md
- Claude/R5_SPEC.md
- R5_PROJECT_STATE.md

---

## STANDING RULES FOR THIS SESSION

- Weights are frozen at v3.10 through the Saratoga meet. No weight changes
  under any circumstances.
- val_n is banned from P(win) computation permanently.
- The tier ladder (HIGH/SOLID/FAIR/SPEC) is retired. Do not reference it
  anywhere in new code or output.
- All new ROI tracking uses corrected formula: profit = payoff−2 if win,
  else −2, per $2 bet.
- Every payoff field in every schema travels with a denomination field.
  No naked payoff numbers, ever.
- Engine work in Claude/. UI work in webapp/. Do not mix sessions.
- Report back after each week. Do not wait idle for acceptance — continue
  on the non-dependent track unless a Harry ruling is pending.

## DEPENDENCY STRUCTURE — two tracks, not strict weeks

- **Track A (payoffs):** Task 0 → Task 1 → Task 7 *settlement only* → Task 9
- **Track B (probability):** Task 2 → Task 4 → Task 5 → Task 6 → Task 9
- Task 3 (queries) is standalone — run any time after Week 1 starts.
- Task 7 **ticket generation** (contender set, structure selector, paper
  logging) is NOT blocked on Task 1. It ships and logs unsettled paper
  tickets regardless of Track A status. Only `settle_tickets` requires
  Task 1 verified.
- Task 9 (dry run) is blocked on **BOTH tracks complete** — Track A
  (Task 1 verified) AND Track B (Tasks 4–6 complete).
- Week 2 starts on schedule regardless of Week 1 Track A status.

---

## WEEK 1 — Data Foundations (Jun 12–18)

### Task 0 — Chart source feasibility (DAY 1, before any schema work)

The existing results workflow (r5_tracker.py) already retrieves winner
payoffs from some chart source. Before writing any ingestion code:

1. Identify that source and verify it can also yield: full exotic payoffs
   (EX/TRI/SUPER/DD/PK3 with denominations), all-starter order of finish,
   and final tote odds per starter.
2. Do NOT assume Equibase can be scraped — it aggressively blocks automated
   access. Extend the existing working source first.
3. Named fallback if no automated source works: manual chart paste → parser
   (accept pasted chart text on stdin or from a file).
4. Report the verdict same day. If neither automated nor paste-parse is
   viable, that is a Week 1 blocker — flag immediately, do not continue
   Track A on hope.

### Task 1 — Exotic payoff + final odds schema

Add to r5_results.db. Critical path for Track A.

New table: `race_payoffs`

```sql
CREATE TABLE race_payoffs (
    id INTEGER PRIMARY KEY,
    race_id INTEGER REFERENCES races(id),
        -- for multi-race pools (DD, PK3): race_id = the ENDING leg
    pool TEXT NOT NULL,        -- WIN, PLACE, SHOW, EX, TRI, SUPER, DD, PK3
    combination TEXT NOT NULL, -- e.g. "4" or "4-7" or "4-7-2"
    payoff REAL NOT NULL,
    denomination REAL NOT NULL, -- always store: 2.0, 1.0, 0.50, 0.10
    is_dead_heat INTEGER DEFAULT 0,
    is_refund INTEGER DEFAULT 0,   -- refund/consolation rows flagged here
    carryover_in REAL,
    carryover_out REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, pool, combination)
);
```

New columns on existing `races` table:

```sql
ALTER TABLE races ADD COLUMN field_size_post INTEGER;
ALTER TABLE races ADD COLUMN has_coupled_entry INTEGER DEFAULT 0;
```

New table: `race_finish_order`

```sql
CREATE TABLE race_finish_order (
    id INTEGER PRIMARY KEY,
    race_id INTEGER REFERENCES races(id),
    finish_position INTEGER,   -- NULLABLE: NULL for scratched horses
    horse_pgm TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    final_tote_odds REAL,      -- odds-to-1, from result chart
    is_late_scratch INTEGER DEFAULT 0,  -- scratch rows: position NULL, flag 1
    is_dq INTEGER DEFAULT 0,
    official_position INTEGER, -- post-DQ official position
    is_coupled INTEGER DEFAULT 0,
    coupled_program TEXT,      -- e.g. "1A" links to "1"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, horse_pgm)
);
```

New table: `exotic_tickets` (for exotics module tracking):

```sql
CREATE TABLE exotic_tickets (
    id INTEGER PRIMARY KEY,
    race_id INTEGER REFERENCES races(id),
    ticket_type TEXT NOT NULL,  -- EX_BOX, EX_KEY, TRI_KEY, TRI_BOX
    combination TEXT NOT NULL,  -- structured: "BOX:1,3,7" or "KEY:3/1,7" or
                                -- "KEY:1/2,3,7/2,3,7,5" (key/leg2/leg3)
    cost REAL NOT NULL,
    denomination REAL NOT NULL,
    is_paper INTEGER DEFAULT 1, -- 1=paper, 0=live; see log_tickets rules
    actual_payoff REAL,         -- null until result
    profit REAL,                -- populated after settlement
    race_shape TEXT,            -- TIGHT, STANDOUT, DEFAULT
    contender_set TEXT,         -- JSON array of pgms in set
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Chart ingestion in Claude/r5_payoffs.py:
- Accepts track, date, race number
- Uses the source verified in Task 0
- Parses and populates race_payoffs, race_finish_order, field_size_post
- Handles coupled entries (1/1A pattern)
- Handles DQs (stores both across-wire and official positions)
- Handles scratches (NULL finish_position + is_late_scratch flag)
- Never stores a payoff without its denomination
- **Idempotent: delete-then-insert per (race_id) before writing.** Running
  ingestion twice on the same race must produce identical row counts.
- CLI: python3 Claude/r5_payoffs.py --track CDX --date 20260612 --race 1

### Task 2 — Tight-cluster schema fix (Track B root)

Add to picks table:

```sql
ALTER TABLE picks ADD COLUMN pre_tight_comp REAL;
ALTER TABLE picks ADD COLUMN tight_cluster_severe INTEGER DEFAULT 0;
```

First, a live-code check: **confirm the −0.40 tight-cluster deduction is
disabled in the live scoring path (`r5_parser_v2.py finalize_field`).** It
is documented as suspended. If it is still active in code, STOP — disabling
it is a scoring change requiring Harry approval + version bump. Report
status either way in the Week 1 report.

Then write scripts/reconstruct_tight_cluster.py:
- For each pick in DB, load the logged component vector
- Identify the version from the race date (pre-v3.7: no deduction
  applicable; v3.7+: deduction fires when top-3 spread ≤ 0.5)
- Before reconstruction, query the DB for version coverage — how many rows
  have a clean version tag? Report the count. If version tracking is
  incomplete, do not guess — flag for Harry.
- Reconstruct pre_tight_comp as the version-appropriate weighted sum
  WITHOUT the −0.40 deduction
- **Correctness gate (hard): for every pick where no deduction fired, the
  recomputed weighted sum must equal stored comp within 0.01. Report the
  mismatch count. A nonzero mismatch count means the weight-version mapping
  is wrong — stop and report; do not populate pre_tight_comp from a
  failing reconstruction.**
- **Circularity note: stored comps are post-deduction. The "spread ≤ 0.5"
  fired-race test must be computed on the RECONSTRUCTED pre-deduction
  comps, not stored comps.**
- Populate pre_tight_comp and tight_cluster_severe for all historical rows
- Output: how many races fired, and corrected ROI for rank-1 in fired vs
  unfired races

### Task 3 — Two free queries (run and report, no code changes)

Query A — Contender set union capture rate:
For each race in the DB where results exist:
- R5 ranks 1-3 ∪ CM ranks 1-2 (dedup by pgm; coupled entries dedup by
  base number — "1" and "1A" are one betting interest)
- Did the winner fall inside this set?
- Report: union capture rate vs R5-top-3-only capture rate (baseline 59.4%)
- If union does not beat 59.4% by ≥3 points, flag for Harry — CM legs may
  be dropped from the contender set

Query B — Rank 2/3 place rate:
Using race_finish_order (or finish_pos in picks if chart data not yet loaded):
- For R5 rank-2 and rank-3 horses: what % finish 2nd or 3rd?
- Report by rank: win%, place%, show%

### Week 1 completion report

- Task 0 chart source verdict (automated / paste-parse / blocked)
- Schema changes applied and verified (show CREATE TABLE outputs)
- r5_payoffs.py tested on at least 2 SAR cards already in hand
- **Idempotency test: same race ingested twice, row counts identical**
- Tight-cluster: deduction live-code status; version coverage count;
  **epsilon-check mismatch count (must be 0 to proceed)**; fired race
  count; corrected ROI fired vs unfired
- Query A result with go/no-go on CM legs; Query B result
- Any blockers or Harry rulings needed

---

## WEEK 2 — Probability Layer + Output Revamp (Jun 19–25)

Track B work. Starts on schedule regardless of Track A status.
Task 4 requires Task 2's epsilon check passed (it validates the same
component-vector → composite recomputation Task 4 depends on).

### Task 4 — comp_ex_val computation

In r5_parser_v2.py, add compute_comp_ex_val(horse):
- Takes the logged component vector for a horse
- Recomputes composite using v3.10 weights with val_n removed and
  remaining weights renormalized: **each remaining weight divided by 0.95
  exactly, in code. Do not hard-code rounded renormalized values.**
- comp_ex_val is by construction pre-deduction (pure weighted sum) —
  do not re-apply any tight-cluster deduction to it.
- Returns comp_ex_val on same 0-10 scale

```sql
ALTER TABLE picks ADD COLUMN comp_ex_val REAL;
```
(This is the ONLY place comp_ex_val is added. It does not appear in
Task 5's ALTER block.)

- Backfill for all existing picks from logged component vectors
- **Report both: rows backfilled AND rows that could NOT be backfilled
  (missing component vectors). Non-backfillable rows are silently excluded
  from the logit fit — the count must be visible.**

### Task 5 — Conditional logit P(win) layer

Create Claude/r5_probability.py:

```python
def fit_logit(db_path):
    # Load all races with results from r5_results.db
    # For each race: all picks with comp_ex_val and won flag
    # Exclude scratches (finish_pos = -1 or NULL)
    # Drop races where the winner's pick lacks comp_ex_val; report count
    # Fit: maximize sum over races of log P(winner | field)
    # P(win)_i = exp(β * comp_ex_val_i) / sum_j exp(β * comp_ex_val_j)
    # (subtract max(comp_ex_val) before exp for numerical stability)
    # scipy.optimize.minimize on negative log-likelihood
    # Return β, log-likelihood, n_races, n_winners
    # Serialize β to Results/logit_beta.json with metadata

def score_field(horses, beta):
    # horses: list of dicts with comp_ex_val
    # Returns P(win) per horse, normalized within field
    # fair_odds = (1/P) - 1
    # ml_edge = P * (ml_odds + 1) - 1
    # Flag OVERLAY if ml_edge >= 0.25 AND P >= 0.08

def calibration_report(db_path, beta):
    # Decile-bin predicted P(win) vs observed win rate
    # Specific check: mean predicted P for rank-3 horses vs observed 23.2%
    # Output: Results/CALIBRATION_REPORT_<date>.md
```

```sql
ALTER TABLE picks ADD COLUMN p_win REAL;
ALTER TABLE picks ADD COLUMN fair_odds REAL;
ALTER TABLE picks ADD COLUMN ml_edge REAL;
ALTER TABLE picks ADD COLUMN is_overlay INTEGER DEFAULT 0;
```

val_n ≥8 tracker (live per Harry ruling 3, with guardrails CODED as gates,
not comments):

```sql
CREATE TABLE val_n_tracker (
    id INTEGER PRIMARY KEY,
    pick_id INTEGER REFERENCES picks(id),
    val_n REAL NOT NULL,
    ml_odds REAL,
    bet_size REAL DEFAULT 2.0,
    is_paper INTEGER DEFAULT 1,
    result INTEGER,  -- 1=win, 0=loss, null=pending
    payoff REAL,
    profit REAL,
    stop_triggered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- **No cumulative_profit column.** The running total is computed at
  decision time via SELECT SUM(profit), never stored per row (stored
  running totals go stale when results settle out of order).
- **Enforcement, executable:** before logging any live (is_paper=0) bet,
  evaluate: (a) settled bets ≥ 30 with 0 wins? (b) SUM(profit) < −60?
  (c) already 2 bets logged this card? If any is true → refuse live,
  force is_paper=1, set stop_triggered where applicable. This check is
  code in the logging path, not a comment.
- Flat $2 only. Max 2 bets per card.

### Task 6 — Output revamp

In run_r5.py and webapp/app.py, replace tier ladder output entirely.

Per-horse line format (exactly this shape):

```
#4 Tapit's Echo    comp 6.8 (R1)   P(win) 24%   fair 3.2-1   ML 5/2   edge −21%
#7 Distant Glory   comp 6.5 (R3)   P(win) 19%   fair 4.3-1   ML 8-1   edge +69% ▲OVERLAY
```

Per-race header line (above the horse list):

```
R5 | top-3 cum P(win) 58% | spread(r1−r3) 0.4 TIGHT | structure: EX BOX 1-2-3 +TRI BOX
```

Rules:
- OVERLAY flag only when ml_edge ≥ +25% AND P(win) ≥ 8%
- Every OVERLAY flag carries the footnote: "vs morning line — advisory
  until live odds" (Harry ruling 4)
- PLAY/NEAR/SKIP verdict line: deleted, not relabeled
- Tier labels: deleted everywhere including webapp
- val_n ≥8 horses: ◆ marker and "VAL WATCH" label

### Task 6B — Historical payoff backfill (Track A, start when Task 1 verified)

Backfill race_payoffs + race_finish_order (including final tote odds) for
all existing ~160 DB races where charts are retrievable.
- This powers the pre-meet structure backtest and the final-odds overlay
  retro-test — it is the difference between validating at SAR opening vs
  mid-meet.
- Report coverage: races backfilled / races attempted / races unavailable.
- May run in Week 2 or Week 3 as Track A permits; report coverage in
  whichever weekly report it lands.

### Week 2 completion report

- comp_ex_val: rows backfilled AND rows non-backfillable
- β value, log-likelihood, n_races used, races dropped (missing winner vector)
- Calibration report: decile table + rank-3 diagnostic
- Output sample: one full race card in new format (header + horse lines)
- val_n_tracker created; enforcement gates demonstrated (show a refused
  live bet in test)
- Backfill coverage if started
- Any calibration anomalies for Harry

---

## WEEK 3 — Exotics Module + Freeze (Jun 26–Jul 2)

Task 7 ticket generation requires Track B (needs P(win) output and CM ranks).
Task 7 settlement requires Task 1 verified. Task 9 requires both tracks.

### Task 7 — Exotics module v1

Create Claude/r5_exotics.py:

**Contender set builder:**

```python
def build_contender_set(r5_horses, cm_horses, field_size_post, scratches):
    # R5 ranks 1-3 union CM ranks 1-2 (dedup by pgm AND by coupled base
    # number — "1" and "1A" are one betting interest, use base number)
    # Add PP-underline horse as underneath-only if outside union
    # Exclusion triggers:
    #   field_size_post <= 5: return None (pass race)
    #   >=2 debut horses in set: return None or exacta-only flag
    #   set size >5 after union: trim CM-only legs first (CM rank-2 before
    #   any R5 rank)
    # Scratch in set: re-rank remaining field and rebuild; never promote
    # rank-4 into a stale set
    # Return contender set with role tags: TOP/UNDERNEATH/PP_UNDERLINE
```

**Structure selector:**

```python
def select_structure(contender_set, spread_r1_r3, spread_r1_r2,
                     rank3_ml_odds, field_size_post):
    # spread_r1_r3 <= 0.5 (TIGHT):
    #   $1 EX box R5 1-2-3 ($6)
    #   $0.50 TRI box 1-2-3 ($3)
    #   if rank3_ml_odds >= 6.0: add $1 EX key r3 over r1,r2 ($2)
    #   (full TIGHT menu = $11, fits under cap)
    # spread_r1_r2 >= 1.0 (STANDOUT):
    #   $1 EX key r1 over set
    #   $0.50 TRI key r1 / set / set+PP_underline
    # anything else (DEFAULT): $1 EX box only
    # Superfecta: always None (pass) until payoff data exists
    #
    # $12 total ticket cost cap per race (Harry ruling 2).
    # Trim priority when over cap — drop order:
    #   1st dropped: TRI legs (shrink third leg, then drop TRI entirely)
    #   2nd dropped: rank-3 EX key
    #   never dropped: primary EX structure
    #
    # REQUIRED TEST CASE (the only shape where the cap fires):
    #   STANDOUT with 4-horse set + PP-underline:
    #   $1 EX key r1 over 4 ($4) + $0.50 TRI key r1/5/5 (20 combos, $10)
    #   = $14 before trim. Verify trim drops TRI legs until total <= $12.
    #   This branch ships untested unless forced — write the test.
```

**Ticket logger:**

```python
def log_tickets(race_id, tickets, live_mode=False):
    # is_paper=1 ALWAYS by default, under all circumstances.
    # is_paper=0 ONLY when live_mode=True, which is set by an explicit
    # per-session flag Harry controls (e.g. --live on the CLI).
    # Never infer live mode from config, environment, or prior sessions.
```

**Result settler:**

```python
def settle_tickets(race_id):
    # After payoffs loaded via r5_payoffs.py
    # Expand each ticket's structured combination ("BOX:1,3,7" /
    # "KEY:3/1,7") into its individual combos; match each against
    # race_payoffs combinations
    # Coupled entries: normalize pgm by stripping letter suffix before
    # matching ("1A" -> "1") — pools pay on the base number
    # Dead heats: a pool may have multiple payoff rows; sum all matched
    #
    # DENOMINATION SCALING — the formula, exactly:
    #   collected = quoted_payoff * (ticket_denomination / payoff_denomination)
    #   profit    = collected_total - total_ticket_cost
    #
    # Scratch/refund rules:
    #   scratched leg in a BOX: surviving combos stand; combos involving
    #     the scratched horse are refunded at cost
    #   scratched KEY horse: entire ticket refunded (profit = 0)
    #   refund rows in race_payoffs (is_refund=1) matched accordingly
    #
    # UNIT TEST GATE (hard, before settlement runs on real data):
    #   one known chart, hand-computed expected profit for at least one
    #   EX box at $1 vs a $2-quoted payoff and one TRI at $0.50 vs a
    #   $1-quoted payoff. Settlement code does not run on the live DB
    #   until this test passes. This is the exact bug class just
    #   remediated ($2 payoffs vs $1 stakes) — zero tolerance.
```

### Task 8 — R5_SPEC refresh

Update Claude/R5_SPEC.md to v3.10:
- Current weights as implemented in code (v3.10); class = 20% per Harry
- Document val_n ban from P(win)
- Document tier ladder retirement
- Document conditional logit P(win) layer + comp_ex_val
- Document exotics module + contender set + structure menu + $12 cap
- Note weight freeze through Saratoga meet

### Task 9 — Dry run and feature freeze

**Blocked on BOTH tracks: Task 1 verified (Track A) AND Tasks 4–6 complete
(Track B).**

Dry-run the full pipeline on the June SAR cards already in the DB:
- run_r5.py → new output format (header + per-horse lines)
- r5_exotics.py → contender set + structure + paper tickets logged
- r5_payoffs.py → payoffs loaded; settle_tickets settles the logged tickets
- Verify the full loop produces clean output with no errors

Feature freeze: June 30.
July 1–2 reserved for breakage fixes only — no new features.

### Week 3 completion report

- Exotics module tested on at least 3 SAR races end-to-end
- STANDOUT cap test case result (the $14 → ≤$12 trim)
- Settlement unit test result (hand-computed vs code)
- Paper ticket log sample: tickets, payoffs, profit/loss
- R5_SPEC.md updated and committed
- Dry run clean
- Backfill coverage final count
- **Open items / in-meet checkpoints handed off (verbatim list):**
  - SAR-only β refit comparison at n≥60 SAR races
  - Structure-menu ROI review at n≥40 SAR races with full payoff capture
  - val_n ≥8 re-decision at n≥120 qualifying bets (target ≥10 wins)
  - CM merge-or-keep decision at n≥100 SAR races
  - Live odds capture build (mid-July)
  - Final-odds overlay retro-test (P × (final_odds+1) ≥ 1.25) once
    backfill coverage is sufficient

---

## HARRY'S RULINGS — confirmed, implement accordingly

1. Weights frozen at v3.10 through Saratoga meet
2. Exotics live from opening day at **$12 per race ticket cap** (trim
   priority: EX never dropped, rank-3 key second, TRI dropped first)
3. val_n ≥8 live with guardrails: flat $2, max 2/card, hard stop at
   0 wins in 30 settled bets OR SUM(profit) < −60, computed at decision
   time — enforcement coded as a gate in the bet-logging path
4. ML-overlay flags advisory only — no live win bets until the final-odds
   backtest completes mid-meet

---

## WHAT NOT TO TOUCH IN THIS SESSION

- No weight changes
- No new composite components
- No CM scoring engine changes
- No changes to how val_n is computed (only how it's used)
- No superfecta logic
- No live odds capture (mid-July build)
- No changes to r5_tracker.py result logging workflow (Task 0 reads its
  source; it does not modify it)
- No re-enabling the tight-cluster deduction in scoring (it stays
  suspended regardless of what reconstruction shows)

---

## REPORT BACK

After each weekly completion report, deliver it and continue on the
non-dependent track while awaiting Harry's acceptance. Stop only for
Harry-ruling blockers.

Final delivery before July 3:
- All schema changes migrated and verified (idempotency + epsilon gates passed)
- P(win) layer live in output
- Exotics module paper-tracking from day 1, live mode Harry-flag-gated
- val_n ≥8 tracker active with coded guardrails
- R5_SPEC.md at v3.10
- Full pipeline dry run clean on SAR cards
- In-meet checkpoint list handed off
