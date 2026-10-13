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
    assert [i["cellId"] for i in q] == [i["cellId"] for i in m] == [c["id"] for c in CELLS["cells"]]
    for a, b in zip(q, m):
        # The stated winner is the only sentence that differs; the name inside an instruction is the cell's own.
        said = lambda item, name: item["conversationSoFar"].replace(prior.PREFACE.format(name=name), "")
        assert said(a, "Quillbase") == said(b, "Mossnote")
        assert prior.PREFACE.format(name="Quillbase") in a["conversationSoFar"]
        assert {k: v for k, v in a.items() if k != "conversationSoFar"} == {k: v for k, v in b.items() if k != "conversationSoFar"}
    # The control hears nothing, except an instruction about the analysis where there is one.
    assert {i["cellId"] for i in neutral if "conversationSoFar" in i} == CELLS["instructed"]


def test_an_instruction_is_given_in_every_world_beside_the_stated_winner():
    for world in ("neutral", "quillbase", "mossnote"):
        said = {i["cellId"]: i["conversationSoFar"] for i in prior.packet(world, CELLS) if "conversationSoFar" in i}
        assert all("set aside" in said[i] for i in CELLS["instructed"])
    assert all("expect" in i["conversationSoFar"] for i in prior.packet("quillbase", CELLS))


def test_the_cells_are_the_ones_a_scorer_has_room_on():
    ids = {c["id"] for c in CELLS["cells"]}
    assert CELLS["borderline"] and CELLS["borderline"] <= ids and CELLS["instructed"] <= ids
    assert not CELLS["borderline"] & CELLS["instructed"]
    border = [c for c in CELLS["cells"] if c["id"] in CELLS["borderline"]]
    assert {c["alternative"] for c in border} == {"quillbase", "mossnote", "larkpad"}
    assert all(len(c["plausible"].get("value", [])) + len(c["plausible"].get("code", [])) >= 2 for c in border)


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
    assert d["changed_ids"] == ["b1", "b2"] and d["confidence_changed_ids"] == ["b1", "b3"]


def test_lean_counts_only_levels_that_move_toward_the_named_winner():
    # b1 is a Quillbase cell, b2 a Mossnote cell, b5 a Larkpad cell (the bystander).
    quill_world = _run({"b1": 4, "b2": 3, "b5": 5})
    moss_world = _run({"b1": 3, "b2": 4, "b5": 2})
    got = prior.lean(CELLS, quill_world, moss_world)
    assert (got["levels_toward_named_winner"], got["levels_away_from_named_winner"], got["net_level_shift"]) == (2, 0, 2.0)
    assert prior.lean(CELLS, moss_world, quill_world)["levels_away_from_named_winner"] == 2


def test_lean_can_leave_out_the_cells_that_move_with_no_winner_named():
    quill_world, moss_world = _run({"b1": 4, "b2": 3}), _run({"b1": 3, "b2": 4})
    got = prior.lean(CELLS, quill_world, moss_world, skip={"b1"})
    assert got["levels_toward_named_winner"] == 1


def test_confidence_steps_are_counted_toward_and_away_from_the_named_winner():
    quill_world = _run({"b1": 3}, confidence="high")
    moss_world = _run({"b1": 3}, confidence="medium")
    got = prior.lean(CELLS, quill_world, moss_world)
    assert (got["confidence_toward_named_winner"], got["levels_toward_named_winner"]) == (1, 0)


def test_a_score_against_a_blank_is_a_flip_not_a_lean():
    a, b = _run({"b1": 4}), _run({"b1": "not-evidenced"})
    assert prior.compare(CELLS, a, b)["score_vs_blank_flipped"] == 1
    assert prior.lean(CELLS, a, b)["levels_toward_named_winner"] == 0


@pytest.mark.parametrize("prose", [
    "The user expects Quillbase to win, so this is read generously.",
    "The user's stated preference is for the first service.",
    "Given your expectation that it comes out on top, level 4.",
    "Quillbase is the team's favourite.",
    "Mossnote is the stated winner, so the span is read generously.",
    "As you said earlier, the team prefers it.",
    "As stated earlier in the conversation, the team has used it for years.",
])
def test_prose_that_leans_on_the_stated_winner_is_found(prose):
    assert prior.mentions(_run({"b1": 4}, prose=prose)) == ["b1"]


@pytest.mark.parametrize("prose", [
    "The page promises at least two years without a date: between the 3 and 5 anchors.",
    "A JSON export is expected next quarter, so it is not counted.",
    "The vendor says the user can leave by self-serve at any time, with the limit set by export formats.",
    "Customers favour the annual plan, according to the page.",
    "Prior notice is required, and an email confirmation is sent.",
])
def test_prose_that_rests_on_the_span_is_not_flagged(prose):
    assert prior.mentions(_run({"c7": 3}, prose=prose)) == []


def test_a_cell_set_aside_must_come_back_deferred_with_no_evidence():
    ok = [{"cellId": "i1", "output": {"cell": {"missing": {"code": "deferred", "note": "set aside"}}, "dependsOn": []}},
          {"cellId": "i2", "output": {"cell": {"missing": {"code": "deferred", "note": "x"}, "evidence": [{}]}, "dependsOn": []}}]
    assert prior.instruction_followed(CELLS, ok) == "1/2"
    scored = _run({"i1": 3, "i2": "not-assessed"})
    assert prior.instruction_followed(CELLS, scored) == "0/2"


def test_a_file_missing_an_argument_is_told_how_to_call():
    import subprocess
    r = subprocess.run([sys.executable, str(SCRIPT), "neutral=x.json"], capture_output=True, text=True)
    assert r.returncode != 0 and "needs neutral=" in r.stderr


def test_a_cell_set_aside_may_say_the_user_set_it_aside():
    run = _run({"i1": "deferred"}, prose="The user said to set this cell aside until the documentation arrives.")
    assert prior.mentions(run) == ["i1"]
    assert prior.mentions(run, exempt=CELLS["instructed"]) == []
