# Mapping sessions: preserved real-model runs for 1.4

[简体中文](README.zh-CN.md)

These are real local Qwen3-8B Q4_K_M responses, not scripted model answers. The
twelve synthetic tasks and original scorer are unchanged from mapping-v1. The
developer owns and has already seen the suite; neither run is a new blind or
independent human study. No binding was accepted during inference.

| Measure | First frozen run | Corrective revision |
| --- | ---: | ---: |
| Tasks | 12 | 12 |
| Core-valid proposals | 5 | 9 |
| Complete reference mapping, out of 9 mappable tasks | 0 | 0 |
| Candidate identity-contract mismatches | 5 | 9 |
| Correct required abstentions, out of 3 | 0 | 0 |
| Invalid actions | 30 / 59 | 19 / 60 |
| Sessions exhausting the correction budget | 7 | 3 |
| Inference-call wall time | 161.499 s | 181.061 s |
| Prompt tokens | 262,210 | 316,603 |
| Completion tokens | 8,127 | 8,026 |
| Paid API cost | USD 0 | USD 0 |

Electricity and hardware amortization were not measured. Hardware, model/runtime
hashes and startup/lifecycle timing are recorded in each protocol and server log.
Both owned model processes were stopped after the runs. No model weights or runtime
binaries are distributed with PaperDelta.

The first run repeatedly used file paths or phrases as identifiers and omitted
table contracts. The corrective revision adds identifier patterns, bilingual field
descriptions, nested validation field paths and a more readable proposed key order.
It was informed by these observed failures. Its implementation and prompts were
frozen separately before inference; the first run was not replaced. The task, seed,
model and correction budget stay the same between these two runs. Comparison to
older staged-v3 also changes prompts, product and action/error budget, so it does
not isolate a single cause.

More structurally valid proposals did **not** produce a correct complete mapping.
The second run still confuses source units, display precision and explicit identity
contracts, and proposes in two tasks requiring abstention. One otherwise promising
proposal also differs in ordered identity-key contract. The scorer is unchanged:
ordered keys, source identity, unit, display and original position all matter.
The supplementary identity comparison ignores only the builder's mandatory count
guard; it does not weaken the other reference fields. Budget exhaustion is a failure,
not an abstention. Do not interpret model wording such as “successfully mapped” as
deterministic verification or scientific approval.

- First protocol, input hashes, source snapshot and raw responses: [protocol.json](protocol.json),
  [implementation](implementation/), [execution.json](execution.json), [score.json](score.json).
- Corrective revision: [protocol](revision-2/protocol.json),
  [execution](revision-2/execution.json), [score](revision-2/score.json).
- Every API request, unchanged response, feedback and timing record is under `cases/`
  in the corresponding run. The initial prompts contain only the task, project,
  discovery, source hints and typed product schemas. Reference answers enter scoring
  after inference; they never enter prompts or correction feedback.

Replay saved model actions without invoking a model:

```sh
python tools/replay_mapping_v4.py --out build/mapping-replay
```

This verifies both frozen implementations and input identities, then checks each
recorded status/error and final proposal. It is a deterministic regression using
recorded real responses, not fresh inference. To conduct a new inference run, use
`python tools/evaluate_mapping_v4.py prepare --directory build/new-mapping-study`
with a new directory and a literal-loopback
OpenAI-compatible local endpoint; preserve the new protocol and all outcomes.

The final release opens joint-review evidence tables and preserves checkbox focus
after a redraw. That browser-only change follows the second model freeze; its exact
file hashes are listed in [release adjustments](../../docs/assets/v1.4/release-adjustments.json).
The two frozen model implementations and their results remain unchanged.

Original PaperDelta code and authored task material retain the repository MIT
license. The cached Qwen model is Apache-2.0 and llama.cpp is MIT, as recorded in
the existing third-party notices and runtime provenance; neither is bundled here.
