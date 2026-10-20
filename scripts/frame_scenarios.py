"""Write the ``frame`` evaluation's scenarios: invented questions, and what a faithful frame names.

Unlike the later stages there is no tool output to read the expectations off: the input is
the user's message. So the expectations are hand-authored here, one place, and
``tests/test_frame_prompt.py`` fails if the stored file drifts from them. Each ambiguity is a
topic with a pattern a named ambiguity must match, so the grader checks that the open points
were *named*, not that the subject agreed with the author's wording. Nothing calls a model.

    python scripts/frame_scenarios.py docs/evaluation/frame/scenarios.json
"""

from __future__ import annotations

import json
import sys

SCENARIOS = [
    {
        "id": "f1", "question": "Help me pick a coffee grinder.",
        "point": "no decider beyond 'me', no budget, no use: a confident reading would invent all three",
        "expected": {"decider": None, "ambiguous": True,
                     "topics": {"use": "brew|espresso|drip|use|purpose|how", "budget": "budget|price|cost|spend"}},
    },
    {
        "id": "f2", "question": "Should we move the reading room to the old mill?",
        "point": "'we' names nobody; 'move' leaves open whether the old mill is the only option",
        "expected": {"decider": None, "ambiguous": True,
                     "topics": {"who": r"\bwe\b|who (decides|is deciding|makes)|decider|decision[- ]maker",
                                "options": "alternative|other (site|option|location)|instead|only option|stay"}},
    },
    {
        "id": "f3", "question": "Which database should we use?",
        "point": "nothing is stated except a category; every one of decider, workload and meaning of 'use' is open",
        "expected": {"decider": None, "ambiguous": True,
                     "topics": {"who": r"\bwe\b|who (decides|is deciding|makes)|decider|decision[- ]maker",
                                "workload": "workload|data|scale|size|query|read|write|application|purpose|for what"}},
    },
    {
        "id": "f4", "question": "Rank our three volunteer-scheduling tools for the food bank board.",
        "point": "the board is named as the audience, not clearly as the decider; 'rank' is not 'choose one'",
        "expected": {"decider": None, "deciderMayBe": "board", "ambiguous": True,
                     "topics": {"what": "rank|choose|pick|select|shortlist|adopt|replace|decision",
                                "basis": "criteria|basis|matter|important|by what|how|judged|on what"}},
    },
    {
        "id": "f5",
        "question": ("I own Pelham Bakery and I alone decide which of three ovens, the Aldous 4, the Brandt 6 and the "
                     "Corvin 5, goes on the bread line. The budget is fixed at 12,000 and it has to fit a 2 m bay."),
        "point": "decider, decision and bounds are all stated: the frame may be recorded with no ambiguity, and must not invent a decider",
        "expected": {"decider": "owner|Pelham|I alone|the user", "ambiguous": False, "topics": {}},
    },
]


def main(path: str) -> None:
    with open(path, "w") as f:
        json.dump(SCENARIOS, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:2])
