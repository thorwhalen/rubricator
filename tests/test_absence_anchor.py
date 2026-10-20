"""An anchor worded as an absence of evidence is refused at authoring (#124, ADR-0012).

"No source states X" is met precisely when there is nothing to quote, so no span can
support it. ``criteria_set`` refuses one with the rewrite, so the scorer never meets it.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.tools.analysis import analysis_open, criteria_set


@pytest.fixture()
def store():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?")
    return s


def _set(store, level_1: str):
    return criteria_set(store, analysis_id="a", criteria=[{
        "id": "residency", "label": "Data residency",
        "anchors": {"1": level_1, "3": "a source names a region without a guarantee",
                    "5": "a source states a contractual EU-only guarantee"},
    }])


@pytest.mark.parametrize("anchor", [
    "no source states where data is stored",
    "No documentation of the storage region",
    "nothing is published about the storage region",
    "the region is not stated",
    "the sources are silent on where data is stored",
    "none of the sources names a region",
    "no evidence of an EU region",
])
def test_an_absence_worded_anchor_is_refused_with_the_rewrite(store, anchor) -> None:
    with pytest.raises(ValueError, match=r'level 1 worded as an absence.*"a source states there is no X"'):
        _set(store, anchor)
    assert store.frame("a").get("criteria", []) == []


@pytest.mark.parametrize("anchor", [
    "a source states there is no EU region",
    "the vendor states data may be stored anywhere",
    "no commitment to a region",
    "a source states that no documentation of the region exists",
])
def test_a_condition_a_source_can_state_is_accepted(store, anchor) -> None:
    _set(store, anchor)
    (criterion,) = store.frame("a")["criteria"]
    assert criterion["defaultMeasurement"]["anchors"]["levels"]["1"] == anchor
