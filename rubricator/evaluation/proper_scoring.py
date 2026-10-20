"""Family B, proper scoring over ``certainty`` (ADR-0008, ADR-0012, #92). A report, not a gate.

``certainty`` is the probability a scorer gives that its score is right, drawn from a fixed closed
set (:data:`ALLOWED_CERTAINTY`). It is elicited **only** in evaluation runs against fixtures with
known answers, and it lives in the harness's own records: a mapping from cell ``(alternativeId,
criterionId)`` to probability, kept beside the produced analysis and never inside it. No delivered
analysis carries it -- the write path refuses an undeclared ``certainty`` measure, and
:func:`graded_certainty` refuses a produced analysis that carries one, so the fence holds from both
sides.

:func:`certainty_report` pools ``(certainty, correct)`` pairs and reports, in this order:

- ``brier`` and its **Murphy decomposition** (``reliability - resolution + uncertainty``), which is
  exact here because every forecast is one of the allowed values -- the decomposition is the
  informative part, the scalar is not;
- ``skill`` -- the Brier skill score against the base-rate forecast (``1 - brier / uncertainty``);
- ``reliability_curve`` -- per allowed value: how many cells, how many right, the observed share and
  its Wilson interval. The closed set makes the bins exact, so no binning choice is hidden in it;
- ``auroc`` -- discrimination: the chance a right score carries more certainty than a wrong one;
- ``ece`` -- **second, and gated**: ``None`` below ``min_n`` cells, with the reason, because ECE's
  binning is the largest source of estimator bias and a small-n ECE reads as calibration it is not.

Correct means what Family A means by it (:func:`~rubricator.evaluation.discrimination.correct_scores`).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from rubricator.evaluation.discrimination import Key, correct_scores
from rubricator.evaluation.harness import Fixture
from rubricator.stats import wilson_interval

__all__ = ["ALLOWED_CERTAINTY", "CERTAINTY", "MIN_N_FOR_ECE", "certainty_report", "graded_certainty"]

#: The measure name that must never reach a delivered analysis.
CERTAINTY = "certainty"

#: The closed set of probabilities a scorer may give: the chance that an expert scoring the cell
#: independently from the same corpus would give the same level. The set is the research brief's
#: (``docs/research/sections/r2-rubrics-and-calibration.md``, "The second measure"): closed, so every
#: value is its own bin and the reliability curve and ECE have no binning choice to make. Pass
#: ``allowed=`` to report over another set.
ALLOWED_CERTAINTY: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

#: ECE is reported only from this many graded cells, the research brief's small-n rule: below it,
#: binning bias dominates and the headline ECE is suppressed while the curve and the decomposition
#: are still reported.
MIN_N_FOR_ECE = 100


def graded_certainty(
    fixture: Fixture, produced: Mapping[str, Any], certainty: Mapping[Key, float], *,
    allowed: Sequence[float] = ALLOWED_CERTAINTY,
) -> list[tuple[float, bool]]:
    """``(certainty, correct)`` for every produced score with a known answer and a stated certainty.

    ``certainty`` is the harness's record for this fixture, keyed by ``(alternativeId,
    criterionId)``. A value outside ``allowed`` is refused (the set is closed by design), and so is a
    produced analysis carrying a ``certainty`` cell: that is the eval-only measure leaking into what
    would be delivered.
    """
    leaked = sorted((c["alternativeId"], c["criterionId"]) for c in produced.get("cells", ())
                    if c.get("measure") == CERTAINTY)
    if leaked:
        raise ValueError(
            f"refused: the produced analysis carries certainty cells {leaked}. certainty is kept in "
            "the harness's own records, never in an analysis (ADR-0012)."
        )
    off = sorted({p for p in certainty.values() if p not in allowed})
    if off:
        raise ValueError(f"refused: certainty {off} is not one of the allowed values {list(allowed)}")
    return [(certainty[k], ok) for k, ok in correct_scores(fixture, produced).items() if k in certainty]


def certainty_report(
    pairs: Iterable[tuple[float, bool]], *, allowed: Sequence[float] = ALLOWED_CERTAINTY,
    min_n: int = MIN_N_FOR_ECE, level: float = 0.95,
) -> dict[str, Any]:
    """The Family B report over pooled ``(certainty, correct)`` pairs; see the module docstring.

    >>> r = certainty_report([(0.9, True), (0.9, True), (0.5, False), (0.5, True)])
    >>> round(r["brier"], 3), round(r["auroc"], 3), r["ece"], r["n"]
    (0.13, 0.833, None, 4)
    >>> round(r["reliability"] - r["resolution"] + r["uncertainty"], 3)
    0.13

    Every number is ``None`` when there is nothing to compute it over, never a zero.
    """
    pairs = list(pairs)
    n = len(pairs)
    base = sum(ok for _, ok in pairs) / n if n else None
    curve = []
    for value in allowed:
        hits = [ok for p, ok in pairs if p == value]
        lo, hi = wilson_interval(sum(hits), len(hits), level=level)
        curve.append({"certainty": value, "n": len(hits), "correct": sum(hits),
                      "observed": sum(hits) / len(hits) if hits else None, "interval": [lo, hi]})
    report: dict[str, Any] = {"n": n, "baseRate": base, "brier": None, "reliability": None,
                              "resolution": None, "uncertainty": None, "skill": None,
                              "reliability_curve": curve, "auroc": _auroc(pairs), "ece": None,
                              "eceWithheld": None}
    if not n:
        return report
    filled = [b for b in curve if b["n"]]
    report["brier"] = sum((p - ok) ** 2 for p, ok in pairs) / n
    report["reliability"] = sum(b["n"] * (b["certainty"] - b["observed"]) ** 2 for b in filled) / n
    report["resolution"] = sum(b["n"] * (b["observed"] - base) ** 2 for b in filled) / n
    report["uncertainty"] = base * (1 - base)
    report["skill"] = 1 - report["brier"] / report["uncertainty"] if report["uncertainty"] else None
    if n >= min_n:
        report["ece"] = sum(b["n"] * abs(b["certainty"] - b["observed"]) for b in filled) / n
    else:
        report["eceWithheld"] = f"{n} graded cells, below the {min_n} ECE needs to mean anything"
    return report


def _auroc(pairs: Sequence[tuple[float, bool]]) -> float | None:
    """P(a right score's certainty > a wrong one's), ties counted half; ``None`` without both kinds."""
    right = [p for p, ok in pairs if ok]
    wrong = [p for p, ok in pairs if not ok]
    if not right or not wrong:
        return None
    wins = sum((r > w) + 0.5 * (r == w) for r in right for w in wrong)
    return wins / (len(right) * len(wrong))
