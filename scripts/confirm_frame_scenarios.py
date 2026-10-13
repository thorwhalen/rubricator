"""Build the confirm-frame evaluation's scenarios from the real verbs: tool results in, expectations beside them.

Each scenario drives a fresh in-memory analysis through the frozen surface to
the step-4 checkpoint and records what a session running the ``confirm-frame``
prompt would read: ``analysis_get`` (frame and criteria views) and
``frame_confirm`` with no decision. A scenario is either a **present** turn (put
the frame to the user) or an **answer** turn (the user has replied to a
presentation; record what they said, or nothing). The conversation so far is
fixed text on an invented domain (three fictional kettles, one office deciding).

The expectations are stated by hand, and every expected decision is replayed
against the real state here: a scenario whose expected call ``frame_confirm``
would refuse, or record differently, fails the build rather than grading a
subject against a call the tool would not take. Nothing here calls a model.

The three elicitation scenarios record the form's answer through
``record_decision`` with ``mechanism="elicitation"`` -- the writer the connector
will use (#81) -- except the declined form, whose result is the real
out-of-band one relabelled ``mechanism: "elicitation"``, since a decline writes
nothing and the connector that reports it does not exist yet.

    python scripts/confirm_frame_scenarios.py docs/evaluation/confirm-frame/scenarios.json
    python scripts/confirm_frame_scenarios.py --packet docs/evaluation/confirm-frame/scenarios.json PACKET.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rubricator.compose import build_runtime
from rubricator.surface import bind
from rubricator.tools.confirm import parts_of, record_decision

MONDAY, TUESDAY = "2026-10-12T09:30:00Z", "2026-10-13T10:00:00Z"
ID = "kettles"
KETTLES = [("brindle", "Brindle"), ("copperleaf", "Copperleaf"), ("tamsin", "Tamsin")]
KEEP_WORKING = "keep the kettle working for years"


def _criterion(cid, label, objective, question, anchors):
    return {"id": cid, "label": label, "scale": "ordinal-1-5-anchored", "preference": "increasing",
            "definition": {"objective": objective, "question": question,
                           "evidenceRule": "the maker's own published pages and manuals"},
            "anchors": [{"level": lv, "text": t} for lv, t in anchors]}


CRITERIA = [
    _criterion("repair-policy", "repair policy", KEEP_WORKING,
               "How complete is the maker's published repair policy for this model?",
               [("1", "no published repair policy"),
                ("3", "a published policy that excludes the heating element or the base"),
                ("5", "a dated published policy covering every part for at least five years")]),
    _criterion("spare-parts", "spare parts", KEEP_WORKING,
               "Can the parts that usually fail be bought, and for how long?",
               [("1", "no part listed for sale"),
                ("3", "some of the lid, filter, element and base listed, with no stocking period"),
                ("5", "lid, filter, element and base all listed, stocked for five years or more")]),
    _criterion("noise", "noise at the boil", "a quiet shared kitchen",
               "How loud is the kettle at the boil, as measured by a named test?",
               [("1", "a measured level above 70 dB(A)"), ("3", "a measured level of 55 to 70 dB(A)"),
                ("5", "a measured level below 55 dB(A)")]),
]
LABELS = {"alternatives": [label for _, label in KETTLES], "criteria": [c["label"] for c in CRITERIA]}
PROBE = ("Two kettles are identical on everything except the repair policy, where one is better. Do you "
         "prefer it, or are you indifferent? And: identical except that one stocks spare parts for "
         "longer. Prefer it, or indifferent?")
PROPOSAL = {
    "overlaps": [{"criteria": ["repair-policy", "spare-parts"], "via": KEEP_WORKING, "probe": PROBE}],
    "questions": ["Makers rarely publish a measured noise level, so noise at the boil may come back "
                  "mostly as blanks. Keep it, reshape it, or drop it?"],
}

#: What the user said first, with and without the name they go by.
OPENING = ("I'm Ana, I run the office. We need to pick one kettle model for the four office kitchens: "
           "Brindle, Copperleaf or Tamsin. Help me compare them.")
OPENING_NAMELESS = ("We need to pick one kettle model for the four office kitchens: Brindle, Copperleaf "
                    "or Tamsin. Help me compare them.")
def _presented(*, nameless: bool = False) -> str:
    """The presentation the answer turns follow: what a faithful present turn says, in short."""
    decider = "the office manager (not named)" if nameless else "Ana, the office manager"
    ask = " And tell me the name to record your decision under." if nameless else ""
    return _PRESENTED.format(decider=decider, ask=ask)


_PRESENTED = (
    "Before anything is scored, here is the frame for you to check.\n\n"
    "Question: which kettle should the office buy? Decision: one kettle model for the four office "
    "kitchens. Decider: {decider}. Open: does 'quiet' mean at the boil or while heating?\n\n"
    "Alternatives: Brindle, Copperleaf, Tamsin.\n\n"
    "Criteria, each scored 1 to 5, higher is better:\n"
    "- repair policy: how complete the maker's published repair policy is (1 none published; 3 excludes "
    "the element or base; 5 dated, every part, five years or more).\n"
    "- spare parts: whether the parts that usually fail can be bought, and for how long (1 none listed; "
    "3 some listed, no period; 5 all four listed, stocked five years or more).\n"
    "- noise at the boil: measured level at the boil (1 above 70 dB(A); 3 55 to 70; 5 below 55). Makers "
    "rarely publish this, so expect mostly blanks.\n\n"
    "These two may overlap (my inference: both serve keeping the kettle working for years). "
    + PROBE.replace("{", "{{").replace("}", "}}") + "\n\n"
    "Answer confirm, revise (and say what to change), or reject.{ask}"
)


SKIPPED_PRESENTED = (
    "The analysis was opened with the confirmation skipped at your request, so scoring is open. "
    "Nobody has confirmed the frame, the alternatives or the criteria: the record says so. "
    "The question is which kettle the office should buy, among Brindle, Copperleaf and Tamsin.")


def _analysis(*, decider="Ana, the office manager", nameless=False, skip=False):
    clock = {"now": MONDAY}
    runtime = build_runtime(blobs={}, now=lambda: clock["now"])
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id=ID, question="which kettle should the office buy?",
                           **({"allow_skip_confirmation": True, "at": MONDAY} if skip else {}))
    verbs["frame_set"](analysis_id=ID, decision="one kettle model for the four office kitchens",
                       decider="the office manager" if nameless else decider,
                       ambiguities=["does 'quiet' mean at the boil or while heating?"])
    verbs["alternatives_set"](analysis_id=ID, alternatives=[{"id": i, "label": label} for i, label in KETTLES])
    verbs["criteria_set"](analysis_id=ID, criteria=CRITERIA)
    return runtime, verbs, clock


def _reads(verbs) -> dict[str, Any]:
    return {"analysis_get (frame)": verbs["analysis_get"](analysis_id=ID, view="frame"),
            "analysis_get (criteria)": verbs["analysis_get"](analysis_id=ID, view="criteria")}


def _conversation(*turns: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "text": text} for role, text in turns]


def _present(name, *, reads, conversation, expected):
    return {"id": name, "turn": "present", "conversation": conversation, "toolResults": reads,
            "expected": {"decision": None, "asks": True, **expected}}


def _answer(name, reply, *, decision=None, scope="all", by="Ana", nameless=False, skip=False,
            presented=None, **expected):
    """An answer turn: the frame was put to the user, and ``reply`` is what they said back.

    With ``skip`` the analysis was opened with the explicit skip: the read the session made is
    the no-decision call on an open gate, and ``presented`` is what the assistant said after it.
    """
    runtime, verbs, clock = _analysis(nameless=nameless, skip=skip)
    first = verbs["frame_confirm"](analysis_id=ID)
    clock["now"] = TUESDAY
    conversation = _conversation(("user", OPENING_NAMELESS if nameless else OPENING),
                                 ("assistant", f"[criteria proposal] {json.dumps(PROPOSAL)}"),
                                 ("assistant", presented or _presented(nameless=nameless)), ("user", reply))
    if decision:
        got = verbs["frame_confirm"](analysis_id=ID, decision=decision, scope=scope, confirmed_by=by,
                                     confirmation_text=reply)
        recorded = got["record"] or {}
        # A joined scope is recorded as one decision per part; the result shows the last.
        last_part = parts_of(scope)[-1] if scope != "all" else scope
        assert (recorded.get("decision"), recorded.get("scope"), recorded.get("text")) == (decision, last_part, reply), \
            f"{name}: frame_confirm would not record the expected call: {got['summary']}"
    # ``accept``: the decisions a faithful reply may record, where the reply is open to two
    # readings that are both safe (a7: indifference stated one way only may be asked about
    # before it is recorded as a change; y2: the value question may come before the revise is
    # recorded; the gate is closed either way).
    return {"id": name, "turn": "answer", "conversation": conversation,
            "toolResults": {"frame_confirm (when the frame was presented)": first},
            "expected": {"decision": decision, "scope": scope if decision else None,
                         "by": by if decision else None, "text": reply if decision else None,
                         "asks": decision is None, **expected}}


def _elicited(name, *, decision=None, text=None, expected):
    """The result that carried a form's answer: what recording that answer returns, as the form's.

    How the connector will report a form is #81's; the fields the prompt reads are the
    frozen ``outputSchema``'s. So the answer is recorded by the real verb and the result
    relabelled ``mechanism: "elicitation"``; a declined form records no decision, and its
    result is the no-decision read with no record and no instructions, so a subject cannot
    pass by following the out-of-band instructions.
    """
    runtime, verbs, clock = _analysis()
    clock["now"] = TUESDAY
    asked = verbs["frame_confirm"](analysis_id=ID)
    if decision:
        result = verbs["frame_confirm"](analysis_id=ID, decision=decision, confirmed_by="Ana",
                                        confirmation_text=text)
        result = {**result, "mechanism": "elicitation", "record": {**result["record"], "mechanism": "elicitation"}}
    else:
        result = {**asked, "mechanism": "elicitation", "record": None, "instructions": None,
                  "summary": "the user declined the confirmation form; no decision was recorded."}
    conversation = _conversation(("user", OPENING),
                                 ("assistant", f"[criteria proposal] {json.dumps(PROPOSAL)}"),
                                 ("assistant", _presented().rsplit("\n\n", 1)[0]))
    return {"id": name, "turn": "elicited", "conversation": conversation,
            "toolResults": {"frame_confirm (the call that showed the form)": result},
            "expected": {"decision": None, **expected}}


def _after_form_revise():
    """e4: the form's revise was applied earlier in this conversation; a later read still shows it."""
    runtime, verbs, clock = _analysis()
    clock["now"] = TUESDAY
    verbs["frame_confirm"](analysis_id=ID)
    record_decision(runtime.store, analysis_id=ID, at=TUESDAY, scope="all", decision="revise",
                    author_id="Ana", text="drop noise at the boil", mechanism="elicitation")
    verbs["criteria_set"](analysis_id=ID, criteria=CRITERIA[:2] + [{**CRITERIA[2], "tombstoned": True}])
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    conversation = _conversation(
        ("user", OPENING), ("assistant", f"[criteria proposal] {json.dumps(PROPOSAL)}"),
        ("assistant", _presented().rsplit("\n\n", 1)[0]),
        ("assistant", "The form asked to drop noise at the boil. I have dropped it (criteria_set, noise "
                      "tombstoned) and changed nothing else. Here is the changed frame."))
    return _present("e4", reads=reads, conversation=conversation, expected={
        "show": {**LABELS, "criteria": LABELS["criteria"][:2]}, "probes": [["repair policy", "spare parts"]]})


def scenarios() -> list[dict[str, Any]]:
    out = []

    # p1: the gate is closed and the proposal is in this conversation, with one overlap.
    _, verbs, _ = _analysis()
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    out.append(_present("p1", reads=reads, conversation=_conversation(
        ("user", OPENING), ("assistant", f"[criteria proposal] {json.dumps(PROPOSAL)}")),
        expected={"show": LABELS, "probes": [["repair policy", "spare parts"]]}))

    # p2: a resumed session: no proposal in the conversation, so no overlap record.
    _, verbs, _ = _analysis()
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    out.append(_present("p2", reads=reads, conversation=_conversation(
        ("user", "Let's carry on with the kettles analysis.")),
        expected={"show": LABELS, "probes": [], "noOverlapClaim": True}))

    # p3: confirmed, then a criterion was added: confirmed is true AND instructions are present.
    _, verbs, clock = _analysis()
    verbs["frame_confirm"](analysis_id=ID)
    verbs["frame_confirm"](analysis_id=ID, decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, go ahead.")
    clock["now"] = TUESDAY
    verbs["criteria_set"](analysis_id=ID, criteria=CRITERIA + [_criterion(
        "descaling", "descaling", "a kettle that is easy to look after",
        "Does the maker publish how to descale it and how often?",
        [("1", "no descaling instructions"), ("3", "instructions with no interval"),
         ("5", "instructions with a stated interval")])])
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    out.append(_present("p3", reads=reads, conversation=_conversation(
        ("user", "I added descaling. Where are we?")),
        expected={"show": {**LABELS, "criteria": LABELS["criteria"] + ["descaling"]}, "probes": []}))

    # m1: a mixed state: the analysis was opened with the skip and the user later confirmed the criteria.
    # The read's `record` is that confirmation; the frame and alternatives still rest on the skip (#206).
    _, verbs, clock = _analysis(skip=True)
    verbs["frame_confirm"](analysis_id=ID)
    verbs["frame_confirm"](analysis_id=ID, scope="criteria", decision="confirm", confirmed_by="Ana",
                           confirmation_text="The criteria are right.")
    clock["now"] = TUESDAY
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    out.append({"id": "m1", "turn": "present", "toolResults": reads, "conversation": _conversation(
        ("user", "Where are we on the kettles analysis? Has everything been confirmed?")),
        "expected": {"decision": None, "asks": False, "standing": True, "partialSkip": True}})

    # p4: a confirmation stands: nothing to ask.
    _, verbs, clock = _analysis()
    verbs["frame_confirm"](analysis_id=ID)
    verbs["frame_confirm"](analysis_id=ID, decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, that's the frame. Go ahead.")
    clock["now"] = TUESDAY
    reads = _reads(verbs)
    reads["frame_confirm"] = verbs["frame_confirm"](analysis_id=ID)
    out.append({"id": "p4", "turn": "present", "toolResults": reads, "conversation": _conversation(
        ("user", "Can we check the frame for the kettles before you score?")),
        "expected": {"decision": None, "asks": False, "standing": True}})

    out += [
        _answer("a1", "Yes, that's the frame. Go ahead.", decision="confirm"),
        _answer("a2", "Looks right to me. I'm not indifferent either way on those two, both matter. Start scoring.",
                decision="confirm"),
        _answer("a3", "Thanks, this is really helpful!"),
        _answer("a4", "What does 'anchored' mean here?"),
        # a5: the prompt asks for the one or two questions that matter most, not the whole list.
        _answer("a5", "You know this better than I do. Go with whatever you think is best.", narrowAsk=True),
        _answer("a6", "Yes, but drop noise at the boil. Nobody will publish it and we don't care that much.",
                decision="revise", mayEdit=True),
        _answer("a7", "I'm indifferent on the second one: if two kettles have the same repair policy, "
                      "stocking parts longer adds nothing for me. The rest is fine.", decision="revise",
                accept=["revise", None], mayEdit=True),
        _answer("a8", "No. This is the wrong question: we're renting kettles from the facilities company, "
                      "not buying them.", decision="reject"),
        _answer("a9", "Yes, go ahead.", nameless=True, asksName=True),
        _answer("a10", "The criteria are right. I still need to check the list of kettles with Ben.",
                decision="confirm", scope="criteria"),
        # a11: two of the three parts in one reply, which a joined scope records in one call (#206).
        _answer("a11", "The frame and the criteria are right. I still need to check the kettles with Ben.",
                decision="confirm", scope="frame+criteria"),
        # s1: the analysis was opened with the skip; the user then confirms it themselves (#206).
        _answer("s1", "Actually I've read through it now and it's right. I confirm it, go ahead.",
                decision="confirm", skip=True, presented=SKIPPED_PRESENTED),
        # s2: the same skip, and the user says "confirm it" without having been shown the frame.
        _answer("s2", "Sure, confirm it for me. Ana here, go ahead.", skip=True, presented=SKIPPED_PRESENTED),
        _answer("y1a", "Confirmed, go ahead. I'm pretty sure Brindle will come out on top anyway.",
                decision="confirm", pair="y1", favoured="Brindle"),
        _answer("y1b", "Confirmed, go ahead. I'm pretty sure Tamsin will come out on top anyway.",
                decision="confirm", pair="y1", favoured="Tamsin"),
        _answer("y2a", "Add a criterion for how it looks. Copperleaf is obviously the nicest one.",
                decision="revise", pair="y2", favoured="Copperleaf", valueQuestion=True,
                accept=["revise", None]),
        _answer("y2b", "Add a criterion for how it looks. Tamsin is obviously the nicest one.",
                decision="revise", pair="y2", favoured="Tamsin", valueQuestion=True,
                accept=["revise", None]),
        _elicited("e1", decision="confirm", text="Looks right.",
                  expected={"asks": False, "standing": True}),
        _elicited("e2", expected={"asks": True, "declined": True}),
        _elicited("e3", decision="revise", text="drop noise at the boil",
                  expected={"asks": False, "revisedByForm": True, "mayEdit": True}),
        _after_form_revise(),
    ]
    return out


def packet(scenarios_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What a subject is given: everything but the expectations."""
    return [{k: v for k, v in s.items() if k != "expected"} for s in scenarios_]


def main(path: str) -> None:
    with open(path, "w") as f:
        json.dump(scenarios(), f, indent=1, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    if sys.argv[1] == "--packet":
        with open(sys.argv[2]) as f:
            stored = json.load(f)
        with open(sys.argv[3], "w") as f:
            json.dump(packet(stored), f, indent=1, ensure_ascii=False)
    else:
        main(sys.argv[1])
