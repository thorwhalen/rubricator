"""The value-free read a re-score needs: ``measures_claim_ids`` (#294).

A re-score replaces a writer's earlier claim (``measures_write`` with
``supersedes``), files the new draw under the next round, and writes as the
contributor who made the claim. All three facts are about *who* claimed *what
id* in *which round*, and none is about what the claim said. So this read hands
back exactly those -- per cell of one criterion, the live claims' ids, their
contributor and their round, and per contributor its latest round -- and never
a value, a justification, evidence, a missingness code, or a count by kind. A
re-scoring generation can then make every decision the write needs with the
earlier scores still withheld (``rescore-criterion``, ADR-0018).

It is also the seam #102 asks for ("one cell's material for re-scoring without
its live assertions"): the material a re-score reads grows here, as output
fields, without a second verb.

Pure: a projection of the stored contributions, no clock, no model.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.rules import live_assertions
from rubricator.store import AnalysisStore

__all__ = ["measures_claim_ids"]


def _live(rows: Any) -> list[Mapping[str, Any]]:
    return [r for r in rows or [] if isinstance(r, Mapping) and not r.get("tombstoned")]


def _round_index(contribution: Mapping[str, Any]) -> dict[str, int]:
    """Round id -> its number, from the contribution's ``rounds[]``."""
    return {
        r["id"]: r["index"]
        for r in contribution.get("rounds", []) or []
        if isinstance(r, Mapping) and isinstance(r.get("index"), int) and "id" in r
    }


def measures_claim_ids(
    store: AnalysisStore,
    *,
    analysis_id: str,
    criterion_id: str,
    alternative_ids: Sequence[str] | None = None,
    contributor_id: str | None = None,
) -> dict[str, Any]:
    """Who holds which live claim, in which round, on one criterion's cells -- and never what it says.

    For each cell of ``criterion_id`` (every live alternative, or the ones in
    ``alternative_ids``), the live claims' ``assertionId``, ``contributorId`` and
    ``round`` (``None`` for a claim written with no round). For each contributor
    with a live claim there, or ``contributor_id`` when given, its ``latestRound``
    over the whole analysis: a re-score is filed under the round after it.
    ``contributor_id`` narrows the claims to that contributor's own.

    An unknown analysis, criterion or alternative is refused with ``KeyError``.
    """
    frame = store.frame(analysis_id)
    criteria = {c["id"]: c for c in _live(frame.get("criteria"))}
    if criterion_id not in criteria:
        raise KeyError(
            f'criterion "{criterion_id}" is not a live criterion of "{analysis_id}"; the '
            f"criteria are {', '.join(sorted(criteria)) or 'none yet'}."
        )
    alternatives = [a["id"] for a in _live(frame.get("alternatives"))]
    if alternative_ids is not None:
        unknown = sorted(set(alternative_ids) - set(alternatives))
        if unknown:
            raise KeyError(
                f"alternatives {', '.join(unknown)} are not live alternatives of "
                f'"{analysis_id}"; the alternatives are {", ".join(alternatives)}.'
            )
        wanted = set(alternative_ids)
        alternatives = [a for a in alternatives if a in wanted]
    measures = [m["name"] for m in frame.get("measures", []) if "name" in m] or ["score"]

    contributions, skipped = store.mergeable_contributions(analysis_id, frame=frame)
    if contributor_id is not None:
        contributions = [(cid, c) for cid, c in contributions if cid == contributor_id]
    latest: dict[str, int | None] = {}
    claims: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cid, contribution in contributions:
        rounds = _round_index(contribution)
        latest[cid] = max(rounds.values(), default=None)
        for cell in contribution.get("cells", []) or []:
            if cell.get("criterionId") != criterion_id:
                continue
            key = (cell.get("alternativeId"), cell.get("measure", "score"))
            for a in live_assertions(cell):
                claims.setdefault(key, []).append({
                    "assertionId": a["id"],
                    "contributorId": cid,
                    "round": rounds.get(a.get("roundId")),
                })

    cells = [
        {
            "alternativeId": alt,
            "measure": measure,
            "liveClaims": sorted(
                claims.get((alt, measure), []),
                key=lambda c: (c["contributorId"], c["assertionId"]),
            ),
        }
        for alt in alternatives
        for measure in measures
    ]
    holders = sorted({c["contributorId"] for cell in cells for c in cell["liveClaims"]})
    named = holders if contributor_id is None else [contributor_id]
    contributors = [
        {"contributorId": cid, "latestRound": latest.get(cid)} for cid in named
    ]

    held = sum(1 for cell in cells if cell["liveClaims"])
    several = [
        cell["alternativeId"]
        for cell in cells
        if len({c["contributorId"] for c in cell["liveClaims"]}) < len(cell["liveClaims"])
    ]
    rounds_text = "; ".join(
        f"{c['contributorId']}'s latest round is "
        + (f"{c['latestRound']}, so a re-score is round {c['latestRound'] + 1}"
           if c["latestRound"] is not None else "unrecorded")
        for c in contributors
    )
    summary = (
        f'"{criterion_id}": {len(cells)} cell(s) in scope, {held} with a live claim'
        + (f" (of {contributor_id})" if contributor_id is not None else "")
        + (f"; {rounds_text}" if rounds_text else "")
        + (f"; several live claims of one contributor in: {', '.join(several)} -- ask which "
           "a re-score replaces" if several else "")
        + (f"; {len(skipped)} stored file(s) could not be merged and were left out (see "
           "skipped)" if skipped else "")
        + ". No value, justification, evidence or code is returned: reading this keeps the "
        "prior withheld."
    )
    return {
        "analysisId": analysis_id,
        "criterionId": criterion_id,
        "cells": cells,
        "contributors": contributors,
        "skipped": skipped,
        "summary": summary,
    }
