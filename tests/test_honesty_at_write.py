"""``measures_write`` refuses the six cells the honesty rules forbid, before the bytes land (#171).

Each was accepted until the adversarial review of score-cell v2 wrote it. A
prompt teaching against them is not a boundary: the connector's model and any
direct caller reach the verb without it. So each row is refused through the
frozen surface (``bind``) and through the verb itself, the refusal names the
path, the fix and the rule with the decision it comes from (ADR-0024), and the
store holds nothing afterwards.

The neighbours of each row -- the honest cell one edit away -- are written, so a
rule that over-reaches fails here too.
"""

from __future__ import annotations

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.rules import EXTERNAL_SOURCE_TYPES, RULE_SOURCES
from rubricator.schema.vocabulary import vocabulary
from rubricator.surface import bind
from rubricator.tools.analysis import measures_write

MOMENT = "2026-10-13T12:00:00Z"
AUTHOR = {"id": "scorer", "displayName": "Scorer", "kind": "agent"}
ANCHORS = [{"level": "1", "text": "none"}, {"level": "3", "text": "some"}, {"level": "5", "text": "all"}]
QUOTE = [{"type": "TextQuoteSelector", "exact": "support ends in 2029"}]
SPAN = {"id": "e1", "target": "doc:policy", "sourceType": "primary", "stance": "supports",
        "selectors": QUOTE}
INFERENCE = {"id": "e2", "target": "doc:policy", "sourceType": "agent-inference",
             "stance": "supports", "excerpt": "four years from the 2025 release"}
SCORE = {"alternativeId": "k1", "criterionId": "support", "value": 5,
         "justification": "the policy states a dated end of support"}


def _blank(code, **extra):
    return {"alternativeId": "k1", "criterionId": "support",
            "missing": {"code": code, "note": "the policy page was read"}, **extra}


#: The six rows of #171: (the cell, the rule it breaks, where the refusal points).
DISHONEST = {
    "an inference with no derivedFrom": (
        {**SCORE, "evidence": [SPAN, INFERENCE]}, "inference-names-its-sources",
        ".evidence[e2].derivedFrom"),
    "a summary with no derivedFrom": (
        {**SCORE, "evidence": [SPAN, {**INFERENCE, "sourceType": "agent-summary"}]},
        "inference-names-its-sources", ".evidence[e2].derivedFrom"),
    "a score with no evidence": (SCORE, "value-cites-evidence", ".evidence"),
    "a score with empty evidence": ({**SCORE, "evidence": []}, "value-cites-evidence", ".evidence"),
    "not-assessed carrying evidence": (
        _blank("not-assessed", evidence=[SPAN]), "unsearched-blank-cites-nothing", ".evidence"),
    "deferred carrying evidence": (
        _blank("deferred", evidence=[SPAN]), "unsearched-blank-cites-nothing", ".evidence"),
    "a blank with no note": (
        {"alternativeId": "k1", "criterionId": "support", "missing": {"code": "not-evidenced"}},
        "blank-has-a-note", ".missing.note"),
    "a blank with a whitespace note": (
        {"alternativeId": "k1", "criterionId": "support",
         "missing": {"code": "not-evidenced", "note": "  "}},
        "blank-has-a-note", ".missing.note"),
    "a blank with a zero-width note": (
        {"alternativeId": "k1", "criterionId": "support",
         "missing": {"code": "not-evidenced", "note": "\u200b"}},
        "blank-has-a-note", ".missing.note"),
    "derivedFrom naming a blank id": (
        {**SCORE, "evidence": [SPAN, {**INFERENCE, "derivedFrom": [""]}]},
        "derived-from-resolves", ".evidence[e2].derivedFrom"),
    "derivedFrom naming nothing": (
        {**SCORE, "evidence": [SPAN, {**INFERENCE, "derivedFrom": ["ghost"]}]},
        "derived-from-resolves", ".evidence[e2].derivedFrom"),
    "an inference derived from itself": (
        {**SCORE, "evidence": [SPAN, {**INFERENCE, "derivedFrom": ["e2"]}]},
        "derived-from-resolves", ".evidence[e2].derivedFrom"),
    "two inferences derived from each other": (
        {**SCORE, "evidence": [SPAN, {**INFERENCE, "derivedFrom": ["e3"]},
                               {**INFERENCE, "id": "e3", "derivedFrom": ["e2"]}]},
        "derived-from-acyclic", ".evidence[e2].derivedFrom"),
    "a span whose only locator is a blank excerpt": (
        {**SCORE, "evidence": [{**SPAN, "selectors": [], "excerpt": "   "}]},
        "cite-a-span", ".evidence[e1]"),
    "a span with neither stance nor selectors": (
        {**SCORE, "evidence": [{"id": "e1", "target": "doc:policy", "sourceType": "primary"}]},
        "cite-a-span", ".evidence[e1]"),
    "two spans with one id": (
        {**SCORE, "evidence": [SPAN, {**SPAN, "selectors": [{**QUOTE[0], "exact": "2029"}]}]},
        "unique-evidence-ids", ".evidence[e1]"),
}

#: The honest cell one edit away from each row: none of these may be refused.
HONEST = {
    "an inference naming its sources": {**SCORE, "evidence": [SPAN, {**INFERENCE, "derivedFrom": ["e1"]}]},
    "an inference drawn through another": {**SCORE, "evidence": [
        SPAN, {**INFERENCE, "derivedFrom": ["e1"]}, {**INFERENCE, "id": "e3", "derivedFrom": ["e2"]}]},
    "a cited score": {**SCORE, "evidence": [SPAN]},
    "an excerpt-only span": {**SCORE, "evidence": [{**SPAN, "selectors": [], "excerpt": "until 2029"}]},
    "a searched blank citing what it read": _blank("indeterminate", evidence=[SPAN]),
    "a withheld blank citing what it read": _blank("withheld", evidence=[SPAN]),
    "an unsearched blank with a note": _blank("not-assessed"),
}


def _runtime():
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k1", "label": "Kettle one"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "support", "label": "Vendor support", "anchors": ANCHORS}])
    return runtime, verbs


def _through_bind(runtime, verbs, cell):
    return verbs["measures_write"](analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                                   cells=[cell])


def _through_the_verb(runtime, verbs, cell):
    return measures_write(runtime.store, analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                          at=MOMENT, cells=[cell])


ROUTES = {"bind": _through_bind, "verb": _through_the_verb}


@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("row", list(DISHONEST.values()), ids=list(DISHONEST))
def test_each_dishonest_cell_is_refused_with_its_rule_and_nothing_is_written(route, row) -> None:
    cell, rule_id, where = row
    runtime, verbs = _runtime()
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError) as refused:
        route(runtime, verbs, cell)
    message = str(refused.value)
    assert message.startswith("refused, nothing was written")
    assert f"[rule {rule_id}; {RULE_SOURCES[rule_id]}]" in message
    assert f"cells[k1/support/score].assertions[scorer:k1-support-score]{where}:" in message
    assert "Fix: " in message
    assert dict(runtime.store.blobs) == before


@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("cell", list(HONEST.values()), ids=list(HONEST))
def test_the_honest_neighbour_of_each_row_is_written(route, cell) -> None:
    runtime, verbs = _runtime()
    assert route(runtime, verbs, cell)["written"] == 1


def test_two_contributors_may_both_call_a_span_e1() -> None:
    """Evidence ids are unique per assertion: colleagues citing one passage collide by name only."""
    runtime, verbs = _runtime()
    _through_bind(runtime, verbs, {**SCORE, "evidence": [SPAN]})
    written = verbs["measures_write"](
        analysis_id="a1", contributor_id="ben", author={**AUTHOR, "id": "ben"},
        cells=[{**SCORE, "evidence": [SPAN], "independence": "independent"}])
    assert written["written"] == 1


def test_a_declared_code_refining_an_unsearched_one_is_held_to_the_same_rule() -> None:
    """Found by the ``terminal`` fact, never the spelling: an extension inherits it."""
    runtime, verbs = _runtime()
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "support", "label": "Vendor support", "anchors": ANCHORS,
         "missingCodes": [{"id": "queued", "broader": "deferred", "means": "next sprint"}]}])
    with pytest.raises(ValueError, match=r"\[rule unsearched-blank-cites-nothing"):
        _through_bind(runtime, verbs, _blank("queued", evidence=[SPAN]))


def test_the_external_source_types_are_members_of_the_closed_enum() -> None:
    """The one fact the manifest does not publish is held to the enum it classifies."""
    members = set(vocabulary().closed_enums["sourceType"])
    assert EXTERNAL_SOURCE_TYPES < members
    assert members - EXTERNAL_SOURCE_TYPES == {"agent-summary", "agent-inference"}


def test_every_new_rule_cites_where_it_was_decided() -> None:
    assert {rule for _cell, rule, _where in DISHONEST.values()} <= set(RULE_SOURCES)
