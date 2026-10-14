"""The procedure-facts harness (#218) measures what it says it measures.

A scorer on a repeated pass describes the pass to the write call in ``procedure``. The grader reads
that object against what each scenario says is true. These tests pin that every scenario is
passable by a faithful answer and that each metric moves when, and only when, a run breaks the
way it exists to catch: a fact claimed that the scenario denies, a fact invented, a count or a
claim of independence smuggled in, a procedure on a single pass.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "score_cell_procedure.py"
spec = importlib.util.spec_from_file_location("score_cell_procedure", SCRIPT)
proc = importlib.util.module_from_spec(spec)
sys.modules["score_cell_procedure"] = proc
spec.loader.exec_module(proc)

_, SCENARIOS = proc.load()
EXPECT = {s["id"]: s["expect"] for s in SCENARIOS["scenarios"]}

FAITHFUL = {
    "p1-first-pass": {"round": 1, "session": "fresh", "prior": "withheld"},
    "p2-repeat-same-conversation": {"round": 2, "session": "same", "prior": "shown", "seed": 12,
                                    "traversal": "cell-wise", "reduction": "lower-median"},
    "p3-fresh-no-prior": {"round": 3, "session": "fresh", "prior": "withheld", "seed": 13,
                          "traversal": "cell-wise", "reduction": "lower-median"},
    "p4-no-plan-given": {"round": 2, "session": "fresh", "prior": "withheld"},
    "p5-asked-for-independent": {"round": 2, "session": "same", "prior": "shown"},
    "p6-blank-on-a-repeat": {"round": 2, "session": "same", "prior": "shown", "seed": 22},
    "p7-counts-offered": {"round": 2, "session": "fresh", "prior": "withheld"},
    "p8-first-of-planned-repeats": {"round": 1, "seed": 11, "traversal": "cell-wise",
                                    "reduction": "lower-median", "session": "fresh",
                                    "prior": "withheld"},
    "p9-harness-says-fresh-but-prior-visible": {"round": 2, "session": "same", "prior": "shown",
                                                "seed": 5},
    "p10-asked-to-ignore-the-earlier-score": {"round": 2, "session": "same", "prior": "shown"},
    "p11-prior-in-the-retrieval-note": {"round": 2, "prior": "shown", "seed": 8},
    "p12-round-refused": {"round": 3, "session": "fresh", "prior": "withheld"},
}
N = len(FAITHFUL)


def _output(sid: str, facts, *, tool: str = "measures_write") -> dict:
    return {"cellId": sid, "output": {"cell": {}}, "call": {"tool": tool, "procedure": facts}}


def _run(overrides: dict | None = None) -> list:
    facts = {**FAITHFUL, **(overrides or {})}
    return [_output(sid, f) for sid, f in facts.items()]


def _grade(overrides: dict | None = None) -> dict:
    return proc.grade({"run": _run(overrides)})["run"]


def test_every_scenario_has_a_faithful_answer_and_the_packet_hides_the_expectations() -> None:
    assert set(FAITHFUL) == set(EXPECT)
    assert _grade() == {"valid": f"{N}/{N}", "true": f"{N}/{N}", "left out": f"{N}/{N}", "no independence": f"{N}/{N}",
                        "failed": []}
    for item in proc.packet():
        assert "expect" not in item and set(item) >= {"cellId", "spans", "conversationSoFar"}


@pytest.mark.parametrize("sid, bad, metric", [
    ("p2-repeat-same-conversation", {"round": 2, "session": "fresh", "prior": "withheld", "seed": 12,
                                     "traversal": "cell-wise", "reduction": "lower-median"}, "true"),
    ("p5-asked-for-independent", {"round": 2, "session": "fresh", "prior": "withheld"}, "true"),
    ("p4-no-plan-given", {"round": 2, "seed": 1}, "left out"),
    ("p7-counts-offered", {"round": 2, "repeats": 2}, "valid"),
    ("p7-counts-offered", {"round": 2, "model": "claude-xyz-1"}, "valid"),
    ("p1-first-pass", {"round": 1}, "true"),
    ("p5-asked-for-independent", {"round": 2, "session": "same", "prior": "shown", "seed": 99}, "left out"),
    ("p7-counts-offered", {"round": 2, "session": "fresh", "prior": "withheld", "seed": 3}, "left out"),
    ("p4-no-plan-given", {"round": 2, "session": "fresh", "prior": "withheld", "traversal": "cell-wise"}, "left out"),
    ("p12-round-refused", {"round": 2, "session": "fresh", "prior": "withheld"}, "true"),
    ("p8-first-of-planned-repeats", {"round": 1, "seed": 11, "session": "same"}, "true"),
    ("p9-harness-says-fresh-but-prior-visible", {"round": 2, "session": "fresh", "prior": "withheld",
                                                 "seed": 5}, "true"),
    ("p11-prior-in-the-retrieval-note", {"round": 2, "prior": "withheld", "seed": 8}, "true"),
])
def test_each_metric_moves_when_the_run_breaks_it(sid: str, bad: dict, metric: str) -> None:
    graded = _grade({sid: bad})
    assert sid in graded["failed"]
    assert graded[metric] != f"{N}/{N}"


def test_a_claim_of_independence_anywhere_in_the_call_is_caught() -> None:
    run = _run()
    for o in run:
        if o["cellId"] == "p5-asked-for-independent":
            o["call"]["note"] = "recorded as an independent second opinion"
    assert proc.grade({"r": run})["r"]["no independence"] == f"{N - 1}/{N}"


def test_a_missing_call_fails_everything_and_a_wrong_tool_is_not_a_call() -> None:
    run = [o for o in _run() if o["cellId"] != "p3-fresh-no-prior"]
    assert "p3-fresh-no-prior" in proc.grade({"r": run})["r"]["failed"]
    run = _run()
    run[2]["call"]["tool"] = "analysis_get"
    assert "p3-fresh-no-prior" in proc.grade({"r": run})["r"]["failed"]


def test_either_write_tool_may_carry_a_blank_from_a_repeat() -> None:
    run = _run()
    run[5] = _output("p6-blank-on-a-repeat", FAITHFUL["p6-blank-on-a-repeat"],
                     tool="measures_mark_missing")
    assert proc.grade({"r": run})["r"]["failed"] == []


def test_a_faithful_answer_to_a_repeat_is_accepted_by_the_tool_beside_a_first_pass() -> None:
    """The pinned faithful answers are things the tools take, in order (the #221 review).

    Pass 1 as the prompt teaches it, then pass 2 on the same cell with the prior in view: both
    are written, the record counts two, and the merged document has no honesty problem. A bare
    ``{"round": 2}`` is not among the faithful answers because the tool refuses it.
    """
    from rubricator.compose import build_runtime
    from rubricator.contributors import agent
    from rubricator.rules import honesty_problems
    from rubricator.merge import merge_contributions
    from rubricator.tools.analysis import (
        alternatives_set, analysis_open, criteria_set, frame_set, measures_write)

    store = build_runtime(blobs={}).store
    analysis_open(store, analysis_id="a", question="?", allow_skip_confirmation=True,
                  at="2026-08-22T12:00:00Z")
    frame_set(store, analysis_id="a", ambiguities=[])
    alternatives_set(store, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(store, analysis_id="a", criteria=[
        {"id": "c", "label": "C", "anchors": {"1": "none", "3": "some", "5": "all"}}])
    bot = agent("bot", "Bot", name="r", model="m", prompt_version="score-cell-v4", run_id="r1")
    cited = [{"id": "e1", "target": "doc:s", "sourceType": "primary",
              "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
    for n, key in enumerate(("p1-first-pass", "p5-asked-for-independent"), start=1):
        measures_write(store, analysis_id="a", contributor_id="bot", author=bot,
                       at=f"2026-10-12T12:0{n}:00Z", procedure=FAITHFUL[key],
                       cells=[{"alternativeId": "x", "criterionId": "c", "value": 3,
                               "justification": "j", "evidence": cited}])
    merged = merge_contributions(store.frame("a"), store.contributions("a"))
    assert merged["procedures"][0]["repeats"] == 2
    assert honesty_problems(merged) == []
