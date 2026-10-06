from paperdelta.source_advice import profile_summary, source_advice
from paperdelta.storage import Project


def test_advice_preserves_text_identity_and_decimal_precision_without_writing(tmp_path):
    project = Project(tmp_path)
    raw = (
        b"model,split,seed,accuracy\n001,test,1,0.800000000000000000000001\n"
        b"001,test,2,0.8\n1,test,1,0.8\n1,test,2,0.8\n"
    )
    project.write("results.csv", raw)
    advice = source_advice(project, "results.csv")
    assert advice["complete"] and advice["requires_confirmation"]
    assert advice["columns"]["model"]["type"] == "string"
    assert advice["columns"]["model"]["examples"] == ["001", "1"]
    assert advice["columns"]["accuracy"]["type"] == "decimal"
    assert advice["columns"]["accuracy"]["examples"][0] == "0.800000000000000000000001"
    assert advice["primary_keys"][0]["columns"] == ["model", "split", "seed"]
    assert advice["experiment"]["group_by"] == ["model"]
    assert advice["experiment"]["unit"] is None
    assert project.read("results.csv") == raw
    assert [p.name for p in tmp_path.iterdir()] == ["results.csv"]


def test_duplicate_identity_never_uses_different_measurements_as_primary_key(tmp_path):
    project = Project(tmp_path)
    project.write("results.csv", b"model,seed,score\nA,1,84\nA,1,85\n")
    advice = source_advice(project, "results.csv")
    assert not advice["primary_keys"] and advice["conflicts"]
    assert advice["experiment"]["result_fields"] == ["score"]


def test_partial_sample_has_no_uniqueness_claim():
    advice = profile_summary(
        {"columns": ["id", "score"], "record_count": 2, "sample": [{"id": "A", "score": "84"}]}
    )
    assert not advice["complete"] and not advice["primary_keys"]
    assert advice["conflicts"]


def test_excel_numeric_storage_and_mixed_identity_are_distinct():
    numeric = profile_summary(
        {
            "columns": ["id", "score"],
            "record_count": 1,
            "sample": [{"id": "1", "score": "84"}],
            "storage_kinds": {"id": ["number"], "score": ["number"]},
        }
    )
    assert numeric["columns"]["id"]["type"] == "integer"
    assert numeric["can_apply"]
    mixed = profile_summary(
        {
            "columns": ["id"],
            "record_count": 2,
            "sample": [{"id": "001"}, {"id": "1"}],
            "storage_kinds": {"id": ["number", "string"]},
        }
    )
    assert mixed["columns"]["id"]["type"] == "string"
    assert not mixed["can_apply"] and mixed["conflicts"]


def test_studio_and_agent_advice_share_read_only_contract(tmp_path):
    from paperdelta.agent import AgentSession
    from paperdelta.studio import StudioSession

    project = Project(tmp_path)
    project.write("results.csv", b"model,seed,score\nA,1,84\nA,2,85\n")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    studio = StudioSession(project)
    en = studio.execute(
        {
            "action": "source-advice",
            "payload": {"path": "results.csv"},
            "revision": studio.revision,
            "language": "en",
        }
    )
    zh = studio.execute(
        {
            "action": "source-advice",
            "payload": {"path": "results.csv"},
            "revision": studio.revision,
            "language": "zh-CN",
        }
    )
    agent = AgentSession(project).source_advice("results.csv")
    assert en["input_hash"] == zh["input_hash"] == agent["input_hash"]
    assert en["notice"] != zh["notice"]
    assert en["primary_keys"][0]["columns"] == agent["primary_keys"][0]["columns"]
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


def test_missing_and_mixed_values_do_not_propose_numeric_coercion(tmp_path):
    project = Project(tmp_path)
    project.write("results.tsv", b"id\tseed\tscore\nA\t01\t84\nB\t02\t\nC\t03\tnot reported\n")
    advice = source_advice(project, "results.tsv")
    assert advice["columns"]["seed"]["type"] == "string"
    assert advice["columns"]["score"]["type"] == "string"
    assert advice["columns"]["score"]["missing_observed"] == 1
    assert advice["conflicts"]
