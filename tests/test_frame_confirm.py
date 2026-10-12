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

MOMENT = "2026-08-22T12:00:00Z"
AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
CELL = {"alternativeId": "k1", "criterionId": "speed", "value": 4, "justification": "spec sheet"}


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
    assert got["confirmed"] is True and 'from version "1" to "2"' in got["summary"]


# --- the explicit skip --------------------------------------------------------


def test_the_skip_is_explicit_at_creation_and_never_a_human_confirmation() -> None:
    _, verbs = _verbs()
    _framed(verbs, allow_skip_confirmation=True)
    assert _score(verbs)["written"] == 1
    got = verbs["frame_confirm"](analysis_id="a1")
    assert got["confirmed"] is True and got["record"]["authorId"] == "agent"
    assert got["record"]["mechanism"] == "skip-at-open"
    # Retrying the same create is fine; adding a skip to an existing analysis is not.
    verbs["analysis_open"](analysis_id="a1", allow_skip_confirmation=True)
    verbs["analysis_open"](analysis_id="b1", question="q")
    with pytest.raises(ValueError, match="only be chosen when an analysis is created"):
        verbs["analysis_open"](analysis_id="b1", allow_skip_confirmation=True)


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
