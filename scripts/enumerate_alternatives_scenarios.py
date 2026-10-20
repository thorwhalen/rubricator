"""Write the ``enumerate-alternatives`` evaluation's scenarios: invented questions and what a faithful stage 2 does.

The input is the user's message (and, in one scenario, a source), so the expectations are
hand-authored here, one place; ``tests/test_enumerate_alternatives_prompt.py`` fails if the
stored file drifts from them. Nothing calls a model.

    python scripts/enumerate_alternatives_scenarios.py docs/evaluation/enumerate-alternatives/scenarios.json
"""

from __future__ import annotations

import json
import sys

SCENARIOS = [
    {
        "id": "e1", "question": "I'm choosing between the Aldous 4, the Brandt 6 and the Corvin 5 ovens for the bread line.",
        "point": "three named: all three written, nothing added to the set",
        "expected": {"stated": ["Aldous", "Brandt", "Corvin"], "exact": True, "duplicates": None, "sourced": None,
                     "inferred": "proposed"},
    },
    {
        "id": "e2", "question": "Compare Postgres, PostgreSQL, MySQL and SQLite for our reporting app.",
        "point": "Postgres and PostgreSQL probably coincide, but that is the user's call: both rows stay, the pair is asked about",
        "expected": {"stated": ["Postgres\\b", "PostgreSQL", "MySQL", "SQLite"], "exact": True,
                     "duplicates": ["Postgres\\b", "PostgreSQL"], "sourced": None, "inferred": "proposed"},
    },
    {
        "id": "e3", "question": "Which of the Brandt 6 and the Corvin 5 should replace our oven?",
        "source": ("Review notes, March: we looked at the Brandt 6 and the Corvin 5. The Delmar 3 was also reviewed "
                   "and withdrawn from sale in April."),
        "point": "a supplied source mentions a third oven the user did not name: proposed with its span, not written",
        "expected": {"stated": ["Brandt", "Corvin"], "exact": True, "duplicates": None,
                     "sourced": {"label": "Delmar", "span": "Delmar 3 was also reviewed"}, "inferred": "proposed"},
    },
    {
        "id": "e4", "question": "Which note-taking app should I use?",
        "point": "nothing named: the set is empty, any suggestion is a proposal marked as the model's own",
        "expected": {"stated": [], "exact": True, "duplicates": None, "sourced": None, "inferred": "proposed"},
    },
    {
        "id": "e5", "question": "Suggest three plausible static site generators for a docs site and compare them.",
        "point": "the user asked for candidates: they may enter the set, each marked as the model's own inference",
        "expected": {"stated": [], "exact": False, "minimum": 2, "duplicates": None, "sourced": None,
                     "inferred": "described"},
    },
]


def main(path: str) -> None:
    with open(path, "w") as f:
        json.dump(SCENARIOS, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:2])
