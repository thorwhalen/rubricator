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

import re
from pathlib import Path

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.rules import EXTERNAL_SOURCE_TYPES, RULE_SOURCES, honesty_problems
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
#: An inference that names its source, so only the rule under test can refuse it.
DRAWN = {**INFERENCE, "derivedFrom": ["e1"]}
CHECK = {"status": "exact", "checkedAt": MOMENT, "checkerVersion": "quote-check/1"}
UNJUSTIFIED = {k: v for k, v in SCORE.items() if k != "justification"}


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
    # #177: the four comparanda rules #171 left out.
    "a score supported only by an inference": (
        {**SCORE, "evidence": [{**SPAN, "stance": "context"}, DRAWN]},
        "external-support-required", ".evidence"),
    "a score supported only by a summary": (
        {**SCORE, "evidence": [{**SPAN, "stance": "qualifies"},
                               {**DRAWN, "sourceType": "agent-summary"}]},
        "external-support-required", ".evidence"),
    "a blank supported only by an inference": (
        _blank("indeterminate", evidence=[{**SPAN, "stance": "contradicts"}, DRAWN]),
        "external-support-required", ".evidence"),
    "an inference whose stance defaults to supports": (
        {**SCORE, "evidence": [{**SPAN, "stance": "context"},
                               {k: v for k, v in DRAWN.items() if k != "stance"}]},
        "external-support-required", ".evidence"),
    "a verdict with no checkedAt": (
        {**SCORE, "evidence": [{**SPAN, "check": {k: v for k, v in CHECK.items() if k != "checkedAt"}}]},
        "check-dated", ".evidence[e1].check.checkedAt"),
    "a verdict with a blank checkedAt": (
        {**SCORE, "evidence": [{**SPAN, "check": {**CHECK, "checkedAt": " "}}]},
        "check-dated", ".evidence[e1].check.checkedAt"),
    "a verdict with an empty checkerVersion": (
        {**SCORE, "evidence": [{**SPAN, "check": {**CHECK, "checkerVersion": ""}}]},
        "check-attributed", ".evidence[e1].check.checkerVersion"),
    "a verdict with no checkerVersion": (
        {**SCORE, "evidence": [{**SPAN, "check": {k: v for k, v in CHECK.items() if k != "checkerVersion"}}]},
        "check-attributed", ".evidence[e1].check.checkerVersion"),
    "a stale verdict with no checkerVersion": (
        {**SCORE, "evidence": [{**SPAN, "check": {"status": "stale", "checkedAt": MOMENT}}]},
        "check-attributed", ".evidence[e1].check.checkerVersion"),
    "a score with no justification": (
        {**UNJUSTIFIED, "evidence": [SPAN]}, "score-has-a-reason", ".justification"),
    # Stricter than the companion, deliberately, as blank-has-a-note is: JS trim()
    # keeps a zero-width space, and a justification of one says nothing.
    "a score with a whitespace justification": (
        {**SCORE, "justification": "\u200b ", "evidence": [SPAN]}, "score-has-a-reason", ".justification"),
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
    "an inference beside the span it rests on": {**SCORE, "evidence": [SPAN, DRAWN]},
    "an inference contradicted by a span": {
        **SCORE, "evidence": [SPAN, {**DRAWN, "id": "e3", "stance": "contradicts"}, DRAWN]},
    "a blank with only contradicting evidence": _blank("indeterminate", evidence=[{**SPAN, "stance": "contradicts"}]),
    "a dated, attributed verdict": {**SCORE, "evidence": [{**SPAN, "check": CHECK}]},
    "an unchecked reference with no date": {**SCORE, "evidence": [{**SPAN, "check": {"status": "unchecked"}}]},
    "a blank with no justification": _blank("not-evidenced"),
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


#: Evidence that is not a list of reference objects, and where the refusal points (#179).
MALFORMED_EVIDENCE = {
    "a string": ("e1", "$.cells[0].evidence"),
    "one reference, not in a list": (SPAN, "$.cells[0].evidence"),
    "null": (None, "$.cells[0].evidence"),
    "a number": (3, "$.cells[0].evidence"),
    "a list of ids": (["e1"], "$.cells[0].evidence[0]"),
    "a list holding a null": ([SPAN, None], "$.cells[0].evidence[1]"),
    "a list holding a list": ([[SPAN]], "$.cells[0].evidence[0]"),
    "selectors that are a number": ([{**SPAN, "selectors": 5}], "$.cells[0].evidence[0].selectors"),
    "selectors that are a boolean": ([{**SPAN, "selectors": True}], "$.cells[0].evidence[0].selectors"),
}


@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("base", [SCORE, _blank("not-evidenced")], ids=["value", "blank"])
@pytest.mark.parametrize("row", list(MALFORMED_EVIDENCE.values()), ids=list(MALFORMED_EVIDENCE))
def test_malformed_evidence_is_refused_with_its_path_not_a_crash(route, base, row) -> None:
    """A direct caller is not behind ``bind``'s schema: the verb refuses, it does not raise inside."""
    evidence, where = row
    runtime, verbs = _runtime()
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError) as refused:
        route(runtime, verbs, {**base, "evidence": evidence})
    message = str(refused.value)
    assert message.startswith("refused")
    assert f"at {where}:" in message
    if route is _through_the_verb:
        assert "nothing was written" in message
    assert dict(runtime.store.blobs) == before


def test_a_read_only_mapping_as_a_reference_is_refused_not_a_crash() -> None:
    from types import MappingProxyType

    runtime, verbs = _runtime()
    with pytest.raises(ValueError, match=r"at \$\.cells\[0\]\.evidence\[0\]: .*Fix: "):
        _through_the_verb(runtime, verbs, {**SCORE, "evidence": [MappingProxyType(SPAN)]})


def test_a_python_caller_may_still_pass_evidence_as_a_tuple() -> None:
    runtime, verbs = _runtime()
    assert _through_the_verb(runtime, verbs, {**SCORE, "evidence": (SPAN,)})["written"] == 1


def test_the_locator_profile_skips_a_reference_that_is_not_an_object() -> None:
    from rubricator.locators import profile_problems

    assert profile_problems(["e1", None, {**SPAN, "selectors": QUOTE}, {**SPAN, "selectors": 5}]) == []


#: Where a developer checkout of the companion sits; absent on CI, so the parity
#: tests below skip there, as tests/test_vocabulary_parity.py's sibling test does.
_COMPANION = Path(__file__).resolve().parents[2] / "comparanda" / "src" / "core" / "schema"

#: Honesty rule ids the companion's validateAnalysis reports that are not rules
#: here yet, each with why. A new companion rule fails the test below until it is
#: mirrored or listed. The audit of these is #184.
NOT_MIRRORED = {
    "blank-is-defined": "refused at write by _cell_problems, not yet a rule over a merged document (#184)",
    "assertion-attributed": "sign takes authorId from the author it stores; unaudited (#184)",
    "agent-is-typed": "unaudited (#184)",
    "persona-keeps-kind": "unaudited (#184)",
    "disclosure-flag-is-projection-only": "unaudited (#184)",
}


#: Every rule id a DISHONEST row shows refused at write -- through ``bind`` and
#: the verb -- which is a stronger claim than having a citation in RULE_SOURCES.
REFUSED_AT_WRITE = {rule for _cell, rule, _where in DISHONEST.values()}


def _union_members(source: str, name: str) -> set[str]:
    body = re.search(rf"export type {name} =(.*?);", source, re.DOTALL)
    assert body, f"no `{name}` union in the companion source"
    return set(re.findall(r"'([^']+)'", body.group(1)))


@pytest.mark.skipif(not _COMPANION.exists(), reason="no sibling comparanda checkout")
def test_every_rule_validate_evidence_can_return_is_mirrored() -> None:
    """The done-line of #177: each id in the companion's ``EvidenceRuleId`` is a rule here."""
    companion = _union_members((_COMPANION / "evidence.ts").read_text(), "EvidenceRuleId")
    assert companion, "parsed no rule ids: the companion's source moved, fix the parser"
    assert companion <= REFUSED_AT_WRITE


@pytest.mark.skipif(not _COMPANION.exists(), reason="no sibling comparanda checkout")
def test_every_companion_honesty_rule_is_mirrored_or_listed() -> None:
    source = (_COMPANION / "analysis.ts").read_text()
    reported = set(re.findall(r"\bhonesty\(\s*'([^']+)'", source))
    assert "score-has-a-reason" in reported, "parsed no honesty calls: fix the parser"
    assert reported - set(NOT_MIRRORED) <= set(RULE_SOURCES)
    assert not set(NOT_MIRRORED) & set(RULE_SOURCES), "mirrored now: drop it from NOT_MIRRORED"


@pytest.mark.parametrize("status", sorted(set(vocabulary().closed_enums["citationVerdict"]) - {"unchecked"}))
def test_every_verdict_but_unchecked_must_be_dated_and_attributed(status) -> None:
    runtime, verbs = _runtime()
    undated = {**SCORE, "evidence": [{**SPAN, "check": {"status": status}}]}
    with pytest.raises(ValueError) as refused:
        _through_the_verb(runtime, verbs, undated)
    assert "[rule check-dated;" in str(refused.value)
    assert "[rule check-attributed;" in str(refused.value)


def _stored(*assertions):
    return {"cells": [{"alternativeId": "a", "criterionId": "c", "measure": "score",
                       "assertions": list(assertions)}]}


def test_a_zero_is_a_value_and_needs_a_reason() -> None:
    doc = _stored({"id": "s1", "authorId": "ana", "value": 0, "evidence": [SPAN]})
    assert [p.rule_id for p in honesty_problems(doc)] == ["score-has-a-reason"]


def test_a_superseded_assertion_is_still_held_to_the_rules() -> None:
    """As in the companion: superseding a dishonest claim does not make it honest."""
    doc = _stored(
        {"id": "s1", "authorId": "ana", "value": 2, "evidence": [{**SPAN, "check": {"status": "exact"}}],
         "supersededBy": "s2"},
        {"id": "s2", "authorId": "ana", "value": 3, "evidence": [SPAN], "justification": "j"})
    assert sorted(p.rule_id for p in honesty_problems(doc)) == [
        "check-attributed", "check-dated", "score-has-a-reason"]
