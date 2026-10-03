# Quick start

[简体中文](zh-CN/quickstart.md)

Word manuscripts use the same review workflow with the optional `docx` extra.
See [Word support and read-only limits](word.md); the LaTeX examples below remain valid.

Install in a Python 3.11+ environment: `python -m pip install paperdelta`.
Run `paperdelta demo --out paperdelta-demo --open` for an included offline report.
For a results table, see [batch binding, scopes and watching](workflows.md).
A source checkout can still use `python -m pip install -e .`.
The examples below run in your paper project's root. To run elsewhere, place
`-C /path/to/project` before the subcommand.

## A complete first mapping

Suppose `paper/main.tex` contains:

```tex
Our method achieves 84.1\% accuracy on Data-A.
```

And `results/metrics.csv` contains:

```csv
dataset,model,split,seed,accuracy
Data-A,Ours,test,1,0.839
Data-A,Ours,test,2,0.841
Data-A,Ours,test,3,0.843
```

Create the discovery configuration and inspect candidates:

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta scan
```

For an interactive first mapping, run `paperdelta --lang en guide`. It asks for
source types, identity, unit, aggregation and positions, then shows a final review.
See the [guided tutorial](guided-bindings.md). The following JSON route exposes
the same proposal contract for scripts and agents.

Save the following as `mapping-input.json`. A person or an existing agent can
draft this input; the checker derives the value from the actual data.

```json
{
  "additions": {
    "sources": {
      "benchmark": {
        "path": "results/metrics.csv", "format": "csv",
        "primary_key": ["dataset", "model", "split", "seed"],
        "columns": {
          "dataset": "string", "model": "string", "split": "string",
          "seed": "integer", "accuracy": "decimal"
        }
      }
    },
    "metrics": {
      "ours": {
        "source": "benchmark", "field": "accuracy",
        "where": {"dataset": "Data-A", "model": "Ours", "split": "test"},
        "reduce": "mean", "expected_seeds": [1, 2, 3], "unit": "fraction"
      }
    },
    "occurrences": {
      "abstract_accuracy": {
        "file": "paper/main.tex",
        "anchor": {"prefix": "Our method achieves ", "suffix": " accuracy on Data-A."},
        "metric": "ours", "display": {"kind": "percent", "places": 1}
      }
    }
  },
  "rationale": {
    "occurrences:abstract_accuracy": "The author identifies mean test accuracy for Ours on Data-A, seeds 1–3."
  }
}
```

```sh
paperdelta propose --input mapping-input.json --out mapping-proposal.json
paperdelta bind --proposal mapping-proposal.json
paperdelta bind --proposal mapping-proposal.json --accept occurrences:abstract_accuracy
paperdelta check --report build/paperdelta
```

The preview includes selected records, identities and the recomputed value.
Acceptance adds only selected bindings and their required metrics/sources. It
saves the previous configuration under `.paperdelta/config-backups/` and leaves
the paper unchanged. Existing IDs cannot be overwritten by proposals.

For guided review, replace the command containing `--accept` with:

```sh
paperdelta bind --proposal mapping-proposal.json --interactive
```

Each card shows the rationale, paper context, unit, calculation, source identity
and up to five selected records. Enter `e` for all records, `y` to select,
`n` or blank to skip, or `q` to cancel the whole selection. Nothing is saved
until you type `accept` at the final prompt. The inputs are rechecked before
saving; changed data, paper or configuration requires a new proposal.
Cancelling or interrupting the input stage saves nothing. Once saving starts,
an interruption is an error, not a confirmed cancellation.

Prompts go to the terminal's error stream; standard output contains the final
JSON result. Interactive mode requires terminal input and error output. Use
explicit `--accept` IDs in scripts and do not combine the two modes.
Confirmation records a mapping, so a correctly mapped stale number can still
fail the next check. It does not attest author review or modify the paper.
Proposals from an earlier tool version must be generated again.

Commit accepted `paperdelta.yaml` if you want checks to be reviewable in Git.
Direct edits to that file are accepted project declarations. Proposal boundaries
cannot prevent an agent with separate filesystem access from editing it directly.

## Update and repair

If a paragraph was rewritten or moved, use `paperdelta repair guide` to propose
an explicit location change. It retains the metric and claim definitions and
does not declare that the scientific result is correct. See [location repair](guided-bindings.md).

Save a snapshot before changing results with `paperdelta snapshot create before-rerun`.
After the update, run:

```sh
paperdelta check --baseline before-rerun --report build/paperdelta
paperdelta fix --report build/paperdelta/report.json --out change-1.pdpatch.json
paperdelta apply change-1.pdpatch.json
paperdelta apply change-1.pdpatch.json --write
```

`apply` defaults to a unified diff. It recomputes replacements and refuses stale
inputs, changed mappings, partial numeric spans and overlap. Use repeated
`fix --only OCCURRENCE_ID` to select individual fixes. A false or unresolved
related comparison blocks its numeric fixes until the author addresses the
comparison and its configuration.

An applied or interrupted transaction prints an ID. `paperdelta recover ID`
previews reversal; add `--write` to restore original paper bytes. Recovery refuses
files edited after the transaction. Keep transaction backups until no longer needed.

## Record author review

Read a claim's `state_fingerprint` from `paperdelta check --format json`. An author
who reviewed that exact evidence and statement can run this command on one line:

```sh
paperdelta review record --claim main_comparison --state sha256:ACTUAL_HASH --reviewer "Author name" --note "Checked the selected test runs" --attest-reviewed
```

This declaration does not make a false predicate pass, change a baseline or
accept mappings. Changed evidence or statements supersede it. Returning to an
earlier state can match an earlier record; saved history remains visible. Local
records are declarations, not identity authentication or proof of execution.

## Literal macros and discovery limits

For a literal macro such as `\score{84.1}`, initialize with `--macro score=1`, or
declare `paper.macros: {score: 1}`. This describes literal arguments; it does not
execute or expand macros. Dynamic TeX and ambiguous includes return unknown.
Anchors must surround the complete number: a suffix of only `.` can stop inside
a decimal and is refused when it cuts a token.

The original multi-file fixture in `examples/research-paper` includes three seeds,
a baseline, a percentage point difference, repeated occurrences and a comparison.

For text PDFs and shared LaTeX/Word/PDF metrics, see the [PDF guide](pdf.md).
Install `paperdelta[pdf]` or `paperdelta[docx,pdf,mcp]` as needed. PDF positions
use original page boxes; source/export relationships require explicit declarations.
