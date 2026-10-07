"""Replay recorded Agent actions and scores with frozen code; never call a model."""

import argparse
import json
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child(study, output):
    # The old lock does not list its own hash. Supply its unchanged metadata to
    # a fresh replay copy instead of altering the original inference snapshot.
    runtime = output.with_suffix(".runtime")
    shutil.copytree(study / "implementation", runtime, ignore=shutil.ignore_patterns("__pycache__"))
    support = json.loads((ROOT / "validation/mapping-v5/replay-support.json").read_text("utf-8"))
    for name, expected in support["supplemental_metadata_sha256"].items():
        source = ROOT / name
        assert "sha256:" + sha256(source.read_bytes()).hexdigest() == expected
        target = runtime / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    sys.path[:0] = [str(runtime / "src"), str(runtime)]
    from paperdelta.agent import AgentSession
    from paperdelta.errors import PaperDeltaError
    from paperdelta.i18n import language_context
    from paperdelta.storage import Project, json_text, parse_json
    from tools.evaluate_mapping_v5 import assess, verify

    protocol, cases = verify(study)
    execution = parse_json((study / "execution.json").read_text("utf-8"))
    scored = parse_json((study / "score.json").read_text("utf-8"))
    outcomes = {}
    for name, case in cases.items():
        expected = execution["outcomes"][name]
        with language_context(case["language"]):
            agent = AgentSession(Project(case["path"] / "project"))
            state = agent.mapping_call("start")
            actions = []
            for record in expected["actions"]:
                index = record["action_index"]
                if "action" not in record:
                    # Transport failures have no core action to replay. Never label them successful.
                    actions.append({"index": index, "replayed": False, "error": record["error"]})
                    break
                raw = study / "cases" / name / f"{index:02d}.response.json"
                response = parse_json(raw.read_text("utf-8"))
                choice = response["choices"][0]
                try:
                    value = parse_json(choice["message"]["content"])
                    if not isinstance(value, dict) or choice.get("finish_reason") != "stop":
                        raise ValueError("A complete JSON action is required")
                    action, arguments, reason = (
                        value.get("action"),
                        value.get("arguments"),
                        value.get("reason", ""),
                    )
                except (ValueError, PaperDeltaError):
                    action, arguments, reason = "invalid_response", {}, ""
                if not isinstance(action, str):
                    action = "invalid_action"
                assert action == record["action"]
                state = agent.mapping_call(
                    "advance", state["session_id"], state["revision"], action, arguments, reason
                )
                code = state.get("error", {}).get("code")
                expected_error = record.get("error")
                expected_code = (
                    expected_error.get("code")
                    if isinstance(expected_error, dict)
                    else expected_error
                )
                assert code == expected_code, (name, index, code, expected_code)
                assert state["status"] == record["status"], (name, index)
                assert ("error" not in state) == record["valid"]
                actions.append(
                    {"action": action, "status": state["status"], "error": code, "replayed": True}
                )
            if expected["status"] != "transport_or_runtime_error":
                assert state["status"] == expected["status"], name
                if expected.get("proposal"):
                    assert parse_json(state["proposal_json"]) == expected["proposal"], name
            assert assess(case, expected, protocol["split"]) == scored["outcomes"][name], name
            outcomes[name] = {
                "status": expected["status"],
                "actions": actions,
                "score_matches": True,
            }
    verify(study)
    result = {
        "status": "passed",
        "case_count": len(outcomes),
        "outcomes": outcomes,
        "network_calls": 0,
        "accepted_bindings": 0,
        "scope": (
            "Replay recorded core actions and original strict scores with archived code; "
            "no fresh model inference."
        ),
    }
    output.write_text(json_text(result), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--child", type=Path)
    args = parser.parse_args()
    if args.child:
        child(args.child.resolve(), args.out.resolve())
        return
    from audit_mapping_v5 import audit_mapping_v5

    study = ROOT / "validation/mapping-v5"
    entries = {
        p.relative_to(ROOT).as_posix(): p.read_bytes()
        for p in study.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    audit = audit_mapping_v5(entries)
    output = args.out.resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    receipts = []
    for name in audit["runs"]:
        target = output / (name + ".json")
        with (output / (name + ".log")).open("w", encoding="utf-8") as log:
            subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-X",
                    "utf8",
                    str(Path(__file__).resolve()),
                    "--child",
                    str(study / "runs" / name),
                    "--out",
                    str(target),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        receipts.append({"run": name, "cases": 12, "status": "passed"})
        print(name + " recorded actions and scores passed", flush=True)
    (output / "evidence.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "replays": receipts,
                "network_calls": 0,
                "scope": "Frozen action and score replay; not fresh inference.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
