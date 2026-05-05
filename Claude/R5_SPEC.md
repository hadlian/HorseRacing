# R5 Model Specification

**Version:** R5_v3.2-R4C
**C suffix:** Continuous Trend (as opposed to prior discrete ±5/0 implementation)
**Authoritative code:** `r5_parser_v2.py`

---

## Model Integrity Rules

1. `R5_SPEC.md` defines the approved model version.
2. `r5_parser_v2.py` is the current executable implementation of R5_v3.2-R4C.
3. If this document and the code disagree, treat it as a model-control conflict. Do not proceed with changes until the human steward resolves it.
4. No scoring logic (WS4, Trend, FCI, Composite weights) may be changed without an explicit version bump and approval.
5. Documentation updates do not require a version bump. Logic changes do.
6. The version string in this file must be updated whenever scoring behavior changes.

---

## WS4 — Weighted Speed Figure

Weighted average of the last 4 BRIS speed figures on the **same surface as today's race**.
Figures from a different surface are excluded before weighting.

```
WS4 = 0.4×S1 + 0.3×S2 + 0.2×S3 + 0.1×S4
```

- S1 = most recent figure, S4 = oldest
- Weights are re-normalised if fewer than 4 figures are available
- If fewer than 2 same-surface figures exist, current code falls back to valid BRIS speed figures regardless of surface. This fallback is documented behavior in R5_v3.2-R4C.

---

## Trend — Continuous Form Direction

Measures whether S1 is improving or declining relative to the horse's recent average.

```
Trend = round(clamp((S1 - Avg(S2..S4)) / 2.0, -5.0, +5.0), 1)
```

- `S1` = most recent same-surface BRIS figure
- `Avg(S2..S4)` = mean of all remaining available same-surface figures
- Result clamped to `[−5.0, +5.0]` before rounding
- Rounded to 1 decimal place
- Returns `0` if fewer than 2 figures are available (no trend signal)

**Examples:**

| S1 | Avg(S2..S4) | Raw diff | ÷2 | Trend |
|----|-------------|----------|----|-------|
| 102 | 97 | +5 | +2.5 | +2.5 |
| 95 | 100 | −5 | −2.5 | −2.5 |
| 108 | 88 | +20 | +10.0 | +5.0 (capped) |
| 80 | 100 | −20 | −10.0 | −5.0 (capped) |

---

## FCI — Form/Class Index

```
FCI = WS4 + Trend
```

FCI is then normalised to a 0–10 scale for the composite:

```
fci_n = clamp((FCI - 60) / 6, 0.0, 10.0)
```

---

## Composite Score

Final score on a 0–10 scale. Computed in two passes inside `finalize_field()`.

| Component | Weight | Field |
|-----------|--------|-------|
| FCI (WS4 + Trend) | 25% | `fci_n` |
| Class vs Speed Par | 20% | `class_n` |
| Bias / Pace Fit | 15% | `bias_n` |
| Trainer / Jockey | 10% | `tj_n` |
| Form Angle | 10% | `form_n` |
| Pedigree | 10% | `ped_n` |
| Value vs ML | 10% | `val_n` |

```
Composite = fci_n×0.25 + class_n×0.20 + bias_n×0.15
          + tj_n×0.10  + form_n×0.10  + ped_n×0.10 + val_n×0.10
```

Pass 1 (`pre_comp`): uses a placeholder `val_n = 5.0` and post position for `bias_n`.
Pass 2 (final `comp`): recalculates with field-context `val_n` (rank divergence) and pace scenario fit baked into `bias_n`.

---

## Confidence Tiers

| Composite | Tier |
|-----------|------|
| ≥ 8.5 | HIGH |
| 7.5 – 8.4 | SOLID |
| 6.5 – 7.4 | FAIR |
| < 6.5 | SPECULATIVE |

---

## Version History

| Version | Change |
|---------|--------|
| R5_v3.2-R4C | Confirmed continuous Trend in code; spec formalised |
| R5_v3.2-R4 | Continuous Trend implemented in r5_parser_v2.py (replaced discrete ±5/0) |
| R5_v3.1 | Two-pass finalize_field(); pace scenario; value as rank divergence |
| R5_v3.0 | Initial r5_parser_v2.py; WS4 surface filtering; actual T/J win % |
