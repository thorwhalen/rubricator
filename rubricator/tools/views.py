"""Reading an analysis back: ``analysis_get``, and the stage an analysis has reached.

**Every view is a pure projection of stored state** (ADR-0017). Nothing here
writes, and nothing here decides: the stage is the earliest ADR-0005 stage
whose work is not on record, and the outstanding cells are the ones no live
assertion settles. Both are facts about the document, computed the same way
every time, so a resuming session reads where the work stands instead of
re-deriving it from a transcript.

The ``outstanding`` view is the resume affordance. It keeps apart the two
reasons a cell is open, because they lead to different next actions:
``not-assessed`` (nobody has looked -- including a cell nobody has written at
all, which is the companion's default for a new cell, reported with
``recorded: false``) and ``deferred`` (somebody chose to leave it).

The ``full`` view returns a resource link and never the document body. A
matrix with its evidence runs to tens of thousands of tokens; the host fetches
it when a person wants it, and the model asks for the projection it needs.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from rubricator.clock import instant
from rubricator.rules import live_assertions
from rubricator.schema.vocabulary import vocabulary
from rubricator.store import AnalysisNotFound, AnalysisStore

__all__ = [
    "analysis_get", "VIEWS", "STAGES", "stage_of", "outstanding_cells", "analysis_uri", "conform",
]

#: The views ``analysis_get`` serves. The frozen row's enum is the contract;
#: this tuple is what the verb dispatches on, and a test holds the two equal.
VIEWS: tuple[str, ...] = ("summary", "frame", "criteria", "outstanding", "full")

#: ADR-0005's six stages, by number, with what moves each one forward. A row
#: rather than a branch per stage, so the summary text and the number cannot
#: disagree.
STAGES: Mapping[int, tuple[str, str]] = {
    1: ("frame", "record the decision and its ambiguities with frame_set"),
    2: ("enumerate", "declare the alternatives with alternatives_set"),
    3: ("propose-criteria", "declare the criteria with criteria_set"),
    4: ("confirm", "put the frame and criteria to the user with frame_confirm"),
    5: ("populate", "score or mark the outstanding cells (analysis_get view=outstanding), and "
        "re-score any cell answering an older criteria definition"),
    6: ("review", "every cell is settled; review the weakest scores"),
}

#: The resource the ``full`` view links to. Served by the connector; a surface
#: without resources still gets a stable name for the document.
_URI = "rubricator://analysis/{analysis_id}"

def analysis_uri(analysis_id: str) -> str:
    """The resource name of one analysis document."""
    return _URI.format(analysis_id=analysis_id)


def _live(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in rows if not r.get("tombstoned")]


def outstanding_cells(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The cells of the live matrix that no live assertion settles, in frame order.

    A cell is **settled** when a live assertion carries a value, or a blank
    whose code is terminal or structural. It is outstanding otherwise, and its
    ``code`` is the latest open blank's (by instant, then id; an unreadable
    moment sorts first), or
    ``not-assessed`` with ``recorded: false`` when nothing was ever written. A
    code this build cannot resolve counts as outstanding: over-reporting work
    remaining is the safe direction, as in ``report_completeness``.
    """
    from rubricator.tools.analysis import declarations_for

    vocab = vocabulary()
    by_key = {
        (c["alternativeId"], c["criterionId"], c.get("measure", "score")): c
        for c in document.get("cells", [])
    }
    measures = [m["name"] for m in document.get("measures", [])] or ["score"]
    out: list[dict[str, Any]] = []
    for alt in _live(document.get("alternatives", [])):
        for crit in _live(document.get("criteria", [])):
            declarations = declarations_for(document, crit["id"])
            for measure in measures:
                cell = by_key.get((alt["id"], crit["id"], measure))
                live = live_assertions(cell) if cell else []
                open_codes: list[tuple[Any, str, str]] = []
                settled = False
                for a in live:
                    if "value" in a:
                        settled = True
                        break
                    code = (a.get("missing") or {}).get("code", "")
                    facts = vocab.resolve(code, declarations).facts
                    if facts is not None and (facts.terminal or facts.structural):
                        settled = True
                        break
                    open_codes.append((_moment(a.get("at")), str(a.get("id", "")), code))
                if settled:
                    continue
                code = max(open_codes)[2] if open_codes else "not-assessed"
                out.append({
                    "alternativeId": alt["id"], "criterionId": crit["id"], "measure": measure,
                    "code": code, "recorded": bool(open_codes),
                })
    return out


def _moment(value: Any) -> tuple[int, Any]:
    """A sort key that orders moments as instants, never as strings."""
    try:
        return (1, instant(value))
    except (TypeError, ValueError):
        return (0, str(value))


def _superseded(document: Mapping[str, Any]) -> int:
    from rubricator.criteria_versions import superseded_cells

    return superseded_cells(document)["count"]


def stage_of(
    document: Mapping[str, Any], *, outstanding: int | None = None, superseded: int | None = None
) -> int:
    """The earliest ADR-0005 stage whose work is not on record.

    Stage 1 is open until ``frame_set`` has recorded whether anyone looked for
    ambiguities; 2 until a live alternative exists; 3 until a live criterion
    does; 5 while any cell is outstanding *or* answers an older definition of
    its criterion (ADR-0016: work genuinely remains); 6 after. Stage 4, the
    confirmation gate, is reported once ``frame_confirm`` exists to pass it
    (#57).
    """
    if "ambiguities" not in (document.get("subject") or {}):
        return 1
    if not _live(document.get("alternatives", [])):
        return 2
    if not _live(document.get("criteria", [])):
        return 3
    if outstanding is None:
        outstanding = len(outstanding_cells(document))
    if superseded is None:
        superseded = _superseded(document)
    return 5 if outstanding or superseded else 6


def conform(value: Any, schema: Mapping[str, Any], path: str = "$") -> tuple[Any, list[str]]:
    """``value`` cut down to what ``schema`` admits, and the paths that were cut.

    The frozen output shapes are closed, and stored data is not guaranteed to
    fit them: a document written before a rule existed, or edited by hand in a
    shared repository, may carry a key, a type or an enum value the contract has
    no room for. Returning it would be a ``ContractViolation`` -- a server bug
    reported for what is a data problem -- so a projection keeps what fits,
    drops what does not, and says where. An object missing a required field is
    dropped whole (``None``), and so is the array item holding it.

    Reads only the keywords the frozen fragments use: ``type``, ``properties``,
    ``required``, ``items``, ``enum``, ``const`` and ``anyOf``.

    >>> conform({"id": "x", "label": 3, "colour": "red"},
    ...         {"type": "object", "properties": {"id": {"type": "string"},
    ...          "label": {"type": "string"}}, "required": ["id"]})
    ({'id': 'x'}, ['$.label', '$.colour'])
    """
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            got, cut = conform(value, branch, path)
            if not cut and (got is not None or value is None):
                return got, []
        return None, [path]
    if "const" in schema and value != schema["const"]:
        return None, [path]
    if "enum" in schema and value not in schema["enum"]:
        return None, [path]
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, Mapping):
            return None, [path]
        props = schema.get("properties", {})
        out: dict[str, Any] = {}
        cut: list[str] = []
        for key, item in value.items():
            if key not in props:
                cut.append(f"{path}.{key}")
                continue
            got, sub = conform(item, props[key], f"{path}.{key}")
            cut.extend(sub)
            if got is not None or not sub:
                out[key] = got
        if any(r not in out for r in schema.get("required", [])):
            return None, cut or [path]
        return out, cut
    if kind == "array":
        if not isinstance(value, list):
            return None, [path]
        items: list[Any] = []
        cut = []
        for i, item in enumerate(value):
            got, sub = conform(item, schema.get("items", {}), f"{path}[{i}]")
            cut.extend(sub)
            if got is not None or not sub:
                items.append(got)
        return items, cut
    checks = {
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if kind in checks and not checks[kind](value):
        return None, [path]
    return value, []


def _criterion(stored: Mapping[str, Any]) -> dict[str, Any]:
    """A stored criterion in the shape ``criteria_set`` takes, so it round-trips.

    The scale, direction, target and anchors are read back out of the expanded
    measurement; what the preset derives (range, levels, the anchor hash) is
    left out, because writing it back would be stating what the scale already
    says. The result is then conformed to the frozen criterion shape.
    """
    measurement = stored.get("defaultMeasurement") or {}
    if not isinstance(measurement, Mapping):
        measurement = {}
    out: dict[str, Any] = {k: stored[k] for k in ("id", "label") if k in stored}
    for key in ("scale", "preference"):
        if key in measurement:
            out[key] = measurement[key]
    target = (measurement.get("range") or {}).get("target")
    if target is not None:
        out["target"] = target
    levels = (measurement.get("anchors") or {}).get("levels") or {}
    if isinstance(levels, Mapping) and levels:
        out["anchors"] = [{"level": str(k), "text": v} for k, v in levels.items()]
    for key in ("missingCodes", "definition", "supersededBy"):
        if key in stored:
            out[key] = stored[key]
    if stored.get("tombstoned"):
        out["tombstoned"] = True
    return out


def _projected(rows: Any, shape: Mapping[str, Any], path: str, cut: list[str]) -> list[Any]:
    got, sub = conform(rows if isinstance(rows, list) else [], {"type": "array", "items": shape}, path)
    cut.extend(sub)
    return got


def analysis_get(
    store: AnalysisStore, *, analysis_id: str, view: str = "summary"
) -> dict[str, Any]:
    """Read the durable state of an analysis as one projection. Writes nothing.

    Every view carries the counts and the stage. ``frame`` adds the subject and
    the alternatives; ``criteria`` adds the criteria in the shape
    ``criteria_set`` takes, with the set version; ``outstanding`` adds the cells
    not yet settled, with counts by missingness code; ``full`` adds a resource
    link to the document, never the document itself.

    An unknown or expired id raises :class:`~rubricator.store.AnalysisNotFound`,
    which names the retention window and the two ways out.
    """
    from rubricator.surface.frozen import ALTERNATIVE, CRITERION, SUBJECT

    if view not in VIEWS:
        raise ValueError(f'unknown view "{view}"; the views are {", ".join(VIEWS)}.')
    try:
        document = store.read(analysis_id)
    except AnalysisNotFound:
        raise
    except (KeyError, TypeError, ValueError) as error:
        # A malformed contribution in a shared store: say which read failed and
        # where the way back in is, rather than a bare decode error.
        raise ValueError(
            f'refused: analysis "{analysis_id}" cannot be read whole: {error}. analysis_open '
            "still reopens it from the frame alone; the contribution file that fails must be "
            "repaired or removed by whoever owns it."
        ) from error
    outstanding = outstanding_cells(document)
    superseded = _superseded(document)
    alternatives = _live(document.get("alternatives", []))
    criteria = _live(document.get("criteria", []))
    measures = len(document.get("measures", [])) or 1
    by_code = Counter(c["code"] for c in outstanding)
    stage = stage_of(document, outstanding=len(outstanding), superseded=superseded)
    name, action = STAGES[stage]
    cells = len(alternatives) * len(criteria) * measures
    subject = document.get("subject") or {}
    result: dict[str, Any] = {
        "analysisId": analysis_id,
        "view": view,
        "question": str(subject.get("question", "")),
        "stage": stage,
        "counts": {
            "alternatives": len(alternatives),
            "criteria": len(criteria),
            "cells": cells,
            "outstanding": len(outstanding),
            "superseded": superseded,
            "byCode": [{"code": k, "count": by_code[k]} for k in sorted(by_code)],
        },
    }
    cut: list[str] = []
    if view == "frame":
        got, sub = conform(subject, SUBJECT, "$.subject")
        cut.extend(sub)
        result["subject"] = got if got is not None else {"question": result["question"]}
        result["alternatives"] = _projected(
            document.get("alternatives"), ALTERNATIVE, "$.alternatives", cut)
    elif view == "criteria":
        result["criteria"] = _projected(
            [_criterion(c) for c in document.get("criteria", []) if isinstance(c, Mapping)],
            CRITERION, "$.criteria", cut)
        version = document.get("criteriaVersion")
        result["criteriaVersion"] = version if isinstance(version, str) else None
    elif view == "outstanding":
        result["outstanding"] = outstanding
    elif view == "full":
        result["resourceLink"] = analysis_uri(analysis_id)
    codes = ", ".join(f"{by_code[k]} {k}" for k in sorted(by_code))
    result["summary"] = (
        f'"{analysis_id}" at stage {stage} ({name}): {len(alternatives)} alternative(s), '
        f"{len(criteria)} criteria, {len(outstanding)} of {cells} cell(s) outstanding"
        + (f" ({codes})" if codes else "")
        + (f"; {superseded} cell(s) answer an older criteria definition" if superseded else "")
        + (f"; {len(cut)} stored field(s) do not fit the contract and were left out: "
           + ", ".join(cut[:5]) + ("..." if len(cut) > 5 else "") if cut else "")
        + f"; next: {action}"
    )
    return result
