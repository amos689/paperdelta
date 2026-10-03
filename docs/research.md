# PaperDelta implementation research

[简体中文](zh-CN/research.md)

Research date: 2026-10-02. These are recorded observations from that date, not
current repository-status claims. The purpose was to decide how to implement
option A, what to reuse and whether a separate project has a clear purpose.

## 1. Refined positioning

Generating paper numbers from evidence and detecting numeric drift already exist.
Calkit and scitexlintr are direct comparisons; these basic capabilities should not
be advertised as PaperDelta inventions.

Proposed positioning: **An experiment-aware change reviewer for existing LaTeX
papers, helping researchers and agents inspect affected statements and edits.**

The hypothesis is that users can keep their scripts, directories, templates and
writing habits while adding a mapping file and a report spanning evidence, text,
tables and conclusions. Adoption cost and the complete workflow need measurement.
Initial research inspected official docs, READMEs, code, tests and public issues.
Later [mechanism probes](evidence/reference-probe.json) and the
[local CLI comparison](comparison.md) ran Calkit's DVC pipeline, scitexlintr's
numeric/text repairs and PaperDelta's impact report/related-patch refusal. They do
not measure independent installation, onboarding or review time. The search did
not cover all GitHub work and cannot guarantee originality or future stars.

## 2. Main references

| Project and source | Verified at the recorded revision | Inspiration and intended use |
| --- | --- | --- |
| [Calkit](https://github.com/calkit/calkit/blob/423e54f03f812a3564168fe3a487b410ceaf62be/docs/questions.md) | Structured questions, answers and evidence; conditional answers, evidence changes/staleness and LaTeX output | Main comparison baseline. Learn from evidence types and independent states. Initially read CSV/JSON; later import evidence/pipeline metadata. Conditional checks and staleness are not unique capabilities. |
| [scitexlintr](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/README.md) | Manifest and numeric/text wrapper macros for drift; figure registration, formatting, local fixes and HTML | Study diagnostic/formatting/write boundaries and manifest interoperability. Test the adoption hypothesis for ordinary handwritten papers. |
| [showyourwork](https://github.com/showyourwork/showyourwork/blob/51621e9d1ede93809a09143a9a0ca88ce1d76667/docs/latex.rst) | Figure-to-script links and external variable dependencies | Inform figure provenance/dependency display without building another full paper build system. |
| [onlycodes-paper](https://github.com/hyang0129/onlycodes-paper/blob/54fb117f83577ece62b147e5a16b6f3ff383cda1/build_numbers.py) | CSV provenance and compound keys generate LaTeX numbers and locate uses | Learn readable keys and text-to-cell tracing. No LICENSE was found in the inspected tree; do not copy its code. |
| [papercheck](https://github.com/cgarryZA/papercheck/tree/8e66cc957d829847ceea1d086a61b2fd9c403f1f) | Deterministic checks plus agents; issue/review/patch records; verifies source excerpts exist | Separate proposed/accepted issues and patches. Design our own hash preconditions/evidence states; source existence is not argument validity. |
| [reviewdog](https://github.com/reviewdog/reviewdog/blob/efaa3c82bf8cf4b21e4d0f82c511146693cc293f/proto/rdf/README.md) | Positions, rule IDs, severity and suggested edits for code review | Compatible diagnostics; retain whole impact reports because data changes affect unchanged paper lines. |
| [DVC](https://dvc.org/doc/user-guide/project-structure/dvcyaml-files) | Dependencies, outputs, parameters, pipeline state and content lock records | Learn content identities/invalidation; later read metadata without making DVC mandatory. |
| [Quarto](https://quarto.org/docs/computations/inline-code.html) | Inline computed results | An alternative that avoids manual copying at authoring time. PaperDelta serves existing-paper review rather than another renderer. |

These projects work at different layers. A configured Calkit/showyourwork pipeline
or established scitexlintr macro workflow may already suffice. Interoperability
and low-cost adoption must earn use; users should not need to rebuild their workflow.

## 3. Two design findings

[Calkit issue #1606](https://github.com/calkit/calkit/issues/1606), open when checked,
proposed recording confirmation using answer/evidence content fingerprints rather
than the last edited commit. Explicit review states already have prior work.
PaperDelta distinguishes mapping acceptance, numeric consistency and author review.
A changed low-order value can retain the same display but still affect review.
Recreating a baseline must not silently clear outstanding review.

scitexlintr documents that naked-value lookup can confuse unrelated equal numbers.
Discovery can therefore suggest candidates only; confirmed identity needs dataset,
model, split, metric and appropriate run/seed identifiers.
[LingTai issue #100](https://github.com/Lingtai-AI/lingtai/issues/100), closed when
checked, described text remaining internally consistent while being associated
with the wrong experiment after revisions. This is a qualitative signal, not a
frequency or market-size measurement. Cards should show the experiment, selected
rows and calculation alongside old/new values.

## 4. Parsing, positions and fixes

| Candidate | Inspected behavior | Decision |
| --- | --- | --- |
| [pylatexenc LatexWalker](https://pylatexenc.readthedocs.io/en/latest/latexwalker/) | Nodes, positions, contexts and macro argument definitions; explicitly not a full TeX engine | First candidate; test real files before pinning. The then-latest docs concerned 3.x, so do not mix APIs across versions. |
| [TexSoup](https://github.com/alvinwan/TexSoup) | Tolerant LaTeX tree/search operations | Comparator; exact original positions/formatting matter more than self-reported parsing rates. |
| [tree-sitter-latex](https://github.com/latex-lsp/tree-sitter-latex) | Editor-oriented best-effort grammar, not all TeX behavior | Future editor option; first test the simpler Python installation path. |

Keep original bytes and explicit position mappings. Syntax nodes limit supported
regions; patches replace only verified spans. Do not globally replace plain text
or serialize a modified tree over an entire paper.
scitexlintr's [_engine.py](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_engine.py)
and [fix tests](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/tests/test_apply_fixes.py)
inform reverse-order replacements, overlap handling, comments and escapes.
PaperDelta also rechecks file/data/mapping identities before applying a saved report.

## 5. Other directions

- [ASTRA](https://github.com/LightconeResearch/astra-spec) modeled analysis inputs,
  outputs and decisions declaratively and was early alpha when inspected. Useful
  naming/export inspiration, not a stable core dependency yet.
- [sciwrite-lint](https://github.com/authentic-research-partners/sciwrite-lint)
  covers citations, internal consistency and figure/text relationships, partly
  using local models. Checking owned experiment outputs remains separate from
  retrieving/judging external paper evidence.
- The [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) supports
  a later stdio adapter. Stabilize core functions and CLI first; share their results.

## 6. Reuse strategy

| Component | Approach | Reason |
| --- | --- | --- |
| LaTeX nodes | Tested existing parser | Avoid inventing a full parser |
| CSV/JSON, decimals, hashes | Python standard library plus strict contracts | Small installation and explicit numeric meaning |
| Selection, confirmation, impact report | Original implementation | Main workflow hypothesis |
| Paper diagnostics | Learn from scitexlintr categories/failures; prefer manifest interchange | Avoid duplicating every generic lint rule |
| Pipelines | Read existing outputs; later Calkit/DVC adapters | No scheduler, training or environment rebuild |
| Review surfaces | JSON, Markdown, offline HTML; later reviewdog | One fact model across interfaces |
| Agents | CLI guide/contracts, then small MCP adapter | No new general agent framework or model account |

The core should work independently of competitors. An unavailable adapter should
report its own failure without breaking unrelated numeric checks.

## 7. Sources and versions

These revisions came from the recorded GitHub API inspection. Recheck released
versions, directory-specific licenses and API compatibility before adopting code.

| Repository | Recorded commit | License inspection |
| --- | --- | --- |
| Calkit | `423e54f03f812a3564168fe3a487b410ceaf62be` | Root LICENSE, MIT |
| scilintr / scitexlintr | `a03cfc2d8ccf034414a058ac62949bfaf014f720` | Subdirectory LICENSE, MIT |
| showyourwork | `51621e9d1ede93809a09143a9a0ca88ce1d76667` | Root LICENSE, MIT |
| papercheck | `8e66cc957d829847ceea1d086a61b2fd9c403f1f` | Root LICENSE, MIT |
| reviewdog | `efaa3c82bf8cf4b21e4d0f82c511146693cc293f` | Root LICENSE, MIT |
| pylatexenc | `e4ddf2bad063a2bb79bd17abe2e5bce59375bf88` | LICENSE.txt, MIT |
| onlycodes-paper | `54fb117f83577ece62b147e5a16b6f3ff383cda1` | No license found; no code copied |

Further references:

- Calkit [questions.py](https://github.com/calkit/calkit/blob/423e54f03f812a3564168fe3a487b410ceaf62be/calkit/questions.py),
  [provenance](https://docs.calkit.org/provenance/),
  [writing-first tutorial](https://docs.calkit.org/tutorials/writing-first/).
- scitexlintr [snapshot_mismatch.py](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_rules/snapshot_mismatch.py)
  and [_finding.py](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_finding.py).
- papercheck [verify.py](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/src/papercheck/core/verify.py),
  [ledger.py](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/src/papercheck/core/ledger.py),
  [patch.schema.json](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/schemas/patch.schema.json).

Record source/license notices for copied snippets and redistributed fixtures.
The plan copied no code from these projects. Paper, data and code licenses are distinct.

## 8. Questions for the prototype

1. Can ten reliable key-result mappings be made in roughly ten minutes without
   rewriting an ordinary LaTeX template?
2. Can an impact report find missed abstract/table/claim updates faster than file diffs?
3. Does a separate tool reduce configuration or review work compared with suitable
   Calkit/scitexlintr configurations?
4. Can AI suggestions save work at an acceptable mismatch rate?

If the third hypothesis fails, prioritize an onboarding/report layer over existing
tools. Establish practical value before expanding independent product engineering.
