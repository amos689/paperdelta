"""Check public owned fixtures, portable evidence and Unicode/BOM/CRLF recovery."""

import argparse
import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from paperdelta.analysis import check_project
from paperdelta.experiment_imports import import_evidence
from paperdelta.patches import apply_patch, create_patch, recover_transaction
from paperdelta.reports import write_reports
from paperdelta.storage import Project, parse_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = Project(repository).path(args.out)
    assert not output.exists(), "Choose a new output directory"
    results = {}
    for name, expected in (
        ("research-paper", 0),
        ("ambiguous-table", 2),
        ("unicode-macro", 0),
        ("evidence-native", 0),
        ("seed-statistics", 0),
    ):
        source = repository / "examples" / name
        root = output / name
        shutil.copytree(
            source,
            root,
            ignore=lambda _, names: [n for n in names if n in {"build", ".paperdelta"}],
        )
        report = check_project(root)
        assert report["exit_code"] == expected, report
        project = Project(root)
        write_reports(project, "build/review", report)
        results[name] = {
            "exit_code": report["exit_code"],
            "coverage": report["coverage"],
            "rules": sorted({d["rule"] for d in report["diagnostics"]}),
        }
        if name == "evidence-native":
            imported = import_evidence(
                project, parse_json(project.text("import.json")[0]), "build/static.pdevidence.json"
            )
            assert imported["records"] == 2
            assert report["coverage"]["pass"] == 2
            assert report["metrics"]["primary"]["value"] == "0.80000000000000000000000000001"
            results[name]["offline_export"] = imported["provenance"]["export_id"]
        if name == "ambiguous-table":
            assert report["occurrences"]["table_accuracy"]["status"] == "unknown"
            assert "ANCHOR_AMBIGUOUS" in results[name]["rules"]
        if name == "seed-statistics":
            assert report["coverage"]["pass"] == 4
            assert report["coverage"]["unbound_numbers"] == []
            data = "results.tsv"
            project.write(
                data, project.read(data).replace(b"\t80\n", b"\t79\n").replace(b"\t84\n", b"\t85\n")
            )
            changed = check_project(root)
            assert changed["metrics"]["accuracy"]["value"] == "82"
            assert changed["occurrences"]["mean_sd"]["status"] == "mismatch"
            assert changed["occurrences"]["interval"]["status"] == "mismatch"
            assert changed["occurrences"]["sample_count"]["status"] == "pass"
            project.write(data, project.read(data).replace(b"method\t3\t82\n", b""))
            assert check_project(root)["metrics"]["accuracy"]["error"] == "SEED_SET"
            results[name]["unchanged_mean_changed_uncertainty"] = True
            results[name]["missing_seed_unknown"] = True
        if name == "unicode-macro":
            path = "论文/主文件.tex"
            original = project.read(path).decode("utf-8").replace("\r\n", "\n")
            original = b"\xef\xbb\xbf" + original.replace("\n", "\r\n").encode("utf-8")
            project.write(path, original)
            assert check_project(root)["exit_code"] == 0
            data = "实验结果/metrics.json"
            project.write(data, project.read(data).replace(b"0.841", b"0.845"))
            changed = check_project(root)
            assert changed["exit_code"] == 1
            patch = create_patch(project, changed)
            assert len(patch["changes"]) == 1
            applied = apply_patch(project, patch)
            assert applied["report"]["exit_code"] == 0
            assert project.read(path) == original.replace(b"84.1", b"84.5")
            recover_transaction(project, applied["transaction_id"], write=True)
            assert project.read(path) == original
            results[name]["bom_crlf_changed_check_exit"] = 1
            results[name]["patched_check_exit"] = 0
            results[name]["outside_bytes_preserved"] = True
            results[name]["recovered_sha256"] = sha256(original).hexdigest()
    evidence = {
        "checked_at": datetime.now(UTC).isoformat(),
        "cases": results,
        "scope": "Owned fixtures, automated local validation; no independent users.",
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
