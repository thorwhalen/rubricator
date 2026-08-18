# Span-level citation: locators, extraction, and verifying a citation supports its claim

**Research question(s):** Which locator format should a comparanda evidence reference use, and how
should it be typed? How should a corpus be chunked and retrieved when the output must be *cited*
rather than summarised? How do we verify that a cited span actually supports the justification it
is attached to — deterministically inside a tool, and with a model inside the evaluation suite?
What vocabulary distinguishes primary source, secondary summary, and the agent's own inference?

**Brief section:** `docs/research/method.md` §4 — Evidence extraction and citation. This is the
mechanism behind rubricator ADR-0006 and comparanda ADR-0014, and the "citation faithfulness" leg
of ADR-0008.

**Evidence grade:** strong — locator formats are settled by primary specifications (W3C, IETF,
WICG) and there is a large, directly-applicable primary literature on attribution metrics with
concrete numbers. Moderate on chunking, where the useful results are industry evaluations rather
than peer-reviewed work.

---

## Bottom line

Adopt a **narrowed profile of W3C Web Annotation selectors, stored as an array, with a
TextQuoteSelector mandatory in every array**. The quote is the locator; character offsets, page
numbers, line numbers and timestamps are *hints* that make resolution fast and are allowed to go
stale. This is not a compromise — it is what Hypothesis does in production and what the W3C model
recommends [1][2]. Invent nothing: where W3C has no selector (pages, media time, rectangles) adopt
Hypothesis's de-facto extensions verbatim [3]; where a real fragment standard exists (RFC 5147 for
line ranges, Media Fragments for time, RFC 8118 for PDF) reach it through `FragmentSelector` +
`conformsTo`, which is precisely the extension point W3C provides [1][7][8][9].

Do not store a `#:~:text=` URL as the primary locator. Text Fragments are isomorphic to a
TextQuoteSelector and now reach ~93% of browsers [5][6], so **derive** the deep link from the
selector at render time. One canonical form, many renderings.

Chunking is a **retrieval** concern and must be kept out of the **citation** path entirely. Every
chunk carries a character offset back into the source document; the model quotes text; the
deterministic tool re-locates that quote in the *full* document, never in the chunk. Do that and a
chunk boundary cutting through the evidence costs you recall, never a broken citation.

Citation checking splits in two, exactly as ADR-0003 demands. The **tool** is a deterministic
ladder — normalise, exact containment, bounded-edit-distance containment, drift classification,
span-size sanity, numeric-claim agreement, polarity trap — and returns a graded verdict, never a
model call. The **judge** is evaluation-only: decompose the justification into atomic claims and
run a small entailment model per (claim, cited span) pair. A 100M–770M parameter checker reaches
GPT-4-level accuracy on grounding at a tiny fraction of the cost [20][22], so this is cheap enough
to run on every prompt change.

For source typing, take the library-science trichotomy, anchor it on `prov:hadPrimarySource`, and
add the member the trichotomy lacks: `agent-inference` [28][33]. Then add the schema rule that
actually prevents ADR-0006's most damaging error: **an evidence reference whose target was produced
by an agent run must carry `derived_from` pointing at an upstream reference; if it cannot, it is
not evidence and belongs in the justification field.** The enum alone will not save you; the
constraint will.

---

## Findings

### 1. Locator formats

#### 1.1 What the W3C model actually gives us, and what to take

comparanda ADR-0014 names W3C Web Annotation selectors as "the obvious candidate". Evaluated
properly, the model is right but too large: it is a general annotation interchange format for
live DOMs, and rubricator works on *extracted text*, not on a rendered page. The correct move is a
profile — a documented subset — not wholesale adoption.

EVIDENCE. The Web Annotation Data Model defines eight selectors [1]:

| Selector | Required fields | Verdict for comparanda | Why |
|---|---|---|---|
| `TextQuoteSelector` | `exact`; `prefix`, `suffix` recommended | **Adopt, mandatory** | The only selector that survives document editing. Carries its own excerpt, which ADR-0014 wants embedded for the offline bundle anyway. |
| `TextPositionSelector` | `start`, `end` (0-indexed, end exclusive) | **Adopt as a hint** | Fast exact resolution; brittle. The spec itself says a State is *recommended* alongside it. |
| `FragmentSelector` | `value`; `conformsTo` recommended | **Adopt as the extension point** | The sanctioned way to carry RFC 5147 line ranges, Media Fragments times, RFC 8118 PDF fragments without inventing anything. |
| `RangeSelector` | `startSelector`, `endSelector` | **Reject for storage** | Composes DOM-bound selectors; meaningless over extracted text. Accept as pass-through if a host app supplies one. |
| `CssSelector` | `value` | **Reject** | Requires a live DOM the agent never sees. Breaks on any re-render. |
| `XPathSelector` | `value` | **Reject** | Same, worse: HTML5 parser-inserted elements shift paths [1]. |
| `SvgSelector` | `value` (SVG shape) | **Defer** | Only needed for figure/scan evidence. Prefer a rectangle first. |
| `DataPositionSelector` | `start`, `end` (bytes) | **Reject** | Byte offsets over an encoded stream are the most fragile locator available. |

EVIDENCE. Two normative points from the spec matter enormously here. First, on
`TextPositionSelector`: "it is *RECOMMENDED* that a State be additionally used" for robustness
against content change [1]. Second, on plurality: "Multiple Selectors *SHOULD* select the same
content, however some Selectors will not have the same precision as others" [1]. The spec's own
design assumes several selectors travel together. Storing exactly one is using the model wrong.

EVIDENCE. `refinedBy` composes selectors — for example a `TextQuoteSelector` refining a
`FragmentSelector` that identifies a paragraph — and "If more than 1 is given, then they are
considered to be alternatives that will result in the same selection" [1]. REASONING (not
evidence): `refinedBy` nesting buys us nothing that a flat array does not, and it costs every
consumer a recursive walk. Flatten. A flat `selectors: Selector[]` array with the documented
invariant "all members select the same span" expresses the same thing and validates in one pass.

#### 1.2 The robustness problem, and what production systems do

EVIDENCE. Hypothesis stores **three** selectors per target and tries **four** reattachment
strategies in order [2]:

1. `RangeSelector` — apply the stored XPaths, verify the matched text against the saved quote;
2. `TextPositionSelector` — global character offsets, for when structure moved but text did not;
3. context-first fuzzy match — fuzzy-search for the `prefix` near the expected position, then the
   `suffix` near the expected end, and compare the intervening text to `exact`;
4. quote-only fuzzy match — last resort, fuzzy-search `exact` across the whole document.

The matcher is "a modified version of the google-diff-match-patch library, which uses the Bitap
matching algorithm" [2]. (The blog post states matching succeeds "if the difference is within a
given acceptance threshold" but does **not** state the threshold — a widely repeated "5% Levenshtein
tolerance" figure is *(UNVERIFIED — could not locate in the primary source)*. Set our own; see §4.)
Hypothesis's current client uses a bit-parallel Myers algorithm running in O((k/w)·n) with an API
of `search(text, pattern, maxErrors) -> {start, end, errors}[]` [31] — the shape our deterministic
tool should copy.

REASONING. The generalisable lesson: **positions are a cache, quotes are the truth.** A
TextPositionSelector breaks on any insertion earlier in the document; a TextQuoteSelector with
prefix and suffix survives edits, re-pagination, re-extraction with a different PDF library, and
whitespace churn — and, critically for us, survives *re-chunking*, which is the change most likely
to happen in this system.

#### 1.3 HTML — Text Fragments are a rendering of the quote, not a competing locator

EVIDENCE. The WICG Text Fragments spec defines `#:~:text=[prefix-,]textStart[,textEnd][,-suffix]`,
percent-encoded, with `&` joining multiple directives; each of prefix, start, end and suffix must
match "within a single block"; matching is case-insensitive and word-boundary aware; text
directives fire only on user-initiated, top-frame navigations, and a site can opt out with
`Document-Policy: force-load-at-top` [4][5]. It is a Draft Community Group Report, explicitly "not
a W3C Standard nor is it on the W3C Standards Track" [4] — but support is real: Chrome 81+, Edge
83+, Safari 16.1+, Firefox 131+, ~93.4% global usage [6].

REASONING. Look at the grammar: `prefix-,textStart,textEnd,-suffix` is *exactly*
`TextQuoteSelector{prefix, exact, suffix}` with an optional range split. This is not a second
locator format to choose between; it is a serialisation of the one we already store. Therefore:
store the selector, and generate the `#:~:text=` URL in `comparanda`'s view layer when the source
is web-reachable HTML. That keeps the data model medium-neutral and gets genuinely deep-linkable
citations for free. Note the block-boundary rule when generating: a quote spanning a paragraph
break must be emitted as `textStart,textEnd` (first and last few words), not as one long string.

#### 1.4 PDF — a standard exists, viewers ignore most of it

EVIDENCE. RFC 8118 standardises PDF fragment identifiers and notes they are "now included in ISO
32000-2": `page=<pageNum>`, `nameddest=`, `structelem=`, `comment=`, `zoom=`, `view=`,
`viewrect=<left,top,width,height>`, `highlight=<left,right,top,bottom>`, `search=<wordList>` [7].

EVIDENCE. What products actually store is narrower. Hypothesis's client models PDF targets with
`PageSelector {index /* 0-based */, label? /* printed label */}` plus a `TextQuoteSelector`, and
adds `ShapeSelector {shape, anchor?: 'page', view?, text?}` for region annotations, documenting
that "PDF user space coordinates (points)" have their origin at bottom-left while image coordinates
have it at top-left [3]. Anthropic's Citations API returns `page_location` with
`start_page_number` (1-indexed) and `end_page_number` (exclusive) plus `cited_text` — it does not
return rectangles at all, and states that "citing images from PDFs is not currently supported" [10].

REASONING and a warning that will bite an implementer: **`PageSelector.index` and
`PageSelector.label` are different numbers and both are needed.** A journal PDF with front matter
has page label "iv" at index 3 and page label "1" at index 12. The index resolves the file; the
label is what a human types. Storing one is a bug. Note also the off-by-one trap across sources:
W3C/Hypothesis page indices are 0-based, Anthropic page numbers are 1-based and end-exclusive [1][3][10].
Normalise on ingest and record which convention you normalised *from*.

Recommendation: store `PageSelector` + `TextQuoteSelector` as the pair; add `ShapeSelector` only
for evidence in a figure, table image or scan where no text layer exists; emit `#page=N` (and
optionally `&search=` for viewers that honour it) as a *derived* link. Do not attempt
`highlight=` — its coordinate space is Acrobat-specific and no browser viewer honours it.

#### 1.5 Code — the drift is real and RFC 5147 already solved it

EVIDENCE. RFC 5147 defines fragment identifiers for `text/plain` with two schemes, `char=` and
`line=`, each accepting a position or a comma-separated range — and, decisively for us, two
optional **integrity checks** appended with a semicolon: `length=<number>[,<charset>]` and
`md5=<32 hex digits>[,<charset>]`. Its own example is
`ftp://example.com/text.txt#line=10,20;length=9876,UTF-8` [8].

REASONING. This is a twenty-year-old IETF answer to "line numbers drift — should we store a
content hash?" The answer is yes, and there is a standard syntax for it. But we can do better than
a hash alone for code, because code lives in a content-addressed store: **put the commit SHA in the
source reference and the line range stops drifting altogether.** A GitHub permalink at a commit SHA
with `#L41-L58` is an exact, permanent locator. So for code sources:

- `SourceRef.revision` = the commit SHA (or an ETag / version string for non-git sources);
- `FragmentSelector { conformsTo: "https://www.rfc-editor.org/rfc/rfc5147", value: "line=40,58" }`
  (RFC 5147 line positions are the *boundaries between* lines, so `line=40,58` denotes lines 41–58 [8]
  — document this, it is the single most likely off-by-one in the whole schema);
- `TextQuoteSelector` with the first and last lines as `exact`, so the span re-anchors if the file
  moved and the revision was not recorded;
- `quote_hash` = SHA-256 of the normalised span (we use SHA-256, not RFC 5147's MD5; same idea,
  a hash function that has not been broken).

#### 1.6 Audio, video, images

EVIDENCE. Media Fragments URI 1.0 is a **W3C Recommendation** (2012) defining a temporal dimension
`t=` in Normal Play Time (`t=10,20`, `t=,20`, `t=0:02:00,121.5`) with a half-open interval — "the
begin time is considered part of the interval whereas the end time is considered to be the first
time point that is not part of the interval" — and a spatial dimension `xywh=160,120,320,240` or
`xywh=percent:25,25,50,50` [9]. The spec is candid about deployment: "there are only few media
types that actually have a specified fragment format" [9]. Hypothesis models this as
`MediaTimeSelector {start, end}` in seconds [3].

REASONING. Audio/video evidence is only *checkable* if a transcript exists, because our
deterministic checker compares text. Therefore: require, for time-based media, a
`MediaTimeSelector` **and** a `TextQuoteSelector` over the transcript, with the transcript itself
registered as its own source (source type `secondary`, derived from the recording). A citation to
`t=372,391` with no quote is a citation nobody can check, which ADR-0006 says is not a citation.

For images and scans, `FragmentSelector` with `conformsTo` the Media Fragments spec and
`value: "xywh=..."` is the standards-compliant rectangle, and is what IIIF-adjacent tooling
expects. Prefer it over `SvgSelector` until a non-rectangular region is genuinely needed.

---

### 2. Extraction: chunking and retrieval for a corpus that must be cited

#### 2.1 The specific failure, and the metric that exposes it

EVIDENCE. Chroma's evaluation of chunking strategies is the most directly relevant study, because
it measures retrieval at **token** granularity against ground-truth excerpt spans rather than at
document granularity. It defines, over the tokens of the relevant excerpts `t_e` and the tokens
retrieved `t_r`: `Precision = |t_e ∩ t_r| / |t_r|`, `Recall = |t_e ∩ t_r| / |t_e|`, and an IoU
[25]. Token-level recall below 1.0 *is* the "chunk boundary cut the evidence in half" failure,
measured. Their comparison covers `RecursiveCharacterTextSplitter`, `TokenTextSplitter`, and
embedding/LLM-driven semantic chunkers at 200/250/300/400/800-token sizes with overlaps of 0, 125
and 400; the headline is that OpenAI's documented default of 800-token chunks with 400-token overlap
"results in slightly below-average recall and the lowest scores across all other metrics", that
smaller chunks did better on precision and IoU, and that reducing overlap *improved* IoU because
redundant tokens are penalised — overlap was not the win it is assumed to be [25]. Token-level
precision is low in absolute terms for every strategy, because every chunk drags in irrelevant
tokens.

EVIDENCE. Semantic chunking does not rescue this. A systematic evaluation across document
retrieval, evidence retrieval and retrieval-based answer generation concludes that "the
computational costs associated with semantic chunking are not justified by consistent performance
gains" [26].

EVIDENCE. The other half of the chunking problem is *context loss*, not boundary loss: a chunk
reading "revenue grew by 3% over the previous quarter" names neither the company nor the quarter.
Anthropic's Contextual Retrieval prepends a 50–100 token Claude-generated situating preamble to
each chunk before both embedding and BM25 indexing, and reports retrieval-failure reductions of
35% (contextual embeddings), 49% (plus contextual BM25) and 67% (plus reranking), at a one-time
cost of "$1.02 per million document tokens" with prompt caching [23]. Late Chunking attacks the
same problem without a generation step: embed the whole document with a long-context model, then
pool token embeddings per chunk, so each chunk embedding carries document context, with no
additional training required [24].

#### 2.2 The design that makes chunking irrelevant to citation correctness

REASONING (this is the load-bearing recommendation of §2). Both failures above are *retrieval*
failures. They must never become *citation* failures, and there is a clean way to guarantee that:

> **Decouple the retrieval unit from the citation unit. Chunks are addresses into a document, not
> copies of it. Citations always resolve against the full original text.**

Concretely, four rules:

1. **Every chunk carries `source_uri` and its `char_start`/`char_end` in the normalised full
   document text.** A chunk that has lost its offset can never produce a checkable citation. This
   is the single most important implementation detail in the extraction layer, and it is one line
   of bookkeeping in the splitter.
2. **Retrieve small, present wide.** Index at roughly 200 tokens per [25], then expand the
   retrieved unit to a surrounding window (its neighbours, or its parent section) before handing it
   to the model. Small units maximise retrieval precision; the window restores the context the
   model needs to judge, and — importantly — lets the model quote text that straddles a chunk
   boundary, because the boundary is no longer in front of it.
3. **The model returns a quote; the tool relocates it in the full document.** A fuzzy search over
   the whole normalised document text (§4) turns any quote the model produces into a
   `TextPositionSelector`, whatever chunk it came from. Boundary damage costs recall — the model
   never saw the evidence — never a mislocated citation.
4. **Contextualise the index, not the corpus.** Prepend contextual preambles to the *embedded*
   text only [23]. Never let a generated preamble enter the document text that quotes resolve
   against, or the agent will eventually cite its own preamble as a primary source. This is
   ADR-0006's damaging error class arriving through the back door of the retrieval layer, and it is
   the reason rule 4 exists.

REASONING on cost. Contextual Retrieval's preamble generation needs a model. Under ADR-0003 that
cannot live inside an MCP tool. Fine: it belongs in an *offline corpus-preparation* step run by
the deployed agent or by a CLI command, whose output is a static index the connector reads. Late
Chunking [24] is the model-free alternative and should be the default for the connector path,
because it needs an embedding pass and no generation.

#### 2.3 In the connector runtime, prefer the Citations API to reimplementing it

EVIDENCE. When rubricator runs as a connector inside Claude, span-level citation is already
available natively. The Citations API chunks plain text and PDFs into sentences, and returns
`char_location {cited_text, document_index, document_title, start_char_index /* 0-indexed */,
end_char_index /* exclusive */}`, `page_location {start_page_number /* 1-indexed */,
end_page_number /* exclusive */}`, or `content_block_location {start_block_index, end_block_index}`
for custom content [10]. The documentation states that "because the API parses citations into the
response formats described in the following sections and extracts `cited_text` directly, citations
are guaranteed to contain valid pointers to the provided documents" [10].

REASONING. That guarantee is exactly the property our deterministic checker exists to verify. Where
it holds, our checker becomes a cheap confirmation rather than the primary defence. Recommendation:
`char_location` → `{TextPositionSelector{start,end}, TextQuoteSelector{exact: cited_text}}`;
`page_location` → `{PageSelector{index: start_page_number - 1, label: str(start_page_number)},
TextQuoteSelector{exact: cited_text}}`. Write a documented adapter and treat it as a first-class
ingestion path, not a special case. Note the API's own guidance that RAG chunks should be passed as
*separate plain-text documents* if you want sentence-level citations within them [10] — which is
the same "retrieve small, cite precisely" shape as rule 2 above.

---

### 3. Verifying that a citation supports its claim

#### 3.1 The frame: attribution, not truth

EVIDENCE. The AIS framework — Attributable to Identified Sources — establishes the right question.
It evaluates whether generated statements are "supported by underlying sources" rather than judged
against absolute factual truth, via a two-stage annotation pipeline (interpretability of the
statement, then attribution to the source) [13].

REASONING. This is precisely rubricator's contract and it should be said explicitly in the prompts:
the agent is not asserting that a score is *true*, it is asserting that a score is *supported by
this span*. A checker cannot verify truth and should never claim to. Every metric below measures
support.

#### 3.2 How bad is this failure mode, really

EVIDENCE. Liu, Zhang and Liang audited four generative search engines and found that only **51.5%
of generated sentences are fully supported by their associated citations**, and only **74.5% of
citations actually support their paired statement** [12]. They characterise the systems as offering
a "facade of trustworthiness".

REASONING. A 74.5% per-citation support rate is the base rate rubricator must beat, and it is the
empirical justification for ADR-0008 treating citation faithfulness as the single most damaging
failure mode. One in four citations wrong, in a well-formatted matrix, is worse than no citations,
because the format certifies the content.

#### 3.3 The metrics, and the exact definitions to copy

EVIDENCE. ALCE gives the definitions to adopt wholesale [11]. For a statement with citation set
{c₁…c_n}, the cited passages are **concatenated with newlines** and fed to an NLI model as premise,
with the statement as hypothesis:

- **Citation recall** is binary per statement: 1 if the statement has at least one citation and the
  NLI model says the concatenated citations entail it.
- **Citation precision** is binary per citation: 1 if the statement's recall is 1 *and* the citation
  is not irrelevant. A citation is **irrelevant** when both (a) the NLI model returns 0 for that
  citation alone entailing the statement, and (b) removing it does not stop the remaining citations
  from entailing the statement.

The NLI model is **TRUE**: a T5-11B fine-tuned on SNLI, MNLI, FEVER, SciTail, PAWS and VitaminC
[11][16]. Reported agreement between the *automatic metric and human annotation* (not between two
human annotators): Cohen's κ = 0.698 for citation recall — "substantial agreement" — and 0.525 for
citation precision — "moderate agreement" — with the automatic metric matching human labels 85.1%
of the time for recall and 77.6% for precision [11].

EVIDENCE. Complementary framings worth knowing:

- **AttrScore** replaces binary entailment with three labels — *attributable*, *extrapolatory*,
  *contradictory* — trained by repurposing QA, fact-checking, NLI and summarisation data, and
  tested on manually curated examples across 12 domains from a generative search engine [14].
- **AttributionBench** aggregates existing attribution datasets into a binary classification
  benchmark and finds that even a fine-tuned GPT-3.5 reaches only **~80% macro-F1**, with errors
  traced to "the model's inability to process nuanced information" and to a mismatch between what
  the model and the human annotator could see [15].
- **TRUE** standardises 11 annotated datasets and concludes that "large-scale NLI and question
  generation-and-answering-based approaches achieve strong and complementary results" [16].
- **HAGRID** is a human–LLM collaborative attribution dataset built over MIRACL, with human
  annotation on informativeness and attributability, intended as training/eval material for
  attributed information-seeking models [17].
- **RAGAS** computes reference-free **faithfulness** as (number of supported claims) / (total
  claims): decompose the response into statements, then verify each against the retrieved context
  [18][19]. Its `FaithfulnessWithHHEM` variant swaps the LLM verifier for Vectara's HHEM-2.1-Open
  classifier [19].
- **LongCite** shows the granularity direction of travel: sentence-level citations in long-context
  QA, with a LongBench-Cite benchmark and models trained on CoF-generated data that surpass
  proprietary frontier models on citation quality [27].
- A 2023 survey of LLM attribution notes the field "is still in its early stages" and names "the
  drawbacks of excessive attribution" — over-citing, not merely under-citing — among the issues
  that hinder attributed systems [32].

REASONING. AttributionBench's ~80% ceiling [15] is the number to keep in mind when designing the
suite: **the judge is a regression detector, not an oracle.** Track deltas between prompt versions,
not absolute grades, and never gate a release on a judge score alone without a deterministic check
underneath it.

#### 3.4 What is cheap enough for a test suite

EVIDENCE. Small dedicated checkers now match frontier models on this task:

| Model | Size | Base | Claim |
|---|---|---|---|
| HHEM-2.1-Open [22] | 100M | flan-t5-base | Apache-2.0; premise/hypothesis → consistency probability; <600MB RAM, ~1.5s per 2k-token input; 74.28% balanced accuracy on RAGTruth-QA vs GPT-4's 74.11% and GPT-3.5's 56.16% |
| AlignScore [21] | 355M | RoBERTa-scale | Unified alignment function trained on 4.7M examples across 7 tasks; "matches or even outperforms metrics based on ChatGPT and GPT-4 that are orders of magnitude larger" over 22 datasets |
| MiniCheck-FT5 [20] | 770M | Flan-T5 | "GPT-4-level performance but for 400x lower cost" on the LLM-AggreFact benchmark |
| TRUE [11][16] | 11B | T5 | The ALCE reference implementation; reproduces published numbers exactly |

REASONING. Recommended ladder, by evaluation tier:

- **Every commit / every prompt edit (CI):** deterministic ladder only (§3.5) — no model, no
  network, milliseconds. This is the gate.
- **Nightly / pre-merge:** HHEM-2.1-Open or AlignScore over the fixture set. Runs on CPU, no API
  key, so it works in a public repo's CI without secrets — which matters given ADR-0002's
  public-repository constraint.
- **Release gate / prompt-family changes:** MiniCheck-FT5, or a frontier LLM judge with the ALCE
  protocol, on the full fixture corpus. Report against the previous release, not against 1.0.

Reproducing ALCE exactly (TRUE / T5-11B) is the wrong trade for a project this size; use it once to
calibrate the small checker against published numbers, then run the small checker.

#### 3.5 The deterministic checks — what a tool can do with no model at all

ADR-0003 forbids a tool from calling a model, so the citation-checking *tool* must be entirely
deterministic. This is a constraint, not a limitation: most real citation failures are mechanical,
and a deterministic ladder catches them faster and more reliably than a judge would.

REASONING throughout this subsection; the individual techniques are standard, the assembly is ours.

**Step 0 — normalisation.** Everything downstream depends on this being pinned and versioned. In
order:

1. Unicode NFC.
2. Strip zero-width and formatting characters: U+00AD soft hyphen, U+200B–U+200D, U+FEFF.
3. Fold typographic variants: curly quotes and apostrophes → ASCII, en/em dash → hyphen-minus,
   ellipsis character → three dots, non-breaking space → space.
4. Fold ligatures (ﬁ ﬂ ﬀ …) — PDF text extraction emits these constantly.
5. Repair PDF line-break hyphenation: `-\n` between two lowercase letters → join.
6. Collapse all whitespace runs to a single space; trim.

Case is **not** folded for the stored quote and **is** folded only at the approximate-match tier.
The normalisation function is versioned (`checker_version`), because changing it silently
invalidates every stored `quote_hash`.

**Step 1 — resolvability.** Does `SourceRef.uri` resolve through the host resolver at all? If not,
verdict `unresolvable`. This alone catches hallucinated documents.

**Step 2 — exact containment.** Is `normalise(quote)` a substring of `normalise(document)`? Verdict
`exact` if it is found at the position the `TextPositionSelector` claims; `normalised` if found
anywhere and the raw form differed; `moved` if found at a different position than claimed.

**Step 3 — approximate containment.** If step 2 fails, run bounded approximate search — Myers
bit-parallel or an equivalent Levenshtein-window search [31] — with
`max_errors = max(1, ceil(0.02 * len(normalised_quote)))`. On a hit, verdict `fuzzy` with
`edit_distance` recorded; the view should show "quote differs from source" rather than a clean
tick. On a miss, verdict `stale`. (2% is a starting threshold, not a finding — tune it on the
fixture corpus and record the tuned value in the ADR.)

**Step 4 — drift classification.** With `SourceRef.document_hash` and `quote_hash` stored, the four
outcomes are distinguishable and each deserves different UI: document unchanged + quote found =
verified; document changed + quote found = `moved` (re-anchor silently, log); document changed +
quote not found = `stale` (surface it, per ADR-0014's "a reference can go stale, and staleness is
surfaced"); document unreachable = `unresolvable`.

**Step 5 — span-size sanity.** Reject or flag spans outside a configured band. Below ~40 characters
or ~6 content words, a quote matches in too many places to be a locator. Above ~1500 characters,
it is a document, not a span, and ADR-0006 says pointing at a 500-page PDF is not evidence — the
same argument applies at every scale. This is the token-precision insight from [25] applied to
citation rather than retrieval: the more irrelevant tokens inside the span, the weaker the
citation, even when it technically contains the evidence.

**Step 6 — numeric-claim agreement.** This is the highest-yield deterministic check for a
comparison matrix, because justifications in this domain are dense with numbers. Extract from the
justification every number, percentage, currency amount, date and duration, with its unit; extract
the same from the union of cited spans; require every numeric claim in the justification to have a
match in some cited span, after normalising magnitude (`1.2M` ≡ `1,200,000`), percentage form
(`12%` ≡ `0.12` where a ratio is in play), thousands separators, and date format. An unmatched
number is a hard flag: the model invented or transformed a figure. Report
`numeric_support_rate` per analysis.

**Step 7 — lexical overlap floor.** Content-word Jaccard, or ROUGE-style precision, between the
justification and the union of cited spans, with stopwords removed. Use it **only** as a weak
"is this even on topic" signal with a low threshold. State plainly in the tool's docstring that
lexical overlap is not a faithfulness measure — a paraphrase scores low and a contradiction scores
high — so nobody later mistakes it for one.

**Step 8 — polarity trap.** Compare negation and hedge markers between the justification and the
span: `not`, `no`, `never`, `without`, `fails to`, `unable`, `declined`, `un-`/`in-` prefixed
antonym pairs, and hedges (`may`, `might`, `plans to`, `is expected to`, `pilot`). A span saying
"the library does **not** support incremental parsing" cited for a justification saying "supports
incremental parsing" is the classic contradiction case, and a token-level polarity mismatch flags
it for zero model calls. High recall, moderate precision — emit it as a `flag`, not a verdict.

#### 3.6 Citation precision and citation recall, kept separate — and the third thing

REASONING. Three distinct quantities get conflated, and the schema should keep all three apart.

**(a) Citation precision** — per evidence reference: does *this span* support the justification it
is attached to? Failure mode: a real span that says something adjacent but not the claim. Measured
by the ALCE irrelevance test [11]; approximated deterministically by steps 5–8.

**(b) Citation recall** — per justification: is *every part* of the justification supported by some
cited span? Failure mode: a two-clause justification with a citation for the first clause only.
Measured by ALCE recall over claim decomposition [11][18]; not deterministically checkable, because
detecting an *uncited* clause requires understanding the clause. This one genuinely needs the
eval-time judge.

**(c) Counter-evidence coverage** — per cell, over the *corpus*: does the corpus contain a span
that contradicts or materially qualifies the score, which the analysis did not cite? A citation can
be perfectly precise and the justification perfectly recalled, and the cell can still be wrong
because the agent cited the three sources that agreed and skipped the one that did not.

EVIDENCE. (c) is not what the attribution literature measures. Glockner, Hou and Gurevych show the
adjacent problem in fact-checking: they define two requirements evidence must meet for realistic
fact-checking — it must be "(1) sufficient to refute the claim and (2) not leaked from existing
fact-checking articles" — and find that every dataset they survey fails at least one, with models
trained on such data relying on "leaked evidence, which makes them unsuitable in real-world
scenarios" [30]. REASONING: no benchmark
I could locate measures omission of contradicting evidence in a decision-matrix setting
*(UNVERIFIED — could not locate a source; treat as a gap, not as a negative result)*.

REASONING — the recommendation, in two parts, one structural and one evaluative:

1. **Structural.** Give every evidence reference a `stance` field —
   `supports | contradicts | qualifies | background` — modelled on CiTO's citation-intent
   properties (`cito:citesAsEvidence`, `cito:confirms`, `cito:disagreesWith`, `cito:supports`)
   [29]. This makes "the agent found a contradicting span and cited it anyway" *representable*,
   which it currently is not, and it makes contradicting evidence countable in the view. A cell
   whose score is 4 and which carries a `contradicts` reference is the most interesting cell on the
   page, and comparanda's `uncertainty-suppressed` encoding (its ADR-0010) is the natural place to
   surface it.
2. **Evaluative.** Add an adversarial probe to ADR-0008's suite: for each scored cell, run
   retrieval a second time with a query built *against* the asserted direction, take the top-k
   spans, and ask the judge whether any contradicts the justification. Report
   `counter_evidence_missed@k`. This is not cheap — it is a second retrieval and k judge calls per
   cell — so run it at the release tier only, on a small fixture set. It is nonetheless the only
   test that catches confident cherry-picking, which is the failure a well-cited matrix is best at
   hiding.

---

### 4. Distinguishing primary source, secondary summary, and own inference

#### 4.1 There is an established vocabulary, in three places, and none of them is complete

EVIDENCE — library science. The primary/secondary distinction is standard: primary sources "are
most often produced around the time of the events you are studying [and] reflect what their creator
observed or believed about the event", while secondary sources "provide an interpretation of the
past based on primary sources" [33]. The same source makes the point that matters most for our
schema: classification is **relational to use** — a work can be secondary for one question and
primary for another [33].

EVIDENCE — W3C PROV. PROV-O gives formal properties with published definitions [28]:
`prov:hadPrimarySource` "cites a preceding Entity produced by some agent with direct experience and
knowledge about the topic (such as a reading from a sensor, or a journal written during an
historical event)"; `prov:wasQuotedFrom` "cites a potentially larger Entity … from which a new
Entity was created by repeating some or all of the original"; `prov:wasDerivedFrom` covers
"transformation of an entity into another, or construction based on pre-existing entity";
`prov:wasAttributedTo` is "ascribing an entity to an agent"; `prov:Agent` is "something that bears
some form of responsibility".

EVIDENCE — CiTO. The Citation Typing Ontology defines 41 sub-properties of `cito:cites` for
citation intent, including `citesAsEvidence` ("cites the cited entity as source of factual evidence
for statements it contains"), `citesAsSourceDocument`, `citesAsDataSource`, `confirms`,
`disagreesWith` and `supports` [29].

REASONING. Three consequences follow directly.

First, **source type belongs on the reference, not on the document.** Because classification is
relational [33], a `SourceRef` cannot carry `source_type`; the `EvidenceRef` must. The same PDF
cited once for what its authors measured (primary) and once for its literature review (secondary)
gets two different values, correctly.

Second, **PROV-O gives us the formal anchor but not the member we need.** `hadPrimarySource` and
`wasDerivedFrom` distinguish primary from derived, and `wasAttributedTo` handles authorship — which
comparanda ADR-0012 already covers with its "agents are identities too" rule. What no external
vocabulary supplies is a first-class value for *the agent's own inference*, because no external
vocabulary was designed for a producer that manufactures plausible-looking sources at scale.

Third, and most important: **the enum alone does not prevent the failure ADR-0006 names.** Agent
summaries get mistaken for primary authorship not because a field was set wrong but because a
derived artefact was allowed into the evidence slot with nothing pointing back to what it derived
from. The enum is a label; a label can be set to `primary` by a model that would rather have a
clean citation. What prevents it is a constraint.

#### 4.2 The recommended enum and the constraint that makes it work

```
source_type:
  primary        the thing itself — the source under discussion, the measurement, the
                 specification text, the commit, the recording, the transcript of the event
  secondary      someone else's account, analysis or summary of a primary source
  tertiary       a compilation or index of accounts — an encyclopaedia entry, an aggregator,
                 a "best of" listing
  agent-inference   asserted by this or another agent run; not a source at all, and marked so
  user-assertion    stated by the user in the conversation; unverified by construction
```

Five members, not three: the trichotomy is the established vocabulary [33] and we keep it verbatim,
plus the two members it never had to model because it predates machine authors.

**The constraint — this is the recommendation, not the enum:**

- `source_type: agent-inference` **requires** a non-empty `derived_from: EvidenceRefId[]`. An
  inference that cannot name what it was inferred from is not evidence; it is a justification, and
  the schema should reject it in the evidence array. This is `prov:wasDerivedFrom` given teeth
  [28].
- `source_type: agent-inference` and `source_type: user-assertion` **cannot** support
  `confidence: high`. ADR-0006 defines high confidence as "directly supported by cited source"; an
  agent's own inference is by definition not that. Enforce it in a deterministic tool
  (`check_confidence_consistency`), not in a prompt, because ADR-0008 correctly predicts that
  prompt-level honesty rules erode.
- Any document produced by an agent run and later re-ingested as a corpus document — a generated
  summary, an extracted table, a contextual preamble per §2.2 rule 4 — carries a
  `SourceRef.produced_by_agent_run` marker, and **any** `EvidenceRef` targeting it is forced to
  `source_type: secondary` at minimum, never `primary`. This closes the loop that the originating
  work's most damaging error class came through.
- The view renders the distinction without being asked. comparanda ADR-0012 already requires human
  and machine assertions to be "distinguishable at a glance"; the same rule must apply to evidence,
  and a `primary` badge and an `agent-inference` badge must not be distinguishable by colour alone
  (ADR-0010's constraint).

Keep `stance` (§3.6) orthogonal to `source_type`. "A primary source that contradicts the score" and
"a secondary summary that supports it" are both real and both need saying.

---

## What this means for the schema / the view / the agent

### 5.1 The evidence reference schema — the concrete proposal to send to comparanda

TypeScript, because comparanda is schema-first on zodal (its ADR-0004) and this is what a zodal
declaration should express. Everything named `*Selector` uses W3C or Hypothesis names and semantics
verbatim; nothing here is invented.

```ts
/** WHAT was cited. Opaque to the core; resolved by the host EvidenceResolver (ADR-0014). */
type SourceRef = {
  uri: string;                    // resolver-opaque; may be a URL, a store key, a DOI, a path token
  mediaType: string;              // 'text/plain' | 'text/html' | 'application/pdf' | 'text/x-python' | 'audio/…'
  title?: string;
  revision?: string;              // commit SHA / ETag / edition — when present, positions are exact
  documentHash?: string;          // sha256 of the NORMALISED extracted text; drives drift classification
  producedByAgentRun?: string;    // run id, when this document is itself agent output (§4.2)
};

/**
 * WHERE in it. All members MUST select the same span (W3C: "Multiple Selectors SHOULD select the
 * same content"). At least one TextQuoteSelector is REQUIRED for any source with a text layer.
 */
type Selector =
  // --- W3C Web Annotation Data Model, verbatim ---
  | { type: 'TextQuoteSelector'; exact: string; prefix?: string; suffix?: string }
  | { type: 'TextPositionSelector'; start: number; end: number }        // 0-based, end exclusive; HINT
  | { type: 'FragmentSelector'; value: string; conformsTo: string }     // the sanctioned escape hatch
  // --- Hypothesis de-facto extensions, verbatim, for media W3C does not cover ---
  | { type: 'PageSelector'; index: number; label?: string }             // index 0-based; label is printed
  | { type: 'MediaTimeSelector'; start: number; end: number }           // seconds, half-open [start, end)
  | { type: 'ShapeSelector'; shape: Rect; anchor?: 'page';
      unit: 'pdf-point' | 'percent' | 'pixel'; text?: string };

type Rect = { x: number; y: number; w: number; h: number };  // pdf-point origin is BOTTOM-left

type SourceType =
  | 'primary' | 'secondary' | 'tertiary' | 'agent-inference' | 'user-assertion';

type Stance = 'supports' | 'contradicts' | 'qualifies' | 'background';

type CitationVerdict =
  | 'exact'         // quote found verbatim at the claimed position
  | 'normalised'    // found after normalisation only
  | 'fuzzy'         // found within the edit-distance budget
  | 'moved'         // found, but not where the position selector claimed
  | 'stale'         // document resolved, quote not found
  | 'unresolvable'; // source did not resolve

type CitationCheck = {
  verdict: CitationVerdict;
  editDistance?: number;
  matchedPosition?: { start: number; end: number };
  numericClaims?: { claim: string; unit?: string; found: boolean }[];
  lexicalOverlap?: number;                    // weak signal only; NOT a faithfulness score
  flags?: ('span-too-long' | 'span-too-short' | 'polarity-mismatch'
         | 'no-numeric-support' | 'quote-differs-from-source')[];
  checkedAt: string;                          // ISO 8601
  checkerVersion: string;                     // pins the normalisation function
};

type EvidenceRef = {
  id: string;                     // stable within the analysis
  source: SourceRef;
  selectors: Selector[];          // >= 1; MUST include a TextQuoteSelector where a text layer exists
  quote: string;                  // REQUIRED. normalised excerpt — the offline bundle shows this
  quoteHash: string;              // sha256(normalise(quote)) — drift detection
  sourceType: SourceType;
  stance: Stance;                 // default 'supports'
  retrievedAt: string;            // ISO 8601 — a flattened W3C TimeState
  derivedFrom?: string[];         // EvidenceRef ids; REQUIRED when sourceType === 'agent-inference'
  check?: CitationCheck;          // written ONLY by the deterministic tool, never by the model
};
```

Six design decisions worth defending to comparanda, because each is a place a reviewer will push
back:

1. **`selectors` is an array, always.** Per W3C's own advice [1] and Hypothesis's production
   practice [2]. A single-selector convenience constructor is fine; a single-selector *schema* is
   not.
2. **`quote` is duplicated out of the TextQuoteSelector to the top level.** Redundant, deliberately:
   ADR-0014 wants excerpts embedded for the standalone bundle, and every consumer wants the excerpt
   without walking a union type. Validate the two agree.
3. **`check` is written by the tool, never by the model.** Make this a schema-level affordance in
   zodal terms: the field is not model-writable. A model that can write its own verdict will.
4. **`selectors` may contain a `TextPositionSelector` that is wrong.** That is not a validation
   error; it is what `verdict: 'moved'` is for. Positions are a cache.
5. **No `RangeSelector`, no `CssSelector`, no `XPathSelector`.** They bind to a DOM the producer
   never had. Accept them on ingest from a host annotation tool, store them, never generate them.
6. **`stance` is a field, not a convention.** Without it, contradicting evidence is unrepresentable
   and therefore uncountable — see §3.6.

Every typed selector must have a documented lossless serialisation to a `FragmentSelector`, so an
`EvidenceRef` can round-trip to a standard W3C annotation:

| Our selector | FragmentSelector serialisation | `conformsTo` |
|---|---|---|
| `TextPositionSelector{s,e}` | `char=s,e` | RFC 5147 [8] |
| line range | `line=s,e` (boundaries, so `line=40,58` is lines 41–58) | RFC 5147 [8] |
| `PageSelector{index}` | `page={index+1}` | RFC 8118 [7] |
| `MediaTimeSelector{s,e}` | `t={s},{e}` | Media Fragments 1.0 [9] |
| `ShapeSelector` rect | `xywh=x,y,w,h` (or `xywh=percent:…`) | Media Fragments 1.0 [9] |
| `TextQuoteSelector` | `:~:text=prefix-,exact,-suffix` (URL-encoded) | Text Fragments [4] |

### 5.2 The deterministic citation-check tool

MCP tool, no model, no network beyond the host resolver. Python signature (this repo is
Python-first per ADR-0004), keyword-only past the second argument per house style:

```python
def check_citations(
    justification: str,
    evidence_refs: Sequence[EvidenceRef],
    *,
    resolve: Callable[[SourceRef], str | None],   # injected; the host's EvidenceResolver
    max_error_rate: float = 0.02,
    min_span_chars: int = 40,
    max_span_chars: int = 1500,
    min_lexical_overlap: float = 0.05,
    normaliser: Normaliser = DEFAULT_NORMALISER,  # versioned; pins quote_hash semantics
) -> CitationReport: ...
```

Returning:

```python
@dataclass(frozen=True)
class CitationReport:
    checks: Mapping[EvidenceRefId, CitationCheck]
    numeric_support_rate: float          # numeric claims in the justification matched in some span
    unmatched_numeric_claims: tuple[NumericClaim, ...]
    uncited_justification: bool          # no evidence refs at all — a hard signal for ADR-0006
    worst_verdict: CitationVerdict
    checker_version: str
```

Algorithm, per reference, short-circuiting downward:

```
doc = resolve(ref.source)
if doc is None:                                   -> unresolvable; stop
D, Q = normalise(doc), normalise(ref.quote)
if len(Q) < min_span_chars:                       flag span-too-short
if len(Q) > max_span_chars:                       flag span-too-long
i = D.find(Q)
if i >= 0:
    pos = position_selector(ref)
    verdict = exact      if pos and pos.start == i
              else moved if pos
              else normalised
else:
    k = max(1, ceil(max_error_rate * len(Q)))
    m = approx_search(D, Q, max_errors=k)         # Myers bit-parallel [31]
    verdict = fuzzy if m else stale
    if m: flag quote-differs-from-source, record edit_distance
if ref.source.documentHash and ref.source.documentHash != sha256(D):
    verdict = moved if verdict in {exact, normalised} else verdict
polarity_mismatch(justification, Q)               -> flag polarity-mismatch
```

and once across the whole reference set:

```
claims = extract_numeric_claims(justification)    # regex + unit normalisation; no model
spans  = " ".join(normalise(r.quote) for r in refs)
unmatched = [c for c in claims if not numeric_match(c, spans)]
numeric_support_rate = 1 - len(unmatched)/len(claims)  (1.0 when there are no numeric claims)
if lexical_overlap(justification, spans) < min_lexical_overlap: flag no-topical-overlap
```

Two more deterministic tools belong beside it, and both fall out of ADR-0006 rather than being
new ideas:

```python
def check_confidence_consistency(analysis: Analysis) -> tuple[Violation, ...]:
    """high confidence requires >=1 EvidenceRef with sourceType in {primary, secondary}
    AND verdict in {exact, normalised}; agent-inference and user-assertion can never be high."""

def report_evidence_coverage(analysis: Analysis) -> CoverageReport:
    """Per cell / criterion / alternative / analysis: cited, uncited, stale, contradicted.
    Feeds ADR-0005 step 6 (review) and comparanda's completeness reporting (its ADR-0009)."""
```

REASONING on granularity, for Phase 1: `check_citations` takes one justification and its
references, not a whole analysis. Cell-level granularity lets the connector call it inside the
scoring loop and repair a bad citation immediately, which is the behaviour we want; an
analysis-level checker only tells you afterwards. Provide `check_analysis_citations` as a thin
fan-out over it for the CLI and the evaluation harness.

### 5.3 The model-based faithfulness judge — evaluation suite only

Never an MCP tool. Lives in the eval harness, where a model is allowed.

```python
def judge_citation_support(
    justification: str,
    cited_spans: Sequence[str],
    *,
    entailment: EntailmentModel,        # HHEM-2.1-Open | AlignScore | MiniCheck-FT5 | LLM judge
    decompose: ClaimDecomposer,         # RAGAS-style atomic-claim extraction
    threshold: float = 0.5,
) -> SupportReport: ...
```

Protocol, following ALCE [11] with RAGAS-style decomposition [18][19]:

1. Decompose `justification` into atomic claims c₁…c_m.
2. `premise = "\n".join(cited_spans)` — ALCE's concatenation rule [11].
3. **citation_recall** = fraction of cᵢ entailed by `premise`. (ALCE's per-statement binary
   generalised to claim level; report both the binary form for comparability and the fraction for
   sensitivity.)
4. **citation_precision**: for each span s, it is *irrelevant* iff (a) s alone does not entail the
   claims it is attached to, and (b) `premise \ {s}` still entails them. Precision = fraction of
   spans that are not irrelevant, conditional on recall = 1 [11].
5. **contradiction rate** = fraction of cᵢ *contradicted* by `premise` — AttrScore's third label
   [14], the one binary entailment throws away and the one that matters most here.

Metrics to add to ADR-0008's suite, with the tier each runs at:

| Metric | Tier | Gate |
|---|---|---|
| `citation_resolvability` | CI, deterministic | must be 1.0 |
| `quote_verbatim_rate` (verdict ∈ {exact, normalised}) | CI, deterministic | 1.0 for text sources |
| `numeric_support_rate` | CI, deterministic | 1.0 on fixtures |
| `unsupported_high_confidence_rate` | CI, deterministic | must be 0 — this *is* ADR-0006 |
| `citation_precision`, `citation_recall`, `contradiction_rate` | nightly, small NLI model | no regression vs previous release |
| `source_type_accuracy` | nightly, fixtures with labelled provenance | no regression |
| `counter_evidence_missed@k` | release, adversarial retrieval + judge | report, do not gate |

REASONING on fixtures: ADR-0008 already requires public-domain fixtures with deliberately absent
evidence. Add three fixture families specifically for this section, all cheap to build in public
domains (programming languages, cities, databases, bicycles): (i) a **moved-text** fixture — same
document with a paragraph inserted above the cited span, which must produce `moved`, not `stale`;
(ii) a **paraphrase** fixture — a justification that is a faithful paraphrase, which the
deterministic ladder must *not* mark `exact` and the judge must mark supported, proving the two
layers do different jobs; (iii) a **contradiction** fixture — a span that says the opposite, which
step 8's polarity trap should flag and the judge should score as contradicted.

### 5.4 What the agent must be told

Three prompt rules follow, for the `score-cell` and `score-column` prompts (per `docs/prompts/`):

- **Quote, do not summarise, in the evidence field.** The `exact` string must be copied verbatim
  from the source with surrounding `prefix` and `suffix` of roughly 32 characters — Hypothesis's
  context length [2] — because that is what makes re-anchoring work.
- **A span you cannot quote is not evidence.** If the support is spread across a document with no
  quotable span, the correct output is `unknown` with a note, or a `secondary`/`agent-inference`
  reference with `derivedFrom` set — never a `primary` reference to the whole document.
- **Say when the source disagrees.** A `contradicts` or `qualifies` reference is a *better* answer
  than omitting the span, and the review stage (ADR-0005 step 6) is required to surface cells whose
  only evidence is `agent-inference`.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| rubricator ADR-0006 | confirm | Nothing found weakens it; the attribution literature strengthens it — 51.5%/74.5% support rates in deployed systems [12] are the empirical case for the whole policy. |
| rubricator ADR-0003 | confirm | The deterministic/judge split of §3.5–§3.6 is achievable with real coverage; the constraint improved the design rather than limiting it. |
| rubricator ADR-0008 | amend | Add the seven-metric table of §5.3 with explicit tiers, separate citation precision from recall, add `counter_evidence_missed@k`, and name the three new fixture families (moved-text, paraphrase, contradiction). |
| rubricator — new ADR | new ADR | "The evidence-reference locator profile": the narrowed W3C selector set, the mandatory TextQuoteSelector, positions-as-hints, the FragmentSelector serialisation table, and the versioned normalisation function. This is a decision with long-lived consequences and it is not currently recorded anywhere. |
| rubricator — new ADR | new ADR | "Source type, stance and the derived-from constraint": the five-member `sourceType` enum, the orthogonal `stance` enum, and the hard rule that `agent-inference` requires `derivedFrom` and can never carry high confidence. ADR-0006 states the principle; the enforceable constraint deserves its own record. |
| rubricator ADR-0004 | (no action from this section) | Untouched by these findings; settled by the `aw_agents` reading. |
| comparanda ADR-0014 | amend *(their repo; recommendation only)* | It says "W3C Web Annotation selectors … should be evaluated first". They have been. Amend to name the profile in §5.1, the `selectors` array with a mandatory TextQuoteSelector, and the `stance` + `sourceType` fields — the last of which ADR-0014 does not currently have and which its own "provenance is distinct from evidence" principle implies. |

---

## Open questions

1. **Where does `check` live when an analysis is shared?** A `CitationCheck` is only meaningful
   relative to a resolver and a moment. If a stale check travels inside the analysis JSON to a
   reader with a different corpus, it will mislead. Settle by deciding whether `check` is persisted
   or recomputed on load — I lean **persisted with `checkedAt` and `checkerVersion` shown in the
   UI**, on the grounds that a standalone bundle with no resolver still needs to show *something*
   — but this is comparanda's call, and it interacts with their ADR-0006 (persistence).
2. **The fuzzy threshold.** 2% edit rate is a starting point, not a finding. Settle empirically on
   the fixture corpus: measure false-anchor rate as the threshold rises. The published Hypothesis
   threshold could not be verified [2].
3. **Claim decomposition quality.** RAGAS-style decomposition is itself a model call and is itself
   unreliable; ALCE avoids it by treating whole statements as hypotheses [11][18]. For one-line
   justifications the difference may be negligible. Settle by running both on the fixture set and
   comparing agreement with human labels.
4. **PDF rectangles.** No standard for "page + rectangle" is well supported outside Acrobat [7],
   and Hypothesis's `ShapeSelector` is a de-facto extension with a coordinate-system footgun [3].
   Defer `ShapeSelector` out of v1 unless a real corpus with scanned evidence arrives. Would be
   settled by one such corpus.
5. **Judge-vs-ground-truth calibration.** AttributionBench's ~80% macro-F1 ceiling [15] means our
   nightly judge is wrong roughly one time in five. Before trusting it, calibrate the chosen small
   model against a few hundred human-labelled fixture citations and record the confusion matrix in
   the repo. Until that exists, treat all judge numbers as deltas.
6. **Whether `unknown` should be forced when every reference is `agent-inference`.** ADR-0006's
   spirit says yes; making it a hard schema rule might over-constrain legitimate synthesis across
   several cited primaries. Recommend starting as a *review-stage warning* and promoting it to a
   rule if the evaluation suite shows the warning being ignored.

---

## REFERENCES

1. [Web Annotation Data Model — Sanderson, Ciccarese & Young, W3C Recommendation (2017)](https://www.w3.org/TR/annotation-model/)
2. [Fuzzy Anchoring — Hypothesis (2013)](https://web.hypothes.is/blog/fuzzy-anchoring/)
3. [Hypothesis client — selector type definitions in `src/types/api.ts` — Hypothesis (2024)](https://github.com/hypothesis/client/blob/main/src/types/api.ts)
4. [Text Fragments — WICG Draft Community Group Report (2023)](https://wicg.github.io/scroll-to-text-fragment/)
5. [Text fragments — MDN Web Docs, Mozilla (2025)](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Fragment/Text_fragments)
6. [URL Scroll-To-Text Fragment — Can I use (2025)](https://caniuse.com/url-scroll-to-text-fragment)
7. [RFC 8118: The application/pdf Media Type — IETF (2017)](https://www.rfc-editor.org/rfc/rfc8118.html)
8. [RFC 5147: URI Fragment Identifiers for the text/plain Media Type — Wilde & Duerst, IETF (2008)](https://www.rfc-editor.org/rfc/rfc5147.html)
9. [Media Fragments URI 1.0 (basic) — W3C Recommendation (2012)](https://www.w3.org/TR/media-frags/)
10. [Citations — Claude Platform documentation, Anthropic (2025)](https://platform.claude.com/docs/en/build-with-claude/citations)
11. [Enabling Large Language Models to Generate Text with Citations (ALCE) — Gao et al., EMNLP (2023)](https://aclanthology.org/2023.emnlp-main.398/)
12. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang, Findings of EMNLP (2023)](https://arxiv.org/abs/2304.09848)
13. [Measuring Attribution in Natural Language Generation Models (AIS) — Rashkin et al. (2021)](https://arxiv.org/abs/2112.12870)
14. [Automatic Evaluation of Attribution by Large Language Models (AttrScore) — Yue et al. (2023)](https://arxiv.org/abs/2305.06311)
15. [AttributionBench: How Hard is Automatic Attribution Evaluation? — Li et al. (2024)](https://arxiv.org/abs/2402.15089)
16. [TRUE: Re-evaluating Factual Consistency Evaluation — Honovich et al., NAACL (2022)](https://arxiv.org/abs/2204.04991)
17. [HAGRID: A Human-LLM Collaborative Dataset for Generative Information-Seeking with Attribution — Kamalloo et al. (2023)](https://arxiv.org/abs/2307.16883)
18. [RAGAS: Automated Evaluation of Retrieval Augmented Generation — Es et al. (2023)](https://arxiv.org/abs/2309.15217)
19. [Faithfulness — Ragas documentation (2025)](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)
20. [MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents — Tang, Laban & Durrett (2024)](https://arxiv.org/abs/2404.10774)
21. [AlignScore: Evaluating Factual Consistency with a Unified Alignment Function — Zha et al., ACL (2023)](https://arxiv.org/abs/2305.16739)
22. [HHEM-2.1-Open hallucination evaluation model — Vectara (2024)](https://huggingface.co/vectara/hallucination_evaluation_model)
23. [Introducing Contextual Retrieval — Anthropic (2024)](https://www.anthropic.com/news/contextual-retrieval)
24. [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models — Günther et al. (2024)](https://arxiv.org/abs/2409.04701)
25. [Evaluating Chunking Strategies for Retrieval — Chroma Research (2024)](https://www.trychroma.com/research/evaluating-chunking)
26. [Is Semantic Chunking Worth the Computational Cost? — Qu, Tu & Bao (2024)](https://arxiv.org/abs/2410.13070)
27. [LongCite: Enabling LLMs to Generate Fine-grained Citations in Long-context QA — Zhang et al. (2024)](https://arxiv.org/abs/2409.02897)
28. [PROV-O: The PROV Ontology — Lebo, Sahoo & McGuinness (eds.), W3C Recommendation (2013)](https://www.w3.org/TR/prov-o/)
29. [CiTO, the Citation Typing Ontology — Peroni & Shotton, SPAR Ontologies](https://sparontologies.github.io/cito/current/cito.html)
30. [Missing Counter-Evidence Renders NLP Fact-Checking Unrealistic for Misinformation — Glockner, Hou & Gurevych, EMNLP (2022)](https://arxiv.org/abs/2210.13865)
31. [approx-string-match-js: bit-parallel approximate string matching (Myers) — Knight](https://github.com/robertknight/approx-string-match-js)
32. [A Survey of Large Language Models Attribution — Li et al. (2023)](https://arxiv.org/abs/2311.03731)
33. [Introduction to Primary Sources — History, Philosophy and Newspaper Library, University of Illinois](https://www.library.illinois.edu/hpnl/tutorials/primary-sources/)
