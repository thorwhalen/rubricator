# Pending ADR actions — a working list, not a decision

**Nothing in `docs/adr/` has been edited.** ADRs are immutable once accepted (ADR-0001), and the two
that are still `proposed` are live questions a human settles. This file consolidates every ADR action
the round-1 research recommends for **this** repository, with a ready-to-adopt draft body for each
new or superseding ADR.

**How to use it.** Read a section, decide, then apply the decision by editing or adding the ADR
itself. **Delete this file once its actions are applied** — a pending list that outlives its
pendency becomes a second, competing source of truth, which is exactly what ADR-0001 exists to
prevent. If an action is rejected, record the rejection in the ADR it targeted (or as a new ADR)
rather than leaving it here.

**Provenance.** Every recommendation traces to [`docs/research/findings-method.md`](../research/findings-method.md)
[1] and through it to the seven section files and to the owner's scoring-order document [2]. The
ledger at [`docs/research/README.md`](../research/README.md) maps question → finding → action. Draft
bodies below are written in the ADR format of [`0000-template.md`](./0000-template.md) and are
**drafts**: adopt, edit, or reject.

**Conventions.** Claims the literature supports are cited. Claims that are inference over evidence
are marked **(reasoning, not evidence)** — these are the ones most worth arguing with.

---

## Order

Ordered by how much downstream work each unblocks, not by ADR number.

| Order | Action | ADR | Unblocks |
|---|---|---|---|
| 1 | **supersede** ADR-0004 with new **ADR-0009** | ADR-0004 → 0009 | Phase 1 (tool surface), Phase 3 (connector), Phase 5 (deployed agent). Nothing can be built until the host framework is settled |
| 2 | **new ADR-0010** — the determinism boundary | 0010 | Every tool contract. Decides what a tool may not do, which is the shape of all of them |
| 3 | **new ADR-0013** — structured output and the JSON Schema subset | 0013 | Phase 1. A hard constraint on tool signatures that must be honoured *before* the surface freezes |
| 4 | **settle ADR-0007** (proposed → accepted, amended) | 0007 | The packaging sequence and the repo layout; removes one deliverable from the plan |
| 5 | **new ADR-0011** — the scoring protocol | 0011 | Phase 2 prompts (`score-cell`, `score-column`), the scoring tools, and the eval harness arms |
| 6 | **new ADR-0012** — scales, confidence, the two uncertainties | 0012 | Phase 2 prompts, the schema requests to comparanda, and the ADR-0008 metric families |
| 7 | **amend ADR-0005** — the mechanism of step 4 | 0005 | Phase 3. The checkpoint is the load-bearing interaction and has no implementation yet |
| 8 | **new ADR-0016** — criteria are revisable | 0016 | `propose-criteria`, the criteria tools, and two schema requests |
| 9 | **new ADR-0014** — the evidence-reference locator profile | 0014 | The evidence and citation tools; the largest single schema request |
| 10 | **new ADR-0015** — source type, stance, derived-from | 0015 | The honesty guarantee's *enforcement*; ADR-0006 is unenforceable without it |
| 11 | **new ADR-0017** — in-progress analyses are durable partial documents | 0017 | Phase 3 resumption, and the store's design |
| 12 | **amend ADR-0008** — four changes | 0008 | Phase 4, and every prompt change after it |
| 13 | **new ADR-0018** — variance policy per runtime | 0018 | Phase 4 harness and the deployed runtime's defaults |
| 14 | **new ADR-0019** — all LLM access through the local `aix` facade | 0019 | Phase 5, and the import test that mechanically enforces ADR-0003 |
| 15 | **confirm** ADR-0001, ADR-0002, ADR-0003, ADR-0006 | — | Nothing — but recording the confirmation is what makes the research legible later |

---

## 1. ADR-0004 → supersede with ADR-0009

**Action:** supersede. **Status of ADR-0004 today:** `proposed` — one of the two the research was
commissioned to settle.

**Definite recommendation: supersede, do not amend.** ADR-0001 permits settling a `proposed` ADR in
place, so amending would be legal. Supersede anyway, because the decision *inverts* rather than
refines: the framework changes, the conditional clause ("if `aw_agents` can host the MCP surface
directly, use it") is answered "it cannot and should not try", and the premise that `aw_agents`
supplies model access is factually wrong. A superseding ADR leaves ADR-0004 readable as the question
that was asked, which is the point of ADR-0001. *(The research explicitly leaves this one to a human
[1] §7.8; the recommendation above is the one this file makes.)*

**Reason:** EVIDENCE, from reading the installed source. `aw_agents`' MCP adapter registers exactly
`list_tools` and `call_tool` over the low-level SDK — no `prompts/list`, no `prompts/get`, no
`resources/*`, no elicitation seam — and ADR-0003's "prompts ship as content the runtime can serve"
is the one sentence that makes one specification serve two runtimes. It also contains no model
client, loop, session or streaming, so it does not supply the deployed runtime ADR-0004 assumed.

### Draft — ADR-0009

```markdown
# ADR-0009: Python, the official MCP SDK, and the rejection of aw_agents as host

- **Status:** proposed (supersedes ADR-0004)
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0004 recommended Python on the local `aw_agents` framework, conditional on reading its source.
The source was read. `aw_agents`' MCP adapter registers exactly two handlers — `list_tools` and
`call_tool` — over the low-level MCP SDK server. There is no prompts capability, no resources
capability, and no seam to add either; results are stringified rather than returned as structured
content; its OpenAPI adapter drops nested input sub-schemas; its adapters carry no tests; and it
contains no model client, loop, session or streaming. ADR-0003 requires the MCP layer to serve
prompts and resources — that requirement is what makes one specification serve two runtimes — and
ADR-0005 step 4 requires elicitation.

## Decision
**Python for both runtimes.** The schema tooling, the LLM facade and every project convention are
already Python; a JS/TS runtime would share a language with the UI and nothing else. No JS/TS runtime
in v1; reserve the npm name.

**Build the MCP surface on the official MCP Python SDK v2 / FastMCP 4**, over a core of plain
deterministic functions in `rubricator.tools` that know nothing about MCP. FastMCP 4 is the first
release implementing modern-protocol elicitation via `InputRequiredResult` [3], which ADR-0005 step 4
needs; dual-era fallback is our code to write, not a freebie.

**Reject `aw_agents` as host** — not forever. If a non-MCP chatbot surface is ever wanted, its
OpenAPI adapter becomes a candidate *second consumer of the same functions*, never the host, and its
sub-schema flattening must be fixed first. The local `py2mcp` keeps a real role on the CLI/OpenAPI
line of ADR-0007; it is tools-only today and pins an unbounded `fastmcp` that resolves to 3.x, so
adopting it would make the load-bearing checkpoint depend on an upstream upgrade outside this
project's control. Contribute `prompts=` / `resources=` kwargs and a FastMCP 4 floor upstream, then
revisit.

**Tool surface: 19 tools, 11 minimum viable** — comfortably under the band where tool selection
degrades — and **generation granularity is separated from write granularity**: the prompt asks for
one criterion per generation, the tool accepts a batch. Conflating them costs dozens of round trips
for no benefit.

## Consequences
The connector installs with no LLM dependency. The tool core is testable with no MCP present and no
key. The cost is that dual-protocol-era support and the elicitation fallback are ours to write and
to test. Rejecting a local framework also means an ecosystem gap stays open — file it as an issue
rather than silently absorbing it.

## Alternatives considered
- *`aw_agents` as host.* Cannot serve prompts, resources or elicitation. This ADR exists because
  ADR-0004 assumed otherwise.
- *`py2mcp` as the builder.* Verified to return a live FastMCP object carrying `.prompt` and
  `.resource`, but tools-only by design and without a FastMCP 4 floor. Revisit after both land.
- *Amend ADR-0004 in place.* Legal (it is `proposed`), but the decision inverts rather than refines.
```

---

## 2. New ADR-0010 — the determinism boundary

**Action:** new. **Reason:** ADR-0003 states "no tool may require a model" as prose. This turns it
into a boundary with named exclusions, and closes the one exception that looked legitimate. EVIDENCE:
MCP sampling was deprecated in specification revision 2026-07-28 with the migration path "integrate
directly with LLM provider APIs" [4] — so the question is settled without a judgement call.

### Draft — ADR-0010

```markdown
# ADR-0010: The determinism boundary — no model calls, no embedding calls, lexical retrieval

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0003 forbids a tool that requires a model, because the connector runtime has no key. Two
apparent escape hatches existed: MCP sampling (ask the client's model from inside a tool), and
embedding-based retrieval (a "small" model that feels unlike a model call). Both would reintroduce
the dependency the architecture exists to avoid, and both would produce judgements invisible to the
transcript where ADR-0006's posture lives and untestable by ADR-0008.

## Decision
**No MCP sampling.** Deprecated in revision 2026-07-28 [4]; would in any case be untestable and
invisible.

**No in-tool model calls of any kind, and no embedding calls** — an embedding model is a model. It
needs either a key (no connector) or a bundled local model whose version silently changes results
between runs.

**Retrieval is lexical**: BM25 plus normalised substring matching, with a fixed tokenizer, a fixed
stopword list, a versioned chunker, and tie-breaking fixed by `(score, document_id, start)`. A
retrieval change must not be able to masquerade as a prompt regression. This is sufficient because
the model does the semantic work in its own loop and can issue several queries.

**Contextual and late-chunked embedding indexes are permitted only in an offline
corpus-preparation step** run by the deployed agent or the CLI, producing a static index the
connector reads.

**Retrieve by default.** Inline the whole corpus only under roughly 25k tokens and only at the
enumeration stage, implemented as one documented behaviour of `corpus_search` rather than a branch
in the model's head. There is no long-context pricing surcharge on current models, so the crossover
is set by cache economics — roughly 20k–40k corpus tokens when you control caching and roughly 5k
when you do not, and in the connector you control neither.

## Consequences
Every tool is testable offline, deterministically, byte-for-byte. Retrieval quality is lower than an
embedding index would give — accepted, because the alternative breaks the connector. Anyone wanting
better recall runs the offline preparation step.

## Alternatives considered
- *MCP sampling for the hard cases.* Deprecated, and it would hide judgement from the transcript.
- *A bundled small embedding model.* Heavy dependency; version drift silently changes results.
- *Semantic chunking.* Costs compute and does not reliably beat fixed-size chunking.
```

---

## 3. New ADR-0013 — structured output and the JSON Schema subset

**Action:** new. **Reason:** the supported JSON Schema subset is a hard constraint on tool signatures
and must be honoured **before Phase 1 freezes the surface** — retrofitting `enum` in place of
`minimum`/`maximum` across a settled surface is pure rework. EVIDENCE: the widely-cited claim that
format restriction degrades reasoning does not survive reading the paper's own body — 100% of its
degraded responses put the answer key before the reason key [5] — and with real constrained decoding
the gap reverses [6][7].

### Draft — ADR-0013

```markdown
# ADR-0013: Structured output, and the JSON Schema subset the tool surface may use

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
Every judgement this agent makes must arrive as schema-valid structured data. A widely-cited paper
claims format restriction degrades reasoning; reading its body shows the degraded configurations put
the answer field before the reasoning field, which is a prompt-ordering defect, not a property of
constrained decoding [5]. Providers also support only a subset of JSON Schema in constrained mode,
and that subset constrains our tool signatures.

## Decision
**Emit judgements through grammar-constrained sampling in both runtimes** — strict tool definitions
in the connector, the same JSON Schema through the provider's constrained decoder in the deployed
agent — with the **reasoning field declared before the value fields**, and deliberation happening
*outside* the constrained region (in prose, or in the model's thinking block).

**The supported subset is a hard constraint on the tool surface, honoured before Phase 1 freezes
it:** scores are `enum`, never `minimum`/`maximum`; no recursion; no external `$ref`; no
string-length constraints; `additionalProperties: false` everywhere. Range checks move into the
deterministic validator, which is where they belong.

**Two enforcement points, both required.** `inputSchema` plus strict mode constrains what the
*model* may say. `outputSchema` plus our own validator constrains what the *server* may return.
Every tool declares `outputSchema` and returns structured content, and every structured result
passes the same deterministic validator before it becomes part of an analysis.

## Consequences
Schema validity stops being an ADR-0008 metric we hope for and becomes a property of the pipeline.
The cost is that the subset is restrictive and expressive schemas must be flattened; the validator
carries what the schema cannot.

## Alternatives considered
- *Free-text output plus a parser.* Reintroduces exactly the failure the schema exists to prevent.
- *Unconstrained JSON mode.* Weaker guarantee for no reasoning benefit.
- *Reasoning after the value.* The measured cause of the degradation the objection rests on [5].
```

---

## 4. ADR-0007 — settle it: proposed → accepted, amended

**Action:** amend and accept in place. ADR-0001 permits settling a `proposed` ADR by changing its
status with reasoning; no superseding ADR is needed because the *sequence* is unchanged.

**Definite recommendation.** Keep the four-stage order (MCP server → prompt bundle → Python package
→ CLI), and make one change: **deliverables (1) and (2) are one artifact, not two.** Claude clients
surface MCP prompts as slash commands and resources as `@` mentions [8], so *serving* the prompts is
the prompt bundle. Also record that the local `py2mcp` moves to the CLI/OpenAPI line rather than the
connector (see ADR-0009).

**Suggested edit to ADR-0007's Decision section:**

> Ship in this order:
> 1. **MCP server, prompts included** — the tool surface of ADR-0003 *and* the elicitation, scoring
>    and review prompts, served as MCP prompts and resources. Claude clients surface prompts as slash
>    commands and resources as `@` mentions [8], so this is one artifact: there is no separate prompt
>    bundle to build, package or keep in sync. Usable from Claude Desktop and Claude Code with no API
>    key. This is the minimum viable product and validates the tool decomposition.
> 2. **Python package** — the deployed agent (ADR-0009), for scheduled and unattended runs.
> 3. **CLI** — thin wrapper over the same tools; disproportionately useful for testing and for users
>    who want no chat at all. The local `py2mcp` is a candidate here, not in the connector.
>
> Deferred: a hosted service, a JS/TS runtime (ADR-0009), and any UI — the UI is `comparanda`.

The Consequences section's warning (that stopping after the connector is a legitimate outcome) stands
and is strengthened: with prompts folded in, the connector *is* the product for the primary user.

---

## 5. New ADR-0011 — the scoring protocol

**Action:** new. **Reason:** this is the direct descendant of the owner's scoring-order document [2]
and the single decision that most constrains Phase 2. EVIDENCE: criterion position inside a prompt
shifts a criterion's mean by up to 0.80 points on a 5-point scale, with 56 of 60 (judge, criterion)
tests significant [9]; attributes scored in one generation collapse toward each other, inflating
inter-attribute correlation from a human r ≈ 0.32 to r ≈ 0.98 [10]; reference-guided judging more
than halves chain-of-thought's failure rate on MT-Bench [11].

### Draft — ADR-0011

```markdown
# ADR-0011: The scoring protocol — pointwise, cell-wise, evidence first

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
Traversal order and scoring protocol change the numbers, measurably and in a known direction. Scoring
several criteria in one generation collapses them toward each other [10]; criterion position inside a
prompt shifts that criterion's mean by up to 0.80 points on a 5-point scale [9]. Pairwise comparison
is the human reliability gold standard, but forced choice manufactures a winner where the judge's own
scalar reading contains no significant difference [12] — the exact opposite of what ADR-0006 is for.

## Decision
**Score pointwise, cell-wise, one criterion per generation**, against a 5-point anchored rubric, with
the traversal order supplied by a **seeded tool permutation** (not by the model, so the run is
replayable and the seed enters provenance) and the rubric level order randomised per read.

**`extract_evidence` runs before `score_cell`, and `score_cell` receives the span, not the corpus.**
Reference-guided judging beats chain-of-thought on MT-Bench by more than 2× on failure count [11],
and scoring-then-citing is the arrangement that produces post-hoc citation.

**Prompt shape per cell is plan → judge → emit**, with the plan persisted as provenance.

**Repeats reduce by lower median.** `mean` is refused at the tool boundary, naming the level of
measurement [13]; a trimmed range is legal, a trimmed mean is not. **No point reduction is emitted
for a polarised cell** — emit the level multiset and a `contested` marker instead. *(REASONING, from
simulation: for a cell split 2/4 at p = .45 each, the median lands on 3 — a level almost nobody chose
— with probability rising from .10 at k = 1 to .36 at k = 21. More repeats make the point estimate
monotonically more misleading.)*

**Pairwise is not the default and is not built in v1.** It may be escalated per criterion only under
*all* of: evidence coverage ≥ 70% (hard veto), decision relevance, and compression or instability —
and then only within the tied cluster, fitted by **Bradley–Terry MLE with Davidson ties and a
bootstrap interval, never online Elo**, whose ratings depend on comparison arrival order [14][15].
The resulting cell is marked as derived. **The escalation thresholds are reasoning, not evidence, and
are the first thing ADR-0008 tunes.**

**Temperature 0 applies to the deployed runtime only.** It does not exist in the connector, and a
parameter that silently no-ops in one of two first-class runtimes is a bug in the specification.

## Consequences
More calls than any batched arrangement, and the connector cannot afford the repeat schedule — which
is why ADR-0018 splits the policy by runtime. In exchange, cross-cell contamination is removed by
construction rather than mitigated, and every number is attributable to one generation with a
recorded seed. `score-column` survives only as a cheaper harness arm awaiting validation, and the
prompts README line calling it "likely better" must be corrected.

## Alternatives considered
- *Column-wise (one criterion, all alternatives).* Holds the scale fixed, which is a real argument —
  but it is reasoning against direct measurement [9][10]. It is harness arm 2, not the default.
- *Single-pass.* Cheapest and worst; also exposed to lost-in-the-middle effects.
- *Pairwise throughout.* Structurally cannot abstain, and costs 7–20× at the reliability comparative
  judgement requires [16].
- *Mean of repeats.* Returns a level no rater could have chosen, on an ordinal scale [13].
```

---

## 6. New ADR-0012 — scales, confidence, and the two uncertainties

**Action:** new, **citing ADR-0006 as its parent and leaving ADR-0006 untouched**. Three sections
said "confirm ADR-0006", one said "amend"; the resolution is that nothing ADR-0006 *decides* is
wrong — what is missing is an unstated consequence, and ADR-0001 makes superseding an accepted ADR
expensive. **Reason:** without these rules, ADR-0006's honesty guarantee is a statement of intent
with nothing enforcing it.

### Draft — ADR-0012

```markdown
# ADR-0012: Measurement scales, what confidence means, and the two uncertainties

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0006 defines `confidence` as evidence quality and prefers a qualified blank to a confident guess.
It does not say what happens when the model wants to hedge, nor what scale `score` uses, nor how
"this cell is uncertain" differs from "this cell moves between runs". Those omissions are where the
guarantee erodes. Separately, ADR-0008's calibration item cannot be computed as written: no proper
scoring rule exists over an ordinal evidence-quality label.

## Decision
**`score` is a 1–5 integer, declared ordinal, not configurable.** Buy discrimination with repeats,
not width: 0–5 beats 0–10 and 0–100 on absolute human–LLM agreement [17], and rubric position bias is
non-monotone in scale length, lowest at 3 or 5 points [9]. A criterion needing more resolution is a
ratio-level criterion and must be typed as such. *(This overrides the "widen to 1–10" recommendation
carried in [2] §6.)*

**Ordinal criteria carry required anchors at levels 1, 3 and 5 only** — 2 and 4 are structurally
"between". Anchors are written as **evidence conditions** ("a source states X"), never evaluative
adjectives ("excellent"), and are **versioned by content hash** with the criterion: two analyses
sharing a criterion key but not an anchor hash are **not comparable on that criterion**, and the
tooling says so.

**`confidence` is a three-level ordinal evidence-quality measure, exactly as ADR-0006 defines it**,
with three enforcement rules ADR-0006 leaves unstated:
1. **No citable span ⇒ `unknown`, never a low-confidence score.**
2. **The score is never hedged toward the midpoint.** All uncertainty lives in `confidence`; hedging
   the score double-counts it.
3. **Contradiction is a downgrade with a named reason** from a closed set.

**`certainty` is an optional ratio measure** from a fixed closed set of allowed probabilities,
elicited **only** in evaluation runs against fixtures with known answers or on explicit request. It
is never required in a delivered analysis, never encoded in the view, and never blended into the
score×confidence palette. It exists because no proper scoring rule can be computed on an ordinal
label; it is restricted because verbalised self-confidence is systematically overconfident wherever
nothing checks it [18].

**The two uncertainties are separated permanently.** *Evidential confidence* is **stored** and
tool-verifiable. *Procedural stability* is **derived** from the assertion set, reported
`n = 1, unmeasured` when unmeasured — never estimated, never self-reported. Sampled consistency is
admissible evidence about the **procedure** and inadmissible as evidence about **correctness** [19].

## Consequences
A cell can now be wrong in a way the system can name. Prompts get longer (anchors), criteria get more
expensive to define, and analyses become incomparable across anchor revisions — which is true today
and merely invisible. ADR-0008 gains two computable metric families in place of one uncomputable one.

## Alternatives considered
- *A configurable scale.* Every consumer would then need scale-awareness, and cross-analysis
  comparison would silently break.
- *Anchors at all five levels.* Elicitation cost per criterion roughly doubles for two levels that
  read as "between".
- *Confidence as model certainty.* Nothing can check it; it is the field most likely to be inflated.
- *Superseding ADR-0006.* Its decisions are all correct; only their consequences were unstated.
```

---

## 7. ADR-0005 — amend

**Action:** amend. ADR-0005 is `accepted`, so per ADR-0001 the amendment is either a superseding ADR
or — preferred here, because nothing it decides changes — a **new ADR that cites it as parent**,
alongside ADR-0016. Two things must be specified that ADR-0005 leaves open:

1. **The mechanism of step 4.** Use MCP **elicitation** where the client supports it — but the
   elicitation schema is restricted to a flat object of primitives [20], so the rich criteria
   discussion stays in the chat turn and the elicitation is the **record of the decision**, not the
   discussion itself. Document the degraded path for clients without the capability. Store the
   confirmation as **authored, timestamped provenance**, not a boolean flag, in both paths.
2. **Step 4 is a gate that opens both ways** — see ADR-0016.

The six stages themselves are **confirmed**, and independently arrived at by the decision-analysis
literature: ADR-0005's pipeline already is PrOACT plus a confirmation checkpoint and a review stage
[21][22].

---

## 8. New ADR-0016 — criteria are revisable

**Action:** new. **Reason:** EVIDENCE — criteria drift is documented: "users need criteria to grade
outputs, but grading outputs helps users define criteria", with some criteria dependent on the
specific outputs observed [23]. This does not contradict value-focused thinking (which forbids
deriving criteria *structure* from the alternatives while endorsing them as *stimuli*), but it does
contradict ADR-0005 read as a one-way gate.

### Draft — ADR-0016

```markdown
# ADR-0016: Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0005 settles the frame before the matrix is populated, which is correct. Read linearly, it also
implies criteria are final at step 4. They are not: criteria drift is documented, and some criteria
are dependent on the outputs actually observed [23]. Left unhandled, drift produces a matrix whose
columns were scored against different rubrics — the worst-of-both outcome, and completely invisible
in the output.

## Decision
**Criteria sets carry a version**, and **every measure records the criterion version it was scored
against.**

**When a criterion's `question`, `scale`, `preference` or `exclusions` changes after cells have been
scored, every cell scored under the old definition is invalidated** — set to `missing` with reason
`not-assessed` and a note naming the definition version — rather than silently retained.

**Criteria that rubricator proposes and then removes are recorded with a reason code**
(`merged-into`, `means-objective`, `not-controllable`, `no-discrimination-expected`,
`user-rejected`) and ship with the analysis. This is ADR-0006's discipline applied one level up: a
criteria set with no visible rejects is a criteria set nobody interrogated.

## Consequences
Revising a criterion becomes visibly expensive, which is honest — it *is* expensive. Users will
sometimes see a column empty itself, and the note explaining why is part of the deliverable. Requires
two schema changes in comparanda (criteria versioning; rejected criteria with reason codes), neither
of which can be retrofitted honestly later.

## Alternatives considered
- *Freeze criteria at step 4.* Contradicts observed practice [23] and pushes revision outside the
  tool, where it goes unrecorded.
- *Keep old scores after a definition change.* Silently mixes rubrics; invisible in the output.
```

---

## 9. New ADR-0014 — the evidence-reference locator profile

**Action:** new. **Reason:** "cite spans, not documents" (ADR-0006) has no locator format, and the
format decision determines whether a citation can be checked by a tool with no model. EVIDENCE:
locator formats are settled by primary specifications [24][25][26].

### Draft — ADR-0014

```markdown
# ADR-0014: The evidence-reference locator profile, and deterministic citation checking

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0006 requires evidence references to point at spans. A span needs a locator format, and the
choice determines whether a citation survives a document being re-fetched, re-paginated or
re-normalised — and whether a tool with no model access can verify it.

## Decision
**A narrowed W3C Web Annotation selector profile, stored as a flat array of selectors that all
select the same span, with a `TextQuoteSelector` mandatory wherever a text layer exists.** Positions
are hints; **quotes are truth** [24].

- Adopted from W3C verbatim: `TextQuoteSelector`, `TextPositionSelector` (a hint, allowed to go
  stale), and `FragmentSelector` + `conformsTo` as the sanctioned extension point [24].
- **Rejected for storage:** `CssSelector`, `XPathSelector`, `DataPositionSelector`, `RangeSelector`
  — all bind to a DOM the producer never had.
- Adopted where W3C has no selector: `PageSelector` (index **and** label — different numbers, both
  needed), `MediaTimeSelector`, and `ShapeSelector` (deferred out of v1).
- **Text Fragments (`#:~:text=`) are a rendering of the quote, not a competing locator** — the
  grammar is isomorphic to a `TextQuoteSelector`. Store the selector; derive the deep link at render
  time [25].
- Every typed selector has a documented lossless serialisation to a `FragmentSelector` [26], so a
  reference can round-trip to a standard annotation.

**Chunking stays out of the citation path.** Chunks are addresses into a document: every chunk
carries `source_uri` and character offsets into the normalised full text, the model quotes text, and
the tool re-locates the quote in the **full** document. A chunk boundary then costs recall, never a
broken citation. *(Chunk overlap is not the fix people assume — the common 800/400 default scored
below average in the most systematic public evaluation [27].)*

**The normalisation function is versioned**, because changing it silently invalidates every stored
quote hash.

**Citation checking is a deterministic eight-step ladder**: normalise (versioned) → resolvability →
exact containment → bounded-edit-distance containment → drift classification → span-size sanity →
numeric-claim agreement → polarity trap. It returns a **graded verdict, never a model call**, and the
verdict field is **written by the tool and never by the model**.

## Consequences
A citation survives re-pagination and minor re-editing, and can be checked offline in the connector.
The cost is storage (several selectors per reference) and a normalisation function that must be
versioned forever. The fuzzy-match threshold is **reasoning, not evidence**, and is an ADR-0008
tuning target.

## Alternatives considered
- *Character offsets alone.* Break on any re-fetch; the failure is silent, which is the worst kind.
- *Document-level citation.* Explicitly rejected by ADR-0006 — a citation nobody can check is not a
  citation.
- *Chunk ids as locators.* Makes every citation hostage to the chunker's version.
```

---

## 10. New ADR-0015 — source type, stance, and the derived-from constraint

**Action:** new. **Reason:** ADR-0006 names "agent-generated summaries mistaken for primary
authorship" as the most damaging error class, and provides no mechanism. **An enum does not prevent
it** — a model that wants a clean citation will set the enum to `primary`. Constraints do. EVIDENCE
for the severity: an audit of four deployed generative search engines found only 51.5% of generated
sentences fully supported by their citations, and only 74.5% of citations actually supporting their
paired statement [28].

### Draft — ADR-0015

```markdown
# ADR-0015: Source type, stance, and the constraint that stops inference passing as source

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0006 requires primary sources, secondary summaries and the agent's own inference to be
distinguishable, and names confusing them as the most damaging error class. It specifies no
mechanism. An enum alone is not one: a model that wants a clean-looking citation will select
`primary`, and nothing checks it. Separately, contradicting evidence is currently unrepresentable,
and what cannot be represented cannot be counted.

## Decision
**Every evidence reference carries `source_type` — `primary | secondary | tertiary |
agent-inference | user-assertion` — on the reference, not on the document**, because classification
is relational to use [29].

**Every evidence reference carries an orthogonal `stance` — `supports | contradicts | qualifies |
background`** [30]. Without it, counter-evidence is invisible.

**Three structural constraints, enforced by a deterministic tool** (not by prompt instruction, because
ADR-0008 correctly predicts prompt-level honesty rules erode):
1. `agent-inference` **requires** a non-empty `derived_from`. An inference that cannot name what it
   was inferred from is not evidence; it is a justification.
2. `agent-inference` and `user-assertion` can **never** carry `confidence: high`.
3. **Any document produced by an agent run and re-ingested carries a marker** that forces every
   reference targeting it to `secondary` at best — closing the loop through which the most damaging
   error class actually arrives.

**Time-based media require a `MediaTimeSelector` and a quote over a registered transcript**, because
a citation nobody can check is not a citation.

## Consequences
Some references become impossible to emit, which is the point. Agent-authored intermediate documents
must be marked at ingestion — a real cost in the pipeline, and the only place the constraint can be
applied. Requires schema support in comparanda for `stance`, `sourceType`, `derivedFrom`, `quoteHash`
and a tool-written `check`.

## Alternatives considered
- *An enum with a prompt instruction.* This is what ADR-0006 effectively has today, and ADR-0008
  exists because such rules erode.
- *`stance` folded into the justification text.* Then it cannot be counted, filtered or rendered.
```

---

## 11. New ADR-0017 — in-progress analyses are durable partial comparanda documents

**Action:** new. **Reason:** the ADR-0005 step-4 checkpoint is worthless if it does not survive a
session boundary, and **MCP gives you nothing here** — request state dies with the request by design,
and a Tasks id is held by the client and scoped to one operation [31].

### Draft — ADR-0017

```markdown
# ADR-0017: An in-progress analysis is a durable partial comparanda document

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0005 puts a human confirmation checkpoint before the expensive step. A real analysis spans
sessions: a user confirms criteria on Monday and returns on Wednesday. No MCP mechanism survives a
session boundary — request state dies with the request, a Tasks id is client-held and scoped to one
operation [31], and prompt caching is a cost optimisation, not persistence.

## Decision
**rubricator owns a store**, keyed by an opaque `analysis_id` whose retention window is stated in the
creating tool's description and whose expiry produces a recoverable error.

**The stored record is itself a schema-valid comparanda analysis** — not a bespoke checkpoint format
that must later be converted. A half-finished analysis is a finished document about an unfinished
analysis. comparanda's closed missingness set carries the resume semantics: `not-assessed` = nobody
has looked; `pending` = deliberately deferred by instruction; `unknown` = someone looked and could
not determine. That last distinction is the one the whole product rests on.

**The step-4 confirmation is stored as authored, timestamped provenance**, not a flag — so a resuming
session does not re-ask, and so the confirmation is auditable.

**Resumption is exposed three ways**: an `rubricator://analyses` resource for the host, an
`analysis_open` tool taking an existing id, and a `resume` prompt.

**The store lives in the platform user-data directory behind a Mapping interface, never inside the
package.**

## Consequences
Every intermediate state is inspectable and renderable by comparanda with no conversion — a partial
analysis is a legitimate deliverable. The costs are real: a retention policy, an expiry error path,
and a store that must be swappable for a remote one later without touching the tools.

## Alternatives considered
- *A bespoke checkpoint format.* Guarantees a conversion step and a second schema to keep in sync.
- *Client-held state.* No MCP mechanism survives a new chat.
- *A store inside the package directory.* Data in a code directory; the deploy eventually deletes it.
```

---

## 12. ADR-0008 — amend (four changes)

**Action:** amend. ADR-0008 is `accepted`; the amendment adds and corrects metrics without changing
the decision that an evaluation suite is mandatory. Four changes:

**(a) Two of its six items are passed by a degenerate agent.** "Stability" is maximised by an agent
that always returns 3, and "Refusal to guess" by one that always returns `unknown`. Each needs a
paired **discrimination counter-metric**, plus chance-corrected agreement, AB/BA swap testing, and a
paradox audit. *(This is the most important of the four — as written, two release gates can be
passed by the worst possible agent.)*

**(b) The calibration bullet names a discrimination test, not calibration.** Split it:
- **Family A — discrimination over `confidence`** (ordinal): accuracy-by-level with Wilson intervals,
  a monotone-trend test, `confidence_inflation_rate` as a release gate, `unknown_preference_rate`,
  `low_confidence_laundering_rate`.
- **Family B — proper scoring over `certainty`** (probability, evaluation runs only, per ADR-0012):
  Brier with Murphy decomposition, skill score, value-binned reliability curve, ECE reported second
  behind a minimum-n gate, AUROC.
- Bootstrap **by analysis, never by cell**, and **never average `confidence`** — it is ordinal.

**(c) Add the citation metric table** with explicit tiers, separating citation **precision** from
**recall**, adding `counter_evidence_missed@k` as report-only, and using the ALCE precision/recall
definitions for the model-based check. Treat the NLI checker as a **regression detector, not an
oracle** — the ceiling in the published benchmark is roughly 80% macro-F1 [32].

**(d) Add fixtures and harness arms.** Three new fixture families — moved-text, paraphrase,
contradiction — and the measurement harness: the five arms of [2] §8 (cell-wise, column-wise,
row-wise, single-pass, cell-wise shuffled) plus two that exist only because rubricator has two
runtimes: `in_session_isolated` (one growing session, each turn returning only an acknowledgement)
and `in_session_visible` (the same session with prior scores restated). Arms 6 vs 1 measure how much
cell-wise isolation survives a shared transcript; arms 6 vs 7 measure whether withholding the prior
works. **Neither question has an answer in the literature and both cost a few dollars.**

Also record the correction from ADR-0008's own remit: **column correlation is a
`traversal_leakage_diagnostic`, never a redundancy finding**, and the tool's output must carry that
sentence. EVIDENCE: preference independence can hold even when criteria correlate in their measures
[21], and for an LLM-scored matrix the judge's own halo inflates inter-criterion correlation far
beyond the signal [10].

**Do not vendor `scipy` for this.** A 21-line pure-Python Kendall tau-b matched the library
implementation to 2.2×10⁻¹⁶ on this project's data shape; make `scipy` a test-only extra so the MCP
server installs fast and light.

---

## 13. New ADR-0018 — variance-mitigation policy per runtime

**Action:** new. **Reason:** ADR-0011 fixes the protocol; this fixes the *budget*, which differs
between a runtime that can spend model calls and one that cannot. It is also where the honest
disclosure lives.

### Draft — ADR-0018

```markdown
# ADR-0018: Variance-mitigation policy per runtime, and the independence ladder

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
ADR-0011 fixes the scoring protocol. It does not fix the budget, and the two runtimes have opposite
constraints: the deployed agent can spend calls and wait; the connector has one shared transcript, no
temperature knob, no seed, and a human waiting.

## Decision
**Deployed default:** cell-wise traversal, a seeded permutation per repeat, `k = 5` with adaptive
early stopping (halt at 3 on agreement, escalate to 9 only for cells the review flags), lower-median
reduction, and a full stability report. The knee is at 5; past 9 you buy decimal places on a 5-level
scale [33][34].

**Connector default:** cell-wise, seeded permutation, `k = 1`, then review → value-of-information
budget allocation over pivotal cells → re-score with the prior withheld → render the disclosure. A
fresh-session pass on the top pivotal cells is offered as an explicit **optional upgrade** whose
independence rung is recorded.

**Both:** never a mean; never a reduction over a polarised cell; never a reliability coefficient over
in-session assertions labelled as inter-rater agreement.

**Every assertion carries its rung on the independence ladder:**
`in-session < fresh-session < distinct-model < distinct-human`. Each rung removes a class of shared
cause; none removes them all except the last. **A statistic over rung-1 assertions is test–retest
reliability, not inter-rater reliability**, and the report must say so — getting this label wrong is
exactly the manufactured rigour ADR-0006 exists to prevent.

**Every analysis carries a `procedure` record** (traversal, k, seeds, prompt versions, model id,
whether re-scoring withheld the prior) and a rendered disclosure. The connector's isolation is
labelled **in-session isolation** — attenuation, not elimination, because the transcript is shared.
The disclosure text is content, not code.

**The headline stability statistic is the weight-free dominance survival rate** — the fraction of
repeated matrices in which an alternative remains non-dominated — plus Pareto-set churn. Kendall's
tau-b and top-1 churn are the **secondary** report, computed only when the user has declared weights.
*(REASONING: [2] §8's primary statistic is tau over the induced ranking, which requires weights —
and comparanda refuses a weighted total by default. A stability report whose headline number needs
the thing the companion tool refuses to compute is architecturally wrong.)*

## Consequences
The two runtimes produce differently-qualified output from the same protocol, and the difference is
stated rather than hidden. The connector's flagship mitigation has **unknown magnitude** until the
harness runs — this is the highest-value open question in the project and it costs a few dollars.

## Alternatives considered
- *One policy for both runtimes.* Either bankrupts the connector or wastes the deployed agent.
- *Self-reported confidence as a stability proxy.* Verbalised self-confidence is systematically
  overconfident [18] and sampled agreement correlates only weakly with correctness [19].
- *Kendall's tau as the headline.* Needs weights the companion tool refuses to compute by default.
```

---

## 14. New ADR-0019 — all LLM access through the local `aix` facade

**Action:** new. **Reason:** the rule "no tool may require a model" is currently prose. This makes it
a **test**. EVIDENCE: from reading the local packages' source — every one of the six gaps listed is a
facade gap, not a capability gap, because the underlying library already supports all of it [35][36].

### Draft — ADR-0019

```markdown
# ADR-0019: All LLM access goes through the local aix facade, and an import test enforces it

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>

## Context
The deployed runtime needs model access; the connector must have none. Written as prose, that rule
erodes the first time a tool "just needs a quick classification". The local ecosystem already has a
facade over provider SDKs, and using it directly is the difference between one chokepoint for model
configuration and credentials, and many.

## Decision
**The deployed runtime never touches a provider SDK directly.** The local `aix` facade is the single
chokepoint for model configuration, credential resolution, aliases and scoped overrides.

**`rubricator.mcp` must never import `rubricator.agent`**, and a **subprocess import test asserts
that neither `aix` nor the underlying provider library appears in `sys.modules` after importing the
MCP layer.** That test is the mechanical enforcement of ADR-0003, and it is worth more than the rule
written in prose.

**The connector installs with no LLM dependency**; `pip install "rubricator[agent]"` adds `aix`.

**Six facade gaps must be filed against `aix`, and two closed before ADR-0008's variance work can
start**: a completion primitive that does not discard the response, a concurrent sampling primitive,
membership enforcement in the constrained-answer helper, provider-enforced structured output,
documented seed support with capability probing, and error propagation in the batch chat helper.
Every one is a facade gap, not a capability gap — the underlying library supports all of it [35][36]
— which is what makes fixing them upstream rather than wrapping around them obviously correct.

## Consequences
A cheap, fast connector install, and a single place to change model configuration. The cost is a
cross-repo dependency on `aix` landing two fixes, which is a scheduling risk on ADR-0008's variance
work — and a reason to file the issues before Phase 4 rather than during it.

## Alternatives considered
- *A provider SDK directly in `rubricator.agent`.* Duplicates credential and alias logic that already
  exists, and makes the import test harder to state.
- *Wrapping around the facade's gaps locally.* Puts the fix in the wrong repository, where the rest
  of the ecosystem cannot use it.
```

---

## 15. Confirmations — no edit needed beyond a status note

| ADR | Why it is confirmed |
|---|---|
| **ADR-0001** | The numbering discipline is what let seven independently-written research sections converge without collision; the collisions that did occur were resolvable because the rule existed. |
| **ADR-0002** | The boundary held under pressure. Every schema need the research found is a **request** to comparanda, and the validation mechanism is unchanged. |
| **ADR-0003** | Its central mechanism is now verified end to end: MCP prompts surface as slash commands and resources as `@` mentions [8]; every check and statistic in the findings is a deterministic tool plus a prompt; and the deprecation of MCP sampling [4] removes the only tempting exception to "no tool may require a model". |
| **ADR-0006** | Strengthened from four directions — deployed citation support rates of 51.5% / 74.5% [28] are the empirical case for the whole policy; verbalised self-confidence is overconfident [18]; sampled agreement correlates weakly with correctness [19]; and the enum-versus-constraint analysis shows the policy needs **enforcement**, not revision. Its missing enforcement rules go into ADR-0012 and ADR-0015, not into a superseding ADR. |

---

## Not actions for this repository

Recorded here so they are not lost, but they belong to `comparanda` (per ADR-0002, rubricator files
these as **requests**, never as changes it can make):

| Request | Why |
|---|---|
| Criteria carry a **structured definition** (objective, question, scale anchors, evidence rule, missing rule, exclusions), not free text | ADR-0006's guarantee is *defined* by the criterion and *exercised* by the cell; today it is expressible only at the cell level |
| Criteria sets are **versioned**; every measure records the criterion version it was scored against | ADR-0016. Cheap now, impossible to retrofit honestly later |
| Criteria carry **provenance**, and **rejected** criteria with reason codes ship with the analysis | ADR-0016 |
| Assertions carry `authorKind`, `independence`, `perturbation`; analyses carry a `procedure` record; `mode` joins the reduction enum | Five draws of one model must never render as five raters. `independence` is the most important field in this table |
| Evidence references carry `stance` and `sourceType`, plus `derivedFrom`, `quoteHash` and a tool-written `check` | ADR-0015 |
| Confirm the criterion `preference` (direction) field | Dominance and veto screening are undefinable without a direction of preference |
| A `missing` reason for `insufficient_evidence_to_discriminate` | The negative case of ADR-0011's pairwise escalation rule has no existing code |

---

## REFERENCES

1. [Findings — comparison method and prompting (2026)](../research/findings-method.md) — in this repository
2. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](../research/scoring-order-effects.md) — in this repository
3. [FastMCP — Elicitation (2026)](https://gofastmcp.com/servers/elicitation)
4. [MCP — Deprecated Features registry, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
5. [Let Me Speak Freely? A Study On The Impact Of Format Restrictions On Large Language Model Performance — Tam, Wu, Tsai, Lin, Lee & Chen (2024), EMNLP Industry Track](https://aclanthology.org/2024.emnlp-industry.91/)
6. [Say What You Mean: A Response to 'Let Me Speak Freely' — .txt Engineering (2024)](https://blog.dottxt.ai/say-what-you-mean.html)
7. [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models — Geng, Cooper, Moskal et al. (2025)](https://arxiv.org/abs/2501.10868)
8. [Connect Claude Code to tools via MCP — Anthropic Claude Code documentation](https://code.claude.com/docs/en/mcp)
9. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2) — *cite v2 specifically*
10. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
11. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — Zheng, Chiang, Sheng et al. (2023), NeurIPS](https://arxiv.org/abs/2306.05685)
12. [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation — Yagubyan (2026)](https://arxiv.org/abs/2606.13685)
13. [On the Theory of Scales of Measurement — Stevens (1946), Science 103(2684):677–680](https://doi.org/10.1126/science.103.2684.677) — *paywalled; paraphrased from secondary summaries, not quoted*
14. [Elo Uncovered: Robustness and Best Practices in Language Model Evaluation — Boubdir, Kim, Ermis, Hooker & Fadaee (2023)](https://arxiv.org/abs/2311.17295)
15. [On Extending the Bradley-Terry Model to Accommodate Ties in Paired Comparison Experiments — Davidson (1970), JASA 65:317–328](https://doi.org/10.1080/01621459.1970.10481082)
16. [Comparative judgement as a research tool: A meta-analysis of application and reliability — Kinnear, Jones & Davies (2025), Behavior Research Methods 57(8):222](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246014/)
17. [Grading Scale Impact on LLM-as-a-Judge: Human–LLM Alignment Is Highest on 0-5 Grading Scale — Li et al. (2026)](https://arxiv.org/abs/2601.03444)
18. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
19. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065) — *single-author preprint; weak evidence*
20. [MCP — Elicitation, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)
21. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf)
22. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985)
23. [Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences — Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran & Arawjo (2024), UIST '24](https://arxiv.org/abs/2404.12272)
24. [Web Annotation Data Model — Sanderson, Ciccarese & Young, W3C Recommendation (2017)](https://www.w3.org/TR/annotation-model/)
25. [Text Fragments — WICG Draft Community Group Report (2023)](https://wicg.github.io/scroll-to-text-fragment/)
26. [RFC 5147: URI Fragment Identifiers for the text/plain Media Type — Wilde & Duerst, IETF (2008)](https://www.rfc-editor.org/rfc/rfc5147.html)
27. [Evaluating Chunking Strategies for Retrieval — Chroma Research (2024)](https://www.trychroma.com/research/evaluating-chunking)
28. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
29. [Introduction to Primary Sources — History, Philosophy and Newspaper Library, University of Illinois](https://www.library.illinois.edu/hpnl/tutorials/primary-sources/)
30. [CiTO, the Citation Typing Ontology — Peroni & Shotton, SPAR Ontologies](https://sparontologies.github.io/cito/current/cito.html)
31. [MCP — Tasks extension overview (2026)](https://modelcontextprotocol.io/extensions/tasks/overview)
32. [AttributionBench: How Hard is Automatic Attribution Evaluation? — Li et al. (2024)](https://arxiv.org/abs/2402.15089)
33. [Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs — Aggarwal, Madaan, Yang & Mausam (2023), EMNLP](https://arxiv.org/abs/2305.11860)
34. [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs — Loo (2025)](https://arxiv.org/abs/2511.00751)
35. [LiteLLM — Input Params for completion()](https://docs.litellm.ai/docs/completion/input)
36. [LiteLLM — JSON Mode and Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode)
