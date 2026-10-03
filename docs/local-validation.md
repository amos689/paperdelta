# Local validation and candidate artifacts

[简体中文](zh-CN/local-validation.md)

Pre-launch acceptance uses local machine tests and Codex developer review, as the
owner instructed on 2026-10-03. Independent users are post-launch work. Historical
[a2 acceptance](release-acceptance.md) does not automatically accept later changes;
the [v0.2 ledger](v0.2-plan.md) tracks current delivery. Native Mac execution and
remote CI remain unverified.

## Current checks

The [v0.2 acceptance record](v0.2-acceptance.md) links current runtime evidence:
four installed Windows Python versions, the bilingual core-only wheel, corpus
regression, performance, browser and actual developer walkthrough. The historical
platform table below remains a2 evidence.

Use a Python 3.11+ development environment:

```sh
python -m pip install -e '.[dev,mcp]'
python tools/run_tests.py -q
python -m ruff check src tests tools
python -m ruff format --check src tests tools
python tools/check_docs.py
python tools/validate_examples.py --out build/example-replay
python tools/demo_ci.py --out build/ci-replay
```

Use fresh output directories. The test wrapper selects a project-local temporary
directory. For prepared **noneditable installed-package** environments:

```sh
python tools/validate_python_matrix.py \
  --python .venv-py311/Scripts/python.exe \
  --python .venv-py313/Scripts/python.exe \
  --python .venv-py314/Scripts/python.exe \
  --out build/python-matrix-replay
```

This helper installs nothing. Each environment needs matching code and dev/MCP
dependencies; it verifies imported source and asset identities, preserves JUnit/logs
and supports POSIX venv paths such as `.venv-3.11/bin/python`.

## Historical platform evidence

| Environment / version | Actual a2 evidence |
| --- | --- |
| Windows 3.11.17 / 3.12.14 | 162-test full suites; independent noneditable 3.11 environment and separate core-only wheel smoke |
| Windows 3.13.16 / 3.14.8 | Each 151-test full suite, then separate 2-process and 10-CI-adapter runs |
| Alpine 3.24.2, kernel 6.18.52, x86_64, Python 3.14.8 | 151 tests, zero skips, core-only install, real MCP/Git, examples and frozen mapping controls; later process and CI checks separately |
| Ubuntu Base 24.04.5 / glibc 2.39 userspace | Python 3.11.17 / 3.12.15 / 3.13.16 / 3.14.8 each 162 tests, zero skips, installed wheel/core-only smoke, examples and CI demos |
| Mac preparation | Windows 167-case suite: 164 passed, 3 POSIX skips; bootstrap verification only, not Mac execution |

Windows matrix dependencies included Pydantic 2.13.5, PyYAML 6.0.3, pylatexenc 2.11,
MCP 2.2.0 and pytest 9.1.1. The Linux environment was project-local QEMU 11.1.0
software emulation: two virtual CPUs, 3 GiB RAM. Ubuntu Base ran in an ext4 chroot
under the Alpine kernel, not an Ubuntu boot or a remote runner. Model runtimes were
not dependencies. Timing under emulation is not performance evidence.

The extra CPython builds were project-local uv 0.12.22/python-build-standalone
installations; system Python, PATH and registry were unchanged. Publisher hashes
were verified for QEMU/Alpine/Ubuntu/uv downloads. Environments and test paths included
Chinese and spaces. Owned guests shut down and loopback services closed after checks.

Evidence and preparation failures remain separately recorded:

- [Windows 151-test matrix](evidence/python-matrix-mapping.json),
  [earlier a1](evidence/python-matrix.json), [earlier a2](evidence/python-matrix-a2.json),
  [interactive tests](evidence/interactive-validation.json).
- [Alpine run](evidence/linux-alpine-a2/evidence.json),
  [JUnit](evidence/linux-alpine-a2/junit.xml),
  [provenance](evidence/linux-alpine-a2/provenance.json).
- [glibc run](evidence/linux-glibc-a2/evidence.json),
  [matrix](evidence/linux-glibc-a2/matrix.json),
  [provenance/setup failures](evidence/linux-glibc-a2/provenance.json),
  [Windows helper regression](evidence/linux-glibc-a2/windows-evidence.json).
  The initial helper followed a POSIX venv symlink to the base interpreter; preserving
  the invoked path fixed that validation-helper bug. Runtime/tests were unchanged.
- [Windows process checks](evidence/process-writes-windows.json),
  [Linux process checks](evidence/process-writes-linux/evidence.json),
  [CI adapter](evidence/ci-adapter/evidence.json),
  [Mac preparation](evidence/macos-preparation.json).

Two real-process cases pause a writer after its first replacement. Competing apply
and recovery return WRITE_LOCKED without mutation. One writer resumes; another is
killed without cleanup, leaving RECOVERY_REQUIRED. Recovery restores all bytes and
the original patch can run again. This covers local process death, not power loss,
network filesystems or arbitrary third-party edits.

## Other checks and interpretation

| Check | Reproduction / evidence |
| --- | --- |
| Three examples, Unicode/BOM/CRLF patch and recovery | `tools/validate_examples.py`; [record](evidence/owned-examples.json) |
| Reversed comparison and positive numeric change | `tools/demo.py`; [record](evidence/workflow-demo.json) |
| Calkit/scitexlintr workflows | [Comparison](comparison.md) |
| Original corpus and a2 replay | [Evaluation](evaluation.md) |
| 500 metrics / 20 files / 10 MB CSV | `tools/benchmark.py`; [a2 record](evidence/performance-final.json) |
| Offline report | [a2 browser](evidence/report-browser-qa.json), [v0.2 bilingual browser](evidence/v0.2-report-browser.json) |
| Owned TeX compilation | [Compiler record](evidence/tex-smoke.json) |
| Core-only installation | [a2 smoke](evidence/package-smoke-a2.json) |
| Identity/abstention scoring | [Frozen controls](evidence/mapping-controls/evidence.json), [staged follow-ups](staged-model-evaluation.md) |
| Target-commit baseline/declaration changes | `tools/demo_ci.py`; [CI guide](ci.md) |

The built-in compiler could not resolve platform directories in the recorded TeX
check; a project-local verified Tectonic 0.17.0 compiled the owned fixture before/after
patches, with a nonfatal Fontconfig notice. This is not a requirement for core users.
Automated/AI operation supplies zero independent participants and no human timing.

## Build and audit

```sh
python tools/build_release.py --out build/release-candidate
python tools/audit_release.py --directory build/release-candidate
```

The project version determines the three names: `paperdelta-VERSION-py3-none-any.whl`,
`paperdelta-VERSION.tar.gz`, and `paperdelta-evaluation-VERSION.zip`.
Wheel/source distribution contain original MIT code, tests, owned examples and paired
docs. The separately licensed corpus and its outputs belong in the evaluation ZIP
with their notices. Its aggregate expression `MIT AND CC-BY-4.0 AND CC-BY-SA-4.0`
does not relicense components. Original mapping tasks and controls are MIT materials.

The audit reads archives without extraction/execution. It checks wheel RECORD,
current source/catalog/assets, all maintained docs, examples, tests/tools, retained
licenses, original corpus bytes and frozen protocol identities. Historical studies
must be verified against their own preserved implementation, not relocked to the
new runtime. No environments, models, native executables, transactions or credentials
belong in a release. `package-audit.json` is an external hash sidecar.

Git attributes disable newline conversion for frozen corpus/evidence/evaluations.
Do not update their locks to make changed code pass. See
[Git byte audit](evidence/corpus-git-identities.json). Replays are regressions on
already seen inputs, never new held-out trials. Build tools publish nothing.

Historical audits remain: [a1](evidence/package-audit.json),
[a2](evidence/package-audit-a2.json), [mapping](evidence/package-audit-mapping.json),
[Linux](evidence/package-audit-linux.json), [processes](evidence/package-audit-process.json),
[CI](evidence/package-audit-ci.json), [glibc](evidence/package-audit-glibc.json),
[final a2](evidence/package-audit-final.json).
[Final a2 installation/identity evidence](evidence/release-replay-final.json) belongs
to `build/release-candidate-final`, not v0.2. Older intermediate builds retain their
own results; refreshed documentation alone never implies a repeated platform run.

## Mac after product convergence

Before native validation, historical studies can be replayed without a model:

```sh
python tools/replay_study.py mapping-v1 --out build/mapping-replay
python tools/replay_study.py staged-v2 --out build/staged-v2-replay
python tools/replay_study.py staged-v3 --out build/staged-v3-replay
python tools/replay_study.py corpus-a2 --out build/corpus-a2-replay
python tools/regress_corpus.py --out build/current-corpus-regression
```

The first four commands copy hash-verified archived code into a new workspace and
compare results with the saved records. Corpus modes require the separate corpus
bundle. The last command runs the current core on the same previously seen inputs,
recording a new protocol and comparing every outcome; it never rewrites an old lock.
Historical code is original MIT material in `evaluations/implementations`, with
source commit and byte identities. Native model weights are unnecessary for rescoring.

Use the [English transfer guide](../START_ON_MAC.en.md) or
[Chinese transfer guide](../START_ON_MAC.md) with a newly audited matching package.
[Native validation](macos.md) creates fresh destination environments and refuses
the wrong host/architecture or Rosetta. Native compatibility requires the owner's
actual Mac run; a portable ZIP is not that evidence.
