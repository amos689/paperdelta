from decimal import Decimal

import pytest

from paperdelta.errors import PaperDeltaError
from paperdelta.metrics import Quantity, comparable, derive, display_matches, render
from paperdelta.models import Display
from paperdelta.storage import decimal_value


def quantity(value, unit="fraction"):
    return Quantity(Decimal(value), unit)


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (quantity("0.841"), quantity("0.810"), "3.100"),
        (quantity("84.1", "percent"), quantity("81.0", "percent"), "3.1"),
        (quantity("84.1", "percent"), quantity("0.810"), "3.100"),
        (quantity("0.809"), quantity("0.810"), "-0.100"),
    ],
)
def test_percentage_points_have_the_right_scale(left, right, expected):
    result = derive("percentage_point_difference", left, right)
    assert result.value == Decimal(expected)
    assert result.unit == "percentage_point"


def test_relative_percent_is_not_percentage_points():
    result = derive("relative_change_percent", quantity("0.84"), quantity("0.80"))
    assert result.value == Decimal("5")
    assert derive("percentage_point_difference", quantity("0.84"), quantity("0.80")).value == 4


@pytest.mark.parametrize(
    "number,expected", [("0.9535", r"95.4\%"), ("0.9534", r"95.3\%"), ("-0.0001", r"0.0\%")]
)
def test_display_rounding_is_explicit(number, expected):
    assert render(quantity(number), Display(kind="percent", places=1), "half_up") == expected


def test_rounding_policy_changes_only_the_declared_boundary():
    assert render(quantity("0.9525"), Display(kind="percent"), "half_up") == r"95.3\%"
    assert render(quantity("0.9525"), Display(kind="percent"), "half_even") == r"95.2\%"


def test_allowed_tex_spacing_and_trailing_zeros():
    assert display_matches(r"96.50\,\%", r"96.5\%")
    assert not display_matches("96.5", r"96.5\%")
    assert display_matches("1,234.00", "1234")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", True, 0.1, "1e99999"])
def test_nonfinite_and_rounded_binary_inputs_are_rejected(value):
    with pytest.raises(PaperDeltaError):
        decimal_value(value)


def test_zero_baseline_and_incompatible_units():
    with pytest.raises(PaperDeltaError, match="zero baseline"):
        derive("ratio", quantity("1"), quantity("0"))
    with pytest.raises(PaperDeltaError, match="Cannot compare"):
        comparable(quantity("3", "count"), quantity("3", "percentage_point"))


def test_difference_does_not_drop_small_terms():
    result = derive("difference", quantity("1e100", "scalar"), quantity("1", "scalar"))
    assert result.value == Decimal("9" * 100)
