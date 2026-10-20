"""Grade an add-criterion adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``add-criterion`` prompt) is given each scenario's
request and tool results and writes a JSON array of ``{"scenarioId", "calls", "reply"}``,
where ``calls`` is the ordered list of ``{"tool", "arguments"}`` it would make. Its
``criteria_set`` call is replayed against a fresh copy of the scenario's analysis
(``scripts/add_criterion_scenarios.py``), so "accepted" means the real verb took it. Nothing
here calls a model. **Existing untouched** is printed first: an existing criterion re-typed
into the call supersedes its cells, which is the regression this prompt exists to stop.

    python scripts/add_criterion_adherence.py docs/evaluation/add-criterion/scenarios.json out-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from add_criterion_scenarios import build  # noqa: E402

WRITES = {"measures_write", "measures_mark_missing"}
DEFINITION = ("objective", "question", "evidenceRule", "missingRules", "exclusions")
METRICS = ("existing_untouched", "action_right", "no_cell_written", "accepted", "new_fully_defined",
           "nothing_superseded", "says_not_assessed", "next_is_confirm", "names_the_criterion")


def _line(reply: str, label: str) -> str | None:
    match = re.search(rf"^\W*{re.escape(label)}\W*:\s*(.+)$", reply, re.M | re.I)
    return match.group(1) if match else None


def grade_one(scenario: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, bool | None]:
    """One scenario's checks; ``None`` where a check does not apply to it."""
    want, reply = scenario["expected"], output.get("reply", "")
    calls = output.get("calls") or []
    sets = [c["arguments"] for c in calls if c.get("tool") == "criteria_set"]
    existing = scenario["toolResults"]["analysis_get"]["criteria"]
    row: dict[str, bool | None] = dict.fromkeys(METRICS)
    row["no_cell_written"] = not any(c.get("tool") in WRITES for c in calls)
    if want["action"] == "ask":
        row["action_right"] = not sets
        if want["names"]:
            row["names_the_criterion"] = want["names"] in reply or (
                next(c["label"] for c in existing if c["id"] == want["names"]).lower() in reply.lower())
        return row
    row["action_right"] = len(sets) == 1
    column = _line(reply, "New column") or ""
    row["says_not_assessed"] = "not-assessed" in column or "nobody has looked" in column.lower()
    row["next_is_confirm"] = "confirm" in (_line(reply, "Next") or "").lower()
    if not sets:
        return row
    sent = sets[0].get("criteria") or []
    row["existing_untouched"] = sent[: len(existing)] == existing and not sets[0].get("editorial")
    new = [c for c in sent if c.get("id") not in {e["id"] for e in existing}]
    try:
        result = build()["criteria_set"](**{"analysis_id": "kettles", **sets[0]})
    except Exception:  # noqa: BLE001 -- any refusal is the finding
        row["accepted"] = False
        return row
    row["accepted"] = len(new) == 1
    gaps = {g["criterionId"] for g in result["definitionGaps"]}
    row["new_fully_defined"] = bool(new) and all(
        n["id"] not in gaps and all((n.get("definition") or {}).get(f) for f in DEFINITION) for n in new)
    row["nothing_superseded"] = not result["revised"] and result["supersededCells"]["count"] == 0
    return row


def grade(scenarios: list[Mapping[str, Any]], outputs: list[Mapping[str, Any]]) -> dict[str, list[int]]:
    """Per metric, ``[hits, applicable]`` over the scenarios a run answered."""
    by_id = {o["scenarioId"]: o for o in outputs}
    totals = {m: [0, 0] for m in METRICS}
    for scenario in scenarios:
        if scenario["id"] not in by_id:
            continue
        for metric, ok in grade_one(scenario, by_id[scenario["id"]]).items():
            if ok is not None:
                totals[metric][0] += ok
                totals[metric][1] += 1
    return totals


def main(scenarios_path: str, *runs: str) -> None:
    scenarios = json.loads(Path(scenarios_path).read_text())
    print("| arm | " + " | ".join(m.replace("_", " ") for m in METRICS) + " |")
    print("|---" * (len(METRICS) + 1) + "|")
    for run in runs:
        row = grade(scenarios, json.loads(Path(run).read_text()))
        cells = " | ".join(f"{h}/{n}" if n else "n/a" for h, n in row.values())
        print(f"| {Path(run).stem} | {cells} |")


if __name__ == "__main__":
    main(*sys.argv[1:])
