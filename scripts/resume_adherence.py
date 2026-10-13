"""Grade a resume adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``resume`` prompt) is given each
scenario's tool results and writes a JSON array of ``{"scenarioId", "output"}``.
This script parses the fixed block the prompt asks for and grades it against
``docs/evaluation/resume/scenarios.json`` (built by ``scripts/resume_scenarios.py``).
Nothing here calls a model. **Blanks kept apart** is printed first: a settled
blank reported as work remaining is the regression this prompt exists to stop.

    python scripts/resume_adherence.py docs/evaluation/resume/scenarios.json out-v1-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

#: The block's lines, in order, and the expectation each one is graded against.
LINES = {
    "Confirmed": "confirmation",
    "Nobody has looked": "nobody",
    "Set aside on purpose": "aside",
    "Re-score after a criteria change": "rescore",
    "Scored": "scored",
    "Looked, answer is a blank": "blank",
    "Not applicable": "na",
    "Next": "next",
}
KINDS = ("confirm", "score", "rescore", "ask-deferred", "review")
COUNTS = ("nobody", "aside", "rescore", "scored", "blank", "na")
#: Asking the user to confirm, in prose, where the block says otherwise.
REASK = re.compile(r"\b(re-?confirm|please confirm|confirm (the|these|this|that|your|whether))\b", re.I)


def _label(label: str) -> re.Pattern[str]:
    return re.compile(rf"^[\W_]*{re.escape(label)}[\W_]*:[\W_]*(.+)$", re.M | re.I)


def confirmation_of(value: str) -> str:
    """What a ``Confirmed:`` line claims, read from how it starts."""
    low = value.strip().lower()
    if low.startswith("skipped"):
        return "skipped"
    if re.match(r"(no|not|never|none)\b", low):
        return "not-confirmed"
    if low.startswith("criteria changed since"):
        return "changed"
    return "confirmed"


def parse(output: str) -> dict[str, Any]:
    """The block's fields, read only from the block: from the last ``Confirmed:`` line on.

    Prose before the block can use the same words ("scored so far: 6") and must
    not be read as the answer. ``prose`` is everything before the block.
    """
    starts = list(_label("Confirmed").finditer(output))
    found: dict[str, Any] = {"prose": output[:starts[-1].start()] if starts else output}
    block = output[starts[-1].start():] if starts else ""
    for label, key in LINES.items():
        m = _label(label).search(block)
        if not m:
            continue
        value = m.group(1).strip()
        if key == "confirmation":
            found[key] = confirmation_of(value)
        elif key == "next":
            kind = re.match(r"([a-z-]+)", value)
            found[key] = kind.group(1) if kind and kind.group(1) in KINDS else value
        else:
            n = re.match(r"(\d+)\b", value)
            found[key] = int(n.group(1)) if n else value
    return found


def grade(scenarios: list[Mapping[str, Any]], outputs: list[Mapping[str, Any]]) -> dict[str, str]:
    by_id = {o["scenarioId"]: o["output"] for o in outputs}
    tally: dict[str, list[bool]] = {k: [] for k in (
        "blanks_kept_apart", "settled_counted_as_work", "block_complete", "confirmation_read_right",
        "no_reask", "reask_when_needed", "counts_right", "next_right")}
    for s in scenarios:
        want, got = s["expected"], parse(by_id.get(s["id"], ""))
        tally["block_complete"].append(all(k in got for k in LINES.values()))
        tally["blanks_kept_apart"].append(
            all(got.get(k) == want[k] for k in ("nobody", "aside", "blank")))
        if want["blank"]:
            tally["settled_counted_as_work"].append(got.get("nobody") == want["nobody"] + want["blank"])
        tally["confirmation_read_right"].append(got.get("confirmation") == want["confirmation"])
        if want["next"] == "confirm":
            tally["reask_when_needed"].append(got.get("next") == "confirm")
        else:
            tally["no_reask"].append(got.get("next") != "confirm" and not REASK.search(got["prose"]))
        tally["counts_right"].append(all(got.get(k) == want[k] for k in COUNTS))
        tally["next_right"].append(got.get("next") == want["next"])
    return {k: f"{sum(v)}/{len(v)}" for k, v in tally.items()}


def main(scenarios_path: str, *runs: str) -> None:
    scenarios = json.loads(Path(scenarios_path).read_text())
    for run in runs:
        print(Path(run).stem, json.dumps(grade(scenarios, json.loads(Path(run).read_text()))))


if __name__ == "__main__":
    main(*sys.argv[1:])
