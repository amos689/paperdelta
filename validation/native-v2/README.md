# Native document study 2: original positions and explicit bindings

[简体中文](README.zh-CN.md)

PaperDelta 1.3.0 was frozen before inspecting held-out text or layout. On the
110 held-out measured values, the frozen reader supports **82**, misses **3**,
mislocates **0**, and leaves **25 unknown**. Published 1.2.1 on the identical
originals and gold supports 32, misses 5, mislocates 0 and leaves 73 unknown.
This is a small, developer-annotated, two-publisher study, not a universal accuracy
claim, independent human review, or reproduction of the papers' experiments.

## Selection and annotation

[Selection](selection.json) and the [initial protocol](protocol-initial.json)
preceded parser changes. Twelve article families provide twenty unchanged,
licensed files: twelve text PDFs and eight publisher DOCX supplements. Four PLOS
date strata (January/July 2024 and January/July 2025) use the first two
metadata-eligible articles with DOCX tables, first for development, second for
held-out. Four latest eligible eLife research versions of record alternate splits.
An article and its supplement always stay together. The split has ten files each.
[Sources, authors, licenses, URLs and hashes](sources.json) identify every byte.

Each file planned twelve measured result tokens from the first result table and
four from abstract/result prose, with the stated fallbacks. IDs, dates, reference
numbers, graph ticks and method constants are excluded. Files were not replaced
after inspection. Five supplements have no eligible results, one has only one,
and one PDF has thirteen: the planned 320 slots yield **222 actual targets**,
112 development and 110 held-out. The 98 unfilled slots remain explicit in gold;
they are neither successes nor invented unknown targets. Zero-target files stay
in the source inventory and converter comparison.

Gold uses independent PDFium glyph coordinates and original OOXML part,
paragraph and character offsets, plus visual inspection of original renders.
Microsoft Word read-only PDF export was used only for visual annotation on this
Windows host; checking does not require Word. The developer is the annotator.
[Development lock](development-gold-lock.json), [implementation lock](implementation-lock.json)
and [held-out annotation lock](held-out-gold-lock.json) retain the sequence.
The [first-run start receipt](first-run-start.json) precedes the first score.

PDFium ink bounds omit side bearings, whereas extraction spans use font advances.
During development, before held-out access, a [coordinate amendment](coordinate-amendment.json)
added independently derived font boxes at the same original glyphs. Both readers
use the same 1.2-point horizontal and vertical-midpoint comparison; original ink
gold and initial ink-mode results remain unchanged. This corrects a measurement
artifact and is not counted as a parser improvement.

## Results and remaining failures

| Inputs / reader | Supported | Missed | Mislocated | Unknown | Targets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development / published 1.2.1 | 50 | 21 | 0 | 41 | 112 |
| Development / frozen 1.3.0 | 76 | 0 | 0 | 36 | 112 |
| Held-out / published 1.2.1 | 32 | 5 | 0 | 73 | 110 |
| Held-out / first frozen 1.3.0 | 82 | 3 | 0 | 25 | 110 |

Supported requires the independently identified original position, a unique
explicit binding, a pass against controlled synthetic evidence, and a mismatch
after increasing that evidence by one. Equal values elsewhere do not qualify.
Missed means no unique original candidate and no position-specific refusal.
Mislocated means a wrong original position or changed binding identity. Unknown
means an explicit unsupported structure or unresolved identity. Unknown is never
counted as success. See [development](results/development.json),
[first held-out](results/held-out-first.json) and the matching
[development](results/development-baseline.json)/[held-out](results/held-out-baseline.json)
baselines for per-target outcomes and dependency versions.

The three first-run misses are retained:

- `held-034` and `held-040`: PDF page 6, PLOS `0312751`, the values 29 and 18
  in a dense result table are not exposed as unique original candidates.
- `held-086`: eLife `110200`, page 8, the complete scientific value `3 × 10⁴`
  is missed. Its mantissa, base and exponent are one measured value, not three
  easier targets. Raised-exponent layouts are not generally supported.

Twenty-two unknowns are blocked original locations; two have ambiguous anchors
and one a refused table identity. The historical native-v1 four PDF misses now
pass a [controlled regression](results/historical-four-misses.json), using
independent font boxes at the original glyphs. Native-v1 gold/results remain
byte-for-byte unchanged, and this is not new held-out evidence.

## Same-input Docling comparison

Docling 2.134.0 ran in a separate environment with OCR disabled and table structure
enabled. The default backend failed to open all six development PDFs on this
Windows installation; [records](docling/development-default-runs.json) retain
those failures with the private checkout path redacted. Its supported PDFium
backend converted all twenty originals. [Environment and decision](docling/comparison.json)
record dependency versions, execution scope and the decision not to add it as a
product dependency in 1.3.

| Split | Extracted in original container | Not extracted there | Original position unknown |
| --- | ---: | ---: | ---: |
| Development | 96 | 0 | 16 |
| Held-out | 91 | 2 | 17 |

These are **container extraction counts, not accepted PaperDelta bindings**.
A PDF token must occur in one container enclosing the independent original box;
matching a number elsewhere is insufficient. Containers do not supply exact
token bounds or reviewed experiment identities. DOCX output lacks the original
OOXML paragraph/offset needed here, so all 33 Word targets have unknown original
positions in this comparison. Full structured outputs, per-target scores and
per-file timings remain under [docling](docling/). A better extraction count alone
does not demonstrate a reliable binding improvement.

## Replay and license

From the matching source checkout with this evaluation bundle present:

```sh
python -m pip install '.[dev]'
python tools/replay_native_v2.py --out build/native-v2-replay
```

Use a new output directory. The replay checks the preserved implementation
hashes, runs both splits and compares each outcome against the recorded results.
It records dependency differences. Reruns are regressions on observed documents;
never overwrite first results or describe a repair as a new held-out result.
[Implementation](implementation/) and [development history](development-history/)
remain available. The initial baseline attempt that aborted at a PDF resource
limit is not a complete score; the complete baseline explicitly counts the
whole-document refusal as unknown.

Original documents retain CC BY 4.0 and their authors' copyright. Annotations and
excerpts are study derivatives. See [attribution](../../THIRD_PARTY_NOTICES.md)
before reusing them. They are distributed in the separate evaluation ZIP, excluded
from the MIT Python wheel and source distribution. No model weights or Docling
runtime are redistributed here.

After the first score, the two locale JSON source files were normalized from CRLF
to LF for Git. [The receipt](release-normalization.json) verifies identical parsed
values; frozen snapshots retain their original bytes. No parser logic changed.

The later [diagnostic text correction](diagnostic-text-correction.json) fixes the displayed PDF region command in both languages; it does not change parsing or recorded outcomes.
