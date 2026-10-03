# macOS preparation and native validation

[简体中文](zh-CN/macos.md)

Install from the public repository using the [Mac quick start](../START_ON_MAC.en.md),
or use a wheel from [GitHub Releases](https://github.com/amos689/paperdelta/releases).
Create a new environment on the Mac. The quick start also preserves the original
local transfer procedure for reproducing the first native validation; those
historical transfer archives are not included in a GitHub clone.

**Native validation passed on 2026-10-03:** Apple Silicon arm64, macOS 27.0.1,
Python 3.12.14 and 3.14.6, each 241 passed with zero failures/errors/skips.
Chrome 154.0.8037.97 also passed offline bilingual desktop/mobile and keyboard checks.
See the [execution record](macos-validation-2026-10-03.md). Intel, other macOS/Python
combinations, Safari and remote CI remain untested in this round.

## Architecture and installation

The macOS workflow has eight explicit cells:

| Runner | Interpreter architecture | Python |
| --- | --- | --- |
| `macos-15` | Apple Silicon `arm64` | 3.11, 3.12, 3.13, 3.14 |
| `macos-15-intel` | Intel `x86_64` | 3.11, 3.12, 3.13, 3.14 |

These labels follow the
[GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
They pin the OS family and architecture, not an immutable image. Actual host
and interpreter versions are recorded per run. See
[Actions results and artifacts](https://github.com/amos689/paperdelta/actions/workflows/ci.yml)
for remote execution; those results are separate from the local return above.

The [Python macOS installers](https://docs.python.org/3/using/mac.html) provide
universal2 builds for Apple Silicon and Intel. Use a native interpreter and a
project virtual environment. The checker does not need Homebrew, CUDA, a TeX
distribution or an application signing step. Python dependency installation may
download packages; the checker itself remains local.

## Actual checks

`tools/validate_platform.py` uses a supplied, matching wheel. It creates fresh
core-only and full-test environments under a new output directory. It then runs:

1. Core-only CLI success, data-only failure, HTML output and the missing-MCP error.
2. Installed-package source identity checks and the entire pytest suite.
3. The existing real-process lock/contention and interrupted-write recovery cases.
4. NFC and NFD accented filenames with Chinese directories and BOM/CRLF recovery.
5. POSIX symlinked roots, rejection of a symlink leaving the root and preserved modes.
6. Actual POSIX pseudo-terminal acceptance and cancellation, with JSON stdout kept
   separate from terminal prompts. These are automated terminal operations.
7. Public examples, actual stdio MCP in the suite and local Git CI demonstrations.

On native macOS/Linux, a skipped test prevents the script from declaring success.
The Windows regression legitimately skips the three POSIX-only cases and records
that fact. CI uploads the result JSON, logs and JUnit, excluding the virtual
environments. No human trial is required.

For an audited source checkout rather than the transfer ZIP:

```sh
python3 tools/validate_platform.py --wheel build/release-candidate/paperdelta-*-py3-none-any.whl --out build/mac-validation --require-system Darwin
```

For Apple Silicon, add `--expected-arch arm64`; for Intel, add
`--expected-arch x86_64`. The macOS CI uses both the host and architecture guards.
Rosetta execution is refused rather than counted as native Apple Silicon evidence.
The validator retains the sysctl exit code and output; a denied or absent probe stays
unknown (`null`), not a confirmed native result. This run independently recorded
`hw.optional.arm64=1`, `hw.machine=arm64` and `sysctl.proc_translated=0`.

Use paths with the spelling stored in the project, including filename case.
The Unicode tests use each declared spelling consistently; they do not claim
interchangeable NFC/NFD aliases or case variants across every filesystem.
Network volumes and power-loss durability remain outside the verified scope.

## Transfer contents and integrity

`tools/build_transfer.py` starts from the audited source distribution and wheel.
The ZIP includes `START_ON_MAC.md`, source/tests/docs/owned examples, the wheel
under `install/` and the separately licensed evaluation ZIP. It verifies every
ZIP member, retains per-file SHA256 values in `TRANSFER.json` and emits
`SHA256SUMS` beside the ZIP. No setup command changes the system Python.

The full validation script's Windows execution only verifies the script and the
Windows-compatible paths. The current
[preparation evidence](evidence/macos-preparation.json) identifies the actual
historical preparation checks. The [native Mac record](macos-validation-2026-10-03.md)
adds new evidence without changing those frozen files.
