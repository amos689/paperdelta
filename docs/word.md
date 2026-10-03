# Review a Word manuscript

[简体中文](zh-CN/word.md)

PaperDelta 0.4 reads `.docx` manuscripts and checks explicitly bound numbers and
comparisons against CSV/JSON evidence. It does not require Microsoft Word, a TeX
installation, a model key or network access during checking.

## Try an original example

```sh
python -m pip install 'paperdelta[docx]'
paperdelta demo --document docx --out word-demo --open
```

The example starts with 84.1% accuracy, then changes the three source runs to a
mean of 80.9%. The same manuscript now has two stale accuracy values and a false
comparison against the 81.0% baseline. `word-demo/before/` contains the original
report; `word-demo/review/` contains the changed report. Both refer to the same
unchanged Word file. The demo command exits 0 when creation succeeds; the expected
changed check exits 1. Use a new output directory for each demo.

For Chinese UI, add `--lang zh-CN` before `demo`. The offline report also has a
language selector. Manuscript text is shown in its original language.

![Word report with paragraph and cell positions](assets/v0.4/word-en.png)

## Connect your manuscript

```sh
paperdelta init --paper manuscript.docx --data results.csv
paperdelta scan
paperdelta guide
paperdelta check --report build/review
paperdelta watch --report build/review --open
```

The guide asks you to identify evidence rows, a metric, its unit and the exact
manuscript uses. Matching numbers alone never confirm a mapping. Ordinary result
tables also work with `paperdelta batch`; see the [workflow guide](workflows.md).
Use `paperdelta repair scan` and `paperdelta repair guide` after rewording a bound
paragraph or changing a table label. Repair proposals require explicit acceptance.

## What the locations mean

- **Paragraph:** the one-based ordinal in the main document body traversal,
  including paragraphs inside tables. Split formatting runs, hyperlinks, tabs
  and line breaks retain their visible text.
- **Table, row, cell:** one-based positions in a supported ordinary table. The
  paragraph ordinal identifies the paragraph within the same traversal. These are
  navigation aids; bindings use unchanged headers and explicit row labels.
- **Section and style:** source heading text and style metadata accompany native
  positions in JSON. Recognized abstract headings and styles support abstract scope.
- **Parser and input hash:** JSON records the extraction implementation and parser
  versions; the report hashes the original `.docx` package.

Word page numbers depend on layout and are not inferred. Native `start`/`end`
values index the extracted read model; they are **not DOCX byte addresses**. A
Word location has no `byte_start`, `byte_end` or invented source line number.

Numeric corrections can retain a paragraph binding when its nonnumeric context
is unchanged. Duplicate indistinguishable paragraphs are ambiguous. Table row
reordering retains a binding when the header and row identity remain unique;
changed headers or row labels require repair. Do not use result values as row identity.

## Supported boundary

Supported: main-body paragraphs, numeric values split across runs, decimal,
scientific and percent displays, headings, plain captions, and ordinary tables
with unique headers and row labels. Existing claims, snapshots, review scopes,
exclusions, watch and the read-only MCP tools use the same evidence rules.

Tracked revisions, fields and generated field results, equations, drawings,
text boxes, inherited hidden formatting, automatic list numbering, superscript/subscript
numeric runs and other special content, nested/merged/irregular/revised tables,
and footnote/endnote references are reported as unverified. Text in headers,
footers, notes and comments is outside the main-body adapter and is reported.
These issues prevent a complete verified verdict; content is never silently
counted as supported. Legacy `.doc`, `.docm`, encrypted or damaged packages are
not supported. Packages are bounded to 32 MiB compressed, 64 MiB expanded,
2,000 members, 16 MiB per member, 10,000 text blocks and 4 MiB extracted text.
No external relationships are fetched, and no archive files are extracted to disk.

**Word review is read-only.** Correct numbers in Word or another DOCX editor,
then recheck. `fix` does not generate Word patches; it returns an explicit
read-only diagnostic. Editing the configuration to accept a mapping does not
edit the manuscript. Guarded LaTeX patches continue to work as before.

## Compatibility and verification

Word projects use configuration schema 3 and native locations use report schema 3.
Existing schema 1/2 LaTeX projects, reports and snapshots remain readable. The core
install remains sufficient for LaTeX; use `paperdelta[docx,mcp]` for Word plus MCP.

The native tests generate 22 supported structural fixtures with 110 labelled
numeric positions, plus unsupported-content cases. They exercise binding,
row reordering, stale evidence, repair, claims, scope, snapshots, partial saves,
watch, bilingual reports and MCP read-only behavior. These are synthetic
regression fixtures, not a claim that every Word layout is supported.

See [0.4 release notes](v0.4.md) for the release checks and upgrade boundary.
