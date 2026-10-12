"""The independence rung on assertions, and the honesty rule that needs it (#30).

`comparanda` refuses a cell holding two or more live assertions where any one
lacks ``independence`` (its rule ``independence-recorded``). These tests pin
the Python mirror and the write-time refusal, so the boundary refuses what the
renderer would.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent, human, sign
from rubricator.merge import merge_contributions
from rubricator.rules import honesty_problems
from rubricator.tools.analysis import (
    analysis_open,
    criteria_set,
    frame_set,
    measures_mark_missing,
    measures_write,
    report_completeness,
)

AT = "2026-10-12T12:00:00Z"
ANCHORS = {"1": "none", "3": "some", "5": "all"}


@pytest.fixture()
def store():
    rt = build_runtime(blobs={})
    s = rt.store
    analysis_open(s, analysis_id="a", question="which?")
    frame_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}], ambiguities=[])
    criteria_set(s, analysis_id="a", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    return s


def _score(store, who, value, **extra):
    return measures_write(
        store, analysis_id="a", contributor_id=who["id"], author=who, at=AT,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": value,
                "justification": "because", **extra}],
    )


def _merged(store):
    return merge_contributions(store.frame("a"), store.contributions("a"))


def test_a_lone_assertion_needs_no_rung(store) -> None:
    _score(store, human("ana", "Ana"), 4)
    assert honesty_problems(_merged(store)) == []


def test_a_second_draw_without_a_rung_is_refused_and_nothing_is_written(store) -> None:
    bot = agent("bot", "Bot", name="rubricator")
    _score(store, bot, 4, independence="resampled")
    before = list(store.contributions("a"))
    with pytest.raises(ValueError, match="independence-recorded|records no independence"):
        _score(store, bot, 3)
    assert list(store.contributions("a")) == before


def test_repeated_draws_of_one_model_record_resampled_and_get_distinct_ids(store) -> None:
    bot = agent("bot", "Bot", name="rubricator")
    _score(store, bot, 4, independence="resampled")
    _score(store, bot, 3, independence="resampled")
    merged = _merged(store)
    ids = [a["id"] for a in merged["cells"][0]["assertions"]]
    assert ids == ["bot:x-c-score", "bot:x-c-score-2"]
    assert honesty_problems(merged) == []


def test_another_contributors_missing_rung_is_reported_but_does_not_block_this_write(store) -> None:
    """The second writer cannot fix the first one's assertion, so only the merged
    check names it -- with the first author's assertion id in the path."""
    _score(store, human("ana", "Ana"), 4)
    _score(store, human("ben", "Ben"), 2, independence="independent")
    problems = honesty_problems(_merged(store))
    assert [p.rule_id for p in problems] == ["independence-recorded"]
    assert "assertions[ana:x-c-score]" in problems[0].path
    assert problems[0].severity == "error" and problems[0].fix


def test_a_blank_counts_as_a_member_of_the_set(store) -> None:
    ana = human("ana", "Ana")
    _score(store, ana, 4, independence="independent")
    with pytest.raises(ValueError, match="records no independence"):
        measures_mark_missing(
            store, analysis_id="a", contributor_id="ana", author=ana, at=AT,
            code="not-evidenced", note="nothing found",
        )


def test_a_superseded_assertion_is_not_live() -> None:
    doc = {"cells": [{"alternativeId": "x", "criterionId": "c", "measure": "score",
                      "assertions": [{"id": "s1", "authorId": "a", "value": 1, "supersededBy": "s2"},
                                     {"id": "s2", "authorId": "a", "value": 2}]}]}
    assert honesty_problems(doc) == []


def test_the_rung_is_spelled_in_the_companion_ladder() -> None:
    for old in ("in-session", "fresh-session", "distinct-model", "distinct-human"):
        with pytest.raises(ValueError, match="unknown independence rung"):
            sign({"id": "a"}, at=AT, assertion_id="s", value=1, independence=old)


def test_perturbed_requires_a_perturbation_record(store) -> None:
    with pytest.raises(ValueError, match="perturbation record"):
        sign({"id": "a"}, at=AT, assertion_id="s", value=1, independence="perturbed")
    bot = agent("bot", "Bot", name="rubricator")
    _score(store, bot, 4, independence="perturbed",
           perturbation={"kind": "traversal-order", "seed": 7})
    a = _merged(store)["cells"][0]["assertions"][0]
    assert a["perturbation"] == {"kind": "traversal-order", "seed": 7}


def test_what_is_emitted_validates_against_the_frozen_schema(store) -> None:
    bot = agent("bot", "Bot", name="rubricator")
    _score(store, bot, 4, independence="perturbed", perturbation={"kind": "order", "seed": 1})
    _score(store, bot, 3, independence="perturbed", perturbation={"kind": "order", "seed": 2})
    rt = build_runtime(blobs={})
    assert rt.schema.validate(_merged(store)).ok


def _two_cell_store():
    rt = build_runtime(blobs={})
    s = rt.store
    analysis_open(s, analysis_id="a", question="which?")
    frame_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}],
              ambiguities=[])
    criteria_set(s, analysis_id="a", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    return s


def test_one_flagged_cell_never_locks_a_contributor_out_of_the_rest() -> None:
    """Review repro C: the flagged assertion is stored and nothing can amend it,
    so refusing every later write by its author would freeze them for good."""
    s = _two_cell_store()
    ana, ben = human("ana", "Ana"), human("ben", "Ben")
    _score(s, ana, 4)
    _score(s, ben, 2, independence="independent")
    measures_write(s, analysis_id="a", contributor_id="ana", author=ana, at=AT,
                   cells=[{"alternativeId": "y", "criterionId": "c", "value": 3,
                           "justification": "because"}])
    report = report_completeness(s, analysis_id="a")
    assert [p["ruleId"] for p in report["honestyProblems"]] == ["independence-recorded"]
    assert "ana:x-c-score" in report["honestyProblems"][0]["path"]


def test_a_rescore_with_a_rung_is_accepted_and_the_older_gap_is_reported(store) -> None:
    """Review repro A."""
    ana = human("ana", "Ana")
    _score(store, ana, 4)
    _score(store, ana, 3, independence="shared-context")
    problems = honesty_problems(_merged(store))
    assert [p.path for p in problems] == ["cells[x/c/score].assertions[ana:x-c-score].independence"]


def test_a_blank_on_a_shared_cell_carries_its_rung(store) -> None:
    """Review repro B: mark_missing takes independence."""
    _score(store, human("ben", "Ben"), 4, independence="independent")
    ana = human("ana", "Ana")
    measures_mark_missing(store, analysis_id="a", contributor_id="ana", author=ana, at=AT,
                          code="not-evidenced", note="nothing found", independence="independent")
    assert honesty_problems(_merged(store)) == []


def test_a_caller_supplied_id_already_in_the_cell_is_refused(store) -> None:
    """Review repro F: comparanda's unique-ids would refuse the merged document."""
    ana = human("ana", "Ana")
    _score(store, ana, 4, assertionId="s1")
    with pytest.raises(ValueError, match="already used"):
        _score(store, ana, 3, assertionId="s1", independence="shared-context")


@pytest.mark.parametrize("bad", [{"kind": 7}, {"kind": "t", "bogus": 1}, {"kind": "t", "seed": [1]}])
def test_a_perturbation_record_has_the_closed_shape(bad) -> None:
    with pytest.raises(ValueError, match="perturbation record is"):
        sign({"id": "a"}, at=AT, assertion_id="s", value=1, independence="perturbed",
             perturbation=bad)


def test_supersession_must_resolve_or_it_would_switch_an_assertion_off() -> None:
    def doc(*assertions):
        return {"cells": [{"alternativeId": "x", "criterionId": "c", "measure": "score",
                           "assertions": list(assertions)}]}
    ghost = doc({"id": "s1", "authorId": "a", "value": 1, "supersededBy": "ghost"},
                {"id": "s2", "authorId": "b", "value": 2})
    assert [p.rule_id for p in honesty_problems(ghost)] == ["supersession-resolves"]
    cycle = doc({"id": "s1", "authorId": "a", "value": 1, "supersededBy": "s2"},
                {"id": "s2", "authorId": "a", "value": 2, "supersededBy": "s1"})
    assert {p.rule_id for p in honesty_problems(cycle)} == {"supersession-acyclic"}
    dup = doc({"id": "s1", "authorId": "a", "value": 1}, {"id": "s1", "authorId": "a", "value": 2,
                                                          "independence": "resampled"})
    assert "unique-ids" in [p.rule_id for p in honesty_problems(dup)]


def test_merge_namespaces_supersession_with_the_ids() -> None:
    frame = {"id": "a", "cells": [], "authors": []}
    contrib = {"authors": [], "cells": [{"alternativeId": "x", "criterionId": "c", "measure": "score",
               "assertions": [{"id": "s1", "authorId": "ana", "value": 1, "supersededBy": "s2"},
                              {"id": "s2", "authorId": "ana", "value": 2}]}]}
    merged = merge_contributions(frame, [("ana", contrib)])
    assert merged["cells"][0]["assertions"][0]["supersededBy"] == "ana:s2"
    assert honesty_problems(merged) == []
