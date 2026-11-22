"""``measures_rescore_context``: the value-free read a re-score needs (#294). Fixtures are invented."""

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


def _sweep(n):
    return {"round": n, "session": "fresh", "prior": "withheld"}


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
    for alt in ("tamsin", "brindle"):
        v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                            cells=[_cell(alt)], procedure=_sweep(1))
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("tamsin", criterionId="quiet")], procedure=_sweep(3))
    return v


def _read(v, **kw):
    return v["measures_rescore_context"](analysis_id="kettles", criterion_id="parts", **kw)


def _claims(got):
    return {c["alternativeId"]: c["liveClaims"] for c in got["cells"]}


def test_each_cell_names_its_live_claims_and_each_writer_its_latest_round(v):
    got = _read(v, contributor_id="scorer")
    assert _claims(got) == {
        "tamsin": [{"assertionId": "tamsin-parts-score", "contributorId": "scorer",
                    "authorId": "scorer", "yours": True}],
        "brindle": [{"assertionId": "brindle-parts-score", "contributorId": "scorer",
                     "authorId": "scorer", "yours": True}],
        "copperleaf": [],  # never written: nothing to supersede
    }
    # the latest round is the writer's over the whole analysis, not this criterion's
    assert got["writers"] == [
        {"contributorId": "scorer", "authorId": "scorer", "kind": "agent", "model": "m-1",
         "latestRound": 3}]
    assert "its re-score is round 4" in got["summary"]


def test_it_never_returns_a_value_justification_evidence_code_or_round(v):
    v["measures_mark_missing"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                               code="not-evidenced", note="nothing on copperleaf's parts",
                               criterion_ids=["parts"], alternative_ids=["copperleaf"])
    got = _read(v)

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
        "assertionId", "contributorId", "authorId", "yours", "writers", "kind", "model", "latestRound",
        "skipped", "summary"}
    text = json.dumps(got)
    for leak in (JUSTIFICATION, "not-evidenced", "nothing on copperleaf", "sold separately"):
        assert leak not in text, leak


def test_a_superseded_claim_is_gone_and_its_successor_is_live(v):
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("brindle", 3, supersedes="brindle-parts-score")],
                        procedure=_sweep(4))
    got = _read(v, alternative_ids=["brindle"], contributor_id="scorer")
    assert [c["assertionId"] for c in got["cells"][0]["liveClaims"]] == ["brindle-parts-score-2"]
    assert got["writers"][0]["latestRound"] == 4


def test_naming_yourself_marks_your_claims_and_never_hides_anothers(v):
    """The blocker of the first review: a filter made Ana's claim read as a never-written cell."""
    v["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA,
                        cells=[_cell("copperleaf", 4)])
    got = _read(v, alternative_ids=["copperleaf"], contributor_id="scorer")
    assert got["cells"][0]["liveClaims"] == [
        {"assertionId": "copperleaf-parts-score", "contributorId": "ana", "authorId": "ana",
         "yours": False}]
    assert [(w["contributorId"], w["kind"], w["latestRound"]) for w in got["writers"]] == [
        ("ana", "human", None), ("scorer", "agent", 3)]  # the named writer is listed even with no claim in scope
    assert "only another writer's claims in: copperleaf/score" in got["summary"]


def test_a_persona_is_its_own_writer_with_its_own_rounds(v):
    persona = {"id": "scorer:buyer", "displayName": "Buyer persona", "kind": "agent",
               "principalId": "scorer", "agent": {"name": "scorer", "model": "m-1"}}
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=persona,
                        cells=[_cell("copperleaf", 2)], procedure=_sweep(7))
    got = _read(v, contributor_id="scorer", author_id="scorer")
    copper = _claims(got)["copperleaf"]
    assert copper == [{"assertionId": "copperleaf-parts-score", "contributorId": "scorer",
                       "authorId": "scorer:buyer", "yours": False}]
    default = _read(v, contributor_id="scorer")  # the principal: a persona is never yours unnamed
    assert _claims(default)["copperleaf"][0]["yours"] is False
    assert "scorer has other authors with claims here (scorer:buyer)" in default["summary"]
    rounds = {(w["contributorId"], w["authorId"]): w["latestRound"] for w in got["writers"]}
    assert rounds == {("scorer", "scorer"): 3, ("scorer", "scorer:buyer"): 7}
    as_persona = _read(v, contributor_id="scorer", author_id="scorer:buyer")
    assert _claims(as_persona)["copperleaf"][0]["yours"] is True


def test_several_live_claims_of_yours_are_flagged(v):
    v["measures_write"](analysis_id="kettles", contributor_id="scorer", author=BOT,
                        cells=[_cell("tamsin", 4)], procedure=_sweep(2))
    got = _read(v, alternative_ids=["tamsin"], contributor_id="scorer")
    assert [c["assertionId"] for c in got["cells"][0]["liveClaims"]] == [
        "tamsin-parts-score", "tamsin-parts-score-2"]
    assert "several live claims of yours in: tamsin/score" in got["summary"]


@pytest.mark.parametrize("kwargs, named", [
    ({"criterion_id": "colour"}, "colour"),
    ({"criterion_id": "parts", "alternative_ids": ["kestrel"]}, "kestrel"),
])
def test_an_unknown_criterion_or_alternative_is_refused(v, kwargs, named):
    with pytest.raises(KeyError, match=named):
        v["measures_rescore_context"](analysis_id="kettles", **kwargs)


def test_a_procedure_under_a_stored_human_signer_is_refused(v):
    """Claiming kind agent in the call does not make a human's record an agent's (#294 re-review)."""
    v["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA,
                        cells=[_cell("copperleaf", 4)])
    posing = {"id": "ana", "displayName": "Ana", "kind": "agent", "agent": {"name": "x", "model": "m"}}
    with pytest.raises(ValueError, match="recorded as human"):
        v["measures_write"](analysis_id="kettles", contributor_id="ana", author=posing,
                            cells=[_cell("copperleaf", 3, supersedes="copperleaf-parts-score")],
                            procedure=_sweep(1))


def test_an_author_without_its_contributor_is_refused(v):
    with pytest.raises(ValueError, match="contributor_id"):
        _read(v, author_id="scorer")
