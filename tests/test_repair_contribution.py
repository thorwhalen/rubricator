"""A contributor can repair their own off-contract file without a hand edit (#166).

#159 leaves a file the comparanda contract refuses out of every read, and #156 then
refuses its contributor's writes. ``rubricator repair`` drops exactly the keys a
closed object refuses, from that one file, a dry run unless asked.
"""

from __future__ import annotations

import json

import pytest

from rubricator.cli import main
from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.rules import schema_problems
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    frame_set,
    measures_mark_missing,
)

AT = "2026-08-22T12:00:00Z"
ANA = human("ana", "Ana")


def _opened(root):
    runtime = build_runtime(root=str(root))
    store = runtime.store
    analysis_open(store, analysis_id="a1", question="which?", allow_skip_confirmation=True, at=AT)
    frame_set(store, analysis_id="a1", ambiguities=[])
    alternatives_set(store, analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(store, analysis_id="a1", criteria=[
        {"id": "c", "label": "C", "anchors": {"1": "none", "3": "some", "5": "all"}}])
    return store


def _off_contract(store, *, extra_on_cell=None):
    """Ana's file as a build before #155 wrote it: her author record carries an email."""
    key = store.contribution_key("a1", "ana")
    document = {
        "contributorId": "ana",
        "authors": [{**ANA, "email": "ana@example.org"}],
        "cells": [{"alternativeId": "x", "criterionId": "c", "measure": "score",
                   "assertions": [{"id": "s1", "authorId": "ana", "at": AT,
                                   "missing": {"code": "deferred", "note": "later"},
                                   **(extra_on_cell or {})}]}],
    }
    store.blobs[key] = json.dumps(document).encode()
    return key


def _mark(store):
    measures_mark_missing(store, analysis_id="a1", contributor_id="ana", author=ANA, at=AT,
                          code="deferred", note="later")


def test_a_dry_run_names_the_key_and_writes_nothing(tmp_path) -> None:
    store = _opened(tmp_path)
    key = _off_contract(store)
    before = store.blobs[key]
    got = store.repair_contribution("a1", "ana")
    assert got["dropped"] == ["$.authors[0].email"] and got["remaining"] == []
    assert got["written"] is False and "--apply" in got["summary"]
    assert store.blobs[key] == before


def test_applied_the_file_is_read_again_and_its_contributor_can_write(tmp_path) -> None:
    store = _opened(tmp_path)
    _off_contract(store)
    _, skipped = store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [store.contribution_key("a1", "ana")]
    with pytest.raises(ValueError):
        _mark(store)
    assert store.repair_contribution("a1", "ana", apply=True)["written"] is True
    merged, skipped = store.read_skipping("a1")
    assert skipped == [] and {a["id"] for a in merged["authors"]} >= {"ana"}
    _mark(store)


def test_a_refusal_no_dropped_key_fixes_writes_nothing(tmp_path) -> None:
    store = _opened(tmp_path)
    key = _off_contract(store, extra_on_cell={"independence": 7})
    before = store.blobs[key]
    got = store.repair_contribution("a1", "ana", apply=True)
    assert got["dropped"] == ["$.authors[0].email"] and got["remaining"]
    assert got["written"] is False and store.blobs[key] == before


def test_the_command_line_repairs_one_file(tmp_path, capsys) -> None:
    store = _opened(tmp_path)
    _off_contract(store)
    assert main(["repair", "a1", "ana", "--root", str(tmp_path)]) == 0
    assert "would drop 1 key(s)" in capsys.readouterr().out
    assert main(["repair", "a1", "ana", "--apply", "--root", str(tmp_path)]) == 0
    assert "dropped 1 key(s)" in capsys.readouterr().out
    assert main(["repair", "a1", "nobody", "--root", str(tmp_path)]) == 1
    assert "has no file" in capsys.readouterr().err


# --- referential integrity is reported on read (#166, item 2) ----------------------


def test_a_cell_naming_an_undeclared_row_or_column_is_a_schema_problem() -> None:
    document = {"alternatives": [{"id": "x"}], "criteria": [{"id": "c"}],
                "cells": [{"alternativeId": "x", "criterionId": "c"},
                          {"alternativeId": "ghost", "criterionId": "gone"}]}
    problems = schema_problems(document)
    assert [(p.path, p.rule_id, p.family) for p in problems] == [
        ("cells[1].alternativeId", "cell-coordinates-exist", "schema"),
        ("cells[1].criterionId", "cell-coordinates-exist", "schema"),
    ]
