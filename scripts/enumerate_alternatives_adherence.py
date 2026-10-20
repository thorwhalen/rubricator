"""Grade an ``enumerate-alternatives`` adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the prompt) is given each scenario's question (and source) and
writes a JSON array of ``{"scenarioId", "output"}``. The output holds the prompt's JSON block;
this script runs its ``alternatives`` through the real ``alternatives_set`` verb (the "feeds it
with no repair" check) and grades the block against
``docs/evaluation/enumerate-alternatives/scenarios.json``. Nothing calls a model.
**No unlicensed rows** and **duplicates kept and flagged** are the metrics the prompt exists for.

    python scripts/enumerate_alternatives_adherence.py docs/evaluation/enumerate-alternatives/scenarios.json out-v1-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from rubricator.compose import build_runtime
from rubricator.surface import bind

FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)
METRICS = ("parses", "feeds alternatives_set", "keeps the stated", "no unlicensed rows",
           "duplicates kept and flagged", "source candidate proposed with span", "inference marked")


def parse(output: str) -> dict[str, Any] | None:
    """The last JSON object in a fence, or None."""
    found = FENCE.findall(output)
    try:
        return json.loads(found[-1]) if found else None
    except ValueError:
        return None


def feeds_alternatives_set(block: Mapping[str, Any]) -> bool:
    """True when the real verb takes the block's ``alternatives`` as they stand."""
    verbs = bind(build_runtime(blobs={}, now=lambda: "2026-10-20T09:00:00Z"))
    verbs["analysis_open"](analysis_id="a", question="q")
    try:
        verbs["alternatives_set"](analysis_id="a", alternatives=block["alternatives"])
    except Exception:  # noqa: BLE001 -- any refusal is the failure being counted
        return False
    return True


def _rows(block: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows = block.get(key)
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _label_index(rows, pattern: str) -> int | None:
    return next((i for i, r in enumerate(rows) if re.search(pattern, str(r.get("label", "")), re.I)), None)


def grade_one(scenario: Mapping[str, Any], output: str) -> dict[str, bool | None]:
    want, block = scenario["expected"], parse(output)
    if block is None:
        return {m: False for m in METRICS}
    alts, proposed = _rows(block, "alternatives"), _rows(block, "proposed")
    labelled = [r for r in alts if r.get("label")]
    stated_found = [_label_index(alts, p) for p in want["stated"]]
    if want["exact"]:
        unlicensed = len(alts) <= len(want["stated"])
    else:
        unlicensed = len(alts) >= want["minimum"]
    dupes = want["duplicates"]
    flagged = None
    if dupes:
        pairs = [d.get("ids") for d in _rows(block, "possibleDuplicates")]
        ids = [alts[_label_index(alts, p)].get("id") if _label_index(alts, p) is not None else None for p in dupes]
        flagged = all(i is not None for i in ids) and any(isinstance(p, list) and set(ids) <= set(p) for p in pairs)
    sourced = want["sourced"]
    if want["inferred"] == "described":
        inferred = bool(alts) and all(re.search(r"own inference", str(r.get("description", "")), re.I) for r in alts)
    else:
        inferred = all(r.get("basis") in ("source", "inference") for r in proposed) and \
            all(r.get("basis") == "inference" or sourced for r in proposed)
    return {
        "parses": True,
        "feeds alternatives_set": "alternatives" in block and feeds_alternatives_set(block),
        "keeps the stated": all(i is not None for i in stated_found) if want["stated"] else None,
        "no unlicensed rows": unlicensed and len(labelled) == len(alts),
        "duplicates kept and flagged": flagged,
        "source candidate proposed with span": (
            any(re.search(sourced["label"], str(r.get("label", "")), re.I) and r.get("basis") == "source"
                and sourced["span"].lower() in str(r.get("why", "")).lower() for r in proposed)
            and _label_index(alts, sourced["label"]) is None
        ) if sourced else None,
        "inference marked": inferred,
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
