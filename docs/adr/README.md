# Architecture decisions — index

**Read them in numeric order for the history; read them by theme for orientation.** The numbering is
chronological and records how the project argued its way to where it is — which ADR superseded which,
what was confirmed under pressure, what is still an amendment away from its original text. That order
is the wrong one for a newcomer who wants to know what this repository *does*. So the sections below
group the same twenty-six ADRs by what they govern, and the table at the end restores the numeric
sequence for anyone reading the history.

Every ADR is Nygard-format, numbered, and immutable once accepted (ADR-0001). A reversal arrives as a
**superseding** ADR; a correction or addition short of a reversal arrives as a dated `## Amendments`
section on the original, leaving its Context, Decision and Consequences untouched. `0000-template.md`
is the blank.

Vocabulary throughout is `comparanda`'s: **alternatives** (rows), **criteria** (columns), **subject**,
**measure** (stored — score, confidence), **encoding** (view-layer, derived), **missing** (always with
a reason).

---

## How decisions are recorded, and where the repository boundary runs

| # | Title | Status | What it decides |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | accepted | Nygard-format ADRs, numbered and immutable; supersede rather than edit, amend for anything short of a reversal, and settle a `proposed` ADR in place with the reasoning recorded. |
| [0002](0002-separation-from-comparanda.md) | Separate repository, joined only by the schema | accepted | Two repositories coupled only by `comparanda`'s published JSON Schema, validated at the boundary. Every schema need this repo finds is a *request* across the boundary, never a change it can make. |
| [0007](0007-outputs-and-packaging.md) | Deliverables and packaging | accepted | Ship in order: MCP server with prompts included, then the Python package, then the CLI. Serving MCP prompts *is* the prompt bundle, so there is no second artifact to keep in sync. |
| [0020](0020-the-composition-root-and-the-seam-discipline.md) | One composition root, and what makes a seam a seam | accepted | Every seam is a keyword argument of `build_runtime`; no tool constructs its own dependency and no module self-registers. Prefer a **row** to a class, because a row crosses the language boundary and an interface does not. A default that leaks through its own interface is not a seam, and every seam ships a test that **fails when the default is replaced**. |

## The runtimes, and what hosts them

| # | Title | Status | What it decides |
|---|---|---|---|
| [0003](0003-mcp-as-the-shared-core.md) | One MCP tool specification, two runtimes | accepted | The tool specification is the shared core, with a keyless connector runtime and a deployed agent runtime over it. **Tools are deterministic, the loop is not** — no tool may require a model. |
| [0004](0004-python-first-with-aw-agents.md) | Python for the agent runtime, on `aw_agents`; JS/TS deferred | **superseded by [0009](0009-python-official-mcp-sdk.md)** | Recommended the local `aw_agents` framework as host, conditional on reading its source. Kept readable as the question that was asked. |
| [0009](0009-python-official-mcp-sdk.md) | Python, the official MCP SDK, and the rejection of `aw_agents` as host | accepted (amended) | Python for both runtimes, on the official MCP Python SDK / FastMCP. A surface of 19 tools, 11 minimum viable, over plain deterministic functions that know nothing about MCP. The amendment drops the pin to `>=3.4` — there is no stable 4.x — keeps the elicitation rationale, and adopts `py2mcp` as the builder for both surfaces. |
| [0019](0019-llm-access-through-the-aix-facade.md) | All LLM access goes through the local `aix` facade | accepted (amended) | One chokepoint for model configuration and credentials, enforced by an import test asserting the MCP package pulls in no LLM library. Six facade gaps go upstream; two block the variance work. The amendment makes it one seam with two adapters — `aix` for the key-holding runtimes, host sampling for the keyless connector — and strengthens the import test rather than weakening it. |

## What a tool is allowed to do

| # | Title | Status | What it decides |
|---|---|---|---|
| [0010](0010-the-determinism-boundary.md) | The determinism boundary | accepted (amended) | Turns ADR-0003's prose rule into a boundary a reviewer can hold a diff against: no MCP sampling, no in-tool model *or embedding* calls, lexical retrieval with a versioned tokenizer, stopword list and chunker, and the corpus inlined only at the enumeration stage under a named threshold. |
| [0013](0013-structured-output-and-schema-subset.md) | Structured output, and the JSON Schema subset the tool surface may use | accepted | Every judgement arrives through grammar-constrained sampling, with the reasoning field declared *before* the value fields. A seven-point checklist constrains tool signatures to the subset providers actually enforce; range checks move into the deterministic validator. |
| [0021](0021-extension-vocabularies-are-data.md) | Extension vocabularies are data — one resolver, `broader` degradation, reported | accepted | Settles the shape ADR-0012's amendment deferred. A closed core enum, an open string at the point of use, a declaration in the document, one resolver — and a `Degradation` record so a reader learns what its build could not interpret. **Reading never raises; authoring does.** No `MeasurementScale` protocol, and an absent `scale` is never stamped with the default. |
| [0024](0024-boundary-validation-two-rule-families.md) | Two rule families — honesty rejects, completeness informs | accepted | The family determines the severity, so a rule cannot choose it. Every problem carries a **required** `fix` and a stable `rule_id`. `strict=False` drops completeness only: **honesty rules can never be suppressed**, by any flag, ruleset, configuration or deployment. |

## The method — eliciting the frame, and keeping it alive across sessions

| # | Title | Status | What it decides |
|---|---|---|---|
| [0005](0005-the-elicitation-pipeline.md) | Elicit the frame before scoring anything | accepted | Six stages — frame, enumerate alternatives, propose criteria, **confirm with the user**, populate, review. The amendment specifies step 4 as an MCP elicitation carrying a flat three-field form, with a chat-plus-record fallback, stored as authored timestamped provenance. The tool never confirms on its own behalf. |
| [0016](0016-criteria-are-revisable.md) | Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door | accepted | Criteria sets carry a version and every measure records the version it was scored against. A **material** bump (a change to `question`, `level`, `range`, `preference`, `exclusions` or `anchors`) invalidates the cells scored under the old definition — `missing`, reason `superseded-by-revision`, prior measures retained; an **editorial** bump re-stamps and invalidates nothing. Rejected criteria ship with the analysis. |
| [0017](0017-durable-partial-analyses.md) | An in-progress analysis is a durable partial comparanda document | accepted | rubricator owns a store keyed by an opaque `analysis_id`, and the stored record is itself a schema-valid `comparanda` analysis. The closed missingness set carries the resume semantics, so resumption costs no schema surface. Retention runs from last write, and export defeats it. |
| [0023](0023-the-store-two-targets-and-a-one-way-projection.md) | One bytes mapping, two targets, and a projection that is write-only by type | accepted | The persistence interface is `MutableMapping[str, bytes]` and nothing else is invented. One file per contributor makes two writers collision-free, which is what lets a shared GitHub repository be the filesystem code path with a different root. The GitHub Discussions/Issues projection has **no read method**, so "never read back as truth" is a type rather than a comment. |

## Honest uncertainty — the product's central claim

| # | Title | Status | What it decides |
|---|---|---|---|
| [0006](0006-evidence-and-honest-uncertainty.md) | Cite spans, and prefer a qualified blank to a confident guess | accepted | The parent of this whole group. Every asserted value carries a confidence and, where possible, span-level evidence; a qualified blank is a first-class outcome; confidence means **evidence quality, not model certainty**; primary source, secondary summary and the agent's own inference stay distinguishable; self-critique is part of the deliverable. |
| [0012](0012-measurement-scales-confidence-and-the-two-uncertainties.md) | Measurement scales, what confidence means, and the two uncertainties | accepted | States the consequences ADR-0006 left unstated. `score` is a 1–5 ordinal with anchors at levels 1/3/5, hashed with the criterion as a change detector — comparability keys on the criterion's last **material** version (ADR-0016); three enforcement rules bind `confidence`; `certainty` is an evaluation-only measure; evidential confidence (stored) and procedural stability (derived) are separated permanently. |
| [0014](0014-evidence-reference-locator-profile.md) | The evidence-reference locator profile, and deterministic citation checking | accepted | Says what a span *is*: a narrowed W3C Web Annotation selector profile where a `TextQuoteSelector` is mandatory and **positions are hints, quotes are truth**. Chunks stay out of the citation path, normalisation is versioned, and `check_citations` is a deterministic eight-step ladder returning a graded verdict — `exact`/`normalised`/`fuzzy`/`moved`/`stale`/`unresolvable` — that the model never writes. |
| [0015](0015-source-type-stance-and-derived-from.md) | Source type, stance, and the constraint that stops inference passing as source | accepted | Gives ADR-0006's "distinguish source types" a mechanism. `source_type` sits on the reference (five members, including `agent-inference`); an orthogonal `stance` records supports / contradicts / qualifies / background; three deterministic constraints make the rule checkable, including agent-authored documents being forced to `secondary` at best. |

## Scoring, and the variance that remains

| # | Title | Status | What it decides |
|---|---|---|---|
| [0011](0011-the-scoring-protocol.md) | The scoring protocol — pointwise, cell-wise, evidence first | accepted | One criterion per generation against a 5-point anchored rubric, traversal supplied by a seeded tool permutation, evidence extracted **before** the score is reached. Repeats reduce by lower median; a polarised cell gets no point value at all; pairwise is escalation-only behind four conditions, and the negative branch — a qualified blank — is the product. |
| [0018](0018-variance-mitigation-per-runtime.md) | Variance-mitigation policy per runtime, and the independence ladder | accepted (amended) | One protocol, two budgets: the deployed runtime repeats with adaptive early stopping, the connector spends its budget on review and re-scoring pivotal cells. Every assertion carries its **independence rung**, and an agreement statistic is labelled by the lowest rung present. The headline stability number is weight-free dominance survival. |
| [0022](0022-contributors-personas-principals-and-attestation.md) | A persona is an Author; a principal is who is behind it; an attestation is how well we know | accepted | Supplies the mechanism for ADR-0018's rule that a persona is not an independence rung: `principalId`, `actingAs` and an `attestation` method, with `effectiveIndependence` collapsing personas that share a principal. `author_id` is deterministic from (principal, persona) because it is a filename. `unverified` is the honest default. |

## Knowing whether any of it works

| # | Title | Status | What it decides |
|---|---|---|---|
| [0008](0008-evaluation.md) | The agent needs an evaluation suite, and it is not optional | accepted | Build the suite alongside the agent and evaluate only what can be checked. The amendment turns each check into a named metric at a named tier, pairs the two checks a degenerate agent would pass with discrimination counter-metrics, splits calibration into discrimination over `confidence` and proper scoring over `certainty`, tiers the citation checks, and names three fixture families and seven harness arms. |

## What we deploy, and what it may own

| # | Title | Status | What it decides |
|---|---|---|---|
| [0025](0025-the-rubricator-application.md) | The `rubricator` application — Preact, one data port, text-only encoding | accepted | The second v1 surface. One `DataProvider<Analysis>` port rather than five, one plain props shape defined in `comparanda`, and `text-only` as v1's only encoding because a colour palette's arity contradicts a pluggable scale. Files own everything durable; the browser owns only a cached response and disposable preferences. |

---

## Numeric order, for the history

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | accepted (amended) |
| [0002](0002-separation-from-comparanda.md) | Separate repository, joined only by the schema | accepted (amended) |
| [0003](0003-mcp-as-the-shared-core.md) | One MCP tool specification, two runtimes | accepted (amended) |
| [0004](0004-python-first-with-aw-agents.md) | Python for the agent runtime, on `aw_agents`; JS/TS deferred | superseded by 0009 |
| [0005](0005-the-elicitation-pipeline.md) | Elicit the frame before scoring anything | accepted (amended) |
| [0006](0006-evidence-and-honest-uncertainty.md) | Cite spans, and prefer a qualified blank to a confident guess | accepted (amended) |
| [0007](0007-outputs-and-packaging.md) | Deliverables and packaging | accepted (settled from proposed) |
| [0008](0008-evaluation.md) | The agent needs an evaluation suite, and it is not optional | accepted (amended) |
| [0009](0009-python-official-mcp-sdk.md) | Python, the official MCP SDK, and the rejection of `aw_agents` as host | accepted (supersedes 0004, amended) |
| [0010](0010-the-determinism-boundary.md) | The determinism boundary | accepted (amended) |
| [0011](0011-the-scoring-protocol.md) | The scoring protocol — pointwise, cell-wise, evidence first | accepted (amended) |
| [0012](0012-measurement-scales-confidence-and-the-two-uncertainties.md) | Measurement scales, what confidence means, and the two uncertainties | accepted (amended) |
| [0013](0013-structured-output-and-schema-subset.md) | Structured output, and the JSON Schema subset the tool surface may use | accepted |
| [0014](0014-evidence-reference-locator-profile.md) | The evidence-reference locator profile, and deterministic citation checking | accepted (amended) |
| [0015](0015-source-type-stance-and-derived-from.md) | Source type, stance, and the constraint that stops inference passing as source | accepted |
| [0016](0016-criteria-are-revisable.md) | Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door | accepted (amended) |
| [0017](0017-durable-partial-analyses.md) | An in-progress analysis is a durable partial comparanda document | accepted (amended) |
| [0018](0018-variance-mitigation-per-runtime.md) | Variance-mitigation policy per runtime, and the independence ladder | accepted (amended) |
| [0019](0019-llm-access-through-the-aix-facade.md) | All LLM access goes through the local `aix` facade | accepted (amended) |
| [0020](0020-the-composition-root-and-the-seam-discipline.md) | One composition root, and what makes a seam a seam | accepted |
| [0021](0021-extension-vocabularies-are-data.md) | Extension vocabularies are data — one resolver, `broader` degradation, reported | accepted |
| [0022](0022-contributors-personas-principals-and-attestation.md) | A persona is an Author; a principal is who is behind it; an attestation is how well we know | accepted |
| [0023](0023-the-store-two-targets-and-a-one-way-projection.md) | One bytes mapping, two targets, and a projection that is write-only by type | accepted |
| [0024](0024-boundary-validation-two-rule-families.md) | Two rule families — honesty rejects, completeness informs | accepted |
| [0025](0025-the-rubricator-application.md) | The `rubricator` application — Preact, one data port, text-only encoding | accepted |

Numbers 0009–0019 were allocated in a single sequence when round-1 research landed, which is why they
are all dated together and why several of them cite ADR-0006 as a parent rather than superseding it.
ADR-0005's step-4 mechanism was folded into that ADR as an amendment rather than given a number of its
own; there is no gap.

Numbers 0020–0025 were allocated together on 2026-08-22, when the v1 seam architecture settled eight
open decisions at once. Two of those decisions needed no new number and landed as amendments to
ADR-0012 and ADR-0018 — a scale that becomes a default with a declared seam, and a stability seam —
because they narrow rather than invert. Seven further amendments landed the same day, on ADR-0002,
0007, 0009, 0010, 0014, 0017 and 0019. **0026 is the next free number.**

`PENDING-ACTIONS.md` has been applied and removed. Where any research document disagrees with an
ADR, the ADR wins.
