# Changelog

[简体中文](CHANGELOG.zh-CN.md)

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
