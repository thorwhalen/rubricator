"""The ``rescore-criterion`` prompt's evaluation: its fixtures are the tools' real output, and its grader replays the writes (#129).

The grader judges a subject by replaying its ``measures_write`` calls against a fresh copy of the
scenario's analysis, so these tests hold the grader to the verbs: a faithful answer grades full
marks, and each failure the prompt is written against is caught by the metric named for it.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from rubricator.prompts import prompts
from script_loader import script as _script

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/rescore-criterion/scenarios.json"
SEARCH = "corpus_search, per alternative, over the whole corpus"


builder = _script("rescore_criterion_scenarios")
grader = _script("rescore_criterion_adherence")
ANALYSIS_ID = builder.ANALYSIS_ID


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


#: What a faithful reply says on each ask scenario: what it is asking about, and nothing else.
ASKS = {
    "r5": "Your earlier scores are in this conversation, so a re-score here would be shown; "
          "a withheld one needs a fresh conversation. Go ahead here?",
    "r6": "Counting anything under 55 dB as top marks changes the criterion's anchors: that is a "
          "revision, not a re-score. Revise it?",
    "r9": "Brindle's cell holds two live claims of mine (brindle-spare-parts-score and "
          "brindle-spare-parts-score-2): which one should the re-score replace?",
    "r10": "Tamsin's quietness is Ana's claim, not mine, and only Ana can replace it. Is Ana this "
           "scorer under another id, or should I add my own claim beside hers?",
    "r11": "The claims on spare parts are all scorer's, an agent whose model is not recorded. "
           "Shall I write as contributor scorer?",
    "r12": "The only claim on Tamsin's quietness is Ana's, and she is a person: I will not write as "
           "her. Who am I writing as, and should my re-score be a second claim beside hers?",
}


def _faithful(scenario):
    want = scenario["expected"]
    if want["action"] == "ask":
        return {"scenarioId": scenario["id"], "calls": [], "reply": ASKS[scenario["id"]]}
    procedure = {"round": want["round"], "session": want["session"] or "fresh", "prior": want["prior"]}
    calls = [{"tool": "analysis_get", "arguments": {"analysis_id": ANALYSIS_ID, "view": "criteria"}},
             {"tool": "analysis_get", "arguments": {"analysis_id": ANALYSIS_ID, "view": "outstanding"}},
             {"tool": "measures_rescore_context",
              "arguments": {"analysis_id": ANALYSIS_ID, "criterion_id": scenario["criterion"]}}]
    calls += [{"tool": "corpus_search", "arguments": {"analysis_id": ANALYSIS_ID, "query": alt}}
              for alt in want["cells"]]
    author = (scenario["contributor"] or {}).get("author") or {"id": "scorer", "displayName": "Scorer",
                                                               "kind": "agent"}
    calls += [{"tool": "measures_write", "arguments": {
        "contributor_id": "scorer", "author": author,
        "expected_criteria_version": "1", "procedure": procedure,
        "cells": [_cell(scenario, alt, outcome, supersedes)]}}
        for alt, (outcome, supersedes) in want["cells"].items()]
    reply = (f"Re-scored: {scenario['criterion']} — {len(want['cells'])} of 3 alternatives\n"
             f"Prior: {want['prior']} — as the pass was\nNext: review")
    return {"scenarioId": scenario["id"], "calls": calls, "reply": reply}


def _scenarios():
    return json.loads(SCENARIOS.read_text())


def _scenario(sid):
    return next(s for s in _scenarios() if s["id"] == sid)


def _run(fault=lambda out, scenario: out):
    scenarios = _scenarios()
    return grader.grade(scenarios, [fault(_faithful(s), s) for s in scenarios])


def _writes(out):
    return [c for c in out["calls"] if c["tool"] == "measures_write"]


def _unicode_neutral(text: str) -> str:
    """``corpus_search`` names the interpreter's Unicode version (``lexical.UNICODE_VERSION``) in its summary."""
    return re.sub(r"Unicode \d+(\.\d+)*", "Unicode <interpreter's>", text)


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    now = _unicode_neutral((tmp_path / "now.json").read_text())
    assert json.loads(now) == json.loads(_unicode_neutral(SCENARIOS.read_text()))


def test_a_faithful_run_grades_full_marks() -> None:
    row = _run()
    assert all(hits == n for hits, n in row.values()), row
    assert row["accepted"] == [6, 6] and row["action_right"] == [12, 12] and row["round_right"] == [6, 6]


def _claims(scenario):
    return scenario["toolResults"]["measures_rescore_context"]


def test_the_value_free_read_names_the_live_claim_and_the_round() -> None:
    """r7's read gives the successor id and round 2, where v1 had to recover them from a refusal (#294)."""
    claims = _claims(_scenario("r7"))
    brindle = next(c for c in claims["cells"] if c["alternativeId"] == "brindle")
    assert brindle["liveClaims"] == [{"assertionId": "brindle-spare-parts-score-2",
                                      "contributorId": "scorer", "authorId": "scorer", "yours": True}]
    assert claims["writers"] == [
        {"contributorId": "scorer", "authorId": "scorer", "kind": "agent", "model": None,
         "latestRound": 2}]
    text = json.dumps({k: v for k, v in claims.items() if k != "summary"})
    assert '"value"' not in text and '"justification"' not in text and "Spare parts are" not in text


def test_claiming_withheld_after_being_shown_the_prior_is_caught() -> None:
    def claims_withheld(out, scenario):
        for call in _writes(out):
            call["arguments"]["procedure"]["prior"] = "withheld"
        return out
    assert _run(claims_withheld)["prior_true"] == [6, 7]


def test_a_re_score_written_beside_the_earlier_claim_is_caught() -> None:
    """Accepted by the verb (a fresh draw earns a rung), and still not a replacement."""
    def beside(out, scenario):
        for call in _writes(out):
            call["arguments"]["cells"][0].pop("supersedes", None)
        return out
    row = _run(beside)
    # r2's cell was never written, so it has nothing to name and stays right.
    assert row["supersedes_right"] == [1, 6]
    assert row["accepted"] == [6, 6]


def test_a_wrong_supersedes_id_is_refused_by_the_verb() -> None:
    def wrong(out, scenario):
        for call in _writes(out):
            cell = call["arguments"]["cells"][0]
            if "supersedes" in cell:
                cell["supersedes"] += "-2"
        return out
    assert _run(wrong)["accepted"] == [1, 6]  # r2 names nothing, so it is untouched


def test_naming_the_default_id_after_it_was_replaced_is_refused() -> None:
    def default_id(out, scenario):
        if scenario["id"] == "r7":
            _writes(out)[0]["arguments"]["cells"][0]["supersedes"] = "brindle-spare-parts-score"
        return out
    row = _run(default_id)
    assert row["accepted"] == [5, 6] and row["supersedes_right"] == [5, 6]


def test_a_counted_round_is_caught_even_where_the_verb_takes_it() -> None:
    """A used round number is accepted on a cell with no draw in it, and files the pass wrongly."""
    def round_one(out, scenario):
        for call in _writes(out):
            call["arguments"]["procedure"]["round"] = 1
        return out
    row = _run(round_one)
    assert row["round_right"] == [0, 6]
    # r2's cell had no draw in round 1, and r4's prior is shown (a round is keyed by number and prior).
    assert row["accepted"] == [2, 6]


def test_ignoring_the_reads_latest_round_is_caught() -> None:
    """r7's scorer last wrote round 2: a re-score counted as round 2 collides with that draw."""
    def stale(out, scenario):
        if scenario["id"] == "r7":
            for call in _writes(out):
                call["arguments"]["procedure"]["round"] = 2
        return out
    row = _run(stale)
    assert row["round_right"] == [5, 6] and row["accepted"] == [5, 6]


def test_writing_over_one_of_several_live_claims_is_caught() -> None:
    def picks(out, scenario):
        if scenario["id"] == "r9":
            out["calls"] = copy.deepcopy(_faithful(_scenario("r7"))["calls"])
        return out
    assert _run(picks)["action_right"] == [11, 12]


def test_writing_beside_another_contributors_claim_is_caught() -> None:
    def beside(out, scenario):
        if scenario["id"] == "r10":
            out["calls"] = copy.deepcopy(_faithful(_scenario("r2"))["calls"])
        return out
    assert _run(beside)["action_right"] == [11, 12]


def test_a_blank_through_mark_missing_is_caught() -> None:
    def marks(out, scenario):
        out["calls"].append({"tool": "measures_mark_missing", "arguments": {}})
        return out
    assert _run(marks)["no_mark_missing"] == [0, 12]


def test_narrowing_to_the_alternative_the_new_document_names_is_caught() -> None:
    def narrows(out, scenario):
        if scenario["id"] == "r1":
            out["calls"] = [c for c in out["calls"] if c["tool"] != "measures_write"
                            or c["arguments"]["cells"][0]["alternativeId"] == "tamsin"]
        return out
    assert _run(narrows)["scope_right"] == [5, 6]


def test_reading_the_earlier_scores_first_is_caught() -> None:
    def peeks(out, scenario):
        out["calls"].insert(0, {"tool": "report_completeness", "arguments": {"analysis_id": ANALYSIS_ID}})
        return out
    assert _run(peeks)["no_prior_read"] == [0, 5]


def test_retrieving_from_the_new_documents_only_is_caught() -> None:
    def narrow_search(out, scenario):
        for call in out["calls"]:
            if call["tool"] == "corpus_search":
                call["arguments"]["document_ids"] = ["doc-new"]
        return out
    assert _run(narrow_search)["fresh_retrieval"] == [0, 6]


def test_skipping_an_alternatives_retrieval_is_caught() -> None:
    def one_search(out, scenario):
        if scenario["id"] == "r1":
            out["calls"] = [c for c in out["calls"]
                            if c["tool"] != "corpus_search" or c["arguments"]["query"] == "tamsin"]
        return out
    assert _run(one_search)["fresh_retrieval"] == [5, 6]


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
    assert _run(carries)["right_outcome"] == [5, 6]


def test_writing_a_revision_as_a_re_score_is_caught() -> None:
    def writes_anyway(out, scenario):
        if scenario["id"] == "r6":
            out["calls"] = copy.deepcopy(_faithful(_scenario("r1"))["calls"])
        return out
    assert _run(writes_anyway)["action_right"] == [11, 12]


def test_asking_on_a_write_scenario_is_graded_not_crashed() -> None:
    row = grader.grade_one(_scenario("r1"), {"scenarioId": "r1", "calls": [], "reply": "Shall I go ahead?"})
    assert row["action_right"] is False
    assert {k for k, v in row.items() if v is not None} == {"action_right"}


def test_nothing_relevant_written_is_not_a_pass() -> None:
    out = _faithful(_scenario("r1"))
    for call in _writes(out):
        call["arguments"]["cells"][0]["criterionId"] = "quietness"
    row = grader.grade_one(_scenario("r1"), out)
    assert row["scope_right"] is False
    assert row["supersedes_right"] is None and row["right_outcome"] is None


def test_an_ask_that_denies_the_prior_was_shown_is_caught() -> None:
    reply = "The prior was not shown to me, so shall I re-score?"
    row = grader.grade_one(_scenario("r5"), {"scenarioId": "r5", "calls": [], "reply": reply})
    assert row["prior_true"] is False


def test_the_grader_reads_the_block_and_the_example_the_prompt_teaches() -> None:
    body = prompts()["rescore-criterion"].body
    block = re.search(r"\n    (Re-scored:.*?)\n\n", body, re.S).group(1)
    assert "Prior" in [line.strip().split(":")[0] for line in block.splitlines()]
    example = re.search(r"`(Prior: [^`]+)`", body.replace("\n", " ")).group(1)
    assert grader._line(example, "Prior").startswith("withheld")


def test_an_empty_ask_is_not_full_marks() -> None:
    """r6, r9 and r10 are judged on what the reply asks, not only on writing nothing."""
    def silent(out, scenario):
        if scenario["id"] in ("r6", "r9", "r10"):
            out["reply"] = ""
        return out
    assert _run(silent)["asks_right"] == [3, 6]


def test_an_ask_about_the_wrong_thing_is_caught() -> None:
    for sid in ("r9", "r10"):
        row = grader.grade_one(_scenario(sid), {"scenarioId": sid, "calls": [], "reply": ASKS["r6"]})
        assert row["action_right"] is True and row["asks_right"] is False, sid


def test_three_cells_in_one_write_is_caught() -> None:
    def batched(out, scenario):
        writes = _writes(out)
        if scenario["id"] == "r1":
            writes[0]["arguments"]["cells"] = [c for w in writes for c in w["arguments"]["cells"]]
            out["calls"] = [c for c in out["calls"] if c not in writes[1:]]
        return out
    assert _run(batched)["scope_right"] == [5, 6]


def test_one_search_naming_every_alternative_is_not_a_search_each() -> None:
    def one_query(out, scenario):
        if scenario["id"] == "r1":
            searches = [c for c in out["calls"] if c["tool"] == "corpus_search"]
            for c in searches:
                c["arguments"]["query"] = "brindle copperleaf tamsin spare parts"
        return out
    assert _run(one_query)["fresh_retrieval"] == [5, 6]


def test_a_write_the_verb_cannot_take_is_a_refusal_not_a_crash() -> None:
    def no_author(out, scenario):
        for call in _writes(out):
            call["arguments"].pop("author")
            call["arguments"]["bogus"] = 1
        return out
    assert _run(no_author)["accepted"] == [0, 6]


def test_r10s_read_shows_anas_claim_although_the_scorer_is_named() -> None:
    """The first review's blocker: the read the prompt instructs must not hide another writer's claim."""
    claims = _claims(_scenario("r10"))
    tamsin = next(c for c in claims["cells"] if c["alternativeId"] == "tamsin")
    assert [(c["contributorId"], c["yours"]) for c in tamsin["liveClaims"]] == [("ana", False)]


def test_an_ask_about_the_round_only_is_not_an_ask_about_the_claims() -> None:
    """Even followed by the block, whose Not written line names the claims and the writer."""
    for reply in ("Which round number is this sweep? Nothing gives me one.",
                  "Which one of these rounds should I use?\nReplaced: brindle-spare-parts-score, "
                  "tamsin (Ana's claim, a person: replace it?)\nNext: re-score"):
        for sid in ("r9", "r10", "r12"):
            row = grader.grade_one(_scenario(sid), {"scenarioId": sid, "calls": [], "reply": reply})
            assert row["asks_right"] is False, (sid, reply)


def test_r12s_read_shows_the_only_writer_is_a_person() -> None:
    claims = _claims(_scenario("r12"))
    assert [(w["contributorId"], w["kind"]) for w in claims["writers"]] == [("ana", "human"),
                                                                            ("scorer", "agent")]
    tamsin = next(c for c in claims["cells"] if c["alternativeId"] == "tamsin")
    assert [(c["contributorId"], c["yours"]) for c in tamsin["liveClaims"]] == [("ana", False)]


def test_an_ask_on_the_not_written_line_counts() -> None:
    reply = ("I wrote nothing.\nNot written: brindle — two live claims of mine (brindle-spare-parts-score, "
             "brindle-spare-parts-score-2); which one should the re-score replace?\nNext: your answer")
    row = grader.grade_one(_scenario("r9"), {"scenarioId": "r9", "calls": [], "reply": reply})
    assert row["asks_right"] is True
