"""Merging one frame and N contributions into one analysis document.

**A pure function, in the core, and not in a backend.** Two backends that merged
differently would be two products: a team on a shared git repository and a team
on a local folder would see different numbers from the same files, and neither
would be wrong from where they were standing. So the merge happens once, here,
over data that has already been read.

## What merging actually means here

Almost nothing, and that is the design working rather than the design being
unfinished. A cell in the comparanda schema is *already a set of assertions*, so
two people scoring the same cell do not conflict -- they contribute two
assertions, which is exactly what the schema was built to hold and what makes
disagreement a finding rather than a collision (ADR-0011). Merging is therefore
concatenation plus a deterministic order, not conflict resolution.

The two places where it is more than that:

- **Assertion ids must not collide across contributors.** Two people whose
  tooling generates ``s1`` would otherwise silently produce one document with two
  different assertions claiming one identity. Ids are namespaced by contributor
  on read, so a contributor's file stays readable on its own and the merged
  document stays unambiguous.
- **Authors are unioned by id**, and a contributor may only introduce authors
  they are behind. Otherwise one contributor could add an author record for
  somebody else -- attributing an assertion to a colleague who never made it,
  which the honesty rules are downstream of and cannot catch.

## Order

Contributions merge in contributor-id order and assertions keep their within-file
order. Nothing downstream should depend on assertion order -- a reduction that
did would be a reduction that changes when a new contributor joins -- but the
*output bytes* must be stable, because these documents are diffed.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = ["merge_contributions", "MergeProblem"]


class MergeProblem(ValueError):
    """A contribution that cannot be merged, with what to do about it."""


def _namespaced(contributor_id: str, assertion_id: str) -> str:
    """An assertion id that is unique across contributors.

    Prefixed rather than hashed so that a person reading the merged document can
    still see who an assertion came from without a lookup, which is the first
    thing anyone asks of a cell with two values in it.
    """
    return f"{contributor_id}:{assertion_id}"


def merge_contributions(
    frame: Mapping[str, Any],
    contributions: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    renditions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build one analysis document from a frame and each contributor's file.

    ``contributions`` is ``(contributor_id, document)`` pairs; the caller decides
    the order and the store hands them over sorted, so the output is reproducible.

    >>> frame = {'id': 'a1', 'schemaVersion': 1, 'subject': {'question': 'which?'},
    ...          'alternatives': [], 'criteria': [], 'authors': [], 'cells': []}
    >>> ana = {'authors': [{'id': 'ana', 'displayName': 'Ana', 'kind': 'human'}],
    ...        'cells': [{'alternativeId': 'a', 'criterionId': 'c', 'measure': 'score',
    ...                   'assertions': [{'id': 's1', 'authorId': 'ana', 'value': 4}]}]}
    >>> ben = {'authors': [{'id': 'ben', 'displayName': 'Ben', 'kind': 'human'}],
    ...        'cells': [{'alternativeId': 'a', 'criterionId': 'c', 'measure': 'score',
    ...                   'assertions': [{'id': 's1', 'authorId': 'ben', 'value': 2}]}]}
    >>> merged = merge_contributions(frame, [('ana', ana), ('ben', ben)])
    >>> len(merged['cells'])
    1
    >>> [a['id'] for a in merged['cells'][0]['assertions']]
    ['ana:s1', 'ben:s1']

    The two people disagreed, and the merged cell holds both claims rather than
    picking one. Which of them is *displayed* is a reduction, and a reduction is
    a separate, named, opt-in decision (ADR-0015).
    """
    merged: dict[str, Any] = {**frame}
    merged.setdefault("authors", [])
    merged.setdefault("cells", [])

    authors: dict[str, Any] = {a["id"]: a for a in merged["authors"]}
    # Keyed by cell identity so two contributors scoring one cell land in one
    # cell rather than in two, which the schema rejects as a duplicate identity.
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    for cell in merged["cells"]:
        cells[(cell["alternativeId"], cell["criterionId"], cell["measure"])] = {
            **cell,
            "assertions": list(cell.get("assertions", [])),
        }

    for contributor_id, contribution in contributions:
        for author in contribution.get("authors", []):
            _check_author(contributor_id, author)
            authors.setdefault(author["id"], author)

        for cell in contribution.get("cells", []):
            key = (cell["alternativeId"], cell["criterionId"], cell["measure"])
            target = cells.setdefault(
                key,
                {
                    "alternativeId": key[0],
                    "criterionId": key[1],
                    "measure": key[2],
                    "assertions": [],
                },
            )
            for assertion in cell.get("assertions", []):
                target["assertions"].append(
                    {**assertion, "id": _namespaced(contributor_id, assertion["id"])}
                )
            # A cell-level reduction override travels with whoever set it. Last
            # writer in contributor order wins, which is arbitrary -- and a
            # contributor overriding the displayed reduction of a shared cell is
            # a coordination question, not a merge one.
            if "reduction" in cell:
                target["reduction"] = cell["reduction"]

    merged["authors"] = [authors[k] for k in sorted(authors)]
    merged["cells"] = [cells[k] for k in sorted(cells)]

    existing = {r["id"] for r in merged.get("renditions", [])}
    merged["renditions"] = list(merged.get("renditions", [])) + [
        dict(r) for r in renditions if r["id"] not in existing
    ]
    return merged


def _check_author(contributor_id: str, author: Mapping[str, Any]) -> None:
    """A contributor may only introduce authors they are behind.

    Their own identity, or a persona whose ``principalId`` is their own identity.
    Without this, one contributor's file could add an author record for a
    colleague and attribute an assertion to them -- a lie the honesty rules sit
    downstream of and cannot catch, because the resulting document is perfectly
    well formed.
    """
    author_id = author.get("id")
    principal = author.get("principalId")
    if author_id == contributor_id or principal == contributor_id:
        return
    raise MergeProblem(
        f'contribution "{contributor_id}" introduces author "{author_id}", who is neither that '
        f'contributor nor a persona of them (principalId is {principal!r}). A contributor may '
        "only speak for themselves; attributing an assertion to a colleague who did not make it "
        "produces a well-formed document that is false, which no later validation can detect. "
        f'Set principalId to "{contributor_id}", or have that person contribute their own file.'
    )
