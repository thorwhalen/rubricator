"""Structured criterion definitions (#27), as comparanda v1 shipped them.

`definition` carries objective, question, evidenceRule, missingRules [{when,
code}] and exclusions. Anchors stay on the measurement. A missing rule must name
a code someone defines (`missing-rule-code-defined`), and an anchor must sit on a
level the scale can take.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.merge import merge_contributions
from rubricator.rules import honesty_problems
from rubricator.tools.analysis import DEFINITION_FIELDS, analysis_open, criteria_set

ANCHORS = {"1": "no commitment", "3": "undated commitment", "5": "dated commitment"}
FULL = {
    "objective": "keep the service running after adoption",
    "question": "How firm is the vendor's published support commitment?",
    "evidenceRule": "only the vendor's own published terms count",
    "missingRules": [{"when": "the terms are behind a sales call", "code": "not-evidenced"}],
    "exclusions": ["third-party support contracts"],
}


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={})
    analysis_open(rt.store, analysis_id="a", question="which?")
    return rt


def _set(rt, **criterion):
    return criteria_set(rt.store, analysis_id="a", criteria=[
        {"id": "c", "label": "Support", "anchors": ANCHORS, **criterion}])


def test_a_full_definition_is_emitted_and_validates(runtime) -> None:
    result = _set(runtime, definition=FULL)
    assert result["definitionGaps"] == {}
    doc = merge_contributions(runtime.store.frame("a"), [])
    assert doc["criteria"][0]["definition"] == FULL
    assert runtime.schema.validate(doc).ok
    assert honesty_problems(doc) == []


def test_missing_fields_are_reported_not_refused(runtime) -> None:
    """ADR-0024: an under-defined criterion is unfinished, not dishonest."""
    result = _set(runtime, definition={"question": "How firm?"})
    assert result["definitionGaps"] == {
        "c": [f for f in DEFINITION_FIELDS if f != "question"]}
    assert set(_set(runtime)["definitionGaps"]["c"]) == set(DEFINITION_FIELDS)


def test_a_missing_rule_naming_an_undefined_code_is_refused(runtime) -> None:
    bad = {**FULL, "missingRules": [{"when": "paywalled", "code": "paywalled"}]}
    with pytest.raises(ValueError, match='"paywalled", which is neither a core code'):
        _set(runtime, definition=bad)


def test_a_code_declared_on_the_criterion_satisfies_its_rule(runtime) -> None:
    rules = {**FULL, "missingRules": [{"when": "paywalled", "code": "paywalled"}]}
    decl = [{"id": "paywalled", "broader": "not-evidenced", "means": "behind a paywall"}]
    _set(runtime, definition=rules, missingCodes=decl)
    doc = merge_contributions(runtime.store.frame("a"), [])
    assert honesty_problems(doc) == []
    assert runtime.schema.validate(doc).ok


def test_the_mirrored_rule_catches_a_document_built_elsewhere() -> None:
    doc = {"criteria": [{"id": "c", "label": "C",
                         "definition": {"missingRules": [{"when": "w", "code": "ghost"}]}}]}
    assert [p.rule_id for p in honesty_problems(doc)] == ["missing-rule-code-defined"]


@pytest.mark.parametrize("bad, match", [
    ({"anchors": "x"}, "unknown field"),
    ({"missingRule": "x"}, "unknown field"),
    ({"exclusions": "none"}, "list of strings"),
    ({"missingRules": [{"when": "w"}]}, "exactly"),
    ({"question": 3}, "must be a string"),
])
def test_the_definition_shape_is_closed(runtime, bad, match) -> None:
    with pytest.raises(ValueError, match=match):
        _set(runtime, definition=bad)


def test_an_anchor_on_a_level_the_scale_cannot_take_is_refused(runtime) -> None:
    with pytest.raises(ValueError, match="cannot take"):
        _set(runtime, anchors={**ANCHORS, "7": "beyond the scale"})
