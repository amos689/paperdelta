# Agent mapping study for 2.0

[简体中文](README.zh-CN.md)

The [protocol](PLAN.md) was committed before product changes. The 24 authored
tasks in [tasks/manifest.json](tasks/manifest.json) contain twelve development
and twelve held-out cases, each with eight mappings and four required abstentions.
English and Chinese requests each account for half the cases. All five manuscript
formats are represented. These are owned synthetic inputs under the repository's
MIT license, not independently annotated research papers or a human user study.

The generator is [create_mapping_v5.py](../../tools/create_mapping_v5.py).
Its first generation stopped at the Excel case because the optional fixture
generation dependency `openpyxl` was absent. After installing `openpyxl==3.1.5`,
a second generation completed. Before freezing, the Chinese requests were fully
translated and runtime/generator provenance was added. No model call or product
tuning occurred during these preparations. The first failure and the intermediate
outputs remain in local build directories; their receipts are in
[preparation.json](preparation.json). Excel reading in the product does not require
openpyxl.

Experiment identities, units, reduction and expected decisions come from the
authored specifications. Original Word/PDF locations were produced by the existing
1.9 parser and checked visually on the original rendered documents. They are not
independent native-parser ground truth. All eight native originals were inspected:
the values and table cells are readable, no text is clipped, and rendering did not
change source bytes. Poppler emitted missing display-font warnings for Symbol and
ArialUnicode while rendering Word exports; the actual ASCII test text rendered
correctly. See [visual evidence](visual/evidence.json).

No inference score is available at task freeze. The held-out suite is held out
from inference-driven tuning, not from its authors. Its first model outcomes must
be preserved and opened only after product and prompt freeze. Reference answers
and control outputs must never be included in model input.

## Recorded inference results

All five runs used real local Qwen3-8B Q4_K_M inference. Complete mapping requires
the declared source, identity, selection, count, units, computation, display and
original manuscript location to satisfy the frozen strict contract. Producing a
valid proposal or matching a number alone does not count as a complete mapping.

| Preserved run | Complete mappings | Explicit abstentions on required cases | Invalid actions / all actions | Prompt / completion tokens | Observed inference seconds |
| --- | --- | --- | --- | --- | --- |
| [Old-task regression 1](runs/regression-1/score.json) | 0/9 | 0/3 | 32/57 | 418,175 / 9,315 | 222.516 |
| [Development 1](runs/development-1/score.json) | 1/8 | 0/4 | 33/57 | 437,803 / 9,986 | 243.997 |
| [Old-task regression 2](runs/regression-2/score.json) | 0/9 | 0/3 | 20/55 | 389,243 / 8,219 | 197.860 |
| [Development 2](runs/development-2/score.json) | 0/8 | 1/4 | 21/50 | 384,348 / 7,626 | 194.845 |
| [First held-out run](runs/held-out-1/score.json) | 1/8 | 2/4 | 25/48 | 362,571 / 7,140 | 180.922 |

The selected second implementation has clearer typed statistical contracts and
general stage guidance, but its development complete-mapping score fell from 1/8
to 0/8. The [selection rationale](selection-rationale.json) records this tradeoff
before the [implementation and prompt freeze](selection-freeze.json). There was
no tuning after the held-out results. These results do not demonstrate improved
mapping accuracy or support autonomous mapping. Explicit abstention here means
a nonempty reason on a required-abstention case; the semantic quality of that
reason was not independently assessed. Budget exhaustion is not abstention.

In the first held-out run, H02 was the only complete mapping; H06 produced an
incorrect proposal, H04 unnecessarily abstained, H11 and H12 explicitly abstained
on required cases, and the other seven cases exhausted their budgets. The
[raw run directories](runs/) retain every request, response, tool feedback,
proposal, failure, score, initial prompt and implementation snapshot. The
[results summary](results-summary.json) records 267 actions, 2,034,426 total
tokens and 1,040.140 seconds of observed inference across all five runs.
Paid API charges were USD 0; electricity and hardware cost were not measured.
Concurrent development tests ran during part of the study, so these timings
are observed call costs, not isolated speed benchmarks. No binding was accepted.

## What changed and what stayed fixed

The [development record](development-adjustments.json) preserves initial machine
failures and the first model diagnoses. The second round added actual typed
statistical schemas and clearer source/unit/count/selector guidance. Its client
sent author notes as plain text and retained the latest cumulative session state
and one previous action, removing obsolete initial state from follow-up requests.
Model weights, sampling parameters, tasks, reference answers, strict scoring and
the 16-action / 3-invalid-action / 2,048-completion-token budgets stayed fixed.
Product and client prompts both changed; the study cannot isolate either effect.

The [old-failure diagnosis](known-failure-diagnosis.json) retains the original
0/9 mapping and 0/3 abstention result and distinguishes the old evaluator's
actual order-insensitive primary-key/seed comparisons from its archived prose.
The new old-task regression records the mandatory count guard separately; it
does not silently replace or rescore the original result. New tasks require
their complete count contract and exact native positions.

Thirteen authored reference/adversarial controls test deterministic behavior with
zero model calls. Sixty recorded cases also replay successfully through their
own frozen implementations. Neither result is a fresh model success rate, an
independent annotation study, a human precision score or a confirmation-time
measurement. See the [release acceptance](../../docs/v2.0.md).

## Reproduce the recorded actions

From the matching source checkout with development dependencies installed, run:

```sh
python tools/replay_mapping_v5.py --out build/mapping-v5-replay
```

Use a new output directory. The command makes no model calls and needs no model
weights. It verifies the [study inventory](study-index.json), copies each frozen
implementation into a fresh replay directory, executes the recorded actions and
checks the feedback, proposals and strict scores. The original snapshots remain
unchanged. The old protocol lock omitted itself from its own identity list, so
the regression snapshot copier did not include that metadata file. The
[replay supplement](replay-support.json) pins its unchanged bytes from `ca42e68`
and supplies them only to fresh replay copies. The first failed replay and
subsequent successful replay are retained in the release acceptance assets.
Interpreter-generated bytecode was excluded from the study inventory; no
authored input or recorded inference source/output was changed.

Fresh inference is a different experiment. Run
`python -m tools.evaluate_mapping_v5 --help` for `prepare`, `run`, `score` and
`freeze`; use fresh output paths,
an explicitly started loopback model server and its actual provenance. The
[recorded runtime](runtime/run-3/model-provenance.json) contains the model revision,
weight hash, llama.cpp b11146 identities, launch command and sampling parameters.
The model and runtime binaries are not bundled. Matching a seed does not promise
identical generation across hardware or runtime versions. All these inputs are
now observed: future inference on them is regression, not a new held-out study.
