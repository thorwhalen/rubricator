"""The ``frame`` prompt's evaluation (#69): the grader reads the prompt's own block and runs it through the real ``frame_set``."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/frame/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("frame_adherence"), _script("frame_scenarios")

#: A faithful block per scenario: ambiguities worded to match each topic, a decider only where one was named.
FAITHFUL = {
    "f1": {"decision": "pick a coffee grinder", "ambiguities": ["What will it be used for: espresso or drip?", "What is the budget?"]},
    "f2": {"decision": "whether to move the reading room", "ambiguities": ["Who is 'we', and who decides?", "Is the old mill the only option, or are there alternatives to staying?"]},
    "f3": {"decision": "choose a database", "ambiguities": ["Who is 'we' and who decides?", "What workload and data size is it for?"]},
    "f4": {"decision": "rank three tools", "context": "for the food bank board",
           "ambiguities": ["Is the aim to choose one or only to rank, and by what criteria?"]},
    "f5": {"decision": "which of three ovens goes on the bread line", "decider": "the owner of Pelham Bakery",
           "context": "budget 12,000; 2 m bay", "ambiguities": []},
}


def _reply(block: dict) -> str:
    return "One line on what is open.\n\n```json\n" + json.dumps(block) + "\n```"


def _graded(edit=None):
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = []
    for s in scenarios:
        block = dict(FAITHFUL[s["id"]])
        if edit:
            block = edit(s["id"], block)
        outputs.append({"scenarioId": s["id"], "output": _reply(block)})
    return grader.grade(scenarios, outputs)


def test_the_stored_scenarios_are_what_the_generator_writes(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_block_in_the_prompt_is_what_frame_set_takes() -> None:
    body = prompts()["frame"].body
    block = json.loads(body[body.index("```json") + 7:].split("```")[0])
    assert set(block) == {"decision", "decider", "context", "ambiguities"}
    assert grader.feeds_frame_set({"decision": "d", "ambiguities": []})


def test_a_faithful_reply_grades_full_marks() -> None:
    row = _graded()
    assert all(hits == total for hits, total in row.values()), row


def test_a_confident_reading_of_a_bare_question_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "ambiguities": []} if i == "f1" else b)
    assert row["no false none"][0] < row["no false none"][1]
    assert row["names the ambiguities"][0] < row["names the ambiguities"][1]


def test_an_invented_decider_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "decider": "the user"} if i == "f2" else b)
    assert row["no invented decider"][0] < row["no invented decider"][1]
    assert row["no placeholder"][0] < row["no placeholder"][1]


def test_a_block_frame_set_refuses_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "ambiguities": "none"} if i == "f3" else b)
    assert row["feeds frame_set"][0] < row["feeds frame_set"][1]


def test_a_reply_with_no_block_fails_everything() -> None:
    row = grader.grade(json.loads(SCENARIOS.read_text()), [])
    assert all(hits == 0 for hits, _ in row.values())


@pytest.mark.parametrize("prompt_id", ["frame"])
def test_the_prompt_is_served(prompt_id) -> None:
    assert prompts()[prompt_id].stage == 1
