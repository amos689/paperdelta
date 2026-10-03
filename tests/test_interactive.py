import io
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.interactive import confirm_bindings
from paperdelta.onboarding import init_project, propose_bindings
from paperdelta.storage import Project, json_text


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def draft(project):
    store = Project(project)
    config, _ = load_config(store)
    additions = {
        group: getattr(config, group)
        for group in ("sources", "metrics", "occurrences", "claims", "figures")
    }
    (project / "paperdelta.yaml").unlink()
    init_project(store, "paper/main.tex", ["results/metrics.csv"], macros={"score": 1})
    rationale = {
        f"{group}:{name}": "Data-A test, seeds 1/2/3; confirm the experimental identity."
        for group in ("occurrences", "claims")
        for name in additions[group]
    }
    proposal = propose_bindings(store, additions, rationale)
    return store, proposal


def files(project):
    return {
        p.relative_to(project.root): p.read_bytes() for p in project.root.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("answers", ["\n" * 6, "y\nq\n", "y\n", "y\n" + "n\n" * 5 + "\n"])
def test_no_commit_means_no_writes(draft, answers):
    project, proposal = draft
    before = files(project)
    result = confirm_bindings(project, proposal, input_stream=Terminal(answers), output=Terminal())
    assert result["status"] == "cancelled" and result["bindings"] == []
    assert files(project) == before


def test_explicit_selection_only_and_preview_contains_real_evidence(draft):
    project, proposal = draft
    original_paper = {p: data for p, data in files(project).items() if p.suffix == ".tex"}
    terminal = Terminal()
    result = confirm_bindings(
        project, proposal, input_stream=Terminal("y\n" + "n\n" * 5 + "accept\n"), output=terminal
    )
    assert result["bindings"] == ["occurrences:abstract_accuracy"]
    config, _ = load_config(project)
    assert set(config.occurrences) == {"abstract_accuracy"}
    assert set(config.metrics) == {"ours"} and not config.claims
    assert project.read(result["backup"])
    assert all(project.read(p.as_posix()) == data for p, data in original_paper.items())
    text = terminal.getvalue()
    for expected in (
        "paper context",
        "Our method achieves",
        "results/metrics.csv",
        '"split": "test"',
        '"seed": 3',
        "0.839",
        "current consistency",
    ):
        assert expected in text
    assert check_project(project.root)["coverage"]["confirmed"] == 1


def test_changed_data_during_review_cannot_be_accepted(draft, change_results):
    project, proposal = draft
    before_config = project.read("paperdelta.yaml")

    class MutatingTerminal(Terminal):
        def readline(self, *args):
            response = super().readline(*args)
            if response.strip() == "accept":
                change_results(project.root)
            return response

    with pytest.raises(PaperDeltaError, match="changed") as error:
        confirm_bindings(
            project,
            proposal,
            input_stream=MutatingTerminal("y\n" + "n\n" * 5 + "accept\n"),
            output=Terminal(),
        )
    assert error.value.code == "STALE_PROPOSAL"
    assert project.read("paperdelta.yaml") == before_config
    assert not project.path(".paperdelta/config-backups").exists()


def test_pipe_is_rejected_without_changing_configuration(draft):
    project, proposal = draft
    before = files(project)
    with pytest.raises(PaperDeltaError) as error:
        confirm_bindings(project, proposal, input_stream=io.StringIO("y\n"), output=Terminal())
    assert error.value.code == "INTERACTIVE_TERMINAL"
    assert files(project) == before


def test_all_evidence_command_and_terminal_control_escaping(tmp_path):
    store = Project(tmp_path)
    store.write("paper.tex", b"Result: 4.0 points.\n")
    store.write("values.json", b"[1,2,3,4,5,6,7]")
    init_project(store, "paper.tex", ["values.json"])
    proposal = propose_bindings(
        store,
        {
            "sources": {"measurements": {"path": "values.json", "format": "json"}},
            "metrics": {
                "mean": {
                    "source": "measurements",
                    "field": "",
                    "reduce": "mean",
                    "expected_count": 7,
                    "unit": "scalar",
                }
            },
            "occurrences": {
                "result": {
                    "file": "paper.tex",
                    "anchor": {"prefix": "Result: ", "suffix": " points."},
                    "metric": "mean",
                }
            },
        },
        {"occurrences:result": "Mean of seven measurements.\x1b[2J\u202euntrusted"},
    )
    output = Terminal()
    result = confirm_bindings(store, proposal, input_stream=Terminal("e\nn\n"), output=output)
    text = output.getvalue()
    assert result["status"] == "cancelled"
    assert "Showing 5 of 7" in text and '"value": 7' in text
    assert "\x1b" not in text and "\u202e" not in text
    assert r"\u001b" in text and r"\u202e" in text


def test_real_cli_rejects_pipe_and_conflicting_modes(draft):
    project, proposal = draft
    project.write("proposal.json", json_text(proposal).encode())
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "-C",
        str(project.root),
        "bind",
        "--proposal",
        "proposal.json",
        "--interactive",
    ]
    piped = subprocess.run(
        command, input="y\naccept\n", capture_output=True, encoding="utf-8", check=False
    )
    assert piped.returncode == 2 and "INTERACTIVE_TERMINAL" in piped.stderr
    conflict = subprocess.run(
        command + ["--accept", "occurrences:abstract_accuracy"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert conflict.returncode == 2 and "not allowed" in conflict.stderr
    assert check_project(project.root)["coverage"]["confirmed"] == 0


def test_keyboard_interrupt_while_choosing_cancels_without_writes(draft):
    project, proposal = draft
    before = files(project)

    class InterruptedTerminal(Terminal):
        def readline(self, *args):
            raise KeyboardInterrupt

    result = confirm_bindings(
        project, proposal, input_stream=InterruptedTerminal(), output=Terminal()
    )
    assert result["status"] == "cancelled"
    assert files(project) == before


def test_interrupt_during_acceptance_is_not_reported_as_cancelled(draft, monkeypatch):
    project, proposal = draft
    output = Terminal()

    def interrupted_write(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr("paperdelta.interactive.accept_bindings", interrupted_write)
    with pytest.raises(KeyboardInterrupt):
        confirm_bindings(
            project,
            proposal,
            input_stream=Terminal("y\n" + "n\n" * 5 + "accept\n"),
            output=output,
        )
    assert "Cancelled" not in output.getvalue()


def test_ten_bindings_can_be_confirmed_without_hiding_a_mismatch(tmp_path):
    project = Project(tmp_path)
    paper = "".join(f"Experiment {i}: 3.0 points.\n" for i in range(10)).encode()
    project.write("paper.tex", paper)
    project.write("values.json", b"[3,4,5]")
    init_project(project, "paper.tex", ["values.json"])
    occurrences = {
        f"result_{i}": {
            "file": "paper.tex",
            "anchor": {"prefix": f"Experiment {i}: ", "suffix": " points."},
            "metric": "mean",
        }
        for i in range(10)
    }
    proposal = propose_bindings(
        project,
        {
            "sources": {"values": {"path": "values.json", "format": "json"}},
            "metrics": {
                "mean": {
                    "source": "values",
                    "field": "",
                    "reduce": "mean",
                    "expected_count": 3,
                    "unit": "scalar",
                }
            },
            "occurrences": occurrences,
        },
        {
            f"occurrences:{name}": "Repeated mean of the declared measurements."
            for name in occurrences
        },
    )
    output = Terminal()
    result = confirm_bindings(
        project, proposal, input_stream=Terminal("y\n" * 10 + "accept\n"), output=output
    )
    assert result["status"] == "accepted" and len(result["bindings"]) == 10
    assert result["consistency_exit_code_before_acceptance"] == 1
    assert "[10/10]" in output.getvalue()
    checked = check_project(project.root)
    assert checked["coverage"]["confirmed"] == checked["coverage"]["mismatch"] == 10
    assert checked["exit_code"] == 1 and project.read("paper.tex") == paper
