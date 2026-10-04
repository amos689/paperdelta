"""Native evidence uses existing exact metrics, drafts and versioned reports."""

import io
import zipfile
from decimal import Decimal

import pytest
from test_xlsx_evidence import book

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Source
from paperdelta.onboarding import accept_bindings, init_project, inspect_proposal, scan_project
from paperdelta.records import StoredReport
from paperdelta.storage import Project
from paperdelta.studio import StudioSession


def project_and_source(tmp_path, kind, raw=None):
    project = Project(tmp_path)
    project.write("paper.tex", b"Accuracy: 80.0\\%.\n")
    raw = raw or (
        book()
        if kind == "xlsx"
        else b"model\taccuracy\n001\t0.80000000000000000000000000001\n1\t0.801\n"
    )
    project.write("results." + kind, raw)
    init_project(project, "paper.tex", ["results." + kind])
    draft = builder.start_draft(project)
    draft = builder.add_source(
        project,
        draft,
        name="results",
        path="results." + kind,
        format=kind,
        columns={"model": "string", "accuracy": "decimal"},
        primary_key=["model"],
        **({"sheet": "Results", "cell_range": "A1:B3"} if kind == "xlsx" else {}),
    )
    return project, draft


@pytest.mark.parametrize("kind", ["tsv", "xlsx"])
def test_native_table_to_accepted_binding_and_exact_schema5_report(tmp_path, kind):
    project, draft = project_and_source(tmp_path, kind)
    draft = builder.add_metric(
        project,
        draft,
        name="accuracy",
        source="results",
        field="accuracy",
        unit="fraction",
        reduce="unique",
        where={"model": "001"},
    )
    scan = scan_project(project)
    candidate = next(item for item in scan["candidates"] if item["text"] == "80.0")
    draft = builder.add_occurrences(
        project,
        draft,
        metric="accuracy",
        candidate_ids=[candidate["candidate_id"]],
        names=["abstract"],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale="The explicit text model ID 001 and accuracy column.",
    )
    proposal = builder.finalize_draft(project, draft)
    _, _, report = inspect_proposal(project, proposal)
    assert report["report_schema_version"] == 5
    assert report["metrics"]["accuracy"]["value"] == "0.80000000000000000000000000001"
    assert report["coverage"]["pass"] == 1
    StoredReport.model_validate(report)
    accept_bindings(project, proposal, ["occurrences:abstract"])
    assert load_config(project)[0].schema_version == 5
    assert check_project(project.root)["coverage"]["pass"] == 1
    evidence = report["metrics"]["accuracy"]["evidence"][0]
    assert evidence["records"][0]["key"] == {"model": "001"} and evidence["format"] == kind
    if kind == "xlsx":
        assert evidence["locations"][0] == {
            "key": {"model": "001"},
            "sheet": "Results",
            "row": 2,
            "cell": "B2",
        }
    else:
        assert evidence["locations"][0]["line"] == 2

    # A version-5 report must retain the existing preview/apply/recover workflow.
    from paperdelta.manuscripts import change_manuscripts
    from paperdelta.patches import apply_patch, create_patch, recover_transaction

    project.write("supplement.tex", b"Additional explanation.\n")
    added = change_manuscripts(project, action="add", file="supplement.tex", accept=True)
    assert added["after"]["schema_version"] == 5
    project.write("paper.tex", b"Accuracy: 79.0\\%.\n")
    before = project.read("paper.tex")
    patch = create_patch(project, check_project(project.root), ["abstract"])
    applied = apply_patch(project, patch)
    assert applied["report"]["occurrences"]["abstract"]["status"] == "pass"
    assert project.read("paper.tex") == b"Accuracy: 80.0\\%.\n"
    recover_transaction(project, applied["transaction_id"], write=True)
    assert project.read("paper.tex") == before


def test_missing_measurement_does_not_make_another_models_result_unknown(tmp_path):
    with zipfile.ZipFile(io.BytesIO(book())) as archive:
        data = (
            archive.read("xl/worksheets/sheet1.xml")
            .decode()
            .split("<sheetData>")[1]
            .split("</sheetData>")[0]
        )
    data = data.replace('<c r="B3"><v>8.01E-1</v></c>', "")
    project, draft = project_and_source(tmp_path, "xlsx", book(data=data))
    draft = builder.add_metric(
        project,
        draft,
        name="available",
        source="results",
        field="accuracy",
        unit="fraction",
        reduce="unique",
        where={"model": "001"},
    )
    _, config = builder.resume_draft(project, draft)
    from paperdelta.sources import EvidenceStore

    assert EvidenceStore(project, config).resolve("available").quantity.value == Decimal(
        "0.80000000000000000000000000001"
    )
    with pytest.raises(PaperDeltaError):
        builder.add_metric(
            project,
            draft,
            name="missing",
            source="results",
            field="accuracy",
            unit="fraction",
            reduce="unique",
            where={"model": "1"},
        )


def test_formatted_numeric_identifiers_are_not_treated_as_text(tmp_path):
    with zipfile.ZipFile(io.BytesIO(book())) as archive:
        data = (
            archive.read("xl/worksheets/sheet1.xml")
            .decode()
            .split("<sheetData>")[1]
            .split("</sheetData>")[0]
        )
    data = data.replace('<c r="A2" t="inlineStr"><is><t>001</t></is></c>', '<c r="A2"><v>1</v></c>')
    with pytest.raises(PaperDeltaError) as error:
        project_and_source(tmp_path, "xlsx", book(data=data))
    assert error.value.code == "XLSX_IDENTITY"


def test_new_optional_source_fields_do_not_rewrite_legacy_identity():
    old = {
        "path": "data.csv",
        "format": "csv",
        "primary_key": ["model"],
        "columns": {"model": "string", "value": "decimal"},
    }
    assert Source.model_validate(old).model_dump() == old


@pytest.mark.parametrize("kind", ["tsv", "xlsx"])
def test_studio_explicit_preview_pagination_and_source_staging(tmp_path, kind):
    project, _ = project_and_source(tmp_path, kind)
    session = StudioSession(project)

    def call(action, payload):
        return session.execute(
            {
                "action": action,
                "payload": payload,
                "revision": session.revision,
                "language": "zh-CN",
            }
        )

    parameters = {"path": "results." + kind, "offset": 1}
    if kind == "xlsx":
        before = call("source-preview", parameters)["source"]
        assert before["needs_selection"] and before["sheets"] == ["Results"]
        parameters.update(sheet="Results", cell_range="A1:B3")
    preview = call("source-preview", parameters)["source"]
    assert preview["sample"][0]["model"] == "1" and len(preview["sample"]) == 1
    assert preview["offset"] == 1
    state = call(
        "source",
        {
            **{k: v for k, v in parameters.items() if k != "offset"},
            "name": "native",
            "format": kind,
            "source_hash": preview["hash"],
            "columns": {"model": "string", "accuracy": "decimal"},
            "primary_key": ["model"],
        },
    )["state"]
    assert state["sources"]["native"]["format"] == kind


def test_missing_numeric_tsv_value_remains_missing_instead_of_zero(tmp_path):
    from paperdelta.batch import create_catalog, inspect_catalog

    project, draft = project_and_source(tmp_path, "tsv", b"model\taccuracy\n001\t0.8\n1\t\n")
    request = {
        "source": "results",
        "fields": ["accuracy"],
        "group_by": ["model"],
        "unit": "fraction",
        "reduce": "unique",
        "expected_count": 1,
    }
    choices = inspect_catalog(project, create_catalog(project, draft, request))["choices"]
    assert [item["status"] for item in choices] == ["ready", "unknown"]
