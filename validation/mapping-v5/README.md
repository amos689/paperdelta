# New mapping task preparation

[简体中文](README.zh-CN.md)

The [protocol](PLAN.md) was committed before product changes. The 24 authored
tasks in [tasks/manifest.json](tasks/manifest.json) contain twelve development
and twelve held-out cases, each with eight mappings and four required abstentions.
English and Chinese requests each account for half the cases. All five manuscript
formats are represented. These are owned synthetic inputs under the repository's
MIT license, not independently annotated research papers or a human user study.

The generator is [create_mapping_v5.py](../../tools/create_mapping_v5.py).
Its first generation stopped at the Excel case because the optional fixture
generation dependency `openpyxl` was absent. After installing `openpyxl==3.1.5`,
a second generation completed. Before freezing, the Chinese requests were fully
translated and runtime/generator provenance was added. No model call or product
tuning occurred during these preparations. The first failure and the intermediate
outputs remain in local build directories; their receipts are in
[preparation.json](preparation.json). Excel reading in the product does not require
openpyxl.

Experiment identities, units, reduction and expected decisions come from the
authored specifications. Original Word/PDF locations were produced by the existing
1.9 parser and checked visually on the original rendered documents. They are not
independent native-parser ground truth. All eight native originals were inspected:
the values and table cells are readable, no text is clipped, and rendering did not
change source bytes. Poppler emitted missing display-font warnings for Symbol and
ArialUnicode while rendering Word exports; the actual ASCII test text rendered
correctly. See [visual evidence](visual/evidence.json).

No inference score is available at task freeze. The held-out suite is held out
from inference-driven tuning, not from its authors. Its first model outcomes must
be preserved and opened only after product and prompt freeze. Reference answers
and control outputs must never be included in model input.
