"""The ``run-analysis`` prompt's evaluation (#77): fixtures are the tools' real output, and the grader reads the prompt's own block."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/run-analysis/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("run_analysis_adherence"), _script("run_analysis_scenarios")
REVIEW = "Re-score with more evidence: none\nNext: nothing further"


def _reply(want: dict, *, kind: str | None = None, prose: str = "Where the run stands.") -> str:
    scope = "not yet set" if want["scope"] is None else ", ".join(want["scope"])
    aside = ", ".join(want["setAside"] or []) or "none"
    if want["deferredOnRecord"]:
        prose += " I mark the other two `deferred` with measures_mark_missing."
    if want["reviewWritten"]:
        prose += f"\n\n```\n{REVIEW}\n```"
    return (f"{prose}\n\n```\nStage: 5 — populate\nScope: {scope}; set aside: {aside}\n"
            f"Next: {kind or want['next'][0]} — the next step\n```")


def _graded(**kinds):
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [{"scenarioId": s["id"], "output": _reply(s["expected"], kind=kinds.get(s["id"]))} for s in scenarios]
    return grader.grade(scenarios, outputs)


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_grader_reads_every_label_and_kind_the_prompt_teaches() -> None:
    body = prompts()["run-analysis"].body
    found = re.search(r"```\n(Stage:.*?)```", body, re.S).group(1)
    assert [line.split(":")[0] for line in found.strip().splitlines()] == list(grader.LINES)
    kinds = re.search(r"^Next: <([^>]*)>", found, re.M).group(1)
    assert tuple(k.strip() for k in kinds.split("|")) == grader.KINDS


def test_a_faithful_reply_grades_full_marks() -> None:
    row = _graded()
    assert all(hits == total for hits, total in row.values()), row


@pytest.mark.parametrize("scenario", ["a2", "a7"])
def test_scoring_past_the_gate_is_caught(scenario) -> None:
    hits, total = _graded(**{scenario: "score"})["gate held"]
    assert hits == total - 1


def test_stopping_at_a_filled_matrix_is_caught() -> None:
    hits, total = _graded(a6="stop")["closes with review"]
    assert hits == total - 1


def test_a_scope_that_drops_the_set_aside_criteria_is_caught() -> None:
    scenarios = json.loads(SCENARIOS.read_text())
    a4 = next(s for s in scenarios if s["id"] == "a4")
    ok = grader.grade_one(a4, "Stage: 4 — confirm\nScope: durability, upkeep-cost; set aside: none\nNext: score — go")
    assert ok["scope right"] is False and ok["deferred on record"] is False


@pytest.mark.parametrize("line, want", [
    ("all; set aside: none", ("all", set())),
    ("durability, upkeep cost; set aside: capacity, ease of turning",
     ({"durability", "upkeep-cost"}, {"capacity", "ease-of-turning"})),
    ("not yet set; set aside: none", (set(), set())),
])
def test_the_scope_line_is_read_with_or_without_hyphens(line, want) -> None:
    assert grader.scope(line) == want
