"""A contribution may only speak for itself, however its file is shaped (#158).

The merge's author rule once checked only the author *records* a file
introduced. Two forgeries got past it and produced a well-formed document that
was false: an assertion signed as somebody the file never introduced, and a
persona whose id shadowed another contributor's. Each is refused by the strict
merge and skipped, named, by the reader that tolerates broken files.
"""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.merge import MergeProblem, author_collisions, merge_contributions
from rubricator.store import AnalysisStore

MOMENT = "2026-08-22T12:00:00Z"
FRAME = {"id": "a1", "schemaVersion": 1, "subject": {"question": "which kettle?"},
         "alternatives": [], "criteria": [], "authors": [], "cells": []}


def _human(author_id: str, name: str, **extra) -> dict:
    return {"id": author_id, "displayName": name, "kind": "human", **extra}


def _contribution(authors: list[dict], *signers: str) -> dict:
    return {
        "authors": authors,
        "cells": [{"alternativeId": "k1", "criterionId": "speed", "measure": "score",
                   "assertions": [{"id": f"s{i}", "authorId": s, "value": 3, "at": MOMENT}
                                  for i, s in enumerate(signers, 1)]}],
    }


BEN = _contribution([_human("ben", "Ben")], "ben")
FORGERIES = {
    "an assertion signed as a colleague the file never introduced": (
        "zed", _contribution([], "ben")),
    "an assertion signed as a colleague while introducing only itself": (
        "zed", _contribution([_human("zed", "Zed")], "zed", "ben")),
    "an assertion with no author": ("zed", _contribution([], None)),
    "a persona that takes another contributor's id": (
        "aaa", _contribution([_human("ben", "Evil", principalId="aaa")], "ben")),
    "its own record naming another principal": (
        "zed", _contribution([_human("zed", "Zed", principalId="ben")], "zed")),
    "one author id declared twice, differently": (
        "zed", _contribution([_human("zed", "Zed"), _human("zed", "Ben")], "zed")),
}


@pytest.mark.parametrize("forger, forged", list(FORGERIES.values()), ids=list(FORGERIES))
def test_the_merge_refuses_a_forgery(forger, forged) -> None:
    with pytest.raises(MergeProblem):
        merge_contributions(FRAME, sorted([(forger, forged), ("ben", BEN)]))


def test_ben_s_scores_never_display_under_another_record() -> None:
    """The exact case from the issue: ``aaa`` sorts first, so its record used to win."""
    forged = _contribution([_human("ben", "Evil", principalId="aaa")])
    with pytest.raises(MergeProblem, match="another contributor's id"):
        merge_contributions(FRAME, [("aaa", forged), ("ben", BEN)])


def test_a_frame_author_cannot_be_redeclared_differently() -> None:
    frame = {**FRAME, "authors": [_human("ben", "Ben")]}
    with pytest.raises(MergeProblem, match="the frame"):
        merge_contributions(frame, [("ben", _contribution([_human("ben", "Evil")], "ben"))])
    merged = merge_contributions(frame, [("ben", BEN)])
    assert merged["authors"] == [_human("ben", "Ben")], "an identical record is not a clash"


def test_a_frame_author_may_be_signed_only_by_its_principal() -> None:
    cfo = _human("cfo", "The CFO", principalId="ana")
    frame = {**FRAME, "authors": [cfo]}
    merge_contributions(frame, [("ana", _contribution([], "cfo"))])
    with pytest.raises(MergeProblem, match="may not speak for"):
        merge_contributions(frame, [("zed", _contribution([], "cfo"))])


def test_honest_contributions_still_merge() -> None:
    """Own id without a record, own record, and a persona of one's own all sign."""
    ana = _contribution(
        [_human("ana", "Ana"), _human("ana-cfo", "the CFO", principalId="ana")],
        "ana", "ana-cfo",
    )
    merged = merge_contributions(
        FRAME, [("ana", ana), ("ben", BEN), ("cy", _contribution([], "cy"))]
    )
    signers = [a["authorId"] for a in merged["cells"][0]["assertions"]]
    assert signers == ["ana", "ana-cfo", "ben", "cy"]


def test_two_files_declaring_one_persona_id_are_both_named() -> None:
    ana = _contribution([_human("p", "the CFO", principalId="ana")], "p")
    aaa = _contribution([_human("p", "Evil", principalId="aaa")], "p")
    with pytest.raises(MergeProblem, match='contribution "aaa"'):
        merge_contributions(FRAME, [("aaa", aaa), ("ana", ana)])
    assert sorted(author_collisions([("aaa", aaa), ("ana", ana), ("ben", BEN)])) == ["aaa", "ana"]


# -- through the store --------------------------------------------------------


@pytest.fixture()
def store():
    store = AnalysisStore({}, now=fixed_clock(MOMENT))
    store.put_frame("a1", {k: v for k, v in FRAME.items() if k != "id"} | {"id": "a1"})
    store.put_contribution("a1", "ben", BEN)
    return store


def _place(store: AnalysisStore, contributor_id: str, document: dict) -> str:
    key = store.contribution_key("a1", contributor_id)
    store.blobs[key] = json.dumps(document).encode()
    return key


@pytest.mark.parametrize("forger, forged", list(FORGERIES.values()), ids=list(FORGERIES))
def test_read_refuses_and_read_skipping_names_the_forger(store, forger, forged) -> None:
    key = _place(store, forger, forged)
    with pytest.raises(MergeProblem):
        store.read("a1")
    document, skipped = store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [key]
    assert [a["authorId"] for c in document["cells"] for a in c["assertions"]] == ["ben"]
    assert document["authors"] == [_human("ben", "Ben")]


def test_read_skipping_leaves_out_both_sides_of_a_persona_clash(store) -> None:
    keys = [
        _place(store, "aaa", _contribution([_human("p", "Evil", principalId="aaa")], "p")),
        _place(store, "ana", _contribution([_human("p", "the CFO", principalId="ana")], "p")),
    ]
    with pytest.raises(MergeProblem):
        store.read("a1")
    document, skipped = store.read_skipping("a1")
    assert [s["file"] for s in skipped] == keys
    assert all('author "p"' in s["because"] for s in skipped)
    assert [a["authorId"] for c in document["cells"] for a in c["assertions"]] == ["ben"]


def test_a_broken_file_still_reserves_its_contributor_s_id(store) -> None:
    """Ben's file being unreadable does not free his id for someone else's persona."""
    store.blobs[store.contribution_key("a1", "ben")] = b"{half-written"
    forged = _place(store, "aaa", _contribution([_human("ben", "Evil", principalId="aaa")], "ben"))
    document, skipped = store.read_skipping("a1")
    assert sorted(s["file"] for s in skipped) == sorted(
        [forged, store.contribution_key("a1", "ben")]
    )
    assert document["authors"] == []
