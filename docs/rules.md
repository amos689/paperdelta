# Rules, file contracts and limitations

[简体中文](zh-CN/rules.md)

Static `.md` and `.qmd` manuscripts use the same evidence and review workflows.
See [Markdown/Quarto source support](markdown-quarto.md) for core demos, original
positions, reviewed-write boundaries and explicit source/PDF comparisons.

Version 1.0 statistical bindings declare seeds, n, SD convention and interval
method explicitly. Compound displays, batch templates and read-only agents share
the [statistical contract](statistics.md).

Word manuscripts use the same review workflow with the optional `docx` extra.
See [Word support and read-only limits](word.md); the LaTeX examples below remain valid.

Use `paperdelta schema KIND` for configuration, proposal-input, proposal, patch,
binding-draft, repair-proposal, figure-record, review-record, snapshot and stored-report JSON schemas. Unknown
fields and unsupported versions are rejected. JSON/YAML duplicate keys and
executable YAML tags are rejected. Nested evidence, diagnostics, positions and
coverage now use the strict [versioned report contract](report-format.md).

## Evidence

CSV sources declare key columns and their string/integer/decimal types. Duplicate
keys, absent columns and malformed rows are errors. Numeric metrics require a
numeric column. `where` types must match the declarations; a model named `001`
must not silently become integer `1`. JSON uses JSON Pointer, including `~0` and
`~1` escapes. JSON evidence must currently declare experiment identity through
its chosen structure; the checker cannot establish a nonempty claim scope from
that structure automatically.

`unique` requires one result. `mean`, `sum` and `count` require explicit selection;
`expected_count` and `expected_seeds` can make missing or duplicate runs unknown.
A mean over available runs is not a substitute for an expected seed-set contract.
The guided/staged builder requires an explicit `expected_count` for aggregations;
older hand-written configurations retain the version-1 optional-count contract.
Nonfinite numbers, unsupported magnitudes and division by zero are errors.

Metrics use Decimal arithmetic. Fraction, percent, percentage point, scalar, count
and ratio are distinct units. Display has explicit precision, half-up/half-even
rounding and optional percent symbols. Percentage point difference and relative
percentage change are different operators. Derived operators are a restricted
contract; configuration never executes Python expressions.

## Source locations

The parser indexes supported LaTeX, including project-local literal `input/include`.
It excludes comments, code environments, references and layout parameters. Unknown
macros can hide unsupported regions; literal argument counts may be declared.
Conditionals and dynamic structural commands require conservative unknown results.
The checker is not a TeX interpreter. It never compiles the paper or runs scripts.

Anchors must be unique and checkable. Numeric bindings must select one complete
numeric token and a supported numeric display. Exact anchors need rebinding when
their text changes; surrounding prefix/suffix anchors usually survive a numeric
update. UTF-8 byte spans preserve BOM, Chinese characters and original line endings.
Paths must resolve inside the chosen root, including symlink targets.
Location repair proposals require an explicit target and fresh input hashes.
They preserve metric definitions, units, sources, predicates and comparison scope.

Current limits include 200 included files, 40 levels of inclusion, 4 MiB per LaTeX
file, 1 MiB configuration, 32 MiB ordinary inputs, 10,000 selected records per
metric and 1,000 review records. These are resource limits, not tested performance
promises at each maximum.

## Comparison and review

Comparisons are declared binary predicates or a ranking within a named candidate
set and direction. Ties are explicit. They cannot establish statistical significance
or global SOTA. A claim's scope must be established by its metric selectors.

Current consistency, historical change, provenance and author review are separate.
Selected evidence changes can supersede review while the displayed number still
rounds to the same value. Unrelated CSV rows or row ordering do not change a
metric's semantic identity. Raw file hashes still invalidate an old numeric patch.

## Figures

A declared figure can have a sidecar from `schema figure-record`. It records output
hash, input hashes, script path/hash, timestamp and method (`manual` or `imported`).
Matching identities mean unchanged since that record. They do not prove script
execution or validate visual contents. Missing records are unknown. Unregistered,
missing or ambiguous literal figure references appear in coverage.

The inspector uses entry-file and including-file directories with common image
extensions. Complex `graphicspath`, generated filenames and graphics macro
expansion need explicit future adapters.

## Writes and recovery

Patches are re-derived from the current checker before use. Changed inputs,
overlaps and incorrect original bytes are refused. Related false/unresolved claims
block numeric fixes so a batch cannot leave their wording unaddressed. Applying a
patch does not change mappings, snapshots or review records.

Each file is atomically replaced, with original bytes stored in a transaction
journal. Multi-file writes are not one atomic filesystem operation. Interrupted
transactions block later PaperDelta patch writes until recovered. Recovery verifies
every backup and target first; later author edits cause a refusal. Writes use an
OS-level PaperDelta lock and repeated identity checks, but cannot make arbitrary
third-party editor activity part of the same lock protocol.

## What a successful exit means

Exit 0 means required confirmed checks pass against supplied evidence. It does not
cover unbound candidates or unsupported content unless `require_complete_coverage`
is enabled. Exit 1 denotes mismatch; exit 2 denotes incomplete required checks or
no bindings. Coverage is always included. No workflow authenticates evidence or
certifies scientific truth.

For text PDFs and shared LaTeX/Word/PDF metrics, see the [PDF guide](pdf.md).
Install `paperdelta[pdf]` or `paperdelta[docx,pdf,mcp]` as needed. PDF positions
use original page boxes; source/export relationships require explicit declarations.
