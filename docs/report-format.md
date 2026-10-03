# Report interchange contract, version 2

[简体中文](zh-CN/report-format.md)

`paperdelta schema report` emits the JSON Schema for a **complete stored report**.
The checked-in [schema](schemas/report.schema.json) records the current contract (readers accept versions 1 and 2).
Configuration, proposals, snapshots, figure records, author-review records and
patches have separate schemas. A snapshot embeds this complete report.

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

`location.start/end` are zero-based Unicode character offsets; `byte_start/end`
are zero-based offsets into the original UTF-8 file. End offsets are exclusive.
Line and column are one-based. Original text and both lengths must agree.
Byte-order marks and CRLF are retained. These positions alone never authorize
a write: numeric patches are re-derived and all input hashes must still match.

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
