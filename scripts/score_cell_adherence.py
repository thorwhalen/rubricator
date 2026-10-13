"""Score a score-cell adherence run: constructed cells in, one table of numbers out.

The subject (whatever model runs the prompt) writes a JSON array of
``{"cellId", "output"}`` per arm; this script grades those outputs against the
expectations in ``docs/evaluation/score-cell/cells.json``. Nothing here calls a
model. Refusal to guess is printed first, because it is the number that decides
whether a prompt change is a regression (``rubricator-dev-prompt-change``).

Schema validity means the emitted ``cell`` is written by ``measures_write`` as it
stands -- no key dropped, renamed or added.

    python scripts/score_cell_adherence.py docs/evaluation/score-cell/cells.json out-v2.json [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind

MOMENT = "2026-10-13T12:00:00Z"
AUTHOR = {"id": "scorer", "displayName": "Scorer", "kind": "agent", "agent": {"name": "eval"}}


def _cell_of(output: Mapping[str, Any]) -> Mapping[str, Any]:
    """v2 emits ``{"cell": ...}``; v1 named fields with no shape, so the object is the cell."""
    return output.get("cell", output)


def _code(output: Mapping[str, Any]) -> str | None:
    cell = _cell_of(output)
    missing = cell.get("missing")
    return missing.get("code") if isinstance(missing, Mapping) else cell.get("code")


def _writes(cells: Mapping[str, Any], case: Mapping[str, Any], output: Mapping[str, Any]) -> bool:
    """The cell is written as it stands, and it is the cell that was asked for."""
    cell = _cell_of(output)
    if (cell.get("alternativeId"), cell.get("criterionId")) != (case["alternative"], case["criterion"]):
        return False
    verbs = bind(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    verbs["analysis_open"](analysis_id="a", question="q", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a", ambiguities=[])
    alternatives = sorted({c["alternative"] for c in cells["cells"]})
    verbs["alternatives_set"](analysis_id="a", alternatives=[{"id": a, "label": a} for a in alternatives])
    verbs["criteria_set"](analysis_id="a", criteria=[
        {"id": k, "label": k, "anchors": [{"level": lv, "text": t} for lv, t in v["anchors"].items()]}
        for k, v in cells["criteria"].items()])
    try:
        verbs["measures_write"](analysis_id="a", contributor_id="scorer", author=AUTHOR, at=MOMENT,
                                cells=[cell])
        return True
    except (KeyError, ValueError, TypeError):
        return False


def grade(cells: Mapping[str, Any], outputs: list[Mapping[str, Any]]) -> dict[str, Any]:
    """One row of numbers for one arm."""
    by_id = {o["cellId"]: o["output"] for o in outputs}
    cases = cells["cells"]

    def rate(selected, ok):
        hits = [ok(c, by_id[c["id"]]) for c in selected if c["id"] in by_id]
        return f"{sum(hits)}/{len(hits)}"

    absent = [c for c in cases if c.get("absent")]
    scored = [c for c in cases if "value" in c["expected"]]
    return {
        "refusal_to_guess": rate(absent, lambda c, o: _code(o) is not None),
        "right_blank": rate(absent, lambda c, o: _code(o) == c["expected"]["code"]),
        "right_level": rate(scored, lambda c, o: str(_cell_of(o).get("value")) == str(c["expected"]["value"])),
        "writes_no_repair": rate(cases, lambda c, o: _writes(cells, c, o)),
        "dependsOn_present": rate(cases, lambda c, o: isinstance(o.get("dependsOn"), list)),
        "dependsOn_right": rate(cases, lambda c, o: isinstance(o.get("dependsOn"), list)
                                and sorted(o["dependsOn"]) == sorted(c["expected"]["dependsOn"])),
        "dependence_caught": rate([c for c in cases if c.get("dependence")],
                                  lambda c, o: sorted(o.get("dependsOn") or []) == sorted(c["expected"]["dependsOn"])),
        "right_confidence": rate([c for c in cases if "confidence" in c["expected"]],
                                 lambda c, o: o.get("confidence", _cell_of(o).get("confidence")) == c["expected"]["confidence"]),
        "downgrade_counted": rate([c for c in cases if "downgrade" in c["expected"]],
                                  lambda c, o: bool(re.match(r"downgraded \([a-z-]+\): ", _cell_of(o).get("justification", "")))),
        "confidence_on_scores_only": rate(cases, lambda c, o: ("confidence" in o or "confidence" in _cell_of(o)) == (_code(o) is None)),
        "plan_emitted": rate(cases, lambda c, o: "plan" in o or "plan" in _cell_of(o)),
    }


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    for path in sys.argv[2:]:
        print(Path(path).stem, json.dumps(grade(spec, json.loads(Path(path).read_text()))))
