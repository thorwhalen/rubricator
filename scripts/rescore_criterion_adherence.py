"""Grade a rescore-criterion adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``rescore-criterion`` prompt) is given each scenario's packet
and writes a JSON array of ``{"scenarioId", "calls", "reply"}``, where ``calls`` is the ordered list
of ``{"tool", "arguments"}`` it would make. Its ``measures_write`` calls are replayed, in order,
against a fresh copy of the scenario's analysis (``scripts/rescore_criterion_scenarios.py``), so
"accepted" means the real verb took every one of them, ``supersedes`` included. Nothing here calls
a model. **Prior true** is printed first: a pass that saw the earlier score and says it did not is
the failure this prompt exists to stop, and it is invisible in the stored record afterwards.

    python scripts/rescore_criterion_adherence.py docs/evaluation/rescore-criterion/scenarios.json out-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rescore_criterion_scenarios import build  # noqa: E402

#: Reads that return a stored cell's value, justification or evidence. ``analysis_get`` is one only
#: in its ``full`` view, which links the document itself.
PRIOR_READS = {"report_weaknesses", "aggregate_assertions", "stability_report", "resources/read"}
METRICS = ("prior_true", "action_right", "scope_right", "supersedes_right", "accepted",
           "right_outcome", "no_mark_missing", "no_prior_read", "fresh_retrieval", "prior_line")


def _line(reply: str, label: str) -> str | None:
    match = re.search(rf"^\W*{re.escape(label)}\W*:\s*(.+)$", reply, re.M | re.I)
    return match.group(1) if match else None


def _reads_prior(call: Mapping[str, Any]) -> bool:
    args = call.get("arguments") or {}
    return call.get("tool") in PRIOR_READS or (
        call.get("tool") == "analysis_get" and args.get("view") == "full")


def _writes(calls):
    return [(i, c.get("arguments") or {}) for i, c in enumerate(calls) if c.get("tool") == "measures_write"]


def _outcome(cell: Mapping[str, Any]) -> Any:
    return cell["value"] if "value" in cell else (cell.get("missing") or {}).get("code")


def _replay(scenario_id: str, writes) -> bool:
    verbs = build(scenario_id)
    try:
        for _, args in writes:
            verbs["measures_write"](**{"analysis_id": "kettles", **args})
    except Exception:  # noqa: BLE001 -- any refusal is the finding
        return False
    return True


def grade_one(scenario: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, bool | None]:
    """One scenario's checks; ``None`` where a check does not apply to it."""
    want, reply = scenario["expected"], output.get("reply", "")
    calls = output.get("calls") or []
    writes = _writes(calls)
    cells = [(cell, args.get("procedure") or {}) for _, args in writes for cell in args.get("cells") or []]
    row: dict[str, bool | None] = dict.fromkeys(METRICS)
    row["no_mark_missing"] = not any(c.get("tool") == "measures_mark_missing" for c in calls)
    if want["action"] == "ask" and not (want.get("either") and writes):
        row["action_right"] = not writes
        if want.get("prior") == "shown":
            # Asked instead of writing: the reply must still say the earlier scores are in view.
            row["prior_true"] = bool(re.search(r"shown|in (this|the) conversation|fresh conversation", reply, re.I))
        return row
    row["action_right"] = bool(writes)
    row["prior_true"] = bool(cells) and all(
        proc.get("prior") == want["prior"] and (want["session"] is None or proc.get("session") == want["session"])
        for _, proc in cells)
    expected = {alt: tuple(v) for alt, v in want["cells"].items()}
    written = {cell.get("alternativeId"): cell for cell, _ in cells if cell.get("criterionId") == scenario["criterion"]}
    row["scope_right"] = set(written) == set(expected) and len(cells) == len(written)
    row["supersedes_right"] = all(
        written[alt].get("supersedes") == expected[alt][1] for alt in expected if alt in written)
    row["right_outcome"] = all(_outcome(written[alt]) == expected[alt][0] for alt in expected if alt in written)
    row["accepted"] = _replay(scenario["id"], writes)
    first_write = writes[0][0] if writes else len(calls)
    if want["prior"] == "withheld":
        row["no_prior_read"] = not any(_reads_prior(c) for c in calls[: writes[-1][0] + 1] if writes)
    searches = [c.get("arguments") or {} for c in calls[:first_write] if c.get("tool") == "corpus_search"]
    row["fresh_retrieval"] = bool(searches) and not any(s.get("document_ids") for s in searches)
    row["prior_line"] = (_line(reply, "Prior") or "").strip().lower().startswith(want["prior"])
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
