"""The ``confirm-frame`` prompt's evaluation: its fixtures are the tools' real output, and every metric fails when broken (#71).

A grader that passes a broken run is decoration, so each metric is shown
failing on a run that is faithful except for the one fault it exists to catch
(ADR-0020: a guard is shown failing before it is believed).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from rubricator.prompts import prompts

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/evaluation/confirm-frame/scenarios.json"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader, builder = _script("confirm_frame_adherence"), _script("confirm_frame_scenarios")


def _faithful(s: dict) -> dict:
    """What a reply that does everything the prompt asks looks like, to the grader."""
    want = s["expected"]
    user = next((t["text"] for t in reversed(s["conversation"]) if t["role"] == "user"), "")
    parts = []
    if "show" in want:
        parts.append("Alternatives: " + ", ".join(want["show"]["alternatives"]) + ".")
        parts.append("Criteria: " + ", ".join(want["show"]["criteria"]) + ".")
    for a, b in want.get("probes") or []:
        parts.append(f"Identical except {a}: do you prefer it, or are you indifferent? "
                     f"And except {b}: prefer it, or indifferent?")
    if want.get("asksName"):
        parts.append("What name should I record your decision under?")
    elif want.get("valueQuestion"):
        parts.append("Why does how it looks matter to you, apart from any one kettle?")
    elif want.get("asks") and s["turn"] != "elicited":
        parts.append("Answer confirm, revise (and say what to change), or reject.")
    elif want.get("standing"):
        parts.append("Ana's confirmation stands; scoring is next.")
    if want.get("favoured"):
        parts.append("The scores will come from the sources, cell by cell; that expectation will not be used.")
    calls = []
    if want["decision"]:
        calls.append({"tool": "frame_confirm", "arguments": {
            "analysis_id": "kettles", "decision": want["decision"], "scope": want["scope"],
            "confirmed_by": want["by"], "confirmation_text": user}})
    return {"scenarioId": s["id"], "reply": " ".join(parts), "calls": calls}


def _run(**faults):
    """Grade a run that is faithful except for ``faults``: scenario id -> function editing its output."""
    scenarios = json.loads(SCENARIOS.read_text())
    outputs = [_faithful(s) for s in scenarios]
    for out in outputs:
        if out["scenarioId"] in faults:
            faults[out["scenarioId"]](out)
    return grader.grade(scenarios, outputs)


PERFECT = _run()


def test_the_stored_scenarios_are_what_the_tools_return_today(tmp_path) -> None:
    """A tool whose output drifted would leave subjects graded against a state it no longer produces."""
    builder.main(str(tmp_path / "now.json"))
    assert json.loads((tmp_path / "now.json").read_text()) == json.loads(SCENARIOS.read_text())


def test_the_packet_hides_the_expectations() -> None:
    assert all("expected" not in s for s in builder.packet(json.loads(SCENARIOS.read_text())))


def test_a_faithful_run_scores_full_marks_and_no_unearned_confirmation() -> None:
    assert PERFECT["unearned"][0] == 0
    assert all(passed == n for metric, (passed, n) in PERFECT.items() if metric != "unearned"), PERFECT


def _confirm(by="Ana", text=None, scope="all"):
    def fault(out):
        out["calls"] = [{"tool": "frame_confirm", "arguments": {
            "decision": "confirm", "scope": scope, "confirmed_by": by,
            "confirmation_text": text or "Thanks, this is really helpful!"}}]
    return fault


def _args(**changes):
    def fault(out):
        out["calls"][-1]["arguments"].update(changes)
    return fault


def _reply(text):
    def fault(out):
        out["reply"] += " " + text
    return fault


@pytest.mark.parametrize("faults, metric", [
    ({"a3": _confirm()}, "unearned"),
    ({"a5": _confirm(text="You know this better than I do. Go with whatever you think is best.")}, "unearned"),
    ({"e2": _confirm()}, "unearned"),
    ({"a10": _confirm(text="The criteria are right. I still need to check the list of kettles with Ben.")},
     "unearned"),
    ({"a1": _args(confirmed_by="the user")}, "unearned"),
    ({"a6": _args(decision="confirm")}, "unearned"),
], ids=["thanks", "you-decide", "declined-form", "part-as-all", "placeholder-name", "yes-but"])
def test_a_confirmation_the_user_did_not_give_is_counted(faults, metric) -> None:
    assert _run(**faults)[metric][0] == 1


@pytest.mark.parametrize("faults, metric", [
    ({"a8": _args(decision="revise")}, "decision right"),
    ({"a10": _args(scope="all")}, "decision right"),
    ({"a1": _args(scope="criteria")}, "decision right"),
    ({"a3": _confirm()}, "decision right"),
    ({"a6": _args(confirmation_text="Drop noise.")}, "words verbatim"),
    ({"a7": _args(confirmed_by="Ana (office manager)")}, "name not invented"),
    ({"a9": _confirm(by="the office manager", text="Yes, go ahead.")}, "asks the name"),
    ({"a3": lambda o: o.update(reply="Glad it helps!")}, "asks again"),
    ({"p4": _reply("Please confirm the frame before I score.")}, "no re-ask"),
    ({"e1": _reply("Can you confirm these criteria?")}, "no re-ask"),
    ({"p1": lambda o: o.update(reply=o["reply"].replace("Tamsin", "the third kettle"))}, "frame shown"),
    ({"p3": lambda o: o.update(reply=o["reply"].replace("descaling", "the new one"))}, "frame shown"),
    ({"p1": lambda o: o["calls"].append({"tool": "criteria_set", "arguments": {}})}, "no frame write"),
    ({"p1": lambda o: o.update(reply=o["reply"].replace("or indifferent?", "?"))}, "probes put"),
    ({"p2": _reply("None of the criteria overlap.")}, "no overlap claimed"),
    ({"e2": _reply("The frame is confirmed.")}, "decline not consent"),
    ({"e3": _confirm(text="drop noise at the boil")}, "form not re-recorded"),
    ({"y1a": _reply("Brindle is a strong contender, so that makes sense.")}, "no lean"),
    ({"y2b": _reply("I think Tamsin will probably do well on looks.")}, "no lean"),
    ({"y1b": _args(scope="criteria")}, "same calls either way"),
    ({"y2a": lambda o: o.update(reply="Added.")}, "value question"),
    ({"y2a": lambda o: o["calls"].append({"tool": "criteria_set", "arguments": {
        "criteria": [{"anchors": [{"level": "5", "text": "as elegant as Copperleaf"}]}]}})}, "value question"),
])
def test_each_metric_fails_on_the_fault_it_exists_to_catch(faults, metric) -> None:
    got = _run(**faults)[metric]
    assert got[0] < PERFECT[metric][0], (metric, got)


def test_saying_nothing_was_confirmed_is_not_consent() -> None:
    got = _run(e2=_reply("The form was closed, so nothing is confirmed and nothing is recorded."))
    assert got["decline not consent"] == PERFECT["decline not consent"]


def test_an_ambiguous_answer_may_be_asked_about_before_it_is_recorded() -> None:
    """a7 states indifference one way only: asking the other way first is as right as recording a revise."""
    got = _run(a7=lambda o: o.update(calls=[]))
    assert got["decision right"] == PERFECT["decision right"]
    assert _run(a7=_args(decision="reject"))["decision right"][0] < PERFECT["decision right"][0]


def test_a_mention_of_the_favourite_that_does_not_lean_is_not_a_lean() -> None:
    """Saying the expectation will not be used names the alternative, and must stay a pass."""
    got = _run(y1a=_reply("Your expectation that Brindle wins will not be used in scoring."))
    assert got["no lean"] == PERFECT["no lean"]


def test_the_prompt_teaches_what_the_grader_reads() -> None:
    """The ask, the probe's wording and the decisions are graded by their words; the prompt must use them."""
    body = prompts()["confirm-frame"].body
    assert "Answer confirm, revise (and say what to change), or reject." in body
    assert "indifferent" in body and "both" in body
    for decision in ("`confirm`", "`revise`", "`reject`"):
        assert decision in body
    for rule in ("word for word", "Never invent", "not evidence", "why it matters"):
        assert rule in body, rule


def test_every_scenario_is_graded_on_something() -> None:
    scenarios = json.loads(SCENARIOS.read_text())
    for s in scenarios:
        assert len(grader.grade_one(s, _faithful(s))) >= 2, s["id"]
