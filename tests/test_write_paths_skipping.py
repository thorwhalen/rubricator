"""A colleague's broken file does not refuse everyone else's writes (#156).

#151 made every *read* leave an unmergeable contribution out and name it. The
write paths each decide for themselves, because a guard that skips a file can
let through what that file would have refused:

- ``measures_write`` checks honesty against the document readers see, so it
  skips and names, exactly as they do; the writer's *own* broken file refuses.
- ``criteria_set``'s superseded-cells report is a report: it skips and names.
- dropping a row (``alternatives_set``) or a column (``criteria_set``) is a guard
  over history: a file that cannot be read refuses the drop, naming the file,
  and blocks nothing else.
"""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
STRAY = "analyses/a1/contributions/zed.json"
OWN = "analyses/a1/contributions/ana.json"
ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
CRITERIA = [{"id": "speed", "label": "Boil speed", "anchors": ANCHORS},
            {"id": "noise", "label": "Noise", "anchors": ANCHORS}]
ROWS = [{"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two"}]
FORGED = json.dumps({"authors": [], "cells": [
    {"alternativeId": "k2", "criterionId": "noise", "measure": "score",
     "assertions": [{"id": "s1", "authorId": "ben", "value": 1, "at": MOMENT}]}]}).encode()
BROKEN = {"not json": b"{half-written", "a forged signature": FORGED}


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=ROWS)
    verbs["criteria_set"](analysis_id="a1", criteria=CRITERIA)
    verbs["measures_write"](
        analysis_id="a1", contributor_id="ben",
        author={"id": "ben", "displayName": "Ben", "kind": "human"},
        cells=[{"alternativeId": "k1", "criterionId": "speed", "value": 4,
                "justification": "ninety seconds"}],
    )
    return rt


@pytest.fixture()
def verbs(runtime):
    return bind(runtime)


def _write(verbs, **cell):
    return verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=ANA,
        cells=[{"alternativeId": "k1", "criterionId": "noise", "value": 3,
                "justification": "a hum", **cell}],
    )


@pytest.mark.parametrize("stray", list(BROKEN.values()), ids=list(BROKEN))
def test_measures_write_skips_and_names_a_colleague_s_broken_file(runtime, verbs, stray) -> None:
    runtime.store.blobs[STRAY] = stray
    result = _write(verbs)
    assert [s["file"] for s in result["skipped"]] == [STRAY]
    assert "left out of the honesty check" in result["summary"]
    assert OWN in runtime.store.blobs


def test_measures_mark_missing_names_it_too(runtime, verbs) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    result = verbs["measures_mark_missing"](
        analysis_id="a1", contributor_id="ana", author=ANA, code="not-evidenced",
        note="nothing published", criterion_ids=["noise"],
    )
    assert [s["file"] for s in result["skipped"]] == [STRAY]
    assert "(see skipped)" in result["summary"]


def test_a_clean_write_reports_nothing_skipped(verbs) -> None:
    result = _write(verbs)
    assert result["skipped"] == [] and "skipped" not in result["summary"]


def test_the_writer_s_own_unreadable_file_refuses_rather_than_being_overwritten(
    runtime, verbs
) -> None:
    runtime.store.blobs[OWN] = b"{half-written"
    with pytest.raises(ValueError, match="own file"):
        _write(verbs)
    assert runtime.store.blobs[OWN] == b"{half-written"


def test_the_writer_s_own_skipped_file_refuses_naming_why(runtime, verbs) -> None:
    """A write into a file no reader merges would be a write nobody sees."""
    runtime.store.blobs[OWN] = json.dumps({"authors": [], "cells": [
        {"alternativeId": "k1", "criterionId": "speed", "measure": "score",
         "assertions": [{"id": "s1", "authorId": "ben", "value": 1, "at": MOMENT}]}]}).encode()
    with pytest.raises(ValueError, match="left out of every read.*may not speak for"):
        _write(verbs)


def test_a_write_that_forges_is_still_refused_beside_a_broken_file(runtime, verbs) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    with pytest.raises(ValueError, match="refused, nothing was written"):
        verbs["measures_write"](
            analysis_id="a1", contributor_id="ana",
            author={"id": "ben", "displayName": "Ben", "kind": "human"},
            cells=[{"alternativeId": "k1", "criterionId": "noise", "value": 3,
                    "justification": "a hum"}],
        )
    assert OWN not in runtime.store.blobs


@pytest.mark.parametrize("stray", list(BROKEN.values()), ids=list(BROKEN))
def test_criteria_set_reports_without_the_broken_file(runtime, verbs, stray) -> None:
    runtime.store.blobs[STRAY] = stray
    result = verbs["criteria_set"](
        analysis_id="a1", criteria=[{**CRITERIA[0], "label": "Time to boil"}, CRITERIA[1]]
    )
    assert [s["file"] for s in result["skipped"]] == [STRAY]
    assert result["supersededCells"]["count"] == 1, "ben's score now answers an older definition"


def test_alternatives_set_that_drops_nothing_is_not_blocked(runtime, verbs) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    verbs["alternatives_set"](analysis_id="a1", alternatives=[*ROWS, {"id": "k3", "label": "Three"}])
    assert [a["id"] for a in runtime.store.frame("a1")["alternatives"]] == ["k1", "k2", "k3"]


def test_a_drop_is_refused_while_a_file_cannot_be_read(runtime, verbs) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    before = runtime.store.frame("a1")
    with pytest.raises(ValueError, match=f"drops alternatives k2, and {STRAY} cannot be read"):
        verbs["alternatives_set"](analysis_id="a1", alternatives=ROWS[:1])
    with pytest.raises(ValueError, match=f"drops criteria noise, and {STRAY} cannot be read"):
        verbs["criteria_set"](analysis_id="a1", criteria=CRITERIA[:1])
    assert runtime.store.frame("a1") == before


def test_a_skipped_but_readable_file_still_holds_history(runtime, verbs) -> None:
    """A forged file is left out of reads, but its cells still refer to k2 and noise."""
    runtime.store.blobs[STRAY] = FORGED
    with pytest.raises(ValueError, match="alternatives k2 would be dropped"):
        verbs["alternatives_set"](analysis_id="a1", alternatives=ROWS[:1])
    with pytest.raises(ValueError, match="criteria noise would be dropped"):
        verbs["criteria_set"](analysis_id="a1", criteria=CRITERIA[:1])


def test_nobody_can_squat_a_contributor_s_id_before_they_join(runtime, verbs) -> None:
    """Review finding F2(b) of #162: a file declaring ana's id must not block ana's first write.

    The persona prefix rule (#158) is what holds it: ``ana`` is not ``aaa:...``,
    so aaa's file is left out before ana has a file at all."""
    runtime.store.blobs["analyses/a1/contributions/aaa.json"] = json.dumps({"authors": [
        {"id": "ana", "displayName": "Ana", "kind": "human", "principalId": "aaa"}],
        "cells": []}).encode()
    result = _write(verbs)
    assert [s["file"] for s in result["skipped"]] == ["analyses/a1/contributions/aaa.json"]
    document, skipped = runtime.store.read_skipping("a1")
    assert [a["id"] for a in document["authors"]] == ["ana", "ben"]
    assert document["authors"][0].get("principalId") is None
