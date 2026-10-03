import json
import re
from copy import deepcopy
from html.parser import HTMLParser

from paperdelta.analysis import check_project
from paperdelta.i18n import language_context, msg
from paperdelta.reports import html_report
from paperdelta.storage import json_text


class Structure(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_html_localizes_first_party_messages_preserving_evidence_and_report(
    project, change_results
):
    change_results(project)
    report = check_project(project)
    original = deepcopy(report)
    with language_context("en"):
        english = html_report(report)
    with language_context("zh-CN"):
        chinese = html_report(report)
    assert report == original
    assert '<html lang="zh-CN">' in chinese
    assert "检查发现" in chinese and "所有严重程度" in chinese
    assert "Our method outperforms Baseline" in chinese
    assert "Our method outperforms Baseline" in english
    for html in (english, chinese):
        elements = Structure(html).elements
        table = json.loads(re.search(r'id="report-locales">(.*?)</script>', html).group(1))
        for _, attributes in elements:
            for key, value in attributes.items():
                if key.startswith("data-i18n"):
                    assert set(table[value]) == {"en", "zh-CN"}
        ids = [attrs["id"] for _, attrs in elements if "id" in attrs]
        assert len(ids) == len(set(ids))
        for _, attrs in elements:
            if "data-finding-link" in attrs:
                assert attrs["href"][1:] in ids
        assert not any("src" in attrs for _, attrs in elements)
    # Historical v1 reports still render; original stored messages are retained.
    assert html_report(json.loads(json_text(report)))


def test_script_and_attributes_escape_translated_parameters_and_user_text(project):
    report = check_project(project)
    payload = '</script><img src=x onerror="alert(1)">'
    report["diagnostics"].append(
        {
            "subject": payload,
            "severity": "unknown",
            "rule": "TEST",
            "message": msg("error.SOURCE_FORMAT", extra=payload),
        }
    )
    report["baseline"] = {"name": payload}
    html = html_report(report)
    assert payload not in html
    elements = Structure(html).elements
    assert [tag for tag, _ in elements].count("script") == 2
    assert "img" not in [tag for tag, _ in elements]
    table = json.loads(re.search(r'id="report-locales">(.*?)</script>', html).group(1))
    assert any(payload in text for values in table.values() for text in values.values())


def test_coverage_groups_preserve_repeated_unsupported_regions(project):
    path = project / "paper/abstract.tex"
    path.write_bytes(path.read_bytes() + b"\n\\mystery{1} \\mystery{2}\n")
    report = check_project(project)
    assert len(report["coverage"]["unsupported"]) == 2
    with language_context("zh-CN"):
        html = html_report(report)
    assert "不支持的区域（2）" in html
    assert "出现 2 次" in html
    assert "UNSUPPORTED_MACRO" in html
    articles = [attrs for tag, attrs in Structure(html).elements if tag == "article"]
    assert len(articles) == len(report["diagnostics"])
