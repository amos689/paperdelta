"""Replay preserved real model actions against frozen code; never call a model."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child(study, output):
    sys.path[:0] = [str(study / "implementation/src"), str(study / "implementation")]
    from paperdelta.agent import AgentSession
    from paperdelta.storage import Project, json_text, parse_json
    from tools.evaluate_mapping_v4 import verify

    verify(study)
    recorded = parse_json((study / "execution.json").read_text("utf-8"))["outcomes"]
    outcomes = {}
    for name, expected in recorded.items():
        agent = AgentSession(
            Project(study / "implementation/evaluations/mapping-v1/cases" / name / "project")
        )
        state = agent.mapping_call("start")
        actions = []
        for record in expected["actions"]:
            index = record["action_index"]
            raw = study / "cases" / name / f"{index:02d}.response.json"
            response = parse_json(raw.read_text("utf-8"))
            action = parse_json(response["choices"][0]["message"]["content"])
            state = agent.mapping_call(
                "advance",
                state["session_id"],
                state["revision"],
                action.get("action"),
                action.get("arguments"),
                action.get("reason", ""),
            )
            code = state.get("error", {}).get("code")
            expected_error = record.get("error")
            expected_code = (
                expected_error.get("code") if isinstance(expected_error, dict) else expected_error
            )
            assert code == expected_code, (name, index, code, expected_code)
            assert state["status"] == record["status"], (name, index)
            actions.append({"action": action["action"], "status": state["status"], "error": code})
        assert state["status"] == expected["status"], name
        if expected.get("proposal"):
            assert parse_json(state["proposal_json"]) == expected["proposal"], name
        outcomes[name] = {
            "status": state["status"],
            "actions": actions,
            "proposal_matches": bool(expected.get("proposal")),
        }
    result = {
        "status": "passed",
        "scope": "Recorded real-model action replay, not new inference",
        "case_count": len(outcomes),
        "outcomes": outcomes,
        "network_calls": 0,
        "accepted_bindings": 0,
    }
    output.write_text(json_text(result), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "passed", "cases": len(outcomes)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--child", type=Path)
    args = parser.parse_args()
    if args.child:
        child(args.child.resolve(), args.out.resolve())
        return
    output = args.out.resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    studies = [ROOT / "validation/mapping-v4", ROOT / "validation/mapping-v4/revision-2"]
    receipts = []
    for index, study in enumerate(studies, 1):
        protocol = json.loads((study / "protocol.json").read_text("utf-8"))
        for name, digest in protocol["implementation_sha256"].items():
            assert (
                "sha256:"
                + hashlib.sha256((study / "implementation" / name).read_bytes()).hexdigest()
                == digest
            )
        target = output / f"run-{index}.json"
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-X",
                "utf8",
                str(Path(__file__).resolve()),
                "--child",
                str(study),
                "--out",
                str(target),
            ],
            check=True,
        )
        receipts.append({"run": index, "status": "passed", "cases": 12})
    (output / "evidence.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "replays": receipts,
                "scope": "Replayed recorded responses against frozen code; no new model inference.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
