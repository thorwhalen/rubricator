"""Build the add-criterion evaluation's scenarios from the real verbs: one analysis, five requests.

Every scenario starts from the same confirmed analysis (three invented kettles, three fully
defined criteria, two cells scored), built through the frozen surface, and records what the
prompt's first read returns (``analysis_get`` with ``view: "criteria"``). The scenarios differ
only in what the user asks for, and in whether the right response is a ``criteria_set`` call
(``add``) or a question naming an existing criterion (``ask``). The grader replays a subject's
``criteria_set`` call against a fresh copy of the same analysis, so nothing here or there calls
a model.

    python scripts/add_criterion_scenarios.py docs/evaluation/add-criterion/scenarios.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rubricator.compose import build_runtime
from rubricator.surface import bind

MONDAY = "2026-10-12T09:30:00Z"
ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
KETTLES = [("brindle", "Brindle"), ("copperleaf", "Copperleaf"), ("tamsin", "Tamsin")]


def _criterion(cid, label, objective, question, anchors, exclusions):
    return {
        "id": cid, "label": label, "preference": "increasing",
        "anchors": [{"level": lvl, "text": text} for lvl, text in zip(("1", "3", "5"), anchors)],
        "definition": {
            "objective": objective, "question": question,
            "evidenceRule": "The maker's own manual or support pages; a retailer's summary is secondary.",
            "missingRules": [
                {"when": "No source the maker publishes says.", "code": "not-evidenced"},
                {"when": "The maker's sources disagree.", "code": "indeterminate"},
            ],
            "exclusions": exclusions,
        },
    }


CRITERIA = [
    _criterion("repair-policy", "Repair policy", "A broken kettle is fixed rather than replaced",
               "What does the maker commit to repairing, and for how long?",
               ("A source states the maker repairs nothing.",
                "A source states a repair policy that names some parts and no period.",
                "A source states a dated repair policy naming every part it covers."),
               ["How long spare parts are stocked; that is spare-parts."]),
    _criterion("spare-parts", "Spare parts", "A broken kettle is fixed rather than replaced",
               "For how long does the maker state it stocks spare parts?",
               ("A source states no spare parts are sold.",
                "A source states parts are stocked for under five years.",
                "A source states parts are stocked for ten years or more."),
               ["What the maker repairs itself; that is repair-policy."]),
    _criterion("quietness", "Quietness", "The kitchen stays usable for calls",
               "How loud is the kettle while boiling, as the maker states it?",
               ("A source states a boiling noise above 65 dB.",
                "A source states a boiling noise between 50 and 65 dB.",
                "A source states a boiling noise below 50 dB."),
               ["Noise from the lid or switch."]),
]
SPAN = {"id": "e1", "target": "doc:brindle-manual", "sourceType": "primary", "stance": "supports",
        "excerpt": "spare parts are stocked for ten years after purchase"}

#: The requests, and the response each one calls for. ``names`` is the existing criterion an
#: ``ask`` must name: the one the request duplicates or revises. ``None`` for a request that is
#: only too vague to define.
REQUESTS = {
    "a1": ("Can we also compare how long each one takes to boil a full kettle? The morning queue is "
           "awful. Faster is better, obviously.", "add", None),
    "a2": ("Add sustainability as a criterion.", "ask", None),
    "a3": ("Please add a column for how many years the maker keeps parts in stock.", "ask", "spare-parts"),
    "a4": ("Add the heating element to the repair policy one: a policy that excludes the element "
           "should count as bad.", "ask", "repair-policy"),
    "a5": ("Add energy use per boil. Our sustainability report counts kitchen electricity, so lower "
           "is better; the makers publish watt-hours per litre.", "add", None),
}


def build() -> dict[str, Any]:
    """The shared starting analysis; a fresh copy on every call. Returns the bound verbs."""
    runtime = build_runtime(blobs={}, now=lambda: MONDAY)
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="kettles", question="which kettle should the office buy?")
    verbs["frame_set"](analysis_id="kettles", ambiguities=[])
    verbs["alternatives_set"](analysis_id="kettles",
                              alternatives=[{"id": i, "label": label} for i, label in KETTLES])
    verbs["criteria_set"](analysis_id="kettles", criteria=CRITERIA)
    verbs["frame_confirm"](analysis_id="kettles")
    verbs["frame_confirm"](analysis_id="kettles", decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, those three, go ahead.")
    verbs["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA, cells=[
        {"alternativeId": "brindle", "criterionId": "spare-parts", "value": 5,
         "justification": "the manual states ten years", "evidence": [SPAN]},
        {"alternativeId": "copperleaf", "criterionId": "quietness", "missing": {
            "code": "not-evidenced", "note": "the maker's pages were read and state no noise level"}},
    ])
    return verbs


def main(out: str) -> None:
    read = build()["analysis_get"](analysis_id="kettles", view="criteria")
    assert [c["id"] for c in read["criteria"]] == [c["id"] for c in CRITERIA], read["criteria"]
    scenarios = [
        {"id": sid, "request": request, "toolResults": {"analysis_get": read},
         "expected": {"action": action, "names": names}}
        for sid, (request, action, names) in REQUESTS.items()
    ]
    with open(out, "w") as f:
        json.dump(scenarios, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
