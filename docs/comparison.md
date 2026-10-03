# Local workflow comparison

This is a developer-prepared command-line comparison, run on Windows with
Python 3.12.14, Calkit 0.47.12, scitexlintr 0.2.1 and PaperDelta 0.1.0a1.
[Recorded commands and outputs](evidence/reference-workflows.json) include
versions, exit codes, durations and retained-file hashes.

The same owned four-file paper and CSV start with Ours = 84.1%, Baseline = 81.0%.
Five numeric sites include the abstract, table, difference and appendix; one
sentence says Ours outperforms Baseline. Only the three Ours test rows then change,
making their mean 80.9%. The baseline, train rows and paper text remain unchanged.
There is no figure in this comparison; the separate PaperDelta demo tests figures.

## Setup required for this particular implementation

| Tool | Explicit configuration | Edits to the starting paper |
| --- | --- | --- |
| PaperDelta | Existing YAML declares typed CSV columns, keys, seed sets, two means, one difference, five occurrences and one comparison | Zero existing TeX files edited |
| Calkit | An owned CSV-to-JSON exporter, five evidence-backed questions and two DVC stages; conditional gain/comparison answers | Six result sites replaced by generated answer macros across three content files; one include added to the main file |
| scitexlintr | The same selection/calculation in an owned exporter; a manifest and generated value/text macros | Six result sites wrapped across three content files; one include added to the main file |

These are working configurations, not a claim that they minimize any tool's
setup cost. A result site can be a whole sentence. Counts do not measure how
hard configuration was to author, and a larger YAML file is not necessarily
harder than a short script. Installation and human mapping time were not timed.

Calkit natively evaluates the declared conditional answer. For scitexlintr,
the exporter evaluates that condition and places the resulting text in its
manifest; the linter checks and repairs the corresponding `SciText` snapshots.
This gives the text workflow a fair working input rather than omitting it.
The exporter is comparison support code, not a released PaperDelta adapter.

## Observed update and review behavior

| Tool | After only the CSV changes | Next action and observed result |
| --- | --- | --- |
| PaperDelta | Exit 1; four numeric mismatches and one false comparison; original paper bytes unchanged | `fix` returns 2 because all four numeric suggestions depend on the false comparison; no patch or source edit is produced |
| Calkit | `check questions --json` returns 1 because upstream evidence is out of date | `calkit run` reruns the CSV exporter and question-to-LaTeX stage; generated output contains 80.9%, -0.1 points and “does not outperform”; evidence check returns 0 |
| scitexlintr | After explicitly regenerating the manifest/macros, lint returns 1 with five snapshot mismatches, including the comparison text | `--write` changes three source files, updates numeric/text snapshots and re-lints successfully with exit 0 |

All three workflows behaved as configured. Calkit keeps a declared template
current through its pipeline. scitexlintr preserves reviewable snapshots next
to generated macros. PaperDelta retains existing handwritten source and
collects the affected positions for review, with a conservative write boundary
when the bound comparison becomes false. These are different workflow choices.
This experiment does not establish superior accuracy or lower adoption time.

PaperDelta's refusal in the reversed-comparison case is intentional. Its
separate positive-change demo exercises numeric apply, recheck and recovery.
A Calkit evidence check passing means its configured evidence is current;
a successful scitexlintr lint means the selected rules pass. Neither result,
nor PaperDelta's exit 0, proves scientific correctness.

## Reproduce

Use a development environment with PaperDelta installed and a separate reference
environment. Run these commands from the checkout root; activate the development
environment first. The reference environment is not a runtime dependency:

```sh
python -m venv .venv-references
# Windows:
.venv-references/Scripts/python -m pip install calkit-python==0.47.12 scitexlintr==0.2.1
# POSIX alternative: .venv-references/bin/python -m pip install the same packages.
python tools/compare_workflows.py --out build/reference-workflows
```

The runner preserves the complete scratch projects, setup diffs and command
transcripts. It creates a dedicated local Git/DVC repository for Calkit, makes
no commits or remote changes, and executes only the owned exporter. A repeat
requires a new output path. The script assumes the development environment is
the checkout's `.venv`; its reference environment can be supplied explicitly.

During preparation, the first harness expected a literal hyphen in generated
TeX, but Calkit correctly emitted `{-}`. A second attempt supplied the
scitexlintr percent value as a string; its percent renderer requires a numeric
fraction. Those harness assumptions were corrected before the successful run.
The initial local outputs are preserved under `build/reference-workflows-first`
and `build/reference-workflows-v2`; the archived successful record is v3.

This run does not compile the generated reference papers, measure reading or
confirmation time, evaluate model proposals, or involve independent first-time
users. Independent first-use comparisons are post-launch follow-up work under the
project owner's revised acceptance policy; macOS and remote CI remain unverified.
The [research notes](research.md) link the primary documentation and code
that informed these configurations.
