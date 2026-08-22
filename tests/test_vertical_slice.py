"""The one-command test: the definition of v1 for this package.

    python -m rubricator demo --root <dir>

runs the whole deterministic chain end to end with **every seam on its default**
and produces an analysis that validates against the companion repository's
published schema, with one scored cell carrying a checked citation and one
honest blank that moves ``silenceRate``.

Two properties make this more than a happy path:

1. **It must still pass after a seam swap.** The store is swapped for an
   in-memory one below and the same assertions hold, which is what makes
   "iteration is an ADD at an existing boundary" verifiable rather than hoped
   for.
2. **It validates against the real contract, not a sketch.** That is the whole
   point of the boundary, and it has already earned its keep: the first run
   returned six failures, of which four were the schema artifact being emitted in
   its output shape rather than its input one, one was a field this package
   invented, and one was a shape this package got wrong.
"""

from __future__ import annotations

from typing import Any

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.contributors import human, persona
from rubricator.merge import MergeProblem, merge_contributions
from rubricator.tools.analysis import (
    analysis_open,
    criteria_set,
    frame_set,
    measures_mark_missing,
    measures_write,
    report_completeness,
)

MOMENT = "2026-08-22T12:00:00Z"


@pytest.fixture()
def runtime(tmp_path):
    """A runtime on a real directory, with a fixed clock so runs are comparable."""
    return build_runtime(root=str(tmp_path / "store"), now=fixed_clock(MOMENT))


@pytest.fixture()
def in_memory():
    """The same runtime with the store seam swapped. Nothing else changes."""
    return build_runtime(blobs={}, now=fixed_clock(MOMENT))


def _run(runtime) -> dict[str, Any]:
    """The chain, exactly as the CLI runs it."""
    store, at = runtime.store, runtime.now()
    analysis_open(store, analysis_id="demo", question="Which runtime should we adopt?")
    frame_set(
        store,
        analysis_id="demo",
        alternatives=[{"id": "alpha", "label": "Alpha"}, {"id": "beta", "label": "Beta"}],
        ambiguities=['"adopt" -- for the new service only, or everywhere?'],
    )
    criteria_set(
        store,
        analysis_id="demo",
        criteria=[{
            "id": "support",
            "label": "Vendor support",
            "anchors": {
                "1": "no published support commitment",
                "3": "a support commitment is stated but not dated",
                "5": "a dated, published support commitment exists",
            },
        }],
    )
    ana = human("ana", "Ana Ruiz")
    cfo = persona(ana, "the sceptical CFO", acting_as="scored on cost exposure alone")
    measures_write(
        store, analysis_id="demo", contributor_id="ana", author=cfo, at=at,
        cells=[{
            "alternativeId": "alpha", "criterionId": "support", "value": 5,
            "justification": "the vendor publishes a dated support window",
            "independence": "independent",
            "evidence": [{
                "id": "e1", "target": "rendition:alpha-support", "sourceType": "primary",
                "stance": "supports", "derivedFrom": [],
                "selectors": [{"type": "TextQuoteSelector", "exact": "supported until 30 June 2029"}],
                "check": {"status": "exact", "checkedAt": at, "checkerVersion": "rubricator/0.0.1"},
            }],
        }],
    )
    measures_mark_missing(
        store, analysis_id="demo", contributor_id="ana", author=cfo, at=at,
        code="not-evidenced",
        note="searched the vendor site and two industry reports; none states a support window",
        criterion_ids=["support"], alternative_ids=["beta"],
    )
    return merge_contributions(store.frame("demo"), store.contributions("demo"))


def test_the_produced_analysis_validates_against_the_published_schema(runtime) -> None:
    """The claim this package makes about its output, checked rather than asserted."""
    merged = _run(runtime)
    result = runtime.schema.validate(merged)
    assert runtime.schema.origin == "published", (
        "validating against a sketch would make this test prove nothing about the contract"
    )
    assert result.ok, result.report()


def test_the_same_chain_on_a_swapped_store(in_memory) -> None:
    """Iteration is an ADD at an existing boundary -- verified, not hoped for.

    The store seam is the one that will actually be swapped: a team moving from
    a local folder to a shared repository changes one argument here. If that
    changes what the chain produces, the seam is not a seam.
    """
    merged = _run(in_memory)
    assert in_memory.schema.validate(merged).ok
    assert [c["criterionId"] for c in merged["cells"]] == ["support", "support"]


def test_one_scored_cell_and_one_honest_blank(runtime) -> None:
    _run(runtime)
    report = report_completeness(runtime.store, analysis_id="demo")
    assert report["present"] == 1
    assert report["settledAbsent"] == 1
    assert report["outstanding"] == 0
    # The blank moves silenceRate because it is informative -- "we looked and the
    # sources are silent" is a statement about the subject. A `withheld` blank
    # would be settled and would NOT move it, which is the distinction the whole
    # honesty metric rests on.
    assert report["informativeAbsent"] == 1
    assert report["silenceRate"] == pytest.approx(0.5)
    assert report["degradations"] == []


def test_the_persona_records_its_principal(runtime) -> None:
    merged = _run(runtime)
    authors = {a["id"]: a for a in merged["authors"]}
    cfo = authors["ana:the-sceptical-cfo"]
    assert cfo["principalId"] == "ana"      # not anonymity: the principal is in the document
    assert cfo["kind"] == "human"           # a persona never changes kind
    assert cfo["actingAs"]                  # and says what perspective it took


def test_assertion_ids_are_namespaced_by_contributor(runtime) -> None:
    """Two contributors whose tooling both generates `s1` must not collide."""
    merged = _run(runtime)
    ids = [a["id"] for c in merged["cells"] for a in c["assertions"]]
    assert all(i.startswith("ana:") for i in ids), ids
    assert len(set(ids)) == len(ids)


def test_a_contributor_may_not_speak_for_someone_else() -> None:
    """The one merge rule no later validation could recover.

    A contribution introducing an author who is neither that contributor nor a
    persona of them produces a perfectly well-formed document that is false. The
    honesty rules sit downstream of it and cannot see it.
    """
    frame = {"id": "a1", "schemaVersion": 1, "subject": {"question": "q"},
             "alternatives": [], "criteria": [], "authors": [], "cells": []}
    forged = {"authors": [{"id": "ben", "displayName": "Ben", "kind": "human"}], "cells": []}
    with pytest.raises(MergeProblem, match="may only speak for themselves"):
        merge_contributions(frame, [("ana", forged)])


def test_the_cli_runs_and_says_something(capsys) -> None:
    """The command in the module docstring, run as a person would run it."""
    from rubricator.cli import main

    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "silenceRate: 0.50" in out
    assert "the sceptical CFO" in out
    assert "principal: ana" in out


def test_an_unknown_scale_raises_at_authoring_and_names_the_alternatives(runtime) -> None:
    """Authoring raises where reading degrades. The asymmetry, at the seam."""
    analysis_open(runtime.store, analysis_id="x", question="q")
    with pytest.raises(KeyError, match="ordinal-1-5-anchored"):
        criteria_set(
            runtime.store, analysis_id="x",
            criteria=[{"id": "c", "label": "C", "scale": "ordinal-1-10"}],
        )


def test_an_undeclared_missingness_code_raises_and_says_how_to_declare_it(runtime) -> None:
    _run(runtime)
    ana = human("ana", "Ana Ruiz")
    with pytest.raises(KeyError, match="broader parent"):
        measures_mark_missing(
            runtime.store, analysis_id="demo", contributor_id="ana", author=ana, at=MOMENT,
            code="paywalled", note="behind a paywall",
        )


def test_a_criterion_missing_a_required_anchor_is_refused(runtime) -> None:
    """An unanchored level is scored against taste rather than against a document."""
    analysis_open(runtime.store, analysis_id="y", question="q")
    with pytest.raises(ValueError, match="missing an anchor at 5"):
        criteria_set(
            runtime.store, analysis_id="y",
            criteria=[{"id": "c", "label": "C", "anchors": {"1": "a", "3": "b"}}],
        )
