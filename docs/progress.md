# Development evidence

[简体中文](zh-CN/progress.md)

Started 2026-10-02; updated 2026-10-03 Sydney time. The active scope is the
[v0.2 ledger](v0.2-plan.md). The earlier a2 alpha has a
[local acceptance decision](release-acceptance.md); new features require their own
validation. The owner accepts local machine tests and Codex developer/first-user
judgment before launch. Independent feedback follows launch. Native Apple Silicon Mac
validation is now [recorded](macos-validation-2026-10-03.md). Subsequent remote
validation is tracked by [commit in Actions](https://github.com/amos689/paperdelta/actions/workflows/ci.yml);
public artifacts and release-specific limits are listed in
[GitHub Releases](https://github.com/amos689/paperdelta/releases).

## v0.2 implementation and recorded checkpoints

| Area | Implemented behavior | Evidence / limit |
| --- | --- | --- |
| Languages | English/Chinese CLI help, errors, prompts, text/Markdown, MCP presentation; stable machine fields and original source text | [Language contract](languages.md); 190 passed, 3 POSIX skips at [foundation](evidence/v0.2-foundation.json), followed by 29 targeted checks |
| Reports | Same offline HTML switches locale, preserving filters/expanded evidence; priorities, grouped coverage, evidence navigation | [Chrome record](evidence/v0.2-report-browser.json), 32 related Python tests; actual desktop/mobile, no external requests/script errors |
| Diagnostics | Read-only doctor with environment/configuration/evidence actions; structured action outputs and transaction IDs | Included in foundation tests; language preference separate from evidence config |
| Human guide | Typed source/identity/unit/aggregation selection, multiple locations, explicit final acceptance | [Guide](guided-bindings.md); scripted ten-binding workflows in both languages |
| Location repair | Explicit old/new context and selection, fresh hashes, metric/claim definitions preserved | Cancellation, ambiguity, overlap, stale input and partial acceptance tests |
| Shared builder / MCP | Thirteen read-only tools, enum choices and available stages; no acceptance or paper writes | [Builder checkpoint](evidence/v0.2-builder.json): 226 passed, 3 POSIX skips; real stdio staged proposal test |
| Local model follow-ups | Separate v2/v3 protocols and raw failures | [Results](staged-model-evaluation.md): v2 0/12 valid actions, v3 3/15; neither produced a valid complete proposal or required abstention |
| Documentation | 28 paired maintained pages, executable bilingual tutorial, current screenshots and demo captions | [Contribution rules](../CONTRIBUTING.md), [final acceptance](v0.2-acceptance.md) |
| Privacy | Repository commit email and maintainer metadata use the verified GitHub noreply address | `101008326+amos689@users.noreply.github.com`; no global identity changes |

The [final acceptance](v0.2-acceptance.md) now adds Windows installed-wheel matrices,
Linux execution and environment correction, corpus/compatibility/browser/performance,
actual developer use and artifact identities. Earlier checkpoints retain their own
scope. The [delivery ledger](v0.2-plan.md) now includes native Apple Silicon execution.
No human observations, general model accuracy or automatic-mapper approval follow.

## Preserved a1/a2 evidence

| Area | Historical result | Record |
| --- | --- | --- |
| Windows / Linux | Four Windows Python minors; Alpine Python 3.14; glibc Python 3.11–3.14. Complete/focused runs are distinguished | [Exact versions, counts and installation scope](local-validation.md) |
| Process writes | Actual lock contention, killed writer, recovery-required journal, exact restoration | [Windows](evidence/process-writes-windows.json), [Linux](evidence/process-writes-linux/evidence.json) |
| First connection | Thirteen CLI steps, ten authored bindings, eight data-change mismatches/edits, ten passing rechecks, byte-exact recovery | [Developer record](evidence/developer-first-use/evidence.json) |
| Terminal review | Actual agent-driven ConPTY accepted one mapping without editing four TeX files; twelve workflow tests | [Interactive record](evidence/interactive-validation.json) |
| Mapping controls | Nine reference mappings/three abstentions; five wrong identities still numerically pass | [Controls](evidence/mapping-controls/evidence.json); no model or human measurement |
| Original local model | Twelve parsed answers, twelve invalid proposals; zero matched targets/required abstentions | [Baseline](local-model-evaluation.md) |
| Discovery / examples | AST abstract/table/repeat priority, ambiguous table, Unicode/literal macro and BOM/CRLF patch recovery | [Examples](evidence/owned-examples.json) |
| Data-only impact | 84.1→80.9: four stale numbers, false comparison, changed figure inputs; 84.1→84.5: four edits/three files and recovery | [Demo](evidence/workflow-demo.json) |
| CI | Target-commit snapshot despite PR replacement; declaration inventory/coverage loss; ten actual Git tests and actionlint | [CI guide](ci.md), [record](evidence/ci-adapter/evidence.json); no remote run |
| Competitors | Configured Calkit pipeline and scitexlintr numeric/text repair, with PaperDelta's comparison refusal | [CLI comparison](comparison.md); no independent setup/timing benefit proved |
| Corpus | Ten licensed papers, one bound literal each, fifteen correlated scenarios; development 75/75, first held-out 51/75; two dynamic-TeX unknown papers | [Evaluation](evaluation.md), [first held-out](evidence/corpus-held-out-first.json) |
| Corpus replay | Original and a2 implementations reproduce all original per-case outcomes, including 24 complete-expectation failures | [a2 regression](evidence/corpus-interactive-v2.json), [original replay](evidence/corpus-original-replay.json) |
| Performance | 500 bindings, 20 TeX files, 10 MB CSV; final a2 20 warm runs P95 1.866 s on the recorded laptop | [Exact source/hardware](evidence/performance-final.json); prior 1.724 s record retained |
| Reports / compilation | Actual headless Chrome, owned TeX before/after patches, 51.68 s actual-report recording | [Browser](evidence/report-browser-qa.json), [compiler](evidence/tex-smoke.json), [recording](evidence/demo-recording.json) |
| Packages | MIT wheel/source separate from paper corpus; installed core-only checks, archive byte identities and licenses | [Final a2 audit](evidence/package-audit-final.json), [replay](evidence/release-replay-final.json) |
| Mac preparation | Native validator, Apple Silicon/Intel CI recipes, filesystem/PTY cases; Windows bootstrap only | [Preparation](evidence/macos-preparation.json); no native Mac pass |

The corpus pairs original paper text with synthetic evidence, not reproduced
experiments. One annotated literal per paper cannot establish whole-paper accuracy.
The developer wrote walkthrough inputs and mappings; this is not independent first use.
During that walkthrough a recorder assumed JSON from apply after the actual write
had already succeeded; the same transaction was then checked/recovered, not reapplied.

## Design decisions and remaining work

- pylatexenc 2.11 plus explicit literal macro contracts, selected from a small probe;
  this does not prove superiority over TexSoup across papers.
- Standard argparse and escaped offline templates; JSON/UI share one checker result.
  MCP 2.x is optional and returns exact proposal text without host float conversion.
- Per-file atomic replacement plus OS lock and journal; multi-file writes are not one
  atomic operation. Power loss/network filesystems remain outside measured guarantees.
- Source identity, consistency, history, provenance and author review remain independent.
  A review cannot make a false predicate pass; a file hash is not execution proof.
- Real feedback and independent onboarding/comparison time follow the
  [post-launch protocol](first-use-trial.md). Three users/ten minutes remain targets.
- Native Apple Silicon validation passed; see the [exact scope](macos-validation-2026-10-03.md)
  and [transfer guide](../START_ON_MAC.en.md). Intel remains untested.
  Remote CI and GitHub/package publication remain separate unperformed actions.

The original PD-101–104, PD-201–205 and PD-301–304 have local functional evidence.
PD-001/003/004 have examples/parser/contracts; PD-002 has a configured comparison;
PD-401–404 have developer onboarding, agents and local CI, without independent adoption
or remote execution. PD-501–505 have scoped corpus/performance/docs/demo/artifact
evidence. Current v0.2 completion is tracked explicitly rather than inherited.
