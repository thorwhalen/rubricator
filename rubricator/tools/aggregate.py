"""Tool 14, ``aggregate_assertions``: one value per cell by an order statistic -- or an honest refusal to give one.

ADR-0011. A cell holds a set of assertions -- repeats of one rater, several
raters, both -- and a reader often wants one value per cell. The reduction is an
**order statistic**, lower median by default, so the result is always a level
some assertion actually chose: never 3.5 on a 1-5 ordinal scale. A mean is
refused at this boundary, naming the level of measurement, because a mean of
ordinal levels is a number no rater could have given. (A trimmed *range* is a
percentile statistic and legal; a trimmed *mean* is still a mean.)

## The polarised cell, and why it gets no point value

For a cell split between 2 and 4 at p = .45 each, the median lands on 3 -- a
level almost nobody chose -- with probability rising from .10 at k = 1 to .36 at
k = 21. More repeats make the point estimate *monotonically more misleading*:
sampling cannot rescue a bimodal cell, it can only reveal that the cell is
bimodal. So a polarised cell is reduced to ``null`` and marked ``contested``,
and what it carries instead is its level multiset and its modes. A caller that
needs a number anyway passes ``allow_contested_reduction`` and still gets the
marker.

**Polarised is comparanda's rule, mirrored, not a second one** (ADR-0011: the
condition is derived from the multiset by the companion repository, and this
repository does not spell it differently). From comparanda's ``cellShape``: two
or more occupied levels, separated somewhere by at least ``polarised_gap`` empty
levels, with no single dominant mode. ``n`` counts the values on the declared
levels; values off them are ignored, as there.

**Only scores that answer the criterion as it is now asked are reduced**
(ADR-0016). A score given under an earlier definition -- its ``criteriaVersion``
older than the criterion's ``definedInVersion`` -- answered another question:
counted beside the new ones it would make a stale 1 and a fresh 5 look like a
polarised cell. It is left out, and the summary says how many were, so the
re-scoring it calls for is visible (#195).

``contested`` is this tool's verdict about its own reduction -- a marker returned
to the caller, never a stored measure (ADR-0002 leaves the schema to the
companion). Today it is exactly ``polarised``; it is a separate field so that a
later reason a reduction is contested adds a condition, not a field.

## Levels of measurement

The reduction reads the measurement declared for the cell's measure -- the
criterion's ``measurements[measure]``, else its ``defaultMeasurement``, which is
comparanda's ``measurementFor``:

- **ordinal**: ``median`` is the lower median -- the average of two central
  levels is a mean of levels. ``lower-median``, ``min``, ``max`` as named.
- **interval / ratio**: ``median`` is the conventional median, which may average
  the two central values; there it is legal.
- **nominal**: no order exists, so nothing that needs one does either: ``reduced``,
  ``min``, ``max`` and ``span`` are ``null``, nothing is polarised, and the modes
  and the level counts carry the answer. Declared levels of a nominal scale are
  display order only.

An ordinal criterion that declares an integer ``range`` but no ``levels`` has its
steps derived from the range, so a bimodal cell there is still caught. Any other
criterion with no levels has no steps to measure a gap in and is never polarised;
its ``span`` is the numeric distance. Values a scale cannot take are not counted
in ``n``; they are counted in ``offScale``, so a dropped value is visible.

Determinism: order statistics over stored values. One store read, no write.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.criteria_versions import answers_an_older_definition
from rubricator.rules import live_assertions
from rubricator.store import AnalysisStore

__all__ = ["aggregate_assertions", "cell_shape", "REDUCTIONS"]

#: The order statistics this tool computes. A row per name, so a percentile
#: reduction (a trimmed range) is an addition here and in the frozen row.
REDUCTIONS: tuple[str, ...] = ("lower-median", "median", "min", "max")

DEFAULT_REDUCTION = "lower-median"

#: comparanda's default ``gap`` for ``cellShape``.
DEFAULT_POLARISED_GAP = 1

def _is_a_mean(reduction: Any) -> bool:
    """``mean``, ``Mean``, ``trimmed-mean``, ``geometric-mean``, ``average`` ..."""
    name = str(reduction).lower()
    return "mean" in name or "average" in name


def refuse_a_mean(store: AnalysisStore, arguments: Mapping[str, Any]) -> None:
    """Refuse a mean before anything else looks at the call, naming the level of measurement.

    Run by the surface ahead of the schema check (whose enum would only say "not
    one of"), and by the verb itself for a Python caller.
    """
    reduction = arguments.get("reduction")
    if reduction is not None and _is_a_mean(reduction):
        try:
            criteria = store.frame(arguments["analysis_id"])["criteria"]
        except (KeyError, TypeError, ValueError):
            criteria = []
        raise ValueError(_mean_refusal(str(reduction), criteria))


def aggregate_assertions(
    store: AnalysisStore,
    *,
    analysis_id: str,
    reduction: str = DEFAULT_REDUCTION,
    allow_contested_reduction: bool = False,
    polarised_gap: int = DEFAULT_POLARISED_GAP,
) -> dict[str, Any]:
    """Reduce every cell's live assertions to one value, or to an honest ``null``.

    At k = 1 this is a no-op: the one value is the reduction. A cell with no
    value on its scale -- only blanks -- reduces to ``null`` with ``n = 0``.
    Tombstoned rows and columns are left out: they are withdrawn, not scored.
    """
    refuse_a_mean(store, {"analysis_id": analysis_id, "reduction": reduction})
    if reduction not in REDUCTIONS:
        raise ValueError(
            f'refused: reduction "{reduction}" is not one of {", ".join(REDUCTIONS)}. Nothing was '
            "computed."
        )
    if isinstance(polarised_gap, bool) or not isinstance(polarised_gap, int) or polarised_gap < 0:
        raise ValueError(
            f"refused: polarised_gap={polarised_gap!r}. It is a whole number of empty levels, 0 or "
            "more."
        )
    from rubricator.tools.views import skipped_note

    document, skipped = store.read_skipping(analysis_id)
    live_alternatives = {a["id"] for a in document["alternatives"] if not a.get("tombstoned")}
    criteria = {c["id"]: c for c in document["criteria"] if not c.get("tombstoned")}
    rows = []
    older = 0
    for cell in sorted(
        document["cells"],
        key=lambda c: (c["alternativeId"], c["criterionId"], c.get("measure", "score")),
    ):
        criterion = criteria.get(cell["criterionId"])
        if criterion is None or cell["alternativeId"] not in live_alternatives:
            continue
        defined_in = criterion.get("definedInVersion")
        older += sum(
            answers_an_older_definition(a, defined_in)
            for a in live_assertions(cell) if a.get("value") is not None
        )
        rows.append(
            _reduce_cell(
                cell, _measurement_for(criterion, cell.get("measure", "score")),
                reduction=reduction, allow_contested=allow_contested_reduction, gap=polarised_gap,
                defined_in=defined_in,
            )
        )
    return {
        "analysisId": analysis_id,
        "reduction": reduction,
        "cells": rows,
        "skipped": skipped,
        "summary": _summary(rows, reduction, allow_contested_reduction, older=older)
        + skipped_note(skipped),
    }


def _measurement_for(criterion: Mapping[str, Any], measure: str) -> Mapping[str, Any]:
    """comparanda's ``measurementFor``: the measure's own declaration, else the default."""
    own = (criterion.get("measurements") or {}).get(measure)
    return own or criterion.get("defaultMeasurement") or {}


def _steps(measurement: Mapping[str, Any]) -> Sequence[Any] | None:
    """The declared levels, or an ordinal integer range's steps, or ``None``."""
    levels = measurement.get("levels")
    if levels is not None:
        return levels
    rng = measurement.get("range") or {}
    lo, hi = rng.get("min"), rng.get("max")
    if (
        measurement.get("level", "ordinal") == "ordinal"
        and all(isinstance(v, int) and not isinstance(v, bool) for v in (lo, hi))
        and lo <= hi
    ):
        return list(range(lo, hi + 1))
    return None


def _reduce_cell(
    cell: Mapping[str, Any], measurement: Mapping[str, Any], *, reduction: str,
    allow_contested: bool, gap: int, defined_in: str | None = None,
) -> dict[str, Any]:
    values = [
        a["value"] for a in live_assertions(cell)
        if a.get("value") is not None and not answers_an_older_definition(a, defined_in)
    ]
    level = measurement.get("level", "ordinal")
    shape = cell_shape(values, _steps(measurement), gap=gap, ordered=level != "nominal")
    contested = shape["polarised"]
    reduced = None
    if shape["ordered"] and (not contested or allow_contested):
        reduced = _order_statistic(shape["ordered"], reduction, level)
    return {
        "alternativeId": cell["alternativeId"],
        "criterionId": cell["criterionId"],
        "measure": cell.get("measure", "score"),
        "n": shape["n"],
        "reduced": reduced,
        "min": shape["min"],
        "max": shape["max"],
        "span": shape["span"],
        "modes": shape["modes"],
        "levels": shape["levels"],
        "offScale": shape["offScale"],
        "polarised": shape["polarised"],
        "contested": contested,
    }


def cell_shape(
    values: Sequence[Any],
    levels: Sequence[Any] | None,
    *,
    gap: int = DEFAULT_POLARISED_GAP,
    ordered: bool = True,
) -> dict[str, Any]:
    """The multiset, extremes, modes and polarisation of one cell's values.

    Mirrors comparanda's ``cellShape``. With declared ``levels`` the values are
    counted per level in level order, values off the levels are ignored, and
    ``span`` is in ordinal steps. Without them the distinct numeric values are
    the levels, ``span`` is the numeric distance, and nothing is polarised.
    ``ordered=False`` is a nominal scale: counts and modes only, nothing that
    needs an order.

    >>> s = cell_shape([2, 4, 2, 4], [1, 2, 3, 4, 5])
    >>> s["modes"], s["polarised"], s["span"]
    ([2, 4], True, 2)
    >>> cell_shape([2, 4, 4], [1, 2, 3, 4, 5])["polarised"]  # one dominant mode
    False
    >>> cell_shape([3, 4], [1, 2, 3, 4, 5])["polarised"]  # adjacent: no empty level between
    False
    """
    if levels is not None:
        counts = [sum(1 for v in values if _same(v, level)) for level in levels]
        occupied = [i for i, c in enumerate(counts) if c]
        values_in_order = [levels[i] for i in occupied for _ in range(counts[i])]
        widest = max((b - a - 1 for a, b in zip(occupied, occupied[1:])), default=0)
        multiset = [{"level": lvl, "count": c} for lvl, c in zip(levels, counts)]
        span = occupied[-1] - occupied[0] if occupied else 0
    else:
        numbers = sorted(
            v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
        )
        distinct = sorted(set(numbers))
        counts = [numbers.count(v) for v in distinct]
        occupied = list(range(len(distinct)))
        values_in_order = numbers
        widest = None
        multiset = [{"level": v, "count": c} for v, c in zip(distinct, counts)]
        span = distinct[-1] - distinct[0] if distinct else 0
    in_order = ordered
    ordered_values = values_in_order
    n = len(ordered_values)
    top = max(counts, default=0)
    modes = [m["level"] for m in multiset if n and m["count"] == top]
    return {
        "n": n,
        "offScale": len(values) - n,
        "ordered": ordered_values if in_order else [],
        "levels": multiset,
        "min": ordered_values[0] if ordered_values and in_order else None,
        "max": ordered_values[-1] if ordered_values and in_order else None,
        "span": span if in_order else None,
        "modes": modes,
        "polarised": in_order and widest is not None and len(occupied) >= 2 and widest >= gap
        and len(modes) != 1,
    }


def _order_statistic(ordered: Sequence[Any], reduction: str, level: str | None) -> Any:
    """``ordered`` is sorted by level order (or numerically, with no levels)."""
    k = len(ordered)
    if level == "nominal":
        return None
    if reduction == "min":
        return ordered[0]
    if reduction == "max":
        return ordered[-1]
    lower = ordered[(k - 1) // 2]
    upper = ordered[k // 2]
    if (
        reduction == "median" and level in ("interval", "ratio") and lower != upper
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lower, upper))
    ):
        return (lower + upper) / 2
    return lower


def _same(a: Any, b: Any) -> bool:
    """Equal as a scale level: a bool is never a number, 1 and 1.0 are one level."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _mean_refusal(reduction: str, criteria: Sequence[Mapping[str, Any]]) -> str:
    levels = sorted({
        (c.get("defaultMeasurement") or {}).get("level", "ordinal") for c in criteria
    }) or ["ordinal"]
    return (
        f'refused: reduction "{reduction}" is a mean, and the criteria here are measured at the '
        f"{' and '.join(levels)} level. A mean of ordinal levels is a value no rater could have "
        "chosen (ADR-0011), so this tool reduces by order statistics only: "
        f'{", ".join(REDUCTIONS)}. A trimmed range is legal; a trimmed mean is still a mean.'
    )


def _summary(
    rows: Sequence[Mapping[str, Any]], reduction: str, allow: bool, *, older: int = 0
) -> str:
    contested = sum(r["contested"] for r in rows)
    empty = sum(r["n"] == 0 for r in rows)
    text = f"{len(rows)} cell(s) reduced by {reduction}"
    if contested:
        text += (
            f"; {contested} polarised, "
            + ("reduced anyway and marked contested" if allow else "left without a value and marked contested")
        )
    if empty:
        text += f"; {empty} with no value on the scale"
    off = sum(r["offScale"] for r in rows)
    if off:
        text += f"; {off} value(s) off their scale, not counted"
    if older:
        text += (
            f"; {older} score(s) given under an earlier definition of their criterion, not "
            "counted: re-score those cells against the current one"
        )
    return text
