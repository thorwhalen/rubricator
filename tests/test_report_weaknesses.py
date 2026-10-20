"""``report_weaknesses`` (#64): pivotal cells are exact, the diagnostic says what it is not, redefine is not rescore."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent
from rubricator.tools.analysis import (
    alternatives_set, analysis_open, criteria_set, frame_set, measures_write,
)
from rubricator.tools.weaknesses import LEAKAGE_NOTE, report_weaknesses

PRIMARY = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
            "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
ANCHORS = {"levels": {"1": "none", "3": "some", "5": "all"}}


def _criterion(cid: str, **extra: Any) -> dict[str, Any]:
    measurement = {"level": "ordinal", "levels": [1, 2, 3, 4, 5], "range": {"min": 1, "max": 5},
                   "preference": "increasing", "anchors": ANCHORS}
    return {"id": cid, "label": cid.upper(), "defaultMeasurement": measurement, **extra}


def _cell(alt: str, crit: str, *values: Any, measure: str = "score", evidence=PRIMARY, missing=None):
    assertions = [{"id": f"{alt}-{crit}-{measure}-{i}", "authorId": "bot", "value": v,
                   "justification": "j", **({"evidence": evidence} if evidence else {})}
                  for i, v in enumerate(values)]
    if missing:
        assertions.append({"id": f"{alt}-{crit}-blank", "authorId": "bot", "missing": missing})
    return {"alternativeId": alt, "criterionId": crit, "measure": measure, "assertions": assertions}


def _document(scores: dict[tuple[str, str], int], **extra: Any) -> dict[str, Any]:
    alts = sorted({a for a, _ in scores})
    crits = sorted({c for _, c in scores})
    return {"id": "a", "alternatives": [{"id": a, "label": a} for a in alts],
            "criteria": [_criterion(c) for c in crits], "missingCodes": [],
            "cells": [_cell(a, c, v) for (a, c), v in scores.items()], **extra}


class _Store:
    """Just the read ``report_weaknesses`` makes."""

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def read_skipping(self, analysis_id: str):
        return copy.deepcopy(self.document), []


#: Hand-computed. x dominates y; x and z are incomparable, so the front is {x, z}.
#: x.c1 4 -> 5 makes x dominate z; z.c1 5 -> 4 does too. Nothing else moves the front:
#: x.c2 3 or 5 leaves x over y and not over z; y moving one level stays under x;
#: z.c2 can only go up, and (5, 2) is still incomparable with x.
PIVOT = {("x", "c1"): 4, ("x", "c2"): 4, ("y", "c1"): 3, ("y", "c2"): 3,
         ("z", "c1"): 5, ("z", "c2"): 1}


def _report(document, **kw):
    return report_weaknesses(_Store(document), analysis_id="a", **kw)


def test_pivotal_cells_match_the_hand_computed_fixture() -> None:
    out = _report(_document(PIVOT), budget=10)
    assert out["dominatedAlternatives"] == ["y"]
    rescore = out["rescoringPlan"]["rescore"]
    pivotal = [(r["alternativeId"], r["criterionId"]) for r in rescore if r["reason"].startswith("pivotal")]
    assert pivotal == [("x", "c1"), ("z", "c1")]
    assert "+1 level (4 to 5)" in rescore[0]["reason"]
    assert "-1 level (5 to 4)" in rescore[1]["reason"]
    assert "2 pivotal cell(s)" in out["summary"]


def test_budget_truncates_with_pivotal_cells_first() -> None:
    document = _document(PIVOT)
    document["cells"][2]["assertions"][0]["evidence"] = [{"id": "e9", "target": "doc:spec", "sourceType": "agent-summary"}]
    plan = _report(document, budget=3)["rescoringPlan"]
    assert [r["reason"].split(":")[0] for r in plan["rescore"]] == ["pivotal", "pivotal", "no primary or secondary ref with a span to check"]
    assert _report(document, budget=1)["rescoringPlan"]["rescore"][0]["criterionId"] == "c1"
    assert _report(document)["rescoringPlan"] is None


def test_weights_add_top_one_pivots() -> None:
    # x (1, 5) and y (5, 1) are incomparable, and one level moves neither past the other.
    # Weighted 0.5 / 0.5 they tie at 0.5 and row order puts x first; x.c2 -1 (0.375) and
    # y.c2 +1 (0.625) each hand the top-1 to y; x.c1 +1 and y.c1 -1 leave x first.
    document = _document({("x", "c1"): 1, ("x", "c2"): 5, ("y", "c1"): 5, ("y", "c2"): 1})
    unweighted = _report(document, budget=10)["rescoringPlan"]["rescore"]
    assert not [r for r in unweighted if r["reason"].startswith("pivotal")]
    halves = [{"criterionId": "c1", "weight": 0.5}, {"criterionId": "c2", "weight": 0.5}]
    rescore = _report(document, budget=10, weights=halves)["rescoringPlan"]["rescore"]
    hits = {(r["alternativeId"], r["criterionId"]): r["reason"] for r in rescore if r["reason"].startswith("pivotal")}
    assert set(hits) == {("x", "c2"), ("y", "c2")}
    assert all("the weighted top-1" in reason and "non-dominated" not in reason for reason in hits.values())


def test_the_diagnostic_says_it_is_not_a_redundancy_finding_in_the_payload() -> None:
    out = _report(_document(PIVOT))
    rows = out["traversalLeakageDiagnostic"]
    assert rows and all(LEAKAGE_NOTE in r["note"] for r in rows)
    assert "never a redundancy finding" in rows[0]["note"]
    assert "none of them a redundancy finding" in out["summary"]


def test_under_defined_criteria_go_to_redefine_never_to_rescore() -> None:
    document = _document(PIVOT)
    del document["criteria"][0]["defaultMeasurement"]["anchors"]  # c1: no anchors, no definition
    plan = _report(document, budget=10)["rescoringPlan"]
    assert plan["redefine"] == ["c1"]
    assert all(r["criterionId"] != "c1" for r in plan["rescore"])


def test_polarised_repeats_across_a_criterion_route_it_to_redefine() -> None:
    document = _document(PIVOT)
    document["cells"] = [_cell(a, c, *((1, 5) if c == "c2" else (v,))) for (a, c), v in PIVOT.items()]
    plan = _report(document, budget=10)["rescoringPlan"]
    assert plan["redefine"] == ["c2"]
    assert all(r["criterionId"] != "c2" for r in plan["rescore"])


def test_evidence_findings() -> None:
    document = _document({("x", "c1"): 3, ("y", "c1"): 3, ("z", "c1"): 3, ("w", "c1"): 3})
    cells = {c["alternativeId"]: c["assertions"][0] for c in document["cells"]}
    del cells["w"]["evidence"]
    cells["x"]["evidence"] = [{"id": "e", "target": "t", "sourceType": "agent-inference", "derivedFrom": ["e1"]}]
    cells["y"]["evidence"] = [{"id": "e", "target": "t", "sourceType": "secondary"}]
    cells["z"]["evidence"] = [{**PRIMARY[0], "check": {"status": "stale"}}]
    out = _report(document)
    assert [r["alternativeId"] for r in out["uncited"]] == ["w"]
    assert [r["alternativeId"] for r in out["agentInferenceOnly"]] == ["x"]
    assert [r["alternativeId"] for r in out["thinEvidence"]] == ["y"]
    assert [(r["alternativeId"], r["reason"]) for r in out["staleCitations"]] == [("z", "a citation checked stale")]


def test_low_confidence_reads_the_confidence_measure() -> None:
    document = _document({("x", "c1"): 3, ("y", "c1"): 3})
    document["criteria"][0]["measurements"] = {"confidence": {"level": "ordinal", "levels": ["low", "medium", "high"]}}
    document["cells"] += [_cell("x", "c1", "low", measure="confidence"), _cell("y", "c1", "high", measure="confidence")]
    out = _report(document)
    assert [(r["alternativeId"], r["criterionId"]) for r in out["lowConfidence"]] == [("x", "c1")]
    assert "no confidence measure recorded" not in out["summary"]
    assert "no confidence measure recorded" in _report(_document(PIVOT))["summary"]


def test_veto_flags_mirror_comparanda_screen() -> None:
    document = _document({("x", "c1"): 1, ("y", "c1"): 4})
    document["alternatives"].append({"id": "z", "label": "z"})
    document["criteria"][0]["acceptability"] = {"threshold": 2, "rationale": "too slow"}
    flags = _report(document)["vetoFlags"]
    assert [(f["alternativeId"], f["reason"].split(" ")[0]) for f in flags] == [("x", "1"), ("z", "blank:")]
    assert "too slow" in flags[0]["reason"] and "untested floor is not a passed one" in flags[1]["reason"]


def test_a_structural_blank_leaves_the_comparison() -> None:
    document = _document({("x", "c1"): 4, ("y", "c1"): 3, ("x", "c2"): 4})
    document["cells"].append(_cell("y", "c2", missing={"code": "not-applicable"}, evidence=None))
    # On c1 alone x beats y; a contingent blank on c2 would have spanned 1..5 and saved y.
    assert _report(document)["dominatedAlternatives"] == ["y"]
    document["cells"][-1] = _cell("y", "c2", missing={"code": "not-evidenced", "note": "n"}, evidence=None)
    assert _report(document)["dominatedAlternatives"] == []


def test_empty_matrix_says_nothing_has_been_scored() -> None:
    out = _report({"id": "a", "alternatives": [{"id": "x", "label": "x"}], "criteria": [_criterion("c1")],
                   "cells": [], "missingCodes": []}, budget=2)
    assert out["summary"].startswith("Nothing has been scored")
    assert out["rescoringPlan"] == {"rescore": [], "redefine": [], "budget": 2}


@pytest.mark.parametrize("kw", [{"top_k": -1}, {"budget": True}, {"weights": [{"criterionId": "nope", "weight": 1}]},
                                {"weights": [{"criterionId": "c1", "weight": -1}]},
                                {"weights": [{"criterionId": "c1", "weight": 1}, {"criterionId": "c1", "weight": 1}]}])
def test_refusals(kw) -> None:
    with pytest.raises(ValueError, match="refused"):
        _report(_document(PIVOT), **kw)


def test_through_the_real_store_end_to_end() -> None:
    store = build_runtime(blobs={}).store
    analysis_open(store, analysis_id="a", question="which?", allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(store, analysis_id="a", ambiguities=[])
    alternatives_set(store, analysis_id="a", alternatives=[{"id": a, "label": a} for a in "xyz"])
    criteria_set(store, analysis_id="a", criteria=[
        {"id": c, "label": c, "anchors": {"1": "none", "3": "some", "5": "all"}} for c in ("c1", "c2")])
    bot = agent("bot", "Bot", name="rubricator", model="model-a", prompt_version="v4", run_id="r1")
    measures_write(store, analysis_id="a", contributor_id="bot", author=bot, at="2026-10-12T12:00:00Z", cells=[
        {"alternativeId": a, "criterionId": c, "value": v, "justification": "j", "evidence": PRIMARY}
        for (a, c), v in PIVOT.items()])
    out = report_weaknesses(store, analysis_id="a", budget=5)
    assert out["dominatedAlternatives"] == ["y"]
    assert [(r["alternativeId"], r["criterionId"]) for r in out["rescoringPlan"]["rescore"]] == [("x", "c1"), ("z", "c1")]
    assert report_weaknesses(store, analysis_id="a", budget=5) == out
