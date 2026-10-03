# Local model proposal experiment

[简体中文](zh-CN/local-model-evaluation.md)

This is the preserved one-request a2-era baseline. The v0.2
[staged experiments](staged-model-evaluation.md) have separate protocols and results.

On 2026-10-03, one local **Qwen3-8B Q4_K_M** run produced twelve JSON answers.
All twelve proposals were invalid; none were accepted. This configuration is
**not recommended for unattended mapping**. Its three required abstentions were
also missed. These failures remain in the published evidence.

| Measurement | Observed result |
| --- | ---: |
| Cases / independent requests / attempts per case | 12 / 12 / 1 |
| Completed JSON answer envelopes | 12 |
| Proposals accepted by the core validator | 0 |
| Invalid proposals | 12 |
| Reference targets matched | 0 of 9 mappable cases |
| Expected abstentions returned | 0 of 3 |
| Retries / answer repairs / accepted bindings | 0 / 0 / 0 |
| Independent participants | 0 |
| Human precision / confirmation time | Unmeasured |

The [frozen score](evidence/local-model-v1/score/report.json) distinguishes an
answer envelope from a valid mapping. The [saved submission](evidence/local-model-v1/submission.json)
was scored unchanged. All twelve exact requests, raw HTTP responses and
per-case execution records accompany the
[pre-inference protocol](evidence/local-model-v1/protocol.json) and
[execution record](evidence/local-model-v1/execution.json).

## What the model saw

Each request contained only its exported project, request, read-only scan,
proposal-input schema, and the generic rules and agent guide. It had no tools,
filesystem access, other-case conversation or scoring feedback. Reference files
and controls were excluded. The complete quick-start example was not supplied;
this was a schema-and-documentation baseline, not the best achievable agent setup.
The developer authored the suite and knows its answers, so this is not a blind
independent study or a representative sample of papers.

The requests were saved and hashed before the first inference. Plain JSON syntax
was constrained, but no answer schema or reference values were forced. Sampling:
temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5,
repeat penalty 1, seed 20261003, 4096 maximum output tokens. Thinking was disabled.
One request occupied a 16384-token context with prompt caching disabled. All
responses finished normally; none reached the output limit.

The official [Qwen model repository](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/7c41481f57cb95916b40956ab2f0b139b296d974)
was pinned at `7c41481f57cb95916b40956ab2f0b139b296d974`. The 5,027,783,488-byte
GGUF SHA256 is `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
The official [llama.cpp b11146 binaries](https://github.com/ggml-org/llama.cpp/releases/tag/b11146)
reported build 11146, commit `7fe450e19`. The CUDA 13.4 archives and model file
matched publisher digests. Execution used the recorded Windows RTX 5080 Laptop
GPU. The server listened on loopback, loaded the local model offline, and disabled
its web UI and MCP proxy. It was
[stopped after the run](evidence/local-model-v1/server-lifecycle.json).
Portable runtime files and weights remain ignored local dependencies; they are
not part of PaperDelta's package or runtime requirements.

## AI developer assessment

This is Codex's inspection of the recorded suggestions, not an observed human
review. The scorer's human review fields remain null.

| Cases | Concrete problems in the original suggestions |
| --- | --- |
| C01–C03 | Invented derived means or a three-operand difference; missing metric definitions; source paths used as IDs |
| C04 | Unqualified rationale keys; subtracting fraction and percentage columns is not the requested mean |
| C05 | Invalid source ID and incomplete predicate; occurrence refers to an undefined metric |
| C06 | Undeclared source and unsupported derived mean; individual seed references do not fix these defects |
| C07 | Dot-style field instead of the requested JSON Pointer; nonexistent source declarations |
| C08 | Invalid source reference and wrong unit; explanation incorrectly calls the stale paper value consistent |
| C09 | Ambiguous identical-value anchor, unsupported derived mean and extra claim |
| C10 | Selects a dataset despite absent identifying evidence |
| C11 | Attempts a mean with a required seed missing |
| C12 | Treats an accuracy difference as a p-value without significance-test evidence |

The core rejected the malformed proposals before confirmation or paper writes.
This does not prove it can detect every plausible but scientifically wrong
mapping: the separate negative controls demonstrate that incorrect experiment
identities can still have matching numbers. Evidence review remains necessary.

My acceptance decision covers the deterministic checker, explicit binding
workflow and agent interfaces. It does not approve this small-model configuration
as an automatic mapper. A separate
[AI developer walkthrough](evidence/developer-first-use/evidence.json) completed
ten explicit bindings, eight data-change findings, patching and recovery using the
documented interface. Its synthetic inputs and mappings were authored by the same
developer; it is neither a replacement model score nor an independent user trial.

## Reproduce the run structure

Use the matching historical a2 source distribution and a separately installed loopback model
server. Record the actual model/runtime provenance as JSON, then:

```sh
python tools/evaluate_mappings.py export --out build/fresh-model-inputs
python tools/run_local_mapping_eval.py prepare --inputs build/fresh-model-inputs --out build/fresh-model-run --model Qwen3-8B-Q4_K_M --provenance model-provenance.json
python tools/run_local_mapping_eval.py run --directory build/fresh-model-run --endpoint http://127.0.0.1:8080/v1/chat/completions
python tools/evaluate_mappings.py score --submission build/fresh-model-run/submission.json --out build/fresh-model-score
```

The harness refuses to reuse a started run, verifies prepared request hashes and
preserves failures. Scoring never calls the model. New prompts, thinking modes,
models or validation-feedback loops require new records; they must not replace
this result. GPU execution need not reproduce identical sampled bytes.
