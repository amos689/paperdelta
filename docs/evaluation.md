# Measured behavior and limits

[简体中文](zh-CN/evaluation.md)

The original corpus/performance studies below retain their a1/a2 identities.
The v0.2 [regression](evidence/corpus-bilingual-v3.json) reproduces all 150 outcomes
(126 full expectations pass; 24 known failures remain). Its 20-run warm P95 is
1.731 s on the recorded laptop ([performance](evidence/v0.2-performance.json)).
These use previously seen inputs, not new held-out samples. See the
[v0.2 acceptance record](v0.2-acceptance.md) and [staged model results](staged-model-evaluation.md).
Replay old studies with their preserved implementations via `tools/replay_study.py`;
run `tools/regress_corpus.py --out build/new-regression` for the current runtime.

These are development measurements, initially on Windows 11 / Python 3.12.14.
Protocols, source hashes, failures and raw per-case outcomes are retained so the
numbers can be examined independently. The separate
[local acceptance decision](release-acceptance.md) uses these scoped results.

The full repository includes the corpus. Python distributions exclude the
separately licensed paper sources and corpus-output JSON; a matching evaluation
bundle preserves them unchanged. See [candidate artifact instructions](local-validation.md).

## Real-source fault injection

Ten licensed manuscripts provide ten manually annotated numeric literals.
Five development papers and five held-out papers were selected before running
the parser on the held-out group. Fifteen predeclared, correlated scenarios per
paper exercise changes, source identity, incomplete data, unknowns and writes.
Evidence CSVs are synthetic, not original experimental records.

| Split / paper | Complete expectations matched | Original literal | Numeric patch and recovery |
| --- | ---: | --- | --- |
| Development: ml-finance | 15/15 | pass | byte-exact |
| Development: rf-curriculum | 15/15 | pass | byte-exact |
| Development: hwo-bows | 15/15 | pass | byte-exact |
| Development: legwork | 15/15 | pass | byte-exact |
| Development: reflectometry | 15/15 | pass | byte-exact |
| Held-out: coronal-abundances | 15/15 | pass | byte-exact |
| Held-out: ce-accretors | 15/15 | pass | byte-exact |
| Held-out: pzflow | 15/15 | pass | byte-exact |
| Held-out: rossby-ridge | 3/15 | unknown: dynamic TeX | refused |
| Held-out: centre-of-mass | 3/15 | unknown: dynamic TeX | refused |

Final development: **75/75**. First held-out run: **51/75**. Combined complete
expectations: **126/150**, not 150/150. Two held-out manuscripts use body-level
dynamic definitions such as `\let`; the conservative parser blocks the document
instead of inferring rendered content. Their sources and failed cases remain.
This is an observed compatibility limitation, not an invitation to disable the
guard. Such constructs were already outside the declared static-LaTeX subset.

Looking only at consistency states, **136/150** matched. The ten additional
failures in complete expectations concern the expected occurrence-level error:
the report detects the data problem as a metric diagnostic, but the occurrence
itself is already blocked by unsupported TeX. We retain the original stricter
expectations instead of changing the score after seeing results.

Among 40 predeclared no-mismatch scenarios, 32 passed and 8 were unknown; none
were falsely called mismatches. For the ten data-only mismatch scenarios,
8 mismatched and 2 were unknown; none silently passed. **8/10** real-text repair
cases were applicable, preserved every byte outside the intended replacement,
rechecked and restored exactly; the other two refused to modify unsupported
content. All eight applicable stale patches were rejected. These small,
correlated counts do not establish a population false-positive rate below 5%.

Whole-paper coverage remains low by design: only one result per paper is bound.
The eight checkable papers expose 37–555 numeric candidates and 27–884 unsupported
construct notices each. An entirely blocked document exposes zero *checkable*
candidates, not zero numbers. Candidates include non-results; their unbound
fraction is not scientific-result recall.

The first development pass matched 71/75 and exposed a parser exception-handling
defect plus invalid math delimiters in some injected cases. Those were fixed
before the held-out protocol was locked. Licensing review also corrected the
reflectometry paper's manuscript-specific CC BY-SA declaration; source bytes and
split were unchanged.

Evidence: [first development](evidence/corpus-development-first.json),
[final development](evidence/corpus-development.json),
[first held-out](evidence/corpus-held-out-first.json),
[corpus, annotations and reproduction commands](../tests/corpus/README.md).

### Versioned regression after the first evaluation

Version 0.1.0a2 adds terminal confirmation and AST-based abstract/table priority
hints in discovery. Its study is `interactive-confirmation-v2`; the named lock
includes current source files, evaluator and input identities. The original
lock and implementation snapshot remain available. Current commands evaluate
**previously seen** papers and cannot replace the first held-out result above.
The [a2 regression](evidence/corpus-interactive-v2.json) and
[original implementation replay](evidence/corpus-original-replay.json) both
matched every original per-case outcome, including the 24 complete-expectation
failures. Neither run adds unseen samples.
The [corpus README](../tests/corpus/README.md) describes both a2 and original
replay commands.

## Performance

The deterministic generated workload has 20 TeX files, 500 different bound
metrics, 10,000,047 CSV bytes and 101,611 records. Each metric selects three
records; remaining records have independent identities. All 500 checks must pass
before a timing counts.

Hardware: Intel Core Ultra 9 275HX, 24 logical processors, approximately 32 GiB
RAM. With the final report contract enabled, the fresh-process core check took
**1.563 seconds**; 20 subsequent checks had empirical nearest-rank **P95 1.724
seconds**. Every run creates a fresh checker and rereads all inputs. Interpreter
startup, imports, model calls, report rendering and training are excluded; the
operating system's file cache is not flushed. This fast laptop is not evidence
for every ordinary laptop or every CSV layout.

An initial check took 22.429 seconds, followed by a 24.410-second warm check.
Profiling identified repeated exhaustive row selection. Per-column indexes now
narrow candidates, then verify all original typed predicates; they preserve row
order and source identity. Duplicate primary keys use exact typed tuple equality.
Correctness regression tests compare indexed selection with exhaustive selection,
including Decimal identity, empty selectors and separate sources.

Reproduce with:

```sh
python tools/benchmark.py --out build/performance --warm-runs 20 --hardware "describe this machine"
```

Evidence: [before optimization](evidence/performance-before.json),
[final measured implementation](evidence/performance.json).

The final 0.1.0a2 core was measured again on the same declared workload after the
local model server stopped: twenty warm runs had P95 **1.866 seconds**, and a fresh
process core check took **1.885 seconds**. All 500 checks passed. The
[new record](evidence/performance-final.json) identifies all twenty current core
files; earlier measurements remain available. Neither run flushes OS file caches
or includes model inference, interpreter startup or report rendering.

## Mapping evaluation

A separate [mapping challenge suite](../evaluations/mapping-v1/README.md) now
provides twelve owned synthetic tasks, an answer-free export, a saved-proposal
scorer and a review template bound to submission bytes. Nine tasks have reference
mappings and three call for abstention. It distinguishes core validity, reference
contract agreement and declared human judgments.

The [control evidence](evidence/mapping-controls/evidence.json) exercises the
measurement tool using known answers: the reference control matches all nine
requested mappings and abstains on three tasks. The deliberately wrong control
has seven contract differences, three proposals despite insufficient evidence,
one invalid proposal and one retained correct stale-paper mapping. Five wrong
identity mappings still have matching numbers and a core `pass`, demonstrating why
numeric consistency alone cannot score mapping correctness.

The controls contain **zero model runs and zero independent participants**. Candidate
precision, ambiguity rate and confirmation time remain unmeasured. Unlisted
equivalent contracts require adjudication; reference differences are not
automatically scientific errors. The first control-draft failure and its 86
frozen files remain in the suite's history.

A later [local Qwen3-8B Q4_K_M run](local-model-evaluation.md) used twelve separately
prepared requests without oracle context, retries or answer repairs. All twelve
JSON answer envelopes parsed, but all twelve proposals failed validation;
zero reference targets matched and none of three required abstentions occurred.
This failed model baseline remains published with exact inputs and outputs.
The locked suite's README describes its earlier control-only freeze; it has not
been rewritten to alter that historical record.

Codex's separate [developer walkthrough](evidence/developer-first-use/evidence.json)
confirmed ten authored bindings, detected eight data-update mismatches, applied
eight changes and restored original bytes. It supports local workflow acceptance,
not independent onboarding speed or model mapping accuracy.

## Still unmeasured

- Post-launch first-time onboarding by three independent users and the ten-minute target.
- AI mapping precision, ambiguity rate and confirmation time. This corpus uses
  manually declared mappings and cannot supply those measurements.
- Independent Calkit/scitexlintr/manual/agent setup and review-time comparisons.
  A [configured CLI comparison](comparison.md) exists; it does not measure
  independent users or establish lower setup effort.
- macOS and remote CI execution. Four Python minors have local Windows and glibc
  Linux evidence; Alpine Linux also has Python 3.14.8 evidence. See
  [the validation record](local-validation.md) for exact runs and limits.

The owner authorized local machine tests and Codex developer review for
pre-release acceptance on 2026-10-03. Independent user measurements are now
post-launch follow-up work. An automated developer assessment remains labeled as
such and does not create human observations.

No “better than existing tools” or broad accuracy claim follows from these tests.
