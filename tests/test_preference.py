"""The direction of preference (#32), as comparanda v1 shipped it.

Required on every measurement; ordered levels carry a range; ``target`` needs
``range.target``. A criterion that states none gets the preset's direction, and
that default is reported rather than silent.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.merge import merge_contributions
from rubricator.tools.analysis import analysis_open, criteria_set

ANCHORS = {"1": "none", "3": "some", "5": "all"}


@pytest.fixture()
def rt():
    rt = build_runtime(blobs={})
    analysis_open(rt.store, analysis_id="a", question="which?")
    return rt


def _set(rt, **kw):
    return criteria_set(rt.store, analysis_id="a", criteria=[
        {"id": "c", "label": "Cost exposure", "anchors": ANCHORS, **kw}])


def _measurement(rt):
    return merge_contributions(rt.store.frame("a"), [])["criteria"][0]["defaultMeasurement"]


def test_a_stated_direction_is_emitted_and_validates(rt) -> None:
    result = _set(rt, preference="decreasing")
    assert result["defaultedPreference"] == []
    assert _measurement(rt)["preference"] == "decreasing"
    assert rt.schema.validate(merge_contributions(rt.store.frame("a"), [])).ok


def test_an_unstated_direction_is_defaulted_and_reported(rt) -> None:
    assert _set(rt)["defaultedPreference"] == ["c"]
    assert _measurement(rt)["preference"] == "increasing"


def test_a_target_sets_range_target(rt) -> None:
    _set(rt, preference="target", target=3)
    m = _measurement(rt)
    assert m["preference"] == "target" and m["range"] == {"min": 1, "max": 5, "target": 3}
    assert rt.schema.validate(merge_contributions(rt.store.frame("a"), [])).ok


@pytest.mark.parametrize("kw, match", [
    ({"preference": "higher"}, "the directions are"),
    ({"preference": "target"}, "no numeric"),
    ({"preference": "target", "target": 9}, "outside its range"),
    ({"preference": "increasing", "target": 3}, "not \"target\""),
])
def test_an_ill_formed_direction_is_refused(rt, kw, match) -> None:
    with pytest.raises(ValueError, match=match):
        _set(rt, **kw)


def test_the_preset_is_not_mutated_by_a_target(rt) -> None:
    from rubricator.tools.analysis import SCALE_PRESETS

    _set(rt, preference="target", target=2)
    assert "target" not in SCALE_PRESETS["ordinal-1-5-anchored"]["measurement"]["range"]


def test_changing_direction_is_a_material_revision(rt) -> None:
    _set(rt)
    result = _set(rt, preference="decreasing")
    assert result["criteriaVersion"] == "2"
    assert result["revised"]["c"] == {"fields": ["defaultMeasurement"], "material": True}
