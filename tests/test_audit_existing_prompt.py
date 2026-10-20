"""The ``audit-existing`` prompt's evaluation (#75): an analysis this repo did not produce, read through the real verbs, and a grader that reads the prompt's own block."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/audit-existing/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("audit_existing_adherence"), _script("audit_existing_scenarios")


def _reply(want: dict, *, prose: str = "What the audit found.", **override) -> str:
    want = {**want, **override}
    join = lambda xs: ", ".join(xs) or "none"  # noqa: E731
    return (f"{prose}\n\n```\nUncited or thinly cited: {join(want['thin'])}\n"
            f"Rests on inference only: {join(want['inference'])}\n"
            f"Confidence above its evidence: {join(want['confidence'])}\n"
            f"No direction of preference: {join(want['direction'])}\n"
            f"Overlap to put to the author: {join([' + '.join(p) for p in want['overlap']])}\n"
            f"Redefine: {join(want['redefine'])}\nChanged: nothing\n```")


def _graded(**override):
    scenarios = json.loads(SCENARIOS.read_text())
    return grader.grade(scenarios, [{"scenarioId": s["id"], "output": _reply(s["expected"], **override)}
                                    for s in scenarios])


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_fixture_is_not_one_this_repo_wrote() -> None:
    """Hand-authored comparanda: a scale preset this repo does not ship, and no version stamps."""
    frame = json.loads((ROOT / "docs/evaluation/audit-existing/foreign/frame.json").read_text())
    from rubricator.tools.analysis import SCALE_PRESETS

    assert {c["defaultMeasurement"]["scale"] for c in frame["criteria"]} - set(SCALE_PRESETS)
    assert "criteriaVersion" not in frame


def test_the_grader_reads_every_label_the_prompt_teaches() -> None:
    found = re.search(r"```\n(Uncited or thinly cited:.*?)```", prompts()["audit-existing"].body, re.S).group(1)
    assert [line.split(":")[0] for line in found.strip().splitlines()] == list(grader.LINES)


def test_a_faithful_reply_grades_full_marks() -> None:
    row = _graded()
    assert all(hits == total for hits, total in row.values()), row


@pytest.mark.parametrize("prose", [
    'CALL measures_mark_missing({"analysis_id": "seed-library", "code": "not-evidenced"})',
    'CALL frame_set({"analysis_id": "seed-library", "ambiguities": []})',
])
def test_a_write_is_caught(prose) -> None:
    hits, total = _graded(prose=prose)["wrote nothing"]
    assert hits == 0 and total > 0


def test_an_overlap_read_off_the_correlations_is_caught() -> None:
    row = _graded(overlap=[["yearly-cost", "offline-mode"]])
    assert row["overlap right"][0] == 0
