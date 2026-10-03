from paperdelta.agent import AgentSession
from paperdelta.analysis import check_project
from paperdelta.storage import Project, parse_json


def test_agent_check_and_explanation_share_core_result(project, change_results):
    change_results(project)
    session = AgentSession(Project(project))
    report = session.check_project()
    core = check_project(project)
    assert report["coverage"] == core["coverage"] and report["exit_code"] == core["exit_code"]
    explanation = session.explain_finding("claim:main_comparison/CLAIM_FALSE")
    assert explanation["state"]["status"] == "mismatch"
    assert explanation["metrics"]["ours"]["value"] == "0.809"


def test_agent_patch_proposal_never_writes_paper_or_approval(project, change_results):
    change_results(project, new=("0.843", "0.845", "0.847"))
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    result = AgentSession(Project(project)).propose_patch()
    assert len(parse_json(result["patch_json"])["changes"]) == 4
    after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert before == after
