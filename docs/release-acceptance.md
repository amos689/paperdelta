# PaperDelta 0.1.0a2 pre-launch acceptance

[简体中文](zh-CN/release-acceptance.md)

Historical decision dated 2026-10-03, by Codex as AI developer and first local user.
For subsequent v0.2 work, see the [current delivery ledger](v0.2-plan.md).

**Decision: accept the local alpha candidate's scoped functionality.** The owner
authorized local machine tests and developer judgment instead of waiting for
independent user trials. This covers explicit mappings for existing papers,
deterministic checks, impact reports, guarded edits and agent interfaces. GitHub/PyPI
publication had not occurred. Distribution requires its passing `package-audit.json`.

## Evidence

| Area | Actual evidence and assessment |
| --- | --- |
| Correctness | Windows Python 3.11/3.12 each passed 162 tests; glibc Linux Python 3.11–3.14 each passed 162 with no failures, errors or skips. [Environments](local-validation.md) |
| First connection | Actual `init → scan → propose → preview → accept → check`, ten bindings with the paper unchanged; data changes found eight mismatches, all ten passed after patching, original bytes recovered. [Thirteen steps](evidence/developer-first-use/evidence.json) |
| Impact review | Four numeric sites, false comparison and figure dependency changes; related numeric fixes blocked when the comparison was false. [Demo](evidence/developer-first-use/change-demo.json) |
| Write protection | Stale inputs, overlaps and partial numeric ranges rejected; partial writes, competing processes and killed-process recovery tested on Windows/Linux. [Process record](evidence/process-writes-windows.json) |
| Agent interface | Actual CLI/schema/five read-only MCP tool tests. Binding acceptance, paper changes and author review remain separate explicit actions. [Guide](agent-guide.md) |
| Local model | All twelve proposals rejected, raw failures retained. This model fails automatic-mapping quality acceptance and is not a built-in automatic capability. [Experiment](local-model-evaluation.md) |
| Performance | Twenty then-current core files; 500 bindings, 20 TeX files, 10 MB CSV; 20 warm runs P95 1.866 s, below the 3 s target. [Record](evidence/performance-final.json) |
| Reports/distribution | Licensed real text, Unicode/BOM/CRLF, offline HTML, compilation, docs, video and package content have scoped records. [Ledger](progress.md) |

Codex authored the ten-binding inputs and mappings before executing real commands.
This is developer workflow acceptance, not novice use, independent accuracy or human
timing. The recording helper wrongly expected `apply` to return JSON; the CLI had
already succeeded and printed its transaction ID. That same transaction was checked
and recovered without repeating the write or changing product code.

## Developer judgment

The tool performs the promised workflow: it detects result-driven impact before
paper changes, shows sources/unknowns, and locally edits/restores confirmed numbers.
This supports an alpha for public trials within the tested scope.

Onboarding still requires correct source IDs, experiment identity, units, seeds and
anchors. The complete [quick start](quickstart.md) is executable and proposal errors
are diagnosed, but complex schemas burden this small model. Release messaging should
describe agent proposals plus explicit confirmation and subsequent deterministic
checks, without promising reliable automatic mapping from a raw paper.

The first held-out real-text group matched 51/75 complete expectations; two dynamic
TeX manuscripts remain unsupported/unknown and refuse unsafe edits. This small
controlled study cannot establish whole-paper accuracy. Native macOS, remote CI,
power loss and network filesystems were not verified.

## Candidate and follow-up

Historical directory: `build/release-candidate-final`, containing wheel, source
archive, separately licensed corpus bundle and exact-artifact audit. Model weights,
native runtimes and temporary environments are excluded. Candidate core files match
tested bytes; later changes need relevant revalidation.

Independent users, three first-use observations, onboarding/comparison timings,
macOS and remote CI are follow-up work, not incomplete gates for this historical
acceptance. Use the [post-launch protocol](first-use-trial.md) for actual feedback;
do not count machine records as human data.
