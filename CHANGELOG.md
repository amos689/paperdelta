# Changelog

[简体中文](CHANGELOG.zh-CN.md)

## 1.0.0 — 2026-10-04

- Explicit statistical bundles: complete typed seeds/observation IDs, n, ddof, analysis unit, mean/SD/SE and declared Student-t intervals. Missing observations remain unknown.
- Scalar and compound statistical displays in LaTeX/Word/PDF, including independently bound n and confidence level. Whole-expression repair preserves declarations.
- Bilingual Studio, terminal/MCP, batch templates and offline report details share the same reviewed contracts.
- Schema 6 preserves older accepted identities; exact rational moments and recorded high-precision approximations have independent numerical checks.
- Restore numeric patch compatibility for schema-5 evidence reports and extend it to schema-6 compounds; companion-manuscript changes retain the current configuration schema.

## 0.9.0 — tables and portable experiment evidence

- Read TSV and static XLSX result tables with explicit types, row identity and worksheet/range selection; retain stored decimals, missingness and original cell locations.
- Add portable `.pdevidence.json` exports with embedded source snapshots, explicit identity mappings, precision declarations and offline projection verification.
- Import complete paginated MLflow histories and unsampled W&B SDK histories, preserving run/step/checkpoint/seed/split context without automatic latest/best selection.
- Extend Studio, terminal/MCP drafts, batches and templates to new table sources; show source provenance in bilingual Studio and HTML.
- Add configuration/report schema 5 while preserving legacy CSV/JSON identities, and refuse overwriting previously imported evidence.
- Verify six new bilingual browser flows, actual local HTTP and real SDK pagination, corruption/missing-value cases, and an owned TSV/XLSX example.

See the [0.9 upgrade guide](docs/v0.9.md) and [experiment-evidence workflow](docs/experiment-evidence.md).

## 0.8.0 — batch binding and portable experiment templates

- Reuse explicit CSV identities, units, aggregations and seed contracts across Studio batch choices.
- Search and paginate metrics/positions, inspect original PDF highlights, and preserve explicit cross-page selections through language changes.
- Save, export and import typed experiment templates across compatible source declarations without reusing paper positions.
- Import existing CLI/MCP proposals, including numeric occurrences, claims and figures, into recoverable graphical subset review.
- Keep missing evidence unknown, refuse stale proposals and overlapping locations, and accept only selected bindings with their dependencies.
- Add six bilingual native-format batch browser flows and an identical-input 24-metric comparison: 270 to 103 recorded interactions versus published 0.6.0.

See the [0.8 release and upgrade guide](docs/v0.8.md).

## 0.7.0 — ongoing review in Studio

- Compare experiments with named snapshots and grouped evidence, numeric, claim and figure impacts.
- Preview edits and dependent removals of accepted declarations, with exact fields and configuration backups.
- Repair numeric and claim positions visually; record reviews without turning failed claims into passes.
- Continuously recheck stable inputs, preserve staged drafts across restarts, and explicitly rebuild selected work after input changes.
- Search every scanned candidate with pagination; keep cross-page selections and paginate large metric/impact lists.
- Add bilingual second-experiment browser flows, recovery/partial-save regressions and reproducible scale measurements.

See the [0.7 release and upgrade guide](docs/v0.7.md).

## 0.6.0 — local visual binding workbench

- Add `studio`: initialize projects, inspect CSV/JSON, declare metrics and select paper positions in a local browser.
- Reuse exact calculations, typed selectors, stable anchors, previews and explicit subset acceptance.
- Add original-PDF point selection/enlargement and native Word/multiple-manuscript positions.
- Support undo, exact draft download/restore, current report downloads and live English/Chinese switching.
- Guard input/session revisions and back up accepted configurations; preserve read-only paper/data and MCP boundaries.
- Add real HTTP, three-format session and six bilingual browser acceptance workflows.

See the [workbench guide](docs/studio.md) and [upgrade notes](docs/v0.6.md).

## 0.5.0 — PDF and multiple-manuscript review

- Add optional text-PDF parsing with original page/box positions and extraction identity.
- Embed bounded original-page previews with highlights, navigation and enlargement in offline HTML.
- Share explicit metrics across LaTeX, Word and PDF; diagnose stale exports only for declared relationships.
- Add previewed manuscript/region commands, backup/hash guards, and schema 4 with legacy readers.
- Keep unsupported/scanned content explicit and native documents read-only; reject partial numeric tokens.
- Add an installed PDF/source demo, bilingual guides and 25 PDF layouts with 125 labelled positions.

See the [PDF guide](docs/pdf.md) and [release notes](docs/v0.5.md).

## 0.4.0 — read-only Word manuscript review

- Add the optional `docx` parser and an installed `demo --document docx`.
- Read paragraphs, split runs, headings, captions and ordinary tables with native locations.
- Share binding, batch selection, repairs, claims, scopes, snapshots, watch and MCP checks.
- Report unsupported Word structures explicitly and refuse native-document writeback.
- Add schema 3 while preserving LaTeX schema 1/2 behavior and historical records.
- Ship bilingual guides/reports and 22 structural fixtures with 110 labelled positions.

See the [Word guide](docs/word.md) and [release notes](docs/v0.4.md).

## 0.3.0 — batch binding and continuous review

- Ship a complete offline `demo` in the core wheel and support PyPI installation.
- Reuse explicit CSV experiment definitions across batch metrics and paper locations;
  support bounded literal table cells and all/subset/cancel confirmation.
- Add numeric review scopes and reasoned, context-bound exclusions without hiding
  accepted failures. Preserve backups when adopting configuration schema 2.
- Watch content changes, mark pending checks, refresh reports and show a linked review queue.
- Add four in-memory batch MCP tools (seventeen overall), with pagination, correction,
  stale-input checks and explicit author acceptance through the CLI.
- Write report schema 2 while reading version 1, and maintain bilingual UI and guides.
- Publish stable versions from verified GitHub assets through PyPI Trusted Publishing.
  Remove Related work from both READMEs; retain historical evaluation records.

See [workflows](docs/workflows.md) and [release notes](docs/v0.3.md).

## 0.2.0a1 — first public alpha

- Trace changed CSV/JSON evidence to declared numeric occurrences, comparisons
  and figure inputs in existing LaTeX papers. Keep incomplete evidence explicit.
- Review findings in an offline HTML report with English/Chinese switching,
  search, filters and expandable evidence. Localize CLI, diagnostics and MCP text.
- Connect a paper with typed `guide` steps and explicit final confirmation.
  Repair moved locations with old/new context while preserving scientific meaning.
- Preview verified numeric patches, apply with stale-input checks, recheck and
  recover original bytes when later edits have not intervened.
- Expose thirteen optional read-only MCP tools and a CI adapter that compares
  target-commit snapshots and highlights mapping/rule/review changes.
- Ship original examples, bilingual documentation, feedback forms, validation
  tools and separately licensed evaluation materials.

Requires Python 3.11+. Checking needs no model key, GPU or TeX installation.
The GitHub release supplies a wheel, source distribution, evaluation bundle and
SHA256 checksums. No package-index release is available.

### Validation and limits

[Local acceptance](docs/v0.2-acceptance.md) and
[native Apple Silicon results](docs/macos-validation-2026-10-03.md) retain exact
commands, identities and failures. The [Actions matrix](https://github.com/amos689/paperdelta/actions/workflows/ci.yml)
covers Python 3.11–3.14 on Windows, Linux and both Mac architectures; inspect the
release commit's run and artifacts for its actual results.

This alpha checks an explicitly declared static LaTeX subset. Dynamic TeX,
significance inference and general scientific correctness are outside its scope.
The 150-case study uses already observed papers with synthetic evidence: 126 cases
passed complete expectations and 24 failed. It is not a fresh accuracy benchmark.
Local model experiments did not establish a reliable automatic mapper. Independent
user feedback starts after launch. See [evaluation](docs/evaluation.md) and
[rules](docs/rules.md). Earlier `0.1.0a2` records are local development history.
