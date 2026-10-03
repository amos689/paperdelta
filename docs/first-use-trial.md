# Post-launch first-use feedback

[简体中文](zh-CN/first-use-trial.md)

Under the owner's 2026-10-03 instruction, pre-launch acceptance uses local machine
tests and Codex developer assessment. No human trial is currently scheduled. This
protocol is retained for feedback after launch, not as a current release gate.
**There are no completed independent-participant observations.** Developer operation,
automated tests and AI-simulated use do not count as independent trials.

Participants should know Python, Git and LaTeX but have never used PaperDelta.
Give each a fresh directory without earlier participants' mappings. Their usual
agent is allowed; record its host/model and do not assume its proposals are correct.
Use public or owned examples; unpublished manuscripts are unnecessary.

## Tasks and timing

1. Install from the candidate source archive following README. Record installation
   duration and failures separately.
2. Connect ten numeric locations in a small personal paper or an answer-free example.
   Include the abstract, main table and repeated references; declare dataset,
   split, seeds, unit and aggregation.
3. Time from first opening the inputs until ten bindings are confirmed and checked.
   Record the ten-minute outcome, accepted/corrected suggestions and assistance.
   Record the actual entry point/version, such as `guide`, `bind --interactive`
   or explicit `--accept`.
4. Change only result data, leaving TeX unchanged. Ask the participant to explain
   affected locations, claims needing review and unchecked content.
5. Preview an independently eligible numeric patch, apply, recheck and recover;
   record obstacles.

Do not demonstrate the correct mapping of these inputs beforehand. Record all
assistance and time. Preserve failures and withdrawals instead of replacing a failed
participant with a later success. Three participants are early usability diagnosis,
not evidence for population adoption.

## Recording

Use the [JSON template](first-use-result.template.json) per participant. Codes such
as U01/U02/U03 suffice; names/contact details are unnecessary. Use seconds, and null
for unmeasured values rather than zero. Retain accepted configurations, redacted
reports and issues. Only actual observations enter the evidence ledger.

The initial target is three participants confirming ten bindings and explaining
one data change. Ten minutes is a target, not an observed result. Terminal guidance
exists but has not demonstrated reduced onboarding time. If configuration dominates
failures, improve proposals/evidence presentation; if parsing dominates, narrow the
supported template scope. Do not relax identity checks or auto-accept proposals to
meet a time target.

Competitor comparisons need separate inputs, suitable configurations and balanced
tool order. This trial alone cannot establish easier adoption than Calkit/scitexlintr.
