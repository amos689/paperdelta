# Agent evidence review and fresh inference protocol

[简体中文](PLAN.zh-CN.md)

This is the approved 2.0 work following 1.9, under the owner's minor-version
rollover convention. The earlier mapping-v4 files and scores remain immutable.
This protocol is recorded before changing the Agent implementation.

## Product work

1. Produce one structured review representation for proposals from staged,
   direct and batch Agent interfaces and for their Studio previews. Include the
   exact source path/hash/typed identity, selectors, seed/count contract, source
   unit, reduction or derivation, original manuscript position/context, displayed
   value and expected value, source rows/cells/pointers, diagnostics and rationale.
   Evidence truncation must disclose totals and retain an inspectable path.
2. Separate verified structural facts from model assertions. Numeric agreement
   never establishes experiment identity. Show mismatches and absent identity
   evidence without treating a stale manuscript value as an invalid mapping.
   A review may explicitly abstain and explain missing evidence. Budget exhaustion
   and invalid actions must not count as abstention.
3. Give staged agents concise, current stage guidance and a review of the proposed
   source unit versus manuscript formatting before finishing. Permit bounded
   corrections while preserving the last valid draft and original input identity.
   Do not add task-specific answers, scorer feedback or unattended acceptance.
4. Keep all actual writes behind existing fresh proposal checks and explicit
   user selection/confirmation. Language switching preserves fields and selections
   while clearing confirmation. Exercise CLI, MCP and real bilingual Studio flows,
   including native original positions, stale inputs and imported proposals.

## Diagnosis and old-task regression

Machine-readable contracts and raw model actions, rather than model claims of
success, establish the diagnosis. The corrective mapping-v4 run proposed the
right original location on seven mappable tasks but retained five source-unit
errors, one display-precision error and one wrong-source/JSON-pointer contract.
Two mappable cases exhausted the error budget. Two of the three required-abstention
tasks received proposals; the third exhausted the budget. Invalid table/derived
stages will be diagnosed from their original feedback before changing the API.

The archived scorer sorts identity keys and expected seeds. The archived README's
claim that an ordered-key difference caused a complete-mapping failure is not
supported by that scorer. Keep the archive unchanged and use its actual strict
contract comparison, including original position and units. Only the previously
documented mandatory count-guard comparison is excluded; record its verification
separately. Preserve the original 0/9 and 0/3 scores and all original responses.

Run the same twelve already-observed cases again as regression, never as held-out
evidence. Record the current product and prompt changes; comparisons do not isolate
one causal improvement.

## New authored tasks

Create separate twelve-case development and twelve-case held-out suites. Both
have eight mappable tasks and four required abstentions, new experiment labels,
values and locations, and explicit English/Chinese requests. The paired families
are fixed below before implementation. They cover all five manuscript formats.

| Family | Required distinction | Development / held-out manuscript |
| --- | --- | --- |
| 01 | Same-valued runs at different checkpoints; exact seed identities | LaTeX / Markdown |
| 02 | TSV scalar loss; stale paper value; exact decimal display | Markdown / LaTeX |
| 03 | Equivalent fraction/percent fields; original table cell | Word / Word |
| 04 | Escaped JSON pointer with slash and dot in keys; decoy CSV | Markdown / Quarto |
| 05 | Percentage-point difference of two declared experiments | Quarto / LaTeX |
| 06 | Raw percentage values with exact original PDF location | PDF / PDF |
| 07 | Explicit Excel worksheet/range and string experiment identity | Word / Markdown |
| 08 | Relative percentage change with declared numerator/baseline | LaTeX / Quarto |
| 09 | Missing required seed: abstain | Quarto / Word |
| 10 | Missing checkpoint identity despite equal values: abstain | PDF / LaTeX |
| 11 | Undeclared source units: abstain, do not infer from magnitude | Markdown / PDF |
| 12 | Requested significance result without observations/test metadata | LaTeX / Quarto |

The generator, requests, original files and reference contracts must be committed
and hashed before product tuning. A held-out label means its inference results are
not opened or used for tuning until the final product/prompt freeze; the developer
authored these synthetic tasks, so this is not a blind or independent human study.
Do not replace failed cases, reduce the task or relabel failures after execution.
Gold and inference inputs are separate. Prompts may contain the request, source
documents and product discovery/inspection output, never reference answers.

## Freeze, run and score

Use actual local Qwen3-8B Q4_K_M calls through AgentSession, the previously recorded
model bytes and llama.cpp runtime. Recheck their hashes. Pin model parameters,
runtime/Python/dependency versions, prompts, action/error/token budgets and all
implementation/input hashes before each new run. Start from the existing budget
of 16 actions, three invalid actions and 2,048 completion tokens per action.
Keep old-task and development attempts distinct. Freeze the chosen implementation
and prompts before opening held-out outcomes. After that point, any repair belongs
to a separately labelled later run; first results and implementation stay intact.

Save every request, unchanged response, tool feedback, wall time and token usage.
Paid API cost is zero for local inference; unmeasured electricity/hardware cost
must remain unmeasured. Record model process startup and shutdown. A deterministic
replay and oracle controls are separate from actual inference and cannot replace it.
Score full identity contracts and original positions, required abstentions,
invalid actions, incomplete sessions and guard failures separately. Report every
outcome even if model quality remains inadequate for autonomous use.

## Delivery

Complete bilingual documentation and final-wheel tests, actual 1.9 upgrade checks,
all seventeen named CI jobs, stable GitHub/PyPI publication and downloaded-byte
verification. Preserve historical licensed/native studies. Only the owner's
noreply Git identity is used. Completing this document does not complete 2.0.
