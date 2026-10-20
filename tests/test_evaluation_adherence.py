"""Instruction adherence (#94): a partial fill leaves the rest *deferred*, fixed criteria are not extended."""

from __future__ import annotations

import copy
import json

from rubricator.compose import build_runtime
from rubricator.evaluation import (
    ADHERENCE_SUITE,
    DEFERRAL_ADHERENCE,
    INVENTED_CRITERIA,
    expected_subject,
    load_fixtures,
    run_suite,
)
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    measures_mark_missing,
)

AT = "2026-10-20T00:00:00Z"
AUTHOR = {"kind": "agent", "id": "m", "displayName": "m"}
ANCHORS = {"1": "poor", "3": "fair", "5": "good"}


def _analysis(*, code_for_rest: str = "deferred", extra_criterion: bool = False) -> dict:
    """An invented partial fill: Pain and Market looked at, Team left, built by the tools."""
    store = build_runtime(blobs={}).store
    analysis_open(store, analysis_id="x", question="Which idea?", allow_skip_confirmation=True, at=AT)
    alternatives_set(store, analysis_id="x", alternatives=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}])
    ids = ["pain", "market", "team"] + (["buzz"] if extra_criterion else [])
    criteria_set(store, analysis_id="x", criteria=[{"id": i, "label": i.title(), "anchors": ANCHORS} for i in ids])
    mark = dict(analysis_id="x", contributor_id="m", author=AUTHOR, at=AT)
    measures_mark_missing(store, **mark, code="not-evidenced", note="sources silent", criterion_ids=["pain", "market"])
    measures_mark_missing(store, **mark, code=code_for_rest, note="left for later", criterion_ids=["team"])
    return store.read("x")


def _fixtures(instruction: dict, analysis: dict):
    return load_fixtures({
        "idea/fixture.json": json.dumps({"id": "idea", "family": "adherence", "instruction": instruction}).encode(),
        "idea/expected.json": json.dumps(analysis).encode(),
    })


PARTIAL = {"fill": ["pain", "market"], "defer": ["team"]}


def _score(instruction: dict, analysis: dict, metric) -> float | None:
    (fixture,) = _fixtures(instruction, analysis)
    return metric.measure(fixture, copy.deepcopy(analysis))


def test_a_correct_partial_fill_scores_perfectly() -> None:
    analysis = _analysis()
    assert _score(PARTIAL, analysis, DEFERRAL_ADHERENCE) == 1.0
    assert _score(PARTIAL, analysis, INVENTED_CRITERIA) == 0.0


def test_not_assessed_is_not_deferred() -> None:
    """The distinction ADR-0008 names: the rest must be *deferred*, not left unasked."""
    analysis = _analysis(code_for_rest="not-assessed")
    assert _score(PARTIAL, analysis, DEFERRAL_ADHERENCE) == 4 / 6


def test_a_deferred_cell_where_a_fill_was_asked_does_not_count_as_filled() -> None:
    analysis = _analysis()
    assert _score({"fill": ["pain", "market", "team"]}, analysis, DEFERRAL_ADHERENCE) == 4 / 6


def test_a_missing_cell_does_not_comply() -> None:
    analysis = _analysis()
    analysis["cells"] = [c for c in analysis["cells"] if c["criterionId"] != "team"]
    assert _score(PARTIAL, analysis, DEFERRAL_ADHERENCE) == 4 / 6


def test_an_invented_criterion_is_counted() -> None:
    analysis = _analysis(extra_criterion=True)
    assert _score({"criteria": ["pain", "market", "team"]}, analysis, INVENTED_CRITERIA) == 1.0


def test_a_tombstoned_criterion_is_not_an_invention() -> None:
    analysis = _analysis(extra_criterion=True)
    for criterion in analysis["criteria"]:
        if criterion["id"] == "buzz":
            criterion["tombstoned"] = True
    assert _score({"criteria": ["pain", "market", "team"]}, analysis, INVENTED_CRITERIA) == 0.0


def test_a_fixture_without_the_instruction_is_not_applicable() -> None:
    analysis = _analysis()
    assert _score({}, analysis, DEFERRAL_ADHERENCE) is None
    assert _score({}, analysis, INVENTED_CRITERIA) is None


def test_the_suite_runs_through_the_harness_and_the_expected_replay_is_perfect() -> None:
    fixtures = _fixtures(PARTIAL, _analysis())
    report = run_suite(fixtures, ADHERENCE_SUITE, subject=expected_subject(), resamples=50, now=lambda: AT)
    assert report["metrics"]["deferral_adherence"]["mean"] == 1.0
    assert report["metrics"]["invented_criteria"]["mean"] == 0.0
