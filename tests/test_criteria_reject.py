"""``criteria_reject`` records rejected criteria with ADR-0016's closed reason (#259, ADR-0026).

The pinned comparanda ``reasonCode`` is another closed set, so each entry is
stored as ``other`` (``merged`` for a merge) with the ADR code prefixed on
``reason``, which keeps rejects countable until the schema learns the codes.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.ladder import REJECT_REASON_CODES, REJECT_REASONS, rejection_record
from rubricator.tools.analysis import alternatives_set, analysis_open, criteria_reject, criteria_set, frame_set
from rubricator.tools.views import analysis_get

ANCHORS = {"1": "none", "3": "some", "5": "all"}
AT = "2026-10-30T12:00:00Z"


@pytest.fixture()
def store():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(s, analysis_id="a", criteria=[
        {"id": "speed", "label": "Speed", "anchors": ANCHORS, "provenance": {"origin": "user-stated"}}])
    return s


def test_every_adr_code_has_a_stored_spelling() -> None:
    assert set(REJECT_REASON_CODES) == set(REJECT_REASONS)
    assert {r["reasonCode"] for r in (rejection_record("l", c, "why", merged_into="m") for c in REJECT_REASONS)} == {"merged", "other"}


def test_a_reject_is_stored_with_the_code_on_its_reason_and_survives_criteria_set(store) -> None:
    out = criteria_reject(store, analysis_id="a", at=AT, rejected=[
        {"label": "Brand", "code": "means-objective", "reason": "it serves reliability"},
        {"label": "Pace", "code": "merged-into", "reason": "the same as speed", "mergedIntoId": "speed", "proposedBy": "agent"},
    ])
    assert (out["written"], out["total"]) == (2, 2)
    assert out["byCode"] == [{"code": "means-objective", "count": 1}, {"code": "merged-into", "count": 1}]
    assert store.frame("a")["rejectedCriteria"] == [
        {"label": "Brand", "reason": "means-objective: it serves reliability", "reasonCode": "other", "at": AT},
        {"label": "Pace", "reason": "merged-into: the same as speed", "reasonCode": "merged", "mergedIntoId": "speed",
         "proposedBy": "agent", "at": AT},
    ]
    criteria_set(store, analysis_id="a", criteria=[{"id": "speed", "label": "Speed", "anchors": ANCHORS}])
    assert len(store.frame("a")["rejectedCriteria"]) == 2


def test_the_same_reject_is_not_recorded_twice_and_later_ones_add(store) -> None:
    one = {"label": "Brand", "code": "means-objective", "reason": "it serves reliability"}
    criteria_reject(store, analysis_id="a", at=AT, rejected=[one])
    again = criteria_reject(store, analysis_id="a", at=AT, rejected=[one, {"label": "Colour", "code": "user-rejected", "reason": "no one cares"}])
    assert (again["written"], again["total"]) == (1, 2)
    assert "already recorded" in again["summary"]


@pytest.mark.parametrize("entry, why", [
    ({"label": "B", "code": "bogus", "reason": "r"}, "unknown reason"),
    ({"label": " ", "code": "user-rejected", "reason": "r"}, "needs a label"),
    ({"label": "B", "code": "user-rejected", "reason": ""}, "needs a label"),
    ({"label": "B", "code": "merged-into", "reason": "r"}, "must be one of the criteria now declared"),
    ({"label": "B", "code": "merged-into", "reason": "r", "mergedIntoId": "ghost"}, "must be one of the criteria"),
    ({"label": "B", "code": "user-rejected", "reason": "r", "mergedIntoId": "speed"}, "only \"merged-into\""),
    ({"label": "speed", "code": "user-rejected", "reason": "r"}, "is a criterion of this analysis"),
    ({"label": "B", "code": "user-rejected", "reason": "r", "url": "u"}, "url"),
])
def test_a_bad_entry_is_refused_and_nothing_is_written(store, entry, why) -> None:
    with pytest.raises(ValueError, match=why):
        criteria_reject(store, analysis_id="a", at=AT, rejected=[{"label": "Fine", "code": "user-rejected", "reason": "ok"}, entry])
    assert store.frame("a")["rejectedCriteria"] == []


def test_a_criterion_provenance_is_kept_and_read_back_as_criteria_set_takes_it(store) -> None:
    assert store.frame("a")["criteria"][0]["provenance"] == {"origin": "user-stated"}
    view = analysis_get(store, analysis_id="a", view="criteria")
    assert view["criteria"][0]["provenance"] == {"origin": "user-stated"}


def test_an_unknown_provenance_origin_is_refused(store) -> None:
    with pytest.raises(ValueError):
        criteria_set(store, analysis_id="a", criteria=[
            {"id": "speed", "label": "Speed", "anchors": ANCHORS, "provenance": {"origin": "a-guess"}}])
