# Local validation and candidate artifacts

These are measured local results. Under the owner's 2026-10-03 instruction,
pre-release acceptance uses machine tests and developer review; independent
user feedback follows launch. See the [acceptance decision](release-acceptance.md)
and [scope ledger](progress.md).

For the subsequent macOS work, use the [transfer instructions](../START_ON_MAC.md)
and [native validator](macos.md). Five platform cases extend the suite to 167:
the Windows bootstrap regression runs 164 and explicitly skips three POSIX cases.
Native macOS verification remains pending. This new Windows run verifies the
bootstrap script, not the Mac operating system; see
[preparation evidence](evidence/macos-preparation.json).

## Version 0.1.0a2 on this Windows host

| Python | Installation used | Recorded test runs |
| --- | --- | --- |
| 3.11.17 | Independent environment, noneditable installed package | 162 full suite; earlier separate records retained |
| 3.12.14 | Development environment; separate core-only wheel smoke test | 162 full suite |
| 3.13.16 | Independent environment, noneditable installed package | 151 full suite; 2 process tests; 10 CI adapter tests |
| 3.14.8 | Independent environment, noneditable installed package | 151 full suite; 2 process tests; 10 CI adapter tests |

The [151-test a2 matrix record](evidence/python-matrix-mapping.json) includes package versions and
hashes of every imported core source file. The new environments used Pydantic
2.13.5, PyYAML 6.0.3, pylatexenc 2.11, MCP 2.2.0 and pytest 9.1.1. Test fixtures
include Chinese and spaced paths, BOM/CRLF, data-only changes, stale proposals,
patch/recovery failures and a real stdio MCP client. The three added runs had
zero skipped tests. Separate Alpine and glibc Linux runs are recorded below.
macOS and remote GitHub jobs have not run.

The later [Windows 3.11 matrix-helper regression](evidence/linux-glibc-a2/windows-evidence.json)
passed all 162 tests after the helper's POSIX path handling was corrected.
Its [JUnit](evidence/linux-glibc-a2/windows-junit.xml) replaces only the host name
with `windows-local`; the original and published hashes are retained in
[provenance](evidence/linux-glibc-a2/provenance.json).

The earlier [a1 record](evidence/python-matrix.json), with 125 tests per version,
and [first a2 record](evidence/python-matrix-a2.json), with 138 tests, remain
available. Thirteen mapping-scorer tests brought that suite to 151, without changing
the a2 runtime core. [Development record](evidence/mapping-test-suite.json).
The [a2 development/terminal record](evidence/interactive-validation.json)
identifies the additional checks and actual terminal operation.

Twelve new tests cover the terminal selection flow, cancellation without writes,
all-evidence expansion, terminal-control escaping, stale data, interruption
boundaries and ten confirmed mappings that still correctly report mismatches.
A thirteenth test checks abstract/table priority and rejects a commented-out
table marker as a priority cue. The actual terminal check selected one mapping,
saved its configuration backup and preserved all four TeX files. It was driven
by the development agent and contributes zero first-time-user participants.

The extra CPython distributions were downloaded with uv 0.12.22 using
`--install-dir .tools/python-matrix --no-bin --no-registry` and a local cache.
These are uv-managed python-build-standalone distributions, as described in
[uv's Python installation documentation](https://docs.astral.sh/uv/guides/install-python/).
The system Python, PATH and registry were not changed.

To validate already prepared independent environments:

```sh
python tools/validate_python_matrix.py \
  --python .venv-py311/Scripts/python.exe \
  --python .venv-py313/Scripts/python.exe \
  --python .venv-py314/Scripts/python.exe \
  --out build/python-matrix-replay
```

This command does not install anything. Each environment must already contain
a noneditable installation of `.[dev,mcp]` matching the checkout. The command
checks installed-file identities and preserves JUnit and logs in a new directory.
It supports prepared POSIX virtual environments as well as Windows environments.

## Version 0.1.0a2 in a local Linux guest

Alpine Linux 3.24.2, kernel 6.18.52, x86_64 and Python 3.14.8 passed the same
**151 tests, with zero failures, errors or skips**. This was an actual Linux
guest under portable QEMU 11.1.0 software emulation on the Windows host, with
two virtual CPUs and 3 GiB RAM. The wheel was installed noneditably in a fresh
guest virtual environment; all 20 imported core files matched the audited source
archive. Tests ran from its extracted directory containing Chinese text and spaces.

The run also verified the core-only installation before adding MCP: normal check
exit 0, data-change exit 1 with an HTML report, and missing-MCP exit 2. After
installing MCP 2.2.0 and pytest 9.1.1, the full suite included the real stdio
handshake and actual Git target-snapshot test. Three public examples passed their
expected states, including Unicode/BOM/CRLF patch-and-recovery byte preservation.
The frozen mapping scorer's controls matched Windows, and its input export
contained no reference-answer files.

[Guest record](evidence/linux-alpine-a2/evidence.json),
[JUnit results](evidence/linux-alpine-a2/junit.xml),
[test log](evidence/linux-alpine-a2/tests.log),
[example results](evidence/linux-alpine-a2/examples.json) and
[host/download provenance](evidence/linux-alpine-a2/provenance.json) retain exact
artifact hashes, dependency versions, commands and setup corrections. QEMU's
Windows binary was obtained through its [official download entry point](https://www.qemu.org/download/);
the Alpine ISO came from [Alpine's release downloads](https://www.alpinelinux.org/downloads/).
Publisher digests were checked before use. The guest shut down normally and both
temporary loopback services were verified closed.

To repeat the checks in a prepared Linux virtual environment, install the matching
candidate wheel and `pytest==9.1.1 mcp==2.2.0`, unpack the matching source archive,
and run from that source root without a `PYTHONPATH` override:

```sh
python -m pip check
python -c "import paperdelta; print(paperdelta.__file__)"
python -X utf8 tools/run_tests.py -q --junitxml=build/linux-tests.xml
python -X utf8 tools/validate_examples.py --out build/linux-examples
python -X utf8 tools/validate_mapping_controls.py --out build/linux-mapping-controls
python -X utf8 tools/evaluate_mappings.py export --out build/linux-mapping-inputs
```

The imported path must be the virtual environment's installed package. Use new
output directories for a repeat. This initial result covers one musl-based Linux
guest and one Python minor. A separate glibc matrix is recorded next; macOS and
remote CI remain unverified. Emulation timings are diagnostic, not performance benchmarks.
This first run exercised POSIX lock acquisition/release. The additional process
checks below establish the stated contention behavior in a separate run.

## Version 0.1.0a2 in a glibc Linux environment

Four independent virtual environments passed the complete installed-package suite
under Ubuntu Base 24.04.5 userspace with glibc 2.39:

| Python | Full suite | JUnit |
| --- | --- | --- |
| 3.11.17 | 162 passed; zero failures, errors or skips | [Record](evidence/linux-glibc-a2/3.11.17-junit.xml) |
| 3.12.15 | 162 passed; zero failures, errors or skips | [Record](evidence/linux-glibc-a2/3.12.15-junit.xml) |
| 3.13.16 | 162 passed; zero failures, errors or skips | [Record](evidence/linux-glibc-a2/3.13.16-junit.xml) |
| 3.14.8 | 162 passed; zero failures, errors or skips | [Record](evidence/linux-glibc-a2/3.14.8-junit.xml) |

This is a chroot on an owned ext4 virtual disk inside the same Alpine 6.18.52
kernel/QEMU environment, not a booted Ubuntu kernel or a GitHub runner. The
[Ubuntu Base archive](https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/)
and uv 0.12.22 archive were verified against publisher SHA256 digests.
Python installations use uv-managed python-build-standalone builds. The system
Python installed inside the chroot only orchestrated the runs; the matrix used
the four explicitly named interpreters.

Every environment first installed the audited wheel without MCP. Its console
entry point passed the unchanged example, a data-only update returned 1 with an
HTML report, and the missing-MCP command returned 2 with `MCP_NOT_INSTALLED`.
After adding pytest 9.1.1 and MCP 2.2.0, the full suite exercised actual stdio MCP,
process contention/termination, Git target snapshots and all other current tests.
All 20 imported core files matched the source archive and checkout. Both virtual
environments and test projects used Chinese text and spaces in their paths.

The first matrix launch exposed a bug in the validation helper: resolving a POSIX
venv executable followed its symlink to the base interpreter, causing an incorrect
project-boundary rejection. The helper now preserves the invoked executable and
checks the actual virtual-environment prefix. The completed installations and
core-only smoke results were retained; a new disk overlay resumed the full suite
after that fix. The prior failed launch and two earlier environment-setup failures
are preserved separately. No PaperDelta runtime or test files were substituted.

The three public examples and both CI Git scenarios also passed in this glibc
environment. The Unicode example preserved outside bytes during its BOM/CRLF
repair and recovered the original bytes. The CI demo matched the Windows scenario
results, including the explicit coverage reduction after bindings were removed.

[Execution record](evidence/linux-glibc-a2/evidence.json),
[matrix identities and versions](evidence/linux-glibc-a2/matrix.json),
[example results](evidence/linux-glibc-a2/examples.json),
[CI demo](evidence/linux-glibc-a2/ci-demo.json) and
[provenance, setup corrections and limits](evidence/linux-glibc-a2/provenance.json)
retain the evidence. The guest shut down normally, and its loopback services
were independently checked closed. Timings under software emulation are not
performance measurements.

To repeat the matrix from an extracted source archive or checkout with matching
noneditable installations and test dependencies already prepared inside it:

```sh
python3 tools/validate_python_matrix.py \
  --python .venv-3.11/bin/python \
  --python .venv-3.12/bin/python \
  --python .venv-3.13/bin/python \
  --python .venv-3.14/bin/python \
  --out build/glibc-matrix-replay
```

## Concurrent writers and process termination

Two added integration tests pause a real writer after its first TeX replacement.
While that process holds its OS lock, independent `apply --write` and
`recover --write` CLI processes both return `WRITE_LOCKED`. They leave the
partial paper, configuration and transaction journal unchanged.

One case resumes the writer and completes normally. The other forcibly kills it,
skipping Python cleanup: the journal remains in `applying` state, and another
application returns `RECOVERY_REQUIRED`. Recovery restores all original TeX bytes;
the same original patch then applies successfully. This covers controlled process
death on local filesystems, not machine power loss, network filesystems or
arbitrary edits by other programs.

The [Windows record](evidence/process-writes-windows.json) contains a new full
153-test run on Python 3.12.14 and focused two-test runs on 3.11.17, 3.13.16 and
3.14.8. The [Linux focused record](evidence/process-writes-linux/evidence.json)
contains the two additional tests on the same Alpine/Python versions as above,
with [JUnit](evidence/process-writes-linux/junit.xml) and
[provenance](evidence/process-writes-linux/provenance.json). The guest used the
unchanged installed candidate wheel and a separately hashed new test file added
to the extracted source tree. The original 151-test guest record is retained;
these are separate executions. No runtime core files changed.

```sh
python -X utf8 tools/run_tests.py -q tests/test_process_writes.py
```

## Other reproducible checks

| Check | Entry point / evidence |
| --- | --- |
| Three public owned examples; Unicode, BOM/CRLF, guarded writes and restoration | `python tools/validate_examples.py --out build/example-replay`; [record](evidence/owned-examples.json) |
| Figure-inclusive reversal and positive-change apply/recovery | `python tools/demo.py --out build/demo-replay`; [record](evidence/workflow-demo.json) |
| Calkit and scitexlintr configured CLI workflows | [Comparison and commands](comparison.md) |
| Original real-text evaluation plus separately frozen a2 regression | [Evaluation](evaluation.md), [a2 record](evidence/corpus-interactive-v2.json) |
| 500 metrics / 20 files / 10 MB CSV | [Performance record](evidence/performance.json) |
| Offline browser report and actual TeX compilation | [Browser record](evidence/report-browser-qa.json), [compiler record](evidence/tex-smoke.json) |
| Wheel without the optional MCP dependency | [a2 smoke record](evidence/package-smoke-a2.json); [a1 record](evidence/package-smoke.json) |
| Saved mapping proposal scoring, equal-value identity errors and abstention | `python tools/validate_mapping_controls.py --out build/mapping-controls`; [controls](evidence/mapping-controls/evidence.json) |
| Target-commit CI, declaration changes and job summaries | `python tools/demo_ci.py --out build/ci-demo`; [adapter evidence](evidence/ci-adapter/evidence.json) |

The later CI adapter run adds nine cases to the earlier one-case Git test.
The main Windows full suite now has 162 tests; each other Windows Python version
passed the ten-case adapter file separately. Alpine Linux passed those same ten
cases in a focused run, retaining the earlier 151-case and two-process records.
The guest received explicitly hashed replacements of the adapter and test files;
its installed runtime core stayed unchanged.
[Windows results](evidence/ci-adapter/windows/evidence.json),
[Linux results](evidence/ci-adapter/linux/evidence.json).

These checks contribute to the authorized local pre-release acceptance. Independent
first-use and observed confirmation-time records remain empty and are deferred
until after launch.
The mapping suite includes separate observation templates; control outputs keep
precision and ambiguity rate null and contain no confirmation-time measurements.

## Build and audit a candidate

From the full checkout in the development environment:

```sh
python tools/build_release.py --out build/release-candidate
python tools/audit_release.py --directory build/release-candidate
```

The build creates three artifacts:

1. `paperdelta-0.1.0a2-py3-none-any.whl` — the MIT Python package.
2. `paperdelta-0.1.0a2.tar.gz` — MIT original source, tests, owned examples and docs.
3. `paperdelta-evaluation-0.1.0a2.zip` — separately licensed paper sources,
   corpus results, notices, current protocol and preserved original implementation.

The source archive also contains the owned mapping challenges, reference answers,
scorer and historical control draft. Those fixtures are MIT materials and do not
require the separately licensed paper-corpus bundle.

The Python distributions exclude `tests/corpus` and corpus-output JSON.
Their MIT metadata therefore describes the code distribution; the evaluation
bundle lists its separately licensed components under `MIT AND CC-BY-4.0 AND
CC-BY-SA-4.0`. This inventory does not relicense any component. The separation
follows the [distribution-specific scope of License-Expression](https://packaging.python.org/en/latest/specifications/core-metadata/#license-expression).

The audit reads archive members without executing or extracting them. It checks
wheel RECORD hashes, current core sources, required support files, the 48
preserved corpus files, retained license notices, the active regression protocol
and all 23 original identities in the historical implementation. It rejects
scratch environments, transactions, native executables
and unexpected archive paths. The exact archive hashes are written beside them
in `package-audit.json`. Earlier build directories are development outputs and
are superseded by the freshly audited candidate.

Corpus files and historical snapshots have Git newline conversion disabled,
preserving their frozen byte identities. Current Python source uses LF. The
[Git identity check](evidence/corpus-git-identities.json) runs the actual Git
clean filters over every current and historical protocol member; this checks
checkout attributes locally and is not a substitute for remote CI.

To reproduce the corpus from the source archive, unpack the matching evaluation
bundle into the source root, preserving paths, then run the evaluation command.
Keep the first held-out record; a reproduction is not a new unseen test.
No package or repository is published by these scripts.

The preserved 0.1.0a1 [audit](evidence/package-audit.json) and
[replay evidence](evidence/release-replay.json) identify the previous artifacts:
their extracted source tests passed 125/125 and all 150 corpus case states
matched the original records, including the 24 complete-expectation failures.
The [a2 audit](evidence/package-audit-a2.json) and
[a2 replay](evidence/release-replay-a2.json) identify the new candidate separately.
The later [mapping-materials audit](evidence/package-audit-mapping.json) and
[archive replay](evidence/release-replay-mapping.json) identify the candidate that
also ships the new scoring tools and all their frozen fixtures.
That exact candidate was used for the Linux guest run. The subsequent
[documentation/evidence candidate audit](evidence/package-audit-linux.json) and
[identity comparison](evidence/release-replay-linux.json) retain the tested core
and test/input bytes while adding these records; they do not claim another guest run.
The later [process-validation candidate audit](evidence/package-audit-process.json)
and [identity comparison](evidence/release-replay-process.json) add the newly
executed process test and its Windows/Linux evidence. They retain all runtime,
existing test and frozen evaluation input bytes.
The subsequent [CI-adapter candidate audit](evidence/package-audit-ci.json) and
[identity record](evidence/release-replay-ci.json) include the updated adapter,
its tests, the workflow example and reproducible CI demo. The 20 runtime core
files and frozen evaluation inputs are unchanged.
The subsequent [glibc-validation candidate audit](evidence/package-audit-glibc.json)
and [identity record](evidence/release-replay-glibc.json) add these Linux results,
the Windows helper regression and the portable matrix-helper fix. Every wheel
member, runtime source, test and frozen evaluation input retains the bytes used
in the recorded executions; the new source archive includes the updated helper
and documentation.
The final candidate is `build/release-candidate-final`. Its
[artifact audit](evidence/package-audit-final.json) and
[identity and installation record](evidence/release-replay-final.json) cover the
acceptance documentation, local model experiment, developer walkthrough and
current-core performance measurement. The same twenty runtime files and all
seventeen test files retain their tested bytes. The wheel has refreshed README
metadata; no model weights or native inference libraries are distributed.
Artifact hash reports are sidecars and are excluded from the distributions to
avoid a self-referential checksum.
