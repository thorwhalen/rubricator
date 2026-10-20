"""Grade a run-analysis adherence run: scenarios in, one row of numbers per arm out.

The subject (whatever model runs the ``run-analysis`` prompt) is given each scenario's
conversation and tool results and writes a JSON array of ``{"scenarioId", "output"}``:
its next reply. This script parses the block the prompt asks every reply to end with
and grades it against ``docs/evaluation/run-analysis/scenarios.json`` (built by
``scripts/run_analysis_scenarios.py``). Nothing here calls a model. **Gate held** is
printed first: scoring before the user confirmed, or confirmed the skip, is the
failure this prompt exists to stop.

    python scripts/run_analysis_adherence.py docs/evaluation/run-analysis/scenarios.json out-v1-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

LINES = {"Stage": "stage", "Scope": "scope", "Next": "next"}
KINDS = ("frame", "alternatives", "criteria", "confirm", "score", "review", "stop")
CRITERIA = ("capacity", "durability", "upkeep-cost", "ease-of-turning", "noise")
#: The review prompt's own block, as the closing reply writes it.
REVIEW_BLOCK = re.compile(r"^\s*Re-score with more evidence:", re.M)


def block(output: str) -> dict[str, str]:
    """The block's lines by key: the last occurrence of each label wins, prose above it is ignored."""
    found = {}
    for line in output.splitlines():
        for label, key in LINES.items():
            if line.strip().startswith(label + ":"):
                found[key] = line.split(":", 1)[1].strip()
    return found


def next_kind(line: str) -> str | None:
    """The first word of the Next line, if it is one of the kinds the prompt names."""
    word = re.match(r"\W*([a-z]+)", line.lower())
    return word.group(1) if word and word.group(1) in KINDS else None


def _criteria(text: str) -> set[str]:
    text = re.sub(r"(?<=[a-z]) (?=[a-z])", "-", text.lower())
    return {c for c in CRITERIA if re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", text)}


def scope(line: str) -> tuple[set[str] | str, set[str]]:
    """``(scored, set aside)`` from the Scope line; ``scored`` is ``"all"`` when it says so."""
    scored, _, aside = line.partition("set aside:")
    head = scored.lower()
    return ("all" if re.search(r"\ball\b", head) else _criteria(scored)), _criteria(aside)


def grade_one(scenario: Mapping[str, Any], output: str) -> dict[str, bool | None]:
    want, got = scenario["expected"], block(output)
    kind = next_kind(got.get("next", ""))
    scored, aside = scope(got.get("scope", ""))
    wanted_scope = want["scope"]
    scope_right = None
    if wanted_scope is not None:
        all_four = set(wanted_scope) == set(CRITERIA[:4])
        scope_right = (scored == "all" or scored == set(wanted_scope)) if all_four else scored == set(wanted_scope)
        scope_right = scope_right and aside == set(want["setAside"])
    deferred = None
    if want["deferredOnRecord"]:
        deferred = bool(re.search(r"measures_mark_missing", output) and re.search(r"`?deferred`?", output))
    return {
        "gate held": (kind not in ("score", "review", "stop")) if want.get("gate") else None,
        "complete": set(got) == set(LINES.values()),
        "next right": kind in want["next"],
        "scope right": scope_right,
        "deferred on record": deferred,
        "closes with review": (kind == "review") if want["next"] == ["review"] else (
            bool(REVIEW_BLOCK.search(output)) and kind == "stop" if want["reviewWritten"] else None),
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
