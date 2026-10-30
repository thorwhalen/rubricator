"""The objective ladder a criteria proposal emits, and the checks that need no model.

``propose-criteria`` (ADR-0005 stage 3, #68) does not only propose criteria: it
emits the **objective ladder** that produced them. Every candidate was asked
"why is that important?" until the chain reached a fundamental objective, and
each fundamental objective was asked "what do you mean by that, exactly?" until
its leaves could be judged for one alternative in isolation. **The leaves are
the criteria.** Means objectives found on the way are rejected, with the
objective they serve, and become ``exclusions`` text on the criteria they serve.

Emitting the ladder is the cheapest structural win available
(``docs/research/sections/r1-criteria-elicitation.md`` §1b, §4a): two criteria
that refine the same objective are double-counting candidates **by
construction**, found by walking a graph rather than by correlating scores. This
module is that walk. Nothing here calls a model.

A proposal is a mapping with these keys (``criteria`` is exactly what
``criteria_set`` takes, with each criterion's ``provenance`` on it; ``rejected``
is what ``criteria_reject`` records; the rest have no slot in the companion
contract and ride beside it):

- ``ladder`` -- ``objectives`` (``id``, ``text``) and ``edges`` (``from`` a
  criterion or an objective, ``to`` the objective it refines);
- ``rejected`` -- each with a ``reason`` from :data:`REJECT_REASONS`;
- ``criteria``;
- ``overlaps`` -- pairs of criteria, ``via`` the objective they share;
- ``groups`` -- each fundamental objective with its criteria and their count;
- ``provenance`` -- per criterion, ``user-stated`` (with the user's words) or
  ``agent-proposed``;
- ``questions`` -- what the step-4 checkpoint must ask, rather than assume.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Mapping

__all__ = [
    "REJECT_REASONS",
    "REJECT_REASON_CODES",
    "rejection_record",
    "PROVENANCE",
    "children",
    "leaves",
    "fundamentals",
    "sibling_pairs",
    "group_sizes",
    "proposal_problems",
]

#: ADR-0016's closed vocabulary for a criterion that was proposed and then removed.
REJECT_REASONS: tuple[str, ...] = (
    "merged-into", "means-objective", "not-controllable", "no-discrimination-expected",
    "user-rejected",
)

#: How each ADR-0016 reject code is stored in comparanda's ``rejectedCriteria`` (#259, ADR-0016).
#: The pinned schema's ``reasonCode`` is a different closed set, so until it carries the five codes
#: (comparanda request 19) every one is stored as ``other``, except a merge, which has its own
#: code and ``mergedIntoId``. The ADR code is prefixed on ``reason`` (``means-objective: ...``), so
#: rejects stay countable by it and migrate mechanically when the schema learns them.
REJECT_REASON_CODES: dict[str, str] = {
    "merged-into": "merged", "means-objective": "other", "not-controllable": "other",
    "no-discrimination-expected": "other", "user-rejected": "other",
}

#: Who a proposed criterion came from. ADR-0006's source-type rule, one level up.
PROVENANCE: tuple[str, ...] = ("user-stated", "agent-proposed")


def _maps(value: Any) -> list[Mapping[str, Any]]:
    """The mapping entries of a list; anything else -- None, a string, a number -- is none.

    A model's output is read here, so every shape is possible. A malformed part
    is reported by the checks below, never raised as a crash.
    """
    return [v for v in value if isinstance(v, Mapping)] if isinstance(value, list) else []


def _ladder(proposal: Mapping[str, Any]) -> Mapping[str, Any]:
    ladder = proposal.get("ladder")
    return ladder if isinstance(ladder, Mapping) else {}


def _edges(ladder: Mapping[str, Any]) -> list[tuple[str, str]]:
    return [(e.get("from"), e.get("to")) for e in _maps(ladder.get("edges"))
            if isinstance(e.get("from"), str) and isinstance(e.get("to"), str)]


def _objective_ids(ladder: Mapping[str, Any]) -> list[str]:
    return [o["id"] for o in _maps(ladder.get("objectives")) if isinstance(o.get("id"), str)]


def children(ladder: Mapping[str, Any]) -> dict[str, list[str]]:
    """Each node's direct refinements, in edge order."""
    out: dict[str, list[str]] = {}
    for child, parent in _edges(ladder):
        out.setdefault(parent, []).append(child)
    return out


def _nodes(ladder: Mapping[str, Any]) -> set[str]:
    return set(_objective_ids(ladder)) | {n for edge in _edges(ladder) for n in edge}


def leaves(ladder: Mapping[str, Any]) -> set[str]:
    """The nodes nothing refines: these, and only these, are the criteria."""
    refined = set(children(ladder))
    return {n for n in _nodes(ladder) if n not in refined}


def fundamentals(ladder: Mapping[str, Any]) -> list[str]:
    """The objectives that refine nothing: where every "why is that important?" chain ends."""
    refining = {child for child, _ in _edges(ladder)}
    return [o for o in _objective_ids(ladder) if o not in refining]


def sibling_pairs(ladder: Mapping[str, Any], criteria: Iterable[str]) -> set[tuple[str, str, str]]:
    """``(a, b, parent)`` for every two criteria that refine the same objective directly.

    These are the double-counting candidates the ladder finds by construction
    (r1 section 4a: two ladders converging on one objective within one hop).
    Each must reach the step-4 checkpoint as an indifference question; the
    ladder cannot say whether they overlap, only that they might.
    """
    wanted = set(criteria)
    return {
        (*sorted((a, b)), parent)
        for parent, kids in children(ladder).items()
        for a, b in combinations([k for k in dict.fromkeys(kids) if k in wanted], 2)
    }


def _descendant_leaves(ladder: Mapping[str, Any], node: str) -> set[str]:
    kids = children(ladder)
    seen, stack, out = set(), [node], set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        below = kids.get(current, [])
        if not below and current != node:
            out.add(current)
        stack.extend(below)
    return out


def group_sizes(ladder: Mapping[str, Any]) -> dict[str, int]:
    """How many criteria sit under each fundamental objective -- the number splitting bias hides in."""
    return {f: len(_descendant_leaves(ladder, f)) for f in fundamentals(ladder)}


def _cycle(ladder: Mapping[str, Any]) -> bool:
    parents: dict[str, set[str]] = {}
    for child, parent in _edges(ladder):
        parents.setdefault(child, set()).add(parent)
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        found = any(visit(p) for p in parents.get(node, ()))
        state[node] = 2
        return found

    return any(visit(n) for n in list(parents))


def _ladder_problems(ladder: Mapping[str, Any], criteria: list[str]) -> list[str]:
    objectives = _objective_ids(ladder)
    out = [f"ladder: objectives[{i}] has no string id" for i, o in enumerate(_maps(ladder.get("objectives")))
           if not isinstance(o.get("id"), str)]
    out += [f"ladder: {o} is declared both as an objective and as a criterion; a criterion is a "
            "leaf that refines an objective, never one itself" for o in objectives if o in criteria]
    out += [f"ladder: objective {o} is declared twice" for o in sorted(set(objectives))
            if objectives.count(o) > 1]
    found = leaves(ladder)
    out += [f"ladder: criterion {c} is not a leaf of the ladder; every criterion refines an objective"
            for c in criteria if c not in found or c in objectives]
    out += [f"ladder: leaf {n} is not a proposed criterion; refine it further or propose it"
            for n in sorted(found - set(criteria))]
    out += [f"ladder: edge {a} -> {b} refines {b}, which is not a declared objective"
            for a, b in _edges(ladder) if b not in objectives]
    parents: dict[str, list[str]] = {}
    for child, parent in _edges(ladder):
        parents.setdefault(child, []).append(parent)
    out += [f"ladder: {c} refines {', '.join(ps)}; a node refines one objective, or it is counted "
            "in two groups and weighs double" for c, ps in parents.items() if len(set(ps)) > 1]
    if _cycle(ladder):
        out.append("ladder: a chain of 'why is that important?' loops back on itself")
    return out


def _rejected_problems(rejected: list[Mapping[str, Any]], by_id: Mapping[str, Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for i, r in enumerate(rejected):
        reason, label = r.get("reason"), r.get("label")
        if not isinstance(label, str) or not label.strip():
            out.append(f"rejected[{i}]: has no label")
            continue
        if reason not in REJECT_REASONS:
            out.append(f"rejected[{i}]: reason {reason!r} is not one of {', '.join(REJECT_REASONS)}")
        elif reason == "merged-into" and r.get("mergedInto") not in by_id:
            out.append(f"rejected[{i}]: merged-into names no proposed criterion ({r.get('mergedInto')!r})")
        elif reason == "means-objective":
            serves = r.get("serves") if isinstance(r.get("serves"), list) else []
            if not serves or any(s not in by_id for s in serves):
                out.append(f"rejected[{i}]: a means objective names the criteria it serves ({serves!r})")
            for s in serves:
                exclusions = (by_id.get(s, {}).get("definition") or {}).get("exclusions")
                entries = [e for e in exclusions if isinstance(e, str)] if isinstance(exclusions, list) else []
                if s in by_id and not any(e.lower().startswith(label.strip().lower() + ":") for e in entries):
                    out.append(f"rejected[{i}]: no exclusion of {s} begins with the means objective's "
                               f"label {label!r} and a colon")
    return out


def proposal_problems(proposal: Mapping[str, Any]) -> list[str]:
    """Every way a criteria proposal breaks its own ladder, each stated with the fix.

    Never raises on a malformed proposal: what cannot be read is reported.

    >>> proposal_problems({"ladder": {"objectives": [{"id": "o", "text": "t"}],
    ...                               "edges": [{"from": "a", "to": "o"}]},
    ...                    "criteria": [{"id": "a", "definition": {"exclusions": ["x"],
    ...                                  "missingRules": [{"when": "w", "code": "not-evidenced"}]}},
    ...                                 {"id": "b"}],
    ...                    "rejected": [], "overlaps": [],
    ...                    "groups": [{"objective": "o", "criteria": ["a"], "size": 1}],
    ...                    "provenance": [{"criterionId": "a", "source": "agent-proposed"}]})  # doctest: +NORMALIZE_WHITESPACE
    ['criteria: b has no exclusions; name at least what it is not about',
     'criteria: b has no missingRules; say when a cell is a blank rather than a score',
     'ladder: criterion b is not a leaf of the ladder; every criterion refines an objective',
     'provenance: criterion b has no provenance']
    """
    ladder = _ladder(proposal)
    criteria_maps = _maps(proposal.get("criteria"))
    criteria = [c["id"] for c in criteria_maps if isinstance(c.get("id"), str)]
    by_id = {c["id"]: c for c in criteria_maps if isinstance(c.get("id"), str)}
    out = [f"criteria: {c} is proposed twice" for c in sorted(set(criteria)) if criteria.count(c) > 1]
    for c in criteria_maps:
        definition = c.get("definition") if isinstance(c.get("definition"), Mapping) else {}
        for field, why in (("exclusions", "name at least what it is not about"),
                           ("missingRules", "say when a cell is a blank rather than a score")):
            if not (isinstance(definition.get(field), list) and definition[field]):
                out.append(f"criteria: {c.get('id')} has no {field}; {why}")

    out += _ladder_problems(ladder, criteria)
    out += _rejected_problems(_maps(proposal.get("rejected")), by_id)

    overlaps = _maps(proposal.get("overlaps"))
    flagged = set()
    for o in overlaps:
        pair = o.get("criteria") if isinstance(o.get("criteria"), list) else []
        # Two *different* criteria: one named twice overlaps with nothing (#195).
        if len(pair) != 2 or not all(isinstance(c, str) and c in by_id for c in pair) \
                or pair[0] == pair[1] or o.get("via") not in _nodes(ladder):
            out.append(f"overlaps: {pair!r} via {o.get('via')!r} is not a pair of criteria on the ladder")
            continue
        flagged.add((*sorted(pair), o.get("via")))
        if not o.get("probe"):
            out.append(f"overlaps: {pair!r} carries no indifference question for the user")
    out += [f"overlaps: {a} and {b} both refine {p} and are not flagged; ask the indifference "
            "question at step 4" for a, b, p in sorted(sibling_pairs(ladder, criteria) - flagged)]

    reported = {g.get("objective"): g for g in _maps(proposal.get("groups"))}
    for objective, size in group_sizes(ladder).items():
        group = reported.get(objective)
        listed = group.get("criteria") if group and isinstance(group.get("criteria"), list) else []
        if group is None:
            out.append(f"groups: fundamental objective {objective} is not reported with its size")
        elif group.get("size") != size or set(map(str, listed)) != _descendant_leaves(ladder, objective):
            out.append(f"groups: {objective} has {size} criteria under it on the ladder; the "
                       f"report says {group.get('size')!r}")

    given = {p.get("criterionId"): p for p in _maps(proposal.get("provenance"))}
    for c in criteria:
        p = given.get(c)
        if p is None:
            out.append(f"provenance: criterion {c} has no provenance")
        elif p.get("source") not in PROVENANCE:
            out.append(f"provenance: criterion {c} has source {p.get('source')!r}, not one of "
                       f"{', '.join(PROVENANCE)}")
        elif p.get("source") == "user-stated" and not p.get("quote"):
            out.append(f"provenance: criterion {c} is user-stated and quotes nothing the user said")
    return out


def rejection_record(
    label: str, code: str, reason: str, *, merged_into: str | None = None,
    proposed_by: str | None = None, at: str | None = None,
) -> dict[str, Any]:
    """One ``rejectedCriteria`` entry, in the pinned schema's shape, for an ADR-0016 reject code.

    >>> rejection_record("Brand", "means-objective", "serves reliability")["reason"]
    'means-objective: serves reliability'
    >>> rejection_record("Noise", "merged-into", "same as Quiet", merged_into="quiet")["reasonCode"]
    'merged'
    """
    if code not in REJECT_REASON_CODES:
        raise ValueError(f'unknown reject code "{code}". Known: {", ".join(REJECT_REASONS)}.')
    record: dict[str, Any] = {
        "label": label, "reason": f"{code}: {reason}", "reasonCode": REJECT_REASON_CODES[code],
    }
    if merged_into is not None:
        record["mergedIntoId"] = merged_into
    if proposed_by is not None:
        record["proposedBy"] = proposed_by
    if at is not None:
        record["at"] = at
    return record
