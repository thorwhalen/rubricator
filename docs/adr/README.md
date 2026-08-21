# Architecture decisions — index

**Read them in numeric order for the history; read them by theme for orientation.** The numbering is
chronological and records how the project argued its way to where it is — which ADR superseded which,
what was confirmed under pressure, what is still an amendment away from its original text. That order
is the wrong one for a newcomer who wants to know what this repository *does*. So the sections below
group the same twenty ADRs by what they govern, and the table at the end restores the numeric
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

## The runtimes, and what hosts them

| # | Title | Status | What it decides |
|---|---|---|---|
| [0003](0003-mcp-as-the-shared-core.md) | One MCP tool specification, two runtimes | accepted | The tool specification is the shared core, with a keyless connector runtime and a deployed agent runtime over it. **Tools are deterministic, the loop is not** — no tool may require a model. |
| [0004](0004-python-first-with-aw-agents.md) | Python for the agent runtime, on `aw_agents`; JS/TS deferred | **superseded by [0009](0009-python-official-mcp-sdk.md)** | Recommended the local `aw_agents` framework as host, conditional on reading its source. Kept readable as the question that was asked. |
| [0009](0009-python-official-mcp-sdk.md) | Python, the official MCP SDK, and the rejection of `aw_agents` as host | accepted | Python for both runtimes, on the official MCP Python SDK / FastMCP 4 — the version floor that carries ADR-0005's elicitation. A surface of 19 tools, 11 minimum viable, over plain deterministic functions that know nothing about MCP. |
| [0019](0019-llm-access-through-the-aix-facade.md) | All LLM access goes through the local `aix` facade | accepted | One chokepoint for model configuration and credentials, enforced by an import test asserting the MCP package pulls in no LLM library. Six facade gaps go upstream; two block the variance work. |

## What a tool is allowed to do

| # | Title | Status | What it decides |
|---|---|---|---|
| [0010](0010-the-determinism-boundary.md) | The determinism boundary | accepted | Turns ADR-0003's prose rule into a boundary a reviewer can hold a diff against: no MCP sampling, no in-tool model *or embedding* calls, lexical retrieval with a versioned tokenizer, stopword list and chunker, and the corpus inlined only at the enumeration stage under a named threshold. |
| [0013](0013-structured-output-and-schema-subset.md) | Structured output, and the JSON Schema subset the tool surface may use | accepted | Every judgement arrives through grammar-constrained sampling, with the reasoning field declared *before* the value fields. A seven-point checklist constrains tool signatures to the subset providers actually enforce; range checks move into the deterministic validator. |

## The method — eliciting the frame, and keeping it alive across sessions

| # | Title | Status | What it decides |
|---|---|---|---|
| [0005](0005-the-elicitation-pipeline.md) | Elicit the frame before scoring anything | accepted | Six stages — frame, enumerate alternatives, propose criteria, **confirm with the user**, populate, review. The amendment specifies step 4 as an MCP elicitation carrying a flat three-field form, with a chat-plus-record fallback, stored as authored timestamped provenance. The tool never confirms on its own behalf. |
| [0016](0016-criteria-are-revisable.md) | Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door | accepted | Criteria sets carry a version and every measure records the version it was scored against. A **material** bump (a change to `question`, `level`, `range`, `preference`, `exclusions` or `anchors`) invalidates the cells scored under the old definition — `missing`, reason `superseded-by-revision`, prior measures retained; an **editorial** bump re-stamps and invalidates nothing. Rejected criteria ship with the analysis. |
| [0017](0017-durable-partial-analyses.md) | An in-progress analysis is a durable partial comparanda document | accepted | rubricator owns a store keyed by an opaque `analysis_id`, and the stored record is itself a schema-valid `comparanda` analysis. The closed missingness set carries the resume semantics, so resumption costs no schema surface. Retention runs from last write, and export defeats it. |

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
| [0018](0018-variance-mitigation-per-runtime.md) | Variance-mitigation policy per runtime, and the independence ladder | accepted | One protocol, two budgets: the deployed runtime repeats with adaptive early stopping, the connector spends its budget on review and re-scoring pivotal cells. Every assertion carries its **independence rung**, and an agreement statistic is labelled by the lowest rung present. The headline stability number is weight-free dominance survival. |

## Knowing whether any of it works

| # | Title | Status | What it decides |
|---|---|---|---|
| [0008](0008-evaluation.md) | The agent needs an evaluation suite, and it is not optional | accepted | Build the suite alongside the agent and evaluate only what can be checked. The amendment turns each check into a named metric at a named tier, pairs the two checks a degenerate agent would pass with discrimination counter-metrics, splits calibration into discrimination over `confidence` and proper scoring over `certainty`, tiers the citation checks, and names three fixture families and seven harness arms. |

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
| [0009](0009-python-official-mcp-sdk.md) | Python, the official MCP SDK, and the rejection of `aw_agents` as host | accepted (supersedes 0004) |
| [0010](0010-the-determinism-boundary.md) | The determinism boundary | accepted |
| [0011](0011-the-scoring-protocol.md) | The scoring protocol — pointwise, cell-wise, evidence first | accepted (amended) |
| [0012](0012-measurement-scales-confidence-and-the-two-uncertainties.md) | Measurement scales, what confidence means, and the two uncertainties | accepted (amended) |
| [0013](0013-structured-output-and-schema-subset.md) | Structured output, and the JSON Schema subset the tool surface may use | accepted |
| [0014](0014-evidence-reference-locator-profile.md) | The evidence-reference locator profile, and deterministic citation checking | accepted (amended) |
| [0015](0015-source-type-stance-and-derived-from.md) | Source type, stance, and the constraint that stops inference passing as source | accepted |
| [0016](0016-criteria-are-revisable.md) | Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door | accepted (amended) |
| [0017](0017-durable-partial-analyses.md) | An in-progress analysis is a durable partial comparanda document | accepted (amended) |
| [0018](0018-variance-mitigation-per-runtime.md) | Variance-mitigation policy per runtime, and the independence ladder | accepted |
| [0019](0019-llm-access-through-the-aix-facade.md) | All LLM access goes through the local `aix` facade | accepted |

Numbers 0009–0019 were allocated in a single sequence when round-1 research landed, which is why they
are all dated together and why several of them cite ADR-0006 as a parent rather than superseding it.
ADR-0005's step-4 mechanism was folded into that ADR as an amendment rather than given a number of its
own; there is no gap.

`PENDING-ACTIONS.md` has been applied and removed. Where any research document disagrees with an
ADR, the ADR wins.
