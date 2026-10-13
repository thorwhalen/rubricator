"""Paths the #195 fixes touch, pinned on the code as it stood before them.

Each test here passes before the fixes and must keep passing after: they hold
the honest cases (a frame cell with no assertions, scores at the current
definition, a supporting citation, a known normaliser) so that tightening a
check is seen not to refuse what it should accept. The error paths below were
uncovered by any test when the review measured them.
"""

from __future__ import annotations

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.locators import from_fragment, profile_problems, selector_from_dict, to_fragment
from rubricator.merge import merge_contributions
from rubricator.normalise import excerpt_hash
from rubricator.rules import cite_a_span, value_cites_evidence
from rubricator.store import AnalysisStore
from rubricator.tools.aggregate import aggregate_assertions, refuse_a_mean
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    measures_write,
)
from rubricator.tools.confirm import frame_confirm, record_decision

AT = "2026-10-12T12:00:00Z"
QUOTE = {"type": "TextQuoteSelector", "exact": "as stated"}
CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary", "selectors": [QUOTE]}]
FRAME = {"id": "a1", "schemaVersion": 1, "subject": {"question": "which kettle?"},
         "alternatives": [], "criteria": [], "authors": [], "cells": []}


def _scored(store, rater: str, value: int) -> None:
    measures_write(store, analysis_id="a", contributor_id=rater, author=human(rater, rater),
                   at=AT, cells=[{"alternativeId": "k1", "criterionId": "speed", "value": value,
                                  "evidence": CITED, "justification": "spec sheet",
                                  "independence": "independent"}])


@pytest.fixture()
def store():
    rt = build_runtime(blobs={})
    s = rt.store
    analysis_open(s, analysis_id="a", question="Which kettle?", allow_skip_confirmation=True,
                  at=AT)
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "k1", "label": "Kettle one"}])
    criteria_set(s, analysis_id="a", criteria=[
        {"id": "speed", "label": "Speed", "anchors": {"1": "slow", "3": "fair", "5": "fast"}}])
    return s


# -- merge: the frame -----------------------------------------------------------


def test_a_frame_cell_with_no_assertions_still_merges() -> None:
    frame = {**FRAME, "cells": [{"alternativeId": "k1", "criterionId": "speed",
                                 "measure": "score", "assertions": []}]}
    ana = {"authors": [], "cells": [{"alternativeId": "k1", "criterionId": "speed",
                                     "measure": "score",
                                     "assertions": [{"id": "s1", "authorId": "ana", "value": 3}]}]}
    merged = merge_contributions(frame, [("ana", ana)])
    assert [a["id"] for a in merged["cells"][0]["assertions"]] == ["ana:s1"]


def test_a_frame_persona_signs_for_its_principal_beside_other_contributors() -> None:
    frame = {**FRAME, "authors": [{"id": "ana:cfo", "displayName": "CFO", "kind": "human",
                                   "principalId": "ana"}]}
    signed = {"authors": [], "cells": [{"alternativeId": "k1", "criterionId": "speed",
                                        "measure": "score",
                                        "assertions": [{"id": "s1", "authorId": "ana:cfo"}]}]}
    merged = merge_contributions(frame, [("ana", signed), ("ben", {"cells": []})])
    assert merged["cells"][0]["assertions"][0]["authorId"] == "ana:cfo"


# -- the gate -------------------------------------------------------------------


def test_unknown_scope_or_decision_is_refused(store) -> None:
    with pytest.raises(ValueError, match="unknown scope"):
        frame_confirm(store, analysis_id="a", at=AT, scope="everything")
    with pytest.raises(ValueError, match="unknown decision"):
        frame_confirm(store, analysis_id="a", at=AT, decision="maybe")
    with pytest.raises(ValueError, match="unknown decision"):
        record_decision(store, analysis_id="a", at=AT, scope="all", decision="maybe",
                        author_id="ana", text="sure", mechanism="out-of-band")


# -- the aggregate --------------------------------------------------------------


def test_scores_at_the_current_definition_are_all_counted(store) -> None:
    criteria_set(store, analysis_id="a", criteria=[
        {"id": "speed", "label": "Speed from cold", "anchors": {"1": "slow", "3": "fair",
                                                                "5": "fast"}}])
    _scored(store, "r2", 4)
    _scored(store, "r3", 4)
    (cell,) = aggregate_assertions(store, analysis_id="a")["cells"]
    assert cell["n"] == 2 and cell["reduced"] == 4


def test_an_unknown_reduction_and_a_mean_on_a_missing_analysis_are_refused(store) -> None:
    with pytest.raises(ValueError, match="not one of"):
        aggregate_assertions(store, analysis_id="a", reduction="mode")
    with pytest.raises(ValueError, match="ordinal"):
        refuse_a_mean(store, {"analysis_id": "nowhere", "reduction": "mean"})


# -- evidence -------------------------------------------------------------------


def _document(*refs) -> dict:
    return {"cells": [{"alternativeId": "k1", "criterionId": "speed", "measure": "score",
                       "assertions": [{"id": "s1", "value": 5, "evidence": list(refs)}]}]}


def test_a_value_with_a_supporting_citation_passes() -> None:
    supports = {**CITED[0]}
    contrary = {**CITED[0], "id": "e2", "stance": "contradicts"}
    assert list(value_cites_evidence(_document(supports, contrary))) == []
    assert list(value_cites_evidence(_document({**supports, "stance": "supports"}))) == []


def test_a_quote_with_visible_words_and_a_known_normaliser_is_in_the_profile() -> None:
    ref = {**CITED[0], "excerpt": "as stated", "excerptHash": excerpt_hash("as stated"),
           "normaliserId": "nfc-v1"}
    assert profile_problems([ref]) == []
    assert list(cite_a_span(_document(ref))) == []


def test_an_unknown_selector_type_and_a_non_selector_are_refused() -> None:
    with pytest.raises(ValueError, match="not a selector type"):
        selector_from_dict({"type": "MadeUpSelector"})
    with pytest.raises(TypeError, match="not a selector"):
        to_fragment("page 4")
    fragment = selector_from_dict({"type": "FragmentSelector", "value": "x=1",
                                   "conformsTo": "urn:example"})
    assert from_fragment(fragment) is fragment


# -- the store ------------------------------------------------------------------


def test_a_rendition_is_written_and_read_back() -> None:
    store = AnalysisStore({}, now=fixed_clock(AT))
    store.put_frame("a1", dict(FRAME))
    rendition = {"id": "r1", "originalLocator": "doc:spec", "originalSha256": "0" * 64,
                 "normaliserId": "nfc-v1"}
    store.put_rendition("a1", rendition)
    assert store.renditions("a1") == [rendition]
    assert store.read("a1")["renditions"] == [rendition]


def test_a_frame_written_over_an_expired_analysis_starts_afresh() -> None:
    clock = {"now": "2026-01-01T00:00:00Z"}
    store = AnalysisStore({}, now=lambda: clock["now"], retention_days=1)
    store.put_frame("a1", dict(FRAME))
    store.put_contribution("a1", "ana", {"authors": [], "cells": []})
    clock["now"] = "2026-03-01T00:00:00Z"
    store.put_frame("a1", dict(FRAME))
    assert store.contributors("a1") == []
