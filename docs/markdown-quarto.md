# Markdown and Quarto source review

[简体中文](zh-CN/markdown-quarto.md)

PaperDelta 1.2 reads literal prose and regular pipe tables in UTF-8 `.md` and
`.qmd` files. Both readers are in the core package. No Quarto, Pandoc, notebook
kernel, model or document rendering installation is required.

```sh
python -m pip install paperdelta
paperdelta demo --document markdown --out markdown-demo --open
paperdelta demo --document quarto --out quarto-demo --open
```

Each command needs a new output directory. The default scenario changes the
evidence from 84.1% to 80.9% while preserving the original manuscript. It shows
two outdated occurrences and a false comparison. `--scenario baseline` shows
the matching evidence. `safe-update` changes the evidence but creates no source
patch for either format.

## Connect an existing source

```sh
paperdelta init --paper paper.qmd --data results.csv
paperdelta studio
```

Alternatively start Studio in an unconfigured project and select its `.md` or
`.qmd` entry. Declare evidence column types, record keys, selectors, units and
any aggregation. Select the corresponding source numbers, inspect the proposed
bindings and explicitly accept them. The same number in two places does not
establish that they refer to the same experiment.

Terminal `guide`, batch binding, experiment templates, snapshots, scopes,
watching, reviewed binding repair and optional read-only MCP use the same model.
English/Chinese switching preserves selections and draft work. Complete literal
statistical expressions such as `82.00 ± 1.58 (n = 5)` and `[80.04, 83.96]` can be
bound using the [declared statistics workflow](statistics.md).

## Supported source structures

| Source | Checked position and identity |
| --- | --- |
| Paragraphs, headings, ordinary lists and block quotes | Literal numeric span in its original source block and section |
| Ordinary emphasis around a complete number | Original number bytes; formatting is retained |
| Markdown links and reference links | Visible literal label only; destinations do not supply results |
| Regular pipe tables with a separator row | Exactly one header row, literal row labels, named column and original cell position |
| Explicit companion `.md` / `.qmd` files | Separate declared manuscripts sharing named metrics |

Tables require at least two columns and consistent cell counts. Row reordering
does not silently reassign a binding: accepted headers and row identities are
resolved again. Duplicate rows or blocks remain ambiguous. Changing a heading,
header, label, prose context or formatting can invalidate an anchor; review the
new location with `paperdelta repair` or Studio. A literal numeric correction
alone can retain the same binding.

The reader uses CommonMark block structure plus pipe tables, not the complete
Pandoc/Quarto language. A candidate or successful binding checks literal source
content; it does not certify a rendered page. See the
[CommonMark specification](https://spec.commonmark.org/0.31.2/),
[Quarto Markdown syntax](https://quarto.org/docs/authoring/markdown-basics.html)
and [Quarto execution rules](https://quarto.org/docs/computations/execution-options.html)
for the broader languages.

## Original positions and read-only review

Schema 8 locations include `format: markdown` or `quarto`, source character and
UTF-8 byte intervals, one-based line/column, parser identity, section and optional
table/row/cell coordinates. End offsets are exclusive. BOM, CRLF and Unicode are
retained; the displayed excerpt is escaped text, not executed HTML. Source hashes
participate in stale-preview rejection, snapshots and file watching.

Markdown and Quarto are **read-only** in this release. Edit the original file in
your source editor and check again. `fix` cannot apply a patch to these formats,
even though their original byte positions are available. Guarded LaTeX patching
continues separately.

## Content that remains unverified

- YAML front matter, code fences, indented or inline code, inline execution,
  shortcodes, dynamic includes and fenced divs are not evaluated.
- Raw HTML, images/alternative text, citations, cross-references and visible
  URLs are not interpreted as numeric manuscript evidence.
- Math, raw TeX blocks, Pandoc grid/simple tables, irregular pipe tables,
  renderer-dependent attributes and unsupported inline syntax remain unverified.
- Numeric entities, escapes or formatting that joins separate numeric pieces
  do not become an invented continuous source span. Unsafe Unicode controls
  invalidate the file's readings; uncertain combining marks invalidate a block.
- A cell with unsupported syntax can invalidate its whole table; an unsupported
  inline construct can invalidate its whole paragraph. This conservative scope
  is displayed through `MARKDOWN_*` diagnostics and coverage.
- Raw HTML tags can affect content outside their parser blocks (for example a
  hidden container or CSS). Non-comment HTML therefore invalidates numeric
  readings throughout that source file.

Unsupported content produces exit 2 even if particular accepted bindings pass.
It is not silently treated as complete coverage. An ordinary Quarto document
with YAML or executable cells can therefore have verified literal results and an
incomplete overall check. No code, filter, project configuration, remote resource
or include is executed, fetched or followed. Declare additional static source
files as companions instead of expecting include traversal.

Limits: 4 MiB per source, 20,000 lines, 65,536 characters per line/inline block,
10,000 source blocks, 100 table columns and 10,000 cells per table. Inputs beyond
these limits are rejected or explicitly unverified.

## Explicit PDF export comparisons

Install `paperdelta[pdf]` for PDF reading. Declare the PDF and its actual source:

```sh
paperdelta manuscript add --file export.pdf --export-of paper.qmd
paperdelta manuscript add --file export.pdf --export-of paper.qmd --accept
```

The first command previews the declaration; the second accepts it with a backup.
Bind each compared metric explicitly in both documents. Once the source is
corrected to match changed evidence, an older PDF occurrence is reported as
stale. Nothing renders or rewrites the PDF. Regenerate it using your own workflow,
then review its positions and repair any changed extraction identity.

The [owned source/PDF example](../examples/static-manuscript/README.md) includes
a Quarto paper, Markdown supplement and PDF. Agreement covers only their declared
metrics, not rendering settings, all prose, figures or complete document equality.

## Compatibility

New Markdown/Quarto configurations and reports use schema 8; adding a static
companion previews that upgrade before acceptance. Existing schema 1–7 projects
keep their established identities and continue to work. Compatible 0.6–1.1
Studio drafts can be restored after validation. See the
[report contract](report-format.md), [release notes](v1.2.md) and
[agent workflow](agent-guide.md).
