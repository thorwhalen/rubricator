"""Grade the procedure facts a scorer passes on a repeated pass (#218): scenarios in, one table out.

``score-cell`` v4 teaches a scorer to describe a repeated pass to ``measures_write`` (or
``measures_mark_missing``) through the closed ``procedure`` argument and to state only what is
true of the pass. This builds the packet a subject is given and grades the ``procedure`` it
would pass, against ``docs/evaluation/score-cell/procedure.json``. Nothing here calls a model.

    python scripts/score_cell_procedure.py --packet OUT.json
    python scripts/score_cell_procedure.py out-v4-sonnet.json [...]

The subject writes ``[{"cellId", "output", "call": {"tool", "procedure"}}]`` -- one entry per
scenario id, ``cellId`` carrying the scenario id -- where ``procedure`` is ``null`` when it passes
none. The graded things, each counted per scenario:

- **valid**: the procedure passes the tool's own check (only the six facts, in range);
- **true**: every fact the scenario fixes is what it says, none the scenario forbids is claimed;
- **left out**: a fact the harness did not give is not invented;
- **no claim of independence**: no key naming one, and no count, model or time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

from rubricator.procedure import check_facts

EVALUATION = Path(__file__).resolve().parent.parent / "docs" / "evaluation" / "score-cell"
TOOLS = ("measures_write", "measures_mark_missing")


def load() -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    return (json.loads((EVALUATION / "cells.json").read_text()),
            json.loads((EVALUATION / "procedure.json").read_text()))


def packet() -> list[dict[str, Any]]:
    """What a subject is given: the cell and what the harness and the conversation said."""
    cells, scenarios = load()
    by_id = {c["id"]: c for c in cells["cells"]}
    out = []
    for s in scenarios["scenarios"]:
        c = by_id[s["cell"]]
        out.append({"cellId": s["id"], "alternative": c["alternative"], "criterion": c["criterion"],
                    "criterionDefinition": cells["criteria"][c["criterion"]],
                    "retrieval": c["retrieval"], "spans": c["spans"],
                    "conversationSoFar": s["conversationSoFar"]})
    return out


def _procedure(output: Mapping[str, Any]) -> tuple[bool, Any]:
    """``(a call was made, its procedure)``; a missing call counts as a procedure of none."""
    call = output.get("call") or {}
    return call.get("tool") in TOOLS, call.get("procedure")


def grade_one(expect: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, bool]:
    made, facts = _procedure(output)
    if expect.get("omit"):
        return {"valid": made, "true": not facts, "left out": not facts, "no independence": not facts}
    facts = facts if isinstance(facts, Mapping) else None
    valid = made and facts is not None
    if valid:
        try:
            check_facts(facts)
        except ValueError:
            valid = False
    facts = facts or {}
    must, must_not = expect.get("must", {}), expect.get("mustNot", {})
    true = valid and all(facts.get(k) == v for k, v in must.items()) and all(
        facts.get(k) not in vs for k, vs in must_not.items())
    return {
        "valid": valid,
        "true": bool(true),
        "left out": valid and not any(k in facts for k in expect.get("absent", ())),
        "no independence": valid and "independen" not in json.dumps(output.get("call", {})).lower(),
    }


def grade(runs: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    _, scenarios = load()
    expects = {s["id"]: s["expect"] for s in scenarios["scenarios"]}
    table: dict[str, Any] = {}
    for name, run in runs.items():
        by_id = {o["cellId"]: o for o in run}
        totals: dict[str, list[int]] = {}
        failed = []
        for sid, expect in expects.items():
            result = grade_one(expect, by_id.get(sid, {}))
            for k, ok in result.items():
                totals.setdefault(k, [0, 0])
                totals[k][0] += ok
                totals[k][1] += 1
            if not all(result.values()):
                failed.append(sid)
        table[name] = {k: f"{a}/{b}" for k, (a, b) in totals.items()} | {"failed": failed}
    return table


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--packet"] and len(args) == 2:
        Path(args[1]).write_text(json.dumps(packet(), indent=1, ensure_ascii=False))
    elif args:
        print(json.dumps(grade({Path(a).stem: json.loads(Path(a).read_text()) for a in args}), indent=1))
    else:
        sys.exit(__doc__)
