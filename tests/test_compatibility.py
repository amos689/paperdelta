"""Actual a2-produced records and journals must retain their supported upgrade behavior."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.onboarding import inspect_proposal
from paperdelta.patches import preview_patch, recover_transaction
from paperdelta.records import StoredReport
from paperdelta.snapshots import read_snapshot
from paperdelta.storage import Project, parse_json

LEGACY = """
import sys
from pathlib import Path
from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.onboarding import propose_bindings
from paperdelta.patches import create_patch, apply_patch
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, json_text
assert __version__ == '0.1.0a2'
project = Project(Path(sys.argv[1]))
report = check_project(project.root)
create_snapshot(project, 'legacy-a2', report)
record_review(project, 'main_comparison', report['claims']['main_comparison']['state_fingerprint'],
              'Synthetic legacy fixture', 'Compatibility check, not a human observation',
              attest_reviewed=True)
config, _ = load_config(project)
proposal = propose_bindings(project,
    {'occurrences': {'legacy_copy': config.occurrences['abstract_accuracy'].model_dump()}},
    {'occurrences:legacy_copy': 'Explicit duplicate location for a version refusal test'})
data, _ = project.text('results/metrics.csv')
# Replace all three simultaneously, avoiding cascaded replacements.
data = data.replace('0.839', 'OLD_A').replace('0.841', 'OLD_B').replace('0.843', 'OLD_C')
data = data.replace('OLD_A', '0.843').replace('OLD_B', '0.845').replace('OLD_C', '0.847')
project.write('results/metrics.csv', data.encode('utf-8'))
patch = create_patch(project, check_project(project.root))
applied = apply_patch(project, patch)
print(json_text({'proposal': proposal, 'patch': patch,
                 'transaction_id': applied['transaction_id']}))
"""


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_upgrade_reads_a2_records_refuses_old_proposals_and_recovers_old_journal(project, language):
    archive = Path(__file__).resolve().parents[1] / "evaluations/implementations/a2/src"
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*.tex")}
    data_before = (project / "results/metrics.csv").read_bytes()
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", LEGACY, str(project)],
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(archive)},
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    legacy = parse_json(completed.stdout)
    store = Project(project)
    with language_context(language):
        snapshot = read_snapshot(store, "legacy-a2")
        assert StoredReport.model_validate(snapshot["report"]).tool_version == "0.1.0a2"
        report = check_project(project, baseline=snapshot)
        assert report["exit_code"] == 0 and report["baseline"]["name"] == "legacy-a2"
        assert report["claims"]["main_comparison"]["review"] == "superseded"
        with pytest.raises(PaperDeltaError) as patch_error:
            preview_patch(store, legacy["patch"])
        assert patch_error.value.code == "PATCH_IDENTITY"
        with pytest.raises(PaperDeltaError) as proposal_error:
            inspect_proposal(store, legacy["proposal"])
        assert proposal_error.value.code == "PROPOSAL_IDENTITY"
        assert recover_transaction(store, legacy["transaction_id"])["status"] == "preview"
        assert (
            recover_transaction(store, legacy["transaction_id"], write=True)["status"] == "reverted"
        )
        assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*.tex")} == before
        store.write("results/metrics.csv", data_before)
        restored = check_project(project, baseline=snapshot)
        assert restored["exit_code"] == 0
        assert restored["claims"]["main_comparison"]["review"] == "reviewed"
