"""The procedure record and the independence ladder on every assertion (#99).

ADR-0018: each assertion carries its rung, the record of what a pass did is
written by the tools from what they saw, and a set of assertions is labelled by
its lowest rung -- with ``distinct-model`` never called independent raters.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import agent, human
from rubricator.independence import agreement, distinct_model_problem
from rubricator.merge import merge_contributions
from rubricator.rules import honesty_problems, procedure_and_round_resolve
from rubricator.schema.source import SchemaSource
from rubricator.surface import bind
from rubricator.tools.aggregate import aggregate_assertions
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    frame_set,
    measures_write,
)

CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]
AT = "2026-10-12T12:00:00Z"
ANCHORS = {"1": "none", "3": "some", "5": "all"}
BOT = agent("bot", "Bot", name="rubricator", model="model-a", prompt_version="score-cell-v3",
            run_id="run-1")


@pytest.fixture()
def store():
    s = build_runtime(blobs={}).store
    analysis_open(s, analysis_id="a", question="which?", allow_skip_confirmation=True,
                  at="2026-08-22T12:00:00Z")
    frame_set(s, analysis_id="a", ambiguities=[])
    alternatives_set(s, analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(s, analysis_id="a", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    return s


def _score(store, who, value, *, at=AT, procedure=None, **cell):
    return measures_write(
        store, analysis_id="a", contributor_id=who["id"], author=who, at=at, procedure=procedure,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": value,
                "justification": "because", "evidence": CITED, **cell}],
    )


def _merged(store):
    return merge_contributions(store.frame("a"), store.contributions("a"))


def _assertions(store):
    return _merged(store)["cells"][0]["assertions"]


# --- the procedure record is written by the tools -------------------------------


def _three_passes(store, *, prior="withheld"):
    for n, seed in enumerate((11, 12, 13), start=1):
        _score(store, BOT, 3 + (n == 2), at=f"2026-10-12T12:0{n}:00Z", procedure={
            "traversal": "cell-wise", "reduction": "lower-median", "seed": seed, "round": n,
            "session": "fresh", "prior": prior})


def test_three_passes_write_one_procedure_counted_from_the_draws(store) -> None:
    _three_passes(store)
    merged = _merged(store)
    (procedure,) = merged["procedures"]
    assert procedure["repeats"] == 3
    assert procedure["traversal"] == "cell-wise" and procedure["reduction"] == "lower-median"
    assert (procedure["startedAt"], procedure["finishedAt"]) == (
        "2026-10-12T12:01:00Z", "2026-10-12T12:03:00Z")
    for fact in ("model-a", "score-cell-v3", "run-1", "11, 12, 13", "round-1, round-2, round-3"):
        assert fact in procedure["notes"]
    assert [r["feedback"] for r in merged["rounds"]] == ["none"] * 3
    assert [r["index"] for r in merged["rounds"]] == [1, 2, 3]
    assert all(a["procedureId"] == procedure["id"] for a in _assertions(store))
    assert [a["roundId"] for a in _assertions(store)] == [
        "bot:round-1", "bot:round-2", "bot:round-3"]


def test_the_stored_record_fits_the_closed_comparanda_schema_and_honesty_rules(store) -> None:
    _three_passes(store)
    merged = _merged(store)
    for field in ("procedures", "rounds"):
        assert SchemaSource.vendored().refusals(
            merged[field], pointer=f"/properties/{field}", root=f"$.{field}") == []
    assert honesty_problems(merged) == []


def test_a_caller_cannot_assert_the_counts(store) -> None:
    with pytest.raises(ValueError, match="unknown key.*repeats"):
        _score(store, BOT, 3, procedure={"repeats": 99})
    with pytest.raises(ValueError, match="pass number"):
        _score(store, BOT, 3, procedure={"round": 0})
    assert not list(store.contributions("a"))


def test_no_procedure_means_no_record_and_nothing_is_stamped(store) -> None:
    _score(store, BOT, 3)
    merged = _merged(store)
    assert merged["procedures"] == [] and merged["rounds"] == []
    assert "procedureId" not in _assertions(store)[0]


def test_a_human_has_no_procedure_record(store) -> None:
    with pytest.raises(ValueError, match="agent's pass"):
        _score(store, human("ana", "Ana"), 3, procedure={"round": 1})


# --- the rung is derived from the pass, and a contradicting claim is refused ----


def test_the_rung_is_derived_from_the_declared_session_and_never_defaults_up(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "session": "same"})
    _score(store, BOT, 4, procedure={"round": 2, "session": "fresh"})
    _score(store, BOT, 4, procedure={"round": 3, "session": "fresh", "seed": 7})
    _score(store, BOT, 4, procedure={"round": 4, "session": "fresh", "prior": "shown"})
    rungs = [a["independence"] for a in _assertions(store)]
    assert rungs == ["shared-context", "resampled", "perturbed", "shared-context"]
    assert _assertions(store)[2]["perturbation"] == {"kind": "traversal-order", "seed": 7}


def test_a_draw_that_saw_the_prior_cannot_claim_more_than_shared_context(store) -> None:
    for claim in ("resampled", "independent"):
        with pytest.raises(ValueError, match="saw the prior"):
            _score(store, BOT, 3, procedure={"round": 1, "prior": "shown"}, independence=claim)
    with pytest.raises(ValueError, match="same session"):
        _score(store, BOT, 3, procedure={"round": 1, "session": "same"}, independence="perturbed")
    assert not list(store.contributions("a"))


def test_understating_the_rung_is_allowed(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "session": "fresh"}, independence="shared-context")
    assert _assertions(store)[0]["independence"] == "shared-context"


def test_a_round_cannot_be_restated_with_a_different_prior(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "prior": "withheld", "session": "fresh"})
    with pytest.raises(ValueError, match="already recorded"):
        _score(store, BOT, 4, procedure={"round": 1, "prior": "shown"})


def test_two_contributors_passes_keep_their_own_records(store) -> None:
    other = agent("bot2", "Bot2", name="rubricator", model="model-b")
    _score(store, BOT, 3, procedure={"round": 1, "session": "fresh"})
    _score(store, other, 4, procedure={"round": 1, "session": "fresh"}, independence="independent")
    merged = _merged(store)
    assert len(merged["procedures"]) == 2 and len(merged["rounds"]) == 2
    assert {r["id"] for r in merged["rounds"]} == {"bot:round-1", "bot2:round-1"}
    assert procedure_and_round_resolve_ok(merged)


def procedure_and_round_resolve_ok(merged) -> bool:
    return list(procedure_and_round_resolve(merged)) == []


def test_a_dangling_procedure_or_round_is_an_honesty_problem() -> None:
    doc = {"procedures": [], "rounds": [], "cells": [{"alternativeId": "x", "criterionId": "c",
           "assertions": [{"id": "a", "procedureId": "p-1", "roundId": "r-1"}]}]}
    assert [p.rule_id for p in procedure_and_round_resolve(doc)] == ["procedure-and-round-resolve"] * 2


# --- the ladder: labels, lowest rung, and distinct-model is not independent ------


def _authors(**kinds):
    return {k: ({"kind": "human"} if v == "human" else {"kind": "agent", "agent": {"name": "r", "model": v}})
            for k, v in kinds.items()}


def _a(i, author, rung):
    return {"id": i, "authorId": author, **({"independence": rung} if rung else {})}


def test_a_mixed_set_is_labelled_by_its_lowest_rung() -> None:
    authors = _authors(bot="m1", ana="human")
    drafts = [_a(str(i), "bot", "shared-context") for i in range(4)] + [_a("h", "ana", "independent")]
    got = agreement(drafts, authors)
    assert got["rung"] == "in-session" and "not inter-rater" in got["label"]
    assert {c["rung"]: c["count"] for c in got["counts"]} == {"in-session": 4, "distinct-human": 1}


def test_an_unrecorded_rung_is_the_bottom_not_a_default_up() -> None:
    got = agreement([_a("1", "bot", None), _a("2", "ana", "independent")], _authors(bot="m1", ana="human"))
    assert got["rung"] == "unrecorded"


def test_distinct_models_are_not_labelled_independent_raters() -> None:
    got = agreement([_a("1", "x", "independent"), _a("2", "y", "independent")], _authors(x="m1", y="m2"))
    assert got["rung"] == "distinct-model"
    assert "not independent raters" in got["label"] and "partly shared" in got["label"]
    assert "records no model" not in got["label"]


def test_an_unrecorded_model_is_named_in_the_label() -> None:
    authors = {"x": {"kind": "agent"}, "y": {"kind": "agent", "agent": {"name": "r", "model": "m2"}}}
    got = agreement([_a("1", "x", "independent"), _a("2", "y", "independent")], authors)
    assert "records no model" in got["label"]


def test_one_assertion_has_no_agreement() -> None:
    assert agreement([_a("1", "bot", "independent")], _authors(bot="m1")) is None


def test_consensus_is_off_the_ladder() -> None:
    got = agreement([_a("1", "x", "consensus"), _a("2", "y", "resampled"), _a("3", "y", "perturbed")],
                    _authors(x="m1", y="m1"))
    assert got["rung"] == "fresh-session"


def test_independent_on_the_same_model_is_refused_and_nothing_is_written(store) -> None:
    _score(store, BOT, 3, independence="resampled")
    twin = agent("twin", "Twin", name="rubricator", model="model-a")
    before = list(store.contributions("a"))
    with pytest.raises(ValueError, match="independent-agent-is-distinct"):
        _score(store, twin, 4, independence="independent")
    assert list(store.contributions("a")) == before


def test_a_distinct_model_may_claim_independent_and_is_labelled_as_such(store) -> None:
    _score(store, BOT, 3, independence="resampled")
    other = agent("other", "Other", name="rubricator", model="model-b")
    _score(store, other, 4, independence="independent")
    authors = {a["id"]: a for a in _merged(store)["authors"]}
    live = _assertions(store)
    assert distinct_model_problem(live[1], live, authors) is None


def test_aggregate_assertions_labels_each_cell_by_its_lowest_rung(store) -> None:
    _three_passes(store)
    (cell,) = aggregate_assertions(store, analysis_id="a")["cells"]
    assert cell["agreement"]["rung"] == "fresh-session"
    assert "test-retest" in cell["agreement"]["label"]


def test_a_single_draw_cell_has_null_agreement(store) -> None:
    _score(store, BOT, 3)
    (cell,) = aggregate_assertions(store, analysis_id="a")["cells"]
    assert cell["agreement"] is None


def test_the_surface_accepts_the_procedure_argument_and_refuses_extras() -> None:
    verbs = bind(build_runtime(blobs={}))
    verbs["analysis_open"](analysis_id="a", question="q", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a", criteria=[{"id": "c", "label": "C", "anchors": [
        {"level": k, "text": v} for k, v in ANCHORS.items()]}])
    cell = {"alternativeId": "x", "criterionId": "c", "value": 3, "justification": "j",
            "evidence": CITED}
    ok = verbs["measures_write"](analysis_id="a", contributor_id="bot", author=BOT, cells=[cell],
                                 procedure={"traversal": "cell-wise", "round": 1, "session": "fresh"})
    assert ok["written"] == 1
    with pytest.raises(Exception, match="repeats"):
        verbs["measures_write"](analysis_id="a", contributor_id="bot", author=BOT, cells=[cell],
                                procedure={"repeats": 5})


# --- regressions from the adversarial review ----------------------------------------


def test_the_record_reads_the_stored_author_not_the_argument(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "session": "fresh"})
    drifted = agent("bot", "Bot", name="rubricator", model="model-z", prompt_version="v9", run_id="run-9")
    _score(store, drifted, 4, procedure={"round": 2, "session": "fresh"})
    merged = _merged(store)
    assert len(merged["procedures"]) == 1
    assert "model-z" not in merged["procedures"][0]["notes"] and merged["procedures"][0]["repeats"] == 2


def test_times_are_ordered_by_instant_not_by_text(store) -> None:
    _score(store, BOT, 3, at="2026-10-12T12:00:00+02:00", procedure={"round": 1, "session": "fresh"})
    _score(store, BOT, 4, at="2026-10-12T11:00:00Z", procedure={"round": 2, "session": "fresh"})
    (procedure,) = _merged(store)["procedures"]
    assert (procedure["startedAt"], procedure["finishedAt"]) == (
        "2026-10-12T12:00:00+02:00", "2026-10-12T11:00:00Z")  # 10:00Z, then 11:00Z


def test_a_persona_has_its_own_pass_numbers(store) -> None:
    from rubricator.contributors import persona

    p = persona(BOT, "the buyer")
    _score(store, BOT, 3, procedure={"round": 1, "prior": "withheld"}, independence="resampled")
    measures_write(store, analysis_id="a", contributor_id="bot", author=p, at=AT,
                   cells=[{"alternativeId": "x", "criterionId": "c", "value": 4, "justification": "j",
                           "evidence": CITED}],
                   procedure={"round": 1, "prior": "shown"})
    ids = [r["id"] for r in _merged(store)["rounds"]]
    assert ids == ["bot:round-1", "bot:round-1-bot:the-buyer"]


def test_stating_the_prior_after_the_fact_completes_a_round_and_a_restatement_names_the_truth(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "session": "fresh"})
    _score(store, BOT, 3, procedure={"round": 1, "session": "fresh", "prior": "withheld"})
    assert _merged(store)["rounds"][0]["feedback"] == "none"
    with pytest.raises(ValueError, match="prior withheld"):
        _score(store, BOT, 3, procedure={"round": 1, "prior": "shown"})


def test_only_a_perturbed_draw_gets_a_perturbation_record(store) -> None:
    _score(store, BOT, 3, procedure={"round": 1, "session": "same", "seed": 5})
    _score(store, BOT, 3, procedure={"round": 2, "session": "fresh", "seed": 5}, independence="resampled")
    assert all("perturbation" not in a for a in _assertions(store))


def test_traversal_and_reduction_are_checked_for_a_direct_caller(store) -> None:
    with pytest.raises(ValueError, match="procedure.reduction"):
        _score(store, BOT, 3, procedure={"reduction": "mean"})
    with pytest.raises(ValueError, match="procedure.traversal"):
        _score(store, BOT, 3, procedure={"traversal": "bogus"})


def test_a_model_id_differing_only_in_case_or_space_is_the_same_model(store) -> None:
    _score(store, BOT, 3, independence="resampled")
    twin = agent("twin", "Twin", name="rubricator", model=" Model-A ")
    with pytest.raises(ValueError, match="independent-agent-is-distinct"):
        _score(store, twin, 4, independence="independent")
