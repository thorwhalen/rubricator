"""Family B, proper scoring over ``certainty`` (#92): the numbers, and the fence around the measure."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from rubricator.evaluation.harness import Fixture
from rubricator.evaluation.proper_scoring import (
    ALLOWED_CERTAINTY, CERTAINTY, certainty_report, graded_certainty,
)

ROOT = Path(__file__).resolve().parents[1]


def _cell(alt, crit, value, measure="score"):
    return {"alternativeId": alt, "criterionId": crit, "measure": measure,
            "assertions": [{"version": 1, "value": value}]}


def _analysis(*cells):
    return {"alternatives": [{"id": a} for a in "abc"], "criteria": [{"id": "x"}], "cells": list(cells)}


FIXTURE = Fixture(id="f1", family="test", expected=_analysis(_cell("a", "x", 4), _cell("b", "x", 2), _cell("c", "x", 5)),
                  sources={}, meta={}, digest="")
PRODUCED = _analysis(_cell("a", "x", 4), _cell("b", "x", 3), _cell("c", "x", 5))


def test_pairs_are_the_stated_certainty_and_family_as_correctness() -> None:
    got = graded_certainty(FIXTURE, PRODUCED, {("a", "x"): 0.9, ("b", "x"): 0.7})
    assert sorted(got) == [(0.7, False), (0.9, True)]  # c has no stated certainty: left out


def test_a_certainty_outside_the_closed_set_is_refused() -> None:
    with pytest.raises(ValueError, match="allowed values"):
        graded_certainty(FIXTURE, PRODUCED, {("a", "x"): 0.3})


def test_a_produced_analysis_carrying_certainty_is_refused() -> None:
    leaked = _analysis(_cell("a", "x", 4), _cell("a", "x", 0.9, measure=CERTAINTY))
    with pytest.raises(ValueError, match="never in an analysis"):
        graded_certainty(FIXTURE, leaked, {("a", "x"): 0.9})


def test_certainty_never_reaches_a_delivered_analysis() -> None:
    """The other side of the fence: the write path will not store it, and no tool's schema names it."""
    spec = importlib.util.spec_from_file_location("scenarios", ROOT / "scripts/add_criterion_scenarios.py")
    scenarios = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenarios)
    verbs = scenarios.build()
    with pytest.raises(ValueError, match="certainty"):
        verbs["measures_write"](analysis_id="kettles", contributor_id="ana", author=scenarios.ANA, cells=[
            {"alternativeId": "tamsin", "criterionId": "quietness", "measure": CERTAINTY, "value": 0.7}])
    with pytest.raises((KeyError, ValueError), match="certainty"):
        verbs["criteria_set"](analysis_id="kettles", criteria=[], confidence_scale=CERTAINTY)
    from rubricator.surface.frozen import FROZEN_TOOLS

    for tool in FROZEN_TOOLS:
        assert CERTAINTY not in json.dumps([tool.input_schema, tool.output_schema]), tool.name


def test_murphy_decomposition_is_exact_on_the_allowed_values() -> None:
    pairs = [(0.9, True)] * 7 + [(0.9, False)] * 3 + [(0.6, True)] * 2 + [(0.6, False)] * 4 + [(0.5, True)]
    r = certainty_report(pairs)
    assert r["brier"] == pytest.approx(r["reliability"] - r["resolution"] + r["uncertainty"])
    assert r["skill"] == pytest.approx(1 - r["brier"] / r["uncertainty"])
    curve = {b["certainty"]: b for b in r["reliability_curve"]}
    assert [b["certainty"] for b in r["reliability_curve"]] == list(ALLOWED_CERTAINTY)
    assert (curve[0.9]["n"], curve[0.9]["observed"]) == (10, 0.7)
    assert curve[0.95]["n"] == 0 and curve[0.95]["observed"] is None


def test_a_perfectly_calibrated_forecaster_has_zero_reliability() -> None:
    pairs = [(0.9, True)] * 9 + [(0.9, False)] + [(0.5, True)] * 5 + [(0.5, False)] * 5
    r = certainty_report(pairs)
    assert r["reliability"] == pytest.approx(0.0) and r["skill"] > 0


def test_ece_is_withheld_below_the_minimum_and_reported_from_it() -> None:
    small = certainty_report([(0.9, True)] * 10 + [(0.5, False)] * 10)
    assert small["ece"] is None and "below the 100" in small["eceWithheld"]
    big = certainty_report([(0.9, True)] * 60 + [(0.5, False)] * 60)
    assert big["ece"] == pytest.approx(0.3) and big["eceWithheld"] is None
    keys = list(big)
    assert keys.index("brier") < keys.index("ece"), "ECE is reported second, behind the proper score"


def test_auroc_counts_ties_half_and_needs_both_outcomes() -> None:
    assert certainty_report([(0.9, True), (0.5, False)])["auroc"] == 1.0
    assert certainty_report([(0.5, True), (0.5, False)])["auroc"] == 0.5
    assert certainty_report([(0.9, True), (0.7, True)])["auroc"] is None


def test_nothing_graded_is_none_never_zero() -> None:
    r = certainty_report([])
    assert r["n"] == 0 and r["brier"] is None and r["skill"] is None and r["auroc"] is None


def test_an_all_right_run_has_no_skill_score_rather_than_a_division_by_zero() -> None:
    r = certainty_report([(0.9, True)] * 4)
    assert r["uncertainty"] == 0 and r["skill"] is None
