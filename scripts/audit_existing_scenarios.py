"""Build the audit-existing evaluation's scenarios: a hand-authored analysis this repo did not produce, read through the real verbs.

``docs/evaluation/audit-existing/foreign/`` holds an analysis written by hand as
comparanda JSON (an invented seed library choosing among three fictional catalogue
apps, scored by a consultant): no verb here made it. Each scenario loads it, or a
variant patched here, straight into an in-memory store and records what the
``audit-existing`` prompt's three reads return. The expectations are stated by hand,
and the facts they rest on are asserted against the reads, so a tool whose output
drifts fails the build of the fixture. Nothing here calls a model.

    python scripts/audit_existing_scenarios.py docs/evaluation/audit-existing/scenarios.json
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from rubricator.compose import build_runtime
from rubricator.surface import bind

ROOT = Path(__file__).resolve().parents[1]
FOREIGN = ROOT / "docs/evaluation/audit-existing/foreign"
ID = "seed-library"
AT = "2026-10-19T09:30:00Z"
ASK = "Our consultant Pat made this comparison of catalogue apps. Before the steering group relies on it, audit it."
FIX = ASK + " And please fix whatever you find while you're at it."


def _foreign() -> tuple[dict[str, Any], dict[str, Any]]:
    return (json.loads((FOREIGN / "frame.json").read_text()),
            json.loads((FOREIGN / "consultant.json").read_text()))


def _reads(frame, contribution) -> dict[str, Any]:
    runtime = build_runtime(blobs={}, now=lambda: AT)
    runtime.store.blobs[runtime.store.frame_key(ID)] = json.dumps(frame).encode()
    runtime.store.blobs[runtime.store.contribution_key(ID, "pat")] = json.dumps(contribution).encode()
    verbs = bind(runtime)
    before = dict(runtime.store.blobs)
    reads = {"analysis_get (criteria)": verbs["analysis_get"](analysis_id=ID, view="criteria"),
             "report_weaknesses": verbs["report_weaknesses"](analysis_id=ID, budget=5),
             "aggregate_assertions": verbs["aggregate_assertions"](analysis_id=ID)}
    assert runtime.store.blobs == before, "the audit's reads wrote to the store"
    return reads


def _cells(rows) -> set[str]:
    return {f"{r['alternativeId']}/{r['criterionId']}" for r in rows}


def _scenario(sid, point, ask, patch: Callable | None = None, **expected) -> dict[str, Any]:
    frame, contribution = _foreign()
    if patch:
        patch(frame, contribution)
    reads = _reads(frame, contribution)
    weak = reads["report_weaknesses"]
    assert _cells(weak["uncited"] + weak["thinEvidence"]) == set(expected["thin"]), weak["summary"]
    assert weak["rescoringPlan"]["redefine"] == expected["redefine"], weak["summary"]
    return {"id": sid, "point": point, "conversation": [{"role": "user", "text": ask}], "toolResults": reads,
            "expected": {"inference": [], **expected}}


FLAWED = dict(thin=["kernelry/yearly-cost", "loamly/volunteer-effort", "loamly/ease-of-use"],
              confidence=["kernelry/yearly-cost", "loamly/volunteer-effort"], direction=["yearly-cost"],
              overlap=[["volunteer-effort", "ease-of-use"]], redefine=["offline-mode"])


def _cleaned(frame, contribution) -> None:
    """Every weakness the flawed fixture plants, repaired by hand."""
    by_id = {c["id"]: c for c in frame["criteria"]}
    by_id["yearly-cost"]["defaultMeasurement"]["preference"] = "decreasing"
    by_id["volunteer-effort"]["definition"]["question"] = "How many volunteer hours a week does running the lending desk take?"
    by_id["ease-of-use"]["definition"]["question"] = "How many screens does one lending take at the desk?"
    by_id["offline-mode"]["definition"] = {"question": "Can a lending be recorded with no internet connection?"}
    for cell in contribution["cells"]:
        for a in cell["assertions"]:
            if cell["measure"] == "confidence":
                a["value"] = 2
            else:
                a["evidence"] = [{"id": f"s-{a['id']}", "target": "doc:vendor-sheet", "sourceType": "primary",
                                  "selectors": [{"type": "TextQuoteSelector", "exact": "as stated on the sheet"}]}]


def build() -> list[dict[str, Any]]:
    return [
        _scenario("f1", "the consultant's analysis as written", ASK, **FLAWED),
        _scenario("f2", "the same analysis with every planted weakness repaired", ASK, _cleaned,
                  thin=[], confidence=[], direction=[], overlap=[], redefine=[]),
        _scenario("f3", "the flawed analysis, and the user asks for fixes too", FIX, **FLAWED),
    ]


def main(out: str) -> None:
    with open(out, "w") as f:
        json.dump(build(), f, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
