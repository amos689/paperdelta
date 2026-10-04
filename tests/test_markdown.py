"""Static source readings are checked against independent literal source positions."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.coverage import change_scope
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.manuscripts import change_manuscripts
from paperdelta.markdown_document import MarkdownDocument
from paperdelta.models import Config
from paperdelta.onboarding import accept_bindings, init_project, scan_project
from paperdelta.patches import create_patch
from paperdelta.records import StoredReport
from paperdelta.reports import html_report, text_report
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project


@pytest.mark.parametrize("extension,format", [("md", "markdown"), ("qmd", "quarto")])
@pytest.mark.parametrize("ending,bom", [("\n", ""), ("\r\n", "\ufeff"), ("\r", "")])
def test_original_unicode_bytes_lines_and_formatting(extension, format, ending, bom):
    text = bom + ending.join(
        [
            "# Abstract",
            "",
            "模型甲的准确率为 **84.1%**，基线为 _80.9_%。",
            "",
            "1. Another result is 72.6.",
            "",
            "> A quoted result is 65.3.",
            "",
        ]
    )
    raw = text.encode("utf-8")
    document = MarkdownDocument("paper." + extension, raw, format)
    numbers = document.numbers()
    assert [n.text for n in numbers] == ["84.1", "80.9", "72.6", "65.3"]
    assert not document.issues
    for number, line in zip(numbers, [3, 3, 5, 7], strict=True):
        expected = text.index(number.text)
        assert number.start == expected and number.end == expected + len(number.text)
        assert number.line == line
        assert number.byte_start == len(text[:expected].encode())
        assert raw[number.byte_start : number.byte_end] == number.text.encode()
        assert number.format == format
        assert document.locate(document.anchor_for_span(number)).to_dict() == number.to_dict()
    assert document.raw == raw


def test_links_keep_only_visible_label_and_original_unique_position():
    text = "A [score **84.1**](https://example.org/result/2026) is compared with 80.9.\n"
    document = MarkdownDocument("p.md", text.encode())
    assert [n.text for n in document.numbers()] == ["84.1", "80.9"]
    assert document.numbers()[0].start == text.index("84.1")
    assert not document.issues


@pytest.mark.parametrize(
    "source",
    [
        "Value **8**4.1.",
        "Value -**84.1**.",
        "Value &#56;4.1.",
        "Value 84.1&#37;.",
        "Value 84\u200b1.",
        "Value 84\u202e1.",
        "Value 84\x00.1.",
        "Value 84\u0338.",
        "<span hidden>Result 84.1</span>",
        "Text <i>84.1</i>.",
        "<div hidden>\n\nValue 84.1\n\n</div>\n",
        "<span hidden>\n\nValue 84.1\n\n</span>\n",
        "Value 84.1\n\n<style>p { display: none }</style>\n",
        "Value `84.1`.",
        "Value `{python} 84.1`.",
        "Value $84.1$.",
        "Value \\(84.1\\).",
        "Value [84.1]{.content-hidden}.",
        "Value [84.1][^note].",
        "Value [@paper2026, p. 84].",
        "Value ~~84.1~~.",
        "{{< include 'result84.1.qmd' >}}",
        "![84.1](figure.png)",
        "::: {.content-hidden}\nValue 84.1\n:::\n",
        "::: {.content-visible}\nValue 84.1\n",
        "---\ntitle: Value 84.1\n---\n",
        "```{python}\nvalue = 84.1\n```\n",
        "```\nvalue = 84.1\n",
        "    value = 84.1\n",
        "$$\n\n84.1\n\n$$\n",
        "\\[\n\n84.1\n\n\\]\n",
        "\\begin{equation}\n\n84.1\n\n\\end{equation}\n",
        "> ::: {.hidden}\n>\n> Value 84.1\n>\n> :::\n",
        "- ::: {.hidden}\n\n  Value 84.1\n\n  :::\n",
        "+--------+--------+\n| Method | Score  |\n+--------+--------+\n"
        "| A      | 84.1   |\n+--------+--------+\n",
        "Method  Score\n------  -----\nA       84.1\n",
        "More at https://example.org/84.1.",
        "See <https://example.org/84.1>.",
    ],
)
def test_unsupported_or_transformed_numbers_are_never_candidates(source):
    document = MarkdownDocument("p.qmd", source.encode(), "quarto")
    assert not document.numbers()
    assert document.issues


def test_front_matter_and_fenced_divs_do_not_hide_later_static_prose():
    source = (
        "---\ntitle: Study 2026\n---\n\n::: {.hidden}\nValue 88.7\n:::\n"
        "\n# Results\n\nScore 84.1.\n"
    )
    document = MarkdownDocument("p.qmd", source.encode(), "quarto")
    assert [n.text for n in document.numbers()] == ["84.1"]
    assert document.numbers()[0].line == 11
    assert {i["code"] for i in document.issues} == {"MARKDOWN_METADATA", "MARKDOWN_DYNAMIC"}


def test_table_reordering_keeps_row_identity_and_changed_headers_require_repair():
    source = "| Method | Score |\n| --- | ---: |\n| A | **84.1** |\n| B | 80.9 |\n"
    document = MarkdownDocument("p.md", source.encode())
    span = document.numbers()[0]
    anchor = document.anchor_for_span(span)
    assert anchor.table.row_prefix == ["A"]
    changed = source.replace("| A | **84.1** |\n| B | 80.9 |", "| B | 80.9 |\n| A | **81.2** |")
    resolved = MarkdownDocument("p.md", changed.encode()).locate(anchor)
    assert resolved.text == "81.2" and resolved.line == 4
    assert resolved.locator["cell"] == 2
    with pytest.raises(PaperDeltaError, match=".*") as failed:
        MarkdownDocument("p.md", changed.replace("Score", "Other").encode()).locate(anchor)
    assert failed.value.code == "ANCHOR_MISSING"


@pytest.mark.parametrize(
    "row", ["| A | 84.1 | extra |", "| A |", "| A | `84.1` |", "| A | <span>84.1</span> |"]
)
def test_ragged_or_nonliteral_cells_cannot_be_used_as_regular_table(row):
    text = "| Method | Score |\n| --- | --- |\n" + row + "\n"
    document = MarkdownDocument("p.md", text.encode())
    assert not document.numbers()
    assert any(i["code"] == "MARKDOWN_TABLE" for i in document.issues)


def static_project(tmp_path, extension="md", *, table=False):
    project = Project(tmp_path)
    file = "paper." + extension
    text = (
        "# Abstract\n\nOur accuracy is **84.1%**.\n"
        if not table
        else "| Method | Accuracy |\n| --- | --- |\n| Ours | 84.1% |\n"
    )
    project.write(file, text.encode())
    project.write("results.csv", b"model,score\nOurs,0.841\n")
    init_project(project, file, ["results.csv"])
    value = load_config(project)[0].model_dump()
    value["sources"] = {
        "results": {
            "path": "results.csv",
            "format": "csv",
            "primary_key": ["model"],
            "columns": {"model": "string", "score": "decimal"},
        }
    }
    value["metrics"] = {
        "accuracy": {
            "source": "results",
            "field": "score",
            "where": {"model": "Ours"},
            "unit": "fraction",
        }
    }
    project.write("paperdelta.yaml", config_text(Config.model_validate(value)).encode())
    return project, file


def bind_accuracy(project, file, name="accuracy_text"):
    candidate = next(
        c for c in scan_project(project)["candidates"] if c["file"] == file and c["text"] == "84.1"
    )
    draft = builder.add_occurrences(
        project,
        builder.start_draft(project),
        metric="accuracy",
        candidate_ids=[candidate["candidate_id"]],
        names=[name],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale="Reviewed literal source position and explicit experiment identity.",
    )
    proposal = builder.finalize_draft(project, draft)
    accept_bindings(project, proposal, ["occurrences:" + name])


@pytest.mark.parametrize("extension", ["md", "qmd"])
@pytest.mark.parametrize("table", [False, True])
def test_full_bind_check_change_snapshot_and_read_only_source(tmp_path, extension, table):
    project, file = static_project(tmp_path, extension, table=table)
    original = project.read(file)
    bind_accuracy(project, file)
    before = check_project(tmp_path)
    assert before["exit_code"] == 0 and before["report_schema_version"] == 8
    assert before["occurrences"]["accuracy_text"]["status"] == "pass"
    StoredReport.model_validate(before)
    old = deepcopy(before)
    old["report_schema_version"] = 7
    with pytest.raises(ValidationError):
        StoredReport.model_validate(old)
    create_snapshot(project, "first", before)
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    report = check_project(tmp_path, baseline=read_snapshot(project, "first"))
    state = report["occurrences"]["accuracy_text"]
    assert state["status"] == "mismatch" and state["location"]["text"] == "84.1%"
    assert state["expected"] == "80.9%"
    with pytest.raises(PaperDeltaError) as failed:
        create_patch(project, report, ["accuracy_text"])
    assert failed.value.code == "DOCUMENT_READ_ONLY"
    for language in ("en", "zh-CN"):
        with language_context(language):
            assert file in text_report(report)
            assert "80.9%" in html_report(report)
    assert project.read(file) == original
    project.write(file, original.replace(b"84.1", b"80.9"))
    assert check_project(tmp_path)["occurrences"]["accuracy_text"]["status"] == "pass"


@pytest.mark.parametrize("extension", ["md", "qmd"])
def test_explicit_pdf_export_shares_metric_and_detects_stale_output(tmp_path, extension):
    from test_manuscripts import source_bytes

    project, file = static_project(tmp_path, extension)
    bind_accuracy(project, file)
    project.write("export.pdf", source_bytes("pdf", "84.1"))
    preview = change_manuscripts(project, action="add", file="export.pdf", export_of=file)
    assert preview["status"] == "preview"
    assert not load_config(project)[0].paper.companions
    change_manuscripts(project, action="add", file="export.pdf", export_of=file, accept=True)
    bind_accuracy(project, "export.pdf", "pdf_text")
    assert check_project(tmp_path)["exports"][0]["status"] == "aligned"
    original_pdf = project.read("export.pdf")
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    project.write(file, project.read(file).replace(b"84.1", b"80.9"))
    report = check_project(tmp_path)
    assert report["exports"][0]["status"] == "stale"
    assert report["occurrences"]["accuracy_text"]["status"] == "pass"
    assert project.read("export.pdf") == original_pdf


def test_adding_static_companion_requires_and_previews_schema_upgrade(project):
    project = Project(project)
    project.write("appendix.qmd", b"Additional accuracy 84.1%.\n")
    preview = change_manuscripts(project, action="add", file="appendix.qmd")
    assert preview["after"]["schema_version"] == 8
    assert load_config(project)[0].schema_version < 8
    accepted = change_manuscripts(project, action="add", file="appendix.qmd", accept=True)
    assert accepted["backup"] and load_config(project)[0].schema_version == 8


def test_abstract_scope_has_real_source_positions_and_does_not_hide_accepted_checks(tmp_path):
    project, file = static_project(tmp_path)
    bind_accuracy(project, file)
    project.write(file, project.read(file) + b"\n# Results\n\nAnother result 80.9.\n")
    value = change_scope(project, action="set", regions=["abstract"], accept=True)
    assert len(value["preview"]["coverage"]["outside_scope_numbers"]) == 1
    assert value["preview"]["occurrences"]["accuracy_text"]["status"] == "pass"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Abstract\n========\n\nScore 84.1.\n", ["84.1"]),
        ("Score 84.1  \nthen 80.9.\n", ["84.1", "80.9"]),
        ("# Score 84.1 ###\n", ["84.1"]),
        ("> Score 84.1\n> then 80.9.\n", ["84.1", "80.9"]),
        ("2. Score 84.1\n   then 80.9.\n", ["84.1", "80.9"]),
        ("See [score 84.1][result].\n\n[result]: https://example.org/2026\n", ["84.1"]),
        # These asterisks are literal under CommonMark, not a split emphasis span.
        ("Value 84**.1**.\n", ["84", ".1"]),
    ],
)
def test_supported_commonmark_structures_have_literal_source_locations(text, expected):
    document = MarkdownDocument("paper.md", text.encode())
    assert [span.text for span in document.numbers()] == expected
    assert not document.issues
    for span in document.numbers():
        assert document.raw[span.byte_start : span.byte_end].decode() == span.text


def test_numeric_header_boundary_is_syntax_not_inferred_from_cell_values():
    text = "| Model | 95% interval |\n| --- | --- |\n| A | **84.1** |\n| B | _80.9_ |\n"
    document = MarkdownDocument("p.md", text.encode())
    anchor = document.anchor_for_span(next(n for n in document.numbers() if n.text == "84.1"))
    assert anchor.table.header_rows == 1
    assert anchor.table.headers == ["Model & 95% interval"]
    assert document.locate(anchor).text == "84.1"


def test_duplicate_source_blocks_require_review_instead_of_first_match():
    document = MarkdownDocument("p.md", b"Score 84.1.\n\nScore 84.1.\n")
    with pytest.raises(PaperDeltaError) as failed:
        document.anchor_for_span(document.numbers()[0])
    assert failed.value.code == "ANCHOR_AMBIGUOUS"


def test_dynamic_code_and_include_have_no_file_or_process_side_effect(tmp_path, monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("Static reading attempted to execute a process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    source = (
        "```{python}\nfrom pathlib import Path\nPath('sentinel').write_text('84.1')\n```\n\n"
        "{{< include remote84.1.qmd >}}\n\nOur result is 80.9.\n"
    )
    document = MarkdownDocument("p.qmd", source.encode(), "quarto")
    assert [n.text for n in document.numbers()] == ["80.9"]
    assert not (tmp_path / "sentinel").exists()


@pytest.mark.parametrize("extension", ["md", "qmd"])
@pytest.mark.parametrize("table", [False, True])
def test_statistics_bind_to_one_contiguous_literal_display(tmp_path, extension, table):
    from test_statistics import CONTRACT

    project = Project(tmp_path)
    file = "paper." + extension
    display = "82.00 ± 1.58 (n = 5)"
    source = (
        f"| Model | Accuracy |\n| --- | --- |\n| method | {display} |\n"
        if table
        else f"# Abstract\n\nAccuracy: **{display}**.\n"
    )
    project.write(file, source.encode())
    project.write(
        "runs.tsv",
        (
            "model\tseed\taccuracy\n" + "".join(f"method\t{i}\t{79 + i}\n" for i in range(1, 6))
        ).encode(),
    )
    init_project(project, file, ["runs.tsv"])
    draft = builder.add_source(
        project,
        builder.start_draft(project),
        name="runs",
        path="runs.tsv",
        format="tsv",
        primary_key=["model", "seed"],
        columns={"model": "string", "seed": "integer", "accuracy": "decimal"},
    )
    draft = builder.add_metric(
        project,
        draft,
        name="accuracy",
        source="runs",
        field="accuracy",
        unit="percent",
        reduce="statistics",
        where={"model": "method"},
        expected_count=5,
        expected_seeds=["1", "2", "3", "4", "5"],
        statistics=CONTRACT,
    )
    candidates = scan_project(project)["candidates"]
    draft = builder.add_occurrences(
        project,
        draft,
        metric="accuracy",
        candidate_ids=[c["candidate_id"] for c in candidates],
        names=["result"],
        display_kind="decimal",
        places=2,
        percent_symbol=False,
        statistics={"component": "mean_sd", "show_n": True},
        rationale="Explicit five seed sample mean, sample standard deviation and count.",
    )
    accept_bindings(project, builder.finalize_draft(project, draft), ["occurrences:result"])
    before = check_project(tmp_path)
    assert before["occurrences"]["result"]["location"]["text"] == display
    assert before["coverage"]["pass"] == 1 and not before["coverage"]["unbound_numbers"]
    project.write("runs.tsv", project.read("runs.tsv").replace(b"\t84\n", b"\t85\n"))
    after = check_project(tmp_path)
    assert after["occurrences"]["result"]["status"] == "mismatch"
    assert project.read(file) == source.encode()


@pytest.mark.parametrize(
    "raw",
    [b"\xff", b"x" * (4 * 1024 * 1024 + 1), b"x" * 65537],
    ids=["invalid-utf8", "file-too-large", "line-too-long"],
)
def test_invalid_encoding_and_bounded_input_are_rejected(raw):
    with pytest.raises(PaperDeltaError) as failed:
        MarkdownDocument("p.md", raw)
    assert failed.value.code in {"ENCODING", "DOCUMENT_LIMIT"}
