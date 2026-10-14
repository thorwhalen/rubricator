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
- **Authors are unioned by id**, and a contributor may only speak for
  themselves (#158). Otherwise one contributor could attribute an assertion to a
  colleague who never made it -- a well-formed document that is false, which the
  honesty rules are downstream of and cannot catch. Three checks hold that line:

  1. a contribution introduces only authors it is behind -- its own id, or a
     persona whose ``principalId`` is its own id and whose id is prefixed with
     it (``ana:the-sceptical-cfo``, as :func:`rubricator.contributors.persona`
     builds it) -- so a persona never takes, and is never taken by, another
     contributor's id;
  2. an author id names one record: a contribution may not redeclare a frame
     author, or another contribution's author, differently;
  3. every assertion's ``authorId`` is one the file may speak for: its own id,
     an author it introduced, or a frame author whose principal it is.

  The frame is a file a person can edit like any other, so it is held to the
  same line (#195). It carries no assertions -- it has no contributor to speak
  for them -- and a persona it declares carries its principal in its id, as a
  contribution's must (``ana:the-cfo``), so no frame can hand one contributor
  an id that is, or would read as, another's. Either broken is the frame's
  problem, raised once.

## Order

Contributions merge in contributor-id order and assertions keep their within-file
order. Nothing downstream should depend on assertion order -- a reduction that
did would be a reduction that changes when a new contributor joins -- but the
*output bytes* must be stable, because these documents are diffed.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = ["merge_contributions", "author_collisions", "MergeProblem"]


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
    contributors: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build one analysis document from a frame and each contributor's file.

    ``contributions`` is ``(contributor_id, document)`` pairs; the caller decides
    the order and the store hands them over sorted, so the output is reproducible.
    ``contributors`` is every contributor id whose identity a persona may not
    take; it defaults to the ids in ``contributions``, and a caller merging one
    file on trial passes the whole roster, so the trial refuses what the joint
    merge would.

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
    contributions = list(contributions)
    roster = frozenset(contributors if contributors is not None else (c for c, _ in contributions))
    merged: dict[str, Any] = {**frame}
    merged.setdefault("authors", [])
    merged.setdefault("cells", [])

    authors, cells = _index_frame(merged)
    # Who declared each author, so a clash names the other party: the frame, or
    # the contribution that got there first.
    declared_by: dict[str, str] = {a: "the frame" for a in authors}
    frame_authors = dict(authors)
    # What each contributor's passes did (ADR-0018, #99): their own records, ids namespaced
    # like assertions', appended after the frame's.
    passes: dict[str, list[Any]] = {
        "procedures": list(merged.get("procedures", [])), "rounds": list(merged.get("rounds", [])),
    }

    for contributor_id, contribution in contributions:
        own: dict[str, Any] = {}
        for author in contribution.get("authors", []):
            _check_author(contributor_id, author, roster=roster)
            _check_one_record(contributor_id, author, own.get(author["id"], author), "itself")
            own[author["id"]] = author
        for author_id, author in own.items():
            if author_id in authors:
                _check_one_record(
                    contributor_id, author, authors[author_id], declared_by[author_id]
                )
            else:
                authors[author_id] = author
                declared_by[author_id] = f'contribution "{contributor_id}"'
        speaks_for = {*own} | {
            a for a, record in frame_authors.items() if record.get("principalId") == contributor_id
        }
        # Its own id, unless the frame gives that id to somebody else: a file
        # named after a frame persona would otherwise sign as that persona.
        if frame_authors.get(contributor_id, {}).get("principalId") in (None, contributor_id):
            speaks_for.add(contributor_id)

        for cell in contribution.get("cells", []):
            key = (cell["alternativeId"], cell["criterionId"], cell["measure"])
            _check_identity(contributor_id, "a cell's alternativeId, criterionId and measure", key)
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
                _check_speaks_for(contributor_id, assertion, speaks_for)
                namespaced = {**assertion, "id": _namespaced(contributor_id, assertion["id"])}
                # The pass an assertion belongs to is the contributor's own record (#99).
                for ref in ("procedureId", "roundId"):
                    if assertion.get(ref):
                        namespaced[ref] = _namespaced(contributor_id, assertion[ref])
                # A contributor supersedes their own assertions, so the reference
                # is namespaced the same way; left bare it would name nothing.
                if assertion.get("supersededBy"):
                    namespaced["supersededBy"] = _namespaced(
                        contributor_id, assertion["supersededBy"]
                    )
                target["assertions"].append(namespaced)
            # A cell-level reduction override travels with whoever set it. Last
            # writer in contributor order wins, which is arbitrary -- and a
            # contributor overriding the displayed reduction of a shared cell is
            # a coordination question, not a merge one.
            if "reduction" in cell:
                target["reduction"] = cell["reduction"]
        for field in ("procedures", "rounds"):
            entries = contribution.get(field, [])
            if not all(isinstance(e, Mapping) for e in entries):
                raise MergeProblem(
                    f'contribution "{contributor_id}" gives {field} that are not objects. Repair or '
                    "remove the file."
                )
            _check_identity(contributor_id, f"a {field[:-1]} id", [e.get("id") for e in entries])
            passes[field].extend({**e, "id": _namespaced(contributor_id, e["id"])} for e in entries)

    merged["authors"] = [authors[k] for k in sorted(authors)]
    merged["cells"] = [cells[k] for k in sorted(cells)]
    merged["procedures"], merged["rounds"] = passes["procedures"], passes["rounds"]

    existing = {r["id"] for r in merged.get("renditions", [])}
    merged["renditions"] = list(merged.get("renditions", [])) + [
        dict(r) for r in renditions if r["id"] not in existing
    ]
    return merged


def _index_frame(
    frame: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[tuple[str, str, str], dict[str, Any]]]:
    """The frame's authors by id and its cells by identity, or the frame's own ``MergeProblem``.

    Cells are keyed by identity so two contributors scoring one cell land in one
    cell rather than in two, which the schema rejects as a duplicate identity.
    A frame that cannot be indexed is reported as the frame's problem, once
    (#159): left to fail inside each contribution's trial it would be blamed on
    every contributor in turn.
    """
    try:
        authors = {a["id"]: a for a in frame["authors"]}
        cells = {
            (c["alternativeId"], c["criterionId"], c["measure"]): {
                **c, "assertions": list(c.get("assertions", []))
            }
            for c in frame["cells"]
        }
    except (AttributeError, KeyError, TypeError) as error:
        raise MergeProblem(
            f"the frame is not shaped like one this build can merge ({type(error).__name__}: "
            f"{error}). Every read of this analysis needs it, so repair the frame file."
        ) from None
    try:
        renditions = [r["id"] for r in frame.get("renditions", [])]
    except (AttributeError, KeyError, TypeError) as error:
        raise MergeProblem(
            f"the frame's renditions are not shaped like ones this build can merge "
            f"({type(error).__name__}: {error}). Every read of this analysis needs the frame, so "
            "repair the frame file."
        ) from None
    signed = sorted("/".join(key) for key, c in cells.items() if c["assertions"])
    if signed:
        raise MergeProblem(
            f"the frame holds assertions in cell(s) {', '.join(signed)}. An assertion belongs in "
            "the contribution of whoever made it, where the merge checks who may sign it; the "
            "frame speaks for nobody. Move them into that person's contribution file, or remove "
            "them. Every read of this analysis needs the frame, so repair the frame file."
        )
    ids = [*authors, *(v for key in cells for v in key), *renditions]
    if not all(isinstance(v, str) for v in ids):
        raise MergeProblem(
            f"the frame gives ids as {[v for v in ids if not isinstance(v, str)]!r}; every id is "
            "a string. Every read of this analysis needs the frame, so repair the frame file."
        )
    unprefixed = sorted(
        f'"{a}" (principalId {record.get("principalId")!r})' for a, record in authors.items()
        if record.get("principalId") not in (None, a)
        and not (isinstance(record.get("principalId"), str) and a.startswith(f'{record["principalId"]}:'))
    )
    if unprefixed:
        raise MergeProblem(
            f"the frame declares persona(s) {', '.join(unprefixed)} whose id does not start with "
            "its principal's id and a colon. A persona id carries its principal, as in a "
            "contribution, so that no frame can hand one contributor an id that is, or reads as, "
            "another's. Rename each to \"<principalId>:<name>\". Every read of this analysis needs "
            "the frame, so repair the frame file."
        )
    return authors, cells


def _check_identity(contributor_id: str, what: str, values: Iterable[Any]) -> None:
    """Ids are strings, or the merge cannot order them beside everyone else's.

    Checked per contribution, so a file that would only fail once merged with
    another -- ``null`` sorted against a string -- fails on its own, where a
    reader that skips unmergeable files can still leave it out (#151).
    """
    if not all(isinstance(v, str) for v in values):
        raise MergeProblem(
            f'contribution "{contributor_id}" gives {what} as {list(values)!r}; every id is a '
            "string. Repair or remove the file."
        )


def _check_author(
    contributor_id: str, author: Mapping[str, Any], *, roster: frozenset[str] = frozenset()
) -> None:
    """A contributor may only introduce authors they are behind.

    Their own identity, or a persona whose ``principalId`` is their own identity.
    Without this, one contributor's file could add an author record for a
    colleague and attribute an assertion to them -- a lie the honesty rules sit
    downstream of and cannot catch, because the resulting document is perfectly
    well formed.

    Their own record names no other principal, and a persona's id is
    ``<contributor>:<anything>``: either rule broken would put a colleague behind
    claims they did not make (#158). The prefix is what keeps the two namespaces
    apart -- a contributor id cannot contain ``:``, so no newcomer's file can be
    named after a persona, and no persona can be named after a contributor.
    ``roster`` is a second line for a hand-made file name that does contain one.
    """
    author_id = author.get("id")
    _check_identity(contributor_id, "an author id", [author_id])
    principal = author.get("principalId")
    if author_id == contributor_id:
        if principal in (None, contributor_id):
            return
        raise MergeProblem(
            f'contribution "{contributor_id}" gives its own author record principalId '
            f'{principal!r}. That would put another account behind this contributor\'s claims. '
            f'Drop principalId, or set it to "{contributor_id}".'
        )
    if author_id in roster:
        raise MergeProblem(
            f'contribution "{contributor_id}" introduces author "{author_id}", which is another '
            f"contributor's id. A persona may not take a colleague's identity: their own "
            "assertions would then display under this record. Give the persona an id of its own."
        )
    if principal == contributor_id:
        if isinstance(author_id, str) and author_id.startswith(f"{contributor_id}:"):
            return
        raise MergeProblem(
            f'contribution "{contributor_id}" introduces persona "{author_id}", whose id does not '
            f'start with "{contributor_id}:". A persona id carries its principal, so that no '
            "contributor can later join under it and no persona can take a contributor's name. "
            f'Rename it "{contributor_id}:{author_id}", as contributors.persona() would.'
        )
    raise MergeProblem(
        f'contribution "{contributor_id}" introduces author "{author_id}", who is neither that '
        f'contributor nor a persona of them (principalId is {principal!r}). A contributor may '
        "only speak for themselves; attributing an assertion to a colleague who did not make it "
        "produces a well-formed document that is false, which no later validation can detect. "
        f'Set principalId to "{contributor_id}", or have that person contribute their own file.'
    )


def _check_one_record(
    contributor_id: str, author: Mapping[str, Any], existing: Mapping[str, Any], where: str
) -> None:
    """One author id names one record, so no file can redefine whose claims an id carries."""
    if author == existing:
        return
    raise MergeProblem(
        f'contribution "{contributor_id}" declares author "{author["id"]}" differently from '
        f"{where}. One author id names one record; otherwise every assertion signed with it "
        "displays under whichever record the merge kept. Give the author an id of its own, or "
        "make the records identical."
    )


def _check_speaks_for(
    contributor_id: str, assertion: Mapping[str, Any], speaks_for: set[str]
) -> None:
    """An assertion's ``authorId`` is one its file may speak for (#158).

    Its contributor's own id (unless the frame gives that id to another
    principal), an author the file introduced (each already checked to be behind
    it), or a frame author whose principal is the contributor.
    Anything else -- a colleague named without a record, a frame author behind
    someone else, no author at all -- attributes the claim to someone who did not
    make it.
    """
    author_id = assertion.get("authorId")
    if author_id in speaks_for:
        return
    raise MergeProblem(
        f'contribution "{contributor_id}" has assertion "{assertion.get("id")}" signed by '
        f"{author_id!r}, whom that file may not speak for: a contribution signs only as its "
        "contributor or as an author it introduces and is behind. Re-sign the assertion, or have "
        "that person contribute their own file."
    )


def author_collisions(
    contributions: Iterable[tuple[str, Mapping[str, Any]]],
) -> dict[str, str]:
    """Contributions that declare an author id another contribution also declares.

    Each such file is a valid merge on its own; together they make one author id
    name two records. The persona prefix rule leaves this only to contributor
    ids containing ``:``, which only a hand-made file name can give, so it is a
    backstop. Once each file has passed the merge's author check, two
    contributors never declare one id identically (each record names its own
    contributor), so any shared id is a clash. Which side is genuine cannot be
    read from the files, and keeping the first in contributor order would hand
    the id to whoever sorts first -- the forgery itself. So every party is
    returned, mapped to why, for a reader that skips unmergeable files to leave
    them all out and name them (#158).

    >>> ana = {"authors": [{"id": "p", "displayName": "CFO", "kind": "human", "principalId": "ana"}]}
    >>> aaa = {"authors": [{"id": "p", "displayName": "Evil", "kind": "human", "principalId": "aaa"}]}
    >>> sorted(author_collisions([("aaa", aaa), ("ana", ana)]))
    ['aaa', 'ana']
    """
    declared: dict[str, list[str]] = {}
    for contributor_id, contribution in contributions:
        for author_id in sorted({a["id"] for a in contribution.get("authors", [])}):
            declared.setdefault(author_id, []).append(contributor_id)
    collisions: dict[str, str] = {}
    for author_id, parties in sorted(declared.items()):
        for contributor_id in parties if len(parties) > 1 else ():
            others = ", ".join(f'"{p}"' for p in parties if p != contributor_id)
            collisions.setdefault(
                contributor_id,
                f'contribution "{contributor_id}" declares author "{author_id}", which '
                f"contribution {others} also declares. One author id cannot name two records, "
                "and which is genuine cannot be told from the files, so none of them is merged "
                "until the id is renamed in all but one.",
            )
    return collisions
