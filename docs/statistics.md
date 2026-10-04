# Declared statistics and uncertainty

[简体中文](zh-CN/statistics.md)

PaperDelta 1.0 can check a mean, SD, SE, sample count, confidence level and interval
against the same explicitly identified observations. It can bind an entire
`mean ± spread` or `[lower, upper]` expression in LaTeX, Word and PDF. The meaning
of `±` comes from your declaration; the program does not guess it from the values.

Start with the [five-seed example](../examples/seed-statistics/README.md).
TSV, CSV, static Excel and [portable experiment exports](experiment-evidence.md)
share the calculation. Statistical bundles require tabular observation identities;
raw JSON arrays retain the existing scalar/mean/count workflow.

## Declare the observations

```yaml
schema_version: 6
paper: {entry: paper.tex}
sources:
  runs:
    path: results.tsv
    format: tsv
    primary_key: [model, seed]
    columns: {model: string, seed: integer, accuracy: decimal}
metrics:
  accuracy:
    source: runs
    field: accuracy
    where: {model: method}
    reduce: statistics
    unit: percent
    expected_count: 5
    seed_column: seed
    expected_seeds: [1, 2, 3, 4, 5]
    statistics:
      ddof: 1
      unit_of_analysis: independent experimental seed
      confidence_interval:
        method: student_t
        level: '0.95'
        assumption: independent_normal_observations
```

One selected row represents one observation. List all expected IDs, not just the
IDs left after dropping failures. `seed_column` can name another observation ID
column, but its declared type must be string or integer. The list, selected IDs
and expected count must agree. Duplicate seeds, absent seeds, missing measurements
and nonfinite values produce **unknown** results. No observations are dropped,
filled with zero or silently averaged across repeated steps.

An MLflow/W&B history often contains many rows per seed. Select a specific run,
metric, step or checkpoint as needed so each observation has one result. The
selection must also distinguish dataset/split/model identity. Equal numbers do not
establish those identities. Offline imports retain their original precision limits.

## Declare the convention

- `ddof: 1` uses the sample variance divisor `n − 1`; `ddof: 0` uses `n`.
- SD is the square root of that variance; SE is that declared SD divided by `sqrt(n)`.
- `n` counts complete numeric observations, after the full expected-ID check.
- The two-sided Student-t interval uses the sample SD (`ddof: 1`), `n − 1` degrees
  of freedom and the declared confidence level. Its endpoints are
  `mean ± t((1 + level)/2, n − 1) × SE`.

The sampling assumption is an author declaration. PaperDelta cannot verify that
seeds, subjects or measurements are independent or normally distributed. Repeated
measurements from one subject are not made independent by assigning different IDs.
Omit `confidence_interval` when no supported interval is intended. Prediction
intervals, bootstrap intervals, weighted/paired/clustered analyses and hypothesis
tests are not implemented. A larger mean or nonoverlapping intervals do not cause
an automatic significance claim.

The formula follows [NIST's mean confidence interval](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)
and [scale definitions](https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm).
Tests also use [NIST's t table](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm)
and the independent closed-form Cauchy quantile at one degree of freedom.

## Bind what the paper actually displays

Each occurrence names the statistical metric and an explicit display component:

| Component | Example | Meaning |
| --- | --- | --- |
| `mean`, `sd`, `se` | `82.00`, `1.58`, `0.71` | A single declared statistic |
| `n` | `5` | Use `display.kind: integer` |
| `confidence_level` | `95\%` | Use percent display with zero places for a 95% level |
| `ci_lower`, `ci_upper` | `80.04`, `83.96` | An independently located endpoint |
| `mean_sd`, `mean_se` | `82.00 \pm 1.58` | Mean and the explicitly chosen spread |
| `ci`, `mean_ci` | `[80.04, 83.96]` | Interval, optionally preceded by the mean |

```yaml
occurrences:
  abstract_result:
    file: paper.tex
    anchor: {prefix: 'Accuracy: $', suffix: '$.'}
    metric: accuracy
    display:
      kind: decimal
      places: 2
      statistics: {component: mean_sd, show_n: true}
```

This declaration expects a complete expression such as
`82.00 \pm 1.58 (n = 5)`. `show_n: false` omits that suffix. `spread_places` can
declare different decimal places for SD/SE or interval endpoints; otherwise the
ordinary `places` applies to all components. `confidence_level` always uses a
fraction quantity, independently of the experiment's unit.

Literal Unicode `±` and LaTeX `\pm` are recognized. Supported compound grammar is
`mean ± spread`, `[lower, upper]`, or `mean [lower, upper]`, optionally followed
by `(n = integer)`. Whitespace is flexible. A percent display with symbols expects
the symbol on each numeric result component. Shared trailing-percent notation,
asymmetric `+a/−b`, arbitrary macros and multi-cell compounds are not inferred;
bind supported individual components or revise the declaration explicitly.

## Studio, terminal and agents

In Studio select **Declared statistics**, fill the complete seed list, choose the
SD convention and analysis unit, and optionally declare the interval assumption
and level. Then choose the display component. For a compound, select **every
number in one expression**, including n when present, and stage it as one binding.
Each paper location stays independent. Mean and interval displays can reuse one
metric with separate anchors. Language switching preserves the unfinished choices.

The same controls are available in batch setup and reusable experiment templates.
Batch one complete compound per metric per staging operation; stage another
occurrence separately. Templates transfer statistical conventions, not positions.
Inspect the complete expression, typed experiment identity and statistics before
accepting the proposal.

`paperdelta guide`, `paperdelta batch guide`, JSON binding proposals and optional
MCP draft/batch tools use the same contracts. MCP remains read-only. For a broken
compound anchor, choose its **first numeric component** in the repair view and
inspect the entire proposed expression before accepting. LaTeX corrections use the
existing preview/backup/transaction safeguards; Word/PDF remain read-only.

## Numerical and compatibility limits

Input lexemes are parsed without a binary-float conversion. Mean and variance
moments use exact rational arithmetic; square roots and division use at least
80 significant decimal digits. Large observations increase this to at most 260.
The new statistical path accepts up to 10,000 observations, 100 significant digits
per observation, and exponents and magnitudes within ±200. Existing scalar limits
remain unchanged. Confidence levels are exact strings from `0.5` through `0.999`,
with up to six decimal places.

Student-t quantiles use an isolated [mpmath context and regularized incomplete beta function](https://www.mpmath.org/doc/current/functions/gamma.html#betainc),
bounded bracketing/bisection and a residual check. Irrational results and interval
endpoints are numerical approximations. The report records precision, algorithm,
quantile-engine version, method, level, df, n and the declared analysis unit.
No claim of exact statistical inference follows from exact evidence parsing.

Configuration/report schema 6 carries these new fields. Schemas 1–5 and legacy
scalar/CSV/JSON identities remain readable and unchanged. Accepting a statistical
proposal upgrades the configuration through normal review and backup. Old accepted
metrics retain their meaning; selecting `statistics` is an explicit new declaration.
Derived arithmetic and comparison claims referencing a statistical metric use its
**mean**; they do not automatically compare uncertainty or test significance.
