"""A re-score replaces the writer's own earlier claim by naming it in ``supersedes`` (#181, ADR-0026).

The verb marks ``supersededBy`` on the stored assertion in the writer's own
file; the claim is kept, not deleted. Someone else's assertion, one that does
not exist, one already replaced and a self-reference are refused with nothing
written.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.merge import merge_contributions
from rubricator.rules import honesty_problems
from rubricator.tools.analysis import alternatives_set, analysis_open, criteria_set, frame_set, measures_write

CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
AT = "2026-10-30T12:00:00Z"
ANA, BEN = human("ana", "Ana"), human("ben", "Ben")


@pytest.fixture()
def store():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(s, analysis_id="a", criteria=[{"id": "c", "label": "C", "anchors": {"1": "none", "3": "some", "5": "all"}}])
    return s


def _score(store, who, value, **extra):
    return measures_write(
        store, analysis_id="a", contributor_id=who["id"], author=who, at=AT,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": value, "justification": "because", "evidence": CITED, **extra}],
    )


def _assertions(store, who):
    return _by_contributor(store)[who["id"]]["cells"][0]["assertions"]


def _by_contributor(store):
    return dict(store.contributions("a"))


def test_a_rescore_replaces_the_earlier_claim_and_keeps_it(store) -> None:
    _score(store, ANA, 3, assertionId="first")
    _score(store, ANA, 4, assertionId="second", supersedes="first")
    first, second = _assertions(store, ANA)
    assert first["id"] == "first" and first["value"] == 3 and first["supersededBy"] == "second"
    assert second["id"] == "second" and "supersededBy" not in second
    # One live claim, so no independence is owed and the honesty rules are quiet.
    merged = merge_contributions(store.frame("a"), store.contributions("a"))
    assert list(honesty_problems(merged)) == []


def test_a_fresh_id_is_given_when_none_is_asked_for(store) -> None:
    _score(store, ANA, 3, assertionId="first")
    _score(store, ANA, 4, supersedes="first")
    first, second = _assertions(store, ANA)
    assert first["supersededBy"] == second["id"]


@pytest.mark.parametrize("supersedes, why", [
    ("nope", "no assertion with that id"),
    ("second", "cannot supersede itself"),
])
def test_an_id_that_is_not_there_or_is_itself_is_refused_and_nothing_is_written(store, supersedes, why) -> None:
    _score(store, ANA, 3, assertionId="first")
    with pytest.raises(ValueError, match=why):
        _score(store, ANA, 4, assertionId="second", supersedes=supersedes)
    assert len(_assertions(store, ANA)) == 1 and "supersededBy" not in _assertions(store, ANA)[0]


def test_someone_elses_assertion_is_refused_by_name(store) -> None:
    _score(store, BEN, 2, assertionId="bens")
    with pytest.raises(ValueError, match=r"it is ben's, and a writer replaces only their own"):
        _score(store, ANA, 4, assertionId="mine", supersedes="bens", independence="independent")
    assert "supersededBy" not in _assertions(store, BEN)[0]
    assert "ana" not in _by_contributor(store)


def test_an_already_replaced_claim_is_refused_and_names_its_successor(store) -> None:
    _score(store, ANA, 3, assertionId="first")
    _score(store, ANA, 4, assertionId="second", supersedes="first")
    with pytest.raises(ValueError, match=r'already replaced by "second"'):
        _score(store, ANA, 5, assertionId="third", supersedes="first")
