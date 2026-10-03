# Mapping contracts, version 1

Twelve original synthetic numeric-mapping tasks. These files are PaperDelta
fixtures under the repository's MIT license, not extracts from research papers.
No model run or independent user trial is supplied as a result.

Nine tasks have declared reference mappings; one accepts either fraction or
percentage storage, giving ten reference formulations. Three require abstention:
missing experiment identity, a missing required seed, and absent significance-test
evidence. The other cases exercise split, dataset, model variant, textual IDs,
units, percentage points, JSON Pointer, a stale number and identical table cells.

Each case has a public `project/` and `request.md`, plus a separate `oracle.json`.
The oracle records the manually specified numeric span, complete declarations and
expected reference behavior. All fields are visible in the repository. Use the
export command and a separate workspace to keep answers out of a model's context.
This is a context-separation procedure, not proof of a blind independent study.

## Reproduce

From an environment containing this checkout's matching implementation:

```sh
python tools/evaluate_mappings.py export --out build/mapping-inputs
python tools/validate_mapping_controls.py --out build/mapping-controls
python tools/evaluate_mappings.py score --submission saved-submission.json --out build/mapping-score
```

The export contains twelve projects, requests, schemas and an empty submission
template. Scoring uses saved output; it does not call a model or accept mappings.
Keep the raw model output and disclose model identity, context, attempts and
format repairs. Missing cases remain missing; do not remove failed attempts.

For a real observed review, fill the generated `review.template.json`, leaving
unobserved values null. Rescore with `--reviews observed-review.json` and a new
output directory. A review is bound to the exact submission bytes. This does
not authenticate the observer or create a first-time-user trial.

## What is scored

1. Structural validity using the actual PaperDelta proposal validator.
2. The requested byte span, independent of the model's chosen binding ID/anchor.
3. A reference contract: source declarations, typed selectors, field, aggregation,
   run completeness, units, derived operands and display. IDs are normalized;
   known fraction/percent alternatives are explicitly listed.
4. Abstention, missing/invalid cases and duplicate target suggestions separately.
5. Optional declared human verdicts and confirmation times.

Reference differences are not automatically counted as scientifically incorrect:
equivalent unlisted formulations may need adjudication. Matching numeric values
cannot substitute for matching experimental identity. A structurally valid
proposal can produce a mismatch because the manuscript is stale.

Candidate precision and ambiguity rate are null until every countable candidate
in a declared model run has an observed review. Invalid candidates with known
occurrence IDs remain in the denominator; uncountable malformed proposals disable
precision. Missing cases and abstentions are reported alongside candidate metrics.
Controls never produce measured model precision or confirmation times.

This small authored suite is neither representative real-paper accuracy nor a
test of automatic scientific reasoning. It does not meet the development plan's
model-quality or independent-user gates by itself.

## Protocol

`protocol-lock.json` fixes every suite file, generator, scorer and core source
file before model evaluation. The freeze command only creates a new lock and
refuses to overwrite one. Changed inputs or code require a separately versioned
suite and retained previous records. The controls test the scorer; their known
answers are not predictions and must never be relabeled as model output.
