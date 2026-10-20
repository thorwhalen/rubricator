"""``stability_report`` (#98): complete with no weights, every agreement figure labelled by its rung."""

from __future__ import annotations

import copy
import random
from typing import Any

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent
from rubricator.stats import kendall_tau_b
from rubricator.tools.analysis import (
    alternatives_set, analysis_open, criteria_set, frame_set, measures_write,
)
from rubricator.tools.stability import stability_report

PRIMARY = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
            "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
AUTHORS = [{"id": "bot", "kind": "agent", "agent": {"name": "r", "model": "m"}},
           {"id": "ana", "kind": "human", "displayName": "Ana"}]


def _criterion(cid: str, **measurement: Any) -> dict[str, Any]:
    m = {"level": "ordinal", "levels": [1, 2, 3, 4, 5], "range": {"min": 1, "max": 5},
         "preference": "increasing", **measurement}
    return {"id": cid, "label": cid.upper(), "defaultMeasurement": m}


def _cell(alt: str, crit: str, draws: list[Any], *, rung: str = "shared-context",
          author: str = "bot") -> dict[str, Any]:
    assertions = [
        {"id": f"{alt}-{crit}-{i}", "authorId": author, "value": v, "justification": "j",
         "evidence": PRIMARY, "independence": rung, "roundId": f"round-{i + 1}"}
        for i, v in enumerate(draws)
    ]
    return {"alternativeId": alt, "criterionId": crit, "measure": "score", "assertions": assertions}


def _document(scores: dict[tuple[str, str], list[Any]], criteria=None, **extra: Any) -> dict[str, Any]:
    alts = sorted({a for a, _ in scores})
    crits = criteria or [_criterion(c) for c in sorted({c for _, c in scores})]
    return {"id": "a", "alternatives": [{"id": a, "label": a} for a in alts], "criteria": crits,
            "authors": AUTHORS, "missingCodes": [],
            "cells": [_cell(a, c, v) for (a, c), v in scores.items() if v], **extra}


class _Store:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def read_skipping(self, analysis_id: str):
        return copy.deepcopy(self.document), []


def _report(document, **kw):
    return stability_report(_Store(document), analysis_id="a", **kw)


def _rate(out, alt):
    return next(r["rate"] for r in out["dominanceSurvival"] if r["alternativeId"] == alt)


#: Three passes. x beats y on both criteria in passes 1 and 2; in pass 3 y.c1 rises to 5
#: and the two are incomparable, so y survives one matrix of three.
THREE = {("x", "c1"): [4, 4, 4], ("x", "c2"): [4, 4, 4],
         ("y", "c1"): [3, 3, 5], ("y", "c2"): [3, 3, 3]}


def test_the_weight_free_report_is_complete_with_no_weights() -> None:
    out = _report(_document(THREE))
    assert out["repeatedMatrices"] == 3 and out["basis"] == ["c1", "c2"]
    assert _rate(out, "x") == 1.0 and _rate(out, "y") == pytest.approx(1 / 3, abs=1e-6)
    # Fronts {x}, {x}, {x, y}: pairs (1,2) 0, (1,3) 1/2, (2,3) 1/2.
    assert out["paretoChurn"] == pytest.approx(1 / 3, abs=1e-6)
    assert out["weighted"] is None and "no weights declared" in out["summary"]
    assert len(out["perCell"]) == 4
    assert [c for c in out["perCell"] if c["span"]] == [
        {"alternativeId": "y", "criterionId": "c1", "n": 3, "span": 2, "polarised": False}]
    c1 = next(c for c in out["perCriterion"] if c["criterionId"] == "c1")
    # Pairs within x.c1 all agree (3), within y.c1 one of three agrees: 4 of 6.
    assert c1["agreement"] == pytest.approx(4 / 6, abs=1e-6)
    assert c1["repeatedCells"] == 2


def test_in_session_agreement_is_labelled_self_consistency_never_inter_rater() -> None:
    c1 = _report(_document(THREE))["perCriterion"][0]
    assert c1["lowestRung"] == "shared-context"
    assert "self-consistency" in c1["agreementLabel"] and "not inter-rater" in c1["agreementLabel"]


def test_one_human_does_not_launder_in_session_draws() -> None:
    doc = _document({("x", "c1"): [3, 3], ("y", "c1"): [2]})
    doc["cells"][0]["assertions"].append(
        {"id": "h", "authorId": "ana", "value": 3, "justification": "j", "evidence": PRIMARY,
         "independence": "independent"})
    c1 = _report(doc)["perCriterion"][0]
    assert c1["lowestRung"] == "shared-context" and "not inter-rater" in c1["agreementLabel"]


def test_fresh_sessions_read_as_test_retest() -> None:
    doc = _document({})
    doc["alternatives"] = [{"id": "x", "label": "x"}]
    doc["criteria"] = [_criterion("c1")]
    doc["cells"] = [_cell("x", "c1", [3, 4], rung="resampled")]
    c1 = _report(doc)["perCriterion"][0]
    assert c1["lowestRung"] == "resampled" and "test-retest" in c1["agreementLabel"]
    assert c1["agreement"] == 0.0


def test_one_pass_is_a_front_not_a_stability_figure() -> None:
    out = _report(_document({k: v[:1] for k, v in THREE.items()}))
    assert out["repeatedMatrices"] == 1 and out["paretoChurn"] == 0.0
    assert [_rate(out, a) for a in ("x", "y")] == [1.0, 0.0]
    assert all(c["agreement"] is None and c["agreementLabel"] is None for c in out["perCriterion"])
    assert "not a stability figure" in out["summary"]


def test_nothing_scored_says_so() -> None:
    out = _report(_document({("x", "c1"): [], ("y", "c1"): []}))
    assert out["repeatedMatrices"] == 0 and "Nothing has been scored" in out["summary"]


def test_blank_density_is_the_counter_metric_and_names_the_inflation() -> None:
    out = _report(_document({("x", "c1"): [4], ("y", "c1"): [], ("x", "c2"): [4], ("y", "c2"): [1]}))
    assert out["blankDensity"] == 0.25
    assert _rate(out, "y") == 1.0  # the blank makes y undominatable
    assert "inflate survival" in out["summary"]


def test_criteria_off_the_basis_are_named_and_still_reported() -> None:
    nominal = {"id": "n", "label": "N", "defaultMeasurement": {"level": "nominal", "levels": ["a", "b"]}}
    doc = _document({("x", "c1"): [4], ("x", "n"): ["a", "a"]},
                    criteria=[_criterion("c1"), nominal])
    out = _report(doc)
    assert out["basis"] == ["c1"] and "n left out" in out["summary"]
    n = next(c for c in out["perCriterion"] if c["criterionId"] == "n")
    assert n["agreement"] == 1.0 and n["histogram"] == [{"level": "a", "count": 0},
                                                        {"level": "b", "count": 0}]


def test_histogram_and_compression_read_the_reduced_column() -> None:
    doc = _document({("x", "c1"): [3], ("y", "c1"): [3], ("z", "c1"): [5]})
    c1 = _report(doc)["perCriterion"][0]
    assert [h["count"] for h in c1["histogram"]] == [0, 0, 2, 0, 1]
    assert c1["compression"] == pytest.approx(2 / 3, abs=1e-6)


def test_weights_give_the_secondary_report() -> None:
    out = _report(_document(THREE), weights=[{"criterionId": "c1", "weight": 1},
                                             {"criterionId": "c2", "weight": 1}])
    w = out["weighted"]
    # Pass 3: y totals 5+3 = 8 against x's 8, a tie: tau-b is undefined for the two pairs
    # with pass 3 in them and left out, never written as a number.
    assert w["tauDistribution"] == [1.0]
    assert w["top1Churn"] == pytest.approx(2 / 3, abs=1e-6)
    assert w["band"] in ("stable", "borderline", "unstable")
    assert "band" in out["summary"]


def test_tau_bands_set_the_verdict() -> None:
    weights = [{"criterionId": "c1", "weight": 1}]
    loose = _report(_document(THREE), weights=weights, tau_bands={"low": -1, "high": -1})
    assert loose["weighted"]["band"] == "stable"


def test_weights_with_one_matrix_say_why_there_is_no_tau() -> None:
    out = _report(_document({k: v[:1] for k, v in THREE.items()}),
                  weights=[{"criterionId": "c1", "weight": 1}])
    assert out["weighted"] is None and "nothing to compare with" in out["summary"]


@pytest.mark.parametrize("bands", [{"low": 0.9, "high": 0.7}, {"low": 0, "high": 2}, {"low": True, "high": 1}])
def test_bad_tau_bands_are_refused(bands) -> None:
    with pytest.raises(ValueError, match="refused: tau_bands"):
        _report(_document(THREE), tau_bands=bands)


def test_a_weight_off_the_basis_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be weighted"):
        _report(_document(THREE, criteria=[_criterion("c1"), _criterion("c2", preference="none")]),
                weights=[{"criterionId": "c2", "weight": 1}])


def test_same_input_twice_is_identical() -> None:
    doc = _document(THREE)
    assert _report(doc, weights=[{"criterionId": "c1", "weight": 2}]) == _report(
        doc, weights=[{"criterionId": "c1", "weight": 2}])


def test_vendored_tau_b_matches_scipy_on_weighted_totals() -> None:
    """The shape the weighted report feeds it: range-normalised totals with ties, a handful long."""
    scipy_stats = pytest.importorskip("scipy.stats")
    rng = random.Random(98)
    for _ in range(300):
        n = rng.randint(2, 12)
        x = [round(sum(rng.randint(0, 4) / 4 * w for w in (1.0, 0.5, 2.0)), 12) for _ in range(n)]
        y = [round(sum(rng.randint(0, 4) / 4 * w for w in (1.0, 0.5, 2.0)), 12) for _ in range(n)]
        ours, theirs = kendall_tau_b(x, y), scipy_stats.kendalltau(x, y).statistic
        assert (ours != ours and theirs != theirs) or abs(ours - theirs) < 1e-12, (x, y)


def test_passes_written_through_the_store_pair_by_round() -> None:
    bot = agent("bot", "Bot", name="rubricator", model="model-a", prompt_version="v4", run_id="r1")
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True,
                  at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}])
    criteria_set(s, analysis_id="a", criteria=[
        {"id": "c", "label": "C", "anchors": {"1": "none", "3": "some", "5": "all"}}])
    for n, (vx, vy) in enumerate([(4, 2), (4, 5)], start=1):
        measures_write(
            s, analysis_id="a", contributor_id="bot", author=bot, at=f"2026-10-12T12:0{n}:00Z",
            procedure={"round": n, "session": "fresh"},
            cells=[{"alternativeId": alt, "criterionId": "c", "value": v, "justification": "j",
                    "evidence": PRIMARY} for alt, v in (("x", vx), ("y", vy))])
    out = stability_report(s, analysis_id="a")
    assert out["repeatedMatrices"] == 2 and out["perCriterion"][0]["repeatedCells"] == 2
    assert "test-retest" in out["perCriterion"][0]["agreementLabel"]
