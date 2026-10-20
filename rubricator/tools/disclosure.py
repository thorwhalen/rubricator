"""Tool 17, ``disclose_variance``: the variance notice, filled from what was actually recorded.

ADR-0018. The wording is content (``data/disclosures/variance.md``); this tool only
substitutes the four fields it declares, and takes every one from the stored
document, never from the plan or from a default:

- **scorings** are *counted* from the live assertions of each cell (a placeholder
  blank that says nobody looked is no scoring), not read from a procedure's
  ``repeats``;
- **traversal** is read off the ``procedures[]`` that live assertions point at;
- **order** is the seeds on the assertions' ``perturbation`` records;
- **independence** is :func:`rubricator.independence.agreement` over the cells that
  hold two or more scorings, labelled by the weakest rung among them.

No cell with two scorings means ``n = 1, unmeasured``. No stability number is ever
estimated here: a figure for the spread between scorings is the job of
``stability_report`` (planned), and a size for what a mitigation removes has not
been measured for this tool. An analysis with no procedure record says so; it is
never given a figure it does not have.

Reads one document; writes nothing; no clock, no model.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from rubricator.disclosures import disclosures
from rubricator.independence import agreement, lowest_rung
from rubricator.rules import live_assertions
from rubricator.store import AnalysisStore

__all__ = ["disclose_variance"]

_NOT_RECORDED = "not recorded"
_UNMEASURED = "n = 1, unmeasured: no cell holds two scorings, so nothing here measures stability"


def disclose_variance(store: AnalysisStore, *, analysis_id: str) -> dict[str, Any]:
    """The variance disclosure for ``analysis_id``, as text plus what it does and does not measure."""
    from rubricator.tools.analysis import _is_placeholder
    from rubricator.tools.views import skipped_note

    document, skipped = store.read_skipping(analysis_id)
    live_a = {a["id"] for a in document["alternatives"] if not a.get("tombstoned")}
    live_c = {c["id"] for c in document["criteria"] if not c.get("tombstoned")}
    authors = {a["id"]: a for a in document.get("authors", [])}
    procedures = {p["id"]: p for p in document.get("procedures", [])}

    per_cell: list[list[Mapping[str, Any]]] = []
    for cell in document["cells"]:
        if cell["alternativeId"] not in live_a or cell["criterionId"] not in live_c:
            continue
        draws = [a for a in live_assertions(cell) if not _is_placeholder(
            {**cell, "missing": a.get("missing")}, document)]
        # A scoring is a value: a terminal blank is a claim about the cell, not a second reading.
        draws = [a for a in draws if a.get("value") is not None]
        if draws:
            per_cell.append(draws)

    counts = [len(d) for d in per_cell]
    repeated = [d for d in per_cell if len(d) >= 2]
    every = [a for d in per_cell for a in d]
    used = sorted({a["procedureId"] for a in every if a.get("procedureId") in procedures})
    seeds = sorted({str(a["perturbation"]["seed"]) for a in every
                    if (a.get("perturbation") or {}).get("seed") is not None})

    fields = {
        "scorings": _scorings(counts, len(repeated)),
        "traversal": _traversal([procedures[p] for p in used]) + _partial(
            sum(a.get("procedureId") in procedures for a in every), len(every), "a procedure record"),
        "order": (f"seeded order, seeds {', '.join(seeds)}" if seeds else _NOT_RECORDED) + _partial(
            sum((a.get("perturbation") or {}).get("seed") is not None for a in every),
            len(every), "a seed") if seeds else _NOT_RECORDED,
        "independence": _independence(repeated, authors),
    }
    template = disclosures()["variance"].body
    measured, not_measured = _ledger(counts, repeated, fields, authors, seeds, used)
    return {
        "analysisId": analysis_id,
        "text": template.format_map(fields),
        "measured": measured,
        "notMeasured": not_measured,
        "procedureIds": used,
        "summary": (
            f"{len(per_cell)} scored cell(s), {len(repeated)} with two or more scorings; "
            f"{len(used)} procedure(s) recorded." + skipped_note(skipped)
        ),
    }


def _scorings(counts: list[int], repeated: int) -> str:
    if not counts:
        return f"{_NOT_RECORDED} (no cell holds a scoring)"
    low, high = min(counts), max(counts)
    span = str(low) if low == high else f"{low} to {high}, varying by cell"
    return f"{span} per cell, counted from the stored scorings ({repeated} of {len(counts)} cells hold two or more)"


def _partial(have: int, total: int, what: str) -> str:
    """A caveat when only some scorings carry ``what``, so a union never reads as universal."""
    return "" if have in (0, total) else f" (only {have} of {total} scorings carry {what})"


def _traversal(used: list[Mapping[str, Any]]) -> str:
    plans = sorted({p["traversal"] for p in used if p.get("traversal")})
    return ", ".join(plans) if plans else _NOT_RECORDED


def _independence(repeated: list[list[Mapping[str, Any]]], authors: Mapping[str, Any]) -> str:
    if not repeated:
        return _UNMEASURED
    found = [agreement(d, authors) for d in repeated]
    found = [f for f in found if f]
    if not found:
        return "not assessable: the repeated scorings are agreed values (consensus), not observations"
    rung = lowest_rung(f["rung"] for f in found)
    label = next(f["label"] for f in found if f["rung"] == rung)
    return f"{label} (weakest rung among {len(found)} cells with repeats: {rung})"


def _ledger(counts, repeated, fields, authors, seeds, used) -> tuple[list[str], list[str]]:
    measured: list[str] = []
    if counts:
        mix = Counter(counts)
        measured.append("scorings per cell, counted: " + ", ".join(
            f"{k} scoring(s) in {mix[k]} cell(s)" for k in sorted(mix)))
    if used:
        measured.append(f"traversal, read from {len(used)} procedure record(s)")
    if seeds:
        measured.append("order seeds, read from the scorings' perturbation records")
    if repeated:
        measured.append("independence rung of the repeated scorings: " + fields["independence"])
    not_measured = ["how large an effect any mitigation (traversal, order, a fresh session) has on the scores"]
    if not repeated:
        not_measured.insert(0, "stability: no cell holds two scorings (n = 1, unmeasured)")
    else:
        not_measured.insert(0, "a stability figure: this tool estimates none")
    if not used:
        not_measured.append("the procedure: no procedure record is attached to any scoring")
    if not seeds:
        not_measured.append("order: no seed recorded")
    return measured, not_measured
