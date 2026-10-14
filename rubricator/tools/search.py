"""Tool 4, ``corpus_search``: spans found by lexical match, never by embedding.

ADR-0010 makes retrieval lexical so that it is reproducible byte for byte: an
embedding model is a model, which the connector has no key for, and a retriever
whose order moves between runs would show up in ADR-0008's stability check as a
prompt regression nobody made. Four things fix the order, and each is named:

- **the tokenizer and stopword list** (:mod:`rubricator.lexical`, ``lex-v1`` and
  ``stop-en-v1``, each pinned);
- **the chunker** (``chunk-v1``): a search reads the spans :func:`corpus_add`
  recorded and never re-chunks, so a span id found today names the same text
  tomorrow;
- **the score**: Okapi BM25 over spans with :data:`BM25_K1` and :data:`BM25_B`,
  collection statistics taken over the whole corpus so that narrowing
  ``document_ids`` never changes a span's score, plus a phrase bonus when the
  span holds the whole query as written (case, punctuation and compatibility
  forms folded). The bonus is BM25's own upper bound for the query, so a span
  holding the phrase always outranks one holding only its words. Scores are
  rounded to :data:`SCORE_DIGITS` places, so a tie is exact;
- **the tie-break**: ``(score descending, documentId, start)``.

**Retrieve small, present wide** (findings-method row 23). A hit is a stored
span, widened to ``window_chars`` of the document around it for reading;
``start`` and ``end`` are the offsets of the text returned, into the normalised
document every quote resolves against, and ``spanId`` names the span itself.

**An empty query reads the whole corpus** when it is under
:data:`INLINE_THRESHOLD_TOKENS` (estimated at four characters a token), and is
refused above it with the threshold and the size. That is the one documented
behaviour ADR-0010 asks for, so whether to inline is never a branch left to the
model's judgement.

**Finding nothing is never silent.** No match is an empty list whose summary says
what was searched; an empty corpus, an unknown document id and a query with
nothing to match are refused, because an empty list there would read as "looked
and found nothing" when nothing was looked at.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from rubricator.lexical import (
    STOPWORDS_ID,
    TOKENIZER_ID,
    UNICODE_VERSION,
    contains_phrase,
    terms,
    tokens,
)
from rubricator.store import AnalysisStore
from rubricator.tools.corpus import CHARS_PER_TOKEN, CHUNKER_ID, INGEST_RECORD, MARKER_RECORD
from rubricator.tools.views import skipped_note

__all__ = [
    "BM25_K1",
    "BM25_B",
    "DEFAULT_K",
    "DEFAULT_WINDOW_CHARS",
    "INLINE_THRESHOLD_TOKENS",
    "SCORE_DIGITS",
    "corpus_search",
]

#: Okapi BM25's term-frequency saturation and length normalisation, at the
#: values the literature and every mainstream implementation default to. Named,
#: because changing either reorders hits.
BM25_K1 = 1.2
BM25_B = 0.75

#: Hits returned by default (findings-method row 4; r6's token discipline).
DEFAULT_K = 8

#: Characters of document returned around each span (findings-method row 4).
DEFAULT_WINDOW_CHARS = 600

#: The size under which an empty query inlines the corpus, in estimated tokens.
#: ADR-0010: a client ceiling (Claude Code truncates a tool result at 25,000
#: tokens by default), not a cost figure; above it, content would be lost silently.
INLINE_THRESHOLD_TOKENS = 25_000

#: Decimal places a score is rounded to, so equal scores are exactly equal and
#: the tie-break, not float noise, decides their order.
SCORE_DIGITS = 6


def _refuse(message: str) -> ValueError:
    return ValueError(f"refused, nothing was searched: {message}")


def _estimate(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _spans(record: Any, content: str) -> list[tuple[int, int]] | None:
    """A document's stored spans, or ``None`` when its ingest record cannot be read as spans."""
    if not isinstance(record, Mapping) or record.get("unreadable"):
        return None
    spans = record.get("spans")
    if not isinstance(spans, list):
        return None
    out = []
    for span in spans:
        start = span.get("start") if isinstance(span, Mapping) else None
        end = span.get("end") if isinstance(span, Mapping) else None
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(content)):
            return None
        out.append((start, end))
    return out


def _widened(start: int, end: int, *, window: int, length: int) -> tuple[int, int]:
    """``[start, end)`` grown evenly to ``window`` characters inside ``[0, length)``, never cut."""
    width = max(window, end - start)
    left = max(0, start - (width - (end - start)) // 2)
    right = min(length, left + width)
    return max(0, right - width), right


def corpus_search(
    store: AnalysisStore,
    *,
    analysis_id: str,
    query: str,
    k: int = DEFAULT_K,
    document_ids: Sequence[str] | None = None,
    must_include: Sequence[str] = (),
    window_chars: int = DEFAULT_WINDOW_CHARS,
) -> dict[str, Any]:
    """Find spans in the corpus by lexical match: BM25 plus the whole query as a phrase.

    Stages 2, 3 and 5 of ADR-0005. Deterministic: a pinned tokenizer and stopword
    list over spans a versioned chunker recorded, with the tie-break ``(score,
    documentId, start)``; nothing is fetched and nothing is written.
    ``must_include`` keeps only spans holding every one of its phrases.
    """
    # JSON Schema's integer admits 2.0; a slice does not (review of #226).
    k, window_chars = (int(v) if isinstance(v, float) and v.is_integer() else v
                       for v in (k, window_chars))
    for name, value in (("k", k), ("window_chars", window_chars)):
        if value < 1:
            raise _refuse(f"{name} must be at least 1; it was {value}.")
    required = list(must_include)
    for phrase in required:
        if not tokens(phrase):
            raise _refuse(
                f'must_include entry "{phrase}" has no letters or digits to match, so no span '
                "could hold it."
            )

    document, skipped = store.read_skipping(analysis_id)
    contents = {
        r["id"]: r["content"]
        for r in document.get("renditions", [])
        if isinstance(r, Mapping) and isinstance(r.get("id"), str) and isinstance(r.get("content"), str)
    }
    if not contents:
        raise _refuse(
            f'the corpus of analysis "{analysis_id}" holds no documents. Add them with corpus_add '
            "first."
        )
    records = store.corpus_records(analysis_id)
    marked = {rid for rid in contents if MARKER_RECORD in records.get(rid, {})}
    chosen = sorted(contents)
    if document_ids is not None and not document_ids:
        raise _refuse(
            "document_ids is empty, which would search nothing. Omit it to search the whole corpus."
        )
    if document_ids is not None:
        unknown = sorted(set(document_ids) - set(contents))
        if unknown:
            raise KeyError(
                f"no document {', '.join(unknown)} in the corpus of analysis \"{analysis_id}\". "
                f"It holds: {', '.join(sorted(contents))}."
            )
        chosen = sorted(set(document_ids))

    base = {"analysisId": analysis_id, "query": query, "skipped": skipped}
    if not query.strip():
        inline = _inline(contents, chosen, marked, required, corpus_size=len(contents))
        return {**base, **inline, "warnings": [], "summary": inline["summary"] + skipped_note(skipped)}
    if not tokens(query):
        raise _refuse(
            f'the query "{query}" has no letters or digits to match. Pass words to search for, or '
            "an empty query to read the whole corpus while it is small enough to inline."
        )

    warnings: list[str] = []
    spans: list[tuple[str, int, int, list[str], str]] = []
    for rid in sorted(contents):
        found = _spans(records.get(rid, {}).get(INGEST_RECORD), contents[rid])
        if found is None:
            if rid in chosen:
                warnings.append(
                    f"{rid} has no readable spans (an imported or hand-made rendition, or a "
                    "damaged ingest record), so it was not searched. An empty query still inlines "
                    "its text; corpus_add of its original text adds it as a searchable document "
                    "under a content-derived id."
                )
            continue
        for start, end in found:
            text = contents[rid][start:end]
            spans.append((rid, start, end, terms(text), text))

    hits = _ranked(query, spans, chosen=set(chosen), required=required)
    searched = [s for s in spans if s[0] in set(chosen)]
    if not searched:
        # Nothing was looked at: an empty list here would read as "looked, found nothing".
        raise _refuse(
            f"no chosen document has readable spans ({', '.join(chosen)}), so nothing could be "
            "searched. An empty query inlines their text; corpus_add of the original text adds a "
            "searchable document."
        )
    shown = []
    for score, rid, start, end in hits[:k]:
        left, right = _widened(start, end, window=window_chars, length=len(contents[rid]))
        shown.append({
            "spanId": f"{rid}:{start}-{end}", "documentId": rid, "start": left, "end": right,
            "text": contents[rid][left:right], "score": score, "agentProduced": rid in marked,
        })
    n_docs = len({s[0] for s in searched})
    where = f"{len(searched)} span(s) in {n_docs} document(s)"
    if n_docs < len(contents):
        where += f" of the {len(contents)} in the corpus"
    if shown:
        summary = (
            f'{len(shown)} hit(s) of {len(hits)} matching "{query}" among {where}, ranked by BM25 '
            f"over {TOKENIZER_ID} (Unicode {UNICODE_VERSION}) terms less {STOPWORDS_ID}, the whole "
            "query as a phrase first, "
            f"ties by documentId then start; each widened to {window_chars} characters around its "
            f"{CHUNKER_ID} span"
        )
        agent = sum(1 for h in shown if h["agentProduced"])
        if agent:
            summary += (
                f"; {agent} hit(s) are in agent-produced documents, so a reference into them is "
                "secondary at best"
            )
    else:
        summary = (
            f'no span matched "{query}"'
            + (f" holding every must_include phrase ({'; '.join(required)})" if required else "")
            + f": searched {where} with {TOKENIZER_ID} (Unicode {UNICODE_VERSION}). Try other "
            "words; there is no stemming, so try other inflections"
        )
    if warnings:
        summary += f"; {len(warnings)} document(s) could not be searched (see warnings)"
    return {
        **base, "hits": shown, "inlined": False, "warnings": warnings,
        "summary": summary + skipped_note(skipped),
    }


def _ranked(
    query: str,
    spans: Sequence[tuple[str, int, int, list[str], str]],
    *,
    chosen: set[str],
    required: Sequence[str],
) -> list[tuple[float, str, int, int]]:
    """``(score, documentId, start, end)`` for every matching span, best first."""
    asked = sorted(set(terms(query)))
    n = len(spans)
    average = (sum(len(s[3]) for s in spans) / n) if n else 0.0
    idf = {}
    for term in asked:
        df = sum(1 for s in spans if term in s[3])
        idf[term] = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
    bonus = max(1.0, sum(idf[t] * (BM25_K1 + 1.0) for t in asked))

    ranked = []
    for rid, start, end, words, text in spans:
        if rid not in chosen:
            continue
        score = 0.0
        if asked:
            norm = BM25_K1 * (1.0 - BM25_B + BM25_B * (len(words) / average if average else 0.0))
            for term in asked:
                tf = words.count(term)
                if tf:
                    score += idf[term] * tf * (BM25_K1 + 1.0) / (tf + norm)
        if contains_phrase(text, query):
            score += bonus
        if score <= 0.0 or not all(contains_phrase(text, p) for p in required):
            continue
        ranked.append((round(score, SCORE_DIGITS), rid, start, end))
    ranked.sort(key=lambda h: (-h[0], h[1], h[2]))
    return ranked


def _inline(
    contents: Mapping[str, str], chosen: Sequence[str], marked: set[str], required: Sequence[str],
    *, corpus_size: int,
) -> dict[str, Any]:
    """The whole (chosen) corpus as hits, one per document, or the refusal ADR-0010 names.

    The summary says how many of the corpus's documents were inlined and why any
    were not, so a narrowed or filtered read never passes for the whole corpus.
    """
    kept = [rid for rid in chosen if all(contains_phrase(contents[rid], p) for p in required)]
    size = sum(_estimate(contents[rid]) for rid in kept)
    if size > INLINE_THRESHOLD_TOKENS:
        raise _refuse(
            f"an empty query returns the whole corpus, which is inlined only under "
            f"{INLINE_THRESHOLD_TOKENS:,} tokens (ADR-0010: past that a client truncates the "
            f"result) and is about {size:,} tokens here, estimated at {CHARS_PER_TOKEN} characters "
            "a token. Pass a non-empty query to retrieve spans, or narrow document_ids."
        )
    hits = [
        {"spanId": f"{rid}:0-{len(contents[rid])}", "documentId": rid, "start": 0,
         "end": len(contents[rid]), "text": contents[rid], "score": 0.0,
         "agentProduced": rid in marked}
        for rid in kept
    ]
    agent = sum(1 for h in hits if h["agentProduced"])
    if len(kept) == corpus_size:
        what = f"the whole corpus inlined, {len(hits)} document(s)"
    else:
        left_out = []
        if len(chosen) < corpus_size:
            left_out.append(f"{corpus_size - len(chosen)} not in document_ids")
        if len(kept) < len(chosen):
            left_out.append(f"{len(chosen) - len(kept)} without every must_include phrase "
                            f"({'; '.join(required)})")
        what = (f"{len(kept)} of the corpus's {corpus_size} document(s) inlined ("
                f"{', '.join(left_out)} left out)")
    return {
        "hits": hits, "inlined": True,
        "summary": (
            f"{what}, about {size:,} tokens, under the {INLINE_THRESHOLD_TOKENS:,}-token "
            "threshold; k does not apply to an empty query"
            + (f"; must_include matched with {TOKENIZER_ID} (Unicode {UNICODE_VERSION})"
               if required else "")
            + (f"; {agent} document(s) are agent-produced, so a reference into them is secondary "
               "at best" if agent else "")
        ),
    }
