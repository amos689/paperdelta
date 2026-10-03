# Development evidence

The authoritative scope remains [the development plan](development-plan.md).
Started 2026-10-02; updated 2026-10-03 Sydney time. The local alpha has
[passed developer acceptance](release-acceptance.md). This ledger distinguishes
implemented behavior from the scope of its supporting evidence.

On 2026-10-03 the owner authorized local machine tests and Codex developer
assessment as the pre-release acceptance basis. Independent users and comparative
usability measurements are post-launch follow-up work. macOS and remote CI remain
explicitly unverified, rather than prerequisites for this local alpha candidate.
The amended [development plan](development-plan.md) retains the functional scope.

After local acceptance, the owner requested macOS support and confirmed access to
a Mac. [Transfer and native verification](../START_ON_MAC.md) are now prepared:
separate Apple Silicon/Intel jobs, a fresh-environment validator and five new
filesystem/terminal cases. This preparation does not add a native Mac pass;
the prior Windows/Linux alpha acceptance and frozen results remain historical evidence.
See [macOS preparation](macos.md) and its [local checks](evidence/macos-preparation.json).

## Verified locally

- Windows, Python 3.11.17 / 3.12.14 / 3.13.16 / 3.14.8, project-local virtual
  environments. Each version passed the earlier 151-test suite for 0.1.0a2;
  Python 3.11 and 3.12 now passed all 162 tests. The other versions passed the two added
  process tests and the updated ten-case CI adapter tests separately.
  The three added versions used noneditable
  installed packages with matching source hashes. See
  [local validation](local-validation.md). System Python was not upgraded.
  Dependency versions and license metadata are recorded in
  [package-metadata.json](evidence/package-metadata.json).
- An actual Alpine Linux 3.24.2 x86_64 guest, Python 3.14.8, passed the same
  151 tests with zero skips using the installed wheel. Core-only checks, actual
  stdio MCP, the Git baseline test, Unicode/BOM/CRLF example recovery and frozen
  mapping controls passed. The guest used project-local QEMU software emulation
  and shut down normally. This adds one Linux environment, not the full CI matrix.
  [Linux evidence](evidence/linux-alpine-a2/evidence.json),
  [provenance and limits](evidence/linux-alpine-a2/provenance.json).
- Four noneditable environments using Python 3.11.17, 3.12.15, 3.13.16 and 3.14.8
  each passed all 162 tests under Ubuntu Base 24.04.5/glibc 2.39 userspace on an
  ext4 disk in the Alpine-kernel QEMU guest. Each first passed core-only installation
  checks. Public examples and both CI Git demos passed as well. This exposed and
  fixed a POSIX venv-symlink bug in the validation helper; the same helper passed
  a Windows 3.11 full-suite regression. Runtime/test bytes did not change.
  [glibc execution](evidence/linux-glibc-a2/evidence.json),
  [matrix](evidence/linux-glibc-a2/matrix.json),
  [setup failures, resumed execution and limits](evidence/linux-glibc-a2/provenance.json).
  This is local userspace compatibility evidence, not remote CI or a native Ubuntu boot.
- Two added process tests pass on Windows and Alpine Linux: competing apply and
  recovery CLI processes cannot write while another writer is paused after its
  first actual replacement. Abruptly killing the owner releases its OS lock while
  preserving a journal that requires recovery. Recovery restores all original
  bytes and permits the same patch to run again. This is controlled local-process
  evidence, not a power-loss guarantee. [Windows](evidence/process-writes-windows.json),
  [Linux](evidence/process-writes-linux/evidence.json).
- **162 tests passed** in the Python 3.12.14 full suite, including parser-error
  handling, citation arguments, indexed selection, nested report contracts and
  target-commit baseline retrieval.
- Terminal `bind --interactive` shows each mapping's paper context, calculations
  and selected evidence; only the final explicit selection is saved. Twelve tests
  cover acceptance, cancellation, stale inputs, ten bindings and interruption
  boundaries. An actual ConPTY session accepted exactly one binding and left all
  four TeX files unchanged. This was agent-driven validation, with zero independent
  participants. [Interactive record](evidence/interactive-validation.json).
- A separate twelve-task mapping suite exports inputs without reference answers
  and scores saved proposals. Thirteen tests exercise its identity checks,
  abstentions, invalid-candidate accounting, stale review records and measurement
  boundaries. Positive/negative controls expose five wrong identities with
  numerically passing values. These controls make no model or user performance claim.
  [Protocol](../evaluations/mapping-v1/README.md),
  [controls](evidence/mapping-controls/evidence.json).
  [Full-suite record](evidence/mapping-test-suite.json),
  [installed-environment results](evidence/python-matrix-mapping.json).
- Discovery now prioritizes actual abstract/table AST regions and repeated
  literals. These are ordering hints, not inferred experiment mappings or a
  semantic determination of which table is the main result.
- Three public owned fixtures now include an intentionally ambiguous table and
  Chinese filenames/context with a declared literal macro. The latter was changed,
  patched and restored in a BOM/CRLF copy, with outside bytes preserved.
  [Example evidence](evidence/owned-examples.json).
- A real local Git regression verifies that the CI wrapper uses the target
  commit's snapshot even when the PR replaces its same-named working-tree file.
  Missing target snapshots stay explicitly unavailable. See [CI instructions](ci.md).
- The CI adapter separately inventories changed configurations, snapshots and
  review declarations, distinguishes formatting from semantic changes, and writes
  a bounded job summary without changing the numerical verdict. Ten cases pass
  on four Windows Python versions and the Alpine guest. A pinned-source paper
  workflow template passes actionlint; two local Git demos retain actual outputs,
  including a green numerical result after bindings were removed.
  [CI adapter evidence](evidence/ci-adapter/evidence.json).
  Remote GitHub jobs have not run.
- The [CLI workflow comparison](comparison.md) runs all three configured tools:
  Calkit's DVC pipeline updates conditional answers, scitexlintr repairs numeric
  and text snapshots, and PaperDelta reports the false comparison while withholding
  associated numeric writes. Setup diffs and command outputs are retained.
- Data-only 84.1% → 80.9% changes produce four numeric mismatches, a false
  comparison and changed figure inputs. 84.1% → 84.5% changes produce four fixes across three files, pass
  after application, and restore byte-exactly. `tools/demo.py` reproduces both.
- Numeric patches are re-derived; stale reports/patches, overlaps, partial numbers,
  changed evidence during writes and later edits during recovery are covered.
  An injected second-file write failure is journaled and recoverable.
- Review state is independent of pass/fail. Changed low-order evidence can
  supersede review even while displayed values still match. Old states can match
  old review records again.
- `init → scan → propose → bind preview → selected acceptance → check` works
  through real CLI subprocesses using the exact inputs in the quick-start guide.
  Decimal selectors survive JSON proposal and YAML configuration round trips.
- Official MCP 2.2 in-process and actual stdio client/server tests verify five
  read-only tools and the same data-only-change result as the core checker.
- Offline HTML was exercised in headless Chrome on this Windows host, at desktop
  and 375-pixel mobile widths: file/source/rule/result/text filters, evidence-table
  expansion, no horizontal page overflow and no JavaScript errors. See
  [browser evidence](evidence/report-browser-qa.json) and the README screenshot.
- Ruff lint/format checks passed. Wheel/sdist builds succeeded. The wheel was
  installed into a clean environment without MCP: both the passing example and
  the data-only failure produced the correct exits and HTML reports. Requesting
  optional MCP gave the documented installation error. See
  [package smoke evidence](evidence/package-smoke.json).
- The previous 0.1.0a1 candidate contents were audited: 19 core files matched, wheel
  RECORD hashes verify, and all 48 retained paper/license files plus 23 frozen
  protocol identities match. MIT wheel/sdist and separately licensed evaluation
  ZIP are distinct artifacts. [Artifact audit](evidence/package-audit.json).
- The 0.1.0a2 candidate audit checks all 20 current core files, 25 current
  regression identities and the 23 preserved original identities. A core-only
  wheel installation passes the normal/data-change checks and optional-MCP error
  path. [a2 audit](evidence/package-audit-a2.json),
  [a2 wheel smoke](evidence/package-smoke-a2.json).
- Mapping-suite files and their preserved draft are included in the original MIT
  source distribution; the third-party paper corpus remains a separate bundle.
  The [candidate audit](evidence/package-audit-mapping.json) and
  [archive replay](evidence/release-replay-mapping.json) identify this later
  candidate. The runtime core remains byte-identical to the a2 regression.
- The 0.1.0a1 extracted source-archive tests passed 125/125. Adding its evaluation bundle
  reproduced 126/150 expectations with the same per-case states as the original
  development and first held-out records. This is packaging/replay evidence,
  not a fresh held-out evaluation. [Replay record](evidence/release-replay.json).
- The 0.1.0a2 named regression and a replay of the preserved original implementation
  both produced exactly the same 150 per-case outcomes as the first records:
  126 complete expectations matched. Original locks, code and failures remain.
  [Regression](evidence/corpus-interactive-v2.json),
  [historical replay](evidence/corpus-original-replay.json).
- Ten licensed paper sources and fifteen predeclared scenarios per paper:
  development 75/75 expectations matched; first held-out run **51/75**. Two
  dynamic-TeX manuscripts remained unknown. All failures and sources are retained.
  Eight applicable real-text patches preserved outside bytes and recovered
  exactly; two unsupported cases refused writes. See [evaluation](evaluation.md).
- With 500 distinct bound metrics, 20 TeX files and 10,000,047 CSV bytes, 20 warm
  core runs had P95 **1.724 seconds** on the recorded Windows laptop. A fresh
  process core check took 1.563 seconds; OS caches were not flushed. This is
  machine/workload-specific evidence, not a universal performance guarantee.
- The full stored-report format now has strict nested contracts and output
  validation; see [schema and semantics](report-format.md).
- The owned multi-file TeX example was flattened through literal includes and
  compiled before/after four real patches. Both PDFs contain the expected values.
  The built-in compiler failed to resolve platform directories; a project-local,
  digest-verified Tectonic 0.17.0 completed the check with a nonfatal Fontconfig
  notice. [Compiler evidence](evidence/tex-smoke.json).
- A **51.68-second** recording shows actual local reports with presentation
  captions. [Video](assets/paperdelta-demo.webm), [recording evidence](evidence/demo-recording.json).

The corpus uses original paper text with **synthetic controlled evidence** and
one selected literal per paper. It does not reproduce original experiments,
establish whole-paper accuracy, evaluate AI mappings or measure first-time use.

## Scope status

| Stage | Implemented | Limits / remaining assessment |
| --- | --- | --- |
| 0: feasibility | Parser probes; ten real texts; three owned examples; Calkit/scitexlintr CLI workflows; package-name lookup | Independent setup/review-time comparisons follow launch |
| 1: checker | Strict config, CSV/JSON identity, Decimal units, byte-exact LaTeX bindings, CLI | Broader compatibility evidence |
| 2: impact | Aggregations, derived metrics, predicates/ranking, snapshots, groups, actual figure demo, review states, strict report schema | Broader template coverage remains limited by dynamic TeX |
| 3: review and writes | Offline reports/filters; guarded patches; journal/recovery; review; eight real-text repairs; controlled writer contention and process death | Applied-case count is small; power-loss/network-filesystem guarantees are not established |
| 4: onboarding/agents | Prioritized scan, validated proposals, terminal/per-ID confirmation, schemas, agent guide, five MCP tools, CI matrix, paper workflow template and target/declaration adapter; ten-binding developer walkthrough | Local small-model baseline failed; independent feedback and remote CI follow later |
| 5: evaluation/release | Guides, corpus and failures, current-core performance, demo, local comparisons, four Windows and four glibc Linux Python versions, Alpine musl evidence, audited packages and archive identities; local alpha accepted | External publication remains separate; macOS remains unverified |

Terminal confirmation and explicit binding IDs both use the same guarded
acceptance API. Their effect on first-time-user effort remains unmeasured.

## Decisions made during implementation

- Chose pylatexenc 2.11 with explicit macro contracts after the small parser probe;
  this does not establish superiority on a real-paper corpus. TexSoup remains a
  comparison dependency, not a runtime requirement.
- Used standard-library argparse and escaped HTML templates rather than adding
  CLI/template libraries. JSON, terminal and HTML use one checker result.
- Adopted current official MCP 2.2 as an optional extra, using its actual APIs.
  Exact proposal JSON text avoids silently changing Decimal selectors at protocol
  boundaries. Proposal tools return values without writing files.
- Retained a local OS lock, per-file atomic replacement and recovery journal.
  No claim is made that multiple filesystem writes form one atomic operation.
- Calkit and scitexlintr passed their mechanism probes and a configured local CLI
  update workflow. Reduced migration cost and better review experience remain
  hypotheses, not established advantages.

## Local acceptance completed

- The [local model run](local-model-evaluation.md) returned twelve invalid proposals.
  All were refused; raw inputs/outputs, zero matched reference targets and the three
  missed abstentions are retained. This small-model setup is not approved as an
  automatic mapper. No human correctness or timing measurements were invented.
- The [developer walkthrough](evidence/developer-first-use/evidence.json) used
  thirteen actual CLI steps: ten explicit bindings, eight data-update mismatches,
  eight numeric writes, ten passing rechecks and exact recovery. Both the synthetic
  inputs and mapping were authored by Codex; this is not an independent user trial.
  A recording-helper assumption about the CLI's text response was corrected after
  the successful apply; that transaction was rechecked and recovered without repeating it.
- A [current-core performance run](evidence/performance-final.json) passed all 500
  bindings across twenty TeX files and 10 MB CSV; twenty warm runs had P95 1.866 s.
  Earlier 1.724 s results remain historical measurements with their original hashes.
- The final candidate has a [package audit](evidence/package-audit-final.json) and
  [identity/installation record](evidence/release-replay-final.json). Runtime, tests
  and frozen evaluation inputs remain identical to their tested versions.
- The [developer acceptance decision](release-acceptance.md) accepts the scoped
  local alpha under the owner's amended policy. Ten annotated real-paper literals
  and one authored developer workflow cannot establish population accuracy or adoption.

## Post-launch and environment-dependent follow-up

- Collect actual first-use feedback with the [trial protocol](first-use-trial.md).
  Three new users and the ten-minute target remain research goals; they do not
  block the owner's authorized local acceptance.
- Measure independent competitor onboarding and review time. The existing CLI
  comparison does not establish those benefits.
- Validate macOS and actual remote CI jobs when the respective environments are
  available. Current compatibility statements cover the recorded Windows/Linux runs.
- Arrange external repository/package publication separately. No repository or
  package has been published. The earlier PyPI name lookup is not a reservation.

## Full-scope checkpoint

The functional plan has been assessed under the owner's amended local acceptance
policy; the decision and limits are recorded in [release acceptance](release-acceptance.md).
PD-101–104, PD-201–205 and PD-301–304 have local functional evidence.
PD-003/004 and PD-402/403 have scoped implementation evidence.
PD-001 now has three public owned examples and local regression evidence; broader
independent adoption evidence is absent. PD-002 has a local CLI workflow comparison
but no independent onboarding-time measurements. PD-401 includes terminal
confirmation and abstract/table/repeated-candidate priority hints; developer
onboarding passed, with independent feedback deferred until launch.
PD-404 has local data-only/configuration regressions, job summaries and a
statically checked paper workflow template, not a remote PR run. PD-501 has the limited corpus
results above. PD-502 has Windows compatibility/performance measurements, Alpine
Linux evidence and four Python minors in a glibc Linux environment; macOS and
remote matrix cells remain open. PD-503 documentation is
available. PD-504 has a recording, corpus outcomes and a scoped CLI comparator
study. PD-505 produces audited local packages and a separately licensed evaluation
bundle; publication remains unperformed.
