"""Create a new, owned synthetic mapping challenge suite; never overwrite one."""

import argparse
import copy
import csv
import io
from pathlib import Path

from paperdelta.storage import json_text

ROOT = Path(__file__).resolve().parents[1]


def csv_data(*groups, variant=False, percent_column=False):
    columns = ["dataset", "model", "split", "seed"]
    if variant:
        columns.append("variant")
    columns.append("accuracy")
    if percent_column:
        columns.append("accuracy_pct")
    rows = []
    for dataset, model, split, values, *extra in groups:
        for seed, value in enumerate(values, 1):
            row = dict(dataset=dataset, model=model, split=split, seed=seed, accuracy=value)
            if variant:
                row["variant"] = extra[0]
            if percent_column:
                from decimal import Decimal

                row["accuracy_pct"] = str(Decimal(value) * 100)
            rows.append(row)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def mapping(prefix, suffix, *, variant=False, percent_column=False, model="Ours"):
    columns = {
        "dataset": "string",
        "model": "string",
        "split": "string",
        "seed": "integer",
        "accuracy": "decimal",
    }
    keys = ["dataset", "model", "split", "seed"]
    where = {"dataset": "Data-A", "model": model, "split": "test"}
    if variant:
        keys.append("variant")
        columns["variant"] = "string"
        where["variant"] = "full"
    if percent_column:
        columns["accuracy_pct"] = "decimal"
    return {
        "additions": {
            "sources": {
                "results": {
                    "path": "results/metrics.csv",
                    "format": "csv",
                    "primary_key": keys,
                    "columns": columns,
                }
            },
            "metrics": {
                "target": {
                    "source": "results",
                    "field": "accuracy",
                    "where": where,
                    "reduce": "mean",
                    "expected_seeds": [1, 2, 3],
                    "unit": "fraction",
                }
            },
            "occurrences": {
                "result": {
                    "file": "paper/main.tex",
                    "anchor": {"prefix": prefix, "suffix": suffix},
                    "metric": "target",
                    "display": {"kind": "percent", "places": 1},
                }
            },
        },
        "rationale": {
            "occurrences:result": "Author-declared experimental identity, unit and aggregation."
        },
    }


def build_suite(output):
    output.mkdir(parents=True, exist_ok=False)
    values = ["0.839", "0.841", "0.843"]
    base = ("Data-A", "Ours", "test", values)
    prefix, literal, suffix = "The test accuracy is ", r"84.1\%", " on Data-A."
    default_mapping = mapping(prefix, suffix)
    tasks = []

    def add(
        case_id,
        category,
        request,
        data,
        *,
        text=None,
        references=None,
        decision="map",
        reason=None,
        target=None,
        expected_status="pass",
        extra_files=None,
    ):
        case = output / "cases" / case_id
        project = case / "project"
        (project / "paper").mkdir(parents=True)
        (project / "results").mkdir()
        paper = text or prefix + literal + suffix + "\n"
        (project / "paper/main.tex").write_bytes(paper.encode("utf-8"))
        (project / "results/metrics.csv").write_bytes(data.encode("utf-8"))
        (project / "paperdelta.yaml").write_bytes(
            b"schema_version: 1\npaper:\n  entry: paper/main.tex\n"
        )
        for name, content in (extra_files or {}).items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        (case / "request.md").write_bytes(
            (
                "# Mapping request\n\n" + request + "\n\n"
                "Propose only the requested numeric occurrence. Preserve the files. "
                "Use the declared experiment identity, units and complete run set. "
                "A stale paper number can have a correct mapping. If identity, data "
                "or the required derivation is unavailable, abstain and explain why. "
                "Do not infer an identity from equal numbers or calculate a significance test.\n"
            ).encode("utf-8")
        )
        oracle = {
            "expected_decision": decision,
            "category": category,
            "reason": reason or request,
            "target": target
            or {"file": "paper/main.tex", "prefix": prefix, "literal": literal, "suffix": suffix},
            "reference_inputs": (references or [copy.deepcopy(default_mapping)])
            if decision == "map"
            else [],
            "expected_reference_status": expected_status if decision == "map" else None,
        }
        (case / "oracle.json").write_bytes(json_text(oracle).encode("utf-8"))
        tasks.append({"id": case_id})

    add(
        "C01",
        "split_identity",
        "Bind the reported mean test accuracy of Ours on Data-A, seeds 1, 2 and 3.",
        csv_data(base, ("Data-A", "Ours", "train", values)),
    )
    add(
        "C02",
        "dataset_identity",
        "Bind the reported mean test accuracy of Ours on Data-A, seeds 1, 2 and 3.",
        csv_data(base, ("Data-B", "Ours", "test", values)),
    )
    add(
        "C03",
        "model_variant",
        "Bind mean test accuracy for the full variant of Ours on Data-A, seeds 1, 2 and 3.",
        csv_data((*base, "full"), (*base, "ablated"), variant=True),
        references=[mapping(prefix, suffix, variant=True)],
    )
    fraction = mapping(prefix, suffix, percent_column=True)
    percent = copy.deepcopy(fraction)
    percent["additions"]["metrics"]["target"].update(field="accuracy_pct", unit="percent")
    add(
        "C04",
        "unit_alternatives",
        "Bind Ours mean test accuracy on Data-A over seeds 1, 2 and 3. "
        "accuracy stores fractions; accuracy_pct stores equivalent percentages.",
        csv_data(base, percent_column=True),
        references=[fraction, percent],
    )
    pp_prefix, pp_suffix = "The accuracy gain is ", " percentage points on Data-A."
    pp = mapping(pp_prefix, pp_suffix)
    metrics = pp["additions"]["metrics"]
    metrics["baseline"] = copy.deepcopy(metrics["target"])
    metrics["baseline"]["where"]["model"] = "Baseline"
    metrics["gain"] = {"op": "percentage_point_difference", "args": ["target", "baseline"]}
    pp["additions"]["occurrences"]["result"].update(
        metric="gain", display={"kind": "decimal", "places": 1}
    )
    add(
        "C05",
        "percentage_point_difference",
        "Bind the percentage point improvement of Ours over Baseline on Data-A test. "
        "Compute each mean over seeds 1, 2 and 3.",
        csv_data(base, ("Data-A", "Baseline", "test", ["0.808", "0.810", "0.812"])),
        text=pp_prefix + "3.1" + pp_suffix + "\n",
        references=[pp],
        target={
            "file": "paper/main.tex",
            "prefix": pp_prefix,
            "literal": "3.1",
            "suffix": pp_suffix,
        },
    )
    add(
        "C06",
        "textual_model_identity",
        "Bind Data-A test accuracy for model identifier 001 (a string, distinct from 1). "
        "Use the mean of seeds 1, 2 and 3.",
        csv_data(("Data-A", "001", "test", values), ("Data-A", "1", "test", values)),
        references=[mapping(prefix, suffix, model="001")],
    )
    json_input = copy.deepcopy(default_mapping)
    json_input["additions"]["sources"] = {
        "results": {"path": "results/summary.json", "format": "json"}
    }
    json_input["additions"]["metrics"]["target"] = {
        "source": "results",
        "field": "/runs/evaluation~1test/accuracy.mean",
        "unit": "fraction",
    }
    add(
        "C07",
        "json_pointer",
        "Bind the test accuracy in summary.json at runs → evaluation/test → accuracy.mean. "
        "It is already a mean over the declared test runs and is stored as a fraction. "
        "metrics.csv is a legacy export with no authority for this request.",
        csv_data(base),
        references=[json_input],
        extra_files={
            "results/summary.json": '{"runs":{"evaluation/test":{"accuracy.mean":0.841},'
            '"evaluation/train":{"accuracy.mean":0.841}}}\n'
        },
    )
    add(
        "C08",
        "stale_manuscript",
        "Bind the paper's test accuracy to the new Ours result on Data-A, seeds 1, 2 and 3. "
        "The manuscript may still contain a value from an earlier run.",
        csv_data(base),
        text=prefix + r"86.0\%" + suffix + "\n",
        target={"file": "paper/main.tex", "prefix": prefix, "literal": r"86.0\%", "suffix": suffix},
        expected_status="mismatch",
    )
    table_prefix, table_suffix = "Ours & ", r" \\"
    table_input = mapping(table_prefix, table_suffix)
    table_input["additions"]["occurrences"]["result"]["display"]["percent_symbol"] = False
    add(
        "C09",
        "same_table_values",
        "Bind the Ours cell in this Data-A test table, using its mean over seeds 1, 2 and 3. "
        "Table values are percentage accuracy without the percent symbol.",
        csv_data(base, ("Data-A", "Baseline", "test", values)),
        text=(
            r"\begin{tabular}{ll}"
            + "\nOurs & 84.1"
            + table_suffix
            + "\nBaseline & 84.1"
            + table_suffix
            + "\n"
            + r"\end{tabular}"
            + "\n"
        ),
        references=[table_input],
        target={
            "file": "paper/main.tex",
            "prefix": table_prefix,
            "literal": "84.1",
            "suffix": table_suffix,
        },
    )
    add(
        "C10",
        "missing_experiment_identity",
        "Map the reported accuracy if its experiment can be established from the supplied files. "
        "No additional author notes are available.",
        csv_data(base, ("Data-B", "Ours", "test", values)),
        text=r"The accuracy is 84.1\%." + "\n",
        decision="abstain",
        reason="Both datasets have the same value; the paper and request do not identify one.",
        target={
            "file": "paper/main.tex",
            "prefix": "The accuracy is ",
            "literal": literal,
            "suffix": ".",
        },
    )
    add(
        "C11",
        "incomplete_seed_set",
        "Bind mean Ours test accuracy on Data-A over exactly seeds 1, 2 and 3. "
        "All available experiment files are included.",
        csv_data(("Data-A", "Ours", "test", values[:2])),
        decision="abstain",
        reason="Required seed 3 is absent; do not average the remaining runs as a substitute.",
    )
    add(
        "C12",
        "unsupported_significance",
        "Bind the paper's p-value using the supplied experimental evidence. "
        "Only aggregate accuracies were retained; raw observations and test metadata are absent.",
        csv_data(base, ("Data-A", "Baseline", "test", ["0.808", "0.810", "0.812"])),
        text="The reported p-value is 0.01 for this comparison.\n",
        decision="abstain",
        reason="No p-value or test specification is provided; means cannot establish it.",
        target={
            "file": "paper/main.tex",
            "prefix": "The reported p-value is ",
            "literal": "0.01",
            "suffix": " for this comparison.",
        },
    )
    manifest = {
        "suite_id": "mapping-contracts-v1",
        "protocol_revision": 2,
        "schema_version": 1,
        "cases": tasks,
        "scope": "Owned synthetic numeric mapping challenges; not representative real papers.",
        "license": "MIT",
    }
    (output / "manifest.json").write_bytes(json_text(manifest).encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT), "Use a new checkout-local directory"
    build_suite(output)
    print(f"Created 12 owned cases in {args.out}. No model or user trials were run.")


if __name__ == "__main__":
    main()
