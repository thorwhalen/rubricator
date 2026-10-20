"""Family A, discrimination over ``confidence`` (ADR-0008 amendment (b), #91).

Do high-confidence cells outperform low-confidence ones? That is a *discrimination* claim about an
ordinal label (ADR-0012), so nothing here averages ``confidence``. A fixture's expected analysis is
the truth: a produced ``score`` cell is *correct* when its live value equals the expected cell's.
The confidence of a cell is the live value of the ``confidence`` cell beside it, read as
:data:`LEVELS` (1 low, 2 medium, 3 high, the ``confidence-1-3`` scale).

Per-analysis metrics (one number per analysis, so the harness bootstraps by analysis, never by
cell), each ``None`` where it does not apply:

- ``accuracy_at_confidence_{low,medium,high}`` -- share of the cells at that level that are correct.
- ``confidence_inflation_rate`` -- share of ``high`` scored cells whose evidence does not support
  the level (no evidence, only the agent's own inference, or no primary/secondary ref with a span).
  **The release gate**: see :func:`gate_failures`.
- ``blank_inflation_rate`` -- share of produced blanks where the expected analysis has a value, i.e.
  evidence was in fact available. ADR-0008 names it for the behaviour; the research's
  ``unknown_preference_rate`` is this.
- ``low_confidence_laundering_rate`` -- the same honesty rule eroding the other way: share of
  ``low`` scored cells with no citable span, a guess hiding in ``low`` rather than emitted blank
  (ADR-0012 rule 1).

:func:`confidence_report` is the pooled view over a set of analyses: counts and a Wilson interval
per level, and a monotone-trend statistic (Kendall tau-b of level against correctness, with a
seeded one-sided permutation p-value). It is a report over cells for reading, not for intervals on
the release numbers.
"""

from __future__ import annotations

import random
from typing import Any, Iterable, Mapping, Sequence

from rubricator.evaluation.harness import Fixture, Metric
from rubricator.stats import kendall_tau_b, wilson_interval

__all__ = [
    "LEVELS", "MAX_CONFIDENCE_INFLATION_RATE", "DISCRIMINATION_SUITE", "confidence_report",
    "correct_scores", "gate_failures",
]

#: Confidence level names by value on the ``confidence-1-3`` scale.
LEVELS = {1: "low", 2: "medium", 3: "high"}

#: The release gate on ``confidence_inflation_rate``: an unsupported ``high`` is ADR-0006 broken.
MAX_CONFIDENCE_INFLATION_RATE = 0.0

_SCORE, _CONFIDENCE = "score", "confidence"
_CHECKABLE_SOURCES = frozenset({"primary", "secondary"})
_INFERENCE = "agent-inference"

Key = tuple[str, str]


def _live(cell: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    assertions = (cell or {}).get("assertions") or []
    return max(assertions, key=lambda a: a.get("version", 0)) if assertions else None


def _cells(analysis: Mapping[str, Any], measure: str) -> dict[Key, Mapping[str, Any] | None]:
    """The live assertion of every cell of ``measure`` on a live alternative and criterion."""
    alternatives = {a["id"] for a in analysis.get("alternatives", ()) if not a.get("tombstoned")}
    criteria = {c["id"] for c in analysis.get("criteria", ()) if not c.get("tombstoned")}
    return {
        (c["alternativeId"], c["criterionId"]): _live(c)
        for c in analysis.get("cells", ())
        if c.get("measure", _SCORE) == measure
        and c["alternativeId"] in alternatives and c["criterionId"] in criteria
    }


def _level(assertion: Mapping[str, Any] | None) -> int | None:
    value = (assertion or {}).get("value")
    return value if isinstance(value, int) and not isinstance(value, bool) and value in LEVELS else None


def _has_value(assertion: Mapping[str, Any] | None) -> bool:
    return assertion is not None and assertion.get("value") is not None


def _citable(assertion: Mapping[str, Any]) -> bool:
    refs = assertion.get("evidence") or []
    return any(r.get("sourceType") in _CHECKABLE_SOURCES and r.get("selectors") for r in refs)


def _supported(assertion: Mapping[str, Any]) -> bool:
    refs = assertion.get("evidence") or []
    return bool(refs) and not all(r.get("sourceType") == _INFERENCE for r in refs) and _citable(assertion)


def correct_scores(fixture: Fixture, produced: Mapping[str, Any]) -> dict[Key, bool]:
    """Whether each produced score is right, for every cell whose expected analysis has a value.

    The one definition of *correct* both families grade against: the produced cell's live value
    equals the expected cell's. A produced blank, or a cell the fixture leaves blank, is not here.
    """
    truth = {k: a["value"] for k, a in _cells(fixture.expected, _SCORE).items() if _has_value(a)}
    return {k: a["value"] == truth[k] for k, a in _cells(produced, _SCORE).items()
            if _has_value(a) and k in truth}


def graded_cells(fixture: Fixture, produced: Mapping[str, Any]) -> list[tuple[int, bool]]:
    """``(confidence level, correct)`` for every produced score that has a level and a known answer."""
    levels = {k: _level(a) for k, a in _cells(produced, _CONFIDENCE).items()}
    return [(levels[k], ok) for k, ok in correct_scores(fixture, produced).items()
            if levels.get(k) is not None]


def _share(hits: int, total: int) -> float | None:
    return hits / total if total else None


def _accuracy_at(level: int):
    def measure(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
        at_level = [ok for lvl, ok in graded_cells(fixture, produced) if lvl == level]
        return _share(sum(at_level), len(at_level))
    return measure


def _high_scored(produced: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    scores = _cells(produced, _SCORE)
    return [
        scores[k] for k, a in _cells(produced, _CONFIDENCE).items()
        if _level(a) == 3 and _has_value(scores.get(k))
    ]


def _confidence_inflation_rate(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
    high = _high_scored(produced)
    return _share(sum(not _supported(a) for a in high), len(high))


def _low_confidence_laundering_rate(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
    scores = _cells(produced, _SCORE)
    low = [scores[k] for k, a in _cells(produced, _CONFIDENCE).items()
           if _level(a) == 1 and _has_value(scores.get(k))]
    return _share(sum(not _citable(a) for a in low), len(low))


def _blank_inflation_rate(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
    available = {k for k, a in _cells(fixture.expected, _SCORE).items() if _has_value(a)}
    blanks = [k for k, a in _cells(produced, _SCORE).items() if a is not None and not _has_value(a)]
    return _share(sum(k in available for k in blanks), len(blanks))


_ACCURACY = tuple(
    Metric(
        f"accuracy_at_confidence_{name}", version=1, tier="nightly", measure=_accuracy_at(level),
        description=f"Share of {name}-confidence scored cells whose value matches the expected one.",
    )
    for level, name in LEVELS.items()
)
CONFIDENCE_INFLATION_RATE = Metric(
    "confidence_inflation_rate", version=1, tier="release", measure=_confidence_inflation_rate,
    description="Share of high-confidence cells whose evidence does not support the level. Gates release.",
)
BLANK_INFLATION_RATE = Metric(
    "blank_inflation_rate", version=1, tier="nightly", measure=_blank_inflation_rate,
    description="Share of blanks emitted where the expected analysis has a value.",
)
LOW_CONFIDENCE_LAUNDERING_RATE = Metric(
    "low_confidence_laundering_rate", version=1, tier="nightly", measure=_low_confidence_laundering_rate,
    description="Share of low-confidence scored cells with no citable span: a guess hiding in low.",
)

DISCRIMINATION_SUITE = (
    *_ACCURACY, CONFIDENCE_INFLATION_RATE, BLANK_INFLATION_RATE, LOW_CONFIDENCE_LAUNDERING_RATE,
)


def gate_failures(
    report: Mapping[str, Any], *, max_inflation: float = MAX_CONFIDENCE_INFLATION_RATE,
) -> list[str]:
    """Why ``report`` (from :func:`~rubricator.evaluation.run_suite`) must not release; ``[]`` if it may.

    A report that never measured ``confidence_inflation_rate`` fails the gate too: an unmeasured
    gate is not a passed one.

    >>> gate_failures({"metrics": {}})
    ['confidence_inflation_rate was not measured']
    >>> gate_failures({"metrics": {"confidence_inflation_rate": {"n": 2, "mean": 0.0}}})
    []
    """
    found = (report.get("metrics") or {}).get("confidence_inflation_rate") or {}
    if not found.get("n"):
        return ["confidence_inflation_rate was not measured"]
    if found["mean"] > max_inflation:
        return [f"confidence_inflation_rate {found['mean']:.3f} exceeds the ceiling {max_inflation:g}"]
    return []


def confidence_report(
    graded: Iterable[tuple[Fixture, Mapping[str, Any]]], *, seed: int = 0, permutations: int = 2000,
    level: float = 0.95,
) -> dict[str, Any]:
    """The pooled distribution of correctness by confidence level, with Wilson intervals and a trend.

    ``graded`` pairs each fixture with the analysis produced for it. ``trend.tau`` is Kendall tau-b of
    level against correctness over all cells (positive: higher confidence is more often right);
    ``trend.p`` is the one-sided permutation p-value of at-least-that-large a tau, seeded.
    Confidence is never averaged: ``levels`` is the distribution.
    """
    pairs = [p for fixture, produced in graded for p in graded_cells(fixture, produced)]
    levels = {}
    for value, name in LEVELS.items():
        ok = [c for lvl, c in pairs if lvl == value]
        lo, hi = wilson_interval(sum(ok), len(ok), level=level)
        levels[name] = {"n": len(ok), "correct": sum(ok), "accuracy": _share(sum(ok), len(ok)),
                        "interval": [lo, hi]}
    tau = kendall_tau_b([lvl for lvl, _ in pairs], [float(c) for _, c in pairs]) if pairs else float("nan")
    return {"levels": levels, "trend": {"tau": None if tau != tau else tau, "n": len(pairs),
                                        "p": _permutation_p(pairs, tau, seed, permutations)}}


def _permutation_p(pairs: Sequence[tuple[int, bool]], tau: float, seed: int, permutations: int) -> float | None:
    if tau != tau:
        return None
    rng = random.Random(seed)
    xs, ys = [lvl for lvl, _ in pairs], [float(c) for _, c in pairs]
    at_least = 0
    for _ in range(permutations):
        shuffled = ys[:]
        rng.shuffle(shuffled)
        at_least += kendall_tau_b(xs, shuffled) >= tau
    return (at_least + 1) / (permutations + 1)
