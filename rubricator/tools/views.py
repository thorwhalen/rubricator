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

from rubricator.rules import live_assertions
from rubricator.schema.vocabulary import vocabulary
from rubricator.store import AnalysisStore

__all__ = ["analysis_get", "VIEWS", "STAGES", "stage_of", "outstanding_cells", "analysis_uri"]

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
    5: ("populate", "score or mark the outstanding cells (analysis_get view=outstanding)"),
    6: ("review", "every cell is settled; review the weakest scores"),
}

#: The resource the ``full`` view links to. Served by the connector; a surface
#: without resources still gets a stable name for the document.
_URI = "rubricator://analysis/{analysis_id}"

#: The keys each projected shape may carry -- the frozen input shapes, so a
#: projection a model reads back can be handed straight to the writing verb.
_SUBJECT_KEYS = ("question", "decision", "decider", "context", "ambiguities")
_ALTERNATIVE_KEYS = ("id", "label", "description", "groupIds", "tombstoned", "supersededBy")
_MISSING_KEYS = ("id", "broader", "means", "structural", "terminal", "informative")
_DEFINITION_KEYS = ("objective", "question", "evidenceRule", "missingRules", "exclusions")


def analysis_uri(analysis_id: str) -> str:
    """The resource name of one analysis document."""
    return _URI.format(analysis_id=analysis_id)


def _live(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in rows if not r.get("tombstoned")]


def outstanding_cells(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The cells of the live matrix that no live assertion settles, in frame order.

    A cell is **settled** when a live assertion carries a value, or a blank
    whose code is terminal or structural. It is outstanding otherwise, and its
    ``code`` is the latest open blank's (by moment, then id), or
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
                open_codes: list[tuple[str, str, str]] = []
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
                    open_codes.append((str(a.get("at", "")), str(a.get("id", "")), code))
                if settled:
                    continue
                code = max(open_codes)[2] if open_codes else "not-assessed"
                out.append({
                    "alternativeId": alt["id"], "criterionId": crit["id"], "measure": measure,
                    "code": code, "recorded": bool(open_codes),
                })
    return out


def stage_of(document: Mapping[str, Any], *, outstanding: int | None = None) -> int:
    """The earliest ADR-0005 stage whose work is not on record.

    Stage 1 is open until ``frame_set`` has recorded whether anyone looked for
    ambiguities; 2 until a live alternative exists; 3 until a live criterion
    does; 5 while any cell is outstanding; 6 after. Stage 4, the confirmation
    gate, is reported once ``frame_confirm`` exists to pass it (#57).
    """
    if "ambiguities" not in document.get("subject", {}):
        return 1
    if not _live(document.get("alternatives", [])):
        return 2
    if not _live(document.get("criteria", [])):
        return 3
    if outstanding is None:
        outstanding = len(outstanding_cells(document))
    return 5 if outstanding else 6


def _pick(row: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {k: row[k] for k in keys if k in row}


def _criterion(stored: Mapping[str, Any]) -> dict[str, Any]:
    """A stored criterion in the shape ``criteria_set`` takes, so it round-trips.

    The scale, direction, target and anchors are read back out of the expanded
    measurement; what the preset derives (range, levels, the anchor hash) is
    left out, because writing it back would be stating what the scale already
    says.
    """
    measurement = stored.get("defaultMeasurement") or {}
    out: dict[str, Any] = {"id": stored["id"], "label": stored["label"]}
    if "scale" in measurement:
        out["scale"] = measurement["scale"]
    if "preference" in measurement:
        out["preference"] = measurement["preference"]
    target = (measurement.get("range") or {}).get("target")
    if target is not None:
        out["target"] = target
    levels = (measurement.get("anchors") or {}).get("levels") or {}
    if levels:
        out["anchors"] = [{"level": str(k), "text": v} for k, v in levels.items()]
    out["missingCodes"] = [_pick(d, _MISSING_KEYS) for d in stored.get("missingCodes", [])]
    definition = stored.get("definition")
    if isinstance(definition, Mapping):
        projected = _pick(definition, _DEFINITION_KEYS)
        if "missingRules" in projected:
            projected["missingRules"] = [
                _pick(r, ("when", "code")) for r in projected["missingRules"]
            ]
        out["definition"] = projected
    if stored.get("tombstoned"):
        out["tombstoned"] = True
    if stored.get("supersededBy"):
        out["supersededBy"] = list(stored["supersededBy"])
    return out


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
    if view not in VIEWS:
        raise ValueError(f'unknown view "{view}"; the views are {", ".join(VIEWS)}.')
    document = store.read(analysis_id)
    outstanding = outstanding_cells(document)
    alternatives = _live(document.get("alternatives", []))
    criteria = _live(document.get("criteria", []))
    measures = len(document.get("measures", [])) or 1
    by_code = Counter(c["code"] for c in outstanding)
    stage = stage_of(document, outstanding=len(outstanding))
    name, action = STAGES[stage]
    cells = len(alternatives) * len(criteria) * measures
    result: dict[str, Any] = {
        "analysisId": analysis_id,
        "view": view,
        "question": document["subject"]["question"],
        "stage": stage,
        "counts": {
            "alternatives": len(alternatives),
            "criteria": len(criteria),
            "cells": cells,
            "outstanding": len(outstanding),
            "byCode": [{"code": k, "count": by_code[k]} for k in sorted(by_code)],
        },
    }
    if view == "frame":
        result["subject"] = _pick(document["subject"], _SUBJECT_KEYS)
        result["alternatives"] = [
            _pick(a, _ALTERNATIVE_KEYS) for a in document.get("alternatives", [])
        ]
    elif view == "criteria":
        result["criteria"] = [_criterion(c) for c in document.get("criteria", [])]
        result["criteriaVersion"] = document.get("criteriaVersion")
    elif view == "outstanding":
        result["outstanding"] = outstanding
    elif view == "full":
        result["resourceLink"] = analysis_uri(analysis_id)
    codes = ", ".join(f"{by_code[k]} {k}" for k in sorted(by_code))
    result["summary"] = (
        f'"{analysis_id}" at stage {stage} ({name}): {len(alternatives)} alternative(s), '
        f"{len(criteria)} criteria, {len(outstanding)} of {cells} cell(s) outstanding"
        + (f" ({codes})" if codes else "")
        + f"; next: {action}"
    )
    return result
