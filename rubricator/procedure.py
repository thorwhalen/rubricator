"""The procedure record: what a scoring pass did, written by the tools from what they saw (ADR-0018, #99).

The record exists so the variance disclosure describes what actually happened and
not what the defaults say should have happened. So the model is never asked to
*author* it. A caller of ``measures_write`` passes a few closed facts about the
pass (traversal, reduction, plan seed, pass number, whether the draw saw the
prior, same session or fresh) and the tools do the rest:

- ``repeats``, ``startedAt`` and ``finishedAt`` are **counted from the stored
  assertions**, never asserted;
- the model id, prompt version and run id are read off the signing **author**;
- the seeds are read off the assertions' ``perturbation`` records;
- the independence rung of a draw is **derived** from the declared facts when the
  caller names none, and is refused when the caller's claim contradicts them.

It lands in the comparanda v1 slots that already exist: ``procedures[]``,
``rounds[]`` and the assertion's ``procedureId`` / ``roundId``, so it needs no
schema request. A fact v1 has no field for (the model id, the prompt version, the
seeds, whether the prior was withheld) is written, in words, to the entry's
``notes`` and the round's ``label``; the fields it does have carry the rest.

Pure: functions of dicts, no store, no clock. The write path is
:func:`rubricator.tools.analysis.measures_write`.

>>> facts = {"traversal": "cell-wise", "reduction": "lower-median", "round": 2, "seed": 7,
...          "session": "fresh", "prior": "withheld"}
>>> bot = {"id": "bot", "kind": "agent", "agent": {"name": "r", "model": "m1", "promptVersion": "v3"}}
>>> procedure_id(facts, bot)
'p-c1dd33d0'
>>> round_entry(facts, "bot")["feedback"]
'none'
>>> derived_rung(facts, has_perturbation=False)
'perturbed'
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "FACTS",
    "check_facts",
    "contradiction",
    "derived_rung",
    "procedure_id",
    "refresh_procedures",
    "round_entry",
    "round_id",
]

#: The facts a caller may state about a pass; everything else is counted or read.
FACTS = ("traversal", "reduction", "seed", "round", "session", "prior")

_FEEDBACK = {"withheld": "none", "shown": "full"}
_NOT_RECORDED = "not recorded"


def check_facts(facts: Any) -> None:
    """Refuse a malformed ``procedure`` argument, naming what is allowed."""
    if not isinstance(facts, Mapping):
        raise ValueError(f"procedure is an object with any of {', '.join(FACTS)}; got {facts!r}.")
    unknown = sorted(set(facts) - set(FACTS))
    if unknown:
        raise ValueError(
            f"procedure has unknown key(s) {', '.join(unknown)}; allowed: {', '.join(FACTS)}. "
            "The tools count the repeats and read the model and seeds themselves."
        )
    r = facts.get("round")
    if r is not None and (isinstance(r, bool) or not isinstance(r, int) or r < 1):
        raise ValueError(f"procedure.round is the pass number, 1 or more; got {r!r}.")
    for key, allowed in (("session", ("same", "fresh")), ("prior", tuple(_FEEDBACK))):
        if facts.get(key) is not None and facts[key] not in allowed:
            raise ValueError(f"procedure.{key} is one of {', '.join(allowed)}; got {facts[key]!r}.")


def procedure_id(facts: Mapping[str, Any], author: Mapping[str, Any]) -> str:
    """The id of the procedure a pass belongs to: the same declared run is the same entry.

    Keyed on what makes two passes *one procedure* -- traversal, reduction, and
    the model, prompt version and run that did them -- and not on the seed, the
    pass number, the session or the prior, which vary pass to pass inside one.
    """
    agent = author.get("agent") or {}
    key = [facts.get("traversal"), facts.get("reduction"), agent.get("model"),
           agent.get("promptVersion"), agent.get("runId"), author.get("id")]
    digest = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()
    return f"p-{digest[:8]}"


def round_id(facts: Mapping[str, Any]) -> str | None:
    return f"round-{facts['round']}" if facts.get("round") is not None else None


def round_entry(facts: Mapping[str, Any], contributor_id: str) -> dict[str, Any]:
    """The ``rounds[]`` entry for a pass: ``feedback`` is what the prior-handling fact says."""
    entry: dict[str, Any] = {
        "id": round_id(facts), "index": facts["round"], "attribution": "attributed",
    }
    label = []
    if facts.get("seed") is not None:
        label.append(f"seed {facts['seed']}")
    if facts.get("prior"):
        label.append(f"prior {facts['prior']}")
        entry["feedback"] = _FEEDBACK[facts["prior"]]
    label.append(f"{contributor_id}'s pass {facts['round']}")
    entry["label"] = ", ".join(label)
    return entry


def derived_rung(facts: Mapping[str, Any], *, has_perturbation: bool) -> str | None:
    """The rung a draw earns from the declared facts, or ``None`` when they say nothing.

    A draw that saw the prior, or shares the session, is ``shared-context``;
    a fresh session of the same model is ``resampled``, and ``perturbed`` when
    something deliberate was varied (a seeded order). Never ``independent``:
    only a distinct assessor is, and no pass fact can say that.
    """
    if facts.get("prior") == "shown" or facts.get("session") == "same":
        return "shared-context"
    if facts.get("session") == "fresh":
        return "perturbed" if has_perturbation or facts.get("seed") is not None else "resampled"
    return None


def contradiction(facts: Mapping[str, Any], independence: str | None) -> str | None:
    """Why a caller's stated rung contradicts the pass facts, or ``None``.

    Understating is always allowed ("shared-context" is the honest choice when
    unsure); only a claim the declared facts rule out is refused. A *fresh* session
    caps nothing here: it says nothing about whether the model differs, which is
    the cell's to show (``independent-agent-is-distinct``).
    """
    if independence in (None, "consensus", "shared-context"):
        return None
    if facts.get("prior") == "shown":
        cause = "the draw saw the prior"
    elif facts.get("session") == "same":
        cause = "the pass is declared the same session"
    else:
        return None
    return (
        f'independence "{independence}" contradicts the pass: {cause}, so the draw shares '
        'context with what came before. State "shared-context", or leave it out and the tools '
        "derive it."
    )


def refresh_procedures(
    contribution: dict[str, Any],
    *,
    facts: Mapping[str, Any],
    author: Mapping[str, Any],
    contributor_id: str,
) -> None:
    """Write the pass into the contribution's ``procedures[]`` and ``rounds[]``, counting what it holds.

    Idempotent: the same pass writes the same entries, and the counts are recomputed
    from every assertion stored under the procedure, so the record cannot drift from
    the draws it describes.
    """
    pid = procedure_id(facts, author)
    procedures = {p["id"]: p for p in contribution.get("procedures", [])}
    rounds = {r["id"]: r for r in contribution.get("rounds", [])}
    rid = round_id(facts)
    if rid is not None:
        entry = round_entry(facts, contributor_id)
        old = rounds.get(rid)
        if old is not None and old.get("feedback") != entry.get("feedback"):
            raise ValueError(
                f"refused, nothing was written: pass {facts['round']} was already recorded with "
                f"prior {'withheld' if old.get('feedback') == 'none' else 'shown'} and cannot be "
                "restated; a draw that saw the prior is a different pass, so give it the next "
                "round number."
            )
        rounds[rid] = {**(old or {}), **entry}
    procedures[pid] = _procedure(pid, facts, author, contribution, procedures.get(pid))
    contribution["procedures"] = [procedures[k] for k in sorted(procedures)]
    contribution["rounds"] = [rounds[k] for k in sorted(rounds, key=lambda k: (rounds[k]["index"], k))]
    for rid_, entry in rounds.items():
        times = sorted(a["at"] for _c, a in _draws(contribution) if a.get("roundId") == rid_)
        if times:
            entry["openedAt"], entry["closedAt"] = times[0], times[-1]


def _draws(contribution: Mapping[str, Any]):
    for cell in contribution.get("cells", []):
        for assertion in cell.get("assertions", []):
            yield cell, assertion


def _procedure(
    pid: str,
    facts: Mapping[str, Any],
    author: Mapping[str, Any],
    contribution: Mapping[str, Any],
    old: Mapping[str, Any] | None,
) -> dict[str, Any]:
    agent = author.get("agent") or {}
    mine = [(c, a) for c, a in _draws(contribution) if a.get("procedureId") == pid]
    per_cell: dict[tuple[str, str, str], int] = {}
    for cell, _a in mine:
        key = (cell["alternativeId"], cell["criterionId"], cell["measure"])
        per_cell[key] = per_cell.get(key, 0) + 1
    seeds = sorted({str(a["perturbation"]["seed"]) for _c, a in mine
                    if (a.get("perturbation") or {}).get("seed") is not None})
    rounds = sorted({a["roundId"] for _c, a in mine if a.get("roundId")})
    traversal = facts.get("traversal") or (old or {}).get("traversal")
    reduction = facts.get("reduction") or (old or {}).get("reduction")
    entry: dict[str, Any] = {
        "id": pid,
        "describedAs": (
            f"{traversal + ' traversal' if traversal else 'traversal ' + _NOT_RECORDED}; "
            f"{reduction + ' reduction' if reduction else 'reduction ' + _NOT_RECORDED}"
        ),
        "repeats": max(per_cell.values(), default=0),
        "notes": (
            f"model {agent.get('model', _NOT_RECORDED)}; prompt version "
            f"{agent.get('promptVersion', _NOT_RECORDED)}; run {agent.get('runId', _NOT_RECORDED)}; "
            f"seeds {', '.join(seeds) if seeds else _NOT_RECORDED}; rounds "
            f"{', '.join(rounds) if rounds else _NOT_RECORDED}. Counted and read by the tools from "
            "the stored draws; whether a pass saw the prior is the caller's statement, on the round."
        ),
    }
    if traversal:
        entry["traversal"] = traversal
    if reduction:
        entry["reduction"] = reduction
    times = sorted(a["at"] for _c, a in mine)
    if times:
        entry["startedAt"], entry["finishedAt"] = times[0], times[-1]
    return entry
