# Ambiguous handwritten table

[简体中文](README.zh-CN.md)

This is an intentional refusal example. The declared anchor matches two table
cells; equal values cannot identify the correct model. From the checkout root:

```sh
paperdelta -C examples/ambiguous-table check --report build/review
```

Expected: exit **2**, the occurrence is **unknown**, and an ambiguous-anchor
diagnostic identifies the problem. No patch is available. The data are readable;
the mapping lacks sufficient context.

In a copy of this example, an author can resolve the mapping by choosing the
specific prefix `Ours & `. That choice must come from the experiment identity,
not from the two currently identical values. PaperDelta never chooses the first
matching number automatically.
