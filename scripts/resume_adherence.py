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
    "Looked, answer is a blank": "blank",
    "Scored": "scored",
    "Re-score after a criteria change": "rescore",
    "Next": "next",
}
KINDS = ("confirm", "score", "rescore", "ask-deferred", "review")


def parse(output: str) -> dict[str, Any]:
    """The block's fields, or what is missing from it."""
    found: dict[str, Any] = {}
    for label, key in LINES.items():
        m = re.search(rf"^\W*{re.escape(label)}\W*:?\s*(.+)$", output, re.M | re.I)
        if not m:
            continue
        value = m.group(1).strip()
        if key == "confirmation":
            low = value.lower()
            found[key] = ("not-confirmed" if re.match(r"(no|not)\b", low)
                          else "changed" if "changed since" in low else "confirmed")
            found["confirmedBy"] = value
        elif key == "next":
            kind = re.match(r"`?([a-z-]+)`?", value)
            found[key] = kind.group(1) if kind and kind.group(1) in KINDS else value
        else:
            n = re.match(r"\D*?(\d+)", value)
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
        if want["confirmation"] == "confirmed":
            tally["no_reask"].append(got.get("next") != "confirm")
        else:
            tally["reask_when_needed"].append(got.get("next") == "confirm")
        tally["counts_right"].append(
            all(got.get(k) == want[k] for k in ("nobody", "aside", "blank", "scored", "rescore")))
        tally["next_right"].append(got.get("next") == want["next"])
    return {k: f"{sum(v)}/{len(v)}" for k, v in tally.items()}


def main(scenarios_path: str, *runs: str) -> None:
    scenarios = json.loads(Path(scenarios_path).read_text())
    for run in runs:
        print(Path(run).stem, json.dumps(grade(scenarios, json.loads(Path(run).read_text()))))


if __name__ == "__main__":
    main(*sys.argv[1:])
