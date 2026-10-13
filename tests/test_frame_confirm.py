"""Tool 8 (#57): ``frame_confirm`` -- the ADR-0005 step-4 gate.

What these hold: no argument combination confirms on the model's say-so; a
decision is recorded only in answer to a question asked since the last one,
with who gave it and their words; a resuming session reads the record rather
than re-asking; and ``measures_write`` writes nothing until the gate is open
or the analysis was opened with the explicit skip.
"""

from __future__ import annotations

import asyncio
import itertools
import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind
from rubricator.tools.confirm import OUT_OF_BAND_INSTRUCTIONS, SCOPES

#: A span every scored cell here cites: since #171 a value with no evidence is refused.
CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]

MOMENT = "2026-08-22T12:00:00Z"
AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
CELL = {"alternativeId": "k1", "criterionId": "speed", "value": 4, "justification": "spec sheet",
        "evidence": CITED}


def _verbs(blobs=None):
    runtime = build_runtime(blobs={} if blobs is None else blobs, now=fixed_clock(MOMENT))
    return runtime, bind(runtime)


def _framed(verbs, **open_kwargs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", **open_kwargs)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k1", "label": "Kettle one"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "speed", "label": "Speed", "anchors": ANCHORS}])


def _score(verbs):
    return verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR, cells=[CELL])


def _ask_and_answer(verbs, decision="confirm", scope="all"):
    verbs["frame_confirm"](analysis_id="a1", scope=scope)
    return verbs["frame_confirm"](analysis_id="a1", scope=scope, decision=decision,
                                  confirmed_by="ana", confirmation_text="Yes, go ahead.")


# --- a confirmation cannot be fabricated --------------------------------------

_DECISIONS = [None, "confirm", "revise", "reject"]
_BLANKS = [None, "", "   ", "ana"]


@pytest.mark.parametrize("scope", SCOPES)
def test_no_single_call_confirms_whatever_its_arguments(scope) -> None:
    """One call can never pass the gate: the question must have been put to a person first."""
    for decision, by, text in itertools.product(_DECISIONS, _BLANKS, _BLANKS):
        _, verbs = _verbs()
        _framed(verbs)
        kwargs = {k: v for k, v in (("decision", decision), ("confirmed_by", by),
                                    ("confirmation_text", text)) if v is not None}
        got = verbs["frame_confirm"](analysis_id="a1", scope=scope, **kwargs)
        assert got["confirmed"] is False, (scope, decision, by, text)
        with pytest.raises(ValueError, match="not confirmed"):
            _score(verbs)


def test_after_the_question_only_a_named_verbatim_confirm_of_everything_opens_the_gate() -> None:
    opened = []
    for scope, decision, by, text in itertools.product(SCOPES, _DECISIONS[1:], _BLANKS, _BLANKS):
        _, verbs = _verbs()
        _framed(verbs)
        verbs["frame_confirm"](analysis_id="a1", scope=scope)
        kwargs = {k: v for k, v in (("confirmed_by", by), ("confirmation_text", text)) if v is not None}
        got = verbs["frame_confirm"](analysis_id="a1", scope=scope, decision=decision, **kwargs)
        if got["confirmed"]:
            opened.append((scope, decision, by, text))
    assert opened == [("all", "confirm", "ana", "ana")]


def test_an_answer_needs_a_question_asked_since_the_last_answer() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs, decision="revise")
    stale = verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                   confirmation_text="fine now")
    assert stale["confirmed"] is False and "not been put to the user" in stale["summary"]
    assert _ask_and_answer(verbs)["confirmed"] is True


# --- the out-of-band path -----------------------------------------------------


def test_the_out_of_band_instructions_can_be_followed_without_further_design() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    got = verbs["frame_confirm"](analysis_id="a1")
    assert (got["confirmed"], got["mechanism"], got["record"]) == (False, "out-of-band", None)
    assert got["instructions"] == OUT_OF_BAND_INSTRUCTIONS
    for must in ("every alternative", "every criterion", "overlap", "confirm, revise",
                 "Do not answer for them", "confirmed_by", "confirmation_text", "word for word"):
        assert must in got["instructions"], must


def test_the_record_is_authored_timestamped_and_carries_the_criteria_version() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    got = _ask_and_answer(verbs)
    assert got["record"] == {
        "authorId": "ana", "at": MOMENT, "text": "Yes, go ahead.", "criteriaVersion": "1",
        "decision": "confirm", "scope": "all", "mechanism": "out-of-band",
    }


def test_a_resuming_session_does_not_re_ask_and_writes_nothing() -> None:
    blobs: dict[str, bytes] = {}
    _, verbs = _verbs(blobs)
    _framed(verbs)
    _ask_and_answer(verbs)
    before = dict(blobs)
    _, resumed = _verbs(blobs)
    got = resumed["frame_confirm"](analysis_id="a1")
    assert (got["confirmed"], got["mechanism"], got["instructions"]) == (True, "recorded", None)
    assert got["record"]["authorId"] == "ana" and "nothing to ask" in got["summary"]
    assert dict(blobs) == before
    assert resumed["analysis_get"](analysis_id="a1")["stage"] == 5


def test_a_partial_confirmation_names_what_is_still_open() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    got = _ask_and_answer(verbs, scope="criteria")
    assert got["confirmed"] is False and "frame, alternatives" in got["instructions"]
    _ask_and_answer(verbs, scope="frame")
    assert _ask_and_answer(verbs, scope="alternatives")["confirmed"] is True


# --- the gate on measures_write -----------------------------------------------


def test_measures_write_refuses_before_confirmation_and_writes_nothing() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    with pytest.raises(ValueError, match="nothing was written.*not confirmed.*frame_confirm"):
        _score(verbs)
    with pytest.raises(ValueError, match="not confirmed"):
        verbs["measures_mark_missing"](analysis_id="a1", contributor_id="ana", author=AUTHOR,
                                       code="deferred", note="later")
    assert not [k for k in runtime.store.blobs if "/contributions/" in k]
    _ask_and_answer(verbs)
    assert _score(verbs)["written"] == 1


def test_a_revise_after_a_confirm_closes_the_gate_again() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    _ask_and_answer(verbs, decision="revise")
    with pytest.raises(ValueError, match="not confirmed"):
        _score(verbs)


def test_a_criteria_revision_keeps_the_gate_open_and_says_the_set_moved() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Speed from cold", "anchors": ANCHORS}])
    assert _score(verbs)["criteriaVersion"] == "2"
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["confirmed"] is True and 'now at "2"' in got["summary"]
    assert got["instructions"] == OUT_OF_BAND_INSTRUCTIONS
    # Following that advice records a fresh confirm of the new version.
    again = verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                   confirmation_text="Yes, version 2 too.")
    assert again["record"]["criteriaVersion"] == "2"
    assert "nothing to ask" in verbs["frame_confirm"](analysis_id="a1")["summary"]


# --- the explicit skip --------------------------------------------------------


def test_the_skip_is_explicit_at_creation_and_never_a_human_confirmation() -> None:
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    assert _score(verbs)["written"] == 1
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["confirmed"] is True and got["record"]["authorId"] == "agent"
    assert got["record"]["mechanism"] == "skip-at-open"
    # The summary says what happened: a skip, not a confirmation (#187).
    assert "skipped at open" in got["summary"] and "nobody confirmed" in got["summary"]
    assert "already confirmed" not in got["summary"]
    # Retrying the same create is fine; adding a skip to an existing analysis is not.
    verbs["analysis_open"](analysis_id="a1", allow_skip_confirmation=True)
    verbs["analysis_open"](analysis_id="b1", question="q")
    with pytest.raises(ValueError, match="only be chosen when an analysis is created"):
        verbs["analysis_open"](analysis_id="b1", allow_skip_confirmation=True)


def test_a_partial_confirm_after_the_skip_does_not_launder_the_rest() -> None:
    """The frame and alternatives still rest on the skip: the summary says so (#187)."""
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1", decision="revise", scope="criteria", confirmed_by="ana",
                           confirmation_text="Tighten the criteria first.")
    verbs["frame_confirm"](analysis_id="a1")  # put the question again
    verbs["frame_confirm"](analysis_id="a1", decision="confirm", scope="criteria", confirmed_by="ana",
                           confirmation_text="Yes, the criteria are right.")
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["confirmed"] is True
    assert "frame, alternatives: skipped at open" in got["summary"]
    assert "nobody confirmed the frame, alternatives" in got["summary"]
    assert "criteria: confirmed by ana" in got["summary"]
    assert "already confirmed" not in got["summary"]


def test_the_gate_and_stage_four_show_on_analysis_get() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    summary = verbs["analysis_get"](analysis_id="a1")
    assert summary["stage"] == 4 and "frame_confirm" in summary["summary"]
    assert verbs["analysis_open"](analysis_id="a1")["stage"] == 4


# --- the document stays valid, and the records stay beside it -----------------


def test_the_confirmation_lives_beside_a_document_that_still_validates() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    document = runtime.store.read("a1")
    assert document["createdAt"] == MOMENT
    assert "confirm" not in json.dumps(document)
    result = runtime.schema.validate(document)
    assert result.ok, result.report()


def test_same_calls_give_byte_identical_results() -> None:
    def run():
        _, verbs = _verbs()
        _framed(verbs)
        return [verbs["frame_confirm"](analysis_id="a1"), _ask_and_answer(verbs),
                verbs["frame_confirm"](analysis_id="a1")]
    assert json.dumps(run()) == json.dumps(run())


def test_over_mcp_a_client_without_elicitation_gets_the_out_of_band_path() -> None:
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    asyncio.run(server.call_tool("analysis_open", {"analysis_id": "a1", "question": "q"}))
    got = asyncio.run(server.call_tool("frame_confirm", {"analysis_id": "a1"})).structured_content
    assert (got["confirmed"], got["mechanism"]) == (False, "out-of-band")


# --- the review's findings, kept failing-able ----------------------------------


def test_two_branches_answering_the_gate_leave_two_files_and_a_revise_survives() -> None:
    """ADR-0017: no two contributors write the same key, so git cannot drop a revise."""
    base: dict[str, bytes] = {}
    _, verbs = _verbs(base)
    _framed(verbs)
    _ask_and_answer(verbs)
    ana, ben = dict(base), dict(base)
    _ask_and_answer(_verbs(ana)[1], decision="revise")
    _ask_and_answer(_verbs(ben)[1], decision="reject")
    new_ana = {k for k in ana if k.endswith(".json") and "/confirmations/" in k} - set(base)
    new_ben = {k for k in ben if k.endswith(".json") and "/confirmations/" in k} - set(base)
    assert len(new_ana) == len(new_ben) == 1 and new_ana.isdisjoint(new_ben)
    merged = {**ana, **ben}  # what a clean git merge leaves: both files
    _, after = _verbs(merged)
    with pytest.raises(ValueError, match="not confirmed"):
        _score(after)


def test_a_future_dated_confirm_cannot_outrank_a_later_revise() -> None:
    """Order is write order, never a caller-supplied moment."""
    _, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                           confirmation_text="yes", at="2099-01-01T00:00:00Z")
    _ask_and_answer(verbs, decision="revise")
    with pytest.raises(ValueError, match="not confirmed"):
        _score(verbs)


@pytest.mark.parametrize("raw", [
    b"not json", b"[]", b'{"decision": "confirm", "scope": "all"}',
    b'{"decision": "confirm", "scope": "all", "authorId": " ", "text": "x", "at": "t"}',
    b'{"decision": "skip", "scope": "all", "at": "t"}',
])
def test_a_malformed_record_closes_the_gate_and_locks_nothing_else(raw) -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    runtime.store.blobs["analyses/a1/confirmations/000099-zz.json"] = raw
    with pytest.raises(ValueError, match="cannot be read as a decision"):
        _score(verbs)
    assert verbs["analysis_open"](analysis_id="a1")["stage"] == 4
    assert verbs["analysis_get"](analysis_id="a1")["stage"] == 4
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["confirmed"] is False and got["record"] is None


def test_a_new_analysis_inherits_no_leftover_confirmation() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    for key in [k for k in runtime.store.blobs if "/confirmations/" not in k]:
        del runtime.store.blobs[key]  # the frame removed outside the surface
    _framed(verbs)
    with pytest.raises(ValueError, match="not confirmed"):
        _score(verbs)


def test_a_skip_overruled_by_a_later_revise_cannot_be_reasserted_on_reopen() -> None:
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    _ask_and_answer(verbs, decision="revise")
    with pytest.raises(ValueError, match="closed the gate since"):
        verbs["analysis_open"](analysis_id="a1", allow_skip_confirmation=True)


def test_removing_a_record_never_lets_a_later_revise_sort_earlier() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    first = min(k for k in runtime.store.blobs if k.endswith(".json") and "/confirmations/" in k)
    del runtime.store.blobs[first]  # "repair or remove", as the gate's message says
    _ask_and_answer(verbs, decision="revise")
    with pytest.raises(ValueError, match="not confirmed"):
        _score(verbs)


@pytest.mark.parametrize("text", [f"take {i}" for i in range(8)])
def test_a_confirm_and_a_revise_at_one_sequence_merge_to_closed(text) -> None:
    """Two branches from one question: the tie is resolved toward caution, not by digest."""
    base: dict[str, bytes] = {}
    _, verbs = _verbs(base)
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    ana, ben = dict(base), dict(base)
    _verbs(ana)[1]["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                    confirmation_text=text)
    _verbs(ben)[1]["frame_confirm"](analysis_id="a1", decision="revise", confirmed_by="ben",
                                    confirmation_text=text)
    with pytest.raises(ValueError, match="not confirmed"):
        _score(_verbs({**ana, **ben})[1])


def test_a_record_with_a_non_string_decision_is_invalid_not_a_crash() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    runtime.store.blobs["analyses/a1/confirmations/000099-zz.json"] = json.dumps(
        {"decision": ["confirm"], "scope": "all", "authorId": "a", "text": "t", "at": MOMENT}).encode()
    assert verbs["analysis_open"](analysis_id="a1")["stage"] == 4
    with pytest.raises(ValueError, match="cannot be read as a decision"):
        _score(verbs)


# --- what a confirmation covered (#195) ---------------------------------------


def _swap_everything(verbs) -> None:
    """The review's case: retire every confirmed row and column, declare new ones."""
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one", "tombstoned": True}, {"id": "k2", "label": "Kettle two"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Speed", "anchors": ANCHORS, "tombstoned": True},
        {"id": "support", "label": "Support", "anchors": ANCHORS}])


def test_a_swapped_frame_is_put_to_the_user_again_not_reported_confirmed() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    _swap_everything(verbs)
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["instructions"] == OUT_OF_BAND_INSTRUCTIONS
    assert "nothing to ask" not in got["summary"]
    assert "alternatives added or changed: k2" in got["summary"]
    assert "criteria added: support" in got["summary"]
    # A fresh confirm answers the new question, and covers what is there now.
    again = verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                   confirmation_text="Yes, the new ones too.")
    assert again["confirmed"] is True
    assert "nothing to ask" in verbs["frame_confirm"](analysis_id="a1")["summary"]


def test_retiring_a_confirmed_row_asks_nothing_new() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two"}])
    _ask_and_answer(verbs)
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one"}, {"id": "k2", "label": "Kettle two", "tombstoned": True}])
    assert "nothing to ask" in verbs["frame_confirm"](analysis_id="a1")["summary"]


def test_a_reworded_frame_is_put_to_the_user_again() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    verbs["frame_set"](analysis_id="a1", ambiguities=[], decision="buy two, not one")
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["instructions"] == OUT_OF_BAND_INSTRUCTIONS and "frame's question" in got["summary"]


def test_a_record_that_kept_nothing_is_asked_again_rather_than_trusted() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    for key in runtime.store._confirmation_keys("a1"):
        record = json.loads(runtime.store.blobs[key])
        record.pop("covered", None)
        runtime.store.blobs[key] = json.dumps(record).encode()
    assert verbs["frame_confirm"](analysis_id="a1")["instructions"] == OUT_OF_BAND_INSTRUCTIONS


@pytest.mark.parametrize("change", [
    lambda v: v["frame_set"](analysis_id="a1", ambiguities=[], context="no budget limit"),
    lambda v: v["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k1", "label": "Kettle one", "description": "a 0.5 l travel kettle"}]),
])
def test_a_changed_context_or_row_description_is_put_to_the_user_again(change) -> None:
    """The review of #196: both read as already confirmed."""
    _, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    change(verbs)
    assert verbs["frame_confirm"](analysis_id="a1")["instructions"] == OUT_OF_BAND_INSTRUCTIONS


# --- two parts in one reply, and a confirmation after the skip (#206) ----------


def _decisions(runtime):
    return [(r["decision"], r["scope"]) for r in runtime.store.confirmations("a1") if r["decision"] != "requested"]


def _requests(runtime):
    return [r for r in runtime.store.confirmations("a1") if r["decision"] == "requested"]


@pytest.mark.parametrize("scope, parts, closed", [
    ("frame+alternatives", ["frame", "alternatives"], ["criteria"]),
    ("frame+criteria", ["frame", "criteria"], ["alternatives"]),
    ("alternatives+criteria", ["alternatives", "criteria"], ["frame"]),
])
def test_two_parts_confirmed_in_one_reply_are_recorded_in_one_call(scope, parts, closed) -> None:
    """One question, one answer, two parts: no second no-decision call, no request for a question never put."""
    runtime, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    got = verbs["frame_confirm"](analysis_id="a1", scope=scope, decision="confirm", confirmed_by="ana",
                                 confirmation_text="The frame and the criteria are right; the rest I'll check.")
    assert got["confirmed"] is False and f"Still to confirm: {closed[0]}" in got["instructions"]
    assert _decisions(runtime) == [("confirm", p) for p in parts]
    assert len(_requests(runtime)) == 1, "the one question that was asked"
    assert {r["text"] for r in runtime.store.confirmations("a1") if r["decision"] == "confirm"} == {
        "The frame and the criteria are right; the rest I'll check."}
    with pytest.raises(ValueError, match=closed[0]):
        _score(verbs)


def test_the_third_part_still_needs_its_own_question() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="frame+criteria", decision="confirm",
                           confirmed_by="ana", confirmation_text="Those two are right.")
    again = verbs["frame_confirm"](analysis_id="a1", scope="alternatives", decision="confirm",
                                   confirmed_by="ana", confirmation_text="Yes, the kettles too.")
    assert again["record"] is None and "has not been put to the user" in again["summary"]
    verbs["frame_confirm"](analysis_id="a1", scope="alternatives")
    done = verbs["frame_confirm"](analysis_id="a1", scope="alternatives", decision="confirm",
                                  confirmed_by="ana", confirmation_text="Yes, the kettles too.")
    assert done["confirmed"] is True and _score(verbs)["written"] == 1


def test_a_request_for_one_part_does_not_license_confirming_two() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1", scope="criteria")
    got = verbs["frame_confirm"](analysis_id="a1", scope="frame+criteria", decision="confirm",
                                 confirmed_by="ana", confirmation_text="Both are right.")
    assert got["record"] is None and not _decisions(runtime)


def test_a_request_for_a_pair_licenses_either_part_of_it_and_the_pair() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1", scope="frame+criteria")
    got = verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm",
                                 confirmed_by="ana", confirmation_text="The criteria are right.")
    assert got["record"]["scope"] == "criteria"


def test_a_joined_scope_revise_closes_both_parts() -> None:
    runtime, verbs = _verbs()
    _framed(verbs)
    _ask_and_answer(verbs)
    assert _score(verbs)["written"] == 1
    verbs["frame_confirm"](analysis_id="a1", scope="frame+alternatives", decision="revise",
                           confirmed_by="ana", confirmation_text="Change the question and the kettles.")
    with pytest.raises(ValueError, match="frame, alternatives"):
        _score(verbs)


def test_a_stored_decision_with_a_joined_scope_is_invalid_and_closes_the_gate() -> None:
    """The writer splits a joined scope; a hand-edited record that keeps it is a record the gate cannot read."""
    runtime, verbs = _verbs()
    _framed(verbs)
    runtime.store.add_confirmation("a1", {"decision": "confirm", "scope": "frame+criteria", "authorId": "ana",
                                         "at": MOMENT, "text": "x", "mechanism": "out-of-band"})
    with pytest.raises(ValueError, match="cannot be read"):
        _score(verbs)


def test_a_confirmation_offered_after_the_skip_is_recorded_as_a_persons() -> None:
    runtime, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    skipped = verbs["frame_confirm"](analysis_id="a1")
    assert skipped["confirmed"] is True and skipped["instructions"] is None
    assert "can be recorded now" in skipped["summary"] and len(_requests(runtime)) == 1
    verbs["frame_confirm"](analysis_id="a1")
    assert len(_requests(runtime)) == 1, "asked once per pending question"
    got = verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                 confirmation_text="I've read it now and it's right.")
    assert got["record"]["authorId"] == "ana" and got["record"]["mechanism"] == "out-of-band"
    after = verbs["frame_confirm"](analysis_id="a1")
    assert "already confirmed by ana" in after["summary"] and "skipped" not in after["summary"]


def test_the_skip_read_asks_for_nothing_and_a_blind_confirm_is_still_refused() -> None:
    """Scoring stays open; and without that read, a confirm nobody was invited to give is not recorded."""
    runtime, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    blind = verbs["frame_confirm"](analysis_id="a1", decision="confirm", confirmed_by="ana",
                                   confirmation_text="Confirmed.")
    assert blind["record"] is None and "has not been put to the user yet" in blind["summary"]
    assert not _decisions(runtime) or all(d[0] == "skip" for d in _decisions(runtime))
    assert _score(verbs)["written"] == 1


def test_a_partial_confirm_after_the_skip_still_names_what_rests_on_it() -> None:
    runtime, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="frame+criteria", decision="confirm", confirmed_by="ana",
                           confirmation_text="Those two are right.")
    got = verbs["frame_confirm"](analysis_id="a1")
    assert "alternatives: skipped at open" in got["summary"] and "frame, criteria: confirmed by ana" in got["summary"]


def test_the_frozen_row_offers_exactly_the_scopes_the_tool_takes() -> None:
    from rubricator.surface.frozen import FROZEN_TOOLS

    row = next(t for t in FROZEN_TOOLS if t.name == "frame_confirm")
    assert tuple(row.input_schema["properties"]["scope"]["enum"]) == SCOPES


def test_a_read_after_the_skip_does_not_reopen_a_part_a_person_confirmed() -> None:
    """The review of #206: a request for criteria after Ana confirmed them let a second name overwrite hers."""
    runtime, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm", confirmed_by="ana",
                           confirmation_text="The criteria are right.")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria")
    again = verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm",
                                   confirmed_by="bob", confirmation_text="Confirmed.")
    assert again["record"] is None and "has not been put to the user yet" in again["summary"]
    assert "criteria: confirmed by ana" in verbs["frame_confirm"](analysis_id="a1")["summary"]
    assert [r["scope"] for r in _requests(runtime)] == ["all", "frame+alternatives"], \
        "the invitation names the parts that rest on the skip, and only them"


def test_a_part_still_resting_on_the_skip_can_be_confirmed_after_a_person_confirmed_another() -> None:
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm", confirmed_by="ana",
                           confirmation_text="The criteria are right.")
    verbs["frame_confirm"](analysis_id="a1")
    got = verbs["frame_confirm"](analysis_id="a1", scope="frame+alternatives", decision="confirm",
                                 confirmed_by="ana", confirmation_text="And the rest, yes.")
    assert got["record"]["authorId"] == "ana"
    assert "skipped" not in verbs["frame_confirm"](analysis_id="a1")["summary"]


def test_record_decision_takes_one_part_and_says_why_it_refuses_a_pair() -> None:
    from rubricator.tools.confirm import record_decision

    runtime, verbs = _verbs()
    _framed(verbs)
    with pytest.raises(ValueError, match="record a pair as one record per part"):
        record_decision(runtime.store, analysis_id="a1", at=MOMENT, scope="frame+criteria",
                        decision="confirm", author_id="ana", text="x", mechanism="elicitation")
    assert not runtime.store.confirmations("a1")


def test_a_joined_confirm_says_what_it_recorded_and_the_scope_to_ask_for_next() -> None:
    _, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    got = verbs["frame_confirm"](analysis_id="a1", scope="frame", decision="confirm", confirmed_by="ana",
                                 confirmation_text="The frame is right.")
    assert "Call frame_confirm with scope alternatives+criteria." in got["instructions"]
    verbs["frame_confirm"](analysis_id="a1", scope="alternatives+criteria")
    both = verbs["frame_confirm"](analysis_id="a1", scope="alternatives+criteria", decision="confirm",
                                  confirmed_by="ana", confirmation_text="Those two as well.")
    assert both["confirmed"] is True


def test_scope_of_is_the_inverse_of_parts_of() -> None:
    from rubricator.tools.confirm import parts_of, scope_of

    assert all(scope_of(parts_of(s)) == s for s in SCOPES)


def test_the_moved_since_read_does_not_report_the_skip_as_a_confirmation_by_the_agent() -> None:
    """The second review of #206: it said 'confirmed by agent' for a part that rested on the skip."""
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="frame", decision="confirm", confirmed_by="ana",
                           confirmation_text="The frame is right.")
    verbs["frame_set"](analysis_id="a1", ambiguities=["does it matter?"])
    got = verbs["frame_confirm"](analysis_id="a1")
    assert "confirmed by agent" not in got["summary"]
    assert "frame: confirmed by ana" in got["summary"] and "skipped at open" in got["summary"]
    assert got["instructions"] and "the frame's question, decision, decider, context or ambiguities changed" in got["summary"]


def test_a_mixed_state_read_names_each_parts_own_record() -> None:
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm", confirmed_by="ana",
                           confirmation_text="The criteria are right.")
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["record"]["authorId"] == "ana"
    assert "nobody confirmed the frame, alternatives" in got["summary"] and "criteria: confirmed by ana" in got["summary"]


def test_the_result_of_a_decision_names_each_parts_own_confirmation() -> None:
    """The third review of #206: 'confirmed by bob: scoring may start' for parts Alice confirmed."""
    _, verbs = _verbs()
    _framed(verbs)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="frame+alternatives", decision="confirm",
                           confirmed_by="alice", confirmation_text="Those two are right.")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria")
    done = verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm", confirmed_by="bob",
                                  confirmation_text="The criteria too.")
    assert done["confirmed"] is True and "scoring may start" in done["summary"]
    assert "frame, alternatives: confirmed by alice" in done["summary"] and "criteria: confirmed by bob" in done["summary"]
    assert "confirmed by bob:" not in done["summary"].replace("criteria: confirmed by bob", "")


def test_the_skip_read_names_the_scope_to_record_under_and_a_whole_confirm_is_told_what_is_pending() -> None:
    runtime, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    verbs["frame_confirm"](analysis_id="a1")
    verbs["frame_confirm"](analysis_id="a1", scope="criteria", decision="confirm", confirmed_by="ana",
                           confirmation_text="The criteria are right.")
    read = verbs["frame_confirm"](analysis_id="a1")
    assert "scope frame+alternatives" in read["summary"]
    refused = verbs["frame_confirm"](analysis_id="a1", scope="all", decision="confirm", confirmed_by="ana",
                                     confirmation_text="Everything looks right.")
    assert refused["record"] is None
    assert "put for frame+alternatives only" in refused["summary"]
    ok = verbs["frame_confirm"](analysis_id="a1", scope="frame+alternatives", decision="confirm",
                                confirmed_by="ana", confirmation_text="Everything looks right.")
    assert ok["confirmed"] is True and "skipped" not in ok["summary"]
