"""``measures_claim_ids``: the value-free read a re-score needs (#294). Fixtures are invented."""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ids import sequential_ids
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "no spare parts"}, {"level": "3", "text": "some parts"},
           {"level": "5", "text": "every part, for years"}]
TEXT = "The Tamsin kettle's lid, filter and base are sold separately for ten years."
BOT = {"id": "scorer", "displayName": "Scorer", "kind": "agent",
       "agent": {"name": "scorer", "model": "m-1"}}
ANA = {"id": "ana", "displayName": "Ana Ruiz", "kind": "human"}
JUSTIFICATION = "the service page lists every part as sold separately"


def _cell(alt: str, value: int = 5, **extra) -> dict:
    return {
        "alternativeId": alt, "criterionId": "parts", "value": value,
        "justification": JUSTIFICATION,
        "evidence": [{"id": "e1", "target": "rendition:tamsin", "sourceType": "primary",
                      "selectors": [{"type": "TextQuoteSelector", "exact": "sold separately"}]}],
        **extra,
    }


@pytest.fixture
def v():
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT), retention_clock=fixed_clock(MOMENT),
                            new_id=sequential_ids("a"))
    v = bind(runtime)
    v["analysis_open"](analysis_id="kettles", question="Which kettle for a small office?")
    v["corpus_add"](analysis_id="kettles", sources=[
        {"id": "tamsin", "title": "Tamsin service", "text": TEXT, "agentProduced": False}])
    v["alternatives_set"](analysis_id="kettles", alternatives=[
        {"id": "tamsin", "label": "Tamsin"}, {"id": "brindle", "label": "Brindle"},
        {"id": "copperleaf", "label": "Copperleaf"}])
    v["criteria_set"](analysis_id="kettles", criteria=[
        {"id": "parts", "label": "Spare parts", "anchors": ANCHORS},
        {"id": "quiet", "label": "Quietness", "anchors": ANCHORS}])
    v["frame_confirm"](analysis_id="kettles")
    v["frame_confirm"](analysis_id="kettles", decision="confirm", scope="all",
                       confirmed_by="Ana Ruiz", confirmation_text="Yes.")
    sweep = {"round": 1, "session": "fresh", "prior": "withheld"}
    for alt in ("tamsin", "brindle"):
        v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                            cells=[_cell(alt)], procedure=sweep)
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("tamsin", criterionId="quiet")],
                        procedure={**sweep, "round": 3})
    return v


def test_each_cell_names_its_live_claims_and_each_contributor_its_latest_round(v):
    got = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts")
    cells = {c["alternativeId"]: c["liveClaims"] for c in got["cells"]}
    assert cells == {
        "tamsin": [{"assertionId": "tamsin-parts-score", "contributorId": "scorer", "round": 1}],
        "brindle": [{"assertionId": "brindle-parts-score", "contributorId": "scorer", "round": 1}],
        "copperleaf": [],  # never written: nothing to supersede
    }
    # The latest round is the contributor's over the whole analysis, not this criterion's.
    assert got["contributors"] == [{"contributorId": "scorer", "latestRound": 3}]
    assert "a re-score is round 4" in got["summary"]


def test_it_never_returns_a_value_justification_evidence_or_code(v):
    v["measures_mark_missing"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                               code="not-evidenced", note="nothing on copperleaf's parts",
                               criterion_ids=["parts"], alternative_ids=["copperleaf"])
    got = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts")

    def keys(node):
        if isinstance(node, dict):
            for k, val in node.items():
                yield k
                yield from keys(val)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    assert set(keys(got)) == {
        "analysisId", "criterionId", "cells", "alternativeId", "measure", "liveClaims",
        "assertionId", "contributorId", "round", "contributors", "latestRound", "skipped",
        "summary"}
    text = json.dumps(got)
    for leak in (JUSTIFICATION, "not-evidenced", "nothing on copperleaf", "sold separately"):
        assert leak not in text, leak


def test_a_superseded_claim_is_gone_and_its_successor_is_live(v):
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("brindle", 3, supersedes="brindle-parts-score")],
                        procedure={"round": 4, "session": "fresh", "prior": "withheld"})
    got = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts",
                                  alternative_ids=["brindle"])
    assert got["cells"] == [{"alternativeId": "brindle", "measure": "score", "liveClaims": [
        {"assertionId": "brindle-parts-score-2", "contributorId": "scorer", "round": 4}]}]
    assert got["contributors"] == [{"contributorId": "scorer", "latestRound": 4}]


def test_contributors_are_told_apart_and_one_can_be_asked_for(v):
    v["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA,
                        cells=[_cell("tamsin", 4, independence="independent")])
    both = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts",
                                   alternative_ids=["tamsin"])
    assert [c["contributorId"] for c in both["cells"][0]["liveClaims"]] == ["ana", "scorer"]
    assert both["contributors"] == [{"contributorId": "ana", "latestRound": None},
                                    {"contributorId": "scorer", "latestRound": 3}]
    own = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts",
                                  alternative_ids=["tamsin"], contributor_id="ana")
    assert own["cells"][0]["liveClaims"] == [
        {"assertionId": "tamsin-parts-score", "contributorId": "ana", "round": None}]
    assert own["contributors"] == [{"contributorId": "ana", "latestRound": None}]
    assert "unrecorded" in own["summary"]


def test_a_contributor_with_no_file_is_named_with_no_round(v):
    got = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts",
                                  contributor_id="nobody")
    assert got["contributors"] == [{"contributorId": "nobody", "latestRound": None}]
    assert all(c["liveClaims"] == [] for c in got["cells"])


def test_several_live_claims_of_one_contributor_are_flagged(v):
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("tamsin", 4)],
                        procedure={"round": 2, "session": "fresh", "prior": "withheld"})
    got = v["measures_claim_ids"](analysis_id="kettles", criterion_id="parts",
                                  alternative_ids=["tamsin"])
    assert [c["assertionId"] for c in got["cells"][0]["liveClaims"]] == [
        "tamsin-parts-score", "tamsin-parts-score-2"]
    assert "several live claims of one contributor in: tamsin" in got["summary"]


@pytest.mark.parametrize("kwargs, named", [
    ({"criterion_id": "colour"}, "colour"),
    ({"criterion_id": "parts", "alternative_ids": ["kestrel"]}, "kestrel"),
])
def test_an_unknown_criterion_or_alternative_is_refused(v, kwargs, named):
    with pytest.raises(KeyError, match=named):
        v["measures_claim_ids"](analysis_id="kettles", **kwargs)
