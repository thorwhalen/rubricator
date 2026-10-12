"""One file that cannot be merged does not take every reader down (#151).

A shared, git-backed store is the design target (ADR-0017/0023), so a stray or
half-written file from one contributor is a when, not an if. Every reading path
leaves such a file out *whole* and names it beside what it returns; the strict
:meth:`AnalysisStore.read` still refuses, for the callers that must.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.merge import MergeProblem
from rubricator.surface import bind
from rubricator.tools.views import analysis_uri

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
STRAY = "analyses/a1/contributions/zed.json"
FORGED = json.dumps({
    "contributorId": "zed",
    "authors": [{"id": "ana", "displayName": "Ana", "kind": "human"}],
    "cells": [{"alternativeId": "k1", "criterionId": "speed", "measure": "score",
               "assertions": [{"id": "s1", "authorId": "ana", "value": 1, "at": MOMENT,
                               "justification": "forged"}]}],
}).encode()
STRAYS = {
    "not json": b"{half-written",
    "not an object": b"[]",
    "cell missing its keys": json.dumps({"authors": [], "cells": [{"assertions": []}]}).encode(),
    "forged author": FORGED,
}


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


@pytest.fixture()
def verbs(runtime):
    return bind(runtime)


@pytest.mark.parametrize("stray", list(STRAYS.values()), ids=list(STRAYS))
def test_the_stray_is_left_out_whole_and_named(runtime, stray) -> None:
    runtime.store.blobs[STRAY] = stray
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == [STRAY]
    assert skipped[0]["because"]
    values = [a["value"] for c in document["cells"] for a in c["assertions"]]
    assert values == [4], "ben's score survives; nothing of zed's is read"
    assert runtime.schema.validate(document).ok


def test_a_forged_author_is_skipped_with_the_merge_rule_s_own_words(runtime) -> None:
    runtime.store.blobs[STRAY] = FORGED
    _, skipped = runtime.store.read_skipping("a1")
    assert "neither that contributor nor a persona of them" in skipped[0]["because"]


def test_the_strict_read_still_refuses(runtime) -> None:
    """Where a forged attribution must be refused, it still is."""
    runtime.store.blobs[STRAY] = FORGED
    with pytest.raises(MergeProblem):
        runtime.store.read("a1")


def test_a_whole_store_reports_nothing_skipped(runtime) -> None:
    document, skipped = runtime.store.read_skipping("a1")
    assert skipped == [] and document == runtime.store.read("a1")


def test_a_broken_rendition_is_skipped_too(runtime) -> None:
    runtime.store.blobs["analyses/a1/renditions/r1.json"] = b"{}"
    document, skipped = runtime.store.read_skipping("a1")
    assert [s["file"] for s in skipped] == ["analyses/a1/renditions/r1.json"]
    assert document["renditions"] == []


@pytest.mark.parametrize("name, arguments", [
    ("analysis_open", {}),
    ("analysis_get", {"view": "summary"}),
    ("analysis_get", {"view": "outstanding"}),
    ("report_completeness", {}),
    ("aggregate_assertions", {}),
])
def test_every_reading_tool_surfaces_what_it_left_out(verbs, runtime, name, arguments) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    got = verbs[name](analysis_id="a1", **arguments)
    assert [s["file"] for s in got["skipped"]] == [STRAY]
    assert "could not be merged and were left out (see skipped)" in got["summary"]


@pytest.mark.parametrize("name, arguments", [
    ("analysis_open", {}), ("analysis_get", {}), ("report_completeness", {}),
    ("aggregate_assertions", {}),
])
def test_a_whole_read_says_nothing_about_skipping(verbs, name, arguments) -> None:
    got = verbs[name](analysis_id="a1", **arguments)
    assert got["skipped"] == [] and "left out" not in got["summary"]


def test_the_counts_include_the_readable_contributions(verbs, runtime) -> None:
    runtime.store.blobs[STRAY] = b"{half-written"
    report = verbs["report_completeness"](analysis_id="a1")
    assert report["present"] == 1
    cells = verbs["aggregate_assertions"](analysis_id="a1")["cells"]
    assert [c["reduced"] for c in cells] == [4]


def test_the_resource_names_what_it_left_out_in_its_metadata(runtime) -> None:
    from rubricator.mcp.server import make_server

    runtime.store.blobs[STRAY] = b"{half-written"
    server = make_server(runtime)
    content = asyncio.run(server.read_resource(analysis_uri("a1"))).contents[0]
    assert content.meta == {"skipped": [{"file": STRAY, "because": content.meta["skipped"][0]["because"]}]}
    assert "ninety seconds" in content.content
