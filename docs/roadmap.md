# Approved roadmap: 0.7 through 1.2

[简体中文](zh-CN/roadmap.md)

Approved on 2026-10-04. This is a delivery ledger, not a claim that planned
capabilities have shipped. The starting release is 0.6.0 at `c133956`.

| Release | Required scope | Status |
| --- | --- | --- |
| 0.7 | Ongoing Studio review: impact dashboard, snapshot creation/comparison, accepted declaration editing/deletion with dependency previews and backups, visual anchor repair, claim review, continuous checking with pending states, durable recoverable drafts, readable selectors, paginated search over all candidates, measured interaction performance, maintained bilingual instructions and demo | Released 0.7.0; see delivery record below |
| 0.8 | Batch binding in Studio, reusable experiment identity/unit templates, import existing CLI/MCP proposals into an explicit graphical subset review, preserve typed evidence and independent location identities, compare setup effort against 0.6 | In development |
| 0.9 | TSV and Excel static result tables, normalized experiment exports, MLflow and W&B adapters; preserve source snapshots, run/step/checkpoint/seed/split identities, upstream precision and missingness; offline checking after explicit import | Pending |
| 1.0 | Explicit mean/standard-deviation/sample-count contracts, missing-seed checks, compound uncertainty displays, declared confidence interval methods/levels; verify statistical conventions and do not infer significance from larger means | Pending |
| 1.1 | Licensed real Word/PDF sample suite with development and held-out cases; common merged table headers, footnotes, rotated/cropped PDF pages and reliable layout handling; publish supported, missed, mislocated and unknown results | Pending |
| 1.2 | Static Markdown and Quarto prose/tables with original locations, shared evidence model, explicit source/export checks, clear treatment of dynamic execution and unsupported constructs | Pending |

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
