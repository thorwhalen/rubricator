"""Grade a rescore-criterion adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``rescore-criterion`` prompt) is given each scenario's packet
and writes a JSON array of ``{"scenarioId", "calls", "reply"}``, where ``calls`` is the ordered list
of ``{"tool", "arguments"}`` it would make. Its ``measures_write`` calls are replayed, in order,
against a fresh copy of the scenario's analysis (``scripts/rescore_criterion_scenarios.py``), so
"accepted" means the real verb took every one of them, ``supersedes`` included. Nothing here calls
a model. **Prior true** is printed first: a pass that saw the earlier score and says it did not is
the failure this prompt exists to stop, and it is invisible in the stored record afterwards.

Every metric is ``None`` (not applicable) rather than passing when there is nothing for it to judge,
so a run that writes nothing cannot score on what it did not do.

    python scripts/rescore_criterion_adherence.py docs/evaluation/rescore-criterion/scenarios.json out-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rescore_criterion_scenarios import ANALYSIS_ID, build  # noqa: E402

#: Reads that return a stored cell's value, justification or evidence, or rates over them.
#: ``analysis_get`` is one only in its ``full`` view, which links the document itself.
PRIOR_READS = {"report_weaknesses", "aggregate_assertions", "stability_report", "report_completeness",
               "resources/read"}
METRICS = ("prior_true", "action_right", "asks_right", "scope_right", "supersedes_right", "round_right", "accepted",
           "right_outcome", "no_mark_missing", "no_prior_read", "fresh_retrieval", "prior_line")


def _line(reply: str, label: str) -> str | None:
    match = re.search(rf"^\W*{re.escape(label)}\W*:\s*(.+)$", reply, re.M | re.I)
    return match.group(1) if match else None


def _reads_prior(call: Mapping[str, Any]) -> bool:
    args = call.get("arguments") or {}
    return call.get("tool") in PRIOR_READS or (
        call.get("tool") == "analysis_get" and args.get("view") == "full")


def _outcome(cell: Mapping[str, Any]) -> Any:
    return cell["value"] if "value" in cell else (cell.get("missing") or {}).get("code")


def _accepted(scenario_id: str, writes: list[Mapping[str, Any]]) -> bool:
    """Whether the real verb takes every write, in order, on a fresh copy of the scenario."""
    verbs = build(scenario_id)
    try:
        for args in writes:
            verbs["measures_write"](**{"analysis_id": ANALYSIS_ID, **args})
    # The verbs' refusals, and a call whose keywords the verb does not take (the subject's error);
    # anything else is a grader bug and raises.
    except (ValueError, LookupError, TypeError):
        return False
    return True


def _searched_each(calls, alternatives) -> bool:
    """A search of its own per alternative in scope, over the whole corpus (no document or phrase filter)."""
    open_queries = [
        str(args.get("query", "")).lower() for args in (c.get("arguments") or {} for c in calls)
        if not args.get("document_ids") and not args.get("must_include")
    ]
    own = {alt: [q for q in open_queries if alt in q and not any(o in q for o in alternatives if o != alt)]
           for alt in alternatives}
    return all(own.values())


def _all_or_none(checks: list[bool]) -> bool | None:
    return all(checks) if checks else None


def _ask_row(want: Mapping[str, Any], writes, reply: str, row: dict) -> dict:
    row["action_right"] = not writes
    row["asks_right"] = bool(re.search(want["asks"], reply, re.I))
    if want.get("prior") == "shown":
        row["prior_true"] = row["asks_right"]
    return row


def grade_one(scenario: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, bool | None]:
    """One scenario's checks; ``None`` where a check does not apply to it."""
    want, reply = scenario["expected"], output.get("reply", "")
    calls = output.get("calls") or []
    at = [i for i, c in enumerate(calls) if c.get("tool") == "measures_write"]
    writes = [calls[i].get("arguments") or {} for i in at]
    row: dict[str, bool | None] = dict.fromkeys(METRICS)
    if calls:
        row["no_mark_missing"] = not any(c.get("tool") == "measures_mark_missing" for c in calls)
    if want["action"] == "ask" and not (want.get("either") and writes):
        return _ask_row(want, writes, reply, row)
    row["action_right"] = bool(writes)
    if not writes:
        return row
    cells = [(cell, args.get("procedure") or {}) for args in writes for cell in args.get("cells") or []]
    procs = [proc for _, proc in cells]
    row["prior_true"] = _all_or_none([
        p.get("prior") == want["prior"] and (want["session"] is None or p.get("session") == want["session"])
        for p in procs])
    row["round_right"] = _all_or_none([p.get("round") == want["round"] for p in procs])
    expected = {alt: tuple(v) for alt, v in want["cells"].items()}
    written = {cell.get("alternativeId"): cell for cell, _ in cells if cell.get("criterionId") == scenario["criterion"]}
    row["scope_right"] = (set(written) == set(expected) and len(cells) == len(written)
                          and all(len(w.get("cells") or []) == 1 for w in writes))
    both = [alt for alt in expected if alt in written]
    row["supersedes_right"] = _all_or_none([written[a].get("supersedes") == expected[a][1] for a in both])
    row["right_outcome"] = _all_or_none([_outcome(written[a]) == expected[a][0] for a in both])
    row["accepted"] = _accepted(scenario["id"], writes)
    if want["prior"] == "withheld":
        row["no_prior_read"] = not any(_reads_prior(c) for c in calls[: at[-1] + 1])
    if not want.get("resumed"):
        row["fresh_retrieval"] = _searched_each(
            [c for c in calls[: at[0]] if c.get("tool") == "corpus_search"], expected)
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
