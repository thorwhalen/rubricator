"""Bringing in a comparanda analysis made elsewhere, as an analysis this store can read (#246).

A document someone else produced is one merged file; the store keeps a frame and
one file per contributor, merged on read. Importing is the split, done once, with
every check on the way in rather than on some later read:

1. **Validated at the boundary** against comparanda's published schema: a document
   the companion refuses is not stored at all.
2. **Split by who stands behind each assertion.** An assertion's contributor is its
   author's principal (a persona's ``principalId``, else the author itself). The
   contributor's own author record, and personas whose ids are prefixed with it,
   travel in that contributor's file; every other author stays in the frame. Each
   ``procedures`` / ``rounds`` record goes with the contributors whose assertions
   point at it, because the merge namespaces those references per contributor.
   A cell with no assertions stays in the frame as it is.
3. **Refused, naming why, wherever the merge would refuse**: the split is merged on
   trial before anything is written, and what the merge cannot represent -- a
   ``supersededBy`` that crosses contributors, a principal that is not a usable id
   -- is refused with what to change.

Nothing is written unless all of it can be. The analysis is stored as it came:
its frame is not confirmed here, so a later write refuses until someone confirms
it (ADR-0005), while every read -- the audit's -- works at once.

Assertion ids are namespaced on read like any contributor's (``pat:s1``); an id that
already carries its contributor's prefix -- a document a store merged and exported --
has it taken off first, so it reads back as it was and not as ``pat:pat:s1``. No
clock, no model.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from rubricator.independence import principal
from rubricator.merge import merge_contributions
from rubricator.store import AnalysisStore

__all__ = ["analysis_import"]

_REFUSED = "refused, nothing was written: "
_PASS_FIELDS = ("procedures", "rounds")
_PASS_REFS = {"procedures": "procedureId", "rounds": "roundId"}
#: The cell fields the merge carries from a contribution; any other would be lost on read.
_CELL_FIELDS = frozenset({"alternativeId", "criterionId", "measure", "assertions", "reduction"})


def analysis_import(
    store: AnalysisStore,
    *,
    document: Mapping[str, Any],
    analysis_id: str | None = None,
) -> dict[str, Any]:
    """Store a comparanda ``document`` made elsewhere as analysis ``analysis_id`` (default: its own ``id``)."""
    from rubricator.tools.analysis import _as_stored, _contract

    if not isinstance(document, Mapping):
        raise ValueError(_REFUSED + "the document is not a JSON object.")
    document = _as_stored(copy.deepcopy(dict(document)))
    refusals = _contract().refusals(document)
    if refusals:
        raise ValueError(_REFUSED + "the document is not one comparanda accepts: " + "; ".join(refusals))
    analysis_id = analysis_id if analysis_id is not None else document.get("id")
    store.check_id(analysis_id)
    if store.exists(analysis_id):
        raise ValueError(
            _REFUSED + f'an analysis "{analysis_id}" is already here. Import under another '
            "analysis_id; an import never merges into, or replaces, an existing analysis.")

    frame, contributions = _split(document, store.check_id)
    try:
        merge_contributions({**frame, "id": analysis_id}, sorted(contributions.items()))
    except ValueError as error:
        raise ValueError(_REFUSED + f"the split would not merge: {error}") from None

    store.put_frame(analysis_id, {**frame, "id": analysis_id})
    for contributor_id, contribution in sorted(contributions.items()):
        store.put_contribution(analysis_id, contributor_id, contribution)
    assertions = {c: sum(len(cell["assertions"]) for cell in f["cells"]) for c, f in contributions.items()}
    return {
        "analysisId": analysis_id,
        "contributors": [{"contributorId": c, "assertions": assertions[c]} for c in sorted(contributions)],
        "summary": (
            f'Imported "{analysis_id}": {len(document.get("alternatives", []))} alternative(s), '
            f'{len(document.get("criteria", []))} criteria, {sum(assertions.values())} assertion(s) '
            f"from {len(contributions)} contributor(s) ({', '.join(sorted(contributions)) or 'none'}). "
            "The frame is not confirmed here: reads work now, writes wait for a confirmation."
        ),
    }


def _unprefixed(who: str, record: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """``record`` with ``who:`` taken off those ids, so an exported analysis imports as it was.

    The merge namespaces a contributor's ids on read; a document a store already merged
    carries them namespaced, and importing it as given would read back as ``pat:pat:s1``.
    """
    out = dict(record)
    for field in fields:
        value = out.get(field)
        if isinstance(value, str) and value.startswith(f"{who}:") and len(value) > len(who) + 1:
            out[field] = value[len(who) + 1:]
    return out


def _split(document: dict[str, Any], check_id) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """The frame, and each contributor's file, from one merged document."""
    authors = {a["id"]: a for a in document.get("authors", [])}
    owner_of: dict[str, str] = {}  # assertion id per contributor, for supersededBy
    contributions: dict[str, dict[str, Any]] = {}
    unowned: list[dict[str, Any]] = []  # cells nobody asserted in: the frame keeps them as they are
    for cell in document.get("cells", []):
        if not cell.get("assertions"):
            unowned.append(cell)
            continue
        dropped = sorted(set(cell) - _CELL_FIELDS)
        if dropped:
            raise ValueError(
                _REFUSED + f"cell {cell['alternativeId']}/{cell['criterionId']}/{cell['measure']} "
                f"carries {', '.join(dropped)}, which a contributor's cell cannot hold: the merge "
                "would drop it on read. Remove it, or record what it says as an assertion.")
        for assertion in cell.get("assertions", []):
            if assertion["authorId"] not in authors:
                raise ValueError(
                    _REFUSED + f'assertion "{assertion["id"]}" names author "{assertion["authorId"]}", '
                    "who is not in the document's authors. Declare the author, so the claim is "
                    "attributed to someone a reader can see.")
            who = principal(authors, assertion["authorId"])
            if not isinstance(who, str):
                raise ValueError(_REFUSED + f'assertion "{assertion["id"]}" has no usable author.')
            try:
                check_id(who)
            except ValueError:
                raise ValueError(
                    _REFUSED + f'assertion "{assertion["id"]}" is by "{who}", which cannot name a '
                    "contributor's file (an id is 1 to 64 letters, digits, \"-\" or \"_\"). Rename "
                    "that author, or give it a principalId that is such an id.") from None
            assertion = _unprefixed(who, assertion, ("id", "supersededBy", *_PASS_REFS.values()))
            if assertion["id"] in owner_of.get(who, set()):
                raise ValueError(
                    _REFUSED + f'contributor "{who}" uses assertion id "{assertion["id"]}" twice.')
            owner_of.setdefault(who, set()).add(assertion["id"])
            file = contributions.setdefault(who, {"authors": [], "cells": {}})
            key = (cell["alternativeId"], cell["criterionId"], cell["measure"])
            target = file["cells"].setdefault(key, {**{k: v for k, v in cell.items() if k != "assertions"},
                                                    "assertions": []})
            target["assertions"].append(assertion)

    for who, ids in owner_of.items():
        for cell in contributions[who]["cells"].values():
            for assertion in cell["assertions"]:
                later = assertion.get("supersededBy")
                if later and later not in ids:
                    raise ValueError(
                        _REFUSED + f'assertion "{assertion["id"]}" by "{who}" is superseded by '
                        f'"{later}", which is not one of "{who}"\'s assertions. A contributor '
                        "supersedes only their own; record the newer claim as a separate assertion.")

    moved: set[str] = set()
    for who, file in contributions.items():
        mine = [a for a in authors.values() if a["id"] == who or (
            a.get("principalId") == who and a["id"].startswith(f"{who}:"))]
        file["authors"] = mine
        moved |= {a["id"] for a in mine}
        file["cells"] = list(file["cells"].values())
        for field in _PASS_FIELDS:
            used = {a.get(_PASS_REFS[field]) for c in file["cells"] for a in c["assertions"]}
            file[field] = [e for e in (_unprefixed(who, e, ("id",)) for e in document.get(field, []))
                           if e.get("id") in used]
            ids = [e["id"] for e in file[field]]
            twice = sorted({i for i in ids if ids.count(i) > 1})
            if twice:
                raise ValueError(
                    _REFUSED + f'contributor "{who}" would hold two {field} records with id '
                    f'{", ".join(twice)} (one given as "{who}:{twice[0]}"): rename one, so each '
                    "assertion points at one record.")

    frame = {k: v for k, v in document.items() if k not in ("cells", *_PASS_FIELDS)}
    frame["authors"] = [a for a in document.get("authors", []) if a["id"] not in moved]
    frame["cells"] = unowned
    claimed = {(who, e["id"]) for who, f in contributions.items() for field in _PASS_FIELDS
               for e in f[field]}
    for field in _PASS_FIELDS:
        rest = [e for e in document.get(field, []) if not any(
            (who, _unprefixed(who, e, ("id",))["id"]) in claimed for who in contributions)]
        if rest:
            frame[field] = rest
    return frame, contributions
