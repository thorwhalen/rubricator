"""Shared code of the ``scripts/*_adherence.py`` graders (#295).

Every adherence grader turns a run (a JSON list of ``{"scenarioId", ...}`` outputs) into
``{metric: (hits, applicable)}`` and prints it. What differs between them is only the per-scenario
check (``grade_one``) and the table's columns, so the rest lives here: :func:`tally` (the totals
loop), :func:`arm_lines` and :func:`table` (the two ``main`` shapes), :func:`line` (read a
``Label: value`` line out of a reply) and :func:`all_or_none` (a metric over nothing is
not-applicable, never a vacuous pass).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

GradeOne = Callable[[Mapping[str, Any], Any], Mapping[str, bool | None]]
Grade = Callable[[list[Mapping[str, Any]], list[Mapping[str, Any]]], Mapping[str, tuple[int, int]]]


def line(reply: str, label: str) -> str | None:
    """The value of the first ``Label: value`` line in ``reply`` (case-insensitive), else ``None``."""
    match = re.search(rf"^\W*{re.escape(label)}\W*:\s*(.+)$", reply, re.M | re.I)
    return match.group(1) if match else None


def all_or_none(checks: Sequence[bool]) -> bool | None:
    """``all(checks)``, or ``None`` (not applicable) when there is nothing to check."""
    return all(checks) if checks else None


def tally(
    scenarios: Iterable[Mapping[str, Any]],
    outputs: Iterable[Mapping[str, Any]],
    grade_one: GradeOne,
    *,
    unwrap: Callable[[Mapping[str, Any]], Any] = lambda o: o["output"],
    missing: Any = "",
    metrics: Sequence[str] | None = None,
    answered_only: bool = False,
) -> dict[str, tuple[int, int]]:
    """``{metric: (hits, applicable)}`` over the scenarios, from ``grade_one(scenario, output)``.

    A check that returns ``None`` is not applicable and is not counted. ``unwrap`` takes one entry of
    ``outputs`` to what ``grade_one`` reads (default: its ``"output"``); a scenario with no entry is
    graded on ``missing``, or skipped when ``answered_only``. ``metrics`` fixes the keys (and their
    order) up front, so a metric with nothing applicable still appears as ``(0, 0)``.
    """
    by_id = {o.get("scenarioId"): unwrap(o) for o in outputs}
    totals: dict[str, list[int]] = {m: [0, 0] for m in metrics or ()}
    for scenario in scenarios:
        if answered_only and scenario["id"] not in by_id:
            continue
        for metric, ok in grade_one(scenario, by_id.get(scenario["id"], missing)).items():
            if ok is None:
                continue
            hits_n = totals.setdefault(metric, [0, 0])
            hits_n[0] += bool(ok)
            hits_n[1] += 1
    return {k: (v[0], v[1]) for k, v in totals.items()}


def _runs(scenarios_path: str, runs: Iterable[str], grade: Grade):
    scenarios = json.loads(Path(scenarios_path).read_text())
    for run in runs:
        yield Path(run), grade(scenarios, json.loads(Path(run).read_text()))


def arm_lines(grade: Grade, scenarios_path: str, *runs: str) -> None:
    """Print one ``<run file> metric a/n | metric a/n`` line per run."""
    for path, row in _runs(scenarios_path, runs, grade):
        print(path.name, " | ".join(f"{k} {a}/{n}" for k, (a, n) in row.items()))


def table(
    grade: Grade,
    columns: Sequence[str],
    scenarios_path: str,
    *runs: str,
    header: Callable[[str], str] = lambda m: m,
    absent: str = "n/a",
    skip_empty: bool = True,
) -> None:
    """Print a markdown table, one row per run and one column per metric in ``columns``.

    A metric with nothing applicable prints ``absent`` (``skip_empty``), and one the run did not
    produce at all prints ``absent`` too.
    """
    print("| arm | " + " | ".join(header(m) for m in columns) + " |")
    print("|---" * (len(columns) + 1) + "|")
    for path, row in _runs(scenarios_path, runs, grade):
        cells = " | ".join(
            f"{row[m][0]}/{row[m][1]}" if m in row and (row[m][1] or not skip_empty) else absent
            for m in columns
        )
        print(f"| {path.stem} | {cells} |")
