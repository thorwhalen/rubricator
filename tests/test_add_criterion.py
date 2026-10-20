"""The ``add-criterion`` prompt's evaluation: its fixtures are the tools' real output, and its grader replays the call (#128).

The grader judges a subject by replaying its ``criteria_set`` call against a fresh copy of
the scenario's analysis, so these tests hold the grader to the verbs: a faithful answer
grades full marks, and each failure the prompt is written against is caught by the metric
named for it.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/add-criterion/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("add_criterion_adherence"), _script("add_criterion_scenarios")

NEW = {
    "id": "boil-time", "label": "Boil time", "preference": "decreasing",
    "anchors": [{"level": "1", "text": "A source states a full kettle boils in under three minutes."},
                {"level": "3", "text": "A source states a full kettle boils in three to five minutes."},
                {"level": "5", "text": "A source states a full kettle boils in more than five minutes."}],
    "definition": {
        "objective": "Nobody waits long for hot water in the morning",
        "question": "How long does the maker state a full kettle takes to boil?",
        "evidenceRule": "The maker's stated boil time for the full capacity.",
        "missingRules": [{"when": "No boil time is stated.", "code": "not-evidenced"},
                         {"when": "The maker's sources state different times.", "code": "indeterminate"}],
        "exclusions": ["How loud it is while boiling; that is quietness."],
    },
}
BLOCK = ("Added: boil-time — Boil time (user-stated)\nCriteria version: 1\n"
         "New column: 3 cells, not-assessed — nobody has looked\n"
         "Existing cells: unchanged — none re-scored, none blanked, none superseded\n"
         "Yours to confirm: the anchors\nNext: confirm the criteria (frame_confirm, scope criteria)")


def _faithful(scenario):
    if scenario["expected"]["action"] == "ask":
        names = scenario["expected"]["names"] or "what you mean"
        return {"scenarioId": scenario["id"], "calls": [], "reply": f"That overlaps {names}; which do you mean?"}
    existing = scenario["toolResults"]["analysis_get"]["criteria"]
    return {"scenarioId": scenario["id"], "reply": BLOCK, "calls": [
        {"tool": "analysis_get", "arguments": {"analysis_id": "kettles", "view": "criteria"}},
        {"tool": "criteria_set", "arguments": {"analysis_id": "kettles", "criteria": [*existing, NEW]}},
        {"tool": "frame_confirm", "arguments": {"analysis_id": "kettles"}}]}


def _run(fault=lambda out, scenario: out):
    scenarios = json.loads(SCENARIOS.read_text())
    return grader.grade(scenarios, [fault(_faithful(s), s) for s in scenarios])


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_a_faithful_run_grades_full_marks() -> None:
    row = _run()
    assert all(hits == n for hits, n in row.values()), row
    assert row["accepted"] == [2, 2] and row["names_the_criterion"] == [2, 2]


def _add_scenario_calls(out):
    return [c for c in out["calls"] if c["tool"] == "criteria_set"]


def test_a_re_typed_existing_criterion_is_caught_twice() -> None:
    """Tidying one anchor of an existing criterion is an edit: it moves that criterion's version."""
    def tidy(out, scenario):
        for call in _add_scenario_calls(out):
            crits = copy.deepcopy(call["arguments"]["criteria"])
            crits[1]["anchors"][2]["text"] = "A source states spare parts are stocked for a decade or more."
            call["arguments"]["criteria"] = crits
        return out
    row = _run(tidy)
    assert row["existing_untouched"] == [0, 2]
    assert row["nothing_superseded"] == [0, 2]


def test_a_placeholder_blank_in_the_new_column_is_caught() -> None:
    def placeholder(out, scenario):
        out["calls"].append({"tool": "measures_mark_missing", "arguments": {}})
        return out
    assert _run(placeholder)["no_cell_written"] == [0, 5]


def test_adding_when_the_request_needed_a_question_is_caught() -> None:
    def adds(out, scenario):
        if scenario["expected"]["action"] == "ask":
            existing = scenario["toolResults"]["analysis_get"]["criteria"]
            out["calls"] = [{"tool": "criteria_set", "arguments": {"criteria": [*existing, NEW]}}]
        return out
    assert _run(adds)["action_right"] == [2, 5]


def test_an_undefined_new_criterion_is_caught() -> None:
    def bare(out, scenario):
        for call in _add_scenario_calls(out):
            call["arguments"]["criteria"][-1] = {**NEW, "definition": {}}
        return out
    assert _run(bare)["new_fully_defined"] == [0, 2]


def test_the_grader_reads_the_block_the_prompt_teaches() -> None:
    body = prompts()["add-criterion"].body
    block = re.search(r"\n    (Added:.*?)\n\n", body, re.S).group(1)
    taught = [line.strip().split(":")[0] for line in block.splitlines()]
    assert {"New column", "Next"} <= set(taught)
    assert "not-assessed" in next(line for line in block.splitlines() if "New column" in line)
