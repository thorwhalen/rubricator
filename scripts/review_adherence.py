"""Grade a review adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``review`` prompt) is given each scenario's
``report_weaknesses`` result and writes a JSON array of ``{"scenarioId", "output"}``.
This script parses the fixed block the prompt asks for and grades it against
``docs/evaluation/review/scenarios.json`` (built by ``scripts/review_scenarios.py``).
Nothing here calls a model. **Kept apart** is printed first: a cell of a criterion
to redefine sent back for re-scoring is the failure this prompt exists to stop.

    python scripts/review_adherence.py docs/evaluation/review/scenarios.json out-v1-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

LINES = {
    "Re-score with more evidence": "rescore",
    "Redefine, then put back to the user": "redefine",
    "Most likely to change the picture": "most",
    "Vetoed or untested floors": "vetoes",
    "Correlations": "correlations",
    "Next": "next",
}
CELL = re.compile(r"\b([a-z][\w-]*)/([a-z][\w-]*)\b")
#: Reading a correlation as overlap: a sentence that says so, with no negation in it.
REDUNDANCY = re.compile(r"\b(redundan\w*|measur\w* the same|merg\w*|collaps\w*|double[- ]count\w*)", re.I)
NEGATION = re.compile(r"\b(not|never|no|none|nor|nothing|isn't|aren't|doesn't|don't|cannot|can't|without"
                      r"|rather than|instead of)\b", re.I)
#: Proposing a value for a cell instead of the evidence that would settle it.
SUGGESTED = re.compile(r"\b(should|would|could|likely) (be|score|read|sit|land) (at |as |around |a )?[1-5]\b"
                       r"|\b(re-?score|raise|lower|bump|set) (it |this cell |the cell )?(to|at) (a )?[1-5]\b", re.I)


def block(output: str) -> dict[str, str]:
    """The block's lines by key: the last occurrence of each label wins, prose above it is ignored."""
    found = {}
    for line in output.splitlines():
        for label, key in LINES.items():
            if line.strip().startswith(label + ":"):
                found[key] = line.split(":", 1)[1].strip()
    return found


def _cells(text: str) -> set[str]:
    return {f"{a}/{c}" for a, c in CELL.findall(text or "")}


def _names(text: str, ids) -> set[str]:
    return {i for i in ids if re.search(rf"\b{re.escape(i)}\b", text or "")}


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]


def grade_one(scenario: Mapping[str, Any], output: str) -> dict[str, bool | None]:
    want, got = scenario["expected"], block(output)
    criteria = {c.split("/")[1] for c in want["rescore"] + want["vetoes"]} | set(want["redefine"])
    criteria |= {"theft-resistance", "upkeep-cost", "weather-sealing"}
    rescored = _cells(got.get("rescore", ""))
    most = got.get("most", "")
    if want["mostLikely"]:
        most_right = bool(_cells(most) & set(want["mostLikely"]) or _names(most, want["mostLikely"]))
    else:
        most_right = most.lower().startswith("none")
    relabelled = any(REDUNDANCY.search(s) and not NEGATION.search(s) for s in _sentences(output))
    return {
        "kept apart": not any(c.split("/")[1] in want["redefine"] for c in rescored),
        "complete": set(got) == set(LINES.values()),
        "rescore right": rescored == set(want["rescore"]),
        "redefine right": _names(got.get("redefine", ""), criteria) == set(want["redefine"]),
        "most right": most_right,
        "vetoes right": _cells(got.get("vetoes", "")) == set(want["vetoes"]),
        "no redundancy reading": not relabelled,
        "no suggested score": not SUGGESTED.search(output),
    }


def grade(scenarios, outputs) -> dict[str, tuple[int, int]]:
    by_id = {o["scenarioId"]: o["output"] for o in outputs}
    totals: dict[str, list[int]] = {}
    for s in scenarios:
        for metric, ok in grade_one(s, by_id.get(s["id"], "")).items():
            if ok is None:
                continue
            t = totals.setdefault(metric, [0, 0])
            t[0] += bool(ok)
            t[1] += 1
    return {k: (v[0], v[1]) for k, v in totals.items()}


def main(scenarios_path: str, *runs: str) -> None:
    scenarios = json.loads(Path(scenarios_path).read_text())
    for run in runs:
        row = grade(scenarios, json.loads(Path(run).read_text()))
        print(Path(run).name, " | ".join(f"{k} {a}/{n}" for k, (a, n) in row.items()))


if __name__ == "__main__":
    main(*sys.argv[1:])
