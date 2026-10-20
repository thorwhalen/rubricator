"""An analysis survives a session boundary, end to end (#82, ADR-0017).

The pieces are tested where they live: expiry in ``test_store``, the no-re-ask
read in ``test_frame_confirm``, the resume block in ``test_resume``. This file
crosses the boundary once, through every entry point ADR-0017 names (the
analyses resource, ``analysis_open`` with the existing id, the ``resume``
prompt), and finishes the analysis in the second session. Two runtimes share
nothing but the stored bytes, which is all a new session has.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from rubricator.compose import build_runtime
from rubricator.mcp.resolve import read_analyses
from rubricator.rules import honesty_problems, schema_problems
from rubricator.store import RETENTION_DAYS, AnalysisNotFound
from rubricator.surface import bind

ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "a source states no repair service exists"},
           {"level": "3", "text": "a source states repairs for some parts"},
           {"level": "5", "text": "a source states repairs for every part, with a period"}]
SPAN = {"id": "e1", "target": "doc:brochure", "sourceType": "primary", "stance": "supports",
        "excerpt": "every part is repaired for ten years"}


class _Clock:
    """Monday, then whenever the test says, so a 30-day window takes no time."""

    def __init__(self) -> None:
        self.at = datetime(2026, 10, 12, 9, 30, tzinfo=timezone.utc)

    def __call__(self) -> str:
        return self.at.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, **delta: float) -> None:
        self.at += timedelta(**delta)


def _session(blobs: dict[str, bytes], clock: _Clock):
    runtime = build_runtime(blobs=blobs, now=clock, retention_clock=clock)
    return runtime, bind(runtime)


def _cell(alternative: str) -> dict:
    return {"alternativeId": alternative, "criterionId": "repair", "value": 5,
            "justification": "the brochure states it", "evidence": [SPAN]}


@pytest.fixture
def monday():
    """Session one: framed, confirmed, one of two cells scored, then closed."""
    blobs: dict[str, bytes] = {}
    clock = _Clock()
    _, verbs = _session(blobs, clock)
    verbs["analysis_open"](analysis_id="kettles", question="which kettle should the office buy?")
    verbs["frame_set"](analysis_id="kettles", ambiguities=[])
    verbs["alternatives_set"](analysis_id="kettles", alternatives=[
        {"id": "brindle", "label": "Brindle"}, {"id": "tamsin", "label": "Tamsin"}])
    verbs["criteria_set"](analysis_id="kettles", criteria=[
        {"id": "repair", "label": "Repair policy", "anchors": ANCHORS}])
    verbs["frame_confirm"](analysis_id="kettles")
    verbs["frame_confirm"](analysis_id="kettles", decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, go ahead.")
    verbs["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA,
                            cells=[_cell("brindle")])
    clock.advance(days=2)
    return blobs, clock


def test_a_new_session_finds_resumes_and_finishes_without_re_asking(monday) -> None:
    blobs, clock = monday
    runtime, verbs = _session(blobs, clock)

    listed = json.loads(read_analyses(runtime.store))["analyses"]
    assert [(r["id"], r["stage"]) for r in listed] == [("kettles", 5)]

    stored = dict(blobs)
    reopened = verbs["analysis_open"](analysis_id="kettles")
    assert reopened["stage"] == 5 and "reopened" in reopened["summary"]
    assert dict(blobs) == stored, "reopening an analysis rewrote it"

    assert "partial analysis" in verbs["prompts_get"](prompt_id="resume")["title"].lower()
    gate = verbs["frame_confirm"](analysis_id="kettles")
    assert (gate["confirmed"], gate["mechanism"], gate["instructions"]) == (True, "recorded", None)
    assert gate["record"]["text"] == "Yes, go ahead."

    outstanding = verbs["analysis_get"](analysis_id="kettles", view="outstanding")["counts"]["outstanding"]
    assert outstanding == 1
    verbs["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA, cells=[_cell("tamsin")])
    assert verbs["analysis_get"](analysis_id="kettles", view="outstanding")["counts"]["outstanding"] == 0
    # analysis_validate is still planned (#61); its two rule families are what it will run.
    finished = runtime.store.read("kettles")
    assert list(schema_problems(finished)) == [] and list(honesty_problems(finished)) == []


def test_expiry_across_the_boundary_is_recoverable(monday) -> None:
    blobs, clock = monday
    clock.advance(days=RETENTION_DAYS)
    runtime, verbs = _session(blobs, clock)
    with pytest.raises(AnalysisNotFound, match=f"{RETENTION_DAYS} days"):
        verbs["analysis_get"](analysis_id="kettles")
    assert json.loads(read_analyses(runtime.store))["analyses"] == []
    fresh = verbs["analysis_open"](analysis_id="kettles", question="which kettle should the office buy?")
    assert fresh["stage"] == 1
    assert verbs["frame_confirm"](analysis_id="kettles")["confirmed"] is False
