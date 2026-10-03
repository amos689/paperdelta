"""Terminal review of binding proposals, using the same guarded acceptance API."""

from __future__ import annotations

import unicodedata
from typing import TextIO

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.onboarding import accept_bindings, inspect_proposal
from paperdelta.storage import Project, json_text


def _safe(value: str, *, formatting_newlines=False) -> str:
    """Do not allow manuscript/proposal text to act as terminal controls."""
    return "".join(
        f"\\u{ord(char):04x}"
        if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"}
        and not (formatting_newlines and char == "\n")
        else char
        for char in value
    )


def _show(output: TextIO, label: str, value) -> None:
    # JSON keeps whitespace/control characters visible and preserves Decimal data.
    rendered = _safe(json_text(value).strip(), formatting_newlines=True)
    rendered = " ".join(line.strip() for line in rendered.split("\n"))
    output.write(f"  {label}: {rendered}\n")


def _answer(input_stream: TextIO, output: TextIO, prompt: str) -> str:
    output.write(prompt)
    output.flush()
    value = input_stream.readline()
    if not value:
        raise EOFError
    return value.strip().lower()


def _metric_names(group, definition):
    if group == "occurrences":
        return [definition.metric]
    if group == "claims":
        predicate = definition.predicate
        names = [predicate.left, *predicate.candidates]
        if isinstance(predicate.right, str):
            names.append(predicate.right)
        return names
    return []


def _show_metric(output, name, config, report, full=False):
    state = report["metrics"][name]
    _show(
        output,
        tr("interactive.label.1", name=name),
        {"value": state["value"], "unit": state["unit"]},
    )
    _show(output, tr("interactive.label.2"), state["definition"])
    dependencies = set(state.get("dependencies", []))
    definitions = {}
    while dependencies:
        child = dependencies.pop()
        if child not in definitions:
            definitions[child] = report["metrics"][child]["definition"]
            dependencies.update(report["metrics"][child].get("dependencies", []))
    if definitions:
        _show(output, tr("interactive.label.7"), definitions)
    for evidence in state["evidence"]:
        source = evidence["source"]
        _show(output, tr("interactive.label.8"), config.sources[source].model_dump())
        _show(
            output,
            tr("interactive.label.9"),
            {key: evidence[key] for key in ("source", "path", "field", "where", "reduce", "count")},
        )
        records = evidence["records"] if full else evidence["records"][:5]
        output.write(tr("interactive.text.3"))
        for record in records:
            _show(output, tr("interactive.label.15"), record)
        _show(
            output,
            tr("interactive.label.10"),
            evidence["locations"] if full else evidence["locations"][:5],
        )
        if len(records) < evidence["count"]:
            output.write(tr("interactive.text.6", value1=len(records), value2=evidence["count"]))


def _card(output, binding, proposal, config, report, project, full=False):
    group, name = binding.split(":", 1)
    definition = getattr(proposal.additions, group)[name]
    state = report[group][name]
    _show(output, tr("interactive.label.3"), binding)
    _show(output, tr("interactive.label.4"), proposal.rationale[binding])
    _show(output, tr("interactive.label.5"), definition.model_dump())
    _show(output, tr("interactive.label.6"), tr("status." + state["status"]))
    location = state.get("location")
    if location:
        text, _ = project.text(location["file"])
        _show(
            output,
            tr("interactive.label.11"),
            text[max(0, location["start"] - 90) : location["end"] + 90],
        )
    if group == "occurrences":
        _show(output, tr("interactive.label.12"), state["actual"])
        _show(output, tr("interactive.label.13"), state["expected"])
    if group == "figures":
        _show(output, tr("interactive.label.14"), state)
    for metric in _metric_names(group, definition):
        _show_metric(output, metric, config, report, full)


def confirm_bindings(
    project: Project, value: dict, *, input_stream: TextIO, output: TextIO, batch=False
) -> dict:
    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError(
            "INTERACTIVE_TERMINAL",
            msg("error.INTERACTIVE_TERMINAL"),
        )
    proposal, config, report = inspect_proposal(project, value)
    bindings = [
        f"{group}:{name}"
        for group in ("occurrences", "claims", "figures")
        for name in getattr(proposal.additions, group)
    ]
    selected = []
    output.write(tr("interactive.text.1"))
    try:
        if batch:
            for index, binding in enumerate(bindings, 1):
                output.write(f"\n[{index}/{len(bindings)}]\n")
                _card(output, binding, proposal, config, report, project)
            while True:
                choice = _answer(input_stream, output, tr("batch.confirm_selection"))
                if choice in {"", "q", "取消"}:
                    return {"status": "cancelled", "bindings": [], "reason": "quit"}
                if choice in {"all", "全部"}:
                    selected = list(bindings)
                    break
                parts = choice.split(",")
                if all(part.strip().isascii() and part.strip().isdigit() for part in parts):
                    indices = [int(part.strip()) for part in parts]
                    if len(set(indices)) == len(indices) and all(
                        1 <= index <= len(bindings) for index in indices
                    ):
                        selected = [bindings[index - 1] for index in indices]
                        break
                output.write(tr("guide.invalid_choice") + "\n")
        for index, binding in enumerate([] if batch else bindings, 1):
            output.write(f"\n[{index}/{len(bindings)}]\n")
            _card(output, binding, proposal, config, report, project)
            while True:
                choice = _answer(input_stream, output, tr("interactive.prompt.2"))
                if choice in {"y", "yes", "是"}:
                    selected.append(binding)
                    break
                if choice in {"", "n", "no", "否"}:
                    break
                if choice in {"q", "取消"}:
                    return {"status": "cancelled", "bindings": [], "reason": "quit"}
                if choice in {"e", "证据"}:
                    _card(output, binding, proposal, config, report, project, full=True)
                else:
                    output.write(tr("interactive.text.8"))
        if not selected:
            return {"status": "cancelled", "bindings": [], "reason": "none selected"}
        output.write(tr("interactive.text.4"))
        for binding in selected:
            output.write("  " + _safe(binding) + "\n")
        output.write(tr("interactive.text.5", value1=_safe(proposal.config_path)))
        if _answer(input_stream, output, tr("interactive.prompt.1")) not in {"accept", "确认"}:
            return {"status": "cancelled", "bindings": [], "reason": "not committed"}
    except (EOFError, KeyboardInterrupt):
        output.write(tr("interactive.text.7"))
        return {"status": "cancelled", "bindings": [], "reason": "input interrupted"}
    output.write(tr("interactive.text.2"))
    output.flush()
    # Outside the input-interruption handler: never report a write as cancelled.
    # Re-inspects data/config/source hashes under the existing write lock.
    return accept_bindings(project, value, selected)
