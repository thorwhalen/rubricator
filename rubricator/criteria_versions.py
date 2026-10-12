"""Criteria-set versions: ordering, the next version, and what a revision supersedes.

ADR-0016: a criterion may change meaning after cells were scored against it, and
the document has to say so, or a matrix's columns end up scored against
different rubrics with nothing in the output showing it. The companion
repository settled the fields (thorwhalen/comparanda#62, #159):

- ``criteriaVersion`` on the analysis: moves forward whenever any criterion's
  meaning changes, so the document records that the frame changed;
- ``definedInVersion`` on a criterion: moves to the new version only when the
  change was **material**, i.e. when earlier scores no longer answer the
  question as it is now asked;
- ``criteriaVersion`` on each assertion: the version it was scored against.

An assertion is **superseded** when its ``criteriaVersion`` is strictly earlier
than its criterion's ``definedInVersion``. Every reading here mirrors the
companion's -- an absent set version reads as ``"1"``, versions are dotted
integers compared segment by segment -- because two producers disagreeing about
which scores are current is the failure the fields exist to prevent.

>>> compare_versions("10", "9"), compare_versions("1.0", "1"), compare_versions("a", "b")
(1, 0, None)
>>> next_version(None), next_version("2"), next_version("v1.4")
('2', '3', 'v1.5')
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

__all__ = [
    "MEANING_FIELDS",
    "compare_versions",
    "effective_version",
    "next_version",
    "meaning_changed",
    "superseded_cells",
]

#: The criterion fields whose change is a change of meaning (the companion's
#: list). A change to any of them moves ``criteriaVersion`` forward.
MEANING_FIELDS: tuple[str, ...] = (
    "label", "definition", "measurements", "defaultMeasurement", "acceptability", "missingCodes",
)

# ASCII digits and a full match: `$` alone admits a trailing newline and `\d`
# admits non-ASCII digits, both of which the companion's parser refuses.
_DOTTED = re.compile(r"[vV]?\d+(\.\d+)*", re.ASCII)
_BUMPABLE = re.compile(r"([vV]?)((?:\d+\.)*)(\d+)", re.ASCII)


def compare_versions(a: str, b: str) -> int | None:
    """-1, 0 or 1 as ``a`` orders before, with or after ``b``; ``None`` if unorderable.

    Exact at any size: segments compare by length after dropping leading zeros,
    then lexically, as the companion's ``compareCriteriaVersions`` does.
    """

    def parse(v: str) -> list[str] | None:
        if not _DOTTED.fullmatch(v):
            return None
        return [seg.lstrip("0") or "0" for seg in v.lstrip("vV").split(".")]

    x, y = parse(a), parse(b)
    if x is None or y is None:
        return 0 if a == b else None
    for i in range(max(len(x), len(y))):
        p = x[i] if i < len(x) else "0"
        q = y[i] if i < len(y) else "0"
        if len(p) != len(q):
            return -1 if len(p) < len(q) else 1
        if p != q:
            return -1 if p < q else 1
    return 0


def effective_version(v: str | None) -> str:
    """The version a set is at, reading an absent one as ``"1"``."""
    return "1" if v is None else v


def next_version(current: str | None) -> str:
    """The version after ``current``. Raises on a version that is not dotted integers."""
    if current is None:
        return "2"
    m = _BUMPABLE.fullmatch(current)
    if not m:
        raise ValueError(
            f'cannot increment the criteria-set version "{current}": it is not a dotted-integer '
            "version."
        )
    return f"{m[1]}{m[2]}{int(m[3]) + 1}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def meaning_changed(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """The meaning fields that differ between two versions of one criterion.

    Only the fields the companion parses with a default (``missingCodes`` to
    ``[]``, ``measurements`` to ``{}``) treat absent and empty as equal. For the
    rest, adding an empty ``definition`` is a change, as it is there.
    """
    defaults = {"missingCodes": [], "measurements": {}}

    def norm(c: Mapping[str, Any], f: str) -> str:
        v = c.get(f)
        return _canonical(defaults.get(f) if v is None and f in defaults else v)

    return [f for f in MEANING_FIELDS if norm(before, f) != norm(after, f)]


def superseded_cells(document: Mapping[str, Any]) -> dict[str, Any]:
    """Which cells hold live assertions scored against an older definition.

    Mirrors the companion's ``supersededCells``: ``cells`` are strictly older,
    ``undetermined`` cannot be ordered, ``unversioned`` counts live assertions
    on a versioned criterion that record no version. A criterion without a
    ``definedInVersion`` has never recorded a change of meaning and supersedes
    nothing; tombstoned rows and columns are skipped.
    """
    live_alts = {a["id"] for a in document.get("alternatives", []) if not a.get("tombstoned")}
    defined_in = {
        c["id"]: c["definedInVersion"]
        for c in document.get("criteria", [])
        if not c.get("tombstoned") and c.get("definedInVersion") is not None
    }
    cells: list[dict[str, Any]] = []
    undetermined: list[dict[str, Any]] = []
    unversioned = 0
    for cell in document.get("cells", []):
        current = defined_in.get(cell["criterionId"])
        if current is None or cell["alternativeId"] not in live_alts:
            continue
        older, unknown = [], []
        for s in _live(cell["assertions"]):
            version = s.get("criteriaVersion")
            if version is None:
                unversioned += 1
                continue
            order = compare_versions(version, current)
            if order == -1:
                older.append({"id": s["id"], "criteriaVersion": version})
            elif order is None:
                unknown.append({"id": s["id"], "criteriaVersion": version})
        base = {
            "alternativeId": cell["alternativeId"],
            "criterionId": cell["criterionId"],
            "measure": cell.get("measure", "score"),
            "definedInVersion": current,
        }
        if older:
            cells.append({**base, "assertions": older})
        if unknown:
            undetermined.append({**base, "assertions": unknown})
    return {"count": len(cells), "cells": cells, "undetermined": undetermined,
            "unversioned": unversioned}


def _live(assertions: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [a for a in assertions if not a.get("supersededBy")]
