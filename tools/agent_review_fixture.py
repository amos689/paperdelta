"""Small original fixtures for browser proposal review; no model or study gold."""

import argparse
from pathlib import Path

from paperdelta import builder
from paperdelta.agent import AgentSession
from paperdelta.onboarding import init_project, scan_project
from paperdelta.storage import Project, json_text, parse_json, sha256
from tools.create_mapping_v5 import EXTENSIONS, paper_bytes


def create(directory, kind):
    directory.mkdir(parents=True, exist_ok=False)
    project = Project(directory)
    entry = "paper." + EXTENSIONS[kind]
    label = "Maple / 001 / selected / test"
    project.write(
        entry,
        paper_bytes(
            kind, "The mean accuracy is ", "88.0%", " for model 001.", label, kind == "docx"
        ),
    )
    project.write(
        "results.csv",
        (
            "dataset,model,checkpoint,split,seed,score\n"
            + "".join(
                f"Maple,001,{checkpoint},test,{seed:03d},0.80000000000000000000000000001\n"
                for checkpoint in ("selected", "other")
                for seed in range(1, 13)
            )
        ).encode(),
    )
    init_project(project, entry, ["results.csv"])
    columns = {key: "string" for key in ("dataset", "model", "checkpoint", "split", "seed")}
    draft = builder.add_source(
        project,
        builder.start_draft(project),
        name="results",
        path="results.csv",
        format="csv",
        primary_key=list(columns),
        columns={**columns, "score": "decimal"},
    )
    draft = builder.add_metric(
        project,
        draft,
        name="accuracy",
        source="results",
        field="score",
        unit="fraction",
        reduce="mean",
        where={"dataset": "Maple", "model": "001", "checkpoint": "selected", "split": "test"},
        expected_count=12,
        expected_seeds=[f"{seed:03d}" for seed in range(1, 13)],
    )
    candidate = next(
        item for item in scan_project(project)["candidates"] if item["text"].startswith("88.0")
    )
    draft = builder.add_occurrences(
        project,
        draft,
        metric="accuracy",
        candidate_ids=[candidate["candidate_id"]],
        names=["result"],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale=(
            "Author selection: Maple, model 001, selected checkpoint, test split, "
            "all 12 string seed IDs."
        ),
        table_identity={"header_rows": 1, "row_prefix": [label]} if kind == "docx" else None,
    )
    response = AgentSession(project).finish_binding_draft(json_text(draft))
    project.write("proposal.json", response["proposal_json"].encode())
    proposal = parse_json(response["proposal_json"])
    project.write("stale-proposal.json", json_text(proposal).encode())
    return {
        "entry": entry,
        "input_sha256": {name: sha256(project.read(name)) for name in (entry, "results.csv")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--document", choices=list(EXTENSIONS), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.out.resolve()
    assert output.is_relative_to(root / "build") and not output.exists()
    print(json_text(create(output, args.document)))


if __name__ == "__main__":
    main()
