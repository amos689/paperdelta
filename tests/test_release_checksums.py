from hashlib import sha256

import pytest

from tools.verify_release import validate_checksums, validate_ci_jobs


def test_release_assets_require_exact_manifest_and_matching_bytes(tmp_path):
    data = b"the verified distribution"
    (tmp_path / "package.whl").write_bytes(data)
    checksum = sha256(data).hexdigest()
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{checksum}  package.whl\n", "utf-8")
    assert validate_checksums(tmp_path, ["package.whl"]) == {"package.whl": checksum}
    with pytest.raises(ValueError, match="expected"):
        validate_checksums(tmp_path, ["different.whl"])
    (tmp_path / "package.whl").write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        validate_checksums(tmp_path, ["package.whl"])
    for line in (f"{checksum}  ../package.whl\n", f"{checksum}  package.whl\n" * 2):
        sums.write_text(line, "utf-8")
        with pytest.raises(ValueError, match="Invalid"):
            validate_checksums(tmp_path, ["package.whl"])


def ci_jobs():
    from pathlib import Path

    import yaml

    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text("utf-8")
    )["jobs"]
    jobs = []
    matrix = workflow["test"]["strategy"]["matrix"]
    for system in matrix["os"]:
        for version in matrix["python"]:
            jobs.append({"name": f"test ({system}, {version})", "conclusion": "success"})
    matrix = workflow["macos"]["strategy"]["matrix"]
    for host in matrix["host"]:
        for version in matrix["python"]:
            jobs.append(
                {"name": f"macOS {host['arch']} / Python {version}", "conclusion": "success"}
            )
    jobs.append({"name": workflow["browser"]["name"], "conclusion": "success"})
    return jobs


def test_release_gate_matches_actual_ci_matrix_and_browser():
    jobs = ci_jobs()
    assert validate_ci_jobs(jobs) == sorted(job["name"] for job in jobs)


@pytest.mark.parametrize("change", ["missing", "browser_failed", "skipped", "duplicate", "renamed"])
def test_release_gate_rejects_incomplete_or_substituted_jobs(change):
    jobs = ci_jobs()
    if change == "missing":
        jobs.pop()
    elif change == "browser_failed":
        jobs[-1]["conclusion"] = "failure"
    elif change == "skipped":
        jobs[0]["conclusion"] = "skipped"
    elif change == "duplicate":
        jobs[-1] = dict(jobs[0])
    else:
        jobs[-1]["name"] = "Unrelated successful job"
    with pytest.raises(ValueError, match="browser job"):
        validate_ci_jobs(jobs)
