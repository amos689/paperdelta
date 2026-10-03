import pytest

from paperdelta.errors import PaperDeltaError
from paperdelta.latex import PaperIndex, TexDocument
from paperdelta.models import Anchor, Paper
from paperdelta.storage import Project


def test_byte_spans_preserve_utf8_bom_and_windows_newlines():
    raw = "\ufeff中文\r\nAccuracy: 84.1\\%.\r\n".encode("utf-8")
    doc = TexDocument("论文.tex", raw)
    # Use exact anchor because a '.' suffix would also occur inside decimal notation.
    span = doc.locate(Anchor(exact=r"84.1\%"))
    assert raw[span.byte_start : span.byte_end] == b"84.1\\%"
    assert span.line == 2
    assert span.column == 11
    replacement = raw[: span.byte_start] + b"80.9\\%" + raw[span.byte_end :]
    assert replacement.startswith(b"\xef\xbb\xbf") and replacement.count(b"\r\n") == 2


def test_comments_verbatim_and_structural_labels_are_not_results():
    source = "% 99\nValue 84.1. \\label{result2026}\n\\begin{verbatim}\n123\n\\end{verbatim}"
    doc = TexDocument("paper.tex", source.encode())
    assert [span.text for span in doc.numbers()] == ["84.1"]
    with pytest.raises(PaperDeltaError, match="not in supported"):
        doc.locate(Anchor(exact="99"))


def test_unknown_macro_requires_explicit_literal_contract():
    source = rb"Result: \score{84.1} percent."
    unknown = TexDocument("paper.tex", source)
    with pytest.raises(PaperDeltaError):
        unknown.locate(Anchor(exact="84.1"))
    declared = TexDocument("paper.tex", source, {"score": 1})
    assert declared.locate(Anchor(exact="84.1")).text == "84.1"


def test_caption_percent_and_nested_formatting():
    source = rb"\caption{Accuracy 84.1\%.} \textbf{\emph{12.5}}"
    doc = TexDocument("paper.tex", source)
    assert not doc.issues
    assert doc.locate(Anchor(exact=r"84.1\%")).text == r"84.1\%"
    assert [span.text for span in doc.numbers()] == ["84.1", "12.5"]


@pytest.mark.parametrize("macro", ["citep", "citealp", "citealt", "citeauthor", "citeyear"])
def test_citation_page_equation_and_year_are_not_reported_results(macro):
    # LEGWORK's development-paper source exposed an Eq. 5.14 citation as a candidate.
    doc = TexDocument("paper.tex", ("\\" + macro + "[][Eq.~5.14]{Peters1964} SNR 4.49.").encode())
    assert [span.text for span in doc.numbers()] == ["4.49"]


def test_conditionals_are_unknown_without_running_tex():
    doc = TexDocument("paper.tex", rb"\ifdefined\foo Value 84.1\else Value 80.9\fi")
    with pytest.raises(PaperDeltaError):
        doc.locate(Anchor(exact="84.1"))
    assert any(issue["code"] == "DYNAMIC_TEX" for issue in doc.issues)


def test_malformed_math_is_unknown_instead_of_an_uncaught_parser_exception():
    doc = TexDocument("paper.tex", rb"\begin{document} Score $0.78 \end{document}")
    assert any(issue["code"] == "LATEX_PARSE" for issue in doc.issues)
    assert doc.numbers() == []
    with pytest.raises(PaperDeltaError) as error:
        doc.locate(Anchor(exact="0.78"))
    assert error.value.code == "UNSUPPORTED_SPAN"


def test_include_cycle_is_detected(tmp_path):
    (tmp_path / "a.tex").write_text(r"\input{b}")
    (tmp_path / "b.tex").write_text(r"\input{a}")
    with pytest.raises(PaperDeltaError, match="cycle"):
        PaperIndex(Project(tmp_path), Paper(entry="a.tex"))


def test_include_cannot_read_outside_project(tmp_path):
    (tmp_path / "a.tex").write_text(r"\input{../secret}")
    with pytest.raises(PaperDeltaError, match="leaves the project"):
        PaperIndex(Project(tmp_path), Paper(entry="a.tex"))


@pytest.mark.parametrize("anchor", [Anchor(exact="84"), Anchor(prefix="Score: ", suffix=".")])
def test_numeric_binding_cannot_select_only_part_of_a_decimal(anchor):
    doc = TexDocument("paper.tex", b"Score: 84.12.")
    with pytest.raises(PaperDeltaError) as error:
        doc.validate_numeric_span(doc.locate(anchor))
    assert error.value.code == "PARTIAL_NUMBER"
