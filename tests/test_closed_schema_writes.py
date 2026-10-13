"""Every write path refuses what the closed comparanda v1 schema would refuse (#136).

v1 closes every object (``additionalProperties: false``). A verb that copies a
caller's dict into the document verbatim would otherwise store an analysis its
own renderer refuses, and a verb that reads a dict field by field would drop an
extra key without a word. Each write path is exercised twice: through ``bind``,
where the frozen input schema refuses at the boundary, and as a direct Python
call, where the verb itself must refuse -- with the path, the fix, and nothing
stored.
"""

from __future__ import annotations

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind
from rubricator.tools.analysis import (
    alternatives_set,
    criteria_set,
    frame_set,
    measures_mark_missing,
    measures_write,
)

MOMENT = "2026-08-22T12:00:00Z"
AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "a"}, {"level": "3", "text": "b"}, {"level": "5", "text": "c"}]
DECLARATION = {"id": "vendor-silent", "broader": "not-evidenced", "means": "the vendor says nothing"}
EVIDENCE = {"id": "e1", "target": "rendition:r", "sourceType": "primary", "stance": "supports",
            "selectors": [{"type": "TextQuoteSelector", "exact": "until 2029"}]}


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    return rt


@pytest.fixture()
def verbs(runtime):
    return bind(runtime)


def _unchanged(runtime, call, match: str) -> None:
    """``call`` is refused with ``match`` and the store is byte-for-byte as it was."""
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=match):
        call()
    assert dict(runtime.store.blobs) == before


def _cell(**extra):
    return {"alternativeId": "x", "criterionId": "c", "value": 5, "justification": "dated",
            "evidence": [dict(EVIDENCE)], **extra}


# -- through bind: the frozen input schema refuses at the boundary -------------------------------

@pytest.mark.parametrize("name, arguments, where", [
    ("alternatives_set", {"alternatives": [{"id": "x", "label": "X", "url": "u"}]},
     r"\$\.alternatives\[0\]"),
    ("criteria_set", {"criteria": [{"id": "c", "label": "C", "anchors": ANCHORS,
                                    "missingCodes": [{**DECLARATION, "notes": "n"}]}]},
     r"\$\.criteria\[0\]\.missingCodes\[0\]"),
    ("criteria_set", {"criteria": [{"id": "c", "label": "C", "anchors": ANCHORS, "notes": "n"}]},
     r"\$\.criteria\[0\]"),
    ("measures_write", {"contributor_id": "ana", "author": AUTHOR, "cells": [_cell(plan="p")]},
     r"\$\.cells\[0\]"),
    ("measures_write", {"contributor_id": "ana", "author": AUTHOR,
                        "cells": [_cell(evidence=[{**EVIDENCE, "url": "u"}])]},
     r"\$\.cells\[0\]\.evidence\[0\]"),
    ("measures_write", {"contributor_id": "ana", "author": AUTHOR, "cells": [{
        "alternativeId": "x", "criterionId": "c",
        "missing": {"code": "not-evidenced", "note": "silent", "reason": "r"}}]},
     r"\$\.cells\[0\]\.missing"),
    ("measures_mark_missing", {"contributor_id": "ana", "author": {**AUTHOR, "avatar": "a"},
                               "code": "not-evidenced", "note": "silent"},
     r"\$\.author"),
])
def test_an_extra_key_is_refused_at_the_boundary(runtime, verbs, name, arguments, where) -> None:
    _unchanged(
        runtime, lambda: verbs[name](analysis_id="a1", **arguments),
        rf"refused: {name}: at {where}: Additional properties .* Allowed here: ",
    )


# -- direct Python calls: the verb itself refuses -------------------------------------------------

def test_an_alternative_key_v1_has_no_slot_for_is_refused_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: alternatives_set(runtime.store, analysis_id="a1",
                                 alternatives=[{"id": "x", "label": "X", "url": "u"}]),
        r"refused, nothing was written: .*comparanda v1.* at \$\.alternatives\[0\]: Additional "
        r"properties are not allowed \('url' was unexpected\)\. Allowed here: description, ",
    )


def test_a_missing_code_declaration_key_is_refused_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: criteria_set(runtime.store, analysis_id="a1", criteria=[
            {"id": "c", "label": "C", "anchors": ANCHORS,
             "missingCodes": [{**DECLARATION, "notes": "n"}]}]),
        r"at \$\.criteria\[0\]\.missingCodes\[0\]: .*'notes' was unexpected.*Allowed here: ",
    )


def test_a_criterion_key_the_verb_would_drop_is_refused(runtime) -> None:
    _unchanged(
        runtime,
        lambda: criteria_set(runtime.store, analysis_id="a1", criteria=[
            {"id": "c", "label": "C", "anchors": ANCHORS, "weight": 2}]),
        r"refused, nothing was written: at \$\.criteria\[0\]: 'weight' is not recorded anywhere\. "
        r"Allowed here: anchors, ",
    )


def test_a_frame_value_v1_refuses_is_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: frame_set(runtime.store, analysis_id="a1", ambiguities=[{"text": "which scope?"}]),
        r"at \$\.subject\.ambiguities\[0\]: .* is not of type 'string'",
    )


@pytest.mark.parametrize("extra", ["plan", "confidence"])
def test_a_cell_key_the_verb_would_drop_is_refused(runtime, extra) -> None:
    """score-cell v1 asked for both inside the cell; neither has a slot in v1, so neither may vanish silently."""
    _unchanged(
        runtime,
        lambda: measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                               author=AUTHOR, at=MOMENT, cells=[_cell(**{extra: "high"})]),
        rf"at \$\.cells\[0\]: '{extra}' is not recorded anywhere\. Allowed here: alternativeId, ",
    )


def test_an_evidence_key_v1_has_no_slot_for_is_refused_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                               author=AUTHOR, at=MOMENT,
                               cells=[_cell(evidence=[{**EVIDENCE, "url": "u"}])]),
        r"at \$\.cells\[0\]\.evidence\[0\]: .*'url' was unexpected.*Allowed here: check, ",
    )


def test_a_missing_key_v1_has_no_slot_for_is_refused_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                               author=AUTHOR, at=MOMENT, cells=[{
                                   "alternativeId": "x", "criterionId": "c",
                                   "missing": {"code": "not-evidenced", "note": "n", "reason": "r"}}]),
        r"at \$\.cells\[0\]\.missing: .*'reason' was unexpected.*Allowed here: code, note",
    )


def test_an_author_key_v1_has_no_slot_for_is_refused_not_stored(runtime) -> None:
    _unchanged(
        runtime,
        lambda: measures_mark_missing(runtime.store, analysis_id="a1", contributor_id="ana",
                                      author={**AUTHOR, "avatar": "a"}, at=MOMENT,
                                      code="not-evidenced", note="silent"),
        r"at \$\.author: .*'avatar' was unexpected.*Allowed here: actingAs, ",
    )


def test_every_problem_is_reported_in_one_pass(runtime) -> None:
    """A caller fixing a model's output wants the whole list, not one round-trip per key."""
    with pytest.raises(ValueError) as refused:
        measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                       author={**AUTHOR, "avatar": "a"}, at=MOMENT,
                       cells=[_cell(evidence=[{**EVIDENCE, "url": "u"}])])
    assert "$.author" in str(refused.value) and "$.cells[0].evidence[0]" in str(refused.value)


def test_a_write_v1_accepts_still_lands(runtime) -> None:
    result = measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                            author=AUTHOR, at=MOMENT, cells=[_cell()])
    assert result["written"] == 1
    assert runtime.schema.validate(runtime.store.read("a1")).ok


# -- from the adversarial review of #155 ---------------------------------------------------------

def _store_off_contract(runtime) -> None:
    """A frame as a build before #136 could have stored it: two problems, in two verbs' parts."""
    frame = runtime.store.frame("a1")
    frame["alternatives"][0]["url"] = "u"
    frame["criteria"][0]["missingCodes"] = [{**DECLARATION, "notes": "n"}]
    runtime.store.put_frame("a1", frame)


def test_a_problem_already_stored_does_not_lock_later_writes(runtime) -> None:
    """Each verb repairs only its own part, so refusing over the other's would deadlock."""
    _store_off_contract(runtime)
    frame_set(runtime.store, analysis_id="a1", ambiguities=["scope?"])
    alternatives_set(runtime.store, analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    criteria_set(runtime.store, analysis_id="a1",
                 criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    assert runtime.schema.validate(runtime.store.frame("a1")).ok


def test_a_problem_already_stored_does_not_excuse_a_new_one(runtime) -> None:
    _store_off_contract(runtime)
    _unchanged(
        runtime,
        lambda: alternatives_set(runtime.store, analysis_id="a1", alternatives=[
            {"id": "x", "label": "X", "url": "u"}, {"id": "y", "label": "Y", "colour": "c"}]),
        r"'colour' was unexpected",
    )


def test_an_anchor_row_key_the_verb_would_drop_is_refused(runtime) -> None:
    _unchanged(
        runtime,
        lambda: criteria_set(runtime.store, analysis_id="a1", criteria=[
            {"id": "c", "label": "C",
             "anchors": [{**ANCHORS[0], "note": "keep me"}, *ANCHORS[1:]]}]),
        r"at \$\.criteria\[0\]\.anchors\[0\]: 'note' is not recorded anywhere\. "
        r"Allowed here: level, text",
    )


def test_a_tuple_is_an_array_once_stored(runtime) -> None:
    alternatives_set(runtime.store, analysis_id="a1",
                     alternatives=[{"id": "x", "label": "X", "groupIds": ("g",)}])
    assert runtime.store.frame("a1")["alternatives"][0]["groupIds"] == ["g"]


def test_an_argument_is_named_at_its_own_path_once(runtime) -> None:
    with pytest.raises(ValueError) as refused:
        measures_write(runtime.store, analysis_id="a1", contributor_id="ana", author=AUTHOR,
                       at=5, cells=[_cell(), _cell(criterionId="c", assertionId="s2")])
    message = str(refused.value)
    assert message.count("at $.at: 5 is not of type 'string'") == 1
    assert "$.cells[0].at" not in message


# -- from the verification pass of #155 ----------------------------------------------------------

def test_a_new_value_breaking_a_stored_rule_in_the_same_place_is_still_new(runtime) -> None:
    _store_off_contract(runtime)
    _unchanged(
        runtime,
        lambda: alternatives_set(runtime.store, analysis_id="a1",
                                 alternatives=[{"id": "z", "label": "Z", "url": "new"}]),
        r"'url' was unexpected",
    )


def test_a_stored_problem_moved_by_a_reordering_is_still_the_stored_one(runtime) -> None:
    """A preset scale sorts ahead of a hand-written one and moves its index."""
    frame = runtime.store.frame("a1")
    frame["scales"] = [{"id": "zz", "broader": "stevens", "means": "m", "params": {}, "legacy": 1}]
    runtime.store.put_frame("a1", frame)
    criteria_set(runtime.store, analysis_id="a1",
                 criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    assert [s["id"] for s in runtime.store.frame("a1")["scales"]] == ["ordinal-1-5-anchored", "zz"]


def test_nan_never_reaches_the_store(runtime) -> None:
    selector = {"type": "TextPositionSelector", "start": float("nan"), "end": float("inf")}
    _unchanged(
        runtime,
        lambda: measures_write(runtime.store, analysis_id="a1", contributor_id="ana",
                               author=AUTHOR, at=MOMENT,
                               cells=[_cell(evidence=[{**EVIDENCE, "selectors": [selector]}])]),
        r"NaN or infinite",
    )


def test_anchors_that_cannot_be_checked_first_are_refused(runtime) -> None:
    _unchanged(
        runtime,
        lambda: criteria_set(runtime.store, analysis_id="a1", criteria=[
            {"id": "c", "label": "C", "anchors": (row for row in ANCHORS)}]),
        r"at \$\.criteria\[0\]\.anchors: pass a list",
    )
