"""Verify candidate archive contents, source identities and retained licenses.

This inspects locally built archives without extracting or executing their files.
It does not establish cross-platform compatibility or perform legal clearance.
"""

import argparse
import base64
import csv
import io
import json
import tarfile
import tomllib
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def check_path(name):
    path = PurePosixPath(name)
    assert not path.is_absolute() and ".." not in path.parts and "\\" not in name, name
    assert not any(
        p in {".git", ".tools", ".paperdelta", "__pycache__", "build"} or p.startswith(".venv")
        for p in path.parts
    ), name
    assert path.suffix.lower() not in {".exe", ".dll", ".pyc", ".pem", ".key"}, name
    assert path.name not in {".env", "credentials"}, name


def read_wheel(path):
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
        assert len(entries) == len(archive.namelist()), "Duplicate wheel paths"
    for name in entries:
        check_path(name)
        assert name.startswith("paperdelta/") or ".dist-info/" in name, name
    record = next(name for name in entries if name.endswith(".dist-info/RECORD"))
    recorded = set()
    for name, digest, size in csv.reader(io.StringIO(entries[record].decode("utf-8"))):
        assert name not in recorded, "Duplicate wheel RECORD entry"
        recorded.add(name)
        if name == record:
            assert not digest and not size
            continue
        assert digest.startswith("sha256="), name
        actual = base64.urlsafe_b64encode(sha256(entries[name]).digest()).decode().rstrip("=")
        assert digest == "sha256=" + actual and int(size) == len(entries[name]), name
    assert recorded == set(entries), "Wheel RECORD must cover every file"
    return entries


def read_sdist(path):
    entries = {}
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        roots = {PurePosixPath(m.name).parts[0] for m in members}
        assert len(roots) == 1, "Source archive must have one root"
        for member in members:
            check_path(member.name)
            assert member.isdir() or member.isfile(), "No links or device files in source archive"
            if member.isfile():
                name = PurePosixPath(member.name).relative_to(next(iter(roots))).as_posix()
                assert name not in entries, "Duplicate source archive path"
                entries[name] = archive.extractfile(member).read()
    return entries


def check_metadata(raw, project):
    metadata = BytesParser().parsebytes(raw)
    assert metadata["Name"] == project["name"]
    assert metadata["Version"] == project["version"]
    assert metadata["Requires-Python"] == project["requires-python"]
    assert metadata["License-Expression"] == project["license"]
    assert "LICENSE" in metadata.get_all("License-File", [])
    extras = metadata.get_all("Provides-Extra", [])
    assert set(extras) == set(project["optional-dependencies"])
    dependencies = metadata.get_all("Requires-Dist", [])
    # Installed dependency libraries are not bundled in these archives.
    assert len([d for d in dependencies if ";" not in d]) == len(project["dependencies"])
    return {
        "version": metadata["Version"],
        "requires_python": metadata["Requires-Python"],
        "license_expression": metadata["License-Expression"],
        "extras": extras,
        "requirements": dependencies,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    assert directory.is_relative_to(ROOT), "Use a candidate directory inside this checkout"
    wheels, sdists = list(directory.glob("*.whl")), list(directory.glob("*.tar.gz"))
    evaluations = list(directory.glob("paperdelta-evaluation-*.zip"))
    assert len(wheels) == len(sdists) == len(evaluations) == 1, "Expected three release artifacts"
    wheel, sdist = read_wheel(wheels[0]), read_sdist(sdists[0])
    with zipfile.ZipFile(evaluations[0]) as archive:
        evaluation = {name: archive.read(name) for name in archive.namelist()}
        assert len(evaluation) == len(archive.namelist())
    for name in evaluation:
        check_path(name)
    bundle = json.loads(evaluation["evaluation-bundle.json"])
    assert bundle["license_expression"] == "MIT AND CC-BY-4.0 AND CC-BY-SA-4.0"
    for name, identity in bundle["files"].items():
        assert sha256(evaluation[name]).hexdigest() == identity["sha256"], name
        assert len(evaluation[name]) == identity["bytes"], name
        assert evaluation[name] == (ROOT / name).read_bytes(), name
    assert not any(
        n.startswith("tests/corpus/") or n.startswith("docs/evidence/corpus") for n in sdist
    ), "Separately licensed paper sources/results must stay out of the MIT Python distribution"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    metadata = check_metadata(
        wheel[next(n for n in wheel if n.endswith(".dist-info/METADATA"))], project
    )
    assert metadata == check_metadata(sdist["PKG-INFO"], project)

    core_files = list((ROOT / "src/paperdelta").glob("*.py"))
    for path in core_files:
        raw = path.read_bytes()
        assert wheel[path.relative_to(ROOT / "src").as_posix()] == raw, path
        assert sdist[path.relative_to(ROOT).as_posix()] == raw, path
    license_name = next(n for n in wheel if n.endswith("/licenses/LICENSE"))
    assert wheel[license_name] == (ROOT / "LICENSE").read_bytes()

    required = [
        "LICENSE",
        "README.md",
        "CONTRIBUTING.md",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
        "MANIFEST.in",
        ".gitattributes",
        ".gitignore",
        ".github/workflows/ci.yml",
        "docs/evaluation.md",
        "docs/progress.md",
        "docs/ci.md",
        "docs/report-format.md",
        "docs/first-use-trial.md",
        "docs/schemas/report.schema.json",
        "docs/assets/paperdelta-demo.webm",
        "docs/assets/report-preview.png",
        "examples/figure-support/accuracy.pdf",
        "examples/figure-support/accuracy.record.json",
        "examples/ci/paper-check.yml",
    ]
    required += [p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("*.py")]
    required += [p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("*.cjs")]
    required += [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("*.py")]
    required += [
        p.relative_to(ROOT).as_posix()
        for case in ("ambiguous-table", "unicode-macro")
        for p in (ROOT / "examples" / case).rglob("*")
        if p.is_file() and not {"build", ".paperdelta"}.intersection(p.relative_to(ROOT).parts)
    ]
    for name in required:
        assert sdist.get(name) == (ROOT / name).read_bytes(), name

    mapping_files = [
        path for path in (ROOT / "evaluations/mapping-v1").rglob("*") if path.is_file()
    ]
    for path in mapping_files:
        name = path.relative_to(ROOT).as_posix()
        assert sdist.get(name) == path.read_bytes(), name
    mapping_lock = json.loads(sdist["evaluations/mapping-v1/protocol-lock.json"])
    for name, digest in mapping_lock["identities"].items():
        assert "sha256:" + sha256(sdist[name]).hexdigest() == digest, name

    manifest = json.loads(evaluation["tests/corpus/manifest.json"])
    corpus_count = corpus_bytes = 0
    for paper in manifest["papers"]:
        retained = {record["path"] for record in paper["files"]}
        assert set(paper["license_files"]) <= retained, paper["id"]
        for record in paper["files"]:
            name = f"tests/corpus/papers/{paper['id']}/source/{record['path']}"
            raw = evaluation[name]
            assert sha256(raw).hexdigest() == record["sha256"], name
            assert len(raw) == record["bytes"], name
            corpus_count += 1
            corpus_bytes += len(raw)
    reflectometry = next(p for p in manifest["papers"] if p["id"] == "reflectometry")
    assert reflectometry["license"] == "CC-BY-SA-4.0"
    notices = evaluation["THIRD_PARTY_NOTICES.md"].decode("utf-8")
    assert "CC BY-SA 4.0" in notices and "does not relicense" in " ".join(notices.split())

    study = json.loads(evaluation["tests/corpus/active-study.json"])
    assert bundle["active_study"] == study
    frozen = json.loads(evaluation[study["protocol_lock"]])
    assert frozen["study"] == study
    for name, digest in frozen["identities"].items():
        raw = evaluation[name] if name.startswith("tests/corpus/") else sdist[name]
        assert "sha256:" + sha256(raw).hexdigest() == digest, name
    original = json.loads(evaluation[study["previous_protocol"]])
    history = study["previous_implementation"]
    assert (
        evaluation[f"{history}/tests/corpus/protocol-lock.json"]
        == evaluation[study["previous_protocol"]]
    )
    for name, digest in original["identities"].items():
        assert "sha256:" + sha256(evaluation[f"{history}/{name}"]).hexdigest() == digest, name
    record = {
        "checked_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            {
                "path": p.relative_to(ROOT).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": sha256(p.read_bytes()).hexdigest(),
            }
            for p in [*wheels, *sdists, *evaluations]
        ],
        "metadata": metadata,
        "wheel_files": len(wheel),
        "sdist_files": len(sdist),
        "evaluation_bundle_files": len(evaluation),
        "evaluation_license_expression": bundle["license_expression"],
        "core_source_files_match_checkout": len(core_files),
        "required_support_files_match_checkout": len(set(required)),
        "owned_mapping_suite_files_match_checkout": len(mapping_files),
        "mapping_protocol_identity_count": len(mapping_lock["identities"]),
        "corpus": {
            "papers": len(manifest["papers"]),
            "files": corpus_count,
            "bytes": corpus_bytes,
            "every_retained_file_digest_matches": True,
            "license_notices_present": True,
        },
        "frozen_protocol_identity_count": len(frozen["identities"]),
        "study": study,
        "retained_original_protocol_identity_count": len(original["identities"]),
        "wheel_record_verified": True,
        "excluded": ["virtual environments", "scratch trees", "transactions", "native executables"],
        "scope": "Content and metadata inspection of these exact locally built artifacts.",
    }
    target = directory / "package-audit.json"
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
