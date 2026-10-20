"""Build the review evaluation's scenarios from the real verbs: ``report_weaknesses`` output in, expectations beside it.

Each scenario drives a fresh in-memory analysis (an invented domain: three bicycle
docks a small town is choosing between) to a scored state, then records what the
``review`` prompt's one read returns. The expectations are read off that result and
the scenario's point is asserted by hand here, so a tool whose output drifts fails
the build of the fixture rather than silently changing what a subject is graded
against. Nothing here calls a model.

    python scripts/review_scenarios.py docs/evaluation/review/scenarios.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rubricator.compose import build_runtime
from rubricator.surface import bind

AT = "2026-10-12T09:30:00Z"
ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
BOT = {"id": "bot", "displayName": "Bot", "kind": "agent", "agent": {"name": "rubricator", "model": "model-a"}}
BOT2 = {"id": "bot2", "displayName": "Bot 2", "kind": "agent", "agent": {"name": "rubricator", "model": "model-b"}}
DOCKS = [("larkspur", "Larkspur"), ("quillon", "Quillon"), ("tessera", "Tessera")]
ANCHORS = [{"level": "1", "text": "no stated figure"}, {"level": "3", "text": "a figure with caveats"},
           {"level": "5", "text": "a tested, published figure"}]
CRITERIA = ["theft-resistance", "upkeep-cost", "weather-sealing"]
SPAN = {"id": "e1", "target": "doc:spec-sheet", "sourceType": "primary", "stance": "supports",
        "selectors": [{"type": "TextQuoteSelector", "exact": "rated for 40,000 cycles"}],
        "excerpt": "rated for 40,000 cycles"}
#: Quoted, so a write accepts it, but with no selector: nothing a reader can locate and check.
THIN = {"id": "e2", "target": "doc:forum-post", "sourceType": "secondary", "stance": "supports",
        "excerpt": "seems pretty sturdy"}
FLOOR = {"threshold": 3, "rationale": "below 3 the insurer will not cover the docks"}


def _analysis(*, confidence=False, floor=False):
    verbs = bind(build_runtime(blobs={}, now=lambda: AT))
    verbs["analysis_open"](analysis_id="docks", question="which bicycle dock should the town install?",
                           allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="docks", ambiguities=[])
    verbs["alternatives_set"](analysis_id="docks", alternatives=[{"id": i, "label": label} for i, label in DOCKS])
    criteria = [{"id": c, "label": c.replace("-", " "), "anchors": ANCHORS,
                 "definition": {"question": f"how good is the dock's {c.replace('-', ' ')}?"}}
                for c in CRITERIA]
    if floor:
        criteria[0]["acceptability"] = FLOOR
    verbs["criteria_set"](analysis_id="docks", criteria=criteria,
                          **({"confidence_scale": "confidence-1-3"} if confidence else {}))
    return verbs


def _write(verbs, scores, *, author=BOT, evidence=(SPAN,), measure="score", independence=None):
    verbs["measures_write"](analysis_id="docks", contributor_id=author["id"], author=author, cells=[
        {"alternativeId": a, "criterionId": c, "measure": measure, "value": v,
         "justification": "the spec sheet states it", "evidence": list(evidence),
         **({"independence": independence} if independence else {})}
        for (a, c), v in scores.items()])


def _grid(rows: dict[str, tuple[int, int, int]]) -> dict[tuple[str, str], int]:
    return {(a, c): v for a, vals in rows.items() for c, v in zip(CRITERIA, vals)}


def _read(verbs) -> dict[str, Any]:
    return verbs["report_weaknesses"](analysis_id="docks", budget=5)


def pivotal_thin():
    """Two docks incomparable, one cell each away from a dominance; one of them cited with nothing to check."""
    verbs = _analysis()
    grid = _grid({"larkspur": (4, 3, 3), "quillon": (3, 3, 4), "tessera": (2, 2, 2)})
    _write(verbs, {k: v for k, v in grid.items() if k != ("larkspur", "theft-resistance")})
    _write(verbs, {("larkspur", "theft-resistance"): 4}, evidence=(THIN,))
    out = _read(verbs)
    assert out["rescoringPlan"]["rescore"][0]["reason"].startswith("pivotal"), out["summary"]
    assert not out["rescoringPlan"]["redefine"]
    return out


def redefine_pivotal():
    """A criterion two scorers apply in opposite ways; the one pivotal cell is on it, so nothing is re-scored."""
    verbs = _analysis()
    _write(verbs, _grid({"larkspur": (4, 3, 1), "quillon": (3, 4, 1), "tessera": (5, 5, 5)}))
    _write(verbs, {("larkspur", "weather-sealing"): 5, ("quillon", "weather-sealing"): 5},
           author=BOT2, independence="independent")
    out = _read(verbs)
    assert out["rescoringPlan"]["redefine"] == ["weather-sealing"], out["summary"]
    assert not out["rescoringPlan"]["rescore"] and "1 pivotal cell(s)" in out["summary"], out["summary"]
    return out


def no_pivot_high_correlation():
    """One dock beats the others by two levels everywhere: no cell is pivotal, and the columns move together."""
    verbs = _analysis()
    _write(verbs, _grid({"larkspur": (5, 5, 5), "quillon": (3, 3, 3), "tessera": (1, 1, 1)}))
    out = _read(verbs)
    assert not any(r["reason"].startswith("pivotal") for r in out["rescoringPlan"]["rescore"])
    assert out["traversalLeakageDiagnostic"] and out["traversalLeakageDiagnostic"][0]["correlation"] == 1.0
    return out


def floors_and_confidence():
    """A dock under the floor, one whose floor was never tested, and two cells scored with low confidence."""
    verbs = _analysis(confidence=True, floor=True)
    grid = _grid({"larkspur": (4, 3, 3), "quillon": (2, 4, 4), "tessera": (5, 2, 2)})
    _write(verbs, {k: v for k, v in grid.items() if k != ("tessera", "theft-resistance")})
    _write(verbs, {("larkspur", "upkeep-cost"): 1, ("quillon", "weather-sealing"): 1,
                   ("tessera", "upkeep-cost"): 3}, measure="confidence")
    out = _read(verbs)
    assert {(v["alternativeId"], v["criterionId"]) for v in out["vetoFlags"]} == {
        ("quillon", "theft-resistance"), ("tessera", "theft-resistance")}, out["vetoFlags"]
    assert len(out["lowConfidence"]) == 2
    return out


def nothing_weak():
    """Every cell cited by a span, one dock dominant, no repeats: the honest review is short."""
    verbs = _analysis()
    _write(verbs, _grid({"larkspur": (5, 4, 5), "quillon": (3, 2, 3), "tessera": (1, 2, 1)}))
    out = _read(verbs)
    assert not out["rescoringPlan"]["rescore"] and not out["rescoringPlan"]["redefine"], out["summary"]
    return out


SCENARIOS = {"r1": pivotal_thin, "r2": redefine_pivotal, "r3": no_pivot_high_correlation,
             "r4": floors_and_confidence, "r5": nothing_weak}


def expected(result: dict[str, Any]) -> dict[str, Any]:
    """What a faithful block holds, read off the tool's own result."""
    plan = result["rescoringPlan"]
    weak = {f"{r['alternativeId']}/{r['criterionId']}"
            for name in ("uncited", "thinEvidence", "agentInferenceOnly", "staleCitations", "lowConfidence")
            for r in result[name]}
    pivotal = [f"{r['alternativeId']}/{r['criterionId']}" for r in plan["rescore"] if r["reason"].startswith("pivotal")]
    return {
        "rescore": [f"{r['alternativeId']}/{r['criterionId']}" for r in plan["rescore"]],
        "redefine": list(plan["redefine"]),
        "pivotal": pivotal,
        # The tool leaves a redefine criterion's cells out of the plan, pivotal or not; the summary
        # still counts them, so a pivotal count with none in the plan points at a criterion to redefine.
        # Among pivotal cells, the thinly evidenced ones first: that is the prompt's rule.
        "mostLikely": [c for c in pivotal if c in weak] or pivotal
                      or (list(plan["redefine"]) if pivotal_count(result) else []),
        "vetoes": [f"{v['alternativeId']}/{v['criterionId']}" for v in result["vetoFlags"]],
        "correlations": len(result["traversalLeakageDiagnostic"]),
    }


def pivotal_count(result: dict[str, Any]) -> int:
    """The summary's pivotal count: the only place a pivotal cell on a criterion to redefine shows."""
    import re

    found = re.search(r"(\d+) pivotal cell", result["summary"])
    return int(found.group(1)) if found else 0


def main(out: str) -> None:
    scenarios = []
    for sid, build in SCENARIOS.items():
        result = build()
        scenarios.append({"id": sid, "toolResults": {"report_weaknesses": result}, "expected": expected(result)})
    with open(out, "w") as f:
        json.dump(scenarios, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
