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
import re
from functools import lru_cache
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
    "agent_produced_names",
    "cited_document",
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


_FENCES = ("```", "~~~")
_INFO_STRING = re.compile(r"[\w-]*\Z")


def _unfenced(text: str) -> str:
    """``text`` without one Markdown code fence around the whole of it. Linear: no backtracking."""
    fence = text[:3]
    if fence not in _FENCES or len(text) < 6 or not text.endswith(fence):
        return text
    info, newline, body = text[3:-3].partition("\n")
    return body if newline and _INFO_STRING.match(info.strip()) else text


def _as_json(text: str) -> Any:
    """``text`` parsed as JSON once a BOM and one enclosing code fence are taken off, else ``None``."""
    try:
        return json.loads(_unfenced(text.lstrip("\ufeff").strip()))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _shapes() -> tuple[tuple[Any, frozenset[str], str], ...]:
    """(validator, keys that must be present, what it is) for every object rubricator emits whole.

    The contracts themselves -- the vendored comparanda schema and the frozen
    output schemas -- with types, nested shapes and closed objects, so a source
    is recognised only when it *validates* as one of them, never on key names
    like ``id`` and ``subject`` that a ticket export also has. An analysis must
    also carry ``alternatives`` and ``criteria``, which every analysis rubricator
    writes has from ``analysis_open`` on.
    """
    from jsonschema import Draft202012Validator

    from rubricator.schema.source import SchemaSource
    from rubricator.surface.frozen import FROZEN_TOOLS

    shapes = [(Draft202012Validator(SchemaSource.vendored().schema), frozenset({"alternatives", "criteria"}),
               "a comparanda analysis document")]
    shapes += [
        (Draft202012Validator(spec.output_schema), frozenset(spec.output_schema["required"]),
         f"a {spec.name} result")
        for spec in FROZEN_TOOLS
    ]
    return tuple(shapes)


def _rubricator_output(text: str) -> str | None:
    """A comparanda analysis or a rubricator tool's result, as the whole text, is a run's output.

    Recognised as JSON, as the entire text, behind at most a BOM and one code
    fence. Prose around the JSON, or a list of results, is not recognised: the
    caller's ``agentProduced`` is what marks those (#202 extends this).
    """
    parsed = _as_json(text)
    if not isinstance(parsed, dict):
        return None
    for validator, present, what in _shapes():
        if present <= parsed.keys() and validator.is_valid(parsed):
            return f"the text is {what}, which only an analysis run produces"
    return None


#: Deterministic recognisers of rubricator's own output. Each returns why the
#: text is agent-produced, or ``None``. They can only *set* the marker; a source
#: none of them recognises is marked or not on the caller's word. Data, so a
#: new output format adds a recogniser here without touching the verb.
AGENT_PRODUCED_DETECTORS: tuple[Callable[[str], str | None], ...] = (_rubricator_output,)


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
    renditions = {
        r["id"]: r for r in [*frame.get("renditions", []), *store.renditions(analysis_id)]
        if isinstance(r, dict) and isinstance(r.get("id"), str)
    }
    records = store.corpus_records(analysis_id)
    before = {rid: set(kept) for rid, kept in records.items()}

    # One plan per document, every occurrence in this call folded in, before
    # anything is written: any occurrence's declaration marks it, and the first
    # uri, title and media type given are the ones kept.
    plans: dict[str, dict[str, Any]] = {}
    for item in prepared:
        plan = plans.setdefault(item["id"], {**item, "source": {}, "reasons": [], "names": []})
        plan["names"].append(_source_name(item["index"], item["source"]))
        plan["declared"] = plan["declared"] or item["declared"]
        if item["declared"]:
            plan["reasons"].append("the caller declared it agent-produced")
        plan["reasons"] += item["detected"]
        for key, value in item["source"].items():
            if value and not plan["source"].get(key):
                plan["source"][key] = value
    warnings: list[str] = []
    _mark_by_content(store, analysis_id, plans, renditions, records, warnings)
    rows: dict[str, dict[str, Any]] = {}
    for doc_id, plan in plans.items():
        rows[doc_id] = _add_one(
            store, analysis_id, doc_id, plan, renditions=renditions,
            stored=records.setdefault(doc_id, {}), chunking=chunking,
            window=window, overlap=overlap, warnings=warnings,
        )
    newly = {
        rid for rid, kept in records.items()
        if MARKER_RECORD in kept and MARKER_RECORD not in before.get(rid, ())
    }
    warnings += _cited_as_primary(store, analysis_id, newly)
    for plan in plans.values():
        if len(plan["names"]) > 1:
            warnings.append(
                f"{', '.join(plan['names'])} are the same text; added once as {plan['id']}."
            )
    documents, listed = [], set()
    for item in prepared:
        row = dict(rows[item["id"]])
        if item["id"] in listed:
            row["added"] = False  # an earlier source in this call added it
        listed.add(item["id"])
        if item["source"].get("id"):
            row["sourceId"] = item["source"]["id"]
        documents.append(row)

    inline = sum(1 for d, p in plans.items() if rows[d]["added"] and not p["source"].get("uri"))
    if inline:
        warnings.append(
            f"{inline} document(s) were added with no uri: the rendition is their only copy, and "
            "no drift check against an original is possible."
        )
    for doc_id, others in _same_content(renditions, [d for d in plans if rows[d]["added"]]).items():
        warnings.append(
            f"{doc_id} has the same normalised text as {', '.join(others)}: different originals "
            "that normalise alike. Both are kept, each with its own original's hash."
        )

    unique = rows.values()
    added = sum(1 for d in unique if d["added"])
    cleaned = sum(1 for d in unique if d["cleaned"])
    agent = sum(1 for d in unique if d["agentProduced"])
    span_count = sum(d["spanCount"] for d in unique)
    token_estimate = sum(d["tokenEstimate"] for d in unique)
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
            f"{added} document(s) added, {len(rows) - added} already present; {cleaned} cleaned "
            f"by {CURRENT}; {agent} marked agent-produced (measures_write refuses a primary "
            f"reference naming those); {span_count} span(s) by {CHUNKER_ID}; about "
            f"{token_estimate} tokens in these, {corpus_tokens} in the corpus (estimated at "
            f"{CHARS_PER_TOKEN} characters a token)"
        ),
    }


def _add_one(
    store: AnalysisStore,
    analysis_id: str,
    doc_id: str,
    plan: Mapping[str, Any],
    *,
    renditions: dict[str, Any],
    stored: dict[str, Any],
    chunking: Mapping[str, Any] | None,
    window: int,
    overlap: int,
    warnings: list[str],
) -> dict[str, Any]:
    """Write what one document still lacks -- marker, then spans, then rendition -- and its row."""
    source, name = plan["source"], plan["names"][0]
    existing = renditions.get(doc_id)
    content = existing.get("content") if existing and isinstance(existing.get("content"), str) \
        else plan["content"]

    # The marker first: a rendition is never visible before the marker it needs.
    if plan["detected"] and not plan["declared"]:
        warnings.append(f"{name} was marked agent-produced although not declared: {plan['detected'][0]}.")
    if MARKER_RECORD in stored and not plan["reasons"]:
        warnings.append(
            f"{name} is already marked agent-produced; a marker is never cleared, so a primary "
            "reference into it stays refused."
        )
    if plan["reasons"] and MARKER_RECORD not in stored:
        stored[MARKER_RECORD] = {"renditionId": doc_id, "reasons": list(dict.fromkeys(plan["reasons"]))}
        store.put_corpus_record(analysis_id, doc_id, MARKER_RECORD, stored[MARKER_RECORD])

    ingest = stored.get(INGEST_RECORD)
    if not _usable(ingest):
        spans = chunk_spans(content, window_chars=window, overlap_chars=overlap)
        ingest = {
            "renditionId": doc_id,
            "normaliserId": CURRENT,
            "cleaned": plan["cleaned"],
            "chunkerId": CHUNKER_ID,
            "chunking": {"windowChars": window, "overlapChars": overlap},
            "spans": [{"start": a, "end": b} for a, b in spans],
            **({"mediaType": source["mediaType"]} if source.get("mediaType") else {}),
        }
        stored[INGEST_RECORD] = ingest
        store.put_corpus_record(analysis_id, doc_id, INGEST_RECORD, ingest)
    elif chunking is not None and ingest.get("chunking") != {
        "windowChars": window, "overlapChars": overlap,
    }:
        warnings.append(
            f"{name} was already chunked with {ingest.get('chunking')}; its spans were kept, "
            "because re-chunking a stored document would move every span into it."
        )

    if existing is None:
        rendition = {
            "id": doc_id,
            "originalLocator": source.get("uri") or _INLINE_LOCATOR,
            "originalSha256": plan["original"],
            "normaliserId": CURRENT,
            "content": content,
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
    else:
        kept = [f"{field} {source[key]!r}" for key, field in (("uri", "uri"), ("title", "title"))
                if source.get(key) and source[key] != existing.get(
                    "originalLocator" if key == "uri" else "label")]
        warnings.append(
            f"{name} is already in the corpus as {doc_id}; nothing was re-added"
            + (f", and its {' and '.join(kept)} were not recorded (the first add's are kept)."
               if kept else ".")
        )
    return {
        "documentId": doc_id,
        "added": existing is None,
        "cleaned": bool(ingest.get("cleaned", plan["cleaned"])),
        "agentProduced": MARKER_RECORD in stored,
        "spanCount": len(ingest.get("spans") or []),
        "tokenEstimate": _tokens(content),
    }


def _mark_by_content(
    store: AnalysisStore,
    analysis_id: str,
    plans: dict[str, dict[str, Any]],
    renditions: Mapping[str, Mapping[str, Any]],
    records: dict[str, dict[str, Any]],
    warnings: list[str],
) -> None:
    """Spread a marker across every document with the same normalised text, both ways.

    A trailing newline, or a re-ingest under a later normaliser, makes a new
    document of the same text; it must not make an unmarked one. So a text group
    is marked when any member is -- stored or in this call -- and every member
    gets the marker, including a document stored before its twin was marked.
    """
    groups: dict[str, set[str]] = {}
    for rid, rendition in renditions.items():
        if isinstance(rendition.get("content"), str):
            groups.setdefault(rendition["content"], set()).add(rid)
    for rid, plan in plans.items():
        groups.setdefault(plan["content"], set()).add(rid)
    for members in groups.values():
        marked = sorted(
            rid for rid in members
            if MARKER_RECORD in records.get(rid, {}) or plans.get(rid, {}).get("reasons")
        )
        if not marked:
            continue
        for rid in sorted(members - set(marked)):
            reason = f"its normalised text is that of {marked[0]}, which is marked"
            if rid in plans:
                plans[rid]["reasons"].append(reason)
            else:
                records.setdefault(rid, {})[MARKER_RECORD] = {"renditionId": rid, "reasons": [reason]}
                store.put_corpus_record(analysis_id, rid, MARKER_RECORD, records[rid][MARKER_RECORD])
                warnings.append(f"{rid}, already in the corpus, is now marked agent-produced: {reason}.")


def _usable(ingest: Any) -> bool:
    """Whether a stored ingest record can be read as spans; anything else is rebuilt."""
    if not isinstance(ingest, dict) or ingest.get("unreadable"):
        return False
    spans = ingest.get("spans")
    return isinstance(spans, list) and all(
        isinstance(sp, dict) and isinstance(sp.get("start"), int) and isinstance(sp.get("end"), int)
        for sp in spans
    )


#: scheme://host, then path, query and fragment. Parsed here rather than with
#: ``urllib``, which the determinism boundary keeps out of the tool layer.
_URI_PARTS = re.compile(r"\A([A-Za-z][\w+.-]*)://([^/?#]*)([^?#]*)(\?[^#]*)?(#.*)?\Z")


def _canonical_uri(value: str) -> str:
    """A uri as spellings of the same page agree on it.

    Folded away: the fragment, a trailing slash or ``?``, ``http`` against
    ``https``, the host's case, a leading ``www.``, and a default port.
    """
    parts = _URI_PARTS.match(value.strip())
    if not parts:
        return value.strip()
    scheme, host, path, query, _ = parts.groups()
    scheme = "https" if scheme.lower() in ("http", "https") else scheme.lower()
    host = re.sub(r":(80|443)\Z", "", host.lower())
    host = host[len("www."):] if host.startswith("www.") else host
    query = "" if query in (None, "?") else query
    return f"{scheme}://{host}{path.rstrip('/')}{query}"


def agent_produced_names(store: AnalysisStore, analysis_id: str) -> dict[str, str]:
    """The marked documents, by id and by canonical original uri, mapped to their id.

    A reference names a document by ``renditionId``, or by ``target``, which
    comparanda leaves opaque. :func:`cited_document` finds an id anywhere in
    either (``rendition:<id>#120-140`` names it as surely as the bare id), and a
    uri in any spelling :func:`_canonical_uri` folds together. A uri counts only
    while no unmarked document shares it, so a summary filed under its source's
    uri leaves the source citable -- at the price that adding an unmarked
    document under a marked one's uri makes that uri ambiguous, and it stops
    naming the marked one. Cheap when nothing is marked: markers are found by key.
    """
    marked = store.corpus_record_ids(analysis_id, MARKER_RECORD)
    if not marked:
        return {}
    names = {rid: rid for rid in marked}
    frame = store.frame(analysis_id)
    by_locator: dict[str, set[str]] = {}
    for r in [*frame.get("renditions", []), *store.renditions(analysis_id)]:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            continue
        names.setdefault(r["id"], "")  # known and unmarked: a renditionId naming it decides
        if isinstance(r.get("originalLocator"), str):
            by_locator.setdefault(_canonical_uri(r["originalLocator"]), set()).add(r["id"])
    for locator, ids in by_locator.items():
        if locator != _INLINE_LOCATOR and ids <= marked:
            names[_URI + locator] = min(ids)
    return names


#: Keys of :func:`agent_produced_names` that are canonical uris rather than ids.
_URI = "uri:"


def cited_document(ref: Mapping[str, Any], names: Mapping[str, str]) -> str | None:
    """The marked document ``ref`` names, or ``None``.

    A ``renditionId`` that names any document in the corpus decides alone: a
    reference into the unmarked original is not refused because its ``target``
    carries a uri a marked summary was filed under. Otherwise an id is matched
    anywhere in ``renditionId`` or ``target``, case-folded, with or without its
    ``doc-`` prefix (ids are 32 hex characters, so nothing contains one by
    accident), and then ``target`` as a uri in any spelling.
    """
    ids = sorted(key for key in names if not key.startswith(_URI))

    def named(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        folded = value.casefold()
        return next(
            (rid for rid in ids if rid.casefold() in folded
             or rid.casefold().removeprefix(_ID_PREFIX) in folded),
            None,
        )

    by_rendition = named(ref.get("renditionId"))
    if by_rendition is not None:
        return names[by_rendition] or None
    by_target = named(ref.get("target"))
    if by_target is not None:
        return names[by_target] or None
    target = ref.get("target")
    return names.get(_URI + _canonical_uri(target)) if isinstance(target, str) else None


def _cited_as_primary(store: AnalysisStore, analysis_id: str, marked: set[str]) -> list[str]:
    """Assertions already on record that cite a document this call has just marked, as primary."""
    if not marked:
        return []
    names = {k: (rid if rid in marked else "") for k, rid in agent_produced_names(store, analysis_id).items()}
    document, _ = store.read_skipping(analysis_id)
    cited: dict[str, list[str]] = {}
    for cell in document.get("cells", []):
        for assertion in cell.get("assertions", []):
            for ref in assertion.get("evidence") or []:
                hit = cited_document(ref, names) if isinstance(ref, dict) else None
                if hit and ref.get("sourceType") == "primary":
                    cited.setdefault(hit, []).append(
                        f"{cell.get('alternativeId')}/{cell.get('criterionId')}#{assertion.get('id')}")
    return [
        f"{rid} is now marked agent-produced, and {len(where)} assertion(s) written before the "
        f"marker cite it as primary ({', '.join(where)}). They were not changed; re-score them "
        "or record the evidence as secondary."
        for rid, where in sorted(cited.items())
    ]


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
