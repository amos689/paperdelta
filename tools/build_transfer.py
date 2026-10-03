"""Create a source-and-wheel transfer ZIP without host environments or model files."""

import argparse
import json
import tomllib
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from audit_release import read_sdist, read_wheel

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    candidate = (ROOT / args.candidate).resolve()
    output = (ROOT / args.out).resolve()
    if not candidate.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output.exists():
        parser.error("Use an audited candidate and a new output directory inside this checkout")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    version = project["version"]
    audit = json.loads((candidate / "package-audit.json").read_text("utf-8"))
    for entry in audit["artifacts"]:
        raw = (candidate / Path(entry["path"]).name).read_bytes()
        if len(raw) != entry["bytes"] or sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Candidate changed after its audit")
    wheel = candidate / f"paperdelta-{version}-py3-none-any.whl"
    read_wheel(wheel)
    files = read_sdist(candidate / f"paperdelta-{version}.tar.gz")
    files["install/" + wheel.name] = wheel.read_bytes()
    evaluation = candidate / f"paperdelta-evaluation-{version}.zip"
    files["install/" + evaluation.name] = evaluation.read_bytes()
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "version": version,
        "kind": "Portable project transfer; create a new environment on the destination",
        "macos_execution_verified": False,
        "licenses": (
            "Original source/wheel MIT; evaluation ZIP retains its separately listed licenses."
        ),
        "files": {name: sha256(raw).hexdigest() for name, raw in sorted(files.items())},
    }
    files["TRANSFER.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    target = output / f"paperdelta-{version}-mac-transfer.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            archive.writestr(f"paperdelta-{version}/{name}", raw)
    with zipfile.ZipFile(target) as archive:
        assert len(archive.namelist()) == len(files)
        for name, raw in files.items():
            assert archive.read(f"paperdelta-{version}/{name}") == raw
    digest = sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    record = {
        "created_at": datetime.now(UTC).isoformat(),
        "file": target.name,
        "bytes": target.stat().st_size,
        "sha256": digest,
        "members_verified": len(files),
        "contains_host_environments_or_model_weights": False,
        "macos_execution_verified": False,
        "candidate_artifacts": audit["artifacts"],
    }
    (output / "transfer-audit.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
