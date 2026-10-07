"""Retain actionable evidence when isolated installation exceeds its deadline."""

import subprocess

from tools.validate_uvx import ROOT, run_logged


def test_timeout_preserves_partial_output_and_failure(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 180
        raise subprocess.TimeoutExpired(
            args[0], 180, output="已开始安装\n".encode(), stderr=b"building native extension"
        )

    monkeypatch.setattr(subprocess, "run", timeout)
    result, stdout, log = run_logged(["uvx", "--isolated"], tmp_path, 4, {})
    assert result["exit_code"] == 124 and result["timed_out"]
    assert stdout == "已开始安装\n"
    assert "building native extension" in log and "not retried" in log
    assert (tmp_path / "command-04.log").read_text("utf-8") == log


def test_success_preserves_both_streams_and_redacts_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "2.0.0\n", str(ROOT)),
    )
    result, stdout, log = run_logged(["uvx", "--isolated"], tmp_path, 0, {})
    assert result["exit_code"] == 0 and not result["timed_out"]
    assert stdout == "2.0.0\n" and "<checkout>" in log and str(ROOT) not in log
