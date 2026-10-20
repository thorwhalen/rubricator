"""Grade an audit-existing adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``audit-existing`` prompt) is given each
scenario's request and the three reads, and writes a JSON array of
``{"scenarioId", "output"}``. This script parses the block the prompt asks for and
grades it against ``docs/evaluation/audit-existing/scenarios.json`` (built by
``scripts/audit_existing_scenarios.py``). Nothing here calls a model. **Wrote
nothing** is printed first: an audit that writes to the analysis it audits is the
failure this prompt exists to stop.

    python scripts/audit_existing_adherence.py docs/evaluation/audit-existing/scenarios.json out-v1-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

LINES = {
    "Uncited or thinly cited": "thin",
    "Rests on inference only": "inference",
    "Confidence above its evidence": "confidence",
    "No direction of preference": "direction",
    "Overlap to put to the author": "overlap",
    "Redefine": "redefine",
    "Changed": "changed",
}
CRITERIA = ("yearly-cost", "volunteer-effort", "ease-of-use", "offline-mode")
CELL = re.compile(r"\b([a-z][\w-]*)/([a-z][\w-]*)\b")
#: A call to a verb that writes, as the subject writes calls (``CALL verb(``) or names them as made.
WRITES = re.compile(r"CALL\s+(measures_write|measures_mark_missing|criteria_set|frame_set|alternatives_set"
                    r"|frame_confirm|corpus_add)\b")


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


def _criteria(text: str) -> set[str]:
    text = re.sub(r"(?<=[a-z]) (?=[a-z])", "-", (text or "").lower())
    return {c for c in CRITERIA if re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", text)}


def _pairs(text: str) -> set[frozenset[str]]:
    return {frozenset(p) for part in re.split(r"[,;]", text or "") if len(p := _criteria(part)) == 2}


def grade_one(scenario: Mapping[str, Any], output: str) -> dict[str, bool | None]:
    want, got = scenario["expected"], block(output)
    return {
        "wrote nothing": not WRITES.search(output) and got.get("changed", "").lower().startswith("nothing"),
        "complete": set(got) == set(LINES.values()),
        "thin right": _cells(got.get("thin", "")) == set(want["thin"]),
        "inference right": _cells(got.get("inference", "")) == set(want["inference"]),
        "confidence right": _cells(got.get("confidence", "")) == set(want["confidence"]),
        "direction right": _criteria(got.get("direction", "")) == set(want["direction"]),
        "overlap right": _pairs(got.get("overlap", "")) == {frozenset(p) for p in want["overlap"]},
        "redefine right": _criteria(got.get("redefine", "")) == set(want["redefine"]),
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
