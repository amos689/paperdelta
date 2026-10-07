"""Explicit statistical display grammar and independently selected source spans."""

from __future__ import annotations

import re
from decimal import Decimal

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.metrics import NUMBER, NUMBER_PATTERN, Quantity, display_matches, render
from paperdelta.models import Display
from paperdelta.storage import decimal_value


def pattern(display):
    """Capture numeric components only; no arbitrary surrounding prose is accepted."""
    statistical = display.statistics
    number = rf"({NUMBER})"
    percent = r"(?:\\%|%)" if display.kind == "percent" and display.percent_symbol else ""
    term = number + r"\s*" + percent
    component = statistical.component
    if component in {"mean_sd", "mean_se"}:
        body = term + r"\s*(?:±|\\pm)\s*" + term
    elif component in {"ci", "mean_ci"}:
        body = r"\[\s*" + term + r"\s*,\s*" + term + r"\s*\]"
        if component == "mean_ci":
            body = term + r"\s*" + body
    else:
        body = term
    if statistical.show_n:
        body += r"\s*\(\s*n\s*=\s*([0-9]+)\s*\)"
    return re.compile(body)


def _plain(text):
    return re.sub(r"\\[,;! ]|~", " ", text)


def parse_statistical(text, display):
    match = pattern(display).fullmatch(_plain(text).strip())
    if match is None:
        raise PaperDeltaError("STATISTICAL_DISPLAY", msg("statistics.grammar"))
    return tuple(
        decimal_value(value.replace(",", "").replace("−", "-")) for value in match.groups()
    )


def render_result(result, display, rounding):
    if display.statistics is None:
        return render(result.quantity, display, rounding)
    summary = result.statistics
    if summary is None:
        raise PaperDeltaError("STATISTICAL_DISPLAY", msg("statistics.explicit_display"))
    specification = display.statistics
    component = specification.component
    scalar = Display(
        kind=display.kind, places=display.places, percent_symbol=display.percent_symbol
    )
    spread = (
        scalar.model_copy(update={"places": specification.spread_places})
        if specification.spread_places is not None
        else scalar
    )

    def value(key, formatting=scalar):
        if key == "n":
            return str(summary["n"])
        if key == "confidence_level":
            return render(
                Quantity(Decimal(summary["confidence_interval"]["level"]), "fraction"),
                formatting,
                rounding,
            )
        raw = (
            summary["confidence_interval"][key.removeprefix("ci_")]
            if key.startswith("ci_")
            else summary[key]
        )
        return render(Quantity(Decimal(raw), result.quantity.unit), formatting, rounding)

    if component in {"mean_sd", "mean_se"}:
        text = value("mean") + r" \pm " + value(component.removeprefix("mean_"), spread)
    elif component in {"ci", "mean_ci"}:
        text = "[" + value("ci_lower", spread) + ", " + value("ci_upper", spread) + "]"
        if component == "mean_ci":
            text = value("mean") + " " + text
    else:
        text = value(component)
    if specification.show_n:
        text += f" (n = {summary['n']})"
    return text


def matches(actual, expected, display):
    if display.statistics is None:
        return display_matches(actual, expected)
    return parse_statistical(actual, display) == parse_statistical(expected, display)


def validate_span(document, span, display):
    if display.statistics is None or not display.statistics.compound:
        document.validate_numeric_span(span)
        return
    if not document.checkable(span.start, span.end):
        raise PaperDeltaError("STATISTICAL_SPAN", msg("statistics.span"))
    parse_statistical(span.text, display)
    for token in NUMBER_PATTERN.finditer(document.text):
        if (
            token.start() < span.end
            and span.start < token.end()
            and not (span.start <= token.start() < token.end() <= span.end)
        ):
            raise PaperDeltaError("PARTIAL_NUMBER", msg("error.PARTIAL_NUMBER"))


def compound_span(document, choices, display):
    """The author selects every numeric component, including n when present."""
    choices = sorted(choices, key=lambda item: item["start"])
    if not choices or len({item["file"] for item in choices}) != 1:
        raise PaperDeltaError("STATISTICAL_SELECTION", msg("statistics.selection"))
    first, last = choices[0]["start"], choices[-1]["end"]
    if last - first > 900:
        raise PaperDeltaError("STATISTICAL_SELECTION", msg("statistics.selection"))
    expected = {(item["start"], item["end"]) for item in choices}
    # Only punctuation immediately adjoining the explicitly chosen numbers can
    # expand the span. The selected source text must match the full grammar.
    low, high = max(0, first - 12), min(len(document.text), last + 12)
    found = []
    for match in pattern(display).finditer(document.text[low:high]):
        a, b = low + match.start(), low + match.end()
        selected = {
            (item.start, item.end)
            for item in document.numbers()
            if a <= item.start and item.end <= b
        }
        if selected == expected:
            span = document.span(a, b)
            validate_span(document, span, display)
            found.append(span)
    if len(found) != 1:
        raise PaperDeltaError("STATISTICAL_SELECTION", msg("statistics.selection"))
    return found[0]


def cell_span(document, bounds, statistical, percent_symbol):
    """A table anchor binds the entire declared compound, never a convenient number."""
    a, b = bounds
    text = document.text[a:b]
    left = len(text) - len(text.lstrip())
    right = len(text.rstrip())
    # Literal LaTeX math delimiters are outside the bound value.
    if text[left:right].startswith("$") and text[left:right].endswith("$"):
        left += 1
        right -= 1
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
    display = Display(
        kind="percent" if percent_symbol else "decimal",
        percent_symbol=percent_symbol,
        statistics=statistical,
    )
    span = document.span(a + left, a + right)
    validate_span(document, span, display)
    return span


def compound_from_start(document, choice, display):
    """Repair a declared compound by its selected first number, then preview it whole."""
    low, high = max(0, choice["start"] - 12), min(len(document.text), choice["start"] + 900)
    found = []
    for match in pattern(display).finditer(document.text[low:high]):
        a, b = low + match.start(), low + match.end()
        first = next((item for item in document.numbers() if a <= item.start < b), None)
        if first and (first.start, first.end) == (choice["start"], choice["end"]):
            span = document.span(a, b)
            validate_span(document, span, display)
            found.append(span)
    if len(found) != 1:
        raise PaperDeltaError("STATISTICAL_SELECTION", msg("statistics.repair_first"))
    return found[0]
