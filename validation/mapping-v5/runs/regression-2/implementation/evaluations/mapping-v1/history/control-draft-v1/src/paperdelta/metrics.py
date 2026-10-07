"""Decimal arithmetic and explicit rendering; no model-generated arithmetic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext

from paperdelta.errors import PaperDeltaError
from paperdelta.models import Display, Unit
from paperdelta.storage import decimal_value

NUMBER = r"[+\-−]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?"
NUMBER_PATTERN = re.compile(rf"(?<![\w.]){NUMBER}(?!\w|\.\d)")


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: Unit


def comparable(left: Quantity, right: Quantity) -> tuple[Decimal, Decimal]:
    with localcontext() as context:
        context.prec = 4096
        if left.unit == right.unit:
            return left.value, right.value
        if {left.unit, right.unit} <= {"fraction", "percent"}:
            return (
                left.value / 100 if left.unit == "percent" else left.value,
                right.value / 100 if right.unit == "percent" else right.value,
            )
    raise PaperDeltaError("UNIT_MISMATCH", f"Cannot compare {left.unit} with {right.unit}")


def derive(op: str, left: Quantity, right: Quantity) -> Quantity:
    a, b = comparable(left, right)
    with localcontext() as context:
        context.prec = max(
            50,
            len(a.as_tuple().digits)
            + len(b.as_tuple().digits)
            + abs(a.adjusted() - b.adjusted())
            + 10,
        )
        if op == "percentage_point_difference":
            if left.unit not in ("fraction", "percent"):
                raise PaperDeltaError("UNIT_MISMATCH", "Percentage points require proportions")
            # comparable keeps identical percent units in their original scale.
            scale = 1 if left.unit == right.unit == "percent" else 100
            return Quantity((a - b) * scale, "percentage_point")
        if op == "difference":
            unit = "fraction" if left.unit != right.unit else left.unit
            return Quantity(a - b, unit)
        if b == 0:
            raise PaperDeltaError("ZERO_DENOMINATOR", f"Cannot calculate {op} with zero baseline")
        if op == "ratio":
            return Quantity(a / b, "ratio")
        if op == "relative_change_percent":
            return Quantity((a - b) / b * 100, "percent")
    raise PaperDeltaError("UNKNOWN_OPERATION", f"Unsupported operation: {op}")


def render(quantity: Quantity, display: Display, rounding: str) -> str:
    with localcontext() as context:
        context.prec = 4096
        context.rounding = ROUND_HALF_UP if rounding == "half_up" else ROUND_HALF_EVEN
        value = quantity.value
        suffix = ""
        if display.kind == "percent":
            if quantity.unit not in ("fraction", "percent"):
                raise PaperDeltaError(
                    "UNIT_MISMATCH", "Percent display requires fraction or percent"
                )
            if quantity.unit == "fraction":
                value *= 100
            suffix = r"\%" if display.percent_symbol else ""
        if display.kind == "scientific":
            return f"{value:.{display.places}E}"
        places = 0 if display.kind == "integer" else display.places
        rounded = value.quantize(Decimal(1).scaleb(-places))
        if rounded.is_zero():
            rounded = abs(rounded)
        return f"{rounded:.{places}f}{suffix}"


def parse_display(text: str) -> tuple[Decimal, bool]:
    compact = re.sub(r"\s|\\[,;! ]|~", "", text)
    percent = compact.endswith(r"\%")
    if percent:
        compact = compact[:-2]
    if re.fullmatch(NUMBER, compact) is None:
        raise PaperDeltaError("UNSUPPORTED_DISPLAY", f"Cannot interpret numeric span {text!r}")
    return decimal_value(compact.replace(",", "").replace("−", "-")), percent


def display_matches(actual: str, expected: str) -> bool:
    return parse_display(actual) == parse_display(expected)
