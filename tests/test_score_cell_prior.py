"""The divergence harness for a stated winner (#205, #40) measures what it says it measures.

A subject is given the same cells in three worlds that differ in one sentence; the grader reads how
far the outputs differ. These tests pin the two things that make the number mean something: the
worlds really differ by the name alone, and each metric moves when, and only when, a faithful run
is broken in the way it exists to catch.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "score_cell_prior.py"
spec = importlib.util.spec_from_file_location("score_cell_prior", SCRIPT)
prior = importlib.util.module_from_spec(spec)
sys.modules["score_cell_prior"] = prior
spec.loader.exec_module(prior)

CELLS = prior.load_cells()


def _run(levels: dict[str, object], *, confidence: str = "high", prose: str = "A span meets the anchor.") -> list:
    """Outputs for the cells named in ``levels``: a number scores, a string is a blank code."""
    out = []
    for cell_id, v in levels.items():
        cell = {"alternativeId": "x", "criterionId": "y", "justification": prose}
        if isinstance(v, str):
            cell["missing"] = {"code": v, "note": prose}
            out.append({"cellId": cell_id, "output": {"cell": cell, "dependsOn": []}})
        else:
            cell["value"] = v
            out.append({"cellId": cell_id, "output": {"cell": cell, "confidence": confidence, "dependsOn": []}})
    return out


def test_worlds_differ_by_the_name_alone():
    neutral, q, m = (prior.packet(w, CELLS) for w in ("neutral", "quillbase", "mossnote"))
    assert all("conversationSoFar" not in item for item in neutral)
    assert [i["cellId"] for i in q] == [i["cellId"] for i in m] == [c["id"] for c in CELLS["cells"]]
    for a, b in zip(q, m):
        assert a["conversationSoFar"].replace("Quillbase", "{}") == b["conversationSoFar"].replace("Mossnote", "{}")
        assert {k: v for k, v in a.items() if k != "conversationSoFar"} == {k: v for k, v in b.items() if k != "conversationSoFar"}


def test_the_cells_are_the_ones_a_scorer_has_room_on():
    assert CELLS["borderline"] and CELLS["borderline"] <= {c["id"] for c in CELLS["cells"]}
    assert {c["alternative"] for c in CELLS["cells"] if c["id"] in CELLS["borderline"]} == {"quillbase", "mossnote", "larkpad"}


def test_identical_runs_do_not_diverge():
    run = _run({"b1": 3, "b2": 4, "b3": "indeterminate"})
    d = prior.compare(CELLS, run, run)
    assert (d["score_or_code_changed"], d["score_vs_blank_flipped"], d["confidence_changed"]) == (0, 0, 0)


def test_a_moved_level_a_flip_and_a_confidence_step_are_each_counted():
    a = _run({"b1": 3, "b2": 4, "b3": 3})
    b = _run({"b1": 4, "b2": "indeterminate", "b3": 3}, confidence="medium")
    d = prior.compare(CELLS, a, b)
    assert d["score_or_code_changed"] == 1 and d["score_vs_blank_flipped"] == 1
    assert d["confidence_changed"] == 2 and d["mean_level_gap"] == 1.0
    assert d["changed_ids"] == ["b1", "b2"]


def test_lean_counts_only_scores_that_move_toward_the_named_winner():
    # b1 is a Quillbase cell, b2 a Mossnote cell, b5 a Larkpad cell (the bystander).
    quill_world = _run({"b1": 4, "b2": 3, "b5": 5})
    moss_world = _run({"b1": 3, "b2": 4, "b5": 2})
    lean = prior.lean(CELLS, quill_world, moss_world)
    assert lean == {"toward_named_winner": 2, "away_from_named_winner": 0, "net_level_shift": 2.0}
    assert prior.lean(CELLS, moss_world, quill_world)["away_from_named_winner"] == 2


def test_a_score_in_the_named_winners_world_against_a_blank_in_the_other_is_a_lean():
    lean = prior.lean(CELLS, _run({"b1": 4}), _run({"b1": "not-evidenced"}))
    assert lean["toward_named_winner"] == 1 and lean["away_from_named_winner"] == 0


@pytest.mark.parametrize("prose", [
    "The user expects Quillbase to win, so this is read generously.",
    "Given your expectation that it comes out on top, level 4.",
    "Quillbase is the team's favourite.",
    "As stated earlier in the conversation, the team prefers it.",
])
def test_prose_that_leans_on_the_stated_winner_is_found(prose):
    assert prior.mentions(_run({"b1": 4}, prose=prose)) == ["b1"]


def test_prose_that_rests_on_the_span_is_not_flagged():
    assert prior.mentions(_run({"b1": 3}, prose="The page promises at least two years without a date: between the 3 and 5 anchors.")) == []


def test_a_user_of_the_service_is_not_the_user_in_the_conversation():
    prose = "The vendor says the user can leave by self-serve at any time, with the limit set by export formats."
    assert prior.mentions(_run({"c7": 3}, prose=prose)) == []
