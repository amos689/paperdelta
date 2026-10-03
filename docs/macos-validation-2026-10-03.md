# Native Mac acceptance — 2026-10-03

[简体中文](zh-CN/macos-validation-2026-10-03.md)

**Accepted for this local development preview on the tested Mac.** macOS 27.0.1
(build 26A434), Apple Silicon arm64, native CPython 3.12.14 and 3.14.6. Each final
installed-wheel suite passed **241 tests, zero failures, errors or skips**.
No product runtime changes, publishing, pushing or independent participant tests
were performed. [Machine-readable results](evidence/macos-native-20261003/summary.json)
record the tested wheel, source identities and evidence locations.

## Received package and execution

All 1,060 `TRANSFER.json` entries passed path, symlink and SHA256 checks before
editing. `handoff/BASELINE.json` agrees on the version, Windows source commit,
wheel and all 32 runtime files/resources, 26 original test files and 29 tools.
The Windows source commit is `5ea7d27e28e5308f6ef3cf5ab4c7f807fb575f64`;
the separately created Mac receipt commit is `722c0032d88ba2692f6737c48e86272dd293e735`.
Only this repository's Git identity was configured, using the handoff's noreply address.

The unchanged `install/paperdelta-0.2.0a1-py3-none-any.whl` has SHA256
`c6f119ad4ded3e7866dd0f7efd233cac9466fd26cf9d9afe0eefdd7b6cf80c78`.
Both original suites passed 237 tests. Four additional validation-tool regressions
explain the final count of 241. Every final suite verifies all 32 installed runtime
files/resources against the source. Only tools, tests and documentation changed,
so the matching original wheel was tested again in fresh environments; no rebuild
was needed. Original and final installation, JUnit and command logs are retained.

For each recorded interpreter, the full command was:

```sh
/path/to/native/python tools/validate_platform.py --wheel install/paperdelta-0.2.0a1-py3-none-any.whl --out build/NEW_DIRECTORY --require-system Darwin --expected-arch arm64
```

Each successful validation includes fresh core/full installations, bilingual core
smoke checks, data-only diagnostics, Ruff lint/format, the full installed-package
suite, examples and local Git CI scenarios. Hardware probes independently reported
`hw.optional.arm64=1`, `hw.machine=arm64` and `sysctl.proc_translated=0`.

## Developer walkthrough and browser

Using the installed Python 3.14 wheel, the developer drove actual CLI commands and
POSIX terminals: bilingual help/doctor/check; all language precedence levels; six
passing example bindings; data-only mismatches; ten guided bindings in Chinese
paths with model ID `001`; construction/final cancellation with no writes; and
explicit final confirmation. Ten numeric edits were previewed, applied, rechecked
and recovered to exact UTF-8 BOM/CRLF bytes. Location repair preserved source,
metric, unit, display and claim definitions, and all non-configuration input bytes.
A real stdio MCP connection listed all 13 read-only tools and checked the project
without writes. These were authored automated inputs, with zero independent users.

Native Google Chrome 154.0.8037.97, driven headlessly using the existing browser QA,
passed both languages, all five filters, bilingual search, evidence expansion,
state/focus retention, Enter/Tab operation, offline/no-JavaScript reading, desktop
1365×1000 and narrow 375×812 layouts. No external requests, script errors or horizontal
overflow were recorded. Desktop Chinese and narrow screenshots were visually reviewed.

## Failures retained and corrections

- The first installation failed because sandbox DNS could not resolve PyPI. A fresh
  authorized run outside that restriction installed dependencies successfully.
- The original browser recorder incorrectly described every host as Windows. It now
  records the actual OS, kernel, architecture and Node version; focus and keyboard
  checks were also added. The original mislabelled record is retained as superseded.
- A denied/absent Rosetta probe was previously recorded as `false`. It now retains
  exit code/stdout/stderr and reports `null` when unknown. Four cases cover native,
  translated, absent and denied probes. This Mac's successful probe returned `0`.
- The first additional walkthrough recorder compared raw YAML dictionaries after
  default fields had been serialized, causing a false assertion. Its original log,
  script and diagnosis remain. The corrected recorder compares the complete typed
  source/metric/claim definitions and independently verifies unchanged other bytes.
  Product behavior was unchanged and the full walkthrough then passed.

## Scope and return

Intel Mac, Python 3.11/3.13, other macOS releases, Safari/Firefox, remote CI,
independent users, power-loss durability and network filesystems were not tested.
No unresolved issue was found within this round's agreed local acceptance scope.
Historical corpus/model limitations remain as documented; they were not re-scored.

The Mac return ZIP contains bilingual reports, a binary/full-index patch, changed
files with before/after hashes, all failed/final logs and JUnit, selected HTML and
screenshots, wheel hashes, unresolved/untested items, and a verified manifest.
Public text replaces the checkout with `<checkout>` and home directory with `<home>`;
raw local records remain in `build/`, and a provenance index records both hashes.
Copy the ZIP and its `.zip.sha256` together into the Windows repository's
`build/mac-return-inbox/`, verify the checksum, then review and merge the patch.
The receive-time `TRANSFER.json` and `handoff/BASELINE.json` remain unchanged.

## Windows review and integration

On 2026-10-03 the original Windows workspace verified the return ZIP checksum,
all 321 members, 320 manifest entries and all 21 changed files' before/after hashes.
The supplied transfer/baseline identities match the package sent to the Mac.
Both final JUnit files agree with the execution records: 241 passes each, retaining
all 237 original cases plus four new validator cases. All 32 runtime files and the
original wheel remain identical. The public provenance index's 288 files and five
links to original run hashes were checked too.

The two tool fixes, four regression cases and bilingual docs were accepted. A fresh
Windows execution of the merged suite against the installed original wheel on
Python 3.12.14 passed **238 tests with 3 POSIX-only skips**. The updated QA also
passed in Windows Chrome 154.0.8037.93, including language-switch focus and keyboard
operations, with no external requests or script errors. Ruff and documentation
checks passed. These are new Windows checks; Linux was not rerun for these tool changes.

The [original return ZIP](evidence/macos-native-20261003/return.zip) preserves both
failed and successful Mac evidence, reports, scripts, patch and its manifest without
rewriting them. The [integration record](evidence/macos-merge-20261003/integration.json),
[Windows suite](evidence/macos-merge-20261003/windows-regression.json) and
[Windows browser record](evidence/macos-merge-20261003/windows-browser.json) record the
receiving-side checks. New evidence uses separate paths; historical records retain
their original bytes. The updated candidate is in `build/release-candidate-v0.2-mac`.
