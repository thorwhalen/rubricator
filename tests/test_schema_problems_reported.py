"""Declaration problems that reach the document another way are reported (#161).

``criteria_set`` refuses a missing-code declaration the companion would refuse
(#140). An analysis-level list, a hand edit, an import or a frame stored before
#140 never passes through it, so ``report_completeness`` reports the schema
family's problems beside the honesty ones.
"""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS}])
    return rt


def _hand_edit(runtime, change) -> None:
    key = runtime.store.frame_key("a1")
    frame = json.loads(runtime.store.blobs[key])
    change(frame)
    runtime.store.blobs[key] = json.dumps(frame).encode()


def test_a_clean_analysis_reports_none(runtime) -> None:
    report = bind(runtime)["report_completeness"](analysis_id="a1")
    assert report["schemaProblems"] == []
    assert "schemaProblems" not in report["summary"]


@pytest.mark.parametrize("declarations, rule", [
    ([{"id": "not-evidenced", "broader": "withheld", "means": "mine"}], "no-redeclaring-core"),
    ([{"id": "gone", "broader": "withheld", "means": "left out", "structural": True}],
     "structural-refines-not-applicable"),
    ([{"id": "later", "broader": "deferred", "means": "a"},
      {"id": "later", "broader": "deferred", "means": "b"}], "unique-declarations"),
])
def test_an_analysis_level_declaration_the_companion_refuses_is_reported(
    runtime, declarations, rule
) -> None:
    _hand_edit(runtime, lambda f: f.__setitem__("missingCodes", declarations))
    report = bind(runtime)["report_completeness"](analysis_id="a1")
    assert rule in [p["ruleId"] for p in report["schemaProblems"]]
    assert all(p["path"].startswith("missingCodes[") for p in report["schemaProblems"])
    assert "declaration(s) the companion would refuse" in report["summary"]


def test_a_criterion_declaration_stored_before_the_check_is_reported(runtime) -> None:
    def redeclare(frame):
        frame["criteria"][0]["missingCodes"] = [
            {"id": "not-evidenced", "broader": "withheld", "means": "mine"}]
    _hand_edit(runtime, redeclare)
    report = bind(runtime)["report_completeness"](analysis_id="a1")
    assert [(p["path"], p["ruleId"]) for p in report["schemaProblems"]] == [
        ("criteria[0].missingCodes[0]", "no-redeclaring-core")]


def test_the_summary_counts_declarations_not_rule_breaks(runtime) -> None:
    """Review F1 of #168: one declaration breaking two rules is one declaration."""
    _hand_edit(runtime, lambda f: f.__setitem__("missingCodes", [
        {"id": "not-evidenced", "broader": "withheld", "means": "mine", "structural": True}]))
    report = bind(runtime)["report_completeness"](analysis_id="a1")
    assert len(report["schemaProblems"]) == 2
    assert "; 1 declaration(s) the companion would refuse" in report["summary"]
