"""Terminal review of binding proposals, using the same guarded acceptance API."""

from __future__ import annotations

import unicodedata
from typing import TextIO

from paperdelta.errors import PaperDeltaError
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
    _show(output, f"metric {name}", {"value": state["value"], "unit": state["unit"]})
    _show(output, "calculation", state["definition"])
    dependencies = set(state.get("dependencies", []))
    definitions = {}
    while dependencies:
        child = dependencies.pop()
        if child not in definitions:
            definitions[child] = report["metrics"][child]["definition"]
            dependencies.update(report["metrics"][child].get("dependencies", []))
    if definitions:
        _show(output, "input calculations", definitions)
    for evidence in state["evidence"]:
        source = evidence["source"]
        _show(output, "source", config.sources[source].model_dump())
        _show(
            output,
            "selection",
            {key: evidence[key] for key in ("source", "path", "field", "where", "reduce", "count")},
        )
        records = evidence["records"] if full else evidence["records"][:5]
        output.write("  selected records:\n")
        for record in records:
            _show(output, "record", record)
        _show(output, "locations", evidence["locations"] if full else evidence["locations"][:5])
        if len(records) < evidence["count"]:
            output.write(
                f"  Showing {len(records)} of {evidence['count']} selected records. "
                "Enter e to view all records.\n"
            )


def _card(output, binding, proposal, config, report, project, full=False):
    group, name = binding.split(":", 1)
    definition = getattr(proposal.additions, group)[name]
    state = report[group][name]
    _show(output, "binding", binding)
    _show(output, "reason", proposal.rationale[binding])
    _show(output, "mapping", definition.model_dump())
    _show(output, "current consistency", state["status"])
    location = state.get("location")
    if location:
        text, _ = project.text(location["file"])
        _show(
            output,
            "paper context",
            text[max(0, location["start"] - 90) : location["end"] + 90],
        )
    if group == "occurrences":
        _show(output, "paper value", state["actual"])
        _show(output, "expected display", state["expected"])
    if group == "figures":
        _show(output, "figure source record", state)
    for metric in _metric_names(group, definition):
        _show_metric(output, metric, config, report, full)


def confirm_bindings(
    project: Project, value: dict, *, input_stream: TextIO, output: TextIO
) -> dict:
    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError(
            "INTERACTIVE_TERMINAL",
            "Interactive binding requires a terminal; use --accept ID for scripted selection",
        )
    proposal, config, report = inspect_proposal(project, value)
    bindings = [
        f"{group}:{name}"
        for group in ("occurrences", "claims", "figures")
        for name in getattr(proposal.additions, group)
    ]
    selected = []
    output.write(
        "Review proposed mappings. Matching values alone do not establish experiment identity.\n"
        "Choose mappings, then commit the selection at the end. "
        "Acceptance does not change paper text or attest review.\n"
    )
    try:
        for index, binding in enumerate(bindings, 1):
            output.write(f"\n[{index}/{len(bindings)}]\n")
            _card(output, binding, proposal, config, report, project)
            while True:
                choice = _answer(
                    input_stream, output, "Select this mapping? [y/N/e=all evidence/q] "
                )
                if choice in {"y", "yes"}:
                    selected.append(binding)
                    break
                if choice in {"", "n", "no"}:
                    break
                if choice == "q":
                    return {"status": "cancelled", "bindings": [], "reason": "quit"}
                if choice == "e":
                    _card(output, binding, proposal, config, report, project, full=True)
                else:
                    output.write("Enter y, n, e or q. Blank skips this mapping.\n")
        if not selected:
            return {"status": "cancelled", "bindings": [], "reason": "none selected"}
        output.write("\nSelected mappings:\n")
        for binding in selected:
            output.write("  " + _safe(binding) + "\n")
        output.write(f"Configuration: {_safe(proposal.config_path)}\n")
        if (
            _answer(
                input_stream, output, "Type accept to save exactly these mappings; blank cancels: "
            )
            != "accept"
        ):
            return {"status": "cancelled", "bindings": [], "reason": "not committed"}
    except (EOFError, KeyboardInterrupt):
        output.write("\nCancelled before acceptance.\n")
        return {"status": "cancelled", "bindings": [], "reason": "input interrupted"}
    output.write("Rechecking inputs and saving the selected mappings.\n")
    output.flush()
    # Outside the input-interruption handler: never report a write as cancelled.
    # Re-inspects data/config/source hashes under the existing write lock.
    return accept_bindings(project, value, selected)
