# Static source and exported PDF example

[简体中文](README.zh-CN.md)

This original MIT-licensed example declares one Quarto paper, one Markdown
supplement and one PDF export. They share explicitly bound accuracy metrics.
It does not run Quarto or claim a renderer produced the illustrative PDF.

From a source checkout with `paperdelta[pdf]` installed:

```sh
paperdelta -C examples/static-manuscript check --report build/review
paperdelta -C examples/static-manuscript studio
```

Initially seven numeric occurrences and one comparison pass; both compared
metrics are aligned. To demonstrate a stale export in a disposable copy, change
Ours' three CSV values to `0.807`, `0.809`, `0.811`, then replace `84.1` with `80.9`
in the `.qmd` and `.md` sources. Recheck: the corrected source numbers pass,
the comparison against 81.0% fails, and the unchanged PDF is stale for accuracy.
All manuscript formats in this example are read-only to PaperDelta.

The PDF's extraction identity is deliberately explicit. If dependencies change
that identity, review and repair its bindings instead of treating old coordinates
as current. The current source generator is [build_markdown_demo.py](../../tools/build_markdown_demo.py).
See [supported syntax and limits](../../docs/markdown-quarto.md).
