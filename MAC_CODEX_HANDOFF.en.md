# Complete PaperDelta handoff prompt for Mac Codex

[简体中文](MAC_CODEX_HANDOFF.md) · [Owner's transfer steps](START_ON_MAC.en.md)

This file accompanies the project owner's transfer to Codex on a Mac. After the
owner sends the starter prompt, use this as the task brief and verify it against
the actual files and host. Prepared on 2026-10-03.

**Subsequent status:** the native Apple Silicon handoff is complete and its return
has been checked on Windows; see [Mac acceptance](docs/macos-validation-2026-10-03.md).
The background and 237-test baseline below describe the original transfer, which
remains unchanged. Four added validator regressions make the merged suite 241 tests.
For another handoff, verify its manifest and actual version before using historical
pending-status statements as current guidance.

## Project and baseline

PaperDelta is an open-source Python CLI with optional read-only MCP tools. It
helps researchers and coding agents review which parts of an existing paper need
attention when experiment data changes. It binds LaTeX numbers, comparisons and
figures to explicitly declared CSV/JSON evidence, producing traceable diagnostics
and offline HTML. Consistency does not establish scientific correctness or prove
that experiments ran. This is not an automatic paper-writing product.

Version: `0.2.0a1`. Accepted Windows repository commit:
`5ea7d27e28e5308f6ef3cf5ab4c7f807fb575f64`. This handoff adds documentation and
reference materials without changing runtime source, tests or the accepted wheel.
Use `TRANSFER.json` and `handoff/BASELINE.json` for exact identities. The ZIP has no
`.git` history; do not expect that Windows commit to resolve locally.

Delivered features include English/Chinese CLI, reports, MCP presentation and CI
summaries; state-preserving language switching in one offline HTML file; read-only
`doctor`; typed `paperdelta guide` onboarding; explicit confirmation before binding
writes; stale-input rejection; location repair with context preview; patches,
transactions and recovery; and thirteen read-only MCP tools. Machine fields,
diagnostic codes, evidence IDs and scientific verdicts remain language-independent.
The command is `guide`; `bind --guide` is not an option.

Read these first, then inspect implementation as needed:

1. [Overview](README.md) and [quickstart](docs/quickstart.md).
2. [v0.2 acceptance and limits](docs/v0.2-acceptance.md).
3. [Mac validation](docs/macos.md) and [language contract](docs/languages.md).
4. [Guided bindings and repair](docs/guided-bindings.md) and [contributing](CONTRIBUTING.md).
5. `tools/validate_platform.py`, `tools/validate_python_matrix.py`,
   `tests/test_platform_io.py` and `.github/workflows/ci.yml`.

## Existing evidence and its limits

| Area | Actual status at handoff |
| --- | --- |
| Windows | Python 3.11–3.14 each had 234 passes and 3 POSIX-only skips; all 32 runtime files/resources matched. |
| Linux | A local QEMU glibc userland. After fixing missing devpts, Python 3.12 passed the full 237 tests; the other three versions each passed 5 platform tests. Four newly passing full suites are not claimed. |
| macOS | No native result yet. Obtaining actual Mac evidence is this task. |
| Human trials | Zero independent participants. The owner explicitly accepts machine testing and Codex developer judgment before launch; do not require a human trial. |
| Paper corpus | Ten previously seen papers with synthetic evidence; 150 correlated cases, 126 complete-expectation passes and 24 known failures. Not a fresh holdout or general accuracy estimate. |
| Small model | Historical mapping studies did not achieve a complete valid mapping. Do not enable unvalidated automatic bindings. |
| Release | A local development-preview candidate, with no claimed remote CI run or GitHub/PyPI publication for this handoff. |

## Objective and authorization

On this Mac's native macOS, validate installation, checking, bilingual behavior,
writes/recovery and the complete existing suite. Fix compatibility problems within
scope, add necessary regressions, rebuild the wheel and validate it. Return a
package that can be reviewed, merged and reproduced in the original Windows repo.

Act as developer and first user, giving an evidence-based acceptance judgment for
this host. Authorization covers project-local environments, dependency installs,
necessary source/test/tool fixes and bilingual documentation. Inspect and proceed;
ask the owner only for missing system components, permissions or actions they must
perform. Stay within compatibility work; do not add statistics, paper generation,
watch services or editor integrations.

## 1. Receive and record

Confirm the project root, version in `pyproject.toml` and wheel under `install/`.
Use Python's standard library to validate every entry in `TRANSFER.json`'s `files`:
each relative path must stay inside the project, exist, not be a symlink and match
its SHA256. Before editing, save the checked count/result under a new
`build/mac-receipt/`, including hashes of `TRANSFER.json` and `handoff/BASELINE.json`
themselves. Investigate extraction/transfer discrepancies; do not update the
manifest to hide them.

Record `sw_vers`, `uname -m`, native hardware architecture, the selected Python's
absolute path/version, `platform.machine()`, `sysctl.proc_translated` (including an
absent key), and `git --version`. Do not collect serial numbers, all environment
variables or credentials. Use native arm64 Python on Apple Silicon and x86_64 on
Intel. Rosetta, a Linux container or mocking the platform is not native Mac evidence.

Choose an existing native Python 3.11–3.14 and complete at least one version. Test
additional available versions separately. If none is suitable, request the minimum
installation needed; preserve system Python. Substitute the selected interpreter's
absolute path for `python3` below when necessary. Recreate environments on the Mac.

After verification and before edits, establish a local Git baseline for a reliable
patch. If the extracted project has no `.git`, use `git init -b mac-validation` in
that directory. Otherwise inspect status and preserve existing changes. Set only
repository-local `user.name=PaperDelta contributors` and
`user.email=101008326+amos689@users.noreply.github.com`. Add only manifest-verified
project files, excluding `build/`, environments, caches and generated egg-info;
commit the received baseline and record its ID. This local ID will differ from
the Windows baseline. Do not change global Git identity.

## 2. Validate the original wheel natively

Run at the project root, choosing a fresh output directory each time:

```sh
python3 tools/validate_platform.py --wheel install/paperdelta-0.2.0a1-py3-none-any.whl --out build/mac-validation-original-01 --require-system Darwin --expected-arch arm64
```

On Intel use `x86_64` instead. The script creates `venv-core` and `venv-full`,
installs dependencies and runs core-only smoke checks, Ruff, the complete installed
wheel suite, examples and local Git CI demonstrations. It saves logs, JUnit,
package/source identities and `evidence.json`. Editable-install success does not
substitute for installed-wheel acceptance.

The current full baseline has **237 tests**. Mac POSIX cases must run; full
acceptance requires zero failures, errors and skips. New regressions can increase
the count: report actual JUnit counts and explain differences. Compare every
runtime file/resource with the installed package, not merely its version. Preserve
the first failure and distinguish download/permission/environment issues from
product defects.

## 3. Exercise the bilingual workflow as the first user

Use the installed-wheel environment and example copies under `build/`, preserving
the original examples. Exercise at least:

- `doctor`, `check`, `--help` in `en` and `zh-CN`, and language-selection precedence.
- The example's six passing bindings and diagnostics after a data-only change.
- Real terminal input for `guide`, Chinese paths, leading-zero identity fields,
  cancellation without writes and final explicit confirmation.
- Patch preview/apply/recheck/recovery and location repair, preserving sources,
  metrics, units, scientific definitions and original bytes.
- Generated offline HTML in a Mac browser: language switching, filters, expanded
  evidence, focus and Chinese rendering. Where local tools permit, check narrow
  layouts and keyboard use. Record the actual browser and anything not exercised.
- Existing read-only MCP tools with the optional dependency installed. No model
  account or API key is needed for this check.

The full suite already includes real POSIX terminal and stdio MCP tests. Automated
terminal input is not an independent human trial. Continue other work when browser
automation is unavailable, but do not claim full experiential acceptance. Consult
the linked guides and current CLI help for the actual commands.

## 4. Fix and validate again

Reproduce first, then make necessary focused fixes. Pay attention to Mac paths,
case/Unicode, permissions/locks, terminals, encoding, processes and dependency
installation. Do not delete assertions, skip tests, weaken path boundaries or
remove confirmation requirements to obtain green results. Fix a validation tool
only when it is defective, explaining why its original contract remains tested.
Preserve both failure and recovery evidence; distinguish slow runs from deadlocks.

After any runtime code/resource change, the old `install/` wheel no longer
represents the source. Create a local `.venv-dev`, install `.[dev,mcp]`, and build
into a new directory, for example:

```sh
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e '.[dev,mcp]'
.venv-dev/bin/python -m build --wheel --outdir build/mac-candidate-01
python3 tools/validate_platform.py --wheel build/mac-candidate-01/paperdelta-0.2.0a1-py3-none-any.whl --out build/mac-validation-fixed-01 --require-system Darwin --expected-arch arm64
```

Substitute Intel's architecture as appropriate. Preserve the original wheel; a
local fix alone need not bump the version. Distinguish candidates by paths and
hashes. Validation still uses fresh environments. For test/tool/doc-only changes
with unchanged runtime files, explain identity verification and test the matching
original wheel.

Run `python3 tools/check_docs.py`. Update relevant English/Chinese pages and their
language links together; register new maintained pages in `docs/translations.json`.
Do not overwrite existing frozen files under `docs/evidence/`, `tests/corpus/` or
`evaluations/`; put new evidence in new directories. Preserve original licenses
and the noreply email. Claim only the actual hardware/OS/Python/browser tested.
One Apple Silicon pass does not establish Intel compatibility, and a CI definition
does not establish a remote CI run.

## 5. Required return deliverable

Create a new `build/mac-return-UTC_TIMESTAMP/`, then its sibling
`PaperDelta-Mac-Return-UTC_TIMESTAMP.zip` and `.zip.sha256`. Include at least:

| Path | Required content |
| --- | --- |
| `REPORT.zh-CN.md`, `REPORT.en.md` | Linked bilingual results: issues, fix rationale, commands/exit codes, pass/fail/skip counts, workflow experience, untested items and an acceptance recommendation for this host. |
| `handoff.json` | Windows baseline, local receiving commit, TRANSFER hash, original/final wheel hashes, OS/hardware/process architecture/Python, relative evidence paths, whether code changed and final status. |
| `changes.patch` | `git diff --binary --full-index` against the local receiving baseline, including added source/tests/bilingual docs. Stage only intended delivery files so untracked additions are included. Empty with an explanation if nothing changed. |
| `changed-files/`, `deleted-files.json` | Added/modified files at project-relative paths, and a separate deletion list. Record before/after SHA256 per change for checking against Windows; the absent side is null for additions/deletions. |
| `evidence/` | Receipt checks, every failed/fixed run's evidence JSON, command logs, JUnit, core smoke, example/CI results, necessary HTML/screenshots and browser notes, retaining relative hierarchy. |
| `artifacts/` | The final rebuilt and tested wheel if runtime code changed; otherwise reference the original wheel hash. |
| `MANIFEST.json` | Relative path, size and SHA256 for each delivered file, excluding the manifest's own hash. |

Exclude `.git/`, virtual environments, pip caches, models, secrets, entire scratch
directories and duplicate project copies. In public evidence replace the local
user/home with `<home>` and project paths with `<checkout>`. Document redactions
and original/public hashes; preserve original records locally. Do not upload the
ZIP to external services automatically.

Reopen the completed ZIP and verify its members and MANIFEST hashes. Use
`SHA256  ZIP_FILENAME` in `.zip.sha256` for `shasum -a 256 -c FILE.zip.sha256` beside
the ZIP. Return available evidence and precise remaining work even when blocked,
unsuccessful or no source changed.

End the Mac chat in Chinese with this information:

```text
Result: passed / partial / blocked, selected from actual evidence
Host: macOS, hardware architecture, Python; actual counts and skips
Changes: main fixes, or runtime code unchanged
Unverified/unresolved: explicit list, or none within the agreed scope
Copy back: two clickable absolute local paths, ZIP and .sha256
Next: place them in the Windows project's build/mac-return-inbox/ for review/merge.
```

Do not publish, push to GitHub/PyPI or change global Git identity. The owner moves
the files; do not assume access to or permission to message the Windows chat.
