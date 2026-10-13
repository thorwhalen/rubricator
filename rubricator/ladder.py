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
``criteria_set`` takes; the rest have no slot in the companion contract yet and
ride beside it):

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

#: Who a proposed criterion came from. ADR-0006's source-type rule, one level up.
PROVENANCE: tuple[str, ...] = ("user-stated", "agent-proposed")


def _edges(ladder: Mapping[str, Any]) -> list[tuple[str, str]]:
    return [(e.get("from"), e.get("to")) for e in ladder.get("edges", []) if isinstance(e, Mapping)]


def children(ladder: Mapping[str, Any]) -> dict[str, list[str]]:
    """Each node's direct refinements, in edge order."""
    out: dict[str, list[str]] = {}
    for child, parent in _edges(ladder):
        out.setdefault(parent, []).append(child)
    return out


def _nodes(ladder: Mapping[str, Any]) -> set[str]:
    objectives = {o.get("id") for o in ladder.get("objectives", []) if isinstance(o, Mapping)}
    return objectives | {n for edge in _edges(ladder) for n in edge}


def leaves(ladder: Mapping[str, Any]) -> set[str]:
    """The nodes nothing refines: these, and only these, are the criteria."""
    refined = set(children(ladder))
    return {n for n in _nodes(ladder) if n not in refined}


def fundamentals(ladder: Mapping[str, Any]) -> list[str]:
    """The objectives that refine nothing: where every "why is that important?" chain ends."""
    refining = {child for child, _ in _edges(ladder)}
    return [o["id"] for o in ladder.get("objectives", [])
            if isinstance(o, Mapping) and o.get("id") not in refining]


def sibling_pairs(ladder: Mapping[str, Any], criteria: Iterable[str]) -> set[tuple[str, str, str]]:
    """``(a, b, parent)`` for every two criteria that refine the same objective directly.

    These are the double-counting candidates the ladder finds by construction.
    Each must reach the step-4 checkpoint as an indifference question; the
    ladder cannot say whether they overlap, only that they might.
    """
    wanted = set(criteria)
    return {
        (*sorted((a, b)), parent)
        for parent, kids in children(ladder).items()
        for a, b in combinations([k for k in kids if k in wanted], 2)
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


def proposal_problems(proposal: Mapping[str, Any]) -> list[str]:
    """Every way a criteria proposal breaks its own ladder, each stated with the fix.

    >>> proposal_problems({"ladder": {"objectives": [{"id": "o", "text": "t"}],
    ...                               "edges": [{"from": "a", "to": "o"}]},
    ...                    "criteria": [{"id": "a"}, {"id": "b"}], "rejected": [],
    ...                    "overlaps": [], "groups": [{"objective": "o", "criteria": ["a"], "size": 1}],
    ...                    "provenance": [{"criterionId": "a", "source": "agent-proposed"}]})
    ['ladder: criterion b is not a leaf of the ladder; every criterion refines an objective', 'provenance: criterion b has no provenance']
    """
    ladder = proposal.get("ladder") or {}
    criteria = [c.get("id") for c in proposal.get("criteria", []) if isinstance(c, Mapping)]
    objectives = {o.get("id") for o in ladder.get("objectives", []) if isinstance(o, Mapping)}
    out: list[str] = []

    found = leaves(ladder)
    out += [f"ladder: criterion {c} is not a leaf of the ladder; every criterion refines an objective"
            for c in criteria if c not in found]
    out += [f"ladder: leaf {n} is not a proposed criterion; refine it further or propose it"
            for n in sorted(found - set(criteria))]
    out += [f"ladder: edge {a} -> {b} refines {b}, which is not a declared objective"
            for a, b in _edges(ladder) if b not in objectives]
    if _cycle(ladder):
        out.append("ladder: a chain of 'why is that important?' loops back on itself")

    for i, r in enumerate(proposal.get("rejected", [])):
        reason = r.get("reason") if isinstance(r, Mapping) else None
        if reason not in REJECT_REASONS:
            out.append(f"rejected[{i}]: reason {reason!r} is not one of {', '.join(REJECT_REASONS)}")
        elif reason == "merged-into" and r.get("mergedInto") not in criteria:
            out.append(f"rejected[{i}]: merged-into names no proposed criterion ({r.get('mergedInto')!r})")
        elif reason == "means-objective":
            serves = r.get("serves") or []
            if not serves or any(s not in criteria for s in serves):
                out.append(f"rejected[{i}]: a means objective names the criteria it serves ({serves!r})")
            by_id = {c.get("id"): c for c in proposal.get("criteria", []) if isinstance(c, Mapping)}
            label = str(r.get("label", "")).lower()
            for s in serves:
                exclusions = " ".join((by_id.get(s, {}).get("definition") or {}).get("exclusions", []))
                if s in by_id and label not in exclusions.lower():
                    out.append(f"rejected[{i}]: means objective {r.get('label')!r} is not named in "
                               f"the exclusions of {s}, the criterion it serves")

    flagged = {(*sorted(o.get("criteria", [])), o.get("via"))
               for o in proposal.get("overlaps", []) if isinstance(o, Mapping)}
    out += [f"overlaps: {a} and {b} both refine {p} and are not flagged; ask the indifference "
            "question at step 4" for a, b, p in sorted(sibling_pairs(ladder, criteria) - flagged)]
    for o in proposal.get("overlaps", []):
        pair = o.get("criteria", []) if isinstance(o, Mapping) else []
        if len(pair) != 2 or not all(c in criteria for c in pair) or o.get("via") not in _nodes(ladder):
            out.append(f"overlaps: {pair!r} via {o.get('via')!r} is not a pair of criteria on the ladder")
        elif not o.get("probe"):
            out.append(f"overlaps: {pair!r} carries no indifference question for the user")

    sizes = group_sizes(ladder)
    reported = {g.get("objective"): g for g in proposal.get("groups", []) if isinstance(g, Mapping)}
    for objective, size in sizes.items():
        group = reported.get(objective)
        if group is None:
            out.append(f"groups: fundamental objective {objective} is not reported with its size")
        elif group.get("size") != size or set(group.get("criteria", [])) != _descendant_leaves(ladder, objective):
            out.append(f"groups: {objective} has {size} criteria under it on the ladder; the "
                       f"report says {group.get('size')!r}")

    given = {p.get("criterionId"): p for p in proposal.get("provenance", []) if isinstance(p, Mapping)}
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
