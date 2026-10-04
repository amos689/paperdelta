# Report interchange contract, version 5

[简体中文](zh-CN/report-format.md)

`paperdelta schema report` emits the JSON Schema for a **complete stored report**.
The checked-in [schema](schemas/report.schema.json) records the current contract (readers accept versions 1–5).
Configuration, proposals, snapshots, figure records, author-review records and
patches have separate schemas. A snapshot embeds this complete report.

## Experiment evidence in schema 5

TSV and XLSX evidence add an explicit `format`. TSV retains line locations; XLSX
uses `key`, `sheet`, one-based `row` and `cell`. Normalized exports use
`format: records`, a strict import selection and `provenance` with export/tool
identity, provider, origin, creation time, precision and snapshot hashes. Each
selected row locates its original snapshot and native pointer. Provider, selection,
precision and location hashes must agree. This is separate from schema-4 manuscript
`exports`, which compare paper source/PDF output.

New fields are omitted for legacy CSV/JSON evidence, preserving existing serialized
identities. Schema 1–4 reports cannot contain new-format evidence. The
[import](schemas/evidence-import.schema.json) and
[portable export](schemas/evidence-export.schema.json) schemas describe the
explicit import contract; [experiment evidence](experiment-evidence.md) explains
precision, snapshots and missing values.

Reports include `report_schema_version`, `tool_version` and `ruleset_version`.
Unknown fields and unsupported major schema versions are rejected. Every core
check validates its output against the report model, including error reports.
The validator covers numeric states, evidence records, locations, claims, figures,
diagnostics, changes, impact groups and coverage, rather than accepting arbitrary
nested objects.

## Numbers and positions

Metric `value` is finite decimal **text**, never a floating-point approximation.
Source record values and typed selector values retain their JSON types. Use a
decimal-capable JSON parser if consuming them outside PaperDelta; converting
them to binary floats can lose identity or precision. A `count` reduction may
select arbitrary JSON payloads; the record container is strict, while its `value`
is intentionally the source's JSON data.

For LaTeX, `location.start/end` are zero-based Unicode character offsets; `byte_start/end`
are zero-based offsets into the original UTF-8 file. End offsets are exclusive.
Line and column are one-based. Original text and both lengths must agree.
Byte-order marks and CRLF are retained. These positions alone never authorize
a write: numeric patches are re-derived and all input hashes must still match.

Word locations use `format: docx`, `parser`, `context` and a `locator` with the
OOXML part, paragraph ordinal, style, section and optional table/row/cell. Their
`start/end` offsets refer to extracted text, never package bytes. Native positions
have no source line or byte address and require report schema 3.
See [Word location semantics](word.md).

## Separate state dimensions

- Metrics resolve to `ok` or `unknown`. Occurrences, claims and figures are
  `pass`, `mismatch` or `unknown`.
- Changes describe evidence or definition identity relative to an explicit
  baseline. A rounded value can pass while its underlying evidence has changed.
- Claim review is `unreviewed`, `reviewed` or `superseded`. An author's review
  does not alter the consistency verdict.
- Figure provenance compares declared byte identities. It does not prove an
  execution occurred or that the visible graphic represents correct science.

Coverage counts must equal the actual stored verdicts. Candidate numbers,
unbound candidates, unsupported regions and unregistered figures are separate.
Unsupported regions are currently reported as constructs/files, not a percentage
of rendered paper area. Unbound candidates include non-results; do not interpret
their ratio as result recall.

## Agent views are intentionally different

The MCP/agent response adds `agent_view`, truncates evidence rows to ten, records
their original totals, and encodes Decimals as strings for host compatibility.
It is a **presentation view**, not a complete stored report. Do not
save it as a baseline or feed it to the stored-report validator. Obtain full JSON
with the CLI/API for archival or independent verification.

Python consumers validating with `StoredReport` should call
`model_dump(by_alias=True)` to preserve the wire field `coverage.pass`. Raw checker
results already use wire names. Hashes identify content; they are not signatures.

Stored JSON retains canonical English messages and stable machine codes.
CLI text, Markdown, HTML and MCP explanations are localized presentation surfaces;
original manuscript/data text is never translated. The same offline HTML switches
languages while retaining its filter and disclosure state. See [language compatibility](languages.md).

Breaking changes require a new schema version and migration documentation.
New reports from 0.3.0 use version 2, adding `actions`, optional `watch` state, and
`coverage.review_scope`, `outside_scope_numbers` and `exclusions`. Version 1 remains
readable with those fields defaulted. Pending watch results have exit code 2 even
when their retained earlier findings passed. Consumers must check the top-level
exit code and watch state, not infer freshness from verdict counts.

Configuration schema 2 adds scope/exclusions and table-cell anchors. Existing
version-1 configurations keep their semantics and baseline identity; explicit
acceptance of a new feature upgrades the configuration with a backup. See
[workflow migration](workflows.md).

## PDF and exports in schema 4

PDF locations have `format: pdf`, `parser`, literal `context`, and a `locator`
with one-based `page`, decimal `bbox`/`page_box`, block identity and text offset,
plus optional region/table/row/cell. Boxes use PDF points from the top-left:
`[x0, top, x1, bottom]`. Start/end refer to the extracted model, never PDF bytes.

Optional `exports` entries carry source/PDF paths, a metric, both binding lists
and `aligned`, `stale`, `source_outdated` or `unknown` status. These compare
explicitly bound metrics, not whole-document equivalence. Review actions add
`reexport_pdf`. Original-page PNGs are bounded presentation assets in HTML only;
they are not embedded into stored reports or snapshots. See [PDF semantics](pdf.md).

Configuration schema 3 introduced native Word positions. Schema 4 adds PDF
regions, extraction identities and `paper.companions` with optional `export_of`.
With legacy CSV/JSON evidence, LaTeX reports use schema 2, Word reports use 3, and
PDF reports use 4. Any new evidence format requires schema 5.
