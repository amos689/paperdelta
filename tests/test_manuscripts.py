"""Shared evidence never implies an undeclared relationship between manuscripts."""

import io

import pytest
from docx import Document
from reportlab.pdfgen.canvas import Canvas

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.cli import main
from paperdelta.config import config_text, load_config
from paperdelta.documents import PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.manuscripts import change_manuscripts
from paperdelta.models import Config
from paperdelta.onboarding import accept_bindings, scan_project
from paperdelta.pdf_previews import pdf_previews
from paperdelta.reports import html_report, text_report, write_reports
from paperdelta.storage import Project, parse_json
from paperdelta.watch import Watcher


def source_bytes(kind, value):
    text = f"Our accuracy is {value}%."
    if kind == "tex":
        return ("\\begin{document}" + text.replace("%", "\\%") + "\\end{document}").encode()
    output = io.BytesIO()
    if kind == "docx":
        document = Document()
        document.add_paragraph(text)
        document.save(output)
    else:
        canvas = Canvas(output, pagesize=(600, 800), invariant=1)
        canvas.drawString(40, 720, text)
        canvas.save()
    return output.getvalue()


def shared_project(tmp_path, source="docx", *, declared=True):
    project = Project(tmp_path)
    project.write(f"source.{source}", source_bytes(source, "84.1"))
    project.write("export.pdf", source_bytes("pdf", "84.1"))
    project.write("results.csv", b"model,score\nOurs,0.841\n")
    value = {
        "schema_version": 4,
        "paper": {
            "entry": f"source.{source}",
            "companions": [
                {"entry": "export.pdf", **({"export_of": f"source.{source}"} if declared else {})}
            ],
        },
        "sources": {
            "results": {
                "path": "results.csv",
                "format": "csv",
                "primary_key": ["model"],
                "columns": {"model": "string", "score": "decimal"},
            }
        },
        "metrics": {
            "accuracy": {
                "source": "results",
                "field": "score",
                "where": {"model": "Ours"},
                "unit": "fraction",
            }
        },
    }
    config = Config.model_validate(value)
    project.write("paperdelta.yaml", config_text(config).encode())
    draft = builder.start_draft(project)
    candidates = scan_project(project)["candidates"]
    draft = builder.add_occurrences(
        project,
        draft,
        metric="accuracy",
        candidate_ids=[item["candidate_id"] for item in candidates],
        names=["export" if item["file"] == "export.pdf" else "source" for item in candidates],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale="Explicit source accuracy and its exported result.",
    )
    proposal = builder.finalize_draft(project, draft)
    accept_bindings(project, proposal, ["occurrences:source", "occurrences:export"])
    return project


@pytest.mark.parametrize("kind", ["tex", "docx"])
def test_corrected_source_and_stale_pdf_are_distinguished(tmp_path, kind):
    project = shared_project(tmp_path, kind)
    assert check_project(tmp_path)["exports"][0]["status"] == "aligned"
    original_pdf = project.read("export.pdf")
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    assert check_project(tmp_path)["exports"][0]["status"] == "source_outdated"
    project.write(f"source.{kind}", source_bytes(kind, "80.9"))
    report = check_project(tmp_path)
    assert report["exit_code"] == 1
    assert report["exports"][0]["status"] == "stale"
    assert report["occurrences"]["source"]["status"] == "pass"
    assert report["occurrences"]["export"]["status"] == "mismatch"
    assert any(item["rule"] == "EXPORT_STALE" for item in report["diagnostics"])
    assert any(item["kind"] == "reexport_pdf" for item in report["actions"])
    assert not any(item["kind"] == "update_document" for item in report["actions"])
    for language in ("en", "zh-CN"):
        with language_context(language):
            text_report(report)
            assert (
                "PDF export is stale" if language == "en" else "PDF 导出结果已过期"
            ) in html_report(report)
    assert project.read("export.pdf") == original_pdf
    project.write("export.pdf", source_bytes("pdf", "80.9"))
    assert check_project(tmp_path)["exports"][0]["status"] == "aligned"


def test_equal_numbers_do_not_invent_export_relationships(tmp_path):
    project = shared_project(tmp_path, declared=False)
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    project.write("source.docx", source_bytes("docx", "80.9"))
    report = check_project(tmp_path)
    assert not report.get("exports")
    assert "EXPORT_STALE" not in [item["rule"] for item in report["diagnostics"]]


def test_missing_bindings_and_failed_source_cannot_certify_export(tmp_path):
    project = shared_project(tmp_path)
    config, _ = load_config(project)
    value = config.model_dump()
    del value["occurrences"]["source"]
    project.write("paperdelta.yaml", config_text(Config.model_validate(value)).encode())
    report = check_project(tmp_path)
    assert report["exports"][0]["status"] == "unknown" and report["exit_code"] == 2
    assert any(item["rule"] == "EXPORT_UNCHECKED" for item in report["diagnostics"])
    project.write("paperdelta.yaml", config_text(config).encode())
    project.write("source.docx", b"PK partial Word save")
    watcher = Watcher(project, debounce=0)
    assert watcher.step(0)["exit_code"] == 2
    assert "export.pdf" in watcher.inputs()
    project.write("source.docx", source_bytes("docx", "84.1"))
    assert watcher.step(1)["exit_code"] == 0
    watcher.stop()


def test_companion_and_region_changes_are_previewed_backed_up_and_read_only(tmp_path):
    project = shared_project(tmp_path)
    project.write("supplement.docx", source_bytes("docx", "84.1"))
    original = project.read("paperdelta.yaml")
    result = change_manuscripts(project, action="add", file="supplement.docx")
    assert result["status"] == "preview" and project.read("paperdelta.yaml") == original
    result = change_manuscripts(project, action="add", file="supplement.docx", accept=True)
    assert project.read(result["backup"]) == original
    assert len(PaperIndex(project, load_config(project)[0].paper).documents) == 3
    change_manuscripts(project, action="remove", file="supplement.docx", accept=True)
    with pytest.raises(PaperDeltaError) as error:
        change_manuscripts(project, action="remove", file="export.pdf", accept=True)
    assert error.value.code == "MANUSCRIPT_REFERENCED"
    pdf_bytes = project.read("export.pdf")
    region = {"name": "abstract", "page": 1, "bbox": [30, 60, 400, 110], "kind": "abstract"}
    result = change_manuscripts(
        project, action="region-add", file="export.pdf", region=region, accept=True
    )
    assert result["preview"]["occurrences"]["export"]["status"] == "unknown"
    assert project.read("export.pdf") == pdf_bytes
    change_manuscripts(
        project, action="region-remove", file="export.pdf", name="abstract", accept=True
    )
    assert check_project(tmp_path)["exit_code"] == 0


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_new_cli_uses_declared_pages_and_bilingual_help(tmp_path, capsys, language):
    project = shared_project(tmp_path)
    base = ["--lang", language, "-C", str(tmp_path)]
    assert main([*base, "pdf", "inspect", "--file", "export.pdf", "--format", "json"]) == 0
    result = parse_json(capsys.readouterr().out)
    assert result["pages"] == [{"page": 1, "bbox": [0, 0, 600, 800]}]
    assert result["numbers"][0]["parser"] == result["parser"]
    assert main([*base, "manuscript", "list", "--format", "json"]) == 0
    assert len(parse_json(capsys.readouterr().out)["manuscripts"]) == 2
    config = project.read("paperdelta.yaml")
    assert (
        main(
            [
                *base,
                "pdf",
                "region-add",
                "--file",
                "export.pdf",
                "--name",
                "abstract",
                "--page",
                "1",
                "--bbox",
                "20",
                "40",
                "400",
                "110",
                "--kind",
                "abstract",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert parse_json(capsys.readouterr().out)["status"] == "preview"
    assert project.read("paperdelta.yaml") == config


def test_original_page_preview_is_offline_hash_bound_and_bounded(tmp_path):
    project = shared_project(tmp_path)
    report = check_project(tmp_path)
    before = project.read("export.pdf")
    preview = pdf_previews(project, report)
    assert len(preview["pages"]) == 1
    page = preview["pages"][0]
    assert page["hash"] == report["input_hashes"]["export.pdf"]
    assert page["image"].startswith("data:image/png;base64,")
    assert (
        page["boxes"][0]["bbox"] == report["occurrences"]["export"]["location"]["locator"]["bbox"]
    )
    html = html_report(report, previews=preview)
    assert '<svg viewBox="0 0 600 800"' in html
    assert "pdf-jump" in html and "img-src data:" in html
    assert project.read("export.pdf") == before
    for limits in ({"max_pages": 0}, {"max_pixels": 1}, {"max_bytes": 1}):
        limited = pdf_previews(project, report, **limits)
        assert not any("image" in page for page in limited["pages"])
        assert limited["omitted"] or limited["pages"][0]["message"]
    project.write("export.pdf", source_bytes("pdf", "80.9"))
    stale = pdf_previews(project, report)
    assert "image" not in stale["pages"][0]
    assert "changed" in str(stale["pages"][0]["message"])
    write_reports(project, "build/stale", report)
    assert "data:image/png;base64," not in project.text("build/stale/report.html")[0]


def test_configuration_commit_rechecks_the_inspected_inputs(tmp_path, monkeypatch):
    import paperdelta.manuscripts as module

    project = shared_project(tmp_path)
    project.write("supplement.docx", source_bytes("docx", "84.1"))
    original = project.read("paperdelta.yaml")
    check = module.check_configuration

    def race(*args, **kwargs):
        result = check(*args, **kwargs)
        project.write("supplement.docx", source_bytes("docx", "80.9"))
        return result

    monkeypatch.setattr(module, "check_configuration", race)
    with pytest.raises(PaperDeltaError) as error:
        change_manuscripts(project, action="add", file="supplement.docx", accept=True)
    assert error.value.code == "STALE_PROPOSAL"
    assert project.read("paperdelta.yaml") == original
