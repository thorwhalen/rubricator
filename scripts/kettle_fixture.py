"""The invented kettle fixture shared by the add-criterion and rescore-criterion evaluations (#295).

Three invented kettles, a human contributor, and three criteria with full definitions. Both scenario
builders start from it, so neither evaluation imports its fixture from the other's builder.
"""

from __future__ import annotations

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
