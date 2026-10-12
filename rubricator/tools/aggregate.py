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

``contested`` is this tool's verdict about its own reduction -- a marker returned
to the caller, never a stored measure (ADR-0002 leaves the schema to the
companion). Today it is exactly ``polarised``; it is a separate field so that a
later reason a reduction is contested adds a condition, not a field.

## Levels of measurement

The reduction reads the criterion's declared measurement (``defaultMeasurement``):

- **ordinal**: ``median`` is the lower median -- the average of two central
  levels is a mean of levels. ``lower-median``, ``min``, ``max`` as named.
- **interval / ratio**: ``median`` is the conventional median, which may average
  the two central values; there it is legal.
- **nominal**: no order exists, so no order statistic does either. ``reduced`` is
  ``null`` and the modes carry the answer.

A criterion with no declared ``levels`` (a numeric range) has no ordinal steps to
measure a gap in, so it is never polarised; its ``span`` is the numeric distance.

Determinism: order statistics over stored values. One store read, no write.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.rules import live_assertions
from rubricator.store import AnalysisStore

__all__ = ["aggregate_assertions", "cell_shape", "REDUCTIONS"]

#: The order statistics this tool computes. A row per name, so a percentile
#: reduction (a trimmed range) is an addition here and in the frozen row.
REDUCTIONS: tuple[str, ...] = ("lower-median", "median", "min", "max")

DEFAULT_REDUCTION = "lower-median"

#: comparanda's default ``gap`` for ``cellShape``.
DEFAULT_POLARISED_GAP = 1

#: Names a caller may reach for that are means, refused with the reason.
_MEANS = frozenset({"mean", "average", "trimmed-mean", "winsorized-mean", "weighted-mean"})


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
    if reduction in _MEANS:
        raise ValueError(_mean_refusal(reduction, store.read(analysis_id)))
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
    document = store.read(analysis_id)
    live_alternatives = {a["id"] for a in document["alternatives"] if not a.get("tombstoned")}
    criteria = {c["id"]: c for c in document["criteria"] if not c.get("tombstoned")}
    rows = []
    for cell in sorted(
        document["cells"],
        key=lambda c: (c["alternativeId"], c["criterionId"], c.get("measure", "score")),
    ):
        criterion = criteria.get(cell["criterionId"])
        if criterion is None or cell["alternativeId"] not in live_alternatives:
            continue
        rows.append(
            _reduce_cell(
                cell, criterion.get("defaultMeasurement", {}),
                reduction=reduction, allow_contested=allow_contested_reduction, gap=polarised_gap,
            )
        )
    return {
        "analysisId": analysis_id,
        "reduction": reduction,
        "cells": rows,
        "summary": _summary(rows, reduction, allow_contested_reduction),
    }


def _reduce_cell(
    cell: Mapping[str, Any], measurement: Mapping[str, Any], *, reduction: str,
    allow_contested: bool, gap: int,
) -> dict[str, Any]:
    values = [
        a["value"] for a in live_assertions(cell) if a.get("value") is not None
    ]
    shape = cell_shape(values, measurement.get("levels"), gap=gap)
    contested = shape["polarised"]
    reduced = None
    if shape["ordered"] and (not contested or allow_contested):
        reduced = _order_statistic(shape["ordered"], reduction, measurement.get("level"))
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
        "polarised": shape["polarised"],
        "contested": contested,
    }


def cell_shape(
    values: Sequence[Any], levels: Sequence[Any] | None, *, gap: int = DEFAULT_POLARISED_GAP
) -> dict[str, Any]:
    """The multiset, extremes, modes and polarisation of one cell's values.

    Mirrors comparanda's ``cellShape``. With declared ``levels`` the values are
    counted per level in level order, values off the levels are ignored, and
    ``span`` is in ordinal steps. Without them the distinct numeric values are
    the levels, ``span`` is the numeric distance, and nothing is polarised.

    >>> s = cell_shape([2, 4, 2, 4], [1, 2, 3, 4, 5])
    >>> s["modes"], s["polarised"], s["span"]
    ([2, 4], True, 2)
    >>> cell_shape([2, 4, 4], [1, 2, 3, 4, 5])["polarised"]  # one dominant mode
    False
    >>> cell_shape([3, 4], [1, 2, 3, 4, 5])["polarised"]  # adjacent: no empty level between
    False
    """
    if levels:
        counts = [sum(1 for v in values if _same(v, level)) for level in levels]
        occupied = [i for i, c in enumerate(counts) if c]
        ordered = [levels[i] for i in occupied for _ in range(counts[i])]
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
        ordered = numbers
        widest = None
        multiset = [{"level": v, "count": c} for v, c in zip(distinct, counts)]
        span = distinct[-1] - distinct[0] if distinct else 0
    n = len(ordered)
    top = max(counts, default=0)
    modes = [m["level"] for m in multiset if n and m["count"] == top]
    return {
        "n": n,
        "ordered": ordered,
        "levels": multiset,
        "min": ordered[0] if ordered else None,
        "max": ordered[-1] if ordered else None,
        "span": span,
        "modes": modes,
        "polarised": widest is not None and len(occupied) >= 2 and widest >= gap
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
    if reduction == "median" and level in ("interval", "ratio"):
        upper = ordered[k // 2]
        return lower if lower == upper else (lower + upper) / 2
    return lower


def _same(a: Any, b: Any) -> bool:
    """Equal as a scale level: a bool is never a number, 1 and 1.0 are one level."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _mean_refusal(reduction: str, document: Mapping[str, Any]) -> str:
    levels = sorted({
        c.get("defaultMeasurement", {}).get("level", "ordinal") for c in document["criteria"]
    }) or ["ordinal"]
    return (
        f'refused: reduction "{reduction}" is a mean, and the criteria here are measured at the '
        f"{' and '.join(levels)} level. A mean of ordinal levels is a value no rater could have "
        "chosen (ADR-0011), so this tool reduces by order statistics only: "
        f'{", ".join(REDUCTIONS)}. A trimmed range is legal; a trimmed mean is still a mean.'
    )


def _summary(rows: Sequence[Mapping[str, Any]], reduction: str, allow: bool) -> str:
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
    return text
