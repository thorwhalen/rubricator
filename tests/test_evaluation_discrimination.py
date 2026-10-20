"""Family A (#91): accuracy by confidence level, inflation as a gate, no mean over an ordinal."""

from __future__ import annotations

import pytest

from rubricator.evaluation import (
    DISCRIMINATION_SUITE,
    Metric,
    confidence_report,
    expected_subject,
    gate_failures,
    run_suite,
)
from rubricator.evaluation.harness import Fixture

SPAN = [{"id": "e", "sourceType": "primary", "selectors": [{"type": "TextQuoteSelector", "exact": "x"}]}]
INFERENCE = [{"id": "i", "sourceType": "agent-inference"}]


def _cell(alt, crit, measure, value=None, *, evidence=None, missing=None):
    assertion = {"version": 1, **({"value": value} if value is not None else {}),
                 **({"evidence": evidence} if evidence else {}), **({"missing": {"code": missing}} if missing else {})}
    return {"alternativeId": alt, "criterionId": crit, "measure": measure, "assertions": [assertion]}


def _analysis(*cells, alts="abcd"):
    return {"alternatives": [{"id": a} for a in alts], "criteria": [{"id": "c"}], "cells": list(cells)}


def _fixture(expected) -> Fixture:
    return Fixture(id="f", family="k", expected=expected, sources={}, meta={}, digest="d")


TRUTH = _analysis(*(_cell(a, "c", "score", 3) for a in "abcd"))


def _measure(name, produced, expected=TRUTH):
    metric = next(m for m in DISCRIMINATION_SUITE if m.name == name)
    return metric.measure(_fixture(expected), produced)


def test_accuracy_is_computed_per_level() -> None:
    produced = _analysis(
        _cell("a", "c", "score", 3, evidence=SPAN), _cell("a", "c", "confidence", 3),
        _cell("b", "c", "score", 3, evidence=SPAN), _cell("b", "c", "confidence", 3),
        _cell("c", "c", "score", 1, evidence=SPAN), _cell("c", "c", "confidence", 1),
        _cell("d", "c", "score", 3, evidence=SPAN), _cell("d", "c", "confidence", 1),
    )
    assert _measure("accuracy_at_confidence_high", produced) == 1.0
    assert _measure("accuracy_at_confidence_low", produced) == 0.5
    assert _measure("accuracy_at_confidence_medium", produced) is None


def test_inflation_counts_high_cells_without_a_span_or_with_only_inference() -> None:
    produced = _analysis(
        _cell("a", "c", "score", 3, evidence=SPAN), _cell("a", "c", "confidence", 3),
        _cell("b", "c", "score", 3, evidence=INFERENCE), _cell("b", "c", "confidence", 3),
        _cell("c", "c", "score", 3), _cell("c", "c", "confidence", 3),
        _cell("d", "c", "score", 3), _cell("d", "c", "confidence", 1),  # low: not inflation
    )
    assert _measure("confidence_inflation_rate", produced) == 2 / 3


def test_laundering_is_a_low_confidence_guess_with_no_citable_span() -> None:
    produced = _analysis(
        _cell("a", "c", "score", 3, evidence=SPAN), _cell("a", "c", "confidence", 1),
        _cell("b", "c", "score", 3), _cell("b", "c", "confidence", 1),
    )
    assert _measure("low_confidence_laundering_rate", produced) == 0.5


def test_blank_inflation_counts_blanks_where_the_expected_analysis_has_a_value() -> None:
    expected = _analysis(_cell("a", "c", "score", 3), _cell("b", "c", "score", missing="not-evidenced"))
    produced = _analysis(
        _cell("a", "c", "score", missing="not-evidenced"), _cell("b", "c", "score", missing="not-evidenced"),
        alts="ab",
    )
    assert _measure("blank_inflation_rate", produced, expected) == 0.5


def test_the_report_gives_wilson_intervals_and_a_positive_trend_when_confidence_discriminates() -> None:
    cells = []
    for i, (level, right) in enumerate([(3, 1)] * 8 + [(1, 1)] * 2 + [(1, 0)] * 6):
        alt = f"a{i}"
        cells += [_cell(alt, "c", "score", 3 if right else 1, evidence=SPAN), _cell(alt, "c", "confidence", level)]
    alts = [f"a{i}" for i in range(16)]
    produced = _analysis(*cells, alts=alts)
    expected = _analysis(*(_cell(a, "c", "score", 3) for a in alts), alts=alts)
    report = confidence_report([(_fixture(expected), produced)], seed=1)
    high, low = report["levels"]["high"], report["levels"]["low"]
    assert (high["n"], high["correct"]) == (8, 8) and high["interval"][1] == 1.0 and high["interval"][0] < 1.0
    assert (low["n"], low["correct"]) == (8, 2)
    assert report["levels"]["medium"]["interval"] == [0.0, 1.0]
    assert report["trend"]["tau"] > 0 and report["trend"]["p"] < 0.05


def test_the_gate_fails_on_inflation_and_on_an_unmeasured_run() -> None:
    inflated = _analysis(_cell("a", "c", "score", 3), _cell("a", "c", "confidence", 3), alts="a")
    fixture = _fixture(inflated)
    subject = expected_subject()
    report = run_suite([fixture], DISCRIMINATION_SUITE, subject=subject)
    assert "exceeds the ceiling" in gate_failures(report)[0]
    clean = _analysis(_cell("a", "c", "score", 3, evidence=SPAN), _cell("a", "c", "confidence", 3), alts="a")
    assert gate_failures(run_suite([_fixture(clean)], DISCRIMINATION_SUITE)) == []
    assert gate_failures({"metrics": {}}) == ["confidence_inflation_rate was not measured"]


def test_the_suite_refuses_a_mean_over_confidence() -> None:
    mean_confidence = Metric("mean_confidence", version=1, tier="nightly", ordinal=True,
                             measure=lambda f, p: 2.0)
    with pytest.raises(ValueError, match="ordinal"):
        run_suite([_fixture(TRUTH)], [mean_confidence])
