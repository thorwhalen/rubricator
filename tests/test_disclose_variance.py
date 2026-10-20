"""``disclose_variance`` (#100): the notice is filled from what was recorded, and claims nothing else."""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent
from rubricator.surface import bind
from rubricator.tools.analysis import (
    alternatives_set, analysis_open, criteria_set, frame_set, measures_write,
)
from rubricator.tools.disclosure import disclose_variance

CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
BOT = agent("bot", "Bot", name="rubricator", model="model-a", prompt_version="v4", run_id="r1")


@pytest.fixture()
def store():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True,
                  at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(s, analysis_id="a", criteria=[
        {"id": "c", "label": "C", "anchors": {"1": "none", "3": "some", "5": "all"}}])
    return s


def _pass(store, n, *, procedure=True, **facts):
    measures_write(
        store, analysis_id="a", contributor_id="bot", author=BOT, at=f"2026-10-12T12:0{n}:00Z",
        procedure={"round": n, "session": "fresh", **facts} if procedure else None,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": 3, "justification": "j",
                "evidence": CITED}])


def test_one_pass_discloses_n_equals_one_unmeasured(store) -> None:
    _pass(store, 1, traversal="cell-wise", reduction="lower-median", session="same")
    out = disclose_variance(store, analysis_id="a")
    assert "n = 1, unmeasured" in out["text"]
    assert "cell-wise" in out["text"]
    assert any("n = 1, unmeasured" in m for m in out["notMeasured"])
    assert "1 per cell" in out["text"]


def test_five_draws_differ_from_one_and_are_counted_not_read(store) -> None:
    for n in range(1, 6):
        _pass(store, n, traversal="cell-wise", reduction="lower-median", seed=n)
    out = disclose_variance(store, analysis_id="a")
    assert "5 per cell" in out["text"] and "(1 of 1 cells hold two or more)" in out["text"]
    assert "seeds 1, 2, 3, 4, 5" in out["text"]
    assert "test-retest" in out["text"]
    assert "n = 1, unmeasured" not in out["text"]
    assert out["procedureIds"] and out["measured"]
    assert any("stability figure" in m for m in out["notMeasured"])


def test_no_procedure_record_discloses_that_nothing_was_measured(store) -> None:
    _pass(store, 1, procedure=False)
    out = disclose_variance(store, analysis_id="a")
    assert out["procedureIds"] == []
    assert "Traversal: not recorded" in out["text"] and "Order: not recorded" in out["text"]
    assert any("no procedure record" in m for m in out["notMeasured"])


def test_it_is_deterministic_and_surface_bound(store) -> None:
    _pass(store, 1, traversal="cell-wise")
    runtime = build_runtime(blobs={})
    runtime.store.__dict__  # the bound verb exists and validates against the frozen row
    verbs = bind(runtime)
    assert "disclose_variance" in verbs
    assert disclose_variance(store, analysis_id="a") == disclose_variance(store, analysis_id="a")
