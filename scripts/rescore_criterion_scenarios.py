"""Build the rescore-criterion evaluation's scenarios from the real verbs: one scored analysis, eight requests.

Every scenario starts from the same confirmed analysis as the add-criterion evaluation (three
invented kettles, the same three criteria), with a small corpus and one sweep already scored by the
agent contributor ``scorer``: spare parts for every kettle, quietness for two of them, Tamsin's
quietness never written. A scenario then adds its own new documents and asks for one criterion to be
re-scored. What the subject sees is what the prompt allows it to read without seeing an earlier
score (``analysis_get`` criteria and outstanding views), and what ``corpus_search`` returns for each
alternative over the corpus as it now stands. The earlier scores are in the packet only where the
scenario puts them in the conversation. The grader replays a subject's ``measures_write`` calls
against a fresh copy of the same scenario, so nothing here or there calls a model.

    python scripts/rescore_criterion_scenarios.py docs/evaluation/rescore-criterion/scenarios.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from add_criterion_scenarios import CRITERIA, KETTLES, MONDAY  # noqa: E402

from rubricator.compose import build_runtime  # noqa: E402
from rubricator.surface import bind  # noqa: E402

ANALYSIS_ID = "kettles"
SCORER = {"id": "scorer", "displayName": "Scorer", "kind": "agent"}
FIRST_SWEEP = {"round": 1, "session": "fresh", "prior": "withheld"}
#: The round the harness hands a re-scoring sweep in these scenarios: the one after the first.
NEXT_ROUND = FIRST_SWEEP["round"] + 1

#: The corpus before any scenario adds to it: (source id, title, text).
BASE_CORPUS = [
    ("brindle-manual", "Brindle care guide",
     "Brindle care guide. Spare parts are stocked for ten years after purchase. "
     "The Brindle boils at a measured 55 dB."),
    ("copperleaf-manual", "Copperleaf manual",
     "Copperleaf manual. Spare parts are stocked for three years. Boiling noise: 70 dB."),
    ("tamsin-leaflet", "Tamsin quick start leaflet",
     "Tamsin quick start leaflet. Fill to the max line. Descale monthly in hard water."),
]

#: The first sweep: (alternative, criterion, value or missing code, the span it rests on).
FIRST = [
    ("brindle", "spare-parts", 5, "Spare parts are stocked for ten years after purchase"),
    ("copperleaf", "spare-parts", 3, "Spare parts are stocked for three years"),
    ("tamsin", "spare-parts", "not-evidenced", None),
    ("brindle", "quietness", 3, "The Brindle boils at a measured 55 dB"),
    ("copperleaf", "quietness", 1, "Boiling noise: 70 dB"),
]

#: Keywords searched per criterion, with the alternative's label in front.
QUERY = {"spare-parts": "spare parts stocked years", "quietness": "boiling noise dB"}

#: An earlier exchange in which the subject itself scored spare parts, for the scenario where the
#: earlier scores are already in the conversation.
EARLIER_IN_THIS_CONVERSATION = [
    {"role": "user", "content": "Score spare parts for all three kettles."},
    {"role": "assistant", "content": "Spare parts: Brindle 5 (the care guide states ten years), "
     "Copperleaf 3 (the manual states three years), Tamsin not-evidenced (the leaflet says nothing "
     "about parts). Written as round 1."},
]

TAMSIN_SERVICE = [("tamsin-service", "Tamsin service page",
                   "Tamsin service and parts. Spare parts for every Tamsin kettle are stocked for twelve "
                   "years after the model is discontinued.")]
BRINDLE_RECALL = [("brindle-recall", "Brindle recall notice",
                   "Brindle recall notice. Affected lids will be replaced free of charge. Spare parts for "
                   "all Brindle kettles remain stocked for ten years after purchase.")]
R1_CELLS = {"brindle": (5, "brindle-spare-parts-score"),
            "copperleaf": (3, "copperleaf-spare-parts-score"),
            "tamsin": (5, "tamsin-spare-parts-score")}

#: What a reply that asks instead of re-scoring where the earlier scores are in the conversation says.
#: Worded so a denial ("they are not in this conversation") does not match.
SAYS_THE_PRIOR_IS_IN_VIEW = r"(fresh|new) conversation|(are|were) (already )?in (this|the) conversation"

#: id -> (request, criterion, new documents, conversation before the request, expected).
#: ``expected["cells"]`` maps each alternative to (its outcome, the id it must supersede or None);
#: an outcome is a level or a missingness code. ``prior``/``session``/``round`` are what every write
#: must state, and ``round`` is also what the harness hands the subject (``None``: it hands none);
#: ``action`` is ``write`` or ``ask``; ``either`` lets an ``ask`` scenario also be answered by writes
#: that state the prior truthfully; ``asks`` is a pattern the reply of an ask must match (what it asks
#: about); ``resumed`` marks a scenario that starts after the subject's own
#: first write attempt, so its retrieval came before the calls it lists.
SCENARIOS: dict[str, tuple[str, str, list[tuple[str, str, str]], list[dict[str, str]], dict[str, Any]]] = {
    "r1": ("I've added Tamsin's service page to the corpus. Please re-score spare parts.",
           "spare-parts", TAMSIN_SERVICE, [],
           {"action": "write", "prior": "withheld", "session": "fresh", "round": NEXT_ROUND,
            "cells": R1_CELLS}),
    "r2": ("Tamsin finally published a noise datasheet; it's in the corpus now. Re-score quietness "
           "for Tamsin only.",
           "quietness",
           [("tamsin-datasheet", "Tamsin datasheet",
             "Tamsin technical datasheet. Rated boiling noise: 48 dB at full capacity.")],
           [],
           {"action": "write", "prior": "withheld", "session": "fresh", "round": NEXT_ROUND,
            "cells": {"tamsin": (5, None)}}),
    "r3": ("Copperleaf's product page is in the corpus now. Re-score quietness for every kettle.",
           "quietness",
           [("copperleaf-product-page", "Copperleaf product page",
             "Copperleaf product page. Quiet boil technology: boiling noise 58 dB.")],
           [],
           {"action": "write", "prior": "withheld", "session": "fresh", "round": NEXT_ROUND,
            "cells": {"brindle": (3, "brindle-quietness-score"),
                      "copperleaf": ("indeterminate", "copperleaf-quietness-score"),
                      "tamsin": ("not-evidenced", None)}}),
    "r4": ("Last time you gave Brindle a 5 on spare parts because the care guide says ten years. "
           "Brindle has since issued a recall notice, which is in the corpus. Look at your old score "
           "against it and re-score spare parts for Brindle.",
           "spare-parts", BRINDLE_RECALL, [],
           {"action": "write", "prior": "shown", "session": None, "round": NEXT_ROUND,
            "cells": {"brindle": (5, "brindle-spare-parts-score")}}),
    "r5": ("I've added Tamsin's service page to the corpus. Re-score spare parts.",
           "spare-parts", TAMSIN_SERVICE, EARLIER_IN_THIS_CONVERSATION,
           {"action": "ask", "either": True, "prior": "shown", "session": "same", "round": NEXT_ROUND,
            "asks": SAYS_THE_PRIOR_IS_IN_VIEW, "cells": R1_CELLS}),
    "r6": ("Re-score quietness, but from now on count anything under 55 dB as top marks.",
           "quietness", [], [],
           {"action": "ask", "either": False, "prior": None, "session": None, "round": NEXT_ROUND,
            "asks": r"criterion|anchor|revis", "cells": {}}),
    # Brindle's spare parts were already re-scored once, so the default id is no longer the live claim:
    # the subject has tried it and holds the tool's refusal, which names the successor.
    "r7": ("Brindle's recall notice is in the corpus. Re-score spare parts for Brindle.",
           "spare-parts", BRINDLE_RECALL, [],
           {"action": "write", "prior": "withheld", "session": "fresh", "round": NEXT_ROUND + 1,
            "resumed": True, "cells": {"brindle": (5, "brindle-spare-parts-score-2")}}),
    # Nobody gives the subject this sweep's round number.
    "r8": ("I've added Tamsin's service page to the corpus. Please re-score spare parts.",
           "spare-parts", TAMSIN_SERVICE, [],
           {"action": "ask", "either": False, "prior": None, "session": None, "round": None,
            "asks": r"\bround\b", "cells": {}}),
}

#: Scenarios whose starting analysis has an extra, earlier re-score on top of the first sweep.
RESCORED_BEFORE = {"r7": ("brindle", "spare-parts", 5, "Spare parts are stocked for ten years after purchase")}


def _sources(rows):
    return [{"id": sid, "title": title, "text": text, "agentProduced": False} for sid, title, text in rows]


def build(scenario_id: str | None = None) -> dict[str, Any]:
    """The scored starting analysis, plus the scenario's new documents; a fresh copy on every call."""
    runtime = build_runtime(blobs={}, now=lambda: MONDAY)
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id=ANALYSIS_ID, question="which kettle should the office buy?")
    verbs["frame_set"](analysis_id=ANALYSIS_ID, ambiguities=[])
    verbs["alternatives_set"](analysis_id=ANALYSIS_ID,
                              alternatives=[{"id": i, "label": label} for i, label in KETTLES])
    verbs["criteria_set"](analysis_id=ANALYSIS_ID, criteria=CRITERIA)
    verbs["frame_confirm"](analysis_id=ANALYSIS_ID)
    verbs["frame_confirm"](analysis_id=ANALYSIS_ID, decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, those three, go ahead.")
    docs = verbs["corpus_add"](analysis_id=ANALYSIS_ID, sources=_sources(BASE_CORPUS))["documentIds"]
    doc_of = dict(zip((s[0] for s in BASE_CORPUS), docs))
    for alt, crit, outcome, quote in FIRST:
        cell: dict[str, Any] = {"alternativeId": alt, "criterionId": crit}
        if quote is None:
            cell["missing"] = {"code": outcome, "note": f"retrieval over the corpus returned nothing on {crit}"}
        else:
            cell |= {"justification": f"the maker's document states it: {quote}", "value": outcome,
                     "evidence": [{"id": "e1", "target": doc_of[f"{alt}-manual"], "sourceType": "primary",
                                   "stance": "supports",
                                   "selectors": [{"type": "TextQuoteSelector", "exact": quote}]}]}
        verbs["measures_write"](analysis_id=ANALYSIS_ID, contributor_id="scorer", author=SCORER,
                                cells=[cell], procedure=FIRST_SWEEP)
    if scenario_id in RESCORED_BEFORE:
        alt, crit, value, quote = RESCORED_BEFORE[scenario_id]
        verbs["measures_write"](analysis_id=ANALYSIS_ID, contributor_id="scorer", author=SCORER, cells=[{
            "alternativeId": alt, "criterionId": crit, "supersedes": f"{alt}-{crit}-score",
            "justification": f"the maker's document states it: {quote}", "value": value,
            "evidence": [{"id": "e1", "target": doc_of[f"{alt}-manual"], "sourceType": "primary",
                          "stance": "supports", "selectors": [{"type": "TextQuoteSelector", "exact": quote}]}]}],
            procedure={**FIRST_SWEEP, "round": NEXT_ROUND})
    if scenario_id is not None and SCENARIOS[scenario_id][2]:
        verbs["corpus_add"](analysis_id=ANALYSIS_ID, sources=_sources(SCENARIOS[scenario_id][2]))
    return verbs


def _refusal_naming_the_default_id(verbs, alt: str, crit: str) -> str:
    """What the tools say to a re-score that names ``alt``'s default id after it was replaced: real output."""
    try:
        verbs["measures_write"](analysis_id=ANALYSIS_ID, contributor_id="scorer", author=SCORER, cells=[{
            "alternativeId": alt, "criterionId": crit, "supersedes": f"{alt}-{crit}-score",
            "missing": {"code": "not-evidenced", "note": "probe"}}], procedure={**FIRST_SWEEP, "round": 9})
    except ValueError as refusal:
        return str(refusal)
    raise AssertionError("the probe write was accepted; the scenario no longer has a replaced claim")


def packet(scenario_id: str) -> dict[str, Any]:
    """What the subject is given for one scenario: the request and the value-free reads."""
    request, criterion, new_docs, conversation, expected = SCENARIOS[scenario_id]
    verbs = build(scenario_id)
    search = {
        alt: verbs["corpus_search"](analysis_id=ANALYSIS_ID, query=f"{label} {QUERY[criterion]}")
        for alt, label in KETTLES
    }
    results: dict[str, Any] = {
        "analysis_get(criteria)": verbs["analysis_get"](analysis_id=ANALYSIS_ID, view="criteria"),
        "analysis_get(outstanding)": verbs["analysis_get"](analysis_id=ANALYSIS_ID, view="outstanding"),
        "corpus_search, per alternative, over the whole corpus": search,
    }
    if scenario_id in RESCORED_BEFORE:
        alt, crit = RESCORED_BEFORE[scenario_id][:2]
        results[f"measures_write: your first attempt for {alt}, naming supersedes {alt}-{crit}-score "
                "(already made; list only the calls you make after it)"] = (
            _refusal_naming_the_default_id(verbs, alt, crit))
    return {
        "id": scenario_id,
        "request": request,
        "conversation": conversation,
        "contributor": {"contributor_id": "scorer", "author": SCORER},
        "harness": {} if expected["round"] is None else {"round": expected["round"]},
        "newDocuments": [sid for sid, _, _ in new_docs],
        "toolResults": results,
        "criterion": criterion,
        "expected": {**expected, "cells": {a: list(v) for a, v in expected["cells"].items()}},
    }


def main(out: str) -> None:
    scenarios = [packet(sid) for sid in SCENARIOS]
    with open(out, "w") as f:
        json.dump(scenarios, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
