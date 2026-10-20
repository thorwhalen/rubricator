"""The ``enumerate-alternatives`` prompt's evaluation (#70): the grader reads the prompt's own block and runs it through the real ``alternatives_set``."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/enumerate-alternatives/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("enumerate_alternatives_adherence"), _script("enumerate_alternatives_scenarios")


def _row(i, label, description):
    return {"id": i, "label": label, "description": description}


#: A faithful block per scenario.
FAITHFUL = {
    "e1": {"alternatives": [_row("aldous", "Aldous 4", 'Stated: "the Aldous 4"'), _row("brandt", "Brandt 6", 'Stated: "the Brandt 6"'),
                            _row("corvin", "Corvin 5", 'Stated: "the Corvin 5"')], "proposed": [], "possibleDuplicates": []},
    "e2": {"alternatives": [_row("postgres", "Postgres", 'Stated: "Postgres"'), _row("postgresql", "PostgreSQL", 'Stated: "PostgreSQL"'),
                            _row("mysql", "MySQL", 'Stated: "MySQL"'), _row("sqlite", "SQLite", 'Stated: "SQLite"')],
           "proposed": [], "possibleDuplicates": [{"ids": ["postgres", "postgresql"], "question": "Are Postgres and PostgreSQL one alternative?"}]},
    "e3": {"alternatives": [_row("brandt", "Brandt 6", 'Stated: "the Brandt 6"'), _row("corvin", "Corvin 5", 'Stated: "the Corvin 5"')],
           "proposed": [{"label": "Delmar 3", "basis": "source", "why": 'Review notes: "The Delmar 3 was also reviewed and withdrawn from sale"'}],
           "possibleDuplicates": []},
    "e4": {"alternatives": [], "proposed": [{"label": "Obsidian", "basis": "inference", "why": "a common note app"}], "possibleDuplicates": []},
    "e5": {"alternatives": [_row("hugo", "Hugo", "Own inference: a widely used static site generator"),
                            _row("mkdocs", "MkDocs", "Own inference: built for documentation"),
                            _row("docusaurus", "Docusaurus", "Own inference: built for documentation sites")],
           "proposed": [], "possibleDuplicates": []},
}


def _reply(block: dict) -> str:
    return "A few lines on what is open.\n\n```json\n" + json.dumps(block) + "\n```"


def _graded(edit=None):
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = []
    for s in scenarios:
        block = dict(FAITHFUL[s["id"]])
        if edit:
            block = edit(s["id"], block)
        outputs.append({"scenarioId": s["id"], "output": _reply(block)})
    return grader.grade(scenarios, outputs)


def _short(row, metric) -> bool:
    return row[metric][0] < row[metric][1]


def test_the_stored_scenarios_are_what_the_generator_writes(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_block_in_the_prompt_is_what_alternatives_set_takes() -> None:
    body = prompts()["enumerate-alternatives"].body
    block = json.loads(body[body.index("```json") + 7:].split("```")[0].replace("|", "/"))
    assert set(block) == {"alternatives", "proposed", "possibleDuplicates"}
    assert grader.feeds_alternatives_set(FAITHFUL["e1"])


def test_a_faithful_reply_grades_full_marks() -> None:
    row = _graded()
    assert all(hits == total for hits, total in row.values()), row


def test_padding_the_set_with_a_guess_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "alternatives": b["alternatives"] + [_row("delmar", "Delmar 3", "plausible")]} if i == "e1" else b)
    assert _short(row, "no unlicensed rows")


def test_merging_look_alikes_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "alternatives": b["alternatives"][1:], "possibleDuplicates": []} if i == "e2" else b)
    assert _short(row, "duplicates kept and flagged")
    assert _short(row, "keeps the stated")


def test_writing_a_source_candidate_into_the_set_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "alternatives": b["alternatives"] + [_row("delmar", "Delmar 3", "Source")], "proposed": []} if i == "e3" else b)
    assert _short(row, "source candidate proposed with span")
    assert _short(row, "no unlicensed rows")


def test_a_source_candidate_with_no_span_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "proposed": [{"label": "Delmar 3", "basis": "source", "why": "the notes"}]} if i == "e3" else b)
    assert _short(row, "source candidate proposed with span")


def test_an_unmarked_inference_is_caught() -> None:
    row = _graded(lambda i, b: {**b, "alternatives": [_row(r["id"], r["label"], "a good one") for r in b["alternatives"]]} if i == "e5" else b)
    assert _short(row, "inference marked")


def test_a_reply_with_no_block_fails_everything() -> None:
    row = grader.grade(json.loads(SCENARIOS.read_text()), [])
    assert all(hits == 0 for hits, _ in row.values())


def test_the_prompt_is_served() -> None:
    assert prompts()["enumerate-alternatives"].stage == 2
