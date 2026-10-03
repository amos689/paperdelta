# Start PaperDelta on a Mac

[简体中文](START_ON_MAC.md)

The locally accepted v0.2 candidate has a matching transfer at
`build/mac-transfer-v0.2/paperdelta-0.2.0a1-mac-transfer.zip` in the development checkout.
Use this 0.2.0a1 package; the 0.1.0a2 transfer remains historical. These steps apply
to the portable source/wheel package;
its version is in `TRANSFER.json`. It includes source, docs, tests, owned examples
and a Python wheel, excluding Windows environments, temporary results and model
weights. No native Mac pass has been recorded.

## Copy and extract

Copy the rebuilt `paperdelta-VERSION-mac-transfer.zip` using a USB drive, external
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
`install/paperdelta-evaluation-VERSION.zip` contains optional separately licensed
paper evaluation materials and is not needed for these checks.
