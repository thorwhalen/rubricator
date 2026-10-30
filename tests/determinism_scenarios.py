"""Computations the determinism helper replays: every exposed verb, and one deliberate leak (#48).

Not a test module (no ``test_`` prefix): ``test_tool_reproducibility.py`` runs
these through :func:`determinism_helper.reproducible`, which imports them by
name in fresh interpreters. Fixtures are invented (comparanda ADR-0033).
"""

from __future__ import annotations

from typing import Any

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ids import sequential_ids
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "over six minutes"}, {"level": "3", "text": "four to six"},
           {"level": "5", "text": "under four minutes"}]
K2 = ("The Brightwater K2 kettle boils one litre in under four minutes. Boil-dry protection "
      "cuts the power when it runs empty.")
L5 = ("The Lumen L5 kettle takes about five minutes a litre. It has no boil-dry protection; "
      "the manual says never to run it empty.")
ANA = {"id": "ana", "displayName": "Ana Ruiz", "kind": "human"}


def every_verb() -> dict[str, Any]:
    """One analysis end to end through the bound surface, each verb's result kept by name.

    The stored bytes are kept too, under ``"store"``: a verb whose *return*
    is reproducible but whose *writes* are not would pass a return-only check.
    """
    # Both clocks fixed: the retention clock dates every write's touched stamp, and
    # left on the wall clock it makes two runs a second apart differ in bytes.
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT), retention_clock=fixed_clock(MOMENT),
                            new_id=sequential_ids("a"))
    v = bind(runtime)
    out: dict[str, Any] = {}
    out["analysis_open"] = v["analysis_open"](question="Which kettle for a small office?")
    aid = out["analysis_open"]["analysisId"]
    out["corpus_add"] = v["corpus_add"](analysis_id=aid, sources=[
        {"id": "k2", "title": "K2 sheet", "text": K2, "agentProduced": False},
        {"id": "l5", "title": "L5 manual", "text": L5, "agentProduced": False},
    ], chunking={"windowChars": 60, "overlapChars": 0})
    out["corpus_search"] = v["corpus_search"](analysis_id=aid, query="boil-dry protection empty")
    out["frame_set"] = v["frame_set"](
        analysis_id=aid, ambiguities=["small office: how many cups a day?"],
        decision="buy one kettle", decider="the office manager")
    out["alternatives_set"] = v["alternatives_set"](analysis_id=aid, alternatives=[
        {"id": "l5", "label": "Lumen L5"}, {"id": "k2", "label": "Brightwater K2"},
        {"id": "k2-kettle", "label": "The Brightwater K2 kettle"}])
    out["criteria_set"] = v["criteria_set"](analysis_id=aid, criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS,
         "provenance": {"origin": "user-stated", "rationale": "the office manager asked for it by name"}},
        {"id": "safety", "label": "Boil-dry safety", "anchors": ANCHORS,
         "provenance": {"origin": "agent-proposed"}}])
    # The messy part of the frame: criteria proposed and removed, one merged into a live one.
    out["criteria_reject"] = v["criteria_reject"](analysis_id=aid, rejected=[
        {"label": "Brand prestige", "code": "means-objective", "reason": "it serves reliability, which safety measures"},
        {"label": "Boil time", "code": "merged-into", "reason": "the same quantity as boil speed", "mergedIntoId": "speed"},
        {"label": "Colour", "code": "user-rejected", "reason": "the office manager does not care"}])
    v["frame_confirm"](analysis_id=aid)
    out["frame_confirm"] = v["frame_confirm"](
        analysis_id=aid, decision="confirm", scope="all", confirmed_by="Ana Ruiz",
        confirmation_text="Yes, those three and those two criteria.")
    out["plan_traversal"] = v["plan_traversal"](
        alternatives=["l5", "k2", "k2-kettle"], criteria=["speed", "safety"], seed="office")
    out["measures_write"] = v["measures_write"](
        analysis_id=aid, contributor_id="ana", author=ANA, cells=[{
            "alternativeId": "k2", "criterionId": "speed", "value": 5,
            "justification": "the sheet states under four minutes a litre",
            "evidence": [{"id": "e1", "target": "rendition:k2", "sourceType": "primary",
                          "selectors": [{"type": "TextQuoteSelector",
                                         "exact": "boils one litre in under four minutes"}]}],
        }])
    out["measures_mark_missing"] = v["measures_mark_missing"](
        analysis_id=aid, contributor_id="ana", author=ANA, code="not-evidenced",
        note="neither document states a boil time for this row",
        criterion_ids=["speed"], alternative_ids=["l5", "k2-kettle"])
    out["report_completeness"] = v["report_completeness"](analysis_id=aid)
    out["aggregate_assertions"] = v["aggregate_assertions"](analysis_id=aid)
    out["disclose_variance"] = v["disclose_variance"](analysis_id=aid)
    out["report_weaknesses"] = v["report_weaknesses"](analysis_id=aid, budget=3)
    out["stability_report"] = v["stability_report"](analysis_id=aid)
    out["analysis_get"] = {view: v["analysis_get"](analysis_id=aid, view=view)
                           for view in ("summary", "frame", "criteria", "outstanding", "full")}
    out["check_citations"] = v["check_citations"](citations=[
        {"quote": "boils one litre in under four minutes", "source": K2},
        {"quote": "boils two litres", "source": K2}])
    out["prompts_list"] = v["prompts_list"]()
    out["prompts_get"] = v["prompts_get"](prompt_id="score-cell")
    out["store"] = {k: runtime.store.blobs[k].decode("utf-8") for k in sorted(runtime.store.blobs)}
    return out


def a_set_order_leak() -> list[str]:
    """The planted failure the helper must catch: a set of strings iterated into output."""
    return list({"alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"})
