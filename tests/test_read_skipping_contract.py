"""A tolerant read never serves a document the published schema refuses (#159).

#151's tolerant read left out files that could not be *merged*. A file can
merge cleanly and still break comparanda v1 -- a value that is a dict, an ``at``
that is a number -- and then every reader served an invalid document. Now each
file must also fit the contract, and be writable back out as JSON; two
renditions with one id are both left out; and a frame's problems are reported
as the frame's, never blamed on each contributor in turn.
"""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.merge import MergeProblem
from rubricator.store import MAX_NESTING
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
STRAY = "analyses/a1/contributions/zed.json"
ZED = {"id": "zed", "displayName": "Zed", "kind": "human"}


def _zed(author=ZED, cell=None, **assertion) -> bytes:
    signed = {"id": "s1", "authorId": "zed", "value": 3, "at": MOMENT, **assertion}
    return json.dumps({"authors": [author], "cells": [{
        "alternativeId": "k1", "criterionId": "speed", "measure": "score",
        "assertions": [signed], **(cell or {})}]}).encode()


OFF_CONTRACT = {
    "a value that is a dict": _zed(value={"n": 3}),
    "a value that is a list": _zed(value=[3]),
    "an authorId that is an int": _zed(authorId=5),
    "an at that is a number": _zed(at=5),
    "a reduction that is a dict": _zed(cell={"reduction": {"kind": "mean"}}),
    "an author with no displayName": _zed(author={"id": "zed", "kind": "human"}),
    "NaN": _zed().replace(b'"value": 3', b'"value": NaN'),
    "a number too large to be finite": _zed().replace(b'"value": 3', b'"value": 1e400'),
}


@pytest.mark.parametrize("depth", [MAX_NESTING + 1, 2_000])
def test_nesting_past_the_limit_is_left_out(runtime, depth) -> None:
    """Counted, not probed: 2,000 levels parse, then break ``json.dump(indent=2)``."""
    runtime.store.blobs[STRAY] = b"[" * depth + b"]" * depth
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [STRAY]
    assert "deep" in skipped[0]["because"]  # counted, or past the parser's own limit
    json.dumps(document, indent=2)


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k1", "label": "Kettle one"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS}])
    verbs["measures_write"](
        analysis_id="a1", contributor_id="ben",
        author={"id": "ben", "displayName": "Ben", "kind": "human"},
        cells=[{"alternativeId": "k1", "criterionId": "speed", "value": 4,
                "justification": "ninety seconds"}],
    )
    return rt


def test_a_well_formed_stray_is_kept(runtime) -> None:
    runtime.store.blobs[STRAY] = _zed()
    document, skipped = runtime.store.read_skipping("a1")
    assert skipped == []
    assert runtime.schema.validate(document).ok


@pytest.mark.parametrize("stray", list(OFF_CONTRACT.values()), ids=list(OFF_CONTRACT))
def test_a_file_that_merges_but_breaks_v1_is_left_out_and_named(runtime, stray) -> None:
    runtime.store.blobs[STRAY] = stray
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [STRAY]
    assert runtime.schema.validate(document).ok
    json.dumps(document, indent=2, allow_nan=False)  # what `rubricator show` writes


def _rendition(rendition_id) -> bytes:
    return json.dumps({"id": rendition_id, "originalLocator": "https://example.org/k1",
                       "originalSha256": "0" * 64, "normaliserId": "plain"}).encode()


def test_a_rendition_off_contract_is_left_out(runtime) -> None:
    runtime.store.blobs["analyses/a1/renditions/r1.json"] = _rendition("r1")
    runtime.store.blobs["analyses/a1/renditions/r2.json"] = _rendition(5)
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == ["analyses/a1/renditions/r2.json"]
    assert [r["id"] for r in document["renditions"]] == ["r1"]
    assert runtime.schema.validate(document).ok


def test_two_renditions_with_one_id_are_both_left_out(runtime) -> None:
    runtime.store.blobs["analyses/a1/renditions/r1.json"] = _rendition("r1")
    runtime.store.blobs["analyses/a1/renditions/r1-copy.json"] = _rendition("r1")
    document, skipped = runtime.store.read_skipping("a1")
    assert sorted(s["file"] for s in skipped) == [
        "analyses/a1/renditions/r1-copy.json", "analyses/a1/renditions/r1.json"]
    assert document["renditions"] == []


def _edit_frame(runtime, change) -> None:
    key = runtime.store.frame_key("a1")
    frame = json.loads(runtime.store.blobs[key])
    change(frame)
    runtime.store.blobs[key] = json.dumps(frame).encode()


def test_a_frame_author_with_a_null_id_is_the_frame_s_problem(runtime) -> None:
    """It used to make every contribution fail its trial, each blamed in turn."""
    _edit_frame(runtime, lambda f: f["authors"].append({"id": None, "displayName": "?"}))
    with pytest.raises(MergeProblem, match="the frame"):
        runtime.store.read_skipping("a1")


def test_a_frame_cell_with_no_alternative_is_the_frame_s_problem(runtime) -> None:
    """It used to make analysis_open raise a bare KeyError."""
    _edit_frame(runtime, lambda f: f["cells"].append({"criterionId": "speed", "measure": "score"}))
    with pytest.raises(MergeProblem, match="the frame"):
        bind(runtime)["analysis_open"](analysis_id="a1")


# -- review findings of #165 ---------------------------------------------------


def test_a_lone_surrogate_is_left_out(runtime) -> None:
    """Finding 3: ``\\ud800`` parses, then no UTF-8 writer can emit it."""
    runtime.store.blobs[STRAY] = _zed().replace(b'"value": 3', b'"value": 3, "justification": "\\ud800"')
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [STRAY]
    json.dumps(document, ensure_ascii=False).encode("utf-8")


def test_a_frame_rendition_with_no_id_is_the_frame_s_problem(runtime) -> None:
    """Finding 5: a bare KeyError on every read and every write."""
    _edit_frame(runtime, lambda f: f.setdefault("renditions", []).append({"label": "?"}))
    with pytest.raises(MergeProblem, match="the frame"):
        runtime.store.read_skipping("a1")


def test_a_frame_holding_nan_is_the_frame_s_problem(runtime) -> None:
    """Finding 7: a frame v1 accepts can still not be written back out."""
    key = runtime.store.frame_key("a1")
    runtime.store.blobs[key] = runtime.store.blobs[key].replace(b'"criteria"', b'"x": NaN, "criteria"', 1)
    with pytest.raises(MergeProblem, match="the frame holds NaN"):
        runtime.store.read_skipping("a1")


def test_a_rendition_the_frame_already_holds_is_named(runtime) -> None:
    """Finding 6: it used to be dropped silently."""
    _edit_frame(runtime, lambda f: f.setdefault("renditions", []).append(json.loads(_rendition("r1"))))
    runtime.store.blobs["analyses/a1/renditions/copy.json"] = _rendition("r1")
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == ["analyses/a1/renditions/copy.json"]
    assert len(document["renditions"]) == 1


def test_a_changed_file_is_judged_again(runtime) -> None:
    """Verdicts are remembered by the file's bytes, never by its name."""
    runtime.store.blobs[STRAY] = _zed()
    assert runtime.store.read_skipping("a1")[1] == []
    runtime.store.blobs[STRAY] = _zed(at=5)
    assert [s["file"] for s in runtime.store.read_skipping("a1")[1]] == [STRAY]


def test_the_runtime_s_contract_is_the_store_s(runtime) -> None:
    """Finding 2: one contract, and a fragment's ``$ref`` resolves against its schema."""
    from rubricator.schema.source import SchemaSource

    assert runtime.store.contract is runtime.schema
    sketched = build_runtime(blobs=dict(runtime.store.blobs), now=fixed_clock(MOMENT),
                             schema=SchemaSource.sketch())
    sketched.store.blobs[STRAY] = _zed()
    _, skipped = sketched.store.read_skipping("a1")
    assert all("PointerToNowhere" not in s["because"] for s in skipped)
