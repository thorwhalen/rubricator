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


def _block(want: dict, *, prose: str = "Where it stands.", **override) -> str:
    want = {**want, **override}
    confirmed = {"confirmed": "Ana at 2026-10-12T09:30:00Z, criteria version 1",
                 "skipped": "skipped at 2026-10-12T09:30:00Z, nobody confirmed",
                 "not-confirmed": "no — never put to anyone",
                 "changed": "criteria changed since Ana's confirmation at 2026-10-12T09:30:00Z"}
    return (f"{prose}\n\n```\nConfirmed: {confirmed.get(want['confirmation'], want['confirmation'])}\n"
            f"Nobody has looked: {want['nobody']} cells\nSet aside on purpose: {want['aside']} cells\n"
            f"Re-score after a criteria change: {want['rescore']} cells\nScored: {want['scored']} claims\n"
            f"Looked, answer is a blank: {want['blank']} claims\nNot applicable: {want['na']} claims\n"
            f"Next: {want['next']} — one step\n```")


def _graded(**fault):
    """The grade of a run where every reply is faithful except for ``fault``, a function of the expectation."""
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [{"scenarioId": s["id"], "output": _block(s["expected"], **{
        k: f(s["expected"]) for k, f in fault.items()})} for s in scenarios]
    return scenarios, grader.grade(scenarios, outputs)


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
    _scenarios, row = _graded()
    assert row.pop("settled_counted_as_work").startswith("0/")
    assert all(hits == total for hits, total in (v.split("/") for v in row.values())), row


def _hits(row, metric):
    return int(row[metric].split("/")[0])


def test_folding_settled_blanks_into_work_is_caught() -> None:
    scenarios, row = _graded(nobody=lambda w: w["nobody"] + w["blank"])
    with_blanks = sum(1 for s in scenarios if s["expected"]["blank"])
    assert _hits(row, "settled_counted_as_work") == with_blanks
    assert _hits(row, "blanks_kept_apart") == len(scenarios) - with_blanks


@pytest.mark.parametrize("field", ["nobody", "aside", "rescore", "scored", "blank", "na"])
def test_every_count_is_graded(field) -> None:
    scenarios, row = _graded(**{field: lambda w, f=field: w[f] + 1})
    assert _hits(row, "counts_right") == 0


def test_a_reask_where_the_confirmation_stands_is_caught() -> None:
    scenarios, row = _graded(next=lambda w: "confirm")
    assert _hits(row, "no_reask") == 0


def test_a_reask_in_the_prose_is_caught_even_when_the_block_says_otherwise() -> None:
    scenarios, row = _graded(prose=lambda w: "Could you re-confirm the criteria before I go on?")
    assert _hits(row, "no_reask") == 0


def test_skipping_a_needed_confirmation_is_caught() -> None:
    scenarios, row = _graded(next=lambda w: "score")
    assert _hits(row, "reask_when_needed") == 0


@pytest.mark.parametrize("line, meaning", [
    ("none on record", "not-confirmed"),
    ("never", "not-confirmed"),
    ("no — Ana asked for changes at 2026-10-12T09:30:00Z", "not-confirmed"),
    ("Ana at 2026-10-12T09:30:00Z, criteria version 1 (not changed since)", "confirmed"),
    ("skipped at 2026-10-12T09:30:00Z, nobody confirmed", "skipped"),
    ("criteria changed since Ana's confirmation at 2026-10-12T09:30:00Z", "changed"),
])
def test_the_confirmation_line_is_read_by_how_it_starts(line, meaning) -> None:
    assert grader.confirmation_of(line) == meaning


def test_only_the_block_is_read() -> None:
    reply = "Scored so far: 6 of 9.\nNext, please look at the noise column.\n\n" + _block(
        {"confirmation": "confirmed", "nobody": 1, "aside": 0, "blank": 1, "scored": 2, "rescore": 0,
         "na": 0, "next": "score"}, prose="").replace("Confirmed:", "**Confirmed:**")
    got = grader.parse(reply)
    assert (got["scored"], got["next"], got["confirmation"]) == (2, "score", "confirmed")


@pytest.mark.parametrize("arm", ["sonnet", "haiku"])
def test_the_recorded_evaluation_still_grades_as_recorded(arm) -> None:
    """A grader change that moved the published v1 numbers would otherwise go unnoticed."""
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = json.loads((ROOT / f"docs/evaluation/resume/2026-10-13/out-v1-{arm}.json").read_text())
    row = grader.grade(scenarios, outputs)
    assert row.pop("settled_counted_as_work") == "0/5"
    assert all(hits == total for hits, total in (v.split("/") for v in row.values())), row
