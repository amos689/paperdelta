# Approved roadmap: 0.7 through 1.2

[简体中文](zh-CN/roadmap.md)

Approved on 2026-10-04. This is a delivery ledger, not a claim that planned
capabilities have shipped. The starting release is 0.6.0 at `c133956`.

| Release | Required scope | Status |
| --- | --- | --- |
| 0.7 | Ongoing Studio review: impact dashboard, snapshot creation/comparison, accepted declaration editing/deletion with dependency previews and backups, visual anchor repair, claim review, continuous checking with pending states, durable recoverable drafts, readable selectors, paginated search over all candidates, measured interaction performance, maintained bilingual instructions and demo | Released 0.7.0; see delivery record below |
| 0.8 | Batch binding in Studio, reusable experiment identity/unit templates, import existing CLI/MCP proposals into an explicit graphical subset review, preserve typed evidence and independent location identities, compare setup effort against 0.6 | Released 0.8.0; see delivery record below |
| 0.9 | TSV and Excel static result tables, normalized experiment exports, MLflow and W&B adapters; preserve source snapshots, run/step/checkpoint/seed/split identities, upstream precision and missingness; offline checking after explicit import | Released 0.9.0; see delivery record below |
| 1.0 | Explicit mean/standard-deviation/sample-count contracts, missing-seed checks, compound uncertainty displays, declared confidence interval methods/levels; verify statistical conventions and do not infer significance from larger means | Released 1.0.0; see delivery record below |
| 1.1 | Licensed real Word/PDF sample suite with development and held-out cases; common merged table headers, footnotes, rotated/cropped PDF pages and reliable layout handling; publish supported, missed, mislocated and unknown results | Released 1.1.0; see delivery record below |
| 1.2 | Static Markdown and Quarto prose/tables with original locations, shared evidence model, explicit source/export checks, clear treatment of dynamic execution and unsupported constructs | Released 1.2.1; see delivery record below |

## 0.7 delivery sequence

Released on 2026-10-04 at `1a52bcd221170256090c633b24c79a3bd7c5309c`:
[17 named CI checks](https://github.com/amos689/paperdelta/actions/runs/37183978866),
[GitHub release](https://github.com/amos689/paperdelta/releases/tag/v0.7.0),
[PyPI](https://pypi.org/project/paperdelta/0.7.0/), and the
[publication receipt](assets/v0.7/publication.json). Both public Python distributions match
the release hashes; a fresh installation ran the English and Chinese bundled examples.
The first CI attempt exceeded the old 240-second suite deadline on Intel macOS/Python 3.12.
The final commit allows 480 seconds and retains timeout diagnostics; all assertions remain.


1. Shared preview/accept configuration maintenance, dependency and coverage changes.
2. Review dashboard, snapshots, declaration editor and visual anchor repairs.
3. Continuous observation, stable checks and durable draft recovery with conflict review.
4. Complete candidate search, bounded cached state, measured interaction workloads.
5. English/Chinese guides, real browser workflows, package and platform verification.

Acceptance covers LaTeX/Word/PDF × English/Chinese, a second experiment after a
snapshot, declaration maintenance, document edits and repairs, restart/recovery,
concurrent tabs, partial saves, stale preview rejection and dependency-aware deletion.
Record a 0.6 performance baseline before evaluating the new implementation. Preserve
all existing command workflows and machine-report/accepted-configuration compatibility.

## 0.8 delivery record

Released on 2026-10-04 at `d73aaeebe457f6331694b1ae77973278c74049f8`:
[17 named CI checks](https://github.com/amos689/paperdelta/actions/runs/37187210089),
[GitHub release](https://github.com/amos689/paperdelta/releases/tag/v0.8.0),
[PyPI](https://pypi.org/project/paperdelta/0.8.0/), and the
[publication receipt](assets/v0.8/publication.json). Public artifact hashes match,
and a fresh installation ran both language demos. The local installed suite passed
506 tests with three POSIX-only skips. Six native-format/language browser flows
verified 24 metrics, templates, subset acceptance and real CLI/MCP proposal imports.
The identical-input comparison recorded 270 interactions in 0.6.0 and 103 in 0.8.0;
[scope and complete traces](v0.8.md) distinguish machine actions from human usability.

## Requirements applying to every release

- Deterministic evidence identity, exact decimal handling and explicit acceptance.
- Local operation and optional integrations; no mandatory model, cloud account or telemetry.
- Complete English/Chinese UI, CLI diagnostics and maintained documentation.
- Windows/Linux/Apple Silicon macOS/Intel macOS with Python 3.11–3.14, native package
  installation, relevant browser workflows and exact published-artifact verification.
- Stable version releases after acceptance. Human recruitment is not a release gate.
- User-owned commits with the GitHub noreply identity; no added assistant attribution.
- Frozen `docs/evidence/**`, `tests/corpus/**`, `evaluations/**` and `LICENSE` retain
  their bytes. New evaluation material is separately versioned and licensed.
- Each release must meet its whole approved scope; pending work is not silently
  dropped because a narrower implementation passes tests.

Release completion will add links to the actual commits, checks, measurements and
publication receipts. Later-version work remains required until individually verified.

## 0.9 delivery record

Released on 2026-10-04 at `b983cf442b5e1a3826055f32c0ef0122965fe682`:
[17 named CI checks](https://github.com/amos689/paperdelta/actions/runs/37191811164),
[GitHub](https://github.com/amos689/paperdelta/releases/tag/v0.9.0),
[PyPI](https://pypi.org/project/paperdelta/0.9.0/) and the
[publication receipt](assets/v0.9/publication.json). Public hashes match; a fresh
installation ran both language demos. The final Windows installed suite passed
550 tests with three POSIX-only skips. Six bilingual new-evidence browser flows
passed. Adapter verification uses a local HTTP server and controlled transport
through the real W&B SDK, not a live platform account. Frozen materials and
licenses retain their bytes.


## 1.0 delivery record

Released at `169a3bee0c152ec6a2168426793489547b2bb5b8`:
[17 CI checks](https://github.com/amos689/paperdelta/actions/runs/37195241435),
[GitHub release](https://github.com/amos689/paperdelta/releases/tag/v1.0.0),
[PyPI](https://pypi.org/project/paperdelta/1.0.0/) and
[publication receipt](assets/v1.0/publication.json). The installed Windows suite
passed 596 tests with three POSIX-only skips; eight statistical browser flows
passed. Public distributions matched release hashes and both language demos ran
in a fresh installation. Versions 1.1 and 1.2 have separate delivery records below.

## 1.1 delivery record

Released at `b82f63605f76679c2187d5c686fcbaaef391aba8`:
[17 CI checks](https://github.com/amos689/paperdelta/actions/runs/37200433223),
[GitHub release](https://github.com/amos689/paperdelta/releases/tag/v1.1.0),
[PyPI](https://pypi.org/project/paperdelta/1.1.0/) and
[publication receipt](assets/v1.1/publication.json). The installed Windows suite
passed 625 tests with three POSIX-only skips. Eight new bilingual layout browser
flows passed. The frozen native replay reproduced all 128 original outcomes;
[development and first held-out failures](v1.1.md) remain public. Public hashes
match, and both language demos ran in a fresh public-package installation.

## 1.2 delivery record

The 1.2.0 GitHub release failed the strict PyPI description rendering check before upload. Version 1.2.1 corrects that heading and checks description rendering in normal CI; the original tag and failed run are retained.

Released at `eee7d663057cda78e1f461a0f95083204eb7cfaf`:
[17 CI checks](https://github.com/amos689/paperdelta/actions/runs/37205758394),
[GitHub release](https://github.com/amos689/paperdelta/releases/tag/v1.2.1),
[PyPI](https://pypi.org/project/paperdelta/1.2.1/) and
[publication receipt](assets/v1.2/publication.json). The final Windows installed
suite passed 755 tests with three POSIX-only skips. Fourteen new bilingual browser
flows passed; the frozen native replay retained every original outcome. The tested
and published wheels have 101 identical internal files. Public distribution hashes
match; a fresh core installation ran LaTeX, Markdown and Quarto demos in both
languages. [Local evidence](assets/v1.2/local-validation.json) and
[static-source limits](v1.2.md) distinguish authored regressions from general accuracy.

All six approved releases, 0.7 through 1.2, have now been delivered.

## Approved continuation: 1.3 through 1.6

Approved on 2026-10-06, starting from published 1.2.1 and documentation commit
`a9171b7`. All four releases below are required. Completion of an earlier release
does not replace the remaining scope. The shared release requirements above apply;
`validation/native-v1/**` also remains byte-frozen.

| Release | Required scope | Acceptance evidence | Status |
| --- | --- | --- | --- |
| 1.3 | Word incomplete grids, multilevel headers and multiple values per cell; PDF numeric token boundaries and reading order; actionable extraction/identity/ambiguity diagnostics and reviewed native position selection; same-input Docling comparison; current README demonstration and links, isolated uvx startup and previewable private-by-default diagnostic bundles | Repair the four recorded PDF misses; about twenty newly sourced licensed native documents with at least 200 independently located targets, article-family development/held-out split, preserved first results and all four outcome classes; bilingual browser and installation verification; comparison records state whether an optional backend improves usable positions | Released 1.3.0; see delivery record below |
| 1.4 | Three-stage onboarding; proposed source types, keys and experiment groups with reasons/conflicts; combined evidence/location review; shared experiment definitions; reviewed aliases; complete Agent proposal workflow with explicit errors and bounded correction | Same 24-metric task at no more than 60 recorded operations while retaining explicit review; independently recorded real-model complete mapping, identity error, abstention, latency and cost results; deterministic validation remains separate from model evidence | Released 1.4.0; see delivery record below |
| 1.5 | Reusable GitHub Action; PR-oriented new/resolved/unverified findings and removed declarations; SARIF for actual text locations; selected portable review bundles with content preview; combined workflow with paper-preflight while both tools remain independent | Fresh paper repository setup; data-only changes show all affected locations; removed bindings visibly reduce coverage; SARIF and binary-document report links agree with original positions; bundle inspection and replay preserve declared scope | Released 1.5.0; see delivery record below |
| 1.6 | Notebook cell/input/output provenance; Quarto render-output freshness; generated LaTeX/Markdown result fragments from accepted metrics; experiment-change revision lists across prose/tables/figures | Real notebook/Quarto workflows distinguish new evidence, refreshed tables, stale PDF and stale figures; records distinguish declared provenance from execution proof; generated fragments are deterministic and reviewed; offline checks retain input identities | Released 1.6.0; delivery record below |

The native sample protocol and source split must precede parser work; held-out
layout and scoring remain unopened until the implementation is frozen. Existing
observed papers are regressions, not fresh held-out data. The developer may also
annotate and operate the browser; independent human testing is not a release gate
and is not claimed. Every release requires installed-package checks, all seventeen
named CI jobs, distribution audits, stable GitHub/PyPI publication and verification
of the exact public artifacts. Record failures and repairs rather than rewriting
historical evidence. Do not replace model or parser measurements with scripted
successes or a narrower, easier task.

## 1.3 delivery record

Released at `72d11bfb3aa11fa3fd094d1fbdec60f31e73b59e`:
[17 named CI jobs](https://github.com/amos689/paperdelta/actions/runs/37457832186), [GitHub](https://github.com/amos689/paperdelta/releases/tag/v1.3.0),
[PyPI](https://pypi.org/project/paperdelta/1.3.0/) and [publication receipt](assets/v1.3/publication.json).
The final installed wheel passed 772 tests with three POSIX-only Windows skips,
eight new bilingual browser flows and thirteen isolated startup checks. Downloaded
wheel, source and evaluation archive hashes match. A fresh public installation ran
LaTeX, Markdown, Quarto, Word and PDF demos in both languages. The twenty-original
study has 222 independent targets; the first frozen held-out run supports 82/110,
with three misses, zero observed mislocations and 25 unknowns. All earlier failures,
frozen outcomes and the separately scoped Docling comparison remain available in
[the study](../validation/native-v2/README.md). The stale public PDF example was
repaired through normal reviewed acceptance, and the final CI reproduces the frozen
study. Versions 1.4–1.6 remain required and are not represented as delivered.

## 1.4 delivery record

Released at `2bb274db33e411ba7d94cec3ca611b59dd1f0efc`: [17 named CI jobs](https://github.com/amos689/paperdelta/actions/runs/37475613344),
[GitHub](https://github.com/amos689/paperdelta/releases/tag/v1.4.0), [PyPI](https://pypi.org/project/paperdelta/1.4.0/) and
[public verification](assets/v1.4/publication.json). The exact final wheel passed
801 tests with three POSIX-only Windows skips. The preserved installed browser
flows cover six onboarding cases and two shared-definition cases; current-commit
CI also passed the full browser suite. Same-input LaTeX/CSV onboarding takes 54
actions versus 103 in v0.8. Both frozen real-model runs remain 0/9 complete mappings
and 0/3 required abstentions; autonomous mapping is not established. Public wheel,
source and evaluation hashes match, and fresh public installs ran all five formats
in both languages. The two earlier CI failures and corrections remain documented.
Versions 1.5 and 1.6 remain required.

## 1.5 delivery record

Released at `89ea49da2316a1348bb82f74c6adc264c9578ab2`: [17 named CI jobs](https://github.com/amos689/paperdelta/actions/runs/37479991798),
[GitHub](https://github.com/amos689/paperdelta/releases/tag/v1.5.0), [PyPI](https://pypi.org/project/paperdelta/1.5.0/) and
[public verification](assets/v1.5/publication.json). The installed suite passed
847 tests with three POSIX-only Windows skips. Ten bilingual browser flows,
thirteen isolated startup cases, a real composite Action invocation in a fresh
repository, official SARIF schema validation and real public 1.4 draft recovery passed.
The tested and final wheels contain 110 identical internal files; only archive
metadata differs. Downloaded wheel, source and evaluation hashes match, and fresh
public installs ran all five manuscript formats in both languages. These authored
checks do not establish independent usability, registry accuracy or scientific validity.
Version 1.6 remains required.


## 1.6 delivery record

Released at `57d4bec23c55191a3de4d0982b4b3f65f0eb7c78`: [17 named CI jobs](https://github.com/amos689/paperdelta/actions/runs/37493921506),
[GitHub](https://github.com/amos689/paperdelta/releases/tag/v1.6.0), [PyPI](https://pypi.org/project/paperdelta/1.6.0/) and
[public verification](assets/v1.6/publication.json). The exact release wheel passed
893 tests with three POSIX-only Windows skips. Four new bilingual workflow
browser flows and 40 existing native/evidence/statistics/layout flows passed against
that wheel. Thirteen isolated startup cases and actual public 1.5 draft recovery passed.
An installed-package workflow executed an actual Jupyter kernel and Quarto/Typst
render, then distinguished refreshed tables/fragments from old prose, false claims,
old figures/PDFs and changed code with unchanged saved outputs. Ordinary checking
did not execute project code. Embedded image content remains explicitly unverified.
All three downloaded public artifact hashes match; fresh public installs ran five
manuscript formats in both languages. Earlier failures and superseded runs remain
recorded. These authored checks do not establish independent usability, complete
causal provenance or scientific validity.

All four approved versions from 1.3 through 1.6 have now been delivered. Further
feature directions require a separately approved scope.
