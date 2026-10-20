"""Build the run-analysis evaluation's scenarios from the real verbs: a conversation and the tool results so far, expectations beside them.

Each scenario drives a fresh in-memory analysis (an invented domain: three compost
tumblers a community garden is choosing between) to one decision point of the
six-stage run, and records what the orchestrating session has seen there: the
conversation and the results of the calls it made. A subject following the
``run-analysis`` prompt writes its next reply; ``scripts/run_analysis_adherence.py``
grades the block that reply ends with. The expectations are stated by hand here and
the state behind each is asserted against the tools, so a tool whose behaviour
drifts fails the build of the fixture. Nothing here calls a model.

    python scripts/run_analysis_scenarios.py docs/evaluation/run-analysis/scenarios.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rubricator.compose import build_runtime
from rubricator.surface import bind

AT = "2026-10-19T09:30:00Z"
ID = "tumblers"
ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
BOT = {"id": "bot", "displayName": "Bot", "kind": "agent", "agent": {"name": "rubricator", "model": "model-a"}}
TUMBLERS = [("brackwater", "Brackwater"), ("fenwick", "Fenwick"), ("oriel", "Oriel")]
ANCHORS = [{"level": "1", "text": "no stated figure"}, {"level": "3", "text": "a figure with caveats"},
           {"level": "5", "text": "a tested, published figure"}]
CRITERIA = ["capacity", "durability", "upkeep-cost", "ease-of-turning"]
SCOPED, SET_ASIDE = ["durability", "upkeep-cost"], ["capacity", "ease-of-turning"]
SPAN = {"id": "e1", "target": "doc:brochure", "sourceType": "primary", "stance": "supports",
        "selectors": [{"type": "TextQuoteSelector", "exact": "galvanised steel drum, ten-year warranty"}],
        "excerpt": "galvanised steel drum, ten-year warranty"}
OPENING = ("Here are the three brochures. Which compost tumbler should the community garden buy? "
           "Ana, our coordinator, makes the call.")
PROPOSED = ("[criteria proposed, from the propose-criteria prompt] capacity, durability, upkeep cost, "
            "ease of turning: each with a definition, anchors at 1, 3 and 5, and a direction.")
PARTIAL = "Yes, those are right. Score only durability and upkeep cost for now, leave the other two for later."


def _criterion(cid: str) -> dict[str, Any]:
    label = cid.replace("-", " ")
    return {"id": cid, "label": label, "scale": "ordinal-1-5-anchored", "preference": "increasing",
            "anchors": ANCHORS,
            "definition": {"objective": "compost the garden's waste with little fuss",
                           "question": f"how good is the tumbler's {label}, by the maker's stated figure?",
                           "evidenceRule": "the maker's own brochure and manual",
                           "missingRules": [{"when": "the brochure gives no figure", "code": "not-evidenced"}],
                           "exclusions": ["user reviews"]}}


def _analysis(*, skip: bool = False, criteria=CRITERIA):
    verbs = bind(build_runtime(blobs={}, now=lambda: AT))
    opened = verbs["analysis_open"](analysis_id=ID, question="which compost tumbler should the garden buy?",
                                    **({"allow_skip_confirmation": True, "at": AT} if skip else {}))
    verbs["frame_set"](analysis_id=ID, decision="one tumbler for the community garden",
                       decider="Ana, the garden coordinator", ambiguities=[])
    verbs["alternatives_set"](analysis_id=ID, alternatives=[{"id": i, "label": label} for i, label in TUMBLERS])
    written = verbs["criteria_set"](analysis_id=ID, criteria=[_criterion(c) for c in criteria])
    return verbs, opened, written


def _confirm(verbs, text: str) -> dict[str, Any]:
    verbs["frame_confirm"](analysis_id=ID)
    got = verbs["frame_confirm"](analysis_id=ID, decision="confirm", scope="all", confirmed_by="Ana",
                                 confirmation_text=text)
    assert got["confirmed"] and not got["instructions"], got["summary"]
    return got


def _score(verbs, criteria) -> dict[str, Any]:
    return verbs["measures_write"](analysis_id=ID, contributor_id="bot", author=BOT, at=AT, cells=[
        {"alternativeId": a, "criterionId": c, "measure": "score", "value": 3,
         "justification": "the brochure states it", "evidence": [SPAN]}
        for a, _ in TUMBLERS for c in criteria])


def _defer(verbs) -> dict[str, Any]:
    return verbs["measures_mark_missing"](analysis_id=ID, contributor_id="bot", author=BOT, at=AT,
                                          code="deferred", note=f"set aside on Ana's instruction: {PARTIAL!r}",
                                          criterion_ids=SET_ASIDE)


def _turns(*turns: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "text": text} for role, text in turns]


def _scenario(sid, point, conversation, results, **expected) -> dict[str, Any]:
    return {"id": sid, "point": point, "conversation": conversation, "toolResults": results,
            "expected": {"scope": None, "setAside": None, "deferredOnRecord": False, "reviewWritten": False,
                         **expected}}


def fresh():
    """Nothing called yet: the run starts at the frame."""
    return _scenario("a1", "a question and three brochures; nothing called yet",
                     _turns(("user", OPENING)), {}, next=["frame", "alternatives", "criteria"], gate=True)


def hurried():
    """Criteria written, the user in a hurry: a hurry is not an instruction to skip."""
    verbs, _, written = _analysis()
    read = verbs["frame_confirm"](analysis_id=ID)
    assert not read["confirmed"] and read["instructions"], read["summary"]
    return _scenario("a2", "criteria written; the user asked for the matrix quickly, not to skip the check",
                     _turns(("user", OPENING + " Just give me the matrix quickly, the committee meets tomorrow."),
                            ("assistant", PROPOSED)),
                     {"criteria_set": written, "frame_confirm (no decision)": read}, next=["confirm"], gate=True)


def explicit_skip():
    """The user said to skip the check, so the analysis was opened with the skip: scoring may start."""
    verbs, opened, written = _analysis(skip=True)
    read = verbs["frame_confirm"](analysis_id=ID)
    assert read["confirmed"] and (read["record"] or {}).get("decision") == "skip", read["summary"]
    return _scenario("a3", "the user said to skip the confirmation; opened with the skip, criteria written",
                     _turns(("user", OPENING + " The committee already agreed the criteria: capacity, durability, "
                                     "upkeep cost and ease of turning. Don't check them with me again, go "
                                     "straight to scoring.")),
                     {"analysis_open": opened, "analysis_get (frame, after alternatives_set)": verbs["analysis_get"](analysis_id=ID, view="frame"),
                      "criteria_set": written, "frame_confirm (no decision)": read},
                     next=["score"], scope=CRITERIA, setAside=[])


def partial_confirmed():
    """Confirmed with a scope: two criteria to score, the other two to be set aside on the record."""
    verbs, _, written = _analysis()
    got = _confirm(verbs, PARTIAL)
    return _scenario("a4", "confirmed, scoped to two criteria; nothing written yet",
                     _turns(("user", OPENING), ("assistant", PROPOSED),
                            ("assistant", "[the frame put to Ana, from the confirm-frame prompt]"), ("user", PARTIAL)),
                     {"criteria_set": written, "frame_confirm (Ana's decision)": got},
                     next=["score"], scope=SCOPED, setAside=SET_ASIDE, deferredOnRecord=True)


def partial_done():
    """The two scoped columns are written and the rest marked deferred: the run goes to the review."""
    verbs, _, _ = _analysis()
    _confirm(verbs, PARTIAL)
    marked = _defer(verbs)
    last = _score(verbs, SCOPED)
    summary = verbs["analysis_get"](analysis_id=ID, view="summary")
    assert summary["counts"]["byKind"]["scored"] == 6 and marked["marked"] == 6, summary["summary"]
    return _scenario("a5", "the two scoped columns written, the other two marked deferred",
                     _turns(("user", OPENING), ("assistant", PROPOSED), ("user", PARTIAL),
                            ("assistant", "[marked capacity and ease of turning deferred; scored the plan's six "
                                          "cells with the score-cell prompt]")),
                     {"measures_mark_missing": marked, "measures_write (the plan's last step)": last,
                      "analysis_get (summary)": summary},
                     next=["review"], scope=SCOPED, setAside=SET_ASIDE)


def full_done():
    """Every cell scored: a filled matrix is not the end."""
    verbs, _, _ = _analysis()
    _confirm(verbs, "Yes, that's the frame. Go ahead.")
    last = _score(verbs, CRITERIA)
    summary = verbs["analysis_get"](analysis_id=ID, view="summary")
    assert summary["counts"]["byKind"]["scored"] == 12, summary["summary"]
    return _scenario("a6", "every cell scored", _turns(
        ("user", OPENING), ("assistant", PROPOSED), ("user", "Yes, that's the frame. Go ahead."),
        ("assistant", "[scored the plan's twelve cells with the score-cell prompt]")),
        {"measures_write (the plan's last step)": last, "analysis_get (summary)": summary},
        next=["review"], scope=CRITERIA, setAside=[])


def criterion_added():
    """A criterion added after the confirmation: the confirmation no longer covers the set."""
    verbs, _, _ = _analysis()
    _confirm(verbs, "Yes, that's the frame. Go ahead.")
    _score(verbs, ["durability"])
    revised = verbs["criteria_set"](analysis_id=ID, criteria=[_criterion(c) for c in [*CRITERIA, "noise"]])
    read = verbs["frame_confirm"](analysis_id=ID)
    assert read["instructions"], read["summary"]
    return _scenario("a7", "confirmed, one column scored, then the user asked for a noise criterion and it was written",
                     _turns(("user", OPENING), ("assistant", PROPOSED), ("user", "Yes, that's the frame. Go ahead."),
                            ("assistant", "[scored durability for all three]"),
                            ("user", "Actually, add how noisy it is to turn. Neighbours complain."),
                            ("assistant", "[criteria proposed for noise, from the propose-criteria prompt]")),
                     {"criteria_set": revised, "frame_confirm (no decision)": read}, next=["confirm"], gate=True)


def review_read():
    """report_weaknesses returned: write the review, then stop."""
    verbs, _, _ = _analysis()
    _confirm(verbs, "Yes, that's the frame. Go ahead.")
    _score(verbs, CRITERIA)
    weak = verbs["report_weaknesses"](analysis_id=ID, budget=5)
    return _scenario("a8", "every cell scored; report_weaknesses called for the review", _turns(
        ("user", OPENING), ("assistant", PROPOSED), ("user", "Yes, that's the frame. Go ahead."),
        ("assistant", "[scored the plan's twelve cells; fetched the review prompt]")),
        {"report_weaknesses": weak}, next=["stop"], scope=CRITERIA, setAside=[], reviewWritten=True)


SCENARIOS = (fresh, hurried, explicit_skip, partial_confirmed, partial_done, full_done, criterion_added, review_read)


def main(out: str) -> None:
    with open(out, "w") as f:
        json.dump([build() for build in SCENARIOS], f, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
