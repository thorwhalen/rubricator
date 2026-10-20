"""Tool 15, ``stability_report``: how much the picture moves between repeated scorings (ADR-0018).

Everything is read off the stored draws; nothing is judged or resampled.

**Repeated matrices.** A cell's draws are its live ``score`` assertions that hold a
value and answer the current definition, ordered by their pass (the number in
``roundId``), then by stored order for draws with no pass. Matrix *i* takes each
cell's *i*-th draw; a cell with fewer draws holds its lower median there, so a cell
scored once sits at its one value in every matrix and moves nothing. There are as
many matrices as the most-scored cell has draws.

**Weight-free first.** ``dominanceSurvival`` is, per alternative, the share of the
matrices in which it is not necessarily dominated -- comparanda's interval dominance,
the same basis as ``report_weaknesses`` (criteria with a direction and a declared
numeric range), named in ``basis``. ``paretoChurn`` is the mean Jaccard distance
between the non-dominated sets of every pair of matrices. A contingent blank widens
to the declared range and makes its row undominatable, so ``blankDensity`` -- the
share of basis cells with no value, structural blanks left out -- is returned beside
them as the counter-metric. ``perCell`` is the wobble of every cell holding two or
more draws: it aggregates nothing, so nothing is inflated away.

**Weighted only when weights are declared**: Kendall's tau-b between the weighted
totals of every pair of matrices, the share of pairs whose top-1 (and top-3) differ,
and a band verdict from the lower median tau against ``tau_bands``.

**Per criterion**: ``agreement`` is the share of within-cell pairs of draws on the
same value, pooled over the criterion's repeated cells -- labelled by the weakest
independence rung among them (``agreementLabel``), so in-session draws read as agent
self-consistency and never as inter-rater agreement. ``histogram`` counts each
cell's reduced value per level, and ``compression`` is the share of those cells on
the most-used level (the escalation trigger and the discrimination counter-metric).

Reads one document; writes nothing; no clock, no model.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from rubricator.criteria_versions import answers_an_older_definition
from rubricator.independence import RUNGS, agreement
from rubricator.rules import live_assertions
from rubricator.stats import kendall_tau_b
from rubricator.store import AnalysisStore

__all__ = ["stability_report", "DEFAULT_TAU_BANDS"]

#: The companion's decision rule (findings-method §8): tau at or above ``high`` is stable.
DEFAULT_TAU_BANDS = {"low": 0.7, "high": 0.9}

_SCORE = "score"
_ROUND = re.compile(r"^round-(\d+)")
#: The stored ``independence`` value that reads as each policy rung. Mapped from the rung
#: ``agreement`` settled on, which may sit below every draw's own claim (one principal
#: behind two ``independent`` draws is in-session); ``unrecorded`` has no stored value.
_STORED_RUNG = {"in-session": "shared-context", "fresh-session": "resampled",
                "distinct-model": "independent", "distinct-human": "independent"}

Key = tuple[str, str]


def stability_report(
    store: AnalysisStore,
    *,
    analysis_id: str,
    weights: Sequence[Mapping[str, Any]] | None = None,
    tau_bands: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Dominance survival and Pareto churn across repeated matrices, per-criterion agreement, and -- with weights -- tau-b."""
    from rubricator.tools.aggregate import _measurement_for, _reduce_cell, _steps
    from rubricator.tools.views import skipped_note
    from rubricator.tools.weaknesses import (
        _admits_dominance, _checked_weights, _dominance, _inapplicability, _number, _ranking,
        _structural_blank, _top,
    )

    bands = _checked_bands(tau_bands)
    document, skipped = store.read_skipping(analysis_id)
    authors = {a["id"]: a for a in document.get("authors", [])}
    alternatives = [a["id"] for a in document["alternatives"] if not a.get("tombstoned")]
    criteria = {c["id"]: c for c in document["criteria"] if not c.get("tombstoned")}
    measurements = {cid: _measurement_for(c, _SCORE) for cid, c in criteria.items()}
    cells = {
        (cell["alternativeId"], cell["criterionId"]): cell
        for cell in document["cells"]
        if cell.get("measure", _SCORE) == _SCORE
        and cell["alternativeId"] in alternatives and cell["criterionId"] in criteria
    }
    order = [(a, c) for a in alternatives for c in criteria]
    draws = {k: _draws(cells.get(k), criteria[k[1]].get("definedInVersion")) for k in order}
    rows = {
        k: _reduce_cell(cells[k], measurements[k[1]], reduction="lower-median", allow_contested=True,
                        gap=1, defined_in=criteria[k[1]].get("definedInVersion"))
        for k in order if k in cells
    }
    fill = {k: _number(rows[k]["reduced"]) if k in rows else None for k in order}
    depth = max((len(d) for d in draws.values()), default=0)
    matrices = [
        {k: _number(d[i]["value"]) if i < len(d) else fill[k] for k, d in draws.items()}
        for i in range(max(depth, 1))
    ]

    inapplicable = _inapplicability(document)
    structural = {k for k in order
                  if inapplicable(*k) or _structural_blank(cells.get(k), document, fill[k])}
    basis = [c for c in criteria if _admits_dominance(measurements[c])]
    weighted = _checked_weights(weights, criteria, basis)

    fronts = [_dominance(alternatives, basis, measurements, m, structural)[0] for m in matrices]
    survival = [{"alternativeId": a, "rate": _share(sum(a in f for f in fronts), len(fronts))}
                for a in alternatives]
    pairs = list(itertools.combinations(range(len(matrices)), 2))
    churn = _mean([_jaccard_distance(fronts[i], fronts[j]) for i, j in pairs])
    on_basis = [(a, c) for a in alternatives for c in basis if (a, c) not in structural]
    blank_density = _share(sum(fill[k] is None for k in on_basis), len(on_basis))

    per_cell = [
        {"alternativeId": k[0], "criterionId": k[1], "n": rows[k]["n"],
         "span": rows[k]["span"], "polarised": rows[k]["polarised"]}
        for k in order if k in rows and rows[k]["n"] >= 2
    ]
    per_criterion = [
        _criterion(cid, [k for k in order if k[1] == cid], draws, rows, measurements[cid], authors,
                   _steps)
        for cid in criteria
    ]
    weighted_report, weighted_note = (None, "no weights declared, so no tau-b")
    if weighted:
        rankings = [_ranking(alternatives, weighted, measurements, m) for m in matrices]
        weighted_report, weighted_note = _weighted(rankings, pairs, bands, _top)

    return {
        "analysisId": analysis_id,
        "repeatedMatrices": len(matrices) if depth else 0,
        "basis": basis,
        "dominanceSurvival": survival,
        "paretoChurn": churn,
        "blankDensity": blank_density,
        "perCell": per_cell,
        "perCriterion": per_criterion,
        "weighted": weighted_report,
        "summary": _summary(
            depth=depth, basis=basis, criteria=criteria, survival=survival, churn=churn,
            blank_density=blank_density, per_cell=per_cell, per_criterion=per_criterion,
            weighted_note=weighted_note,
        ) + skipped_note(skipped),
    }


def _checked_bands(tau_bands: Mapping[str, float] | None) -> dict[str, float]:
    bands = dict(DEFAULT_TAU_BANDS if tau_bands is None else tau_bands)
    low, high = bands.get("low"), bands.get("high")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (low, high)) \
            or not -1 <= low <= high <= 1:
        raise ValueError(
            f"refused: tau_bands={tau_bands!r}. It is {{low, high}} with -1 <= low <= high <= 1. "
            "Nothing was computed.")
    return {"low": low, "high": high}


def _draws(cell: Mapping[str, Any] | None, defined_in: str | None) -> list[Mapping[str, Any]]:
    """The cell's scorings, by pass number, then stored order for those with no pass."""
    if cell is None:
        return []
    found = [a for a in live_assertions(cell)
             if a.get("value") is not None and not answers_an_older_definition(a, defined_in)]

    def by_pass(indexed: tuple[int, Mapping[str, Any]]) -> tuple[int, int, int]:
        i, a = indexed
        match = _ROUND.match(a.get("roundId") or "")
        return (0, int(match.group(1)), i) if match else (1, 0, i)

    return [a for _, a in sorted(enumerate(found), key=by_pass)]


def _share(part: int, whole: int) -> float:
    return round(part / whole, 6) if whole else 0.0


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _jaccard_distance(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a ^ b) / len(union) if union else 0.0


def _criterion(cid, keys, draws, rows, measurement, authors, steps) -> dict[str, Any]:
    """Agreement labelled by its weakest rung, and the column's histogram and compression."""
    repeated = [draws[k] for k in keys if len(draws[k]) >= 2]
    same = total = 0
    found = [r for r in (agreement(d, authors) for d in repeated) if r is not None]
    for d in repeated:
        for x, y in itertools.combinations(d, 2):
            total += 1
            same += x["value"] == y["value"]
    rung, label, stored = None, None, None
    if found:
        weakest = min(found, key=lambda r: RUNGS.index(r["rung"]))
        rung, label = weakest["rung"], weakest["label"]
        stored = _STORED_RUNG.get(rung)
    elif repeated:
        label = "not assessable: the repeated scorings are agreed values (consensus), not observations"
    levels = steps(measurement)
    reduced = [rows[k]["reduced"] for k in keys if k in rows and rows[k]["reduced"] is not None]
    if levels is not None:
        histogram = [{"level": str(lvl), "count": sum(v == lvl for v in reduced)} for lvl in levels]
    else:
        histogram = [{"level": str(v), "count": reduced.count(v)}
                     for v in sorted(set(reduced), key=lambda v: (str(type(v)), v))]
    return {
        "criterionId": cid,
        "agreement": round(same / total, 6) if found and total else None,
        "lowestRung": stored,
        "agreementLabel": label,
        "repeatedCells": len(repeated),
        "histogram": histogram,
        "compression": _share(max((h["count"] for h in histogram), default=0), len(reduced)),
    }


def _weighted(rankings, pairs, bands, top) -> tuple[dict[str, Any] | None, str]:
    """tau-b, top-1 and top-3 churn over every pair of matrices' weighted totals."""
    if not pairs:
        return None, "weights declared, but one matrix has nothing to compare with, so no tau-b"
    taus, top1, top3 = [], 0, 0
    for i, j in pairs:
        a, b = dict((alt, t) for t, alt in rankings[i]), dict((alt, t) for t, alt in rankings[j])
        both = [alt for alt in a if alt in b]
        tau = kendall_tau_b([a[x] for x in both], [b[x] for x in both]) if len(both) >= 2 else math.nan
        if not math.isnan(tau):
            taus.append(round(tau, 6))
        top1 += top(rankings[i], 1) != top(rankings[j], 1)
        top3 += top(rankings[i], 3) != top(rankings[j], 3)
    if not taus:
        return None, ("weights declared, but no pair of matrices ranks two alternatives with "
                      "distinct totals, so tau-b is undefined")
    median = sorted(taus)[(len(taus) - 1) // 2]
    band = "stable" if median >= bands["high"] else "borderline" if median >= bands["low"] else "unstable"
    return (
        {"tauDistribution": taus, "top1Churn": _share(top1, len(pairs)),
         "top3Churn": _share(top3, len(pairs)), "band": band},
        f"weighted: lower-median tau-b {median} over {len(taus)} pair(s), band {band}",
    )


def _summary(*, depth, basis, criteria, survival, churn, blank_density, per_cell, per_criterion,
             weighted_note) -> str:
    if not depth:
        return ("Nothing has been scored, so there is no matrix to repeat and no stability to "
                "report: every survival rate is the empty picture's, not a measurement.")
    if depth == 1:
        head = ("One scoring per cell: the survival rates are the non-dominated set of the one "
                "matrix (1 or 0), not a stability figure; score again to measure stability.")
    else:
        stable = sum(r["rate"] == 1 for r in survival)
        head = (f"{depth} repeated matrices: {stable} of {len(survival)} alternative(s) "
                f"non-dominated in every one; Pareto churn {churn}.")
    excluded = [c for c in criteria if c not in basis]
    parts = [
        head,
        f"Basis: {', '.join(basis) or 'none'}"
        + (f" ({', '.join(excluded)} left out: no direction and declared range)." if excluded else "."),
        f"Blank density {blank_density}: blanks make a row undominatable and inflate survival.",
        f"{len(per_cell)} cell(s) hold two or more scorings.",
    ]
    labelled = [c for c in per_criterion if c["agreement"] is not None]
    if labelled:
        parts.append("Agreement is labelled per criterion by its weakest rung, e.g. "
                     f'"{labelled[0]["agreementLabel"]}".')
    else:
        parts.append("No criterion has repeated observations, so no agreement figure is given.")
    parts.append(weighted_note + ".")
    return " ".join(parts)
