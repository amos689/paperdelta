"""Probe installed reference mechanisms. Run in .venv-references.

This measures concrete behavior, not adoption effort or scientific correctness.
Each reference is given the configuration its own documented workflow expects.
"""

import json
import platform
import sys
import uuid
from importlib.metadata import version
from pathlib import Path

from calkit.questions import latex_values
from scitexlintr import apply_fixes, lint_tex, load_manifest

root = Path(__file__).resolve().parents[1]
scratch = root / ".tools/reference-probes" / uuid.uuid4().hex
scratch.mkdir(parents=True)
question = {
    "name": "comparison",
    "question": "Does Ours beat Baseline on Data-A?",
    "answer": {
        "if ours > baseline": "Ours achieves {ours:.1%} and beats Baseline.",
        "else": "Ours achieves {ours:.1%} and does not beat Baseline.",
    },
    "evidence": [
        {"kind": "value", "path": "result.json", "key": name, "name": name}
        for name in ["ours", "baseline"]
    ],
}
source = r"\newcommand{\SciVal}[2]{#1}" + "\n" + r"Accuracy: \SciVal{\Ours}{84.1\%}."
results = []
for phase, value in [("before", 0.841), ("after", 0.809)]:
    (scratch / "result.json").write_text(
        json.dumps({"ours": value, "baseline": 0.810}), encoding="utf-8"
    )
    manifest_path = scratch / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"numbers": [{"id": "ours", "value": value, "unit": "percent", "precision": 1}]}
        ),
        encoding="utf-8",
    )
    findings = lint_tex(
        source,
        filename="paper.tex",
        manifest=load_manifest(manifest_path),
        rules=["snapshot-mismatch"],
    )
    fixed, count = apply_fixes(source, findings)
    rendered = latex_values({"questions": [question]}, wdir=str(scratch))
    results.append(
        {
            "phase": phase,
            "calkit_conditional_answer": rendered["comparison.answer"],
            "scitexlintr_findings": [
                {"rule": finding.rule, "message": finding.message, "line": finding.line}
                for finding in findings
            ],
            "scitexlintr_fix_count": count,
            "scitexlintr_fixed_source": fixed,
        }
    )
assert results[0]["scitexlintr_findings"] == []
assert results[1]["scitexlintr_fix_count"] == 1
assert "80.9" in results[1]["scitexlintr_fixed_source"]
assert "does not beat" in results[1]["calkit_conditional_answer"]
record = {
    "python": platform.python_version(),
    "platform": sys.platform,
    "versions": {name: version(name) for name in ["calkit-python", "scitexlintr"]},
    "results": results,
    "scope": (
        "Public library APIs on an authored numeric-change scenario; no pipeline or TeX execution."
    ),
    "limits": [
        "No installation or onboarding time comparison was measured.",
        "scitexlintr was configured for its snapshot-mismatch rule and wrapper convention.",
        "Calkit was configured for conditional answers and evidence-driven LaTeX values.",
        "Both mechanisms work; this is not evidence that PaperDelta is more accurate.",
        "Independent product value still needs existing-paper onboarding trials.",
    ],
}
target = root / "docs/evidence/reference-probe.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, ensure_ascii=False, indent=2))
