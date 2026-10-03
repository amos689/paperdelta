"""Verify and download a stable release before its isolated PyPI publication job."""

import argparse
import json
import re
import subprocess
import tomllib
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "amos689/paperdelta"


def run(*arguments):
    return subprocess.check_output(arguments, cwd=ROOT, text=True, encoding="utf-8").strip()


def validate_checksums(directory, expected):
    entries = {}
    for line in (directory / "SHA256SUMS").read_text("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if not match or match[2] in entries:
            raise ValueError("Invalid or duplicate checksum entry")
        entries[match[2]] = match[1]
    if set(entries) != set(expected):
        raise ValueError("Checksum list does not match the expected three distribution artifacts")
    for name, digest in entries.items():
        if sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.tag) or args.tag != "v" + version:
        raise ValueError("Only a stable tag matching package metadata can be published")
    git = ("git", "-c", f"safe.directory={ROOT.as_posix()}")
    head = run(*git, "rev-parse", "HEAD")
    if head != run(*git, "rev-parse", f"{args.tag}^{{commit}}"):
        raise ValueError("Checkout must match the exact release tag")
    release = json.loads(
        run(
            "gh",
            "release",
            "view",
            args.tag,
            "--repo",
            REPOSITORY,
            "--json",
            "tagName,isDraft,isPrerelease,url",
        )
    )
    if release["isDraft"] or release["isPrerelease"] or release["tagName"] != args.tag:
        raise ValueError("A published, stable GitHub release is required")
    runs = json.loads(
        run(
            "gh",
            "run",
            "list",
            "--repo",
            REPOSITORY,
            "--workflow",
            "ci.yml",
            "--commit",
            head,
            "--limit",
            "50",
            "--json",
            "databaseId,headSha,status,conclusion,url",
        )
    )
    passed = [
        r
        for r in runs
        if r["headSha"] == head and r["status"] == "completed" and r["conclusion"] == "success"
    ]
    if not passed:
        raise ValueError("No successful complete CI run exists for this exact commit")
    ci = passed[0]
    details = json.loads(
        run("gh", "run", "view", str(ci["databaseId"]), "--repo", REPOSITORY, "--json", "jobs")
    )
    if len(details["jobs"]) != 16 or any(j["conclusion"] != "success" for j in details["jobs"]):
        raise ValueError("All 16 supported-platform CI jobs must pass")
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError("Use a fresh project-local output directory")
    output.mkdir(parents=True, exist_ok=False)
    artifacts = [
        f"paperdelta-{version}-py3-none-any.whl",
        f"paperdelta-{version}.tar.gz",
        f"paperdelta-evaluation-{version}.zip",
    ]
    patterns = [argument for name in [*artifacts, "SHA256SUMS"] for argument in ("--pattern", name)]
    run(
        "gh", "release", "download", args.tag, "--repo", REPOSITORY, "--dir", str(output), *patterns
    )
    identities = validate_checksums(output, artifacts)
    receipt = {
        "version": version,
        "commit": head,
        "release": release["url"],
        "ci": ci["url"],
        "passed_platform_jobs": 16,
        "artifacts_sha256": identities,
    }
    (output / "publication-verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n", "utf-8"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
