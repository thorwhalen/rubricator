"""``criteria_set`` records floors and a confidence measure (#236), so a built analysis fills vetoFlags and lowConfidence."""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent
from rubricator.tools.analysis import (
    alternatives_set, analysis_open, criteria_set, frame_set, measures_write,
)
from rubricator.tools.weaknesses import report_weaknesses

ANCHORS = {"1": "none", "3": "some", "5": "all"}
PRIMARY = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
            "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
BOT = agent("bot", "Bot", name="rubricator", model="model-a", prompt_version="v4", run_id="r1")
FLOOR = {"threshold": 3, "rationale": "below 3 the vendor cannot meet the audit"}


def _store(**criteria_kw):
    store = build_runtime(blobs={}).store
    analysis_open(store, analysis_id="a", question="which?", allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(store, analysis_id="a", ambiguities=[])
    alternatives_set(store, analysis_id="a", alternatives=[{"id": a, "label": a} for a in "xy"])
    criteria_set(store, analysis_id="a", criteria=[
        {"id": "c1", "label": "C1", "anchors": ANCHORS, "acceptability": FLOOR},
        {"id": "c2", "label": "C2", "anchors": ANCHORS}], **criteria_kw)
    return store


def _write(store, *cells):
    measures_write(store, analysis_id="a", contributor_id="bot", author=BOT, at="2026-10-12T12:00:00Z", cells=[
        {"alternativeId": a, "criterionId": c, "measure": m, "value": v, "justification": "j", "evidence": PRIMARY}
        for a, c, m, v in cells])


def test_a_floor_and_a_confidence_measure_fill_both_lists() -> None:
    store = _store(confidence_scale="confidence-1-3")
    _write(store, ("x", "c1", "score", 2), ("y", "c1", "score", 4), ("x", "c2", "score", 3),
           ("y", "c2", "score", 3), ("x", "c1", "confidence", 1), ("y", "c1", "confidence", 3))
    out = report_weaknesses(store, analysis_id="a")
    assert [(v["alternativeId"], v["criterionId"]) for v in out["vetoFlags"]] == [("x", "c1")]
    assert FLOOR["rationale"] in out["vetoFlags"][0]["reason"]
    assert [(r["alternativeId"], r["criterionId"]) for r in out["lowConfidence"]] == [("x", "c1")]
    assert "no confidence measure recorded" not in out["summary"]


def test_a_confidence_value_is_checked_against_the_confidence_scale() -> None:
    store = _store(confidence_scale="confidence-1-3")
    with pytest.raises(ValueError, match=r"value 5 is not one of the levels its scale declares \(1, 2, 3\)"):
        _write(store, ("x", "c1", "confidence", 5))


def test_without_a_confidence_scale_the_measure_is_not_declared() -> None:
    store = _store()
    with pytest.raises(ValueError, match='measure "confidence" is not one this analysis declares'):
        _write(store, ("x", "c1", "confidence", 1))


def test_a_later_call_that_omits_the_confidence_scale_keeps_it() -> None:
    store = _store(confidence_scale="confidence-1-3")
    criteria_set(store, analysis_id="a", criteria=[{"id": "c1", "label": "C1", "anchors": ANCHORS},
                                                   {"id": "c2", "label": "C2", "anchors": ANCHORS}])
    frame = store.frame("a")
    assert all(c["measurements"]["confidence"]["scale"] == "confidence-1-3" for c in frame["criteria"])
    assert [m["name"] for m in frame["measures"]] == ["score", "confidence"]


@pytest.mark.parametrize("floor, match", [
    ({"threshold": 9, "rationale": "r"}, "off its scale"),
    ({"threshold": 3, "rationale": " "}, "needs a rationale"),
])
def test_a_floor_nobody_could_test_or_explain_is_refused(floor, match) -> None:
    store = _store()
    with pytest.raises(ValueError, match=match):
        criteria_set(store, analysis_id="a", criteria=[{"id": "c1", "label": "C1", "anchors": ANCHORS,
                                                        "acceptability": floor}])


@pytest.mark.parametrize("scale, error", [("nope", KeyError), ("ordinal-1-5-anchored", ValueError)])
def test_an_unknown_or_anchored_confidence_scale_is_refused(scale, error) -> None:
    with pytest.raises(error):
        _store(confidence_scale=scale)


def test_confidence_cells_can_be_marked_missing() -> None:
    from rubricator.tools.analysis import measures_mark_missing
    from rubricator.tools.views import outstanding_cells

    store = _store(confidence_scale="confidence-1-3")
    _write(store, *[(a, c, "score", 3) for a in "xy" for c in ("c1", "c2")])
    measures_mark_missing(store, analysis_id="a", contributor_id="bot", author=BOT, at="2026-10-12T12:00:00Z",
                          code="not-assessed", note="confidence not recorded on this pass", measure="confidence")
    owed = outstanding_cells(store.read("a"))
    assert {o["measure"] for o in owed} == {"confidence"} and all(o["code"] == "not-assessed" for o in owed)


def test_a_floor_on_a_criterion_with_no_direction_is_refused() -> None:
    store = _store()
    with pytest.raises(ValueError, match="a floor needs a direction"):
        criteria_set(store, analysis_id="a", criteria=[{"id": "c1", "label": "C1", "anchors": ANCHORS,
                                                        "preference": "target", "target": 3,
                                                        "acceptability": FLOOR}])


def test_an_emptied_measures_list_keeps_score_beside_confidence() -> None:
    store = _store()
    frame = store.frame("a")
    frame["measures"] = []
    from rubricator.tools.analysis import _put_frame

    _put_frame(store, "a", frame)
    criteria_set(store, analysis_id="a", criteria=[{"id": "c1", "label": "C1", "anchors": ANCHORS}],
                 confidence_scale="confidence-1-3")
    assert [m["name"] for m in store.frame("a")["measures"]] == ["score", "confidence"]
