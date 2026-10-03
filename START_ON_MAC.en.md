# Start PaperDelta on a Mac

[简体中文](START_ON_MAC.md)

## Install from GitHub

Use Python 3.11+ and run in a Mac terminal:

```sh
git clone https://github.com/amos689/paperdelta.git
cd paperdelta
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
paperdelta --lang en -C examples/research-paper doctor
python tools/demo.py --out build/demo
```

Open `build/demo/comparison-reversed/review/report.html`. Connect your own paper
with the [quick start](docs/quickstart.md); see
[Actions](https://github.com/amos689/paperdelta/actions/workflows/ci.yml) for each
Mac architecture's results. To continue development, open the cloned `paperdelta`
folder as the project in Codex on the Mac. Development dependencies and checks are
in [Contributing](CONTRIBUTING.md).

## Historical transfer for the first native validation

The steps below preserve the original Windows → Mac handoff and return procedure.
Its `build/` archives were generated locally and are not part of a GitHub clone;
new installations can use the repository workflow above.

**To work with Codex on the Mac, use the new Codex handoff edition:**
`build/mac-transfer-v0.2-codex/paperdelta-0.2.0a1-mac-codex-transfer.zip`.
Copy its neighboring `SHA256SUMS` too. The original `build/mac-transfer-v0.2/`
is preserved.

This edition retains the accepted 0.2.0a1 wheel and runtime source, adding bilingual
handoff prompts, referenced documentation materials and a change baseline. It
contains source, tests, examples and historical evidence, without Windows
environments, model weights or Git history. Paper materials retain their
[individual licenses](THIRD_PARTY_NOTICES.md). This handoff originally had no native
Mac results. The [2026-10-03 Mac return](docs/macos-validation-2026-10-03.md) records
Apple Silicon macOS 27.0.1 with Python 3.12.14 / 3.14.6. That local return contains
no Intel tests; subsequent CI results are recorded separately.

## Historical handoff: give the transfer archive to Mac Codex

### 1. Copy two files from Windows

Open `build/mac-transfer-v0.2-codex` in File Explorer. Copy the ZIP and `SHA256SUMS`
using a drive accessible to both computers or your existing cloud drive. There is
no need to copy the whole Windows workspace or upload the project to GitHub first.

### 2. Save and extract on the Mac

Copy both files onto the Mac, for example into `PaperDelta-transfer` in Downloads.
Double-click the ZIP. Move the resulting `paperdelta-0.2.0a1` folder to a permanent
local location, such as a `Developer` folder in your home directory. Create that
folder in Finder if necessary.

The project folder should directly contain `pyproject.toml`, `src`, `tests`,
`install`, `MAC_CODEX_HANDOFF.md` and `TRANSFER.json`. If you see only another folder
with the same name, open that inner folder. Keep the original ZIP and checksum.

Optional manual checksum: in Terminal type `cd ` with a trailing space, drag the
**folder containing the ZIP and SHA256SUMS** into Terminal, press Return, then run:

```sh
shasum -a 256 -c SHA256SUMS
```

Expect `paperdelta-0.2.0a1-mac-codex-transfer.zip: OK`. You can leave this to Codex
if unfamiliar with Terminal; the prompt also requires checking every extracted file.

### 3. Open a local project in Mac Codex

Open Codex and sign in. Use its Add project/Open folder entry to choose the
extracted `paperdelta-0.2.0a1` directory, then start a chat in that project. If your
version uses Projects → project menu → Edit project → Add folder, add the same
folder as the local project's primary directory. Labels vary by version; the chat
must have access to that local folder. Attaching a ZIP to an ordinary chat does
not replace opening the local project. See the
[official local-project documentation](https://learn.chatgpt.com/docs/projects).

### 4. Send this starter prompt

```text
The open folder is the PaperDelta Mac handoff project. Read MAC_CODEX_HANDOFF.en.md
in full, then verify TRANSFER.json and handoff/BASELINE.json. Follow the handoff
to perform native macOS validation, necessary compatibility fixes and bilingual
documentation updates. I authorize project-local environments, dependency installs,
necessary code changes and tests. Act as developer and first user; no human user
study is required. Do not publish or push. Preserve real failures. Return the
required ZIP, SHA256 file, English/Chinese reports, code diff and test evidence,
and identify the two files to copy back to Windows. Inspect the project and host,
then proceed; explain only system installations or approvals that require me.
```

The full [English handoff](MAC_CODEX_HANDOFF.en.md) and
[Chinese handoff](MAC_CODEX_HANDOFF.md) contain the background, so you do not need
to reconstruct the development conversation.

### 5. Bring the result back

Codex checks the architecture, Python and Git, creates fresh environments and runs
the installed-wheel checks. If Python or Git is missing, let it explain the minimum
installation needed; you do not need to install an entire development toolchain
in advance. Dependency installation uses the network; everyday PaperDelta checks
need no model key, GPU or TeX.

Expect `PaperDelta-Mac-Return-TIMESTAMP.zip` and its `.sha256` file. The ZIP should
contain bilingual conclusions, changed files and a patch, artifact identities,
logs, JUnit and unresolved issues. Return evidence even when no code changed or a
run failed.

Copy the two files to a new `build/mac-return-inbox/` directory in the Windows
project, preserving the existing source. Send this in **the original Windows chat**:

```text
Mac Codex has finished this round. The return files are in build/mac-return-inbox/.
Please verify the package, baseline, changes and test evidence, then merge necessary
fixes, run Windows regressions, and update bilingual docs and the release candidate.
List any Mac checks still unverified.
```

The return package connects the two workspaces. Do not depend on a new chat knowing
this conversation or automatically sending its results back.

## Manual reference

Mac Codex can run the steps below; you need not repeat them yourself.

## Copy and extract

Copy the handoff ZIP using a USB drive, external
disk or cloud drive. Extract it and put `paperdelta-VERSION` where you want to keep
the project. Recreate the Python environment; do not copy Windows `.venv`.

Open Terminal, type `cd ` including the trailing space, drag the extracted folder
into the window and press Return. Run subsequent commands there.

## Check Python

```sh
python3 --version
```

Python 3.11+ is required; the configured matrix covers 3.11–3.14. If Python is absent
or too old, install a supported version from the [official Mac downloads](https://www.python.org/downloads/macos/)
and reopen Terminal. Official universal2 installers support Apple Silicon and Intel.
Use a project environment without changing system Python; see the
[official macOS guide](https://docs.python.org/3/using/mac.html).

## Run the example

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./install/paperdelta-*-py3-none-any.whl
.venv/bin/python -m paperdelta --lang en -C examples/research-paper doctor
.venv/bin/python -m paperdelta --lang en -C examples/research-paper check --report build/review
open examples/research-paper/build/review/report.html
```

Installation downloads normal Python dependencies. Checking needs no network,
model key, GPU, TeX or Xcode. Six passing confirmed bindings and a readable report
demonstrate the basic workflow.

```sh
.venv/bin/python tools/demo.py --out build/mac-demo
open build/mac-demo/comparison-reversed/review/report.html
```

The demo copies the example into a new directory, changes data and shows the
impact, preserving the original example. Use another output name for a repeat.

## Record native validation

Full validation also requires Git and downloads test/MCP dependencies:

```sh
git --version
python3 tools/validate_platform.py --out build/mac-validation --require-system Darwin
```

The script selects the wheel under `install/` and creates fresh core-only and full
test environments. It checks file locking, interrupted writes/recovery, Chinese
and accented paths, actual terminal confirmation, MCP, examples and local Git
scenarios, recording OS, architecture, logs and results. On Apple Silicon use
native arm64 Python; Rosetta translation is rejected. Keep separate output paths
for repeated runs to preserve evidence.

Send the final terminal result back to this chat. On failure keep
`build/mac-validation/evidence.json` and its `.log` files; there is no need to upload
the virtual environments. [macOS preparation](docs/macos.md) explains the scope.
`install/paperdelta-evaluation-VERSION.zip` retains the paper evaluation materials
and their licenses. The Codex edition already includes the frozen materials used
by documentation links at their original paths; do not extract the inner ZIP again.
