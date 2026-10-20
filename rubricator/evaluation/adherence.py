"""Instruction adherence (ADR-0008, #94): did the analysis do what it was told about the frame?

Two instructions a user gives are first-class (ADR-0008, ``measures_mark_missing``): *fill these
criteria and leave the rest deferred*, and *use exactly these criteria*. A fixture states which
one it is in its ``fixture.json``::

    {"instruction": {"fill": ["pain", "market"], "defer": ["team"]}}     # partial fill
    {"instruction": {"criteria": ["pain", "market"]}}                      # fixed criteria

``fill`` and ``defer`` together name the criteria the user gave, so a partial fill also fixes the
criteria. Two metrics, each one number per analysis and ``None`` where the fixture gives no such
instruction:

- :data:`DEFERRAL_ADHERENCE` -- the share of the named cells that comply: a ``fill`` cell holds a
  live assertion that is a value or a *terminal* qualified blank (somebody looked); a ``defer`` cell
  holds a live assertion coded exactly ``deferred`` -- not ``not-assessed`` (nobody was asked to
  look and nobody looked), and not a value.
- :data:`INVENTED_CRITERIA` -- how many live criteria the analysis carries that the user did not
  give. Zero is the only good value; it is a count, not a share, so one invention is visible.

Both are deterministic and need no model: they read the produced analysis.
"""

from __future__ import annotations

from typing import Any, Mapping

from rubricator.evaluation.harness import Fixture, Metric

__all__ = ["DEFERRAL_ADHERENCE", "INVENTED_CRITERIA", "ADHERENCE_SUITE"]

#: The one code a deferred cell carries. Named here, not matched ad hoc: the 2026-08-21
#: vocabulary amendment renamed ``pending`` to this, and a metric must follow the vocabulary.
DEFERRED = "deferred"

#: Codes that say nobody looked; a ``fill`` cell holding one was not filled.
_PLACEHOLDERS = frozenset({DEFERRED, "not-assessed"})


def _instruction(fixture: Fixture) -> Mapping[str, Any]:
    found = fixture.meta.get("instruction")
    return found if isinstance(found, Mapping) else {}


def _live_assertion(cell: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The latest assertion of a cell, or ``None`` for a cell nobody wrote."""
    assertions = cell.get("assertions") or []
    return max(assertions, key=lambda a: a.get("version", 0)) if assertions else None


def _complies(assertion: Mapping[str, Any] | None, *, deferred: bool) -> bool:
    if assertion is None:
        return False
    code = (assertion.get("missing") or {}).get("code")
    if deferred:
        return code == DEFERRED and "value" not in assertion
    return "value" in assertion or (code is not None and code not in _PLACEHOLDERS)


def _deferral_adherence(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
    instruction = _instruction(fixture)
    fill, defer = set(instruction.get("fill") or ()), set(instruction.get("defer") or ())
    if not (fill or defer):
        return None
    alternatives = {a["id"] for a in produced.get("alternatives", ()) if not a.get("tombstoned")}
    cells = {(c["alternativeId"], c["criterionId"]): c for c in produced.get("cells", ())}
    owed = [(alt, crit, crit in defer) for alt in sorted(alternatives) for crit in sorted(fill | defer)]
    if not owed:
        return None
    met = sum(
        _complies(_live_assertion(cells.get((alt, crit), {})), deferred=deferred)
        for alt, crit, deferred in owed
    )
    return met / len(owed)


def _invented_criteria(fixture: Fixture, produced: Mapping[str, Any]) -> float | None:
    instruction = _instruction(fixture)
    given = set(instruction.get("criteria") or ()) | set(instruction.get("fill") or ()) | set(
        instruction.get("defer") or ()
    )
    if not given:
        return None
    live = {c["id"] for c in produced.get("criteria", ()) if not c.get("tombstoned")}
    return float(len(live - given))


DEFERRAL_ADHERENCE = Metric(
    "deferral_adherence", version=1, tier="nightly", measure=_deferral_adherence,
    description="Share of named cells that comply: asked-for criteria filled, the rest coded deferred.",
)
INVENTED_CRITERIA = Metric(
    "invented_criteria", version=1, tier="nightly", measure=_invented_criteria,
    description="Live criteria the user did not give. Zero is the only good value.",
)

ADHERENCE_SUITE = (DEFERRAL_ADHERENCE, INVENTED_CRITERIA)
