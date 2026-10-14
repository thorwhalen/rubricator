"""Grade the procedure facts a scorer passes with each pass (#218): scenarios in, one table out.

``score-cell`` v4 teaches a scorer to describe a pass to ``measures_write`` (or
``measures_mark_missing``) through the closed ``procedure`` argument and to state only what is
true of the pass. This builds the packet a subject is given and grades the ``procedure`` it
would pass, against ``docs/evaluation/score-cell/procedure.json``. Nothing here calls a model.

    python scripts/score_cell_procedure.py --packet OUT.json
    python scripts/score_cell_procedure.py out-v4-sonnet.json [...]

The subject writes ``[{"cellId", "output", "call": {"tool", "procedure"}}]`` -- one entry per
scenario id, ``cellId`` carrying the scenario id -- where ``procedure`` is ``null`` when it passes
none, and a ``measures_mark_missing`` call also carries ``alternative_ids`` and ``criterion_ids``.
The graded things, each counted per scenario:

- **valid**: a write call whose procedure passes the tool's own check (only the six facts, in
  range), and a ``measures_mark_missing`` that names exactly its one cell;
- **true**: every fact the scenario fixes is what it says, none the scenario forbids is claimed;
- **left out**: a fact the scenario does not give is not invented (a fact outside `must` and `may` fails);
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


def _call(output: Mapping[str, Any]) -> Mapping[str, Any]:
    call = output.get("call")
    return call if isinstance(call, Mapping) and call.get("tool") in TOOLS else {}


def _names_its_cell(call: Mapping[str, Any], cell: Mapping[str, Any]) -> bool:
    """``measures_mark_missing`` names exactly the one alternative and criterion; the other tool needs no ids."""
    if call.get("tool") != "measures_mark_missing":
        return True
    return (call.get("alternative_ids") == [cell["alternative"]]
            and call.get("criterion_ids") == [cell["criterion"]])


def grade_one(expect: Mapping[str, Any], output: Mapping[str, Any], cell: Mapping[str, Any]) -> dict[str, bool]:
    """Four verdicts on one scenario.

    ``valid``: a write call was made, its procedure (if the scenario wants one) passes the
    tool's own check, and a ``measures_mark_missing`` names its one cell. ``true``: the
    facts the scenario fixes are as it says. ``left out`` and ``no independence`` read what
    was passed whether or not it was valid: a stated fact outside ``must`` and ``may`` is
    invented, and any word of independence in the call is a claim. Passing no procedure
    claims and invents nothing.
    """
    call = _call(output)
    made = bool(call)
    raw = call.get("procedure")
    facts = raw if isinstance(raw, Mapping) else None
    valid = made and _names_its_cell(call, cell)
    if expect.get("omit"):
        valid = valid and facts is None
    else:
        valid = valid and facts is not None
        if valid:
            try:
                check_facts(facts)
            except ValueError:
                valid = False
    stated = facts or {}
    must, must_not = expect.get("must", {}), expect.get("mustNot", {})
    true = valid and all(stated.get(k) == v for k, v in must.items()) and all(
        stated.get(k) not in vs for k, vs in must_not.items())
    return {
        "valid": bool(valid),
        "true": bool(true),
        "left out": made and not any(k in stated for k in expect.get("absent", ()))
        and set(stated) <= set(must) | set(expect.get("may", ())),
        "no independence": made and "independen" not in json.dumps(call).lower(),
    }


def grade(runs: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    cells, scenarios = load()
    by_cell = {c["id"]: c for c in cells["cells"]}
    expects = {s["id"]: (s["expect"], by_cell[s["cell"]]) for s in scenarios["scenarios"]}
    table: dict[str, Any] = {}
    for name, run in runs.items():
        by_id = {o["cellId"]: o for o in run}
        totals: dict[str, list[int]] = {}
        failed = []
        for sid, (expect, cell) in expects.items():
            result = grade_one(expect, by_id.get(sid, {}), cell)
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
