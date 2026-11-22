"""The value-free read a re-score needs: ``measures_rescore_context`` (#294).

A re-score replaces a writer's earlier claim (``measures_write`` with ``supersedes``),
files the new draw under the writer's next round, and writes as the contributor and
author who made the claim. All three facts are about *who* claimed *which id*, and none
is about what the claim said. So this read hands back exactly those -- per cell of one
criterion, the live claims' ids with their contributor and author, and per writer
(contributor and author) its latest round -- and never a value, a justification,
evidence, a missingness code, a per-claim round, or a count by kind. A re-scoring
generation can then make every decision the write needs with the earlier scores still
withheld (``rescore-criterion``, ADR-0018).

A writer is a contributor and one of its authors: a persona (``scorer:buyer`` under
``scorer``) writes into its principal's file, and its rounds are its own (ADR-0018), so
"yours" and "latest round" are per writer, never per file.

It is also the seam #102 asks for ("one cell's material for re-scoring without its live
assertions"): the material a re-score reads grows here, as output fields.

Pure: a projection of the stored contributions, no clock, no model.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.rules import live_assertions
from rubricator.store import AnalysisStore

__all__ = ["measures_rescore_context"]


def _live(rows: Any) -> list[Mapping[str, Any]]:
    return [r for r in rows or [] if isinstance(r, Mapping) and not r.get("tombstoned")]


def _latest_rounds(contribution: Mapping[str, Any]) -> dict[str, int]:
    """Each author's highest round number in the contribution, over every draw it made."""
    index = {
        r["id"]: r["index"]
        for r in contribution.get("rounds", []) or []
        if isinstance(r, Mapping) and isinstance(r.get("index"), int) and "id" in r
    }
    latest: dict[str, int] = {}
    for cell in contribution.get("cells", []) or []:
        for a in cell.get("assertions", []) or []:
            n = index.get(a.get("roundId"))
            if n is not None:
                who = a.get("authorId")
                latest[who] = max(n, latest.get(who, n))
    return latest


def measures_rescore_context(
    store: AnalysisStore,
    *,
    analysis_id: str,
    criterion_id: str,
    alternative_ids: Sequence[str] | None = None,
    contributor_id: str | None = None,
    author_id: str | None = None,
) -> dict[str, Any]:
    """Who holds which live claim on one criterion's cells, and each writer's latest round -- never what a claim says.

    For each cell of ``criterion_id`` (every live alternative, or those in
    ``alternative_ids``, per measure), every live claim's ``assertionId``,
    ``contributorId`` and ``authorId``, and ``yours`` when it is the writer named by
    ``contributor_id`` and ``author_id`` (which defaults to the contributor id, the
    principal: a persona is never "yours" unless named). For each writer holding a live
    claim there, and for the named writer always, its ``kind`` and ``model`` (as stored:
    agent or human, and the agent's model) and ``latestRound`` over the whole analysis
    (None when it has drawn in no round): a re-score is that writer's round
    ``latestRound + 1``.

    An unknown analysis, criterion or alternative is refused with ``KeyError``;
    ``author_id`` without ``contributor_id`` with ``ValueError``.
    """
    if author_id is not None and contributor_id is None:
        raise ValueError("author_id names an author of contributor_id: give contributor_id too")
    frame = store.frame(analysis_id)
    criteria = {c["id"] for c in _live(frame.get("criteria"))}
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

    me = author_id if author_id is not None else contributor_id

    def is_yours(cid, aid) -> bool:
        return cid == contributor_id and aid == me

    contributions, skipped = store.mergeable_contributions(analysis_id, frame=frame)
    latest: dict[tuple[str, str], int | None] = {}
    kinds: dict[tuple[str, str], str | None] = {}
    models: dict[tuple[str, str], str | None] = {}
    claims: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cid, contribution in contributions:
        for a in contribution.get("authors", []) or []:
            kinds[(cid, a.get("id"))] = a.get("kind")
            agent = a.get("agent") if isinstance(a.get("agent"), Mapping) else {}
            models[(cid, a.get("id"))] = agent.get("model")
        for author, n in _latest_rounds(contribution).items():
            latest[(cid, author)] = n
        for cell in contribution.get("cells", []) or []:
            if cell.get("criterionId") != criterion_id:
                continue
            key = (cell.get("alternativeId"), cell.get("measure", "score"))
            for a in live_assertions(cell):
                claims.setdefault(key, []).append({
                    "assertionId": a["id"],
                    "contributorId": cid,
                    "authorId": a.get("authorId"),
                    "yours": is_yours(cid, a.get("authorId")),
                })

    cells = [
        {
            "alternativeId": alt,
            "measure": measure,
            "liveClaims": sorted(
                claims.get((alt, measure), []),
                key=lambda c: (c["contributorId"], c["authorId"] or "", c["assertionId"]),
            ),
        }
        for alt in alternatives
        for measure in measures
    ]
    holders = {(c["contributorId"], c["authorId"]) for cell in cells for c in cell["liveClaims"]}
    if contributor_id is not None:
        holders.add((contributor_id, me))
    writers = [
        {"contributorId": cid, "authorId": aid, "kind": kinds.get((cid, aid)),
         "model": models.get((cid, aid)), "latestRound": latest.get((cid, aid))}
        for cid, aid in sorted(holders, key=lambda w: (w[0], w[1] or ""))
    ]
    summary = _summary(criterion_id, cells, writers, contributor_id, me, skipped)
    return {
        "analysisId": analysis_id,
        "criterionId": criterion_id,
        "cells": cells,
        "writers": writers,
        "skipped": skipped,
        "summary": summary,
    }


def _summary(criterion_id, cells, writers, you, me, skipped) -> str:
    """``you`` is the named contributor id (or None), ``me`` the author id taken as yours."""
    def name(cid, aid):
        return cid if aid in (None, cid) else f"{cid}/{aid}"

    held = sum(1 for c in cells if c["liveClaims"])
    parts = [f'"{criterion_id}": {len(cells)} cell(s) in scope, {held} with a live claim']
    for w in writers:
        n = w["latestRound"]
        parts.append(
            f"{name(w['contributorId'], w['authorId'])} ({w['kind'] or 'kind unknown'})'s latest round is "
            + (f"{n}, so its re-score is round {n + 1}" if n is not None else "unrecorded")
        )
    if you is not None:
        several = [
            f"{c['alternativeId']}/{c['measure']}"
            for c in cells
            if sum(cl["yours"] for cl in c["liveClaims"]) > 1
        ]
        others = [
            f"{c['alternativeId']}/{c['measure']}"
            for c in cells
            if c["liveClaims"] and not any(cl["yours"] for cl in c["liveClaims"])
        ]
        if several:
            parts.append(f"several live claims of yours in: {', '.join(several)} -- ask which a re-score replaces")
        if others:
            parts.append(f"only another writer's claims in: {', '.join(others)} -- ask before writing there")
        co_authors = sorted({
            cl["authorId"] for c in cells for cl in c["liveClaims"]
            if cl["contributorId"] == you and cl["authorId"] != me
        })
        if co_authors:
            parts.append(
                f"{you} has other authors with claims here ({', '.join(co_authors)}): they are "
                f"not yours as {me}; name author_id to write as one of them"
            )
    if skipped:
        parts.append(
            f"{len(skipped)} stored file(s) could not be merged and were left out (see skipped): "
            "claims in them are not listed"
        )
    return "; ".join(parts) + (
        ". No value, justification, evidence or code is returned: reading this keeps the "
        "prior withheld."
    )
