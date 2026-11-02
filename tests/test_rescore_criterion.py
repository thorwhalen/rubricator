"""The ``rescore-criterion`` prompt's evaluation: its fixtures are the tools' real output, and its grader replays the writes (#129).

The grader judges a subject by replaying its ``measures_write`` calls against a fresh copy of the
scenario's analysis, so these tests hold the grader to the verbs: a faithful answer grades full
marks, and each failure the prompt is written against is caught by the metric named for it.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/rescore-criterion/scenarios.json"
SEARCH = "corpus_search, per alternative, over the whole corpus"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _script("rescore_criterion_scenarios")
grader = _script("rescore_criterion_adherence")


def _span(hit, stance="supports"):
    return {"id": hit["spanId"], "target": hit["documentId"], "sourceType": "primary", "stance": stance,
            "selectors": [{"type": "TextQuoteSelector", "exact": hit["text"]}]}


def _own_hits(scenario, alt):
    label = alt.capitalize()
    return [h for h in scenario["toolResults"][SEARCH][alt]["hits"] if h["text"].startswith(label)]


def _cell(scenario, alt, outcome, supersedes):
    cell = {"alternativeId": alt, "criterionId": scenario["criterion"]}
    if supersedes:
        cell["supersedes"] = supersedes
    hits = _own_hits(scenario, alt)
    if isinstance(outcome, int):
        return {**cell, "justification": "the maker states it", "evidence": [_span(hits[-1])], "value": outcome}
    if outcome == "indeterminate":
        return {**cell, "evidence": [_span(hits[0]), _span(hits[1], "contradicts")],
                "missing": {"code": outcome, "note": "the maker's two documents state different levels"}}
    return {**cell, "missing": {"code": outcome, "note": "retrieval over the corpus returned nothing on it"}}


def _faithful(scenario):
    want = scenario["expected"]
    if want["action"] == "ask":
        return {"scenarioId": scenario["id"], "calls": [],
                "reply": "Your earlier scores are in this conversation, so a re-score here would be shown; "
                         "a withheld one needs a fresh conversation. Go ahead here?"}
    procedure = {"round": 2, "session": want["session"] or "fresh", "prior": want["prior"]}
    calls = [{"tool": "analysis_get", "arguments": {"analysis_id": "kettles", "view": "criteria"}},
             {"tool": "analysis_get", "arguments": {"analysis_id": "kettles", "view": "outstanding"}}]
    calls += [{"tool": "corpus_search", "arguments": {"analysis_id": "kettles", "query": alt}}
              for alt in want["cells"]]
    calls += [{"tool": "measures_write", "arguments": {
        "contributor_id": "scorer", "author": scenario["contributor"]["author"],
        "expected_criteria_version": "1", "procedure": procedure,
        "cells": [_cell(scenario, alt, outcome, supersedes)]}}
        for alt, (outcome, supersedes) in want["cells"].items()]
    reply = (f"Re-scored: {scenario['criterion']} — {len(want['cells'])} of 3 alternatives\n"
             f"Prior: {want['prior']} — as the pass was\nNext: review")
    return {"scenarioId": scenario["id"], "calls": calls, "reply": reply}


def _scenarios():
    return json.loads(SCENARIOS.read_text())


def _run(fault=lambda out, scenario: out):
    scenarios = _scenarios()
    return grader.grade(scenarios, [fault(_faithful(s), s) for s in scenarios])


def _writes(out):
    return [c for c in out["calls"] if c["tool"] == "measures_write"]


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == _scenarios()


def test_a_faithful_run_grades_full_marks() -> None:
    row = _run()
    assert all(hits == n for hits, n in row.values()), row
    assert row["accepted"] == [4, 4] and row["action_right"] == [6, 6]


def test_claiming_withheld_after_being_shown_the_prior_is_caught() -> None:
    def claims_withheld(out, scenario):
        for call in _writes(out):
            call["arguments"]["procedure"]["prior"] = "withheld"
        return out
    assert _run(claims_withheld)["prior_true"] == [4, 5]


def test_a_re_score_written_beside_the_earlier_claim_is_caught() -> None:
    """Accepted by the verb (a fresh draw earns a rung), and still not a replacement."""
    def beside(out, scenario):
        for call in _writes(out):
            call["arguments"]["cells"][0].pop("supersedes", None)
        return out
    row = _run(beside)
    # r2's cell was never written, so it has nothing to name and stays right.
    assert row["supersedes_right"] == [1, 4]
    assert row["accepted"] == [4, 4]


def test_a_wrong_supersedes_id_is_refused_by_the_verb() -> None:
    def wrong(out, scenario):
        for call in _writes(out):
            cell = call["arguments"]["cells"][0]
            if "supersedes" in cell:
                cell["supersedes"] += "-2"
        return out
    assert _run(wrong)["accepted"] == [1, 4]  # r2 names nothing, so it is untouched


def test_reusing_the_first_sweeps_round_is_refused_by_the_verb() -> None:
    def round_one(out, scenario):
        for call in _writes(out):
            call["arguments"]["procedure"]["round"] = 1
        return out
    # r2's cell had no draw in round 1; r4's prior is shown, and the tools key a round by (number, prior).
    assert _run(round_one)["accepted"] == [2, 4]


def test_a_blank_through_mark_missing_is_caught() -> None:
    def marks(out, scenario):
        out["calls"].append({"tool": "measures_mark_missing", "arguments": {}})
        return out
    assert _run(marks)["no_mark_missing"] == [0, 6]


def test_narrowing_to_the_alternative_the_new_document_names_is_caught() -> None:
    def narrows(out, scenario):
        if scenario["id"] == "r1":
            out["calls"] = [c for c in out["calls"] if c["tool"] != "measures_write"
                            or c["arguments"]["cells"][0]["alternativeId"] == "tamsin"]
        return out
    assert _run(narrows)["scope_right"] == [3, 4]


def test_reading_the_earlier_scores_first_is_caught() -> None:
    def peeks(out, scenario):
        out["calls"].insert(0, {"tool": "report_weaknesses", "arguments": {"analysis_id": "kettles"}})
        return out
    assert _run(peeks)["no_prior_read"] == [0, 3]


def test_retrieving_from_the_new_documents_only_is_caught() -> None:
    def narrow_search(out, scenario):
        for call in out["calls"]:
            if call["tool"] == "corpus_search":
                call["arguments"]["document_ids"] = ["doc-new"]
        return out
    assert _run(narrow_search)["fresh_retrieval"] == [0, 4]


def test_a_score_carried_forward_onto_a_conflict_is_caught() -> None:
    def carries(out, scenario):
        if scenario["id"] == "r3":
            for call in _writes(out):
                cell = call["arguments"]["cells"][0]
                if cell["alternativeId"] == "copperleaf":
                    hit = _own_hits(scenario, "copperleaf")[0]
                    cell.pop("missing")
                    cell |= {"justification": "kept", "evidence": [_span(hit)], "value": 1}
        return out
    assert _run(carries)["right_outcome"] == [3, 4]


def test_writing_a_revision_as_a_re_score_is_caught() -> None:
    def writes_anyway(out, scenario):
        if scenario["id"] == "r6":
            out["calls"] = copy.deepcopy(_faithful(_scenarios()[0])["calls"])
        return out
    assert _run(writes_anyway)["action_right"] == [5, 6]


def test_the_grader_reads_the_block_the_prompt_teaches() -> None:
    body = prompts()["rescore-criterion"].body
    block = re.search(r"\n    (Re-scored:.*?)\n\n", body, re.S).group(1)
    taught = [line.strip().split(":")[0] for line in block.splitlines()]
    assert "Prior" in taught
    assert "withheld | shown" in next(line for line in block.splitlines() if "Prior:" in line)
