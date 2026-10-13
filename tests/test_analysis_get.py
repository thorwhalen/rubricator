"""Tools 1-2 (#52): ``analysis_open`` and ``analysis_get`` -- the entry and the inspection points.

What these hold: a fresh analysis is a valid document; reopening reads and
never writes; every view is a pure projection; the ``outstanding`` view keeps
"nobody has looked" apart from "deliberately left", which is what the resume
flow branches on; and ``full`` links to the document rather than inlining it.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ids import sequential_ids
from rubricator.store import AnalysisNotFound, RETENTION_DAYS
from rubricator.surface import bind, frozen
from rubricator.tools.views import VIEWS, analysis_uri

#: A span every scored cell here cites: since #171 a value with no evidence is refused.
CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]

MOMENT = "2026-08-22T12:00:00Z"
AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]


@pytest.fixture()
def runtime():
    return build_runtime(blobs={}, now=fixed_clock(MOMENT), new_id=sequential_ids("a"))


@pytest.fixture()
def verbs(runtime):
    return bind(runtime)


def _matrix(verbs) -> None:
    """Two live rows, one retired row, two criteria: six live cells, settled unevenly."""
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    verbs["frame_set"](analysis_id="a1", ambiguities=[], decision="buy one")
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two"},
        {"id": "k3", "label": "Kettle three", "tombstoned": True},
    ])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS,
         "definition": {"objective": "fast tea", "missingRules": [{"when": "no spec", "code": "not-evidenced"}]}},
        {"id": "cost", "label": "Cost", "preference": "decreasing", "anchors": ANCHORS},
    ])
    _confirm(verbs)


def _confirm(verbs, analysis_id="a1") -> None:
    """ADR-0005 step 4, out of band: ask, then record the user's answer."""
    verbs["frame_confirm"](analysis_id=analysis_id)
    verbs["frame_confirm"](analysis_id=analysis_id, decision="confirm", confirmed_by="ana",
                           confirmation_text="Yes, go ahead.")


def _write(verbs, contributor="ana", **cell):
    return verbs["measures_write"](
        analysis_id="a1", contributor_id=contributor, author={**AUTHOR, "id": contributor},
        cells=[{**({"evidence": CITED} if "value" in cell else {}), **cell}])


# --- analysis_open ------------------------------------------------------------


def test_a_freshly_opened_analysis_validates(runtime, verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    result = runtime.schema.validate(runtime.store.read("a1"))
    assert result.ok, result.report()


def test_reopening_returns_the_same_state_byte_identically_and_writes_nothing(runtime, verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec sheet")
    before = dict(runtime.store.blobs)
    first = verbs["analysis_open"](analysis_id="a1")
    second = verbs["analysis_open"](analysis_id="a1", question="a different question")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["created"] is False and first["question"] == "which kettle?"
    assert dict(runtime.store.blobs) == before


def test_reopening_reports_the_stage_and_counts_only_live_rows(verbs) -> None:
    _matrix(verbs)
    reopened = verbs["analysis_open"](analysis_id="a1")
    assert (reopened["alternatives"], reopened["criteria"], reopened["stage"]) == (2, 2, 5)
    assert "next:" in reopened["summary"]


def test_an_unknown_id_with_no_question_names_the_retention_window(verbs) -> None:
    with pytest.raises(ValueError, match=f"{RETENTION_DAYS} days.*needs a question"):
        verbs["analysis_open"](analysis_id="gone")


def test_an_open_with_neither_id_nor_question_is_refused_before_an_id_is_minted(verbs) -> None:
    with pytest.raises(ValueError, match="needs a question"):
        verbs["analysis_open"]()
    with pytest.raises(ValueError, match="needs a question"):
        verbs["analysis_open"](question="   ")
    # The refusal consumed no handle: the next minted id is still the first.
    assert verbs["analysis_open"](question="which?")["analysisId"] == "a-1"


# --- analysis_get -------------------------------------------------------------


def test_the_stage_follows_the_work(verbs) -> None:
    stage = lambda: verbs["analysis_get"](analysis_id="a1")["stage"]  # noqa: E731
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    assert stage() == 1
    verbs["frame_set"](analysis_id="a1", ambiguities=["which budget?"])
    assert stage() == 2
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k1", "label": "K1"}])
    assert stage() == 3
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "speed", "label": "S", "anchors": ANCHORS}])
    assert stage() == 4
    _confirm(verbs)
    assert stage() == 5
    _write(verbs, alternativeId="k1", criterionId="speed", value=3, justification="ok")
    assert stage() == 6


def test_the_outstanding_view_keeps_not_assessed_apart_from_deferred(verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec sheet")
    _write(verbs, alternativeId="k1", criterionId="cost", missing={"code": "not-evidenced", "note": "no price"})
    _write(verbs, alternativeId="k2", criterionId="speed", missing={"code": "deferred", "note": "later"})
    _write(verbs, alternativeId="k2", criterionId="cost", missing={"code": "not-assessed", "note": "not yet"})
    got = verbs["analysis_get"](analysis_id="a1", view="outstanding")
    rows = {(r["alternativeId"], r["criterionId"]): (r["code"], r["recorded"]) for r in got["outstanding"]}
    # Valued and terminal blanks are settled; the retired row is not in the matrix.
    assert rows == {("k2", "speed"): ("deferred", True), ("k2", "cost"): ("not-assessed", True)}
    assert got["counts"]["byCode"] == [
        {"code": "deferred", "count": 1}, {"code": "not-assessed", "count": 1}]
    assert (got["counts"]["cells"], got["counts"]["outstanding"]) == (4, 2)


def test_a_cell_nobody_wrote_is_not_assessed_and_says_it_was_never_recorded(verbs) -> None:
    _matrix(verbs)
    got = verbs["analysis_get"](analysis_id="a1", view="outstanding")
    assert len(got["outstanding"]) == 4
    assert {(r["code"], r["recorded"]) for r in got["outstanding"]} == {("not-assessed", False)}


def test_one_contributors_score_settles_a_cell_another_deferred(verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec",
           independence="independent")
    _write(verbs, "ben", alternativeId="k1", criterionId="speed",
           missing={"code": "deferred", "note": "later"}, independence="independent")
    cells = verbs["analysis_get"](analysis_id="a1", view="outstanding")["outstanding"]
    assert ("k1", "speed") not in {(r["alternativeId"], r["criterionId"]) for r in cells}


def test_the_frame_view_carries_the_subject_and_every_row(verbs) -> None:
    _matrix(verbs)
    got = verbs["analysis_get"](analysis_id="a1", view="frame")
    assert got["subject"] == {"question": "which kettle?", "decision": "buy one", "ambiguities": []}
    assert [a["id"] for a in got["alternatives"]] == ["k1", "k2", "k3"]
    assert got["alternatives"][2]["tombstoned"] is True
    assert "criteria" not in got and "outstanding" not in got


def test_the_criteria_view_round_trips_through_criteria_set(verbs) -> None:
    _matrix(verbs)
    got = verbs["analysis_get"](analysis_id="a1", view="criteria")
    assert got["criteriaVersion"] == "1"
    speed = got["criteria"][0]
    assert speed["anchors"] == ANCHORS and speed["definition"]["objective"] == "fast tea"
    again = verbs["criteria_set"](analysis_id="a1", criteria=got["criteria"])
    assert again["revised"] == [] and again["criteriaVersion"] == "1"


def test_the_full_view_links_and_never_inlines_the_body(verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4,
           justification="the spec sheet says ninety seconds")
    got = verbs["analysis_get"](analysis_id="a1", view="full")
    assert got["resourceLink"] == analysis_uri("a1") == "rubricator://analysis/a1"
    text = json.dumps(got)
    for body_only in ("ninety seconds", "fast tea", "assertions", "Kettle one"):
        assert body_only not in text


def test_every_view_is_a_pure_projection(runtime, verbs) -> None:
    _matrix(verbs)
    before = dict(runtime.store.blobs)
    for view in VIEWS:
        first = verbs["analysis_get"](analysis_id="a1", view=view)
        assert json.dumps(first) == json.dumps(verbs["analysis_get"](analysis_id="a1", view=view))
    assert dict(runtime.store.blobs) == before


def test_the_views_are_the_rows_enum() -> None:
    assert list(VIEWS) == frozen()["analysis_get"].input_schema["properties"]["view"]["enum"]


def test_an_unknown_id_is_refused_naming_the_window(verbs) -> None:
    with pytest.raises(AnalysisNotFound, match=f"{RETENTION_DAYS} days"):
        verbs["analysis_get"](analysis_id="gone")


def test_an_unknown_view_is_refused_at_the_boundary(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="q")
    with pytest.raises(ValueError, match=r"at \$\.view"):
        verbs["analysis_get"](analysis_id="a1", view="pending")


# --- the connector serves what full links to ----------------------------------


def test_the_link_resolves_over_mcp_to_the_merged_document() -> None:
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    server = make_server(runtime)
    asyncio.run(server.call_tool("analysis_open", {"analysis_id": "a1", "question": "which kettle?"}))
    got = asyncio.run(server.call_tool("analysis_get", {"analysis_id": "a1", "view": "full"}))
    link = got.structured_content["resourceLink"]
    body = asyncio.run(server.read_resource(link)).contents[0].content
    assert json.loads(body) == runtime.store.read("a1")


# --- the adversarial review's findings, kept failing-able ----------------------


def test_a_score_answering_an_older_definition_keeps_the_stage_at_populate(verbs) -> None:
    _matrix(verbs)
    for alt in ("k1", "k2"):
        for crit in ("speed", "cost"):
            _write(verbs, alternativeId=alt, criterionId=crit, value=3, justification="ok")
    assert verbs["analysis_get"](analysis_id="a1")["stage"] == 6
    got = verbs["analysis_get"](analysis_id="a1", view="criteria")["criteria"]
    got[0]["label"] = "Boil speed, measured cold"
    got[0]["definition"]["objective"] = "fast tea from cold"
    verbs["criteria_set"](analysis_id="a1", criteria=got)
    summary = verbs["analysis_get"](analysis_id="a1")
    assert summary["stage"] == 5 and summary["counts"]["superseded"] == 2
    assert "older criteria definition" in summary["summary"]


@pytest.mark.parametrize("stray", [
    b"not json",
    b"[]",
    json.dumps({"authors": [{"id": "someone-else", "displayName": "S", "kind": "human"}],
                "cells": []}).encode(),
])
def test_a_bad_contribution_does_not_lock_the_resume_entry_point(runtime, verbs, stray) -> None:
    """Left out and named (#151), not a refusal of the whole analysis."""
    _matrix(verbs)
    runtime.store.blobs["analyses/a1/contributions/zed.json"] = stray
    reopened = verbs["analysis_open"](analysis_id="a1")
    assert reopened["created"] is False and "could not be merged" in reopened["summary"]
    got = verbs["analysis_get"](analysis_id="a1")
    assert [s["file"] for s in got["skipped"]] == ["analyses/a1/contributions/zed.json"]


def test_open_blanks_are_ordered_as_instants_not_strings(verbs) -> None:
    _matrix(verbs)
    write = lambda who, code, at: verbs["measures_write"](  # noqa: E731
        analysis_id="a1", contributor_id=who, author={**AUTHOR, "id": who}, at=at,
        cells=[{"alternativeId": "k1", "criterionId": "speed",
                "missing": {"code": code, "note": "n"}, "independence": "independent"}])
    write("ana", "deferred", "2026-08-22T10:00:00+02:00")  # 08:00Z: earlier
    write("ben", "not-assessed", "2026-08-22T09:00:00Z")
    rows = verbs["analysis_get"](analysis_id="a1", view="outstanding")["outstanding"]
    assert next(r for r in rows if (r["alternativeId"], r["criterionId"]) == ("k1", "speed"))["code"] == "not-assessed"
    write("cy", "deferred", "2026-08-22T09:00:00.5Z")  # half a second later
    rows = verbs["analysis_get"](analysis_id="a1", view="outstanding")["outstanding"]
    assert next(r for r in rows if (r["alternativeId"], r["criterionId"]) == ("k1", "speed"))["code"] == "deferred"


@pytest.mark.parametrize("edit, view, path", [
    (lambda f: f["criteria"][0]["missingCodes"].append({"id": "x", "broader": "deferred"}),
     "criteria", "$.criteria[0].missingCodes[0]"),
    (lambda f: f["criteria"][0]["defaultMeasurement"].update(preference="ascending"),
     "criteria", "$.criteria[0].preference"),
    (lambda f: f["subject"].update(ambiguities=None), "frame", "$.subject.ambiguities"),
    (lambda f: f["alternatives"][0].update(url="u"), "frame", "$.alternatives[0].url"),
])
def test_stored_data_the_contract_cannot_hold_is_left_out_and_named(
    runtime, verbs, edit, view, path
) -> None:
    """A data problem in a hand-edited store is not a server bug (ContractViolation)."""
    _matrix(verbs)
    key = runtime.store.frame_key("a1")
    frame = json.loads(runtime.store.blobs[key])
    edit(frame)
    runtime.store.blobs[key] = json.dumps(frame).encode()
    for each in VIEWS:  # bind validates every envelope, so no view may raise
        verbs["analysis_get"](analysis_id="a1", view=each)
    got = verbs["analysis_get"](analysis_id="a1", view=view)
    assert path in got["omitted"] and "do NOT hand this view back" in got["summary"]
    assert verbs["analysis_get"](analysis_id="a1", view="summary")["omitted"] == []


def test_a_blank_id_is_treated_as_no_id(verbs) -> None:
    with pytest.raises(ValueError, match="needs a question") as caught:
        verbs["analysis_open"](analysis_id="  ")
    assert "expired" not in str(caught.value)


def test_the_criteria_round_trip_holds_for_unsorted_anchors_and_a_target(verbs) -> None:
    _matrix(verbs)
    crit = {"id": "temp", "label": "Temperature", "preference": "target", "target": 3,
            "anchors": [ANCHORS[2], ANCHORS[0], ANCHORS[1]],
            "missingCodes": [{"id": "lab-only", "broader": "not-evidenced", "means": "only in a lab"}],
            "definition": {"objective": "o", "question": "q", "evidenceRule": "e",
                           "missingRules": [{"when": "w", "code": "lab-only"}], "exclusions": ["x"]}}
    verbs["criteria_set"](analysis_id="a1", criteria=[
        *verbs["analysis_get"](analysis_id="a1", view="criteria")["criteria"], crit])
    got = verbs["analysis_get"](analysis_id="a1", view="criteria")
    # The store keeps anchors in level order and names the scale it defaulted.
    assert got["criteria"][2] == {**crit, "scale": "ordinal-1-5-anchored", "anchors": ANCHORS}
    again = verbs["criteria_set"](analysis_id="a1", criteria=got["criteria"])
    assert again["revised"] == [] and again["criteriaVersion"] == got["criteriaVersion"]


def test_the_resource_is_served_as_json() -> None:
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    asyncio.run(server.call_tool("analysis_open", {"analysis_id": "a1", "question": "q"}))
    content = asyncio.run(server.read_resource(analysis_uri("a1"))).contents[0]
    assert content.mime_type == "application/json"


@pytest.mark.parametrize("edit", [
    lambda f: f["criteria"][0]["defaultMeasurement"].update(anchors=["1", "3", "5"]),
    lambda f: f["criteria"][0]["defaultMeasurement"].update(range=[1, 5]),
])
def test_a_malformed_measurement_is_cut_not_crashed_on(runtime, verbs, edit) -> None:
    _matrix(verbs)
    key = runtime.store.frame_key("a1")
    frame = json.loads(runtime.store.blobs[key])
    edit(frame)
    runtime.store.blobs[key] = json.dumps(frame).encode()
    assert verbs["analysis_get"](analysis_id="a1", view="criteria")["criteria"][0]["id"] == "speed"


def test_a_non_string_code_is_left_out_and_named_rather_than_crashing(runtime, verbs) -> None:
    """A hand-edited code of 7 breaks comparanda v1, so since #159 the file is left
    out whole and named, and the cell it held reads as not yet assessed."""
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", missing={"code": "deferred", "note": "n"})
    key = runtime.store.contribution_key("a1", "ana")
    contribution = json.loads(runtime.store.blobs[key])
    contribution["cells"][0]["assertions"][0]["missing"]["code"] = 7
    runtime.store.blobs[key] = json.dumps(contribution).encode()
    result = verbs["analysis_get"](analysis_id="a1", view="outstanding")
    assert [s["file"] for s in result["skipped"]] == [key]
    assert {"alternativeId": "k1", "criterionId": "speed", "measure": "score",
            "code": "not-assessed", "recorded": False} in result["outstanding"]


# --- the settled cells by kind (#186) -----------------------------------------


def test_the_counts_by_kind_add_up_to_the_cells(verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec sheet")
    _write(verbs, alternativeId="k1", criterionId="cost", missing={"code": "not-evidenced", "note": "no price"})
    _write(verbs, alternativeId="k2", criterionId="speed", missing={"code": "not-applicable", "note": "no motor"})
    _write(verbs, alternativeId="k2", criterionId="cost", missing={"code": "deferred", "note": "later"})
    counts = verbs["analysis_get"](analysis_id="a1")["counts"]
    assert counts["byKind"] == {"scored": 1, "settledBlank": 1, "notApplicable": 1}
    assert sum(counts["byKind"].values()) + counts["outstanding"] == counts["cells"] == 4


def test_a_cell_with_a_value_and_a_blank_is_scored_once(verbs) -> None:
    _matrix(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec sheet",
           independence="independent")
    _write(verbs, "ben", alternativeId="k1", criterionId="speed",
           missing={"code": "not-evidenced", "note": "no spec"}, independence="independent")
    counts = verbs["analysis_get"](analysis_id="a1")["counts"]
    assert counts["byKind"] == {"scored": 1, "settledBlank": 0, "notApplicable": 0}
    assert counts["outstanding"] == 3


def test_claims_on_a_removed_row_leave_the_completeness_counts(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "speed", "label": "S", "anchors": ANCHORS}])
    _confirm(verbs)
    _write(verbs, alternativeId="k1", criterionId="speed", value=4, justification="spec sheet")
    _write(verbs, alternativeId="k2", criterionId="speed", value=2, justification="spec sheet")
    assert verbs["report_completeness"](analysis_id="a1")["present"] == 2
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two", "tombstoned": True}])
    done = verbs["report_completeness"](analysis_id="a1")
    assert (done["total"], done["present"]) == (1, 1)
    assert verbs["analysis_get"](analysis_id="a1")["counts"]["byKind"]["scored"] == 1
