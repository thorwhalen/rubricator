"""The ``resume`` prompt's evaluation: its fixtures are the tools' real output, and its grader reads the prompt's own block (#76).

The prompt asks for a fixed block and the grader parses it, so the two are
held together here: a label renamed in one and not the other would make every
run grade zero, or grade a different form than the one the prompt teaches.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/resume/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("resume_adherence"), _script("resume_scenarios")


def _block(want: dict, **override) -> str:
    want = {**want, **override}
    confirmed = {"confirmed": "Ana at 2026-10-12T09:30:00Z, criteria version 1", "not-confirmed": "no",
                 "changed": "criteria changed since Ana's confirmation at 2026-10-12T09:30:00Z"}
    return (f"Where it stands.\n\n```\nConfirmed: {confirmed[want['confirmation']]}\n"
            f"Nobody has looked: {want['nobody']}\nSet aside on purpose: {want['aside']}\n"
            f"Looked, answer is a blank: {want['blank']}\nScored: {want['scored']}\n"
            f"Re-score after a criteria change: {want['rescore']}\nNext: {want['next']} — one step\n```")


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    """A tool whose output drifted would leave subjects graded against a state it no longer produces."""
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_grader_reads_every_label_the_prompt_teaches() -> None:
    body = prompts()["resume"].body
    block = re.search(r"```\n(Confirmed:.*?)```", body, re.S).group(1)
    taught = [line.split(":")[0] for line in block.strip().splitlines()]
    assert taught == list(grader.LINES)
    kinds = set(re.findall(r"^- `([a-z-]+)` —", body, re.M))
    assert kinds == set(grader.KINDS)


def test_a_faithful_reply_grades_full_marks() -> None:
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [{"scenarioId": s["id"], "output": _block(s["expected"])} for s in scenarios]
    row = grader.grade(scenarios, outputs)
    assert row.pop("settled_counted_as_work").startswith("0/")
    assert all(hits == total for hits, total in (v.split("/") for v in row.values())), row


@pytest.mark.parametrize("fault, metric", [
    (lambda w: {"nobody": w["nobody"] + w["blank"]}, "blanks_kept_apart"),
    (lambda w: {"next": "confirm"}, "no_reask"),
])
def test_each_failure_the_prompt_exists_to_stop_is_caught(fault, metric) -> None:
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [{"scenarioId": s["id"], "output": _block(s["expected"], **fault(s["expected"]))}
               for s in scenarios]
    unaffected = sum(fault(s["expected"]) == {"nobody": s["expected"]["nobody"]} for s in scenarios)
    hits, _total = grader.grade(scenarios, outputs)[metric].split("/")
    assert int(hits) == unaffected  # a scenario with no settled blank cannot fold one


@pytest.mark.parametrize("arm", ["sonnet", "haiku"])
def test_the_recorded_evaluation_still_grades_as_recorded(arm) -> None:
    """A grader change that moved the published v1 numbers would otherwise go unnoticed."""
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = json.loads((ROOT / f"docs/evaluation/resume/2026-10-13/out-v1-{arm}.json").read_text())
    row = grader.grade(scenarios, outputs)
    assert row.pop("settled_counted_as_work") == "0/5"
    assert all(hits == total for hits, total in (v.split("/") for v in row.values())), row
