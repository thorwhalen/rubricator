"""The ``review`` prompt's evaluation (#74): fixtures are the tools' real output, and the grader reads the prompt's own block."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/review/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("review_adherence"), _script("review_scenarios")


def _reply(want: dict, *, prose: str = "Where the matrix is weak.", **override) -> str:
    want = {**want, **override}
    most = (f"{want['mostLikely'][0]} — a tested figure from the maker's lab report"
            if want["mostLikely"] else "none — no cell is pivotal")
    return (f"{prose}\n\n```\nRe-score with more evidence: {', '.join(want['rescore']) or 'none'}\n"
            f"Redefine, then put back to the user: {', '.join(want['redefine']) or 'none'}\n"
            f"Most likely to change the picture: {most}\n"
            f"Vetoed or untested floors: {', '.join(want['vetoes']) or 'none'}\n"
            f"Correlations: {want['correlations']} diagnostic, none of them a redundancy finding\n"
            f"Next: gather the evidence named above\n```")


def _graded(**override):
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [{"scenarioId": s["id"], "output": _reply(s["expected"], **{
        k: f(s["expected"]) if callable(f) else f for k, f in override.items()})} for s in scenarios]
    return grader.grade(scenarios, outputs)


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_grader_reads_every_label_the_prompt_teaches() -> None:
    block = re.search(r"```\n(Re-score with more evidence:.*?)```", prompts()["review"].body, re.S).group(1)
    assert [line.split(":")[0] for line in block.strip().splitlines()] == list(grader.LINES)


def test_a_faithful_reply_grades_full_marks() -> None:
    row = _graded()
    assert all(hits == total for hits, total in row.values()), row


def test_rescoring_a_criterion_to_redefine_is_caught() -> None:
    row = _graded(rescore=lambda w: w["rescore"] + [f"larkspur/{c}" for c in w["redefine"]])
    assert row["kept apart"][0] < row["kept apart"][1]


@pytest.mark.parametrize("prose, caught", [
    ("Theft resistance and upkeep cost are redundant: they correlate at 1.0.", True),
    ("The two columns measure the same thing, so merge them.", True),
    ("The correlation is not a redundancy finding; a fresh session could score one column.", False),
    # Both read as redundancy by the first grader, in the 2026-10-20 run, and are the opposite.
    ("The correlation reflects judge carry-over rather than redundancy.", False),
    ("The correlations are scoring-run diagnostics and say nothing about redundancy.", False),
])
def test_a_correlation_read_as_redundancy_is_caught(prose, caught) -> None:
    hits, total = _graded(prose=prose)["no redundancy reading"]
    assert (hits < total) is caught


@pytest.mark.parametrize("prose", ["larkspur/theft-resistance should be 3.", "Re-score it to 2."])
def test_a_suggested_score_is_caught(prose) -> None:
    hits, total = _graded(prose=prose)["no suggested score"]
    assert hits == 0 and total > 0


def test_naming_a_pivotal_cell_where_none_is_pivotal_is_caught() -> None:
    row = _graded(mostLikely=["tessera/upkeep-cost"])
    assert row["most right"][0] < row["most right"][1]
