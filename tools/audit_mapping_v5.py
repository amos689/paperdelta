"""Audit preserved real model records without executing models or archived code."""

import json
from collections import Counter
from hashlib import sha256


def audit_mapping_v5(entries):
    prefix = "validation/mapping-v5/"

    def read(name):
        return json.loads(entries[prefix + name])

    def digest(name):
        return "sha256:" + sha256(entries[prefix + name]).hexdigest()

    index = read("study-index.json")
    for name, expected in index["raw_files_sha256"].items():
        assert digest(name) == expected, name
    tasks = read("tasks/manifest.json")
    assert len(tasks["cases"]) == 24
    assert Counter(case["split"] for case in tasks["cases"]) == {
        "development": 12,
        "held-out": 12,
    }
    for name, expected in tasks["input_sha256"].items():
        assert digest("tasks/" + name) == expected, name
    for split in ("development", "held-out"):
        cases = [case for case in tasks["cases"] if case["split"] == split]
        assert Counter(case["expected_decision"] for case in cases) == {"map": 8, "abstain": 4}
        assert {case["manuscript_format"] for case in cases} == {
            "latex",
            "markdown",
            "quarto",
            "docx",
            "pdf",
        }
        assert Counter(case["request_language"] for case in cases) == {"en": 6, "zh-CN": 6}
    summaries = {}
    protocols = {}
    for label in index["runs"]:
        base = f"runs/{label}/"
        protocol = read(base + "protocol.json")
        execution = read(base + "execution.json")
        score = read(base + "score.json")
        started = read(base + "started.json")
        protocols[label] = protocol
        assert protocol["protocol_id"] == "paperdelta-mapping-v5"
        assert protocol["prepared_at"] < started["started_at"] < execution["completed_at"]
        assert score["protocol_sha256"] == digest(base + "protocol.json")
        assert score["execution_sha256"] == digest(base + "execution.json")
        assert protocol["max_actions_per_case"] == 16 and protocol["max_invalid_actions"] == 3
        assert protocol["max_tokens_per_action"] == 2048
        assert score["case_count"] == len(execution["outcomes"]) == 12
        assert score["accepted_bindings"] == protocol["accepted_bindings"] == 0
        assert score["cost"]["paid_api_cost_usd"] == 0
        assert score["cost"]["electricity_and_hardware_cost"] is None
        for name, expected in {
            **protocol["implementation_sha256"],
            **protocol["frozen_case_sha256"],
        }.items():
            assert digest(base + "implementation/" + name) == expected, name
        for name, expected in protocol["initial_prompt_sha256"].items():
            prompt_path = base + f"initial-prompts/{name}.json"
            assert digest(prompt_path) == expected
            messages = read(prompt_path)
            assert (
                "sha256:" + sha256(messages[0]["content"].encode()).hexdigest()
                == protocol["system_sha256"]
            )
            assert "oracle.json" not in messages[1]["content"]
        all_records = []
        for name, outcome in execution["outcomes"].items():
            assert outcome == read(base + f"cases/{name}/outcome.json")
            assert 1 <= len(outcome["actions"]) <= 16 and outcome["accepted_bindings"] == 0
            all_records.extend(outcome["actions"])
            for position, record in enumerate(outcome["actions"], 1):
                stem = base + f"cases/{name}/{position:02d}"
                assert record == read(stem + ".record.json")
                assert record["request_sha256"] == digest(stem + ".request.json")
                request = read(stem + ".request.json")
                assert request["max_tokens"] == 2048 and request["model"] == protocol["model"]
                if "response_sha256" in record:
                    assert record["response_sha256"] == digest(stem + ".response.json")
                    response = read(stem + ".response.json")
                    assert response.get("usage") == record.get("usage")
                if "action" in record:
                    feedback = read(stem + ".feedback.json")
                    assert record["status"] == feedback["status"]
                    assert record["valid"] == ("error" not in feedback)
            if outcome["status"] == "abstained":
                assert outcome.get("reason", "").strip()
                assert outcome["actions"][-1]["action"] == "abstain"
                assert outcome["actions"][-1]["valid"]
        assert score["action_count"] == len(all_records)
        assert score["invalid_actions"] == sum(not record["valid"] for record in all_records)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            assert score["usage"][key] == sum(
                (record.get("usage") or {}).get(key, 0) for record in all_records
            )
        results = score["outcomes"]
        assert set(results) == set(execution["outcomes"])
        assert score["statuses"] == dict(Counter(raw["status"] for raw in results.values()))
        assert score["complete_mapping_cases"] == sum(
            raw["complete_mapping"] for raw in results.values()
        )
        assert score["expected_abstentions"] == sum(
            raw["expected_abstention"] for raw in results.values()
        )
        for name, result in results.items():
            assert result["status"] == execution["outcomes"][name]["status"]
            if result["complete_mapping"]:
                assert result["core_valid_proposal"] and result["count_guard_verified"]
                assert result["expected_decision"] == "map"
            assert result["expected_abstention"] == (
                result["status"] == "abstained" and result["expected_decision"] == "abstain"
            )
        summaries[label] = {
            key: score[key]
            for key in (
                "split",
                "complete_mapping_cases",
                "mappable_cases",
                "expected_abstentions",
                "required_abstentions",
                "invalid_actions",
            )
        }
    selection = read("selection-freeze.json")
    chosen = index["selected_development"]
    assert selection["development_protocol_sha256"] == digest(f"runs/{chosen}/protocol.json")
    assert selection["development_score_sha256"] == digest(f"runs/{chosen}/score.json")
    assert selection["frozen_at"] > read(f"runs/{chosen}/score.json")["scored_at"]
    held = protocols[index["first_held_out"]]
    assert held["split"] == "held-out" and held["selection_freeze"] == selection
    assert held["selection_freeze_sha256"] == digest("selection-freeze.json")
    assert held["prepared_at"] > selection["frozen_at"]
    assert held["implementation_sha256"] == selection["implementation_sha256"]
    assert held["system_sha256"] == selection["system_sha256"]
    for name in index["runtime_runs"]:
        lifecycle = read(f"runtime/{name}/lifecycle.json")
        assert lifecycle["owned_process_stopped"] and lifecycle["owned_process"]
    return {
        "tasks": 24,
        "runs": summaries,
        "raw_record_hashes_verified": True,
        "held_out_selection_freeze_verified": True,
        "scope": "Archive integrity and recorded totals; no fresh inference or human review.",
    }
