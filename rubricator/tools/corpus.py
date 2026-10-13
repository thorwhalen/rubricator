"""Tool 3, ``corpus_add``: documents into an analysis's corpus, normalised once, addressed by content.

ADR-0014 (amended 2026-08-22, #50) makes a quote index into a **persisted
normalised rendition** of its source, stored with the original's locator and a
hash of the original. This verb is the only thing that makes one. Four rules,
each mechanical here:

- **Normalised once, under a named normaliser.** The rendition's ``content`` is
  :func:`rubricator.normalise.normalise` of the text the caller supplied, and
  its ``normaliserId`` says which. Nothing is prepended -- no title, no
  contextual preamble -- because the rendition is the text quotes resolve
  against, and a preamble in it would eventually be cited as the source
  (findings-method row 23). If the normaliser's behaviour has drifted from its
  pin, the call is refused: every rendition made under it would carry hashes
  nobody could reproduce.
- **The id is the content.** A document's id is derived from the normaliser and
  the original's hash, so adding the same text twice yields the same id and one
  document, and the same text under a new normaliser is a *second* document
  rather than a silent rewrite of the first's offsets.
- **Chunks are addresses, not text.** The chunker (:data:`CHUNKER_ID`) records
  ``[start, end)`` character offsets into the rendition's ``content``, and is
  versioned like the normaliser. Retrieval reads them; a quote never resolves
  against a chunk, so a chunk boundary costs recall and never a citation.
- **The ADR-0015 marker is set here and nowhere else.** A source the caller says
  a model wrote -- a prior analysis, a summary, an extracted table -- is marked,
  and so is one this verb recognises as rubricator's own output whatever the
  caller says. The marker is a file whose presence is the fact; nothing clears it.

The rendition itself merges into the analysis document's ``renditions`` (it is
comparanda v1's ``Rendition``); what v1 has no slot for -- the spans, whether
normalisation cleaned the text, the marker -- is kept beside it as corpus
records (see :mod:`rubricator.store`).

>>> chunk_spans("one two three four", window_chars=9, overlap_chars=0)
[(0, 7), (8, 13), (14, 18)]
>>> rendition_id("sha256:" + "0" * 64, normaliser_id="nfc-v1")
'doc-1e1d731dd583eb1357a176e70940e047'
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable, Mapping, Sequence

from rubricator.normalise import CURRENT, drifted, normalise
from rubricator.store import AnalysisStore

__all__ = [
    "CHUNKER_ID",
    "DEFAULT_WINDOW_CHARS",
    "DEFAULT_OVERLAP_CHARS",
    "CHARS_PER_TOKEN",
    "AGENT_PRODUCED_DETECTORS",
    "INGEST_RECORD",
    "MARKER_RECORD",
    "chunk_spans",
    "original_sha256",
    "rendition_id",
    "corpus_add",
]

#: The chunker's id, stored with every document's spans. A change to
#: :func:`chunk_spans` is a new id, exactly as for the normaliser: spans recorded
#: under one chunker are not reproducible under another.
CHUNKER_ID = "chunk-v1"

#: Retrieve small, present wide (findings-method row 23): a span is a retrieval
#: unit, and ``corpus_search`` widens it for presentation. Overlap defaults to
#: none, because overlap is not the recall mitigation it is assumed to be [84].
DEFAULT_WINDOW_CHARS = 400
DEFAULT_OVERLAP_CHARS = 0

#: The ratio behind ``tokenEstimate``. An estimate, said to be one: a real count
#: is model-specific and would need the provider's counter, which no tool may call.
CHARS_PER_TOKEN = 4

#: The names of the two corpus records kept beside a rendition.
INGEST_RECORD = "ingest"
MARKER_RECORD = "agent-produced"

#: Where an inline source's original is: nowhere but the text itself.
_INLINE_LOCATOR = "inline"

#: Media types whose text *is* the original, so its hash is the original's hash.
_TEXT_TYPES = ("text/", "application/json", "application/xml")

_ID_PREFIX = "doc-"
_ID_HEX = 32


def chunk_spans(text: str, *, window_chars: int, overlap_chars: int) -> list[tuple[int, int]]:
    """``chunk-v1``: ``[start, end)`` spans of at most ``window_chars`` over ``text``.

    A span ends at the last space inside its window, so no word is cut unless one
    word is longer than the window; it then ends at the window. The next span
    starts ``overlap_chars`` before the end, moved forward to the start of a
    word, and always after the previous start -- except that a word the window
    cut is continued where the cut fell, not skipped. Spans never begin or end
    with a space, and every non-space character is inside at least one span.

    >>> chunk_spans("aaa bbb ccc", window_chars=7, overlap_chars=4)
    [(0, 7), (4, 11)]
    >>> chunk_spans("", window_chars=5, overlap_chars=0)
    []
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    start = _word_start(text, 0)
    while start < n:
        end = min(start + window_chars, n)
        if end < n and text[end] != " ":
            cut = text.rfind(" ", start + 1, end)
            if cut > start:
                end = cut
        while end > start and text[end - 1] == " ":
            end -= 1
        spans.append((start, end))
        if end >= n:
            break
        resume = _past_spaces(text, end)
        overlapped = _word_start(text, max(end - overlap_chars, start + 1))
        # A word the window cut is continued, never skipped: resume is then inside it.
        start = min(overlapped, resume)
    return spans


def _past_spaces(text: str, at: int) -> int:
    while at < len(text) and text[at] == " ":
        at += 1
    return at


def _word_start(text: str, at: int) -> int:
    """The first word start at or after ``at``: past any space, and past the rest of a word cut at ``at``."""
    if 0 < at < len(text) and text[at - 1] != " " and text[at] != " ":
        space = text.find(" ", at)
        at = len(text) if space < 0 else space
    return _past_spaces(text, at)


def original_sha256(text: str) -> str:
    """``originalSha256``: ``sha256:`` over the UTF-8 bytes of the text *as supplied*."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def rendition_id(original_hash: str, *, normaliser_id: str) -> str:
    """The content-addressed id of a rendition: one per (original, normaliser)."""
    digest = hashlib.sha256(f"{normaliser_id}\n{original_hash}".encode("utf-8")).hexdigest()
    return _ID_PREFIX + digest[:_ID_HEX]


def _comparanda_analysis(text: str) -> str | None:
    """A comparanda analysis document is a prior run's output, whatever the caller says."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    if isinstance(parsed, dict) and {"schemaVersion", "alternatives", "criteria"} <= parsed.keys():
        return "the text is a comparanda analysis document, which only an analysis run produces"
    return None


#: Deterministic recognisers of rubricator's own output. Each returns why the
#: text is agent-produced, or ``None``. They can only *set* the marker; a source
#: none of them recognises is marked or not on the caller's word. Data, so a
#: new output format adds a recogniser here without touching the verb.
AGENT_PRODUCED_DETECTORS: tuple[Callable[[str], str | None], ...] = (_comparanda_analysis,)


def _refuse(message: str) -> ValueError:
    return ValueError(f"refused, nothing was added: {message}")


def _source_name(index: int, source: Mapping[str, Any]) -> str:
    named = source.get("id") or source.get("title")
    return f"sources[{index}]" + (f' ("{named}")' if named else "")


def _chunking(chunking: Mapping[str, Any] | None) -> tuple[int, int]:
    chunking = chunking or {}
    window = chunking.get("windowChars", DEFAULT_WINDOW_CHARS)
    overlap = chunking.get("overlapChars", DEFAULT_OVERLAP_CHARS)
    if window < 1:
        raise _refuse(f"chunking.windowChars is {window}; a window holds at least one character.")
    if not 0 <= overlap < window:
        raise _refuse(
            f"chunking.overlapChars is {overlap} with windowChars {window}; overlap is at least 0 "
            "and less than the window, or the chunker would never move forward."
        )
    return window, overlap


def _prepared(
    index: int, source: Mapping[str, Any], *, normaliser_id: str
) -> dict[str, Any]:
    """Everything about one source that does not depend on the store, or a refusal naming it."""
    text = source.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _refuse(f"{_source_name(index, source)} has no text. A document is its text.")
    content = normalise(text, normaliser_id=normaliser_id)
    if not content:
        raise _refuse(
            f"{_source_name(index, source)} has no text once normalised under {normaliser_id}: "
            "it holds only invisible characters and whitespace."
        )
    original = original_sha256(text)
    detected = [why for detect in AGENT_PRODUCED_DETECTORS if (why := detect(text))]
    return {
        "index": index,
        "source": source,
        "id": rendition_id(original, normaliser_id=normaliser_id),
        "original": original,
        "content": content,
        "cleaned": content != text,
        "declared": bool(source.get("agentProduced")),
        "detected": detected,
    }


def corpus_add(
    store: AnalysisStore,
    *,
    analysis_id: str,
    sources: Sequence[Mapping[str, Any]],
    chunking: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Add source documents to the corpus: normalised, content-addressed, chunked into offsets.

    Stages 2 and 5 of ADR-0005. Deterministic: a fixed chunker and a versioned
    normaliser over text the caller supplies; nothing is fetched. Every source is
    checked before anything is written, so a refusal adds nothing. Adding a
    document that is already present writes nothing new except a marker it did
    not yet carry, and says so.
    """
    stale = drifted()
    if stale:
        raise _refuse(
            f"normaliser(s) {', '.join(stale)} no longer produce what their pin records. A "
            "rendition made now would carry hashes no other build reproduces; restore the "
            "normaliser or add a new version beside it."
        )
    if not sources:
        raise _refuse("no sources were given.")
    window, overlap = _chunking(chunking)
    prepared = [_prepared(i, s, normaliser_id=CURRENT) for i, s in enumerate(sources)]

    frame = store.frame(analysis_id)
    renditions = {r["id"]: r for r in frame.get("renditions", []) if isinstance(r, dict)}
    renditions.update({r["id"]: r for r in store.renditions(analysis_id)})
    records = store.corpus_records(analysis_id)

    warnings: list[str] = []
    documents: list[dict[str, Any]] = []
    for item in prepared:
        doc_id, source = item["id"], item["source"]
        name = _source_name(item["index"], source)
        repeated = any(d["documentId"] == doc_id for d in documents)
        if repeated:
            warnings.append(f"{name} is the same text as an earlier source in this call; added once.")
        stored = records.setdefault(doc_id, {})
        present = doc_id in renditions

        # The marker first: a rendition is never visible before the marker it needs.
        reasons = ["the caller declared it agent-produced"] if item["declared"] else []
        reasons += item["detected"]
        if item["detected"] and not item["declared"]:
            warnings.append(
                f"{name} was marked agent-produced although not declared: {item['detected'][0]}."
            )
        if MARKER_RECORD in stored and not reasons and not repeated:
            warnings.append(
                f"{name} is already marked agent-produced; a marker is never cleared, so every "
                "reference into it stays secondary at best."
            )
        if reasons and MARKER_RECORD not in stored:
            stored[MARKER_RECORD] = {"renditionId": doc_id, "reasons": reasons}
            store.put_corpus_record(analysis_id, doc_id, MARKER_RECORD, stored[MARKER_RECORD])

        ingest = stored.get(INGEST_RECORD)
        if ingest is None or ingest.get("unreadable"):
            spans = chunk_spans(item["content"], window_chars=window, overlap_chars=overlap)
            ingest = {
                "renditionId": doc_id,
                "normaliserId": CURRENT,
                "cleaned": item["cleaned"],
                "chunkerId": CHUNKER_ID,
                "chunking": {"windowChars": window, "overlapChars": overlap},
                "spans": [{"start": a, "end": b} for a, b in spans],
                **({"mediaType": source["mediaType"]} if source.get("mediaType") else {}),
            }
            stored[INGEST_RECORD] = ingest
            store.put_corpus_record(analysis_id, doc_id, INGEST_RECORD, ingest)
        elif chunking is not None and not repeated and ingest.get("chunking") != {
            "windowChars": window, "overlapChars": overlap,
        }:
            warnings.append(
                f"{name} was already chunked with {ingest.get('chunking')}; its spans were kept, "
                "because re-chunking a stored document would move every span into it."
            )

        if not present:
            rendition = {
                "id": doc_id,
                "originalLocator": source.get("uri") or _INLINE_LOCATOR,
                "originalSha256": item["original"],
                "normaliserId": CURRENT,
                "content": item["content"],
            }
            if source.get("title"):
                rendition["label"] = source["title"]
            store.put_rendition(analysis_id, rendition)
            renditions[doc_id] = rendition
            media = source.get("mediaType")
            if media and not media.startswith(_TEXT_TYPES):
                warnings.append(
                    f"{name} is {media}: its originalSha256 fingerprints the text supplied, not "
                    "the file, so a later check against the file's bytes will report it changed."
                )
        elif not repeated:
            warnings.append(f"{name} is already in the corpus as {doc_id}; nothing was re-added.")

        documents.append({
            "documentId": doc_id,
            **({"sourceId": source["id"]} if source.get("id") else {}),
            "added": not present,
            "cleaned": bool(ingest.get("cleaned", item["cleaned"])),
            "agentProduced": MARKER_RECORD in stored,
            "spanCount": len(ingest.get("spans", [])),
            "tokenEstimate": _tokens(renditions[doc_id].get("content") or item["content"]),
        })

    inline = sum(1 for s in sources if not s.get("uri"))
    if inline:
        warnings.append(
            f"{inline} source(s) have no uri: the rendition is their only copy, and no drift "
            "check against an original is possible."
        )
    for doc_id, others in _same_content(renditions, [d["documentId"] for d in documents if d["added"]]).items():
        warnings.append(
            f"{doc_id} has the same normalised text as {', '.join(others)}: different originals "
            "that normalise alike. Both are kept, each with its own original's hash."
        )

    unique = {d["documentId"]: d for d in reversed(documents)}
    added = sum(1 for d in unique.values() if d["added"])
    cleaned = sum(1 for d in unique.values() if d["cleaned"])
    agent = sum(1 for d in unique.values() if d["agentProduced"])
    span_count = sum(d["spanCount"] for d in unique.values())
    token_estimate = sum(d["tokenEstimate"] for d in unique.values())
    corpus_tokens = sum(_tokens(r.get("content") or "") for r in renditions.values())
    return {
        "analysisId": analysis_id,
        "documentIds": [d["documentId"] for d in documents],
        "documents": documents,
        "spanCount": span_count,
        "tokenEstimate": token_estimate,
        "corpusTokenEstimate": corpus_tokens,
        "warnings": warnings,
        "summary": (
            f"{added} document(s) added, {len(unique) - added} already present; {cleaned} cleaned "
            f"by {CURRENT}; {agent} marked agent-produced (references into those are secondary at "
            f"best); {span_count} span(s) by {CHUNKER_ID}; about {token_estimate} tokens in these, "
            f"{corpus_tokens} in the corpus (estimated at {CHARS_PER_TOKEN} characters a token)"
        ),
    }


def _tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _same_content(
    renditions: Mapping[str, Mapping[str, Any]], ids: Sequence[str]
) -> dict[str, list[str]]:
    """For each document in this call, the other documents with the same normalised text."""
    found: dict[str, list[str]] = {}
    for rid in sorted(set(ids)):
        content = renditions[rid].get("content")
        others = sorted(o for o, r in renditions.items() if o != rid and r.get("content") == content)
        if others:
            found[rid] = others
    return found
