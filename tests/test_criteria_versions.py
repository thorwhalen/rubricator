"""Criteria-set versions (#28, ADR-0016), as comparanda v1 shipped them.

A meaning change moves ``criteriaVersion``; a material one also moves the
criterion's ``definedInVersion``; every assertion records the version it was
scored against; scores under an older definition are reported as superseded.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.criteria_versions import compare_versions, next_version, superseded_cells
from rubricator.merge import merge_contributions
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    frame_set,
    measures_write,
)

#: A span every scored cell here cites: since #171 a value with no evidence is refused.
CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]

AT = "2026-10-12T00:00:00Z"
ANCHORS = {"1": "none", "3": "some", "5": "all"}
ANA = human("ana", "Ana")


@pytest.fixture()
def rt():
    rt = build_runtime(blobs={})
    analysis_open(rt.store, analysis_id="a", question="which?",
        allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(rt.store, analysis_id="a", ambiguities=[])
    alternatives_set(rt.store, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    return rt


def _criteria(rt, label="Support", *, extra=(), **kw):
    return criteria_set(rt.store, analysis_id="a", criteria=[
        {"id": "c", "label": label, "anchors": ANCHORS}, *extra], **kw)


def _score(rt, crit="c", value=4):
    measures_write(rt.store, analysis_id="a", contributor_id="ana", author=ANA, at=AT,
                   cells=[{"alternativeId": "x", "criterionId": crit, "value": value,
                           "justification": "because", "independence": "shared-context",
                           "evidence": CITED}])


def _doc(rt):
    return merge_contributions(rt.store.frame("a"), rt.store.contributions("a"))


def test_the_first_set_is_version_1_and_assertions_record_it(rt) -> None:
    result = _criteria(rt)
    assert result["criteriaVersion"] == "1" and result["revised"] == []
    _score(rt)
    doc = _doc(rt)
    assert doc["criteriaVersion"] == "1"
    assert doc["cells"][0]["assertions"][0]["criteriaVersion"] == "1"
    assert "definedInVersion" not in doc["criteria"][0]
    assert rt.schema.validate(doc).ok


def test_a_material_change_supersedes_earlier_scores(rt) -> None:
    _criteria(rt)
    _score(rt)
    result = _criteria(rt, label="Vendor support, dated")
    assert result["criteriaVersion"] == "2"
    assert result["revised"] == [{"criterionId": "c", "fields": ["label"], "material": True}]
    assert result["supersededCells"]["count"] == 1
    doc = _doc(rt)
    assert doc["criteria"][0]["definedInVersion"] == "2"
    _score(rt, value=3)
    current = superseded_cells(_doc(rt))
    assert [a["criteriaVersion"] for a in current["cells"][0]["assertions"]] == ["1"]
    assert rt.schema.validate(_doc(rt)).ok


def test_an_editorial_change_moves_the_set_but_supersedes_nothing(rt) -> None:
    _criteria(rt)
    _score(rt)
    result = _criteria(rt, label="Support.", editorial=["c"])
    assert result["criteriaVersion"] == "2"
    assert result["revised"][0]["material"] is False
    assert result["supersededCells"]["count"] == 0
    assert "definedInVersion" not in _doc(rt)["criteria"][0]


def test_an_unchanged_resubmission_does_not_move_the_version(rt) -> None:
    _criteria(rt)
    assert _criteria(rt)["criteriaVersion"] == "1"


def test_defined_in_version_is_carried_through_later_unrelated_changes(rt) -> None:
    other = {"id": "d", "label": "D", "anchors": ANCHORS}
    _criteria(rt, extra=[other])
    _criteria(rt, label="changed", extra=[other])
    result = _criteria(rt, label="changed", extra=[{**other, "label": "D2"}], editorial=["d"])
    assert result["criteriaVersion"] == "3"
    by_id = {c["id"]: c for c in _doc(rt)["criteria"]}
    assert by_id["c"]["definedInVersion"] == "2" and "definedInVersion" not in by_id["d"]


def test_dropping_a_scored_criterion_is_refused(rt) -> None:
    _criteria(rt, extra=[{"id": "d", "label": "D", "anchors": ANCHORS}])
    _score(rt, crit="d")
    with pytest.raises(ValueError, match="cells refer to them"):
        _criteria(rt)
    assert {c["id"] for c in rt.store.frame("a")["criteria"]} == {"c", "d"}


def test_dropping_an_unscored_criterion_is_allowed(rt) -> None:
    _criteria(rt, extra=[{"id": "d", "label": "D", "anchors": ANCHORS}])
    assert _criteria(rt)["criteria"] == ["c"]


def test_editorial_must_name_a_changed_criterion(rt) -> None:
    _criteria(rt)
    with pytest.raises(ValueError, match="did not change meaning"):
        _criteria(rt, editorial=["c"])


def test_versions_order_like_the_companions() -> None:
    assert compare_versions("2", "10") == -1
    assert compare_versions("01", "1") == 0
    assert compare_versions("1.2", "1.10") == -1
    assert compare_versions("x", "x") == 0 and compare_versions("x", "y") is None
    assert next_version("99999999999999999999") == "100000000000000000000"
    with pytest.raises(ValueError):
        next_version("draft")


def test_adding_an_empty_definition_is_a_meaning_change(rt) -> None:
    """Review finding 1: only missingCodes/measurements default to empty."""
    _criteria(rt)
    result = criteria_set(rt.store, analysis_id="a", criteria=[
        {"id": "c", "label": "Support", "anchors": ANCHORS, "definition": {}}])
    assert result["criteriaVersion"] == "2" and result["revised"][0]["fields"] == ["definition"]


def test_an_unmergeable_file_is_left_out_of_the_report_not_a_refusal(rt) -> None:
    """Review finding 2 was "merge before put_frame", when a forged file made the
    merge raise. Since #156 that file is left out of supersededCells and named, as
    every read leaves it out, so a colleague's broken file no longer refuses this."""
    _criteria(rt)
    rt.store.put_contribution("a", "ana", {"contributorId": "ana", "cells": [],
                                           "authors": [{"id": "ben", "displayName": "B",
                                                        "kind": "human"}]})
    result = _criteria(rt, label="changed")
    assert [s["file"] for s in result["skipped"]] == ["analyses/a/contributions/ana.json"]
    assert rt.store.frame("a")["criteriaVersion"] == result["criteriaVersion"]


def test_a_reintroduced_criterion_supersedes_stray_scores(rt) -> None:
    """Review finding 3: drop unscored d, a stray score on d, re-add d."""
    other = {"id": "d", "label": "D", "anchors": ANCHORS}
    _criteria(rt, extra=[other])
    _criteria(rt, label="v2")
    rt.store.put_contribution("a", "peer", {"contributorId": "peer", "authors": [], "cells": [
        {"alternativeId": "x", "criterionId": "d", "measure": "score", "assertions": [
            {"id": "s1", "authorId": "peer", "at": AT, "value": 3, "criteriaVersion": "1"}]}]})
    result = _criteria(rt, label="v3", extra=[{**other, "label": "D, new meaning"}])
    assert {c["criterionId"] for c in result["supersededCells"]["cells"]} == {"d"}


def test_scores_on_an_undeclared_criterion_are_refused(rt) -> None:
    _criteria(rt)
    with pytest.raises(KeyError, match="not in this analysis"):
        _score(rt, crit="ghost")


def test_a_stale_expected_version_is_refused(rt) -> None:
    _criteria(rt)
    _criteria(rt, label="v2")
    with pytest.raises(ValueError, match='criteria version "1"'):
        measures_write(rt.store, analysis_id="a", contributor_id="ana", author=ANA, at=AT,
                       expected_criteria_version="1",
                       cells=[{"alternativeId": "x", "criterionId": "c", "value": 4,
                               "justification": "b"}])


def test_the_version_parser_is_ascii_and_whole() -> None:
    assert compare_versions("1\n", "2") is None
    assert compare_versions("１", "2") is None
    with pytest.raises(ValueError):
        next_version("1\n")
