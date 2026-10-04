# Review a Word manuscript

[简体中文](zh-CN/word.md)

PaperDelta 1.1 reads `.docx` manuscripts and checks explicitly bound numbers and
comparisons against declared experiment evidence. It does not require Microsoft Word, a TeX
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
- **Table, row, cell:** one-based logical grid positions in a supported table. Merged
  continuations refer to their original owner, not duplicate result cells. The
  paragraph ordinal identifies the paragraph within the same traversal. These are
  navigation aids; bindings use unchanged headers and explicit row labels.
- **Footnote/endnote:** the original OOXML part, `note_id` and paragraph ordinal
  within that note. An ID is not the displayed Word footnote number. Only a visible
  body reference through a valid internal relationship enables a note.
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

Supported: body paragraphs, numeric values split across runs, decimal/scientific/
percent displays, headings, ordinary captions and tables with unique literal
headers and row labels. Common horizontal header merges and regular vertical
merges retain logical cell owners. Explicit `header_rows` and optional literal
`caption` disambiguate numeric headers and repeated tables. A horizontally merged
numeric value is not treated as a uniquely identified ordinary cell.

Footnotes and endnotes use linked original parts and visible body references.
Unreferenced notes and invalid, duplicate or external relationships are not inferred
from number matches. Note markers are shown as `[note]`; they cannot join adjacent
digits into a new number. A note can be selected, bound, checked and repaired using
the same explicit workflow as body prose.

Tracked revisions, fields/generated results, equations, drawings, text boxes,
hidden formatting, automatic list numbering, superscript/subscript numeric runs,
nested/revised/irregular tables and unresolvable merges remain unverified. Headers,
footers and comments are outside the supported read model. Unsupported structures
stay visible in diagnostics and coverage. Legacy `.doc`, `.docm`, encrypted or
damaged packages are unsupported. Resource guards: 32 MiB compressed, 64 MiB expanded,
2,000 members, 16 MiB/member, 10,000 blocks and 4 MiB extracted text. No external
relationships are fetched or archive members extracted to disk.

**Word review is read-only.** Correct numbers in your document editor and recheck.
`fix` returns an explicit read-only diagnostic for Word; accepting a mapping only
changes the reviewed configuration. Guarded LaTeX patches remain available.

## Compatibility and verification

Ordinary Word projects retain configuration/report schema 3. New table-header or
caption anchors and note/merged-cell positions require schema 7. Older accepted
identities remain readable; new features upgrade only through preview, explicit
acceptance and backup. The core remains sufficient for LaTeX. Install
`paperdelta[docx,mcp]` for Word plus MCP.

Owned tests cover structural positions, unchanged-byte checks, changed evidence,
table reordering, notes, hidden references, malformed merges, repair, claims,
scope, snapshots, watch, bilingual reports and read-only MCP behavior. They do not
establish support for every Word layout. The separately licensed native study
found **0/32 supported held-out Word scalar targets**, chiefly multi-number cells
and uncertain table identities. See the [full four-outcome results](v1.1.md).
