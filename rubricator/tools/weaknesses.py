"""Tool 16, ``report_weaknesses``: the deterministic half of the review stage (ADR-0005 step 6).

Everything here is read off the stored document; nothing is judged. Each list is
of cells (``alternativeId``, ``criterionId``, ``reason``) on the ``score`` measure:

- **uncited**: a value with no evidence at all.
- **agentInferenceOnly**: a value whose every evidence ref is ``agent-inference``.
- **thinEvidence**: cited, but by no ``primary`` or ``secondary`` ref that carries
  a selector -- nothing a reader could go and check.
- **staleCitations**: a ref whose recorded check is ``stale`` or ``unresolvable``.
- **lowConfidence**: the cell's ``confidence`` measure, reduced, sits on the lowest
  level of its scale. comparanda v1 stores confidence as a measure, not as a field,
  so an analysis that records none has nothing here and the summary says so.

**Dominance** is comparanda's necessary dominance over intervals: an observed value
is ``[v, v]``, a contingent blank is the criterion's declared range, a structural
blank (``not-applicable`` or a kind of it) takes that criterion out of the pairs it
is in. The basis is fixed for the whole analysis: criteria with a direction
(``increasing`` / ``decreasing``) and a declared numeric range.

**Pivotal cells** are found by exact perturbation: every observed value on the basis
is moved one declared level up and one down (never off the scale), and the cell is
pivotal when that changes the non-dominated set -- or, with ``weights``, the top-1
or the top-3 of the weighted sum over range-normalised values. A criterion with no
declared levels (interval or ratio) moves by its declared ``thresholds.preference``,
else ``indifference``, clamped to its range (#237); one that declares neither has no
step to move by and is named, not guessed at.

**traversalLeakageDiagnostic** is Kendall's tau-b between two criteria's reduced
scores across the alternatives scored on both. Every row carries, in its ``note``,
the sentence that it is a scoring-run diagnostic and never a redundancy finding:
for an LLM-scored matrix the judge's halo inflates inter-criterion correlation
beyond the signal (findings-method §7.7).

**Under-defined criteria** -- no written definition and no anchors, or repeats that
polarise in most of the criterion's repeated cells -- go to ``redefine``. Their cells
never enter ``rescore``: re-scoring cannot fix a criterion nobody can apply the
same way twice.

Reads one document; writes nothing; no clock, no model.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from rubricator.rules import declarations_for, live_assertions
from rubricator.schema.vocabulary import vocabulary
from rubricator.stats import kendall_tau_b
from rubricator.store import AnalysisStore

__all__ = ["report_weaknesses", "LEAKAGE_NOTE"]

#: The sentence every diagnostic row carries, in the payload and not only in the docs.
LEAKAGE_NOTE = (
    "A scoring-run diagnostic, never a redundancy finding: a correlation between "
    "criteria scored by the same judge measures that judge's halo and carry-over as "
    "much as the alternatives. Redundancy is settled by the criteria's definitions "
    "(the ladder and the indifference probe), not by this number."
)

DEFAULT_TOP_K = 10
#: Fewer alternatives than this scored on both criteria and tau-b says nothing.
MIN_DIAGNOSTIC_PAIRS = 3
#: A criterion is unstable when at least this many of its repeated cells polarise ...
MIN_UNSTABLE_CELLS = 2
#: ... and they are at least this share of its cells holding repeats.
UNSTABLE_SHARE = 0.5

_SCORE = "score"
_CONFIDENCE = "confidence"
_CHECKABLE_SOURCES = frozenset({"primary", "secondary"})
_STALE_CHECKS = frozenset({"stale", "unresolvable"})
_DIRECTIONS = frozenset({"increasing", "decreasing"})

Key = tuple[str, str]


def report_weaknesses(
    store: AnalysisStore,
    *,
    analysis_id: str,
    top_k: int = DEFAULT_TOP_K,
    budget: int | None = None,
    weights: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Which cells are weak, which alternatives are dominated, and -- with a budget -- what to fix first."""
    from rubricator.tools.aggregate import _measurement_for, _reduce_cell, _steps
    from rubricator.tools.views import skipped_note

    for name, value in (("top_k", top_k), ("budget", budget)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f"refused: {name}={value!r}. It is a whole number, 0 or more. Nothing was computed.")

    document, skipped = store.read_skipping(analysis_id)
    alternatives = [a["id"] for a in document["alternatives"] if not a.get("tombstoned")]
    criteria = {c["id"]: c for c in document["criteria"] if not c.get("tombstoned")}
    measurements = {cid: _measurement_for(c, _SCORE) for cid, c in criteria.items()}
    cells = {
        (cell["alternativeId"], cell["criterionId"], cell.get("measure", _SCORE)): cell
        for cell in document["cells"]
        if cell["alternativeId"] in alternatives and cell["criterionId"] in criteria
    }

    def reduced(key: Key, measure: str) -> dict[str, Any] | None:
        cell = cells.get((*key, measure))
        if cell is None:
            return None
        criterion = criteria[key[1]]
        return _reduce_cell(cell, _measurement_for(criterion, measure), reduction="lower-median",
                            allow_contested=False, gap=1, defined_in=criterion.get("definedInVersion"))

    order = [(a, c) for a in alternatives for c in criteria]
    rows = {k: reduced(k, _SCORE) for k in order}
    values = {k: _number(r["reduced"]) if r else None for k, r in rows.items()}
    inapplicable = _inapplicability(document)
    structural = {k for k in order
                  if inapplicable(*k) or _structural_blank(cells.get((*k, _SCORE)), document, values[k])}

    evidence = _evidence_findings(order, cells)
    low_confidence, confidence_seen = _low_confidence(order, cells, criteria, reduced, _steps)

    basis = [c for c in criteria if _admits_dominance(measurements[c])]
    weighted = _checked_weights(weights, criteria, basis)
    excluded = [c for c in criteria if c not in basis]

    def picture(vals: Mapping[Key, float | None]) -> tuple[frozenset[str], ...]:
        front, _ = _dominance(alternatives, basis, measurements, vals, structural)
        if not weighted:
            return (front,)
        ranked = _ranking(alternatives, weighted, measurements, vals)
        return front, _top(ranked, 1), _top(ranked, 3)

    front, dominated = _dominance(alternatives, basis, measurements, values, structural)
    pivotal, unlevelled = _pivotal(order, basis, measurements, values, picture, _steps)

    redefine = _under_defined(criteria, measurements, rows)
    instability = [
        _ref(k, f"observed instability: {r['n']} scorings spanning {r['span']} level(s)")
        for k, r in rows.items() if r and r["n"] >= 2 and r["span"]
    ]
    plan = None
    if budget is not None:
        queue = [*pivotal, *evidence["thin"], *evidence["uncited"], *evidence["inference"], *instability]
        rescore, seen = [], set()
        for ref in queue:
            key = (ref["alternativeId"], ref["criterionId"])
            if key not in seen and key[1] not in redefine:
                seen.add(key)
                rescore.append(ref)
        plan = {"rescore": rescore[:budget], "redefine": redefine, "budget": budget}

    leakage = _leakage(criteria, measurements, alternatives, values)
    vetoes = _vetoes(alternatives, criteria, measurements, values)

    lists = {
        "uncited": evidence["uncited"], "thinEvidence": evidence["thin"],
        "lowConfidence": low_confidence, "staleCitations": evidence["stale"],
        "agentInferenceOnly": evidence["inference"],
    }
    return {
        "analysisId": analysis_id,
        **{name: found[:top_k] for name, found in lists.items()},
        "dominatedAlternatives": dominated,
        "vetoFlags": vetoes[:top_k],
        "traversalLeakageDiagnostic": leakage[:top_k],
        "rescoringPlan": plan,
        "summary": _summary(
            scored=sum(v is not None for v in values.values()), lists=lists, top_k=top_k,
            front=front, dominated=dominated, basis=basis, excluded=excluded, pivotal=pivotal,
            unlevelled=unlevelled, confidence_seen=confidence_seen, vetoes=vetoes,
            leakage=leakage, plan=plan, weighted=bool(weighted),
        ) + skipped_note(skipped),
    }


# --- cell findings ------------------------------------------------------------------------


def _ref(key: Key, reason: str) -> dict[str, str]:
    return {"alternativeId": key[0], "criterionId": key[1], "reason": reason}


def _number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _structural_blank(cell: Mapping[str, Any] | None, document: Mapping[str, Any], value: Any) -> bool:
    """A cell with no value whose blank says the criterion does not apply to this alternative."""
    if cell is None or value is not None:
        return False
    declarations = declarations_for(document, cell["criterionId"])
    for assertion in live_assertions(cell):
        code = (assertion.get("missing") or {}).get("code")
        if isinstance(code, str):
            facts = vocabulary().resolve(code, declarations).facts
            if facts is not None and facts.structural:
                return True
    return False


def _evidence_findings(order: Sequence[Key], cells: Mapping[tuple, Any]) -> dict[str, list[dict[str, str]]]:
    found: dict[str, list[dict[str, str]]] = {"uncited": [], "thin": [], "inference": [], "stale": []}
    for key in order:
        cell = cells.get((*key, _SCORE))
        scored = [a for a in live_assertions(cell) if a.get("value") is not None] if cell else []
        refs = [r for a in scored for r in a.get("evidence") or []]
        if any(not a.get("evidence") for a in scored):
            found["uncited"].append(_ref(key, "a value with no evidence"))
        elif refs and all(r.get("sourceType") == "agent-inference" for r in refs):
            found["inference"].append(_ref(key, "every ref is the agent's own inference"))
        elif refs and not any(r.get("sourceType") in _CHECKABLE_SOURCES and r.get("selectors") for r in refs):
            found["thin"].append(_ref(key, "no primary or secondary ref with a span to check"))
        stale = sorted({r["check"]["status"] for r in refs
                        if (r.get("check") or {}).get("status") in _STALE_CHECKS})
        if stale:
            found["stale"].append(_ref(key, f"a citation checked {' and '.join(stale)}"))
    return found


def _low_confidence(order, cells, criteria, reduced, steps) -> tuple[list[dict[str, str]], bool]:
    """Read only off a declared ``confidence`` measurement: the score scale is not a confidence scale."""
    found, seen = [], False
    for key in order:
        own = (criteria[key[1]].get("measurements") or {}).get(_CONFIDENCE)
        if (*key, _CONFIDENCE) not in cells or not own:
            continue
        seen = True
        row = reduced(key, _CONFIDENCE)
        levels = steps(own)
        if row and row["reduced"] is not None and levels and row["reduced"] == levels[0]:
            found.append(_ref(key, f"confidence at the lowest level of its scale ({levels[0]})"))
    return found, seen


# --- dominance and perturbation -----------------------------------------------------------


def _admits_dominance(m: Mapping[str, Any]) -> bool:
    rng = m.get("range") or {}
    return (m.get("level", "ordinal") != "nominal" and m.get("preference") in _DIRECTIONS
            and _number(rng.get("min")) is not None and _number(rng.get("max")) is not None)


def _oriented(m: Mapping[str, Any], lo: float, hi: float) -> tuple[float, float]:
    """The interval with larger always better."""
    return (lo, hi) if m["preference"] == "increasing" else (-hi, -lo)


def _dominance(alternatives, basis, measurements, values, structural) -> tuple[frozenset[str], list[str]]:
    """Necessary dominance over intervals: the front, and the alternatives dominated, in row order."""
    def interval(alt: str, crit: str) -> tuple[float, float]:
        v = values[(alt, crit)]
        rng = measurements[crit]["range"]
        lo, hi = (v, v) if v is not None else (rng["min"], rng["max"])
        return _oriented(measurements[crit], lo, hi)

    def dominates(a: str, b: str) -> bool:
        shared = [c for c in basis if (a, c) not in structural and (b, c) not in structural]
        if not shared:
            return False
        pairs = [(interval(a, c), interval(b, c)) for c in shared]
        return all(ia[0] >= ib[1] for ia, ib in pairs) and any(ia[0] > ib[1] for ia, ib in pairs)

    dominated = [b for b in alternatives if any(dominates(a, b) for a in alternatives if a != b)]
    return frozenset(a for a in alternatives if a not in dominated), dominated


def _inapplicability(document: Mapping[str, Any]) -> Callable[[str, str], bool]:
    """comparanda's ``makeInapplicability``: is the cell inside a declared inapplicable group pair?

    Membership is by closure on both axes, so a block on a group covers its sub-groups' members.
    """
    blocks = [(b.get("alternativeGroupId"), b.get("criterionGroupId")) for b in document.get("inapplicable") or []]
    if not blocks:
        return lambda alt, crit: False

    def closure(axis: str) -> dict[str, set[str]]:
        groups = {g["id"]: g for g in document.get("groups") or [] if g.get("axis") == axis and not g.get("tombstoned")}
        out = {}
        for entity in document.get(axis) or []:
            found: set[str] = set()
            todo = [g for g in entity.get("groupIds") or [] if g in groups]
            while todo:
                g = todo.pop()
                if g not in found:
                    found.add(g)
                    parent = groups[g].get("parentId")
                    if parent in groups:
                        todo.append(parent)
            out[entity["id"]] = found
        return out

    alts, crits = closure("alternatives"), closure("criteria")
    return lambda alt, crit: any(a in alts.get(alt, ()) and c in crits.get(crit, ()) for a, c in blocks)


def _top(ranked: Sequence[tuple[float, str]], k: int) -> frozenset[str]:
    """The first ``k`` and everything tied with the k-th, so breaking a tie is never a change."""
    if not ranked:
        return frozenset()
    cut = ranked[min(k, len(ranked)) - 1][0]
    return frozenset(alt for total, alt in ranked if total >= cut)


def _ranking(alternatives, weighted, measurements, values) -> list[tuple[float, str]]:
    """Weighted sum over range-normalised values, best first; an alternative blank on a weighted criterion is unranked."""
    scores = []
    for i, alt in enumerate(alternatives):
        if any(values[(alt, c)] is None for c, _ in weighted):
            continue
        total = 0.0
        for crit, w in weighted:
            m = measurements[crit]
            lo, hi = m["range"]["min"], m["range"]["max"]
            share = (values[(alt, crit)] - lo) / (hi - lo) if hi != lo else 0.0
            total += w * (share if m["preference"] == "increasing" else 1 - share)
        scores.append((-round(total, 12), i, alt))
    return [(-negated, alt) for negated, _, alt in sorted(scores)]


def _pivotal(order, basis, measurements, values, picture: Callable, steps) -> tuple[list[dict[str, str]], list[str]]:
    """Cells whose one-step move changes the picture, with the move and what changed in the reason.

    A step is one declared level; on a criterion with no levels it is the declared
    ``thresholds.preference`` (else ``indifference``), comparanda's own size of a
    meaningful difference, clamped to the range. A criterion with neither is named.
    """
    baseline = picture(values)
    names = ("the non-dominated set", "the weighted top-1", "the weighted top-3")
    found = []
    unlevelled = [c for c in basis if not steps(measurements[c]) and _threshold_step(measurements[c]) is None]
    for key in order:
        v = values[key]
        if v is None or key[1] not in basis or key[1] in unlevelled:
            continue
        for target, move in _moves(measurements[key[1]], v, steps):
            moved = picture({**values, key: target})
            changed = [n for n, before, after in zip(names, baseline, moved) if before != after]
            if changed:
                found.append(_ref(key, f"pivotal: {move} ({v} to {target}) changes {' and '.join(changed)}"))
                break
    return found, unlevelled


def _threshold_step(m: Mapping[str, Any]) -> tuple[float, str] | None:
    """The declared size of a meaningful difference, and which threshold it is."""
    for name in ("preference", "indifference"):
        step = _number((m.get("thresholds") or {}).get(name))
        if step is not None and step > 0 and math.isfinite(step):
            return step, name
    return None


def _moves(m: Mapping[str, Any], v: float, steps) -> list[tuple[float, str]]:
    """The one-step moves up then down from ``v``, never off the scale."""
    levels = steps(m)
    if levels:
        if v not in levels:
            return []
        i = levels.index(v)
        return [(levels[j], f"{sign} level") for j, sign in ((i + 1, "+1"), (i - 1, "-1")) if 0 <= j < len(levels)]
    step, name = _threshold_step(m)
    lo, hi = m["range"]["min"], m["range"]["max"]
    out = []
    if v < hi:
        out.append((min(v + step, hi), f"+{step} ({name} threshold)"))
    if v > lo:
        out.append((max(v - step, lo), f"-{step} ({name} threshold)"))
    return out


def _checked_weights(weights, criteria, basis) -> list[tuple[str, float]]:
    if not weights:
        return []
    out, seen = [], set()
    for w in weights:
        crit, weight = w.get("criterionId"), w.get("weight")
        if crit not in criteria:
            raise ValueError(f'refused: weight names criterion "{crit}", which is not a live criterion here. Nothing was computed.')
        if crit not in basis:
            raise ValueError(
                f'refused: criterion "{crit}" cannot be weighted: it has no direction (increasing or '
                "decreasing) and declared numeric range to normalise over. Nothing was computed.")
        if crit in seen:
            raise ValueError(f'refused: criterion "{crit}" is weighted twice. Nothing was computed.')
        if _number(weight) is None or weight < 0 or not math.isfinite(weight):
            raise ValueError(f'refused: weight {weight!r} for "{crit}" is not a number 0 or more. Nothing was computed.')
        seen.add(crit)
        out.append((crit, weight))
    return out


# --- criteria -----------------------------------------------------------------------------


def _written(definition: Any) -> bool:
    """comparanda v1's definition is an object of fields; any non-blank field is a definition.

    >>> _written({"question": "how fast?"}), _written({"question": " "}), _written(None)
    (True, False, False)
    """
    if isinstance(definition, Mapping):
        return any(_written(v) for v in definition.values())
    if isinstance(definition, (list, tuple)):
        return any(_written(v) for v in definition)
    return isinstance(definition, str) and bool(definition.strip())


def _under_defined(criteria, measurements, rows) -> list[str]:
    out = []
    for cid, criterion in criteria.items():
        unwritten = not _written(criterion.get("definition")) and not measurements[cid].get("anchors")
        repeated = [r for (_, c), r in rows.items() if c == cid and r and r["n"] >= 2]
        polarised = sum(r["polarised"] for r in repeated)
        unstable = polarised >= MIN_UNSTABLE_CELLS and polarised >= UNSTABLE_SHARE * len(repeated)
        if unwritten or unstable:
            out.append(cid)
    return out


def _leakage(criteria, measurements, alternatives, values) -> list[dict[str, Any]]:
    ordered = [c for c in criteria if measurements[c].get("level", "ordinal") != "nominal"]
    rows = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            both = [(values[(x, a)], values[(x, b)]) for x in alternatives
                    if values[(x, a)] is not None and values[(x, b)] is not None]
            if len(both) < MIN_DIAGNOSTIC_PAIRS:
                continue
            tau = kendall_tau_b([p[0] for p in both], [p[1] for p in both])
            if math.isnan(tau):
                continue
            rows.append({"criterionA": a, "criterionB": b, "correlation": round(tau, 6),
                         "note": f"Kendall tau-b over {len(both)} alternatives. {LEAKAGE_NOTE}"})
    return sorted(rows, key=lambda r: (-abs(r["correlation"]), r["criterionA"], r["criterionB"]))


def _vetoes(alternatives, criteria, measurements, values) -> list[dict[str, str]]:
    """comparanda's ``screen``: a value on the wrong side of a floor, or a blank where none could be tested."""
    out = []
    for cid, criterion in criteria.items():
        floor = criterion.get("acceptability")
        if not floor:
            continue
        decreasing = measurements[cid].get("preference") == "decreasing"
        for alt in alternatives:
            v = values[(alt, cid)]
            if v is None:
                reason = f"blank: the floor {floor['threshold']} was not tested, and an untested floor is not a passed one"
            elif (v > floor["threshold"]) if decreasing else (v < floor["threshold"]):
                reason = f"{v} fails the floor {floor['threshold']}: {floor['rationale']}"
            else:
                continue
            out.append({"alternativeId": alt, "criterionId": cid, "reason": reason})
    return out


def _summary(*, scored, lists, top_k, front, dominated, basis, excluded, pivotal, unlevelled,
             confidence_seen, vetoes, leakage, plan, weighted) -> str:
    if not scored:
        return "Nothing has been scored yet, so there is nothing to weigh: every list is empty."

    def count(name: str, found: Sequence[Any]) -> str:
        shown = f" (first {top_k} shown)" if len(found) > top_k else ""
        return f"{len(found)} {name}{shown}"

    parts = [f"{scored} scored cell(s)", *(count(n, f) for n, f in lists.items())]
    if not confidence_seen:
        parts.append("no confidence measure recorded, so lowConfidence cannot be read")
    if basis:
        parts.append(f"dominance over {len(basis)} criteria: {len(dominated)} dominated, "
                     f"{len(front)} on the front" + (f"; {len(excluded)} excluded (no direction "
                                                     "or no declared range)" if excluded else ""))
    else:
        parts.append("no criterion has a direction and a declared range, so dominance was not computed")
    parts.append(f"{len(pivotal)} pivotal cell(s)" + (" under weights too" if weighted else ""))
    if unlevelled:
        parts.append(f"{', '.join(unlevelled)} declare no levels and no threshold, so no cell there was perturbed")
    parts.append(count("veto flag(s)", vetoes))
    parts.append(count("diagnostic correlation(s), none of them a redundancy finding", leakage))
    if plan is not None:
        parts.append(f"plan: {len(plan['rescore'])} cell(s) to rescore within a budget of {plan['budget']}, "
                     f"{len(plan['redefine'])} criteria to redefine rather than rescore")
    return "; ".join(parts) + "."
