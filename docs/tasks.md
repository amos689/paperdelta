# Choose your next task

[简体中文](zh-CN/tasks.md)

PaperDelta connects explicitly declared experiment evidence to manuscript
positions. Start with the task you need, then open the detailed guide as needed.
Studio, reports and CLI diagnostics support English and Simplified Chinese.

## Try a complete revision without configuring your own paper

```sh
python -m pip install --upgrade paperdelta
paperdelta demo --document markdown --scenario safe-update --out revision-demo
paperdelta -C revision-demo studio
```

Use a new directory. Open `table_accuracy` in **Review and revise**, inspect its
evidence, select the numeric edit and preview it. Confirm only after reading the
diff. Then use **Change history and recovery** to restore the original bytes.
Nothing changes in your existing paper. [Step-by-step revision guide](v1.7.md).

## Connect an existing paper for the first time

1. In your paper directory run `paperdelta studio`. Select the entry file and
   evidence files. Word/PDF need the optional `paperdelta[docx,pdf]` installation.
2. Inspect evidence rows and declare their types and unique record identity.
   Keep model IDs such as `001` as text. Select the actual model, dataset,
   split, seeds, units and aggregation; suggestions still require review.
3. Define the experiment and inspect candidate locations beside their evidence.
   Select the intended occurrences and explicitly save the reviewed bindings.
4. Save a reviewed experiment definition if you will reuse the same contract.
   Next time, **Review candidates using this definition** skips repeated form
   input while keeping position review and acceptance explicit.

Binding a number declares what it means. It can correctly reveal that the
manuscript is outdated. [Studio](studio.md) · [Evidence formats](experiment-evidence.md)
· [JSON example](quickstart.md) · [Statistics](statistics.md).

## Review the next experiment

Before changing your experiment, save a snapshot in Studio or run:

```sh
paperdelta snapshot create submitted-v1
```

Run experiments through your normal process. Studio observes saves and shows
pending changes until the new check is ready. Choose the snapshot, then inspect
the affected task's original context, old/current result and evidence.

For supported LaTeX/Markdown/Quarto numbers, select edits and review the diff.
For false/unknown comparisons, correct and review the claim instead of merely
replacing numbers. Regenerate stale figures or exports using your own tools,
then check and review the declared dependencies again. A review note alone does
not make a false claim pass. [Revision and recovery](v1.7.md) ·
[Notebook/Quarto generation records](v1.6.md).

## Send a review to a collaborator

Use **Share selected review files** in Studio. Choose the reports and exact
inputs you intend to share, preview the archive and explicitly export it.
The HTML opens offline; including the required inputs allows the documented
replay workflow. The preview explains missing inputs and the resulting scope.
Recipients can switch report language. [Portable review bundles](review-bundle.md).

The current release does not export Word comment copies or PDF annotation copies.
Those are subsequent work; original Word/PDF manuscripts stay read-only.

## Check before submission

Run a fresh check, optionally against your submitted snapshot:

```sh
paperdelta check --baseline submitted-v1 --report build/submission-review
```

Review remaining mismatches, unknowns, unbound/excluded content, stale figures
and source/export differences. Recheck after corrections. Keep the final report
and selected evidence with your project. Exit 0 describes accepted required
checks within the declared scope, not a certification of the whole paper or its
science. [Checking scope](rules.md) · [CI and PR review](ci.md).

Use `paperdelta --lang zh-CN ...` for Chinese CLI output. In Studio/report pages,
use the language selector; switching clears write confirmations while preserving
working selections. [Language settings](languages.md).
