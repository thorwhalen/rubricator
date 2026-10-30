"""Where an alternative came from is kept beside the frame, and an unsourced one is flagged (#274, #55, ADR-0026).

comparanda v1's closed ``Alternative`` has no slot for a source, so
``alternatives_set`` keeps ``source`` and ``evidence`` in a side record and
computes ``unsourced`` from it.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.tools.analysis import alternatives_set, analysis_open, frame_set
from rubricator.tools.corpus import corpus_add
from rubricator.tools.views import analysis_get


@pytest.fixture()
def setup():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    added = corpus_add(s, analysis_id="a", sources=[
        {"id": "sheet", "title": "Sheet", "text": "The Brightwater K2 boils fast and cuts out when dry.", "agentProduced": False}])
    return s, added["documentIds"][0]


def test_corpus_or_inference_with_no_evidence_is_unsourced(setup) -> None:
    store, doc = setup
    out = alternatives_set(store, analysis_id="a", alternatives=[
        {"id": "k2", "label": "Brightwater K2", "source": "corpus", "evidence": [f"{doc}:0-20"]},
        {"id": "guess", "label": "A kettle I imagine", "source": "inference"},
        {"id": "listed", "label": "Mentioned in the corpus", "source": "corpus"},
        {"id": "mine", "label": "The user's pick", "source": "user"},
        {"id": "plain", "label": "Says nothing"},
    ])
    assert out["unsourced"] == ["guess", "listed"]
    assert "guess, listed" in out["summary"]


def test_the_frame_stays_a_valid_comparanda_alternative_and_the_record_sits_beside_it(setup) -> None:
    store, doc = setup
    alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2", "source": "corpus", "evidence": [doc]}])
    assert store.frame("a")["alternatives"] == [{"id": "k2", "label": "K2"}]
    assert store.alternative_provenance("a") == {"k2": {"source": "corpus", "evidence": [doc]}}
    # And the view hands it back, so a view round-trips into the verb.
    row = analysis_get(store, analysis_id="a", view="frame")["alternatives"][0]
    assert row["source"] == "corpus" and row["evidence"] == [doc]
    again = alternatives_set(store, analysis_id="a", alternatives=[row])
    assert again["unsourced"] == []


def test_a_redeclaration_that_omits_provenance_keeps_it_and_a_dropped_row_loses_it(setup) -> None:
    store, doc = setup
    alternatives_set(store, analysis_id="a", alternatives=[
        {"id": "k2", "label": "K2", "source": "corpus", "evidence": [doc]}, {"id": "l5", "label": "L5", "source": "inference"}])
    out = alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2 kettle"}])
    assert out["unsourced"] == []
    assert store.alternative_provenance("a") == {"k2": {"source": "corpus", "evidence": [doc]}}
    # Saying only a new source keeps the evidence already named.
    alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2 kettle", "source": "corpus"}])
    assert store.alternative_provenance("a")["k2"]["evidence"] == [doc]


def test_evidence_the_corpus_does_not_hold_is_refused_and_nothing_is_written(setup) -> None:
    store, _ = setup
    with pytest.raises(ValueError, match="names a document the corpus does not hold"):
        alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2", "source": "corpus", "evidence": ["doc-nope:0-5"]}])
    assert store.frame("a")["alternatives"] == [] and store.alternative_provenance("a") == {}


def test_a_users_alternative_takes_no_evidence(setup) -> None:
    store, doc = setup
    with pytest.raises(ValueError, match="a user's alternative is their word"):
        alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2", "source": "user", "evidence": [doc]}])


def test_an_unknown_source_is_refused(setup) -> None:
    store, _ = setup
    with pytest.raises(ValueError):
        alternatives_set(store, analysis_id="a", alternatives=[{"id": "k2", "label": "K2", "source": "a-hunch"}])
