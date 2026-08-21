# ADR-0014: The evidence-reference locator profile, and deterministic citation checking

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0006 requires every evidence reference on a measure to point at a **span**, and says a citation
nobody can check is not a citation. It does not say what a span *is*. Without a locator format the
requirement is a slogan: two agents can both satisfy it and produce references that nothing can
compare, re-anchor, or verify.

The format choice decides three things at once. Whether a reference survives its document being
re-fetched, re-paginated, or re-extracted with a different PDF library. Whether it survives
**re-chunking**, which is the change most likely to happen in this system. And whether a tool with
no model access can check it — which ADR-0010 makes non-negotiable, because citation checking is the
whole of the Phase 1 evidence surface and the connector has no key.

The empirical case is not subtle. An audit of four deployed generative search engines found only
51.5% of generated sentences fully supported by their citations, and only 74.5% of citations
supporting the statement they were attached to [1]. One citation in four being wrong is worse than
no citations at all, because a well-formatted matrix certifies its own content.

## Decision

**Evidence references carry a narrowed W3C Web Annotation selector profile, stored as a flat array
of selectors that all select the same span.** A `TextQuoteSelector` is **mandatory** wherever a text
layer exists. **Positions are hints; quotes are truth.**

This is the specification's own intent rather than a compromise with it: the Web Annotation Data
Model recommends carrying State alongside a `TextPositionSelector` for robustness, and states that
multiple Selectors SHOULD select the same content [2]. Hypothesis stores three selectors per target
and runs several reattachment strategies in production [3].

**Adopted verbatim from W3C** [2]:

| Selector | Role |
|---|---|
| `TextQuoteSelector` | The truth. `prefix` / `exact` / `suffix` survives edits, re-pagination, re-extraction and re-chunking |
| `TextPositionSelector` | A **hint**, explicitly allowed to go stale. Never the sole locator |
| `FragmentSelector` + `conformsTo` | The sanctioned extension point, and the only one we use |

**Rejected for storage:** `CssSelector`, `XPathSelector`, `DataPositionSelector`, `RangeSelector`.
All four bind a reference to a DOM the producer never had; a corpus document is text, a PDF, or a
media file, not a live page.

**Adopted where W3C has no selector**, taking Hypothesis's de-facto extensions verbatim rather than
inventing our own [4]: `PageSelector` and `MediaTimeSelector`. `ShapeSelector` is deferred out of v1
— we have no image corpus yet, and an unused selector is a schema request we cannot justify.

`PageSelector` carries **both `index` and `label`**. They are different numbers and both are needed:
a journal PDF has label "iv" at index 3. Recording that here is cheaper than rediscovering it in a
bug report.

**Every typed selector has a documented lossless serialisation to a `FragmentSelector`**, reaching a
real fragment standard through `conformsTo` — RFC 5147 for character and line ranges, with its
integrity checks [5]; RFC 8118 for PDF [6]; Media Fragments for time and rectangles [7]. So a
reference can round-trip to a standard annotation and back. One trap to document rather than
discover: RFC 5147 line positions are the boundaries *between* lines, so `line=40,58` denotes lines
41–58 [5].

**Text Fragments (`#:~:text=`) are a rendering of the quote, not a competing locator.** The grammar
`prefix-,textStart,textEnd,-suffix` is isomorphic to `TextQuoteSelector{prefix, exact, suffix}` [8].
Store the selector; `comparanda`'s view layer derives the deep link at render time. One canonical
form, many renderings.

Where the connector runs inside Claude, the native Citations API is a first-class ingestion path
rather than a special case: it guarantees the pointers it returns are valid, and its `page_location`
and character ranges map onto this profile without loss [9].

### Chunking stays out of the citation path

Chunks are addresses into a document, never the target of a citation. Every chunk carries
`source_uri` and character offsets into the normalised full text; the model returns a **quote**; the
tool re-locates that quote in the **full** document. A chunk boundary then costs recall, never a
broken citation.

One corollary is load-bearing: contextual preambles are prepended to the *indexed* text only, never
to the document text that quotes resolve against. Otherwise the agent eventually cites its own
preamble as a primary source — ADR-0006's most damaging error class, arriving through the back door
of the retrieval layer.

Chunk overlap is not the mitigation it is assumed to be. The widely-copied 800-token/400-overlap
default scored below average on token-level recall and worst on every other metric in the most
systematic public evaluation [10]. It is not a reason to relax any of the above.

### The normalisation function is versioned

Normalisation is NFC, zero-width strip, typographic-variant and ligature folding, PDF line-break
hyphenation repair, and whitespace collapse. Changing it silently invalidates every stored
`quote_hash`, so it carries a version, the version is stored on the reference, and a bump is a
release-note event — the same treatment ADR-0010 gives the retrieval tokenizer and chunker.

### Citation checking is a deterministic eight-step ladder

`check_citations` runs these in order, and needs no model:

1. **Versioned normalisation** of both quote and document.
2. **Resolvability** — does the source URI resolve through the host resolver at all? This step alone
   catches hallucinated documents.
3. **Exact containment** — is the normalised quote a substring of the normalised document?
4. **Bounded approximate containment** — bit-parallel Myers search [11] with
   `max_errors = max(1, ceil(0.02 × len(quote)))`.
5. **Drift classification** — using the stored document and quote hashes, distinguish *verified*
   (document unchanged, quote found), *moved* (document changed, quote found — re-anchor and log),
   *stale* (document changed, quote gone — surface it), and *unresolvable*.
6. **Span-size sanity** — below ~40 characters a quote matches in too many places to be a locator;
   above ~1500 it is a document, not a span, and ADR-0006's objection to pointing at a 500-page PDF
   applies at every scale.
7. **Numeric-claim agreement** — every figure in the justification must match one in some cited
   span, after magnitude, percentage, separator and date normalisation. This is the highest-yield
   deterministic check we have, because justifications in a comparison matrix are dense with numbers.
8. **Polarity trap** — compare negation and hedge markers between justification and span, which
   catches the classic "cited source says the opposite" case for zero model calls.

The ladder returns a **graded verdict per reference** — `exact` / `normalised` / `fuzzy` / `moved` /
`stale` / `unresolvable` — plus a numeric-support rate and the unmatched claims. **The verdict field
is written by the tool and never by the model.** A model-written verdict is a self-assessment
wearing a checker's clothes.

The check is available at **cell granularity**, not only analysis-wide, so the connector can repair
a bad citation inside the scoring loop rather than learning about it afterwards.

Model-based citation judging is not abolished — it is confined to the evaluation harness, where
ADR-0010 permits it and ADR-0008 owns it.

### The thresholds are reasoning, not evidence

The 2% fuzzy-match error rate, the ~40 and ~1500 character span bounds: all three are starting
values chosen by argument, not measured. They are named parameters with defaults, and they are among
the first things the ADR-0008 evaluation suite tunes against the fixture corpus. The tuned values
get recorded by amendment to this ADR.

## Consequences
An evidence reference survives re-pagination, minor re-editing, a different PDF extractor, and a
re-chunk, and it can be checked offline inside the connector with no key. `comparanda` can render a
deep link without storing one. The evidence surface becomes the largest single schema request this
repository makes of the companion repo, and it is a self-contained typed module with round-trip
serialisation tests — which is the cheapest possible shape for that ask.

The costs are real and accepted. Several selectors per reference is more storage than a character
offset. The normalisation function must be versioned forever, and every version ever written has to
stay resolvable. And a `missing` with a reason becomes the *expected* outcome more often, because a
measure whose quote will not survive step 3 or step 4 should not be carrying `high` confidence — the
ladder makes ADR-0006's honesty posture enforceable rather than aspirational, which means it will
also make it visible.

## Alternatives considered
- *Character offsets alone.* Break on any re-fetch, and break **silently**, which is the worst kind
  of breakage. This is exactly the uncheckable citation ADR-0006 forbids.
- *Document-level citation.* Rejected by ADR-0006 outright.
- *Chunk ids as locators.* Makes every citation hostage to the chunker's version — and ADR-0010
  already treats the chunker as versioned, mutable surface.
- *Text Fragments as the stored format.* Isomorphic to `TextQuoteSelector` but tied to a browser
  URL grammar, and it cannot carry page, time, or position hints alongside.
- *A ninth rung: a lexical-overlap floor between justification and span.* Left out of the ladder.
  Lexical overlap is not a faithfulness measure, and a rung that returns a number nobody may act on
  invites exactly the misreading the graded verdict exists to prevent. It belongs in the harness, as
  a weak on-topic signal, if anywhere.
- *`ShapeSelector` in v1.* Deferred. No image corpus yet.

## Evidence
Question rows 21–24 and § 5 of [`docs/research/findings-method.md`](../research/findings-method.md);
the selector-by-selector adjudication, the serialisation table and the full ladder are in
[`docs/research/sections/r5-evidence-citation.md`](../research/sections/r5-evidence-citation.md).

1. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
2. [Web Annotation Data Model — Sanderson, Ciccarese & Young, W3C Recommendation (2017)](https://www.w3.org/TR/annotation-model/)
3. [Fuzzy Anchoring — Hypothesis (2013)](https://web.hypothes.is/blog/fuzzy-anchoring/)
4. [Hypothesis client — selector type definitions in `src/types/api.ts` (2024)](https://github.com/hypothesis/client/blob/main/src/types/api.ts)
5. [RFC 5147: URI Fragment Identifiers for the text/plain Media Type — Wilde & Duerst, IETF (2008)](https://www.rfc-editor.org/rfc/rfc5147.html)
6. [RFC 8118: The application/pdf Media Type — IETF (2017)](https://www.rfc-editor.org/rfc/rfc8118.html)
7. [Media Fragments URI 1.0 (basic) — W3C Recommendation (2012)](https://www.w3.org/TR/media-frags/)
8. [Text Fragments — WICG Draft Community Group Report (2023)](https://wicg.github.io/scroll-to-text-fragment/)
9. [Citations — Claude Platform documentation, Anthropic (2025)](https://platform.claude.com/docs/en/build-with-claude/citations)
10. [Evaluating Chunking Strategies for Retrieval — Chroma Research (2024)](https://www.trychroma.com/research/evaluating-chunking)
11. [approx-string-match-js: bit-parallel approximate string matching (Myers) — Knight](https://github.com/robertknight/approx-string-match-js)
