"""Re-score frozen v2 targets with complete scientific values supported by v1.8.

Never overwrite v2 gold, frozen scores or its original evaluator. This is a
regression on previously inspected documents, not a new held-out experiment.
"""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import evaluate_native_v3 as scorer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out).resolve()
    assert output.is_relative_to(scorer.ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    scorer.CORPUS = scorer.ROOT / "validation/native-v2"
    results, inputs = [], {}
    for split in ("development", "held-out"):
        gold_path = scorer.CORPUS / (split + "-gold.json")
        font_path = scorer.CORPUS / (split + "-font-boxes.json")
        gold, font = (
            json.loads(gold_path.read_text("utf-8")),
            json.loads(font_path.read_text("utf-8")),
        )
        assert font["gold_sha256"] == scorer.digest(gold_path)
        inputs[split] = {"gold": scorer.digest(gold_path), "font_boxes": scorer.digest(font_path)}
        targets = []
        for target in gold["targets"]:
            target = {
                **target,
                "shape": "scientific" if "×10" in target["text"].replace(" ", "") else "scalar",
            }
            if target["format"] == "pdf":
                target["locator"] = {
                    **target["locator"],
                    "ink_bbox": target["locator"]["bbox"],
                    "bbox": font["boxes"][target["id"]],
                }
            targets.append(target)
        for case, filename in dict.fromkeys((t["case"], t["file"]) for t in targets):
            scored = scorer.score_file(
                output,
                case,
                filename,
                [t for t in targets if (t["case"], t["file"]) == (case, filename)],
            )
            results.extend({**r, "split": split} for r in scored)
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "tool_version": scorer.__version__,
        "mode": "previously_seen_v2_regression",
        "gold": inputs,
        "implementation": scorer.implementation(),
        "harness_sha256": scorer.digest(Path(__file__)),
        "compatibility_changes": [
            "The frozen v2 evaluator cannot parse complete ×10 scientific values; "
            "the v3 scorer accepts their complete normalized value and uses "
            "scientific display for that target.",
            "The unknown-location check permits 0.0001 point coordinate rounding, "
            "matching the product's four decimal coordinates. Supported-position "
            "tolerances are unchanged. Frozen historical outcomes remain unchanged.",
        ],
        "counts": dict(Counter(r["outcome"] for r in results)),
        "by_split": {
            s: dict(Counter(r["outcome"] for r in results if r["split"] == s))
            for s in ("development", "held-out")
        },
        "results": results,
    }
    scorer.save(output / "results.json", summary)
    print(json.dumps({"counts": summary["counts"], "by_split": summary["by_split"]}))
    return int(summary["counts"].get("mislocated", 0) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
