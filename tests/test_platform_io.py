"""Exercise filesystem and real terminal behavior used by macOS and other hosts."""

import errno
import json
import os
import stat
import subprocess
import sys
import time
import unicodedata

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import init_project, propose_bindings
from paperdelta.patches import apply_patch, create_patch, recover_transaction
from paperdelta.storage import Project, json_text


def one_mapping(root, paper="paper.tex"):
    store = Project(root)
    raw = b"\xef\xbb\xbf" + "结果: 42.0 points.\r\n".encode()
    store.write(paper, raw)
    store.write("data.json", b'{"value": 42.0}')
    init_project(store, paper, ["data.json"])
    proposal = propose_bindings(
        store,
        {
            "sources": {"data": {"path": "data.json", "format": "json"}},
            "metrics": {"value": {"source": "data", "field": "/value", "unit": "scalar"}},
            "occurrences": {
                "result": {
                    "file": paper,
                    "anchor": {"prefix": "结果: ", "suffix": " points."},
                    "metric": "value",
                }
            },
        },
        {"occurrences:result": "The declared scalar in data.json, not inferred from equal values."},
    )
    store.write("proposal.json", json_text(proposal).encode())
    return store, raw


@pytest.mark.parametrize("normalization", ["NFC", "NFD"])
def test_unicode_filename_patch_recovery(tmp_path, normalization):
    from paperdelta.onboarding import accept_bindings

    name = unicodedata.normalize(normalization, "论文 café/主文件 résumé.tex")
    store, original = one_mapping(tmp_path, name)
    proposal = json.loads(store.text("proposal.json")[0])
    accept_bindings(store, proposal, ["occurrences:result"])
    store.write("data.json", b'{"value": 43.5}')
    patch = create_patch(store, check_project(store.root))
    assert len(patch["changes"]) == 1
    applied = apply_patch(store, patch)
    assert applied["report"]["exit_code"] == 0
    assert store.read(name) == original.replace(b"42.0", b"43.5")
    recover_transaction(store, applied["transaction_id"], write=True)
    assert store.read(name) == original


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX symlink and mode semantics")
def test_symlinked_project_root_keeps_boundary_and_permissions(tmp_path):
    target = tmp_path / "physical"
    target.mkdir()
    alias = tmp_path / "linked"
    alias.symlink_to(target, target_is_directory=True)
    store = Project(alias)
    store.write("paper.tex", b"before")
    (target / "paper.tex").chmod(0o640)
    store.write("paper.tex", b"after")
    assert store.read("paper.tex") == b"after"
    assert stat.S_IMODE((target / "paper.tex").stat().st_mode) == 0o640
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PaperDeltaError) as error:
        store.write("escape/forbidden.tex", b"must not be written")
    assert error.value.code == "UNSAFE_PATH"
    assert not (outside / "forbidden.tex").exists()


@pytest.mark.skipif(os.name == "nt", reason="Requires a POSIX pseudo-terminal")
@pytest.mark.parametrize("decision", ["accept", "cancel"])
def test_actual_posix_terminal_binding(tmp_path, decision):
    import pty
    import select

    store, original = one_mapping(tmp_path / "论文 terminal")
    configuration = store.read("paperdelta.yaml")
    master, slave = pty.openpty()
    process = None
    transcript = bytearray()
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-X",
                "utf8",
                "-m",
                "paperdelta",
                "-C",
                str(store.root),
                "bind",
                "--proposal",
                "proposal.json",
                "--interactive",
            ],
            stdin=slave,
            stderr=slave,
            stdout=subprocess.PIPE,
        )
        os.close(slave)
        slave = None

        def until(marker):
            deadline = time.monotonic() + 30
            while marker not in transcript:
                assert time.monotonic() < deadline, transcript.decode("utf-8", errors="replace")
                if not select.select([master], [], [], 0.25)[0]:
                    assert process.poll() is None, "CLI exited before its terminal prompt"
                    continue
                try:
                    chunk = os.read(master, 8192)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    chunk = b""
                assert chunk, "Terminal closed before the expected prompt"
                transcript.extend(chunk)
                assert len(transcript) < 128 * 1024

        until(b"Select this mapping?")
        assert store.read("paperdelta.yaml") == configuration
        os.write(master, b"y\n" if decision == "accept" else b"q\n")
        if decision == "accept":
            until(b"Type accept to save")
            assert store.read("paperdelta.yaml") == configuration
            os.write(master, b"accept\n")
        stdout, _ = process.communicate(timeout=30)
        assert process.returncode == 0
        result = json.loads(stdout)
        assert b"paper context" in transcript and "结果".encode() in transcript
        assert store.read("paper.tex") == original
        config, _ = load_config(store)
        if decision == "accept":
            assert result["bindings"] == ["occurrences:result"]
            assert set(config.occurrences) == {"result"}
            assert check_project(store.root)["exit_code"] == 0
            assert store.read(result["backup"]) == configuration
        else:
            assert result["status"] == "cancelled"
            assert not config.occurrences
            assert store.read("paperdelta.yaml") == configuration
            assert not store.path(".paperdelta/config-backups").exists()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        if slave is not None:
            os.close(slave)
        os.close(master)
