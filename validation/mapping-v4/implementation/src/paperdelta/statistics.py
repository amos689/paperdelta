"""Declared descriptive statistics and two-sided Student-t intervals.

Rational sums/variance precede bounded high-precision decimal square roots.
The interval is an approximation under an author-declared sampling assumption;
it is never a significance test or a claim about the independence of the runs.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
from functools import lru_cache

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg


@lru_cache(maxsize=128)
def t_critical(df: int, level: str, precision: int = 80) -> str:
    from mpmath import mp

    # A private context avoids cross-session global precision changes in Studio.
    context = mp.clone()
    context.dps = precision + 20
    target = 1 - context.mpf(level)
    degrees = context.mpf(df)

    def tail(value):
        x = degrees / (degrees + value * value)
        return context.betainc(degrees / 2, context.mpf("0.5"), 0, x, regularized=True)

    try:
        left, right = context.mpf(0), context.mpf(1)
        for _ in range(16):
            if tail(right) <= target:
                break
            right *= 2
        else:
            raise ValueError("quantile bracket")
        for _ in range(4 * precision + 32):
            middle = (left + right) / 2
            if tail(middle) > target:
                left = middle
            else:
                right = middle
        result = (left + right) / 2
        if abs(tail(result) - target) > context.power(10, -precision):
            raise ValueError("quantile residual")
        return context.nstr(result, precision)
    except (ArithmeticError, ValueError) as exc:
        raise PaperDeltaError("STATISTICS_NUMERICS", msg("statistics.numerics")) from exc


def summarize(numbers: list[Decimal], contract) -> dict:
    if not numbers or len(numbers) <= contract.ddof:
        raise PaperDeltaError("STATISTICS_COUNT", msg("statistics.expected"))
    # These additional bounds apply only to the new statistical calculation.
    # Legacy scalar and exact decimal workflows retain their existing limits.
    if any(
        not value.is_finite()
        or len(value.as_tuple().digits) > 100
        or abs(value.as_tuple().exponent) > 200
        or abs(value.adjusted()) > 200
        for value in numbers
    ):
        raise PaperDeltaError("STATISTICS_LIMIT", msg("statistics.limit"))
    count = len(numbers)
    observations = [Fraction(value) for value in numbers]
    mean = sum(observations, Fraction(0)) / count
    variance = sum(((value - mean) ** 2 for value in observations), Fraction(0)) / (
        count - contract.ddof
    )
    magnitude = max(0, *(value.adjusted() for value in numbers))
    precision = max(80, magnitude + 60)
    with localcontext() as context:
        context.prec = precision

        def decimal(value):
            return Decimal(value.numerator) / Decimal(value.denominator)

        average = decimal(mean)
        sd = decimal(variance).sqrt()
        se = sd / Decimal(count).sqrt()
        result = {
            "mean": str(average),
            "sd": str(sd),
            "se": str(se),
            "n": count,
            "ddof": contract.ddof,
            "unit_of_analysis": contract.unit_of_analysis,
            "arithmetic": "rational-moments-decimal-sqrt-v1",
            "precision_digits": precision,
        }
        if contract.confidence_interval is not None:
            from mpmath import __version__ as mpmath_version

            declaration = contract.confidence_interval
            critical = Decimal(t_critical(count - 1, declaration.level, precision))
            margin = critical * se
            result["confidence_interval"] = {
                **declaration.model_dump(),
                "df": count - 1,
                "critical_value": str(critical),
                "lower": str(average - margin),
                "upper": str(average + margin),
                "quantile_engine": "mpmath-" + mpmath_version,
            }
    return result
