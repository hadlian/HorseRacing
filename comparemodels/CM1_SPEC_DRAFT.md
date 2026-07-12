# CM1 — Scoring Rules (DRAFT for red-line)

> **Status:** DRAFT — rules only, no code. Derived from Harry's morning-homework
> checklist (2026-07-11). To be red-lined before any implementation.
> **Purpose:** A third ranked model to compare head-to-head against R5 and CM,
> built to isolate signals the other two do **not** carry: workout sharpness,
> connection meet-form & surface splits, distance/pace-collapse fit, dam-side pedigree.

---

## Design principle

R5 (9 components) and CM (8 weighted categories) already saturate **speed** and
**class**. CM1 deliberately **down-weights** those to the minimum needed to produce
a rank, and puts its weight budget on the **net-new** signals. If CM1 beats the
market where R5/CM did not (gate NO-GO, 2026-07-06), it will be *because* of the
net-new categories — that is the whole point of the model.

**Output:** a single composite integer per horse → ranked descending → CM1 top pick,
rank-2, rank-3. Directly comparable to R5/CM top picks for ROI/hit-rate.

**Weight budget (max points each category can contribute):**

| Category | Max pts | Net-new? | Data status |
|---|---:|---|---|
| 1. Workout Sharpness | 5 | ✅ | ✅ done — `cm1_workouts.py` (Q1 resolved) |
| 2. Connection Angles (+ surface, Cat-4 merged) | 6 | ✅ | ✅ done — DRF f1337-1372 (Q2 resolved) |
| 3. Distance / Pace-Collapse Fit | 4 | ✅ | ✅ done — `cm1_pace_fit.py` (Q3 resolved) |
| ~~4. Connection Surface Split~~ | — | | folded into Cat-2 (Q2) |
| 5. Pedigree (sire + dam) | 3 | ~ (dam side) | ✅ parseable now (sire/dam_sire fields) |
| 6. Speed backbone | 3 | ❌ redundant | ✅ parseable now |
| 7. Class Move | 2 | ❌ redundant | ✅ parseable now |
| **Composite max** | **23** | | |

---

## Category 1 — Workout Sharpness  (max 5)  ✅ net-new  ✅ RESOLVED (Q1)

**Data: fully in the BRIS DRF.** Confirmed against `Schema/June2026Schema.txt` and
extracted by `comparemodels/cm1_workouts.py`. Fields (12 slots/horse): Date 102-113,
Time 114-125 (seconds, leading `-` = bullet/best-of-day), Track 126-137, Distance
138-149 (yards; ÷220 = furlongs), Condition 150-161, Description 162-173 (H/B, `g`=gate,
`D`=dogs), Main/Inner track indicator 174-185 (`MT`/`IM` dirt, `TT` training, `T`/`IT` turf).

### Q1 finding (8,732 works, 8 SAR July cards)

- Harry's `3F<36 / 4F<48 / 5F<1:00` land almost exactly on the **p10** of each distance
  → genuinely top-decile "sharp" works, not routine drills. Keep the intent.
- **Median clock is near-universal across surfaces** (within ~0.5s), so the raw time
  travels. But the **rate** of beating it is strongly track-relative:

  | Dist | % beating threshold — main dirt / training / turf |
  |---|---|
  | 3F `<36` | 9% / **5%** / **25%** |
  | 4F `<48` | 10% / **6%** / 11% |
  | 5F `<1:00` | 8% / **2%** / 11% |

  Training-track sub-threshold works are ~half as common (worth **more**); turf ones
  2–3× as common (worth **less**). The meaningful axis is **main / training / turf**
  (field 174), *not* fast/off — off-track medians matched fast in-sample.

### Resolved scoring (percentile-relative, self-calibrating)

For each horse, take the **best qualifying published work in the last 45 days** per
distance band (3F/4F/5F). Score the single best line; "sharp" is defined **relative to
the same distance+surface bucket** in the current card pool, so it auto-tightens on
turf and auto-loosens on the training track — and needs no re-tuning across meets.

| Condition (within distance+surface bucket) | Points |
|---|---:|
| Time ≤ **p10** of bucket (≈ Harry's numbers on dirt) | +3 |
| Time ≤ **p25** of bucket | +1 |
| Bullet (leading `-`, best of day at track/distance) | +2 |

- Take the **max** distance-band score (not additive across bands), then add the bullet
  bonus. Cap category at 5.
- Buckets computed live by `cm1_workouts.py` percentiles; falls back to Harry's absolute
  `36/48/60` if a bucket has < ~30 works (thin turf/off samples).
- Gate works (`g`) and dogs-up (`D`) are **flagged but not penalized** in v0 —
  revisit if they prove to distort (a gate breeze is often intentionally slow).

## Category 2 — Connection Angles  (max 5)  ✅ net-new  ✅ RESOLVED (Q2)

**Data: fully in the BRIS DRF — no external stat file needed.** Two discoveries flip
the original plan:

1. **Plain meet win% is NOT net-new.** Fields 29/30 (Trainer Sts/Wins Current Meet) and
   35/36 (Jockey Sts/Wins Current Meet) are populated (Brown 57-10=17.5%, Prat 79-16=20.3%
   this meet) — and `r5_parser_v2` already maps them into R5's `tj_n` and CM's jockey/
   trainer rating. Re-spending CM1 points on meet win% would just replicate R5/CM.
2. **The net-new signal is BRIS's situational angle stats**, which neither model uses:
   - **6 trainer angles** (f1337-1366): BRIS pre-selects the angles relevant to *today's*
     spot for this horse — {label, starts, Win%, ITM%, **$2 ROI**}. Live example (Brown):
     `2nd off layoff 369s 24.9% roi -0.02` · `Btn favorite 258s 28.3%` · `Routes` · `Dirt starts`.
   - **1 jockey context stat** (f1367-1372): {label, starts, W, P, S, **ROI**}, label toggles
     `Routes`/`@Distance` vs `on Turf` by race. Live: Prat `Routes 190-61 = 32%, ROI +0.16`.

**Why this is the CM1 thesis, sharpened:** the **$2 ROI** field is *market-anchored* — it
already encodes whether the angle beat the odds historically. Given the gate NO-GO (nothing
fundamental beat the closing market), a connection angle with **positive $2 ROI** is exactly
the orthogonal, market-relative signal worth testing. R5/CM see none of it.

### Resolved scoring (data-driven, watch-list dropped)

Score the **best relevant trainer angle** + the **jockey context stat**, gated on sample size
(≥ ~30 starts) so early-meet noise doesn't fire:

| Condition | Points |
|---|---:|
| Best trainer angle Win% ≥ 20% **and** $2 ROI ≥ 0 (angle beats market) | +3 |
| Best trainer angle Win% ≥ 20% but ROI < 0 (effective but bet-down) | +1 |
| Jockey context stat Win% ≥ 18% **and** ROI ≥ 0 | +2 |
| Jockey context stat Win% ≥ 18% but ROI < 0 | +1 |
| Surface-specific angle present & positive (turf/dirt/wet context, from Cat-4 merge) | +1 |

- Cap category at 6 (absorbs the folded-in Cat-4 budget). Sample floor ≥30 starts on any angle used.
- **Watch-list DROPPED** — real meet win%, angle win%, and ROI identify hot/effective
  connections directly (and market-relatively); a hardcoded Ortiz/Brown list only adds
  bias and goes stale. This answers Q2's literal question: *pure numbers, no names.*
- Meet win% (f29/30, 35/36) is **left to R5/CM** to avoid double-counting; CM1 spends its
  connection budget only on the angle+ROI signal they lack.
- **RED-LINE Q:** are the 20%/18% Win% cutoffs right, and is ROI≥0 the correct market gate
  (vs. a stricter ROI ≥ +0.05 to demand a real edge)?

## Category 3 — Distance / Pace-Collapse Fit  (max 4)  ✅ net-new  ✅ RESOLVED (Q3)

Encodes your "led to 5F then faded in a route → cut back to a sprint" angle, and its mirror.
**Data: fully in the DRF** — per-PP running lines (10 slots) read by `comparemodels/cm1_pace_fit.py`:
distance f316-325, surface f326-335, positions at start/1c/2c/str/finish (f566-625), finish
beaten-lengths f736-745; today distance f6, surface f7.

### Q3 calibration (777 horses, 8 SAR July cards)

Draft thresholds (faded ≥2 pos / closed ≥3 pos / 0.75F gap) fired on **a quarter of the
field** — not a signal. The magnitude distributions showed why: "lost 2 pos" (153 horses)
is drift, and "gained 4" is the single most common outcome (235) — ordinary closing style.
Tightened thresholds cut it to ~4 cut-back + ~7 stretch-out candidates per card, and the
survivors are the true archetype (TRUMAN'S COMMANDER 8.5F→5.5F faded 7p; CONTRARY THINKING
10F→6.5F faded 8p, beaten 38 lengths after leading).

### Resolved rules

- **Faded from speed** = best early position (1c or 2c) ≤ **2** (led/pressed) AND lost ≥ **4**
  positions to the finish. (2–3 = drift.)
- **Closed** = start-or-1c position ≥ **5** (off the pace) AND gained ≥ **5** positions.
  (3–4 = normal closing.)
- **Distance gap ≥ 1.5F** between the past race and today (1F is a nudge, not a cut-back).
- **Same-surface only** — pace shape doesn't transfer dirt↔turf (`T`/`t` count as one turf class).

| Pattern (best single matching line, recent 6 starts) | Points |
|---|---:|
| Faded-from-speed in a race **≥1.5F longer** than today → **cut-back sprint fit** | +3 |
| Closed in a race **≥1.5F shorter** than today → **stretch-out route fit** | +2 |
| Ran evenly at today's exact distance & surface with a competitive finish position | +1 |
| Faded-from-speed at a distance **≤ today** (no cut-back relief) | −1 |

- Score the **single best-matching** line only (don't sum multiple qualifying PPs); cap 4, floor −1.
- **Recency weight:** a qualifying fade/close in the last 1–2 starts counts full; older lines at
  half. (Contrary Thinking's collapses are recent form → stronger than a stale line.)
- **Caveat (data-observed):** horses with a fade line often *also* have wire-to-wire wins at the
  route — the flag is contributory, not standalone. Consistent with CM1's role as a divergence/
  contender flag, not a lone win-bet basis.

## Category 4 — Connection Surface Split  (max 4)  ✅ net-new  ⚠️ PARTLY in DRF

Your Rosario-on-turf / Brown-on-turf angle. **Update (Q2 probe):** surface/distance splits
are *partly* in the DRF after all — no external file needed for the common cases:
- **Jockey on turf / at distance** — f1367-1372, but only when BRIS selects that context
  (a dirt route shows `Routes`, a turf race shows `on Turf`). One slot, race-dependent.
- **Trainer on surface** — appears among the 6 angle slots (`Dirt starts`, `Routes`, …)
  **when relevant**, but not guaranteed every card.

**Consequence:** Cat-4 largely **collapses into Cat-2** — both draw from the same angle/context
blocks. Recommendation: **fold Cat-4 into Cat-2** rather than keep a separate category, and
reallocate its 4-pt budget (see weight note below). A standalone Cat-4 only earns its keep if
we later add a full jockey×surface×meet matrix from an external BRIS stat file — deferred.

- **RED-LINE Q:** OK to merge Cat-4 into Cat-2 for v0 and revisit a dedicated surface matrix
  post-v0? And should off-track (`my`/`sy`/`sl`) get its own split when today is wet?

## Category 5 — Pedigree  (max 3 at full spec; **v0 ships REDUCED, max 1-2**)

`sire` (f52), `sire_sire` (f53), **`dam` (f54)**, `dam_sire` (f55) all parse today.
**Re-correlation warning (2026-07-12 review):** R5's `ped_n` already scores the *sire*
(vs the same `classic_sires` list) and the BRIS ped ratings f1264 (dirt) / f1267 (dist).
A sire-based Cat-5 would just be a third backbone. CM1's orthogonal pedigree content is
the **dam side (f54/f55)** and the **unused turf/mud ped ratings f1266/f1265** (R5 parses
but never scores them).

### v0 — SHIPS NOW, reduced (Harry ruling 2026-07-12: "reduced now, dam row later")
| Condition | Points | Note |
|---|---:|---|
| Surface-switch matches breeding — turf today & strong **f1266** (turf ped), or wet & **f1265** (mud ped) | +1 | orthogonal — R5 ignores f1265/f1266 |
| **Debut or ≤2 lifetime starts** with a strong surface ped rating (pedigree-carries) | +1 | pedigree matters most with no form |
| ~~Sire on legendary list~~ | tie-break only | duplicates R5 `ped_n` — demoted, not scored |

v0 **caps at 2** (often effectively 1). **Parsing:** strip trailing `*` from ped ratings
(e.g. `115*`) — the starred form exists in live data and silently None-outs a naive `float()`.

### Deferred — the "dam row" (adds back to max 3 later)
| Condition | Points | Blocked on |
|---|---:|---|
| Broodmare-sire (f55) on legendary list | +1 | **Harry's dam/broodmare-sire list** |
| Broodmare-sire positive **$2 ROI** (winsorized, ex-outlier-gated, n≥100/surface) | +1 | the parallel **BMS ROI DB** maturing |

- The dam ROW turns on when the list arrives; the ROI leg turns on per-broodmare-sire as
  the [[project_cm1]] BMS database clears its floor. Neither blocks the v0 ship.

## Category 6 — Speed backbone  (max 3)  ❌ redundant  ✅ parseable

Deliberately minimal — only present so every horse is rankable. Uses best BRIS speed
at today's distance (`best_dist` / `bris_speed`).

| In-race rank by best speed @ distance | Points |
|---|---:|
| 1st | +3 |
| 2nd | +2 |
| 3rd | +1 |

## Category 7 — Class Move  (max 2)  ✅ RESOLVED (field-mapped 2026-07-12)

**Design principle — score the MOVE, not the LEVEL.** R5's `class_n` is a par-anchored
class *level* (`5.0 + (ws4 − par)/3`) and already consumes the BRIS class par
(f1167-1176). CM1 must NOT re-read that par or it re-correlates with R5 (the backbone
problem). Cat-7 instead scores the **direction of the class move** — today's class tier vs
the horse's most recent start — which R5's level signal does not capture.

### Fields (verified against Del Mar BC card, 2026-11-01)
| Purpose | Field(s) |
|---|---|
| Today's race type code | **f9** (e.g. `AO`) |
| Today's classification text | **f11** (e.g. `OClm 50000n1x`) |
| Today's purse | **f12** |
| Today's low claiming price | **f238** (f239 = statebred flag) |
| Past race type code (last 10) | **f1086-1095** |
| Past classification text (per PP) | **f536** |
| Past claiming price of race (per PP, 10-slot) | **f1202-1211** low / **f1212-1221** high |
| Past claiming price of *horse* (per PP) | **f546-555** *(alt basis — see note)* |
| Past purse (per PP) | **f556** |
| Past finish position (per PP, for step-up justification) | **f616** |

> **⚠️ Field correction (2026-07-12):** today's claiming price is **f238**, NOT f1202 —
> f1202-1211/f1212-1221 are the 10-slot *past-PP* race-band blocks (f1202 = most recent
> past race). Comparing a past band to a past band would read as "always lateral." Use the
> **race band** (today f238 / past f1202+i) as ONE consistent ordinal basis; f546-555 is the
> horse's *entered* price and must not be mixed with the race band on the other side.

### Class-tier ladder — `class_rank(race)` (coarse → fine)
1. **Race-type tier** from the type code (f9 today / f1086 past). **Validated map**
   (derived 2026-07-12 from f9→f11 classification text across all 24 retained DRFs):

   | Code | Meaning | Tier |
   |---|---|---:|
   | `G1` / `G2` / `G3` | Graded stakes | 9 / 8 / 7 |
   | `N` | Listed / nongraded stakes (`…L200k`) | 6 |
   | `A` | Allowance (`Alw …n1x`) | 5 |
   | `AO` | Allowance optional claiming (`OClm …n1x`) | 5 → refine by claim |
   | `R` | Restricted / statebred allowance (`Alw …s`) | 4 |
   | `C` / `CO` | Claiming / optional claiming | 3 → refine by claim |
   | `S` | **Maiden Special Weight** (`Md Sp Wt`) — NOT stakes | 2 |
   | `M` | Maiden claiming (`Md 50000`) | 1 |
   | past-only: `MO` maiden-opt-claim | | 1 |
   | past-only: `T` trial, `HR`/`HO` (hurdle/other) | | neutral — exclude from baseline |

   > ⚠️ **`S` is Maiden Special Weight, not Stakes** — the intuitive guess would invert the
   > single most common race type (620 today / 3,664 past) and score every maiden as a top
   > stakes. Any *new* code not in this table = HARD FAIL at Gate-0, never a silent tier-0.
2. **Within claiming tiers:** order by claiming price using the race band consistently —
   today **f238**, past **f1202+i** (NOT f1202 for today; see correction above).
3. **Within allowance/stakes:** break ties by purse (f556 past / f12 today).

### Scoring (max 2) — move = today's `class_rank` − most-recent-start `class_rank`
| Condition | Points |
|---|---:|
| **Drop** (today tier < most-recent tier) — attach an **"ask why" flag** (well-placed vs declining) | +2 |
| **Same / lateral** (equal tier) | +1 |
| **Step up** (today tier > most-recent tier) | 0 |

- Uses the **most recent start** as the baseline; optionally dampen a one-off with the
  median tier of the last 3 starts (decide on the backfill).
- The old "step-up **and** best speed top-3" row is **removed** — it re-used the Cat-6 speed
  rank (internal double-count, per the 2026-07-12 review). Step-ups are simply neutral here;
  any speed justification already lives in Cat-6.
- Ships at **max 2** and earns no increase without backfill evidence (redundant-backbone
  discipline).

---

## Composite & tie-breaks

```
CM1_composite = Σ (cat1,2,3,5,6,7),  range −? .. 23   (Cat-4 merged into Cat-2)
```

- Rank horses descending by composite.
- **Tie-break order:** (1) Workout Sharpness, (2) Distance-Fit, (3) Speed backbone.
- **Dominant flag:** composite gap of ≥4 between rank-1 and rank-2.
- **Divergence flag (the CM-style workflow output):** when CM1 top pick ≠ R5 top pick
  ≠ CM top pick, surface all three for exotic construction.

---

## Data-source decision tree (blocks implementation)

| Signal | Source | Effort |
|---|---|---|
| Workout times | ✅ BRIS DRF f102-185 — parsed by `cm1_workouts.py` | DONE |
| **Trainer/jockey MEET win%** | ✅ DRF f29/30, 35/36 (already in R5/CM) | in-file |
| **Trainer situational angles** | ✅ DRF f1337-1366 (6× label/sts/win%/ITM%/ROI) | scoring only |
| **Jockey context (turf/dist) stat** | ✅ DRF f1367-1372 (label/sts/W/P/S/ROI) | scoring only |
| Distance/pace fit | already parsed (`past_post`, `pace_*`) | scoring logic only |
| Sire/dam pedigree | already parsed; need dam list from Harry | list + scoring |
| Speed backbone (Cat-6) | already parsed (`best_dist`/`bris_speed`) | scoring only |
| Class **move** (Cat-7) | ✅ DRF f9/f11/f12/**f238** today, f1086-1095/f536/**f1202+i**/f556 past (NOT the par f1167 — R5 owns that) | scoring only |

**No external stat file needed.** The Q2 probe found every connection signal — meet win%,
situational trainer angles, and jockey turf/distance context — already inside the DRF row.
CM1 is a build on the existing `comparemodels/` harness with **no data dependency**; the
only outstanding input from Harry is the legendary **dam list** for Cat-5.

---

## Open red-line questions (summary)

1. ~~Workout thresholds — universal or surface/track-relative?~~ ✅ **RESOLVED**:
   percentile-relative per distance+surface; training-track premium, turf discount;
   split on main/training/turf not fast/off. See Cat-1.
2. ~~Meet-form — keep the named watch-list, or pure win%?~~ ✅ **RESOLVED**: meet win% is
   in-DRF but already used by R5/CM; CM1's net-new edge is the situational **angle win% +
   $2 ROI** (f1337-1372). Watch-list dropped — numbers only. Cat-4 folds into Cat-2. See Cat-2.
   *Remaining tweak:* Win% cutoffs (20%/18%) and ROI gate (≥0 vs ≥+0.05)?
3. ~~Distance-fit — lengths for "faded" / positions for "closed"; same-surface only?~~
   ✅ **RESOLVED** (8-card scan): faded = led early + lost ≥4 pos; closed = back + gained
   ≥5 pos; ≥1.5F distance gap; same-surface only; recent lines weighted. See Cat-3.
4. ~~Surface split — separate off-track bucket?~~ → merged into Cat-2 (Q2); off-track split
   deferred to a post-v0 surface matrix.
5. Pedigree — provide the legendary **dam / broodmare-sire** list.
6. Weight budget — is the 5/6/4/3/3/2 tilt right, or push even harder onto workouts + connections?
7. Ship order — **no data blockers remain**; full model is buildable now (only the dam list
   for Cat-5 is outstanding, and that category can ship with the sire list alone as v0).
