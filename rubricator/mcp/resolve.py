"""Resolving a resource URI to the content it names (#80, #230).

Pure functions over the store, with no MCP import, so the connector and a test
read the same thing. A span id is ``{document_id}:{start}-{end}`` and indexes
into the document's *persisted normalised rendition* (#50), never the original:
the text returned is exactly what the quote was checked against.

A span is only what ingest stored. An id that parses but is not one of the
document's stored spans is refused, never rounded to the nearest one: a
citation that quietly resolves to different text is worse than one that fails.

>>> from rubricator.surface.resources import parse_span_id
>>> parse_span_id("doc-a:0-4")
('doc-a', 0, 4)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rubricator.schema.source import published_schema_text
from rubricator.schema.vocabulary import vocabulary
from rubricator.store import AnalysisStore
from rubricator.surface.resources import parse_span_id
from rubricator.tools.corpus import INGEST_RECORD

__all__ = [
    "read_document", "read_span", "read_shipped", "read_missingness_codes", "read_comparanda_schema",
    "read_analyses",
]


def _renditions(store: AnalysisStore, analysis_id: str) -> dict[str, dict[str, Any]]:
    """Every rendition of one analysis by id; an unknown analysis raises ``AnalysisNotFound``."""
    frame = store.frame(analysis_id)
    return {r["id"]: r for r in [*frame.get("renditions", []), *store.renditions(analysis_id)]}


def _rendition(store: AnalysisStore, analysis_id: str, document_id: str) -> dict[str, Any]:
    held = _renditions(store, analysis_id)
    if document_id not in held:
        known = ", ".join(sorted(held)) or "none"
        raise KeyError(f'no document "{document_id}" in analysis "{analysis_id}". It holds: {known}.')
    return held[document_id]


def read_document(store: AnalysisStore, analysis_id: str, document_id: str) -> tuple[str, dict[str, Any]]:
    """The rendition's text and the provenance that names its original."""
    rendition = _rendition(store, analysis_id, document_id)
    return rendition["content"], {
        "documentId": document_id,
        "normaliserId": rendition.get("normaliserId"),
        "originalLocator": rendition.get("originalLocator"),
        "originalSha256": rendition.get("originalSha256"),
    }


def read_span(store: AnalysisStore, analysis_id: str, span: str) -> tuple[str, dict[str, Any]]:
    """The exact text of one stored span, with its document, offsets and provenance."""
    document_id, start, end = parse_span_id(span)
    text, meta = read_document(store, analysis_id, document_id)
    ingest = store.corpus_records(analysis_id).get(document_id, {}).get(INGEST_RECORD) or {}
    stored = {(s.get("start"), s.get("end")) for s in ingest.get("spans") or [] if isinstance(s, dict)}
    if (start, end) not in stored:
        raise KeyError(
            f'"{span}" is not a stored span of document "{document_id}" in analysis "{analysis_id}". '
            f"That document has {len(stored)} stored span(s); spans are never re-chunked or rounded."
        )
    return text[start:end], {**meta, "start": start, "end": end}


# -- the fixed and listed resources (#230) -----------------------------------

_SHIPPED = Path(__file__).resolve().parent.parent / "data" / "resources"


def read_shipped(name: str) -> str:
    """One shipped content file (``method``, ``confidence-rubric``): content, not code.

    >>> read_shipped("method").startswith("# The rubricator method")
    True
    """
    return (_SHIPPED / f"{name}.md").read_text(encoding="utf-8")


def read_missingness_codes() -> str:
    """The core missingness vocabulary as JSON: each code, its three flags and what it means.

    Core only: the frozen URI names no analysis, so an analysis's own extensions
    are read from its document (``rubricator://analysis/{id}``, ``missingCodes``).

    >>> [c["code"] for c in json.loads(read_missingness_codes())["codes"]][:2]
    ['not-applicable', 'not-assessed']
    """
    vocab = vocabulary()
    codes = [
        {"code": code, "structural": f.structural, "terminal": f.terminal,
         "informative": f.informative, "means": f.means}
        for code, f in vocab.missing_codes.items()
    ]
    return json.dumps({"vocabularyVersion": vocab.version, "codes": codes}, ensure_ascii=False)


def read_comparanda_schema(version: str) -> str:
    """The published schema at one version; a non-integer or unsupported one is refused."""
    if not re.fullmatch(r"0|[1-9][0-9]*", version):
        raise ValueError(f'a schema version is a whole number; got "{version}".')
    return published_schema_text(int(version))


def read_analyses(store: AnalysisStore) -> str:
    """The live analyses, newest change first: id, question, stage, last change.

    Never an error for an empty store. An analysis whose files cannot be read is
    listed by id with ``unreadable`` set, rather than hiding it or failing the list.
    """
    from rubricator.tools.confirm import gate
    from rubricator.tools.views import stage_of

    rows = []
    for analysis_id in store.analyses():
        row: dict[str, Any] = {"id": analysis_id, "lastChange": store.last_write(analysis_id)}
        try:
            document, _ = store.read_skipping(analysis_id)
            row["question"] = str((document.get("subject") or {}).get("question", ""))
            row["stage"] = stage_of(document, confirmed=gate(store.confirmations(analysis_id))["open"])
        except Exception as error:  # a bad analysis must not hide the others
            row.update(question="", stage=None, unreadable=f"{type(error).__name__}: {error}")
        rows.append(row)
    rows.sort(key=lambda r: (r["lastChange"] or "", r["id"]), reverse=True)
    return json.dumps({"analyses": rows}, ensure_ascii=False)
