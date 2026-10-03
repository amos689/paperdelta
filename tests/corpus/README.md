# Frozen real-text fault-injection corpus

This corpus contains source material from ten public research repositories:
five development papers and five held-out papers. Assignment preceded parser
execution on the held-out group. Every file has a pinned commit and byte hash in
`manifest.json`. `annotations.json` records manually selected literals, context
and meaning. `scenarios.json` defines transformations and expected outcomes.

## What this measures

There is **one selected numeric literal per paper**, with fifteen correlated
scenarios around it, for 150 scenarios. Real surrounding text exercises templates,
macros, inclusion, tables, math and UTF-8 offsets. Controlled CSV fixtures exercise
identity, incomplete evidence, changes, conservative unknowns, guarded writes and
restoration. These are **not 150 independent research results**.

CSV values are synthetic: three records whose mean matches the literal, with
separate train and decoy identities. They do not come from original experiments.
The harness does not claim that the paper's result is true. A standard deviation,
physical parameter or bound is a literal scalar here; its scientific derivation
is not re-estimated.

This convenience sample is weighted toward open astrophysics and physical-science
manuscripts, with two ML-related sources. It is not a representative random sample
of ML papers. All unbound candidates, unsupported constructs and missing figure
registrations remain visible. Figures, data, bibliographies and TeX dependencies
were not collected, so these are not complete buildable paper projects.

The HWO table identifies itself as generated upstream. The benchmark tests a
disposable edit; real users should update the generator and its inputs. Passing
byte-edit tests is not advice to maintain generated files by hand.

## Reproduce

Install PaperDelta from this checkout and choose new output directories.
The current implementation uses the already seen papers as a **regression**:

```sh
python tools/evaluate_corpus.py --split development --out build/corpus-development
python tools/evaluate_corpus.py --split held-out --out build/corpus-held-out
```

`active-study.json` names the current regression lock, which must match the
implementation and inputs for either split. The historical split labels are
retained for comparison; these runs are not fresh held-out evaluations.
Maintainers create a new named lock with
`python tools/evaluate_corpus.py --freeze --out unused` only after versioning
the active study. The command refuses to overwrite an existing lock.

The original `protocol-lock.json`, first results, and all 23 implementation/input
files it identified remain under `history/original-v1` and the evidence directory.
To run that original implementation in a new tree:

```sh
python tools/replay_original_corpus.py --out build/original-corpus-replay
```

The helper verifies every historical digest and copies the unmodified paper
sources into the new tree. It uses the current interpreter and dependencies:
this is an implementation replay, not an exact historical environment. Never
overwrite the original results or label a replay as new unseen data.

The evaluator refuses modified upstream bytes and writes only new scratch
copies. It saves every case's report and combined `evidence.json`, including
failures and unknowns. Exit 1 means an expectation did not match. Project exits
and bound-literal outcomes are separate: a checked literal does not make the
whole paper pass.

The initial development run exposed four failures: some injections broke math
delimiters, and the checker failed to catch the parser's syntax-error exception.
Both were corrected before held-out evaluation. First development results are
retained in `docs/evidence/`. No held-out paper was dropped.

## Attribution and scope

See [third-party notices](../../THIRD_PARTY_NOTICES.md) and preserved licenses.
Sources are unmodified; evaluation changes disposable copies and labels the
modifications. Derived reflectometry text remains CC BY-SA 4.0; PaperDelta's
independent implementation is MIT.

This does not evaluate AI mapping accuracy, first-time-user setup time, original
experiment reproducibility, whole-paper accuracy or cross-platform support.
