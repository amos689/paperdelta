# CI and data-only changes

[简体中文](zh-CN/ci.md)

For the current reusable Action, finding transitions, SARIF and independent
paper-preflight workflow, use the [1.5 integration guide](v1.5.md). Historical
validation below is retained with its original scope.

The execution counts below are historical a2 evidence. Current release validation
is tracked separately in the [0.3.0 release notes](v0.3.md). Use a 0.3.0-or-newer
checker commit for schema-2 scope, exclusion and table-cell configurations.
The adapter reports exclusion changes by ID and scope changes with other settings.

The checked-in `.github/workflows/ci.yml` is the **tool development** matrix:
Windows, Linux and macOS, Python 3.11–3.14, read-only repository permissions,
tests, lint, owned-example validation, separate code/evaluation package builds,
archive content audits and preserved JUnit results. See the
[actual Actions runs](https://github.com/amos689/paperdelta/actions/workflows/ci.yml)
for each commit's results and downloadable evidence. A workflow file alone is
not cross-platform compatibility evidence.

macOS now uses separate `macos-15` Apple Silicon and `macos-15-intel` jobs,
each with Python 3.11–3.14. The [native platform validator](macos.md) installs the
built wheel in core-only and full-test virtual environments, checks host/CPU
identity, runs real POSIX terminal and filesystem tests, and preserves its logs.
Use each job's recorded system/architecture and test counts when assessing support.

Official Action revisions were resolved from their public repositories during
development: checkout v6.1.0, setup-python v6.3.0 and upload-artifact v4.6.2.
They are pinned to commit IDs in the workflow. Update these deliberately and
repeat the relevant checks when changing them.

## A paper repository's job

The [copyable workflow](../examples/ci/paper-check.yml) checks every pull request,
keeps report artifacts even on failure and preserves the checker's exit code as
the final job verdict. It checks out paper inputs and the checker into separate
directories. Configure these repository variables before enabling it:

- `PAPERDELTA_REPOSITORY`: `amos689/paperdelta`, or your reviewed trusted fork.
- `PAPERDELTA_REVISION`: its reviewed full 40-character commit SHA.

Choose a reviewed commit from the [release](https://github.com/amos689/paperdelta/releases)
and copy its full SHA; do not substitute a mutable branch name. The template rejects
absent settings.
Change `submitted-v1` if using another baseline name. Its history checkout makes
the PR target commit available; a manually dispatched run uses its selected commit.
The checker is installed from the pinned source, and `python -I` keeps the paper
checkout and `PYTHONPATH` out of Python's import search path. Only the trusted
checker copy is executed. The template uses read-only permissions and ordinary
`pull_request` events.

For a basic current-state check without the adapter:

Install a trusted PaperDelta release or wheel into a clean environment, then run:

```sh
paperdelta -C paper-project check --report build/paperdelta
```

Keep the command's exit code as the job verdict. Upload
`paper-project/build/paperdelta/` even when the check fails; put its `report.md`
in the job summary. Use exit code 2 for incomplete required checks, not success.
The supplied adapter instead writes a combined `ci-summary.md` with declaration
changes and current findings, and appends it automatically when
`GITHUB_STEP_SUMMARY` is present. This follows GitHub's
[job-summary file interface](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary).
Stable packages are available on PyPI and GitHub Releases. Pin the PaperDelta version
in CI so tool upgrades are deliberate; use GitHub's SHA256SUMS to verify downloaded artifacts.

Trigger checks for relevant CSV/JSON, figure, source-record, configuration and
LaTeX changes. Do not filter reports to changed LaTeX lines: the regression
`test_data_only_change_finds_every_affected_span_and_false_claim` changes only CSV
and checks all affected paper locations.

If historical comparison is needed, retrieve a committed baseline from the PR's
target revision into the check workspace and use its name with `--baseline`.
Do not create a new snapshot from the proposed changes and call it the old state.
Review changes to mappings, rules, snapshot files and review declarations as part
of the PR; an editable local record is not an authenticated approval.

For an untrusted paper PR, execute the installed checker, not scripts from that
paper repository. Use read-only tokens and ordinary `pull_request` events. Inline
PR comments and remote writes are outside the current adapter; downloadable
reports do not need such permissions.

## Target-commit snapshot wrapper

Use `--lang en` or `--lang zh-CN` for the wrapper's help, diagnostics, report and job
summary. It shares the CLI's flag/environment/project-preference/system precedence.
The stored report and `ci-context.json` retain canonical machine fields and identities.
Raw Git or other third-party error details are preserved in their original language.

`tools/ci_check.py` is an adapter to run from a **trusted PaperDelta copy**,
using an environment with the matching package installed:

```sh
python -I /trusted/paperdelta/tools/ci_check.py \
  --project /workspace/paper-repository \
  --base-commit FULL_TARGET_COMMIT_SHA \
  --snapshot submitted-v1 --report build/paperdelta
```

Fetch the target commit before invoking it. It reads the snapshot blob directly
from that commit with Git, never from the PR's same-named working-tree file.
The adapter writes `ci-context.json` with the target SHA and snapshot hash next
to normal reports. A missing target snapshot is explicitly unavailable; current
consistency checks still run. A missing commit or malformed snapshot is an error.
No target source files are checked out or executed.

`--config` selects a canonical project-relative configuration path. For another
CI system, `--summary-file` appends to a chosen file outside the paper root; the
completed check also saves a project-relative `ci-summary.md`. Output files cannot
replace checked inputs, configurations, snapshots or review declarations.

## Changes to the check itself

The version-1 CI context inventories the selected configuration and JSON files
under `.paperdelta/baselines` and `.paperdelta/reviews`. Each added, modified or
removed file has a category and target/current SHA256 values. The inventory
compares working-tree bytes with target-commit blobs, including deleted files
and newly added declarations.

Configuration comparison uses the same safe loader and strict models as the
checker. It separately lists added, removed and changed IDs under sources,
metrics, occurrences, claims and figures, plus changed settings such as rounding,
paper configuration and completeness requirements. Formatting-only differences
remain file changes with unchanged configuration semantics. If either side
cannot be parsed, semantic comparison is unavailable; it does not claim equality.

Declaration changes do not automatically change the numerical check verdict.
For example, deleting four result bindings and one comparison can leave a single
passing binding. The CI summary must then show the reduced coverage and removed
IDs. A PR's rewritten snapshot remains a visible declaration change; historical
comparison still reads the target snapshot.

The adapter reads regular Git metadata files only, up to 2000 files, 32 MiB per
file and 64 MiB per side; configuration semantics retain the core's 1 MiB limit.
Changing declarations during a check is an error. Summaries escape source text
and limit displayed rows/values, with a 900 KiB size cap. Full JSON and ordinary
reports remain in the artifact directory.

## Reproduce the local examples

From this trusted checkout, with Git and PaperDelta installed:

```sh
python tools/demo_ci.py --out build/ci-demo
```

The command creates two new synthetic repositories and changes no existing paper:

| Scenario | Current check | CI review |
| --- | --- | --- |
| Data-only update, 84.1% → 80.9% | Exit 1; five mismatches | All affected locations remain visible although all TeX bytes are unchanged |
| Same update plus removed bindings and rewritten snapshot | Exit 0; one remaining confirmed check | Lists four removed occurrences, one removed claim and both changed declaration files; compares against the original target snapshot |

Read the generated `build/ci-demo/CASE/build/review/ci-summary.md` or the retained
[data-only summary](evidence/ci-adapter/data-only/ci-summary.md) and
[changed-declarations summary](evidence/ci-adapter/changed-declarations/ci-summary.md).
Use a new output directory for another run.

Ten adapter tests passed on four local Windows Python versions and one Alpine
Linux/Python 3.14 guest. They include actual Git object reads, CLI exit codes,
job-summary output, isolated imports and output protection. The full Windows
Python 3.12 suite passed 162 tests. Both workflow files passed
[actionlint](https://github.com/rhysd/actionlint) 1.7.12 static checks.
[Evidence and exact file hashes](evidence/ci-adapter/evidence.json).
These historical results are local and static checks. Later remote runs are
recorded separately in Actions and do not change these original counts.
