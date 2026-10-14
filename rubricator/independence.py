"""The independence ladder, read off what an assertion set records (ADR-0018, #99).

The stored field is the companion's closed ``independence`` enum; the *policy*
ladder ADR-0018 argues in is ``in-session < fresh-session < distinct-model <
distinct-human``. This module is the one place the two meet, and it is pure: a
function of stored assertions and their authors, so a report, an aggregate and
a disclosure all label an assertion set the same way.

Three rules it holds, each because the obvious reading is worse:

1. **Absent is the bottom rung, never a default up.** An assertion that records
   no rung is ``unrecorded`` and ranks below ``in-session``: unknown is treated
   as not independent, so nothing is ever quietly promoted.
2. **An agreement statistic is labelled by the lowest rung present** in the set
   it was computed over. Four in-session draws and one human are *in-session*:
   one independent rater does not launder four dependent draws.
3. **``independent`` on an agent is not independence.** Confident errors are
   partly shared even across providers, so ``independent`` on agent-authored
   assertions reads ``distinct-model`` and the label says *not independent
   raters*. And the claim is refused when the cell itself shows it false
   (:func:`distinct_model_problem`): a fresh session of the **same** model is
   ``resampled``. Where a model is simply unrecorded the claim cannot be shown
   false, so it stands, and the label says the models are unrecorded.

>>> a = lambda i, rung: {"id": i, "authorId": "bot", "independence": rung}
>>> agreement([a("1", "shared-context"), a("2", "resampled")], {"bot": {"kind": "agent"}})["rung"]
'in-session'
>>> agreement([a("1", "independent")], {"bot": {"kind": "agent"}}) is None
True
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

__all__ = [
    "RUNGS",
    "UNRECORDED",
    "agreement",
    "agent_model",
    "distinct_model_problem",
    "policy_rung",
    "lowest_rung",
]

UNRECORDED = "unrecorded"

#: The policy ladder, weakest first. ``unrecorded`` is below the ladder on purpose.
RUNGS: Sequence[str] = (UNRECORDED, "in-session", "fresh-session", "distinct-model", "distinct-human")

#: What a set whose weakest member is at each rung may honestly be called.
#: Content of the report, so a reviewer finds the wording in one place.
LABELS: Mapping[str, str] = {
    UNRECORDED: (
        "not labelled: at least one assertion records no independence rung, so it is treated "
        "as not independent"
    ),
    "in-session": "agent self-consistency (in-session draws); not inter-rater agreement",
    "fresh-session": (
        "test-retest reliability across fresh sessions of one model; not inter-rater agreement"
    ),
    "distinct-model": (
        "agreement across distinct models; not independent raters, because confident errors "
        "are partly shared across providers"
    ),
    "distinct-human": "inter-rater agreement across distinct humans",
}


def agent_model(author: Mapping[str, Any] | None) -> str | None:
    """The model id an agent author records, or ``None`` when it does not."""
    model = ((author or {}).get("agent") or {}).get("model")
    return model if isinstance(model, str) and model else None


def policy_rung(assertion: Mapping[str, Any], authors: Mapping[str, Mapping[str, Any]]) -> str | None:
    """The policy rung one assertion earns, or ``None`` for ``consensus``.

    ``consensus`` is an agreed value, not an observation, so it sits off the
    ladder and a set is never labelled by it.

    >>> policy_rung({"independence": "independent", "authorId": "a"}, {"a": {"kind": "human"}})
    'distinct-human'
    >>> policy_rung({"independence": "independent", "authorId": "a"}, {"a": {"kind": "agent"}})
    'distinct-model'
    >>> policy_rung({"authorId": "a"}, {})
    'unrecorded'
    """
    rung = assertion.get("independence")
    if not rung:
        return UNRECORDED
    if rung == "consensus":
        return None
    if rung == "shared-context":
        return "in-session"
    if rung in ("resampled", "perturbed"):
        return "fresh-session"
    if rung == "independent":
        kind = (authors.get(assertion.get("authorId")) or {}).get("kind")
        return "distinct-human" if kind == "human" else "distinct-model"
    return UNRECORDED


def lowest_rung(rungs: Iterable[str | None]) -> str | None:
    """The weakest of ``rungs`` on the ladder (``None`` entries are off it)."""
    ranked = [r for r in rungs if r is not None]
    return min(ranked, key=RUNGS.index) if ranked else None


def agreement(
    assertions: Sequence[Mapping[str, Any]], authors: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any] | None:
    """How an assertion set may be described: its lowest rung and the wording that goes with it.

    ``None`` for fewer than two observations: there is nothing to agree *with*.
    The counts are per rung so a reader sees the mix the label summarises.
    """
    rungs = [policy_rung(a, authors) for a in assertions]
    observed = [r for r in rungs if r is not None]
    if len(observed) < 2:
        return None
    lowest = lowest_rung(observed)
    label = LABELS[lowest]
    if lowest == "distinct-model" and any(
        policy_rung(a, authors) == "distinct-model" and agent_model(authors.get(a.get("authorId"))) is None
        for a in assertions
    ):
        label += "; at least one of those agents records no model, so the claim is unchecked"
    return {
        "rung": lowest,
        "label": label,
        "counts": [{"rung": r, "count": observed.count(r)} for r in RUNGS if r in observed],
    }


def distinct_model_problem(
    assertion: Mapping[str, Any],
    live: Sequence[Mapping[str, Any]],
    authors: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Why an agent's ``independent`` claim does not hold in this cell, or ``None``.

    The claim is that this agent is a separate assessor from every other agent
    beside it. It is refused only when the cell shows it false: the same author,
    or a recorded model another agent beside it shares. An unrecorded model
    cannot be shown to match, so it is not refused (it is labelled instead, see
    :func:`agreement`). Humans are separate assessors by kind and are not compared.

    >>> authors = {"x": {"kind": "agent", "agent": {"name": "r", "model": "m1"}},
    ...            "y": {"kind": "agent", "agent": {"name": "r", "model": "m1"}}}
    >>> mine = {"id": "1", "authorId": "x", "independence": "independent"}
    >>> distinct_model_problem(mine, [mine, {"id": "2", "authorId": "y"}], authors)
    'this agent shares its model "m1" with "y"; a fresh session of the same model is "resampled"'
    """
    if assertion.get("independence") != "independent":
        return None
    me = authors.get(assertion.get("authorId")) or {}
    if me.get("kind") != "agent":
        return None
    model = agent_model(me)
    for other in live:
        if other.get("id") == assertion.get("id"):
            continue
        theirs_id = other.get("authorId")
        theirs = authors.get(theirs_id) or {}
        if theirs_id == assertion.get("authorId"):
            return (
                f'"{theirs_id}" also scored this cell, and one author is one model: another '
                'draw of it is "resampled"'
            )
        if theirs.get("kind") != "agent":
            continue
        if model is not None and agent_model(theirs) == model:
            return (
                f'this agent shares its model "{model}" with "{theirs_id}"; a fresh session of '
                'the same model is "resampled"'
            )
    return None
