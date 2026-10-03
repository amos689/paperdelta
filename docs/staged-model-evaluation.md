# Staged local model experiment

[简体中文](zh-CN/staged-model-evaluation.md)

On 2026-10-03, Qwen3-8B Q4_K_M completed two separately recorded staged experiments.
The v2 run stopped at an invalid first action in all twelve cases. After publishing
enum choices and available stages, v3 produced three valid actions across fifteen
actions, but all twelve cases still ended at an invalid action. Neither run produced
a valid proposal, reference identity match or required abstention. Nothing was
accepted. This model has not demonstrated reliable use of the staged interface.

The author-written controls constructed all nine reference mappings through the
same builder. The three scripted abstentions are controls, not model measurements.
Structural correctness of that builder is distinct from a model's ability to use it.

| Measurement | Staged v2 | Staged v3 |
| --- | ---: | ---: |
| Cases / actions returned | 12 / 12 | 12 / 15 |
| Valid actions / core-valid proposals | 0 / 0 | 3 / 0 |
| Identity contract matches | 0 of 9 | 0 of 9 |
| Expected abstentions | 0 of 3 | 0 of 3 |
| Retries / response repairs / accepted bindings | 0 / 0 / 0 | 0 / 0 / 0 |
| Independent participants | 0 | 0 |
| Human precision / confirmation time | Unmeasured | Unmeasured |

The v3 [protocol](evidence/local-model-staged-v3/protocol.json),
[score](evidence/local-model-staged-v3/score.json),
[controls](evidence/local-model-staged-v3/controls.json) and
[raw execution](evidence/local-model-staged-v3/) preserve the follow-up separately.
Examples of remaining errors are an unsupported source format and an aggregation
without an explicit expected record count. Both local servers were stopped.

The [protocol](evidence/local-model-staged-v2/protocol.json) pins source bytes,
all frozen v1 case bytes, initial prompts and model/runtime provenance. Every
request was saved before inference; raw responses, stage errors and timing are
under [the run directory](evidence/local-model-staged-v2/). The
[score](evidence/local-model-staged-v2/score.json) and
[controls](evidence/local-model-staged-v2/controls.json) are separate records.
The owned loopback server was [stopped after the run](evidence/local-model-staged-v2/server-lifecycle.json).

Each independent case supplied raw project files, its request, a read-only scan
and flat stage schemas. The harness carried the draft in memory; the model had no
filesystem or shell access. It could choose source, metric, derived, locations,
finish or abstain, with up to eight actions. Invalid actions ended the case without
retry. No oracle, other-case context, quick-start example or scorer feedback entered
the prompts. The developer authored and knows the suite; this is not a blind study.

Sampling retained temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5,
repeat penalty 1, seed 20261003 and disabled thinking. The per-action output limit was
2048 tokens; context was 16384 tokens. Plain JSON syntax was constrained, not an
answer schema. This used the same pinned local model/runtime files as the
[one-request experiment](local-model-evaluation.md), with their hashes reverified.

The scorer reports exact reference contract matches and a second identity comparison
that ignores **only** `expected_count`: the builder adds an explicit count guard to
aggregations, while some older references omitted it. Scope, source identity, seeds,
unit, aggregation, derivation, display and target position remain exact. Neither
metric is independent human precision or general model accuracy. The protocol differs
from v1 in implementation, interface and possible request count, so it is not a
controlled causal comparison of interface quality.

The first run exposed an interface issue worth improving independently of this model:
stage schemas used broad strings for several enum arguments, and the response did
not explicitly list currently available stages. The v3 run tests those improvements
with the same budgets and sampling settings. It is an observed follow-up, not an
independent held-out study. The failed v2 run and original v1 run remain unchanged.

Use commit `fb8b00e` for the exact v2 implementation. The current v3 protocol pins
its own files; a later checkout can replay it only when those hashes match.

Reproduce a matching checkout with:

```sh
python -m tools.evaluate_staged_mappings controls --directory build/staged-controls.json
python -m tools.evaluate_staged_mappings prepare --directory build/staged-run --model MODEL --provenance provenance.json
python -m tools.evaluate_staged_mappings run --directory build/staged-run --endpoint http://127.0.0.1:PORT/v1/chat/completions
python -m tools.evaluate_staged_mappings score --directory build/staged-run
```

Use new output paths. The runner verifies its pinned implementation and cases; a
different implementation requires a new preparation. It never updates the original
v1 lock or rewrites a saved model answer. Runtime files and model weights remain
optional local scratch dependencies and are not distributed with PaperDelta.
