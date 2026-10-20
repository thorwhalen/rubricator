"""Grade a ``frame`` adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``frame`` prompt) is given each scenario's question and
writes a JSON array of ``{"scenarioId", "output"}``. The output holds the prompt's JSON block;
this script runs it through the real ``frame_set`` verb (the "feeds frame_set with no repair"
check) and grades it against ``docs/evaluation/frame/scenarios.json``. Nothing calls a model.
**Names the ambiguities** is the metric the prompt exists for: a question that gives nothing
and comes back with an empty list is the confident reading it stops.

    python scripts/frame_adherence.py docs/evaluation/frame/scenarios.json out-v1-*.json
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
#: A stand-in a decider or context field must not carry: it is a blank written as a value.
PLACEHOLDER = re.compile(r"^\s*(unknown|n/?a|none|unspecified|not (stated|specified)|tbd|the (user|team)|you)\s*\.?\s*$", re.I)


def parse(output: str) -> dict[str, Any] | None:
    """The last JSON object in a fence, or None."""
    found = FENCE.findall(output)
    try:
        return json.loads(found[-1]) if found else None
    except ValueError:
        return None


def feeds_frame_set(args: Mapping[str, Any]) -> bool:
    """True when the real verb takes the block as it stands."""
    verbs = bind(build_runtime(blobs={}, now=lambda: "2026-10-20T09:00:00Z"))
    verbs["analysis_open"](analysis_id="a", question="q")
    try:
        verbs["frame_set"](analysis_id="a", **args)
    except Exception:  # noqa: BLE001 -- any refusal is the failure being counted
        return False
    return True


def _decider_ok(want: Mapping[str, Any], decider: Any) -> bool:
    """Absent where nobody was named; a named one only where the message plausibly names it (``deciderMayBe``)."""
    if want["decider"] is not None:
        return bool(decider and re.search(want["decider"], decider, re.I))
    return not decider or bool(want.get("deciderMayBe") and re.search(want["deciderMayBe"], decider, re.I))


def grade_one(scenario: Mapping[str, Any], output: str) -> dict[str, bool | None]:
    want, args = scenario["expected"], parse(output)
    if args is None:
        return {m: False for m in ("parses", "feeds frame_set", "names the ambiguities", "no invented decider",
                                   "no placeholder", "no false none")}
    ambiguities = args.get("ambiguities")
    named = ambiguities if isinstance(ambiguities, list) else []
    text = " ".join(map(str, named))
    decider = args.get("decider")
    return {
        "parses": True,
        "feeds frame_set": feeds_frame_set(args),
        # every topic the author found open is named by some ambiguity
        "names the ambiguities": (all(re.search(p, text, re.I) for p in want["topics"].values())
                                  if want["ambiguous"] else None),
        "no invented decider": _decider_ok(want, decider),
        "no placeholder": not any(isinstance(args.get(k), str) and PLACEHOLDER.match(args[k]) for k in ("decider", "context")),
        # an empty list where the question gives nothing is the confident reading
        "no false none": bool(named) if want["ambiguous"] else None,
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
