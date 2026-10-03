# Batch binding and continuous review

[简体中文](zh-CN/workflows.md)

Word manuscripts use the same review workflow with the optional `docx` extra.
See [Word support and read-only limits](word.md); the LaTeX examples below remain valid.

These workflows are available in PaperDelta 0.3.0. Run commands in your paper
project, or put `-C /path/to/project` before the subcommand. Add `--lang zh-CN`
before the subcommand for Chinese prompts. A check never runs experiment or plot code.

## Start with a complete offline example

```sh
paperdelta demo --out paperdelta-demo --open
```

The core package contains an original LaTeX/CSV example and a pre-generated PDF
figure. No checkout, model, TeX or plotting dependency is needed. Open
`paperdelta-demo/review/report.html` if a browser was not launched. The report
switches between English and Chinese. `before/` preserves the passing baseline.

The default `changed` scenario changes only the data: 84.1% becomes 80.9%. Four
numeric occurrences, a comparison and figure dependencies need attention. Its
**check exits 1**, as intended; the **demo command exits 0** when creation succeeds.
`demo --scenario baseline` leaves the evidence unchanged. `demo --scenario
safe-update` changes the result to 84.5% and produces `changes.pdpatch.json` and
`changes.diff` for review. It does not apply them. Numeric updates do not regenerate
the figure. Every invocation requires a new `--out` directory.

## Bind a results table in batches

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta batch guide
```

Declare a CSV source with column types and record identity once. Then choose the
identity columns to group by, result fields, fixed selectors, unit, aggregation,
expected count, and any expected seeds. The guide reuses these choices across the
table. Expected counts and seeds describe the intended experiment, not whatever
rows happen to remain in a file.

Each metric shows source evidence and candidate paper locations. Suggestions use
row labels, column headers and experiment identity; matching numbers alone do
not establish a mapping. Select one or more explicit positions, review the display
format and give a reason. You can edit, skip or cancel choices. The final review
supports all or a subset; only a final `accept` writes accepted configuration.
The Chinese guide uses `确认`. The paper itself is unchanged.

For scripted use, save this request as `request.json` after declaring the
`benchmark` source (as in the bundled demo):

```json
{
  "source": "benchmark",
  "fields": ["accuracy"],
  "group_by": ["model"],
  "where": {"dataset": "Data-A", "split": "test"},
  "unit": "fraction",
  "reduce": "mean",
  "expected_count": 3,
  "expected_seeds": ["1", "2", "3"],
  "display": {"kind": "percent", "places": 1}
}
```

```sh
paperdelta batch scan --request request.json --out catalog.json
paperdelta schema batch-selection
paperdelta batch propose --catalog catalog.json --selections selections.json --out proposal.json
paperdelta bind --proposal proposal.json --interactive
```

`batch scan` returns metric `choice_id` values and ranked location `candidate_id`
values. `selections.json` is a JSON array of objects with `choice_id`,
`candidate_ids`, `rationale` and an optional `display` override. IDs must come from
that fresh catalog; no candidates are accepted automatically. A draft can be
supplied with `--draft` when its source is not yet in the configuration. Use
`schema batch-request` and `schema batch-catalog` for the exact contracts.

Batch grouping currently supports CSV. JSON sources and derived metrics continue
to use the existing [guide and staged tools](guided-bindings.md). Repeated prose
locations may need separate display choices. A missing experiment identity or an
ambiguous location remains a review decision.

Literal table cells can use a `table` anchor containing the header cells, leading
row labels and a zero-based result column. This keeps multiple numeric cells
distinct and survives numeric updates. Changed headers, repeated rows, multirow
or multicolumn constructions are not guessed. Such cases require an explicit
repair or another supported unique anchor. This is bounded static parsing, not
arbitrary TeX expansion.

## Make review coverage explicit

```sh
paperdelta scope show
paperdelta scope set --file paper/results.tex --region table --require-complete
paperdelta scope set --file paper/results.tex --region table --require-complete --accept
```

Without `--accept`, scope commands preview the change. Files and regions jointly
restrict the **unbound numeric candidates** that are required for completeness.
An empty file list means all included files; an empty region list means their
whole contents. Supported regions are `abstract` and `table`. Missing files or
empty selected regions are rejected. `--allow-incomplete` disables the completeness
gate without hiding coverage. `scope clear --accept` removes the scope restriction.

All previously accepted numeric bindings, claims and figures still run, including
ones outside the selected scope. Unsupported constructs and unregistered figures
remain visible and still block `require_complete_coverage`. Scope does not turn
unknown parsing into a certified region of a rendered paper.

For a non-result number such as a year, take its candidate ID from `scan`:

```sh
paperdelta scope exclude --candidate CANDIDATE_ID --name publication_year --reason "Year, not an experimental result"
paperdelta scope exclude --candidate CANDIDATE_ID --name publication_year --reason "Year, not an experimental result" --accept
paperdelta scope remove-exclusion --name publication_year --accept
```

An exclusion records its location, reason and nearby text identity. A changed
number, changed surrounding context or lost anchor makes it stale and requires
review. Existing accepted bindings and claims cannot be excluded. Reports list
checked, unbound, outside-scope and excluded numbers separately; exclusions never
erase failing scientific checks. Scope changes preserve the old configuration in
`.paperdelta/config-backups/` and are visible in CI configuration diffs.

## Keep a report current while editing

```sh
paperdelta snapshot create submitted-v1
paperdelta watch --baseline submitted-v1 --report build/paperdelta --open
```

The watcher polls content hashes (default one second), combines saves within a
0.5-second quiet period and runs a complete check. Paper, configured data, figures,
provenance, review records, baseline and configuration changes trigger review.
It discovers new `.tex` includes while excluding environments and generated output.
Use `--interval` and `--debounce` to adjust timing. There is no result cache.

When a change is observed, the report becomes **pending**, with exit code 2,
until the new check finishes. Previous findings can still be read but are not a
current success. Inputs changing during a check cause another pass. The HTML
refreshes every three seconds while watching and keeps language, filters, open
evidence and scroll position when browser session storage is available.

The next-action list separates evidence problems, broken locations, stale
exclusions, conclusions to review, numeric updates and figure updates. A false or
unresolved claim continues to block related numeric edits. The watcher does not
apply patches or execute scripts. `Ctrl+C` stops it and writes a final static
report; unchecked changes still return 2. A forcibly killed process cannot update
its banner, so check the report timestamp and rerun before treating it as current.

`--once` runs one check. `--max-checks N` bounds a session. `--format json` emits
one JSON event per line; the complete report remains in `report.json`.

## Upgrade existing projects

Version-1 configurations remain readable and keep their existing identities.
Using table anchors, review scopes or exclusions explicitly upgrades the accepted
configuration to schema version 2, with a backup. Old clients cannot consume these
new fields. New reports use schema version 2; the reader still accepts version 1.
Old snapshots/review records are retained, and stale or tool-version-bound patches
and proposals must be recreated. See the [report contract](report-format.md).

Agent hosts can use the same catalog through four compact session tools described
in the [Agent guide](agent-guide.md). Machine protocol tests establish tool behavior;
they do not establish a model's automatic mapping accuracy.
