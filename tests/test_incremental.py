"""A fresh full check is the oracle for every reused report, including positions."""

import io
import os
import zipfile
from copy import deepcopy
from decimal import ROUND_DOWN, ROUND_UP, localcontext

import pytest

from paperdelta.analysis import check_project, check_stored_project
from paperdelta.config import config_text, load_config
from paperdelta.demo import create_demo
from paperdelta.documents import PaperIndex
from paperdelta.experiment_imports import import_evidence
from paperdelta.i18n import language_context
from paperdelta.incremental import MIB, CheckCache, retained_size
from paperdelta.models import Config, Source
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.sources import EvidenceStore
from paperdelta.storage import Project, json_text
from paperdelta.watch import Watcher


def normalized(report):
    result = deepcopy(report)
    result.pop("created_at", None)
    result.pop("watch", None)
    return result


def equivalent(root, cache, baseline=None):
    full = check_project(root, baseline=baseline)
    reused = check_project(root, baseline=baseline, cache=cache)
    assert normalized(reused) == normalized(full)
    return reused


@pytest.mark.parametrize("format", ["latex", "docx", "pdf", "markdown", "quarto"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_all_formats_cold_warm_changes_deleted_inputs_and_private_copies(
    tmp_path, format, language
):
    with language_context(language):
        create_demo(Project(tmp_path), "demo", "baseline", format)
        root, cache = tmp_path / "demo", CheckCache()
        first = equivalent(root, cache)
        assert first["exit_code"] == 0
        equivalent(root, cache)
        assert cache.stats()["counts"]["document.hit"] > 0
        assert cache.stats()["counts"]["source_metric.hit"] > 0
        # Public report dictionaries must not alias a private reusable result.
        next(iter(first["metrics"].values()))["evidence"][0]["locations"].clear()
        next(iter(first["occurrences"].values()))["location"]["file"] = "forged"
        equivalent(root, cache)
        store = Project(root)
        config, _ = load_config(store)
        source = store.path(next(iter(config.sources.values())).path)
        original, metadata = source.read_bytes(), source.stat()
        source.write_bytes(original.replace(b"0.841", b"0.809"))
        os.utime(source, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        assert source.stat().st_size == len(original)
        assert equivalent(root, cache)["exit_code"] != 0
        source.unlink()
        assert equivalent(root, cache)["exit_code"] == 2
        source.write_bytes(original)
        assert equivalent(root, cache)["exit_code"] == 0
        paper = store.path(config.paper.entry)
        manuscript = paper.read_bytes()
        paper.write_bytes(b"broken manuscript")
        assert equivalent(root, cache)["exit_code"] != 0
        paper.unlink()
        assert equivalent(root, cache)["exit_code"] == 2
        paper.write_bytes(manuscript)
        assert equivalent(root, cache)["exit_code"] == 0


def test_reordered_csv_updates_all_derived_evidence_locations(project):
    cache = CheckCache()
    before = equivalent(project, cache)
    source = project / "results/metrics.csv"
    lines = source.read_bytes().splitlines(keepends=True)
    source.write_bytes(b"".join([lines[0], *reversed(lines[1:])]))
    after = equivalent(project, cache)
    derived = [name for name, item in before["metrics"].items() if item.get("dependencies")]
    assert derived
    for name in derived:
        assert before["metrics"][name]["value"] == after["metrics"][name]["value"]
        assert before["metrics"][name]["evidence"] != after["metrics"][name]["evidence"]


def test_config_selectors_units_anchors_scope_and_macros_invalidate(project):
    cache, store = CheckCache(), Project(project)
    equivalent(project, cache)
    original = store.read("paperdelta.yaml")
    config, _ = load_config(store)
    metric = next(value for value in config.metrics.values() if hasattr(value, "source"))
    metric.where["model"] = "missing-experiment"
    store.write("paperdelta.yaml", config_text(config).encode())
    assert equivalent(project, cache)["exit_code"] == 2
    store.write("paperdelta.yaml", original)
    config, _ = load_config(store)
    metric = next(value for value in config.metrics.values() if hasattr(value, "source"))
    metric.unit = "scalar"
    store.write("paperdelta.yaml", config_text(config).encode())
    assert equivalent(project, cache)["exit_code"] != 0
    store.write("paperdelta.yaml", original)
    config, _ = load_config(store)
    config.occurrences.clear()
    config.paper.macros["ignored"] = 1
    store.write("paperdelta.yaml", config_text(config).encode())
    assert equivalent(project, cache)["occurrences"] == {}
    store.write("paperdelta.yaml", b"sources: [")
    assert equivalent(project, cache)["exit_code"] == 2
    store.write("paperdelta.yaml", original)
    assert equivalent(project, cache)["exit_code"] == 0


def test_include_graph_rebuilt_when_a_missing_file_appears_or_becomes_ambiguous(project):
    cache, store = CheckCache(), Project(project)
    equivalent(project, cache)
    main = store.read("paper/main.tex")
    store.write(
        "paper/main.tex", main.replace(b"\\end{document}", b"\\input{sub/new}\n\\end{document}")
    )
    assert equivalent(project, cache)["exit_code"] == 2
    store.write("paper/sub/new.tex", b"Discussion.\\input{leaf}\n")
    assert equivalent(project, cache)["exit_code"] == 2
    store.write("paper/sub/leaf.tex", b"Details.\n")
    assert equivalent(project, cache)["exit_code"] == 0
    store.write("paper/leaf.tex", b"Conflicting include.\n")
    report = equivalent(project, cache)
    assert report["exit_code"] == 2
    assert any(item["rule"] == "INCLUDE_PATH" for item in report["diagnostics"])


def test_baseline_and_author_review_are_read_fresh(project, change_results):
    cache, store = CheckCache(), Project(project)
    original = equivalent(project, cache)
    create_snapshot(store, "before", original)
    baseline = read_snapshot(store, "before")
    claim, state = next(iter(original["claims"].items()))
    review = record_review(
        store, claim, state["state_fingerprint"], "author", "Reviewed.", attest_reviewed=True
    )
    assert equivalent(project, cache, baseline)["claims"][claim]["review"] == "reviewed"
    store.path(review).unlink()
    assert equivalent(project, cache, baseline)["claims"][claim]["review"] == "unreviewed"
    change_results(project)
    report = equivalent(project, cache, baseline)
    assert report["changes"] and report["exit_code"] == 1


def test_parser_identity_language_and_decimal_context_do_not_reuse_wrong_results(project):
    cache = CheckCache(identity="engine-1")
    equivalent(project, cache)
    first = cache.stats()["counts"]["document.miss"]
    cache.identity = "engine-2"
    equivalent(project, cache)
    assert cache.stats()["counts"]["document.miss"] > first
    for language in ("zh-CN", "en"):
        with language_context(language):
            equivalent(project, cache)
    for rounding in (ROUND_DOWN, ROUND_UP):
        with localcontext() as context:
            context.rounding = rounding
            equivalent(project, cache)


def test_cached_parses_do_not_hide_read_boundary_or_changes_during_check(project, change_results):
    cache = CheckCache()
    equivalent(project, cache)

    class ChangingProject(Project):
        def read(self, relative, limit=32 * MIB):
            result = super().read(relative, limit)
            if relative == "results/metrics.csv" and not getattr(self, "changed", False):
                self.changed = True
                change_results(self.root)
            return result

    report = check_stored_project(ChangingProject(project, check_cache=cache))
    assert report["exit_code"] == 2
    assert any(item["rule"] == "INPUT_CHANGED" for item in report["diagnostics"])
    assert equivalent(project, cache)["exit_code"] == 1


def test_cache_eviction_and_oversized_inputs_preserve_results_and_bounds(project):
    cache, store = CheckCache(max_bytes=MIB, max_entries=3), Project(project)
    original = store.read("paper/main.tex")
    for index in range(20):
        store.write("paper/main.tex", original + f"\n% revision {index}\n".encode())
        equivalent(project, cache)
        stats = cache.stats()
        assert stats["retained_bytes"] <= stats["max_bytes"]
        assert stats["entries"] <= stats["max_entries"]
    assert cache.stats()["counts"]["evictions"] > 0
    store.write("paper/main.tex", original + b"\n% " + b"comment " * 50000)
    equivalent(project, cache)
    assert cache.stats()["counts"]["document.bypass"] > 0
    zero = CheckCache(max_bytes=0, max_entries=0)
    equivalent(project, zero)
    assert zero.stats()["entries"] == zero.stats()["retained_bytes"] == 0


def test_word_xml_memory_is_charged_and_returned_documents_are_isolated(tmp_path):
    create_demo(Project(tmp_path), "demo", "baseline", "docx")
    cache = CheckCache()
    store = Project(tmp_path / "demo", check_cache=cache)
    config, _ = load_config(store)
    first = PaperIndex(store, config.paper)
    document = first.document(config.paper.entry)
    node = next(iter(document.style_nodes.values()))
    assert retained_size(node, 16 * MIB) > 10000
    node.clear()
    document.blocks.clear()
    second = PaperIndex(store, config.paper).document(config.paper.entry)
    fresh = PaperIndex(Project(store.root), config.paper).document(config.paper.entry)
    assert second.numbers() == fresh.numbers()
    assert cache.stats()["counts"]["document.hit"] == 1


def test_watch_can_disable_reuse_without_changing_its_results(project, change_results):
    cached = Watcher(Project(project), debounce=0, write_output=False)
    full = Watcher(Project(project), debounce=0, write_output=False, use_cache=False)
    assert full.cache is None
    assert normalized(cached.step(0)) == normalized(full.step(0))
    change_results(project)
    assert normalized(cached.step(1)) == normalized(full.step(1))


@pytest.mark.parametrize("format", ["csv", "tsv", "xlsx", "json", "records"])
def test_each_evidence_format_keeps_exact_values_positions_and_provenance(tmp_path, format):
    from test_xlsx_evidence import book

    project = Project(tmp_path, check_cache=CheckCache())
    path = "results." + ("csv" if format == "records" else format)
    source = {"path": path, "format": "csv" if format == "records" else format}
    if format == "json":
        raw = b'{"accuracy": 0.80000000000000000000000000001}'
        metric = {"source": "results", "field": "/accuracy", "unit": "fraction"}
    else:
        raw = (
            book() if format == "xlsx" else b"model,accuracy\n001,0.80000000000000000000000000001\n"
        )
        if format == "tsv":
            raw = raw.replace(b",", b"\t")
        source.update(columns={"model": "string", "accuracy": "decimal"}, primary_key=["model"])
        if format == "xlsx":
            source.update(sheet="Results", cell_range="A1:B3")
        metric = {
            "source": "results",
            "field": "accuracy",
            "where": {"model": "001"},
            "unit": "fraction",
        }
    project.write(path, raw)
    input_source = source.copy()
    if format == "records":
        imported = import_evidence(
            project,
            {"provider": "file", "origin": path, "source": source},
            "export.pdevidence.json",
        )
        source = imported["source"]
        path, raw = source["path"], project.read(source["path"])
    config = Config(
        schema_version=5,
        paper={"entry": "paper.tex"},
        sources={"results": source},
        metrics={"accuracy": metric},
    )

    def compare():
        full = EvidenceStore(Project(tmp_path), config).resolve("accuracy")
        cached = EvidenceStore(project, config).resolve("accuracy")
        assert full.to_dict() == cached.to_dict()
        return cached

    compare()
    warm = compare()
    assert warm.to_dict()["value"] == "0.80000000000000000000000000001"
    if format == "xlsx":
        stream = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(stream, "w") as changed:
            for item in original.infolist():
                contents = original.read(item.filename).replace(
                    b"0.80000000000000000000000000001", b"0.70000000000000000000000000001"
                )
                changed.writestr(item, contents)
        project.write(path, stream.getvalue())
    elif format == "records":
        # Re-export to preserve the export integrity contract, not forge its hash.
        project.write("results.csv", project.read("results.csv").replace(b"0.800", b"0.700"))
        imported = import_evidence(
            project,
            {"provider": "file", "origin": "results.csv", "source": input_source},
            "changed-export.pdevidence.json",
        )
        config.sources["results"] = Source.model_validate(imported["source"])
    else:
        project.write(path, raw.replace(b"0.800", b"0.700"))
    assert compare().quantity != warm.quantity
    assert project.check_cache.stats()["counts"]["source_metric.hit"] == 1


def test_only_dependent_metrics_recompute_when_one_source_changes(tmp_path):
    store, cache = Project(tmp_path), CheckCache()
    store.write("paper.tex", b"A: 1.0. B: 2.0. Difference: -1.0.\n")
    store.write("a.json", b'{"score":1.0}')
    store.write("b.json", b'{"score":2.0}')
    store.write(
        "paperdelta.yaml",
        json_text(
            {
                "schema_version": 1,
                "paper": {"entry": "paper.tex"},
                "sources": {key: {"format": "json", "path": key + ".json"} for key in ["a", "b"]},
                "metrics": {
                    "a": {"source": "a", "field": "/score", "unit": "scalar"},
                    "b": {"source": "b", "field": "/score", "unit": "scalar"},
                    "difference": {"op": "difference", "args": ["a", "b"]},
                },
            }
        ).encode(),
    )
    equivalent(tmp_path, cache)
    before = cache.stats()["counts"]
    store.write("a.json", b'{"score":3.0}')
    report = equivalent(tmp_path, cache)
    after = cache.stats()["counts"]
    assert report["metrics"]["difference"]["value"] == "1.0"
    assert after["source_metric.miss"] - before["source_metric.miss"] == 1
    assert after["source_metric.hit"] == 1
    assert after["derived_metric.miss"] - before["derived_metric.miss"] == 1


@pytest.mark.parametrize("cached", [False, True])
def test_source_aliases_cannot_hide_a_mid_check_file_change(project, cached):
    store = Project(project)
    config, _ = load_config(store)
    name = next(iter(config.sources))
    config.sources["alias"] = config.sources[name].model_copy(deep=True)
    metric = next(
        value for value in config.metrics.values() if getattr(value, "source", None) == name
    )
    config.metrics["alias_metric"] = metric.model_copy(update={"source": "alias"}, deep=True)
    store.write("paperdelta.yaml", config_text(config).encode())
    path = config.sources[name].path
    cache = CheckCache() if cached else None
    equivalent(project, cache)

    class ChangingAliases(Project):
        def read(self, relative, limit=32 * MIB):
            raw = super().read(relative, limit)
            if relative == path and not getattr(self, "changed", False):
                self.changed = True
                self.write(path, raw + b"\n")  # Same values, different input snapshot.
            return raw

    report = check_stored_project(ChangingAliases(project, check_cache=cache))
    assert report["exit_code"] == 2
    assert any(item["rule"] == "INPUT_CHANGED" for item in report["diagnostics"])
