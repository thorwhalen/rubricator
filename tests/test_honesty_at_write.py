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
    # #195 (from #178): cited, and nothing cited says it is so.
    "a score whose only evidence contradicts it": (
        {**SCORE, "evidence": [{**SPAN, "stance": "contradicts"}]}, "value-cites-evidence", ".evidence"),
    "a score whose only evidence is context": (
        {**SCORE, "evidence": [{**SPAN, "stance": "context"}, {**SPAN, "id": "e3", "stance": "qualifies"}]},
        "value-cites-evidence", ".evidence"),
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
    "a blank whose code nothing defines": (
        _blank("paywalled"), "blank-is-defined", ".missing.code"),
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
    "a score cited for and against": {**SCORE, "evidence": [{**SPAN, "stance": "contradicts"},
                                                             {**SPAN, "id": "e3", "stance": "supports"}]},
    "a score whose span's stance defaults to supports": {
        **SCORE, "evidence": [{k: v for k, v in SPAN.items() if k != "stance"}]},
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
#: mirrored or listed. All five that were listed here are mirrored now (#184).
NOT_MIRRORED: dict[str, str] = {}


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
    return {"authors": [{"id": "ana", "displayName": "Ana", "kind": "human"}], "cells": [{"alternativeId": "a", "criterionId": "c", "measure": "score",
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


#: Other malformed cells, and where the refusal points (#182). The direct verb used to crash on each.
MALFORMED_CELLS = {
    "a string instead of an object": ("k1", "$.cells[0]"),
    "missing with no code": ({**SCORE, "value": None, "missing": {"note": "n"}}, "$.cells[0].missing"),
    "missing.code a list": (_blank(["x"]), "$.cells[0].missing.code"),
    "missing a string": ({**SCORE, "value": None, "missing": "x"}, "$.cells[0].missing"),
    "measure a list": ({**SCORE, "measure": ["score"]}, "$.cells[0].measure"),
    "alternativeId a list": ({**SCORE, "alternativeId": ["k1"]}, "$.cells[0].alternativeId"),
    "no criterionId": ({k: v for k, v in SCORE.items() if k != "criterionId"}, "$.cells[0]"),
    "justification a number": ({**SCORE, "justification": 3}, "$.cells[0].justification"),
}


@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("row", list(MALFORMED_CELLS.values()), ids=list(MALFORMED_CELLS))
def test_a_malformed_cell_is_refused_with_its_path_not_a_crash(route, row) -> None:
    cell, where = row
    runtime, verbs = _runtime()
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError) as refused:
        route(runtime, verbs, cell)
    assert str(refused.value).startswith("refused")
    assert f"at {where}:" in str(refused.value)
    assert dict(runtime.store.blobs) == before


def test_the_verb_reports_every_malformed_cell_in_one_pass() -> None:
    runtime, verbs = _runtime()
    with pytest.raises(ValueError) as refused:
        measures_write(runtime.store, analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                       at=MOMENT, cells=["k1", {**SCORE, "measure": ["score"]},
                                         {**SCORE, "evidence": "e1", "bogus": 1}])
    message = str(refused.value)
    for where in ("$.cells[0]:", "$.cells[1].measure:", "$.cells[2].evidence:", "$.cells[2]: 'bogus'"):
        assert f"at {where}" in message, message


def test_the_verb_refuses_cells_that_are_not_a_list() -> None:
    runtime, _verbs = _runtime()
    with pytest.raises(ValueError, match=r"at \$\.cells:"):
        measures_write(runtime.store, analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                       at=MOMENT, cells="k1")


def test_a_non_string_key_beside_a_string_one_is_refused_not_a_crash() -> None:
    runtime, _verbs = _runtime()
    with pytest.raises(ValueError, match=r"at \$\.cells\[0\]:"):
        measures_write(runtime.store, analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                       at=MOMENT, cells=[{**SCORE, 1: "x", "bogus": 2}])


# --- the analysis-level rules (#184) -------------------------------------------


def _write_as(verbs_or_runtime, author, *, contributor="scorer", cell=SCORE, evidence=(SPAN,)):
    return verbs_or_runtime["measures_write"](
        analysis_id="a1", contributor_id=contributor, author=author, cells=[{**cell, "evidence": list(evidence)}])


def test_a_model_dressed_as_a_person_is_refused_at_write() -> None:
    runtime, verbs = _runtime()
    bot = {"id": "bot", "displayName": "Bot", "kind": "human", "agent": {"name": "scorer-bot"}}
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=r"authors\[bot\]: .*\[rule agent-is-typed; comparanda ADR-0012\]"):
        _write_as(verbs, bot, contributor="bot")
    assert dict(runtime.store.blobs) == before
    # The honest neighbour: the same run, typed as an agent.
    assert _write_as(verbs, {**bot, "kind": "agent"}, contributor="bot")["written"] == 1


def test_a_persona_that_changes_its_principals_kind_is_refused_at_write() -> None:
    runtime, verbs = _runtime()
    ana = {"id": "ana", "displayName": "Ana", "kind": "human"}
    assert _write_as(verbs, ana, contributor="ana")["written"] == 1
    persona = {"id": "ana:bot", "displayName": "Ana's bot", "kind": "agent", "principalId": "ana"}
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=r"authors\[ana:bot\]: .*\[rule persona-keeps-kind; comparanda ADR-0012\]"):
        _write_as(verbs, persona, contributor="ana", cell={**SCORE, "criterionId": "support",
                                                            "independence": "independent"})
    assert dict(runtime.store.blobs) == before
    assert _write_as(verbs, {**persona, "kind": "human"}, contributor="ana",
                     cell={**SCORE, "independence": "independent"})["written"] == 1


def test_an_author_already_stored_is_not_this_calls_problem() -> None:
    """The rule refuses the record a call introduces, never locks a contributor out over a stored one."""
    runtime, verbs = _runtime()
    bot = {"id": "bot", "displayName": "Bot", "kind": "agent", "agent": {"name": "scorer-bot"}}
    _write_as(verbs, bot, contributor="bot")
    stored = runtime.store._read(runtime.store.contribution_key("a1", "bot"))
    stored["authors"][0]["kind"] = "human"  # a hand edit
    runtime.store.put_contribution("a1", "bot", stored)
    again = _write_as(verbs, bot, contributor="bot", cell={**SCORE, "criterionId": "support",
                                                           "independence": "independent"})
    assert again["written"] == 1
    assert "agent-is-typed" in {p["ruleId"] for p in verbs["report_completeness"](
        analysis_id="a1")["honestyProblems"]}


def test_a_written_assertion_is_always_attributed_to_a_listed_author() -> None:
    """``assertion-attributed`` cannot occur through the verb: ``sign`` takes the author's own id and the author is stored with it."""
    runtime, verbs = _runtime()
    _through_bind(runtime, verbs, {**SCORE, "evidence": [SPAN]})
    assert verbs["report_completeness"](analysis_id="a1")["honestyProblems"] == []
    document = runtime.store.read("a1")
    assert {a["authorId"] for c in document["cells"] for a in c["assertions"]} <= {
        x["id"] for x in document["authors"]}


def test_the_disclosure_flag_cannot_be_written_through_the_verb() -> None:
    """``disclosure-flag-is-projection-only``: a cell has no ``disclosure`` key, so a producer cannot set it."""
    runtime, verbs = _runtime()
    with pytest.raises(ValueError, match="disclosure"):
        _through_the_verb(runtime, verbs, {**SCORE, "evidence": [SPAN],
                                           "disclosure": {"withheldFromReader": True}})


def test_the_five_rules_report_what_reaches_the_store_another_way() -> None:
    """An import, a hand edit or a colleague's file is checked by ``honesty_problems`` over the merged document."""
    doc = {
        "authors": [
            {"id": "bot", "displayName": "Bot", "kind": "human", "agent": {"name": "b"}},
            {"id": "p", "displayName": "P", "kind": "agent", "principalId": "ana"},
            {"id": "ana", "displayName": "Ana", "kind": "human"},
        ],
        "cells": [{"alternativeId": "a", "criterionId": "c", "measure": "score", "assertions": [
            {"id": "s1", "authorId": "ghost", "value": 3, "justification": "j", "evidence": [SPAN],
             "disclosure": {"withheldFromReader": True}},
            {"id": "s2", "authorId": "ana", "missing": {"code": "paywalled", "note": "n"},
             "independence": "independent"},
        ]}],
    }
    found = {(p.rule_id, p.path) for p in honesty_problems(doc)}
    assert {
        ("agent-is-typed", "authors[bot]"),
        ("persona-keeps-kind", "authors[p]"),
        ("assertion-attributed", "cells[a/c/score].assertions[s1].authorId"),
        ("disclosure-flag-is-projection-only",
         "cells[a/c/score].assertions[s1].disclosure.withheldFromReader"),
        ("blank-is-defined", "cells[a/c/score].assertions[s2].missing.code"),
    } <= found


def test_a_projected_out_assertion_may_carry_the_flag() -> None:
    doc = {"authors": [{"id": "ana", "displayName": "Ana", "kind": "human"}],
           "cells": [{"alternativeId": "a", "criterionId": "c", "measure": "score", "assertions": [
               {"id": "s1", "authorId": "ana", "disclosure": {"withheldFromReader": True},
                "missing": {"code": "withheld"}}]}]}
    assert "disclosure-flag-is-projection-only" not in {p.rule_id for p in honesty_problems(doc)}


def test_introducing_a_principal_whose_kind_contradicts_a_stored_persona_is_refused() -> None:
    """A persona is judged against its principal once the principal exists: the call that introduces it answers for it."""
    runtime, verbs = _runtime()
    persona = {"id": "ana:bot", "displayName": "Ana's bot", "kind": "human", "principalId": "ana"}
    assert _write_as(verbs, persona, contributor="ana")["written"] == 1
    ana_as_agent = {"id": "ana", "displayName": "Ana", "kind": "agent", "agent": {"name": "ana-bot"}}
    with pytest.raises(ValueError, match=r"authors\[ana:bot\]: .*\[rule persona-keeps-kind"):
        _write_as(verbs, ana_as_agent, contributor="ana", cell={**SCORE, "independence": "independent"})
    assert _write_as(verbs, {"id": "ana", "displayName": "Ana", "kind": "human"}, contributor="ana",
                     cell={**SCORE, "independence": "independent"})["written"] == 1


def test_the_disclosure_flag_counts_a_whitespace_note_as_content_like_the_companion() -> None:
    doc = {"authors": [{"id": "ana", "displayName": "Ana", "kind": "human"}],
           "cells": [{"alternativeId": "a", "criterionId": "c", "measure": "score", "assertions": [
               {"id": "s1", "authorId": "ana", "disclosure": {"withheldFromReader": True},
                "missing": {"code": "withheld", "note": "\u200b"}}]}]}
    assert "disclosure-flag-is-projection-only" in {p.rule_id for p in honesty_problems(doc)}


def test_two_personas_of_a_principal_not_yet_stored_cannot_disagree_in_kind() -> None:
    """Otherwise the contributor could never write as the principal, whichever kind they gave it."""
    runtime, verbs = _runtime()
    human = {"id": "ana:me", "displayName": "Ana", "kind": "human", "principalId": "ana"}
    bot = {"id": "ana:bot", "displayName": "Ana's bot", "kind": "agent", "principalId": "ana",
           "agent": {"name": "ana-bot"}}
    assert _write_as(verbs, human, contributor="ana")["written"] == 1
    with pytest.raises(ValueError, match=r"authors\[ana:bot\]: .*another persona of \"ana\".*\[rule persona-keeps-kind"):
        _write_as(verbs, bot, contributor="ana", cell={**SCORE, "independence": "independent"})
    same_kind = {**human, "id": "ana:other"}
    assert _write_as(verbs, same_kind, contributor="ana", cell={**SCORE, "independence": "independent"})["written"] == 1


@pytest.mark.parametrize("author", [{"displayName": "No id", "kind": "agent"}, "scorer", None,
                                    {"id": 3, "displayName": "N", "kind": "agent"}])
def test_a_malformed_author_is_refused_with_its_path_not_a_crash(author) -> None:
    """#195 (from #178): a direct caller once got a bare ``KeyError: 'id'``."""
    runtime, _ = _runtime()
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=r"refused, nothing was written: at \$\.author"):
        measures_write(runtime.store, analysis_id="a1", contributor_id="scorer", author=author,
                       at=MOMENT, cells=[{**SCORE, "evidence": [SPAN]}])
    assert dict(runtime.store.blobs) == before
