# Roadmap

**The GitHub issues are the live source of truth.** This file is the map: it says what the epics
are, in what order, what each one unblocks, where the gates are, and what gets cut first when time
runs out. When an issue and this file disagree, the issue is right — and this file should be
corrected in the same PR.

It elaborates [`BRIEF.md`](../BRIEF.md)'s six phases with what round-1 research found. The evidence
behind every decision is in [`docs/research/findings-method.md`](./research/findings-method.md); the
decisions themselves are in [`docs/adr/`](./adr/), once Phase 0 lands them.

Anything involving both repositories — the gates, the schema-request protocol, the version handshake,
where fixtures live — is specified once, in `comparanda: docs/cross-repo-coordination.md`. That file
is canonical and is **not** copied here; where it and this map disagree, it wins.

---

## The spine

| # | Epic | Phase | Unblocks | Gate |
|---|---|---|---|---|
| 1 | Settle the ADRs | 0 | Everything. ADR-0004's supersession is order-1 and blocks Phases 1, 3 and 5 | `none` |
| 2 | Cross-repo schema requests | 0 | The schema freeze that Phase 1 validation and Phase 4 metrics depend on | `none` |
| 3 | Upstream dependencies (`aix`, `py2mcp`) | 0 | Phase 4 variance work and Phase 5's runtime. Two `aix` gaps are hard blockers | `none` |
| 4 | Open research questions | 0 | Phase 2 (anchors), Phase 3 (client capabilities), Phase 4 (harness arms) | `none` |
| 5 | Repository scaffolding and CI | 1 | Every line of code, and the two tests that make ADR-0003 mechanical | `none` |
| 6 | The MCP tool surface | 1 | Phases 2–5. The core artifact of the whole project | `none` (it *produces* `tool-surface`; two of its issues carry `schema-v1`) |
| 7 | Prompts | 2 | Phase 3's first real analysis; Phase 4 has nothing to measure without them | `none` at epic level; `tool-surface` on the issues that bind to a signature |
| 8 | The connector | 3 | The product. Phases 4 and 5 both run against it | `none` at epic level; `tool-surface` on the issues that wire tools to the server |
| 9 | Evaluation | 4 | Every prompt change after it. Without it, prompt edits are prompt churn | `none` at epic level; `eval-suite` on the conformance arms |
| 10 | Variance and uncertainty | 4 | The connector's honesty claim, and the deployed runtime's defaults | `none` |
| 11 | Deployed agent and CLI | 5 | Unattended runs. Legitimately the last thing | `none` |

### Gates

Three, shared with `comparanda` and specified in `comparanda: docs/cross-repo-coordination.md` §1.
A gate is the value of an issue's or epic's `gate` field — **not a label**; neither repository's
label set contains a gate name. The value is one of `tool-surface`, `schema-v1`, `eval-suite` or
`none`, spelled exactly. There is no such value as "partly" a gate: when only some issues in an epic
are blocked, the gate goes on those issues and the epic stays `none`.

- **`tool-surface`** — **owned here.** Passes when the Phase 1 tool contracts are frozen — names,
  signatures, the minimum viable subset — and one issue states that the schema-request set is
  complete as of that surface. Its only cross-repo consumer is `comparanda`'s intake close.

  **It gates far less here than a first reading suggests.** It applies to the specific work that
  binds to a frozen signature: a prompt that names a tool's arguments, the server wiring that
  registers the tools, and the harness arms that call them. It does **not** gate prompt drafting, the
  corpus tools, the citation ladder, the traversal planner, the connector scaffolding or the
  evaluation-harness design — all of which run in parallel and are enumerated in
  `comparanda: docs/cross-repo-coordination.md` §2.2. Gating those epics wholesale would stall
  roughly the whole of Phases 2–4 behind a freeze that does not constrain them.

- **`schema-v1`** — owned by `comparanda`; passes when it has closed request intake and published its
  versioned JSON Schema artifact. Applies here to `analysis_validate` and `measures_write` against the
  *real* schema, the `rubricator://schema/comparanda/{version}` resource, the declared `EMITS` set,
  and any claim of conformance. Everything else builds against the domain model plus a hand-written
  sketch, exactly as `BRIEF.md` instructs — see the `SchemaSource` facade below, which is what makes
  that safe.

- **`eval-suite`** — owned jointly. Passes when every fixture in either repository that *is* a
  comparanda document validates in that repository's CI against a pinned schema version, this
  repository emits a real analysis that validates strict, `comparanda` renders every shared fixture
  without a runtime error, and the schema-validity, citation-faithfulness and refusal-to-guess arms
  run against them. It gates the `1.0.0` release and the demo being called done — not development.

**The one indirection that keeps the parallelism honest.** All validation goes through a single
`SchemaSource` facade with two implementations, `SketchSchema` and `PublishedSchema(version)`, over a
hand-written provisional sketch of the comparanda document in the domain-model vocabulary. Nothing
else in the codebase names a schema file, so the swap at `schema-v1` is one line at the composition
root, and `diff(sketch, published)` is the enumerable list of what changed. Without it this
repository's chain begins where `comparanda`'s ends and the path to a demo roughly doubles. It is the
assumption most likely to be quietly dropped under pressure, so it needs its own issue.

---

## Epic by epic

### 1. Settle the ADRs (Phase 0)

Fifteen issues, in the order `docs/adr/README.md` already
established — ordered by how much downstream work each unblocks, not by ADR number. Two ADRs
(0004, 0007) entered the epic `proposed`; the research was commissioned to settle them, and both are
now settled — 0004 superseded by ADR-0009, 0007 accepted. Four issues were marked
`decision-needed` because they are genuinely contested rather than merely undecided:

- **ADR-0009** (supersede vs amend ADR-0004) — the research explicitly leaves the mechanism to a
  human, though it makes a definite recommendation;
- **ADR-0007** — entered `proposed`; its sequence survives but its item count does not;
- **ADR-0012** — its 1–5 scale decision **overrides** the owner's own prior recommendation to widen
  to 1–10;
- **ADR-0018** — its headline stability statistic **replaces** the owner's Kendall-τ proposal,
  because τ needs weights the companion tool refuses to compute by default.

**No number was allocated, and none is needed.** The pending list settled the ADR-0005 step-4
checkpoint by adding *a new ADR that cites ADR-0005 as parent* — but 0009 through 0019 were all
claimed by the other fourteen items. It was folded into ADR-0005 as a dated amendment instead of
taking 0020, which ADR-0005 and `docs/adr/README.md` both record. There is no numbering gap and
nothing to allocate; 0020 remains the first free number for the next genuinely new decision.

The epic finished by deleting `PENDING-ACTIONS.md`. A pending list that outlives its pendency
becomes a second source of truth.

### 2. Cross-repo schema requests (Phase 0)

Seven requests to `comparanda`, per ADR-0002 — requests, never changes this repo can make. The
important ones are `independence` on assertions (without it, five draws of one model render as five
raters) and `stance` on evidence references (without it, contradicting evidence is unrepresentable
and therefore uncountable). Each is filed here with a concrete JSON fragment **and the fallback if it
is rejected** — a request with no stated fallback is a demand — and mirrored into `comparanda`,
which records the disposition. Mirror-issue keys must be unique across `comparanda`'s whole roadmap,
not just its cross-repo epic; `schema-criterion-preference` is already taken there by the
implementation issue, so the mirrors take a `request-` prefix and the `{{comparanda:…}}` references
here must match exactly.

**Traffic in the other direction, which is not a request and is easy to miss.** `comparanda`'s
ADR-0009 amendment **renames** two missingness codes — `pending` → `deferred`, `unknown` →
`indeterminate` — and adds `not-evidenced`. This repository's ADR drafts, prompts and evaluation
metric names are written against the old spellings (`unknown_preference_rate`, the
always-returns-`unknown` degenerate-agent counter-metric, the resume semantics keyed on
`not-assessed` / `pending` / `unknown`). **That disposition has now been recorded** — `comparanda`'s
ADR-0009 amendment of 2026-08-21, with the six-code core set shipping in its code and domain model —
so the embargo on writing a code literal is lifted and ADR-0017's amendment discharges the
conditionals in the ADR set. One issue here still tracks the prose sweep, which is a **per-site
mapping and never a search-and-replace**: `unknown` resolves to `not-evidenced` where the sources
are silent and to `indeterminate` where they do not settle the level.
`comparanda: docs/cross-repo-coordination.md` §7.1.

### 3. Upstream dependencies (Phase 0)

Six facade gaps in the local `aix` package and two in `py2mcp` — `prompts=` / `resources=` kwargs on
the builders, and a FastMCP 4 version floor. They become issues in *those*
repos; this repo carries a tracking issue recording which gap blocks which phase. One of them is
not a gap but a live correctness bug: `constrained_answer` type-coerces its answer and never checks
membership in the allowed set, so an out-of-set reply is returned as valid — which is exactly the
anchored-criterion-level case.

### 4. Open research questions (Phase 0)

The cheap, decisive experiments the ledger carries. Three of them are one afternoon each. The
client-capability probe should be the first thing the connector phase does, because the
confirmation checkpoint's fallback path either matters enormously or not at all depending on the
answer. The anchors-on/off ablation should run **before** anchors are written at scale.

The single highest-value unknown — how much of cell-wise isolation survives a shared transcript —
is executed by the traversal harness in epic 10, not here, because it is the same code.

### 5. Repository scaffolding and CI (Phase 1)

Package layout on the ecosystem's conventions, CI, and the two tests that turn prose rules into
mechanism:

- a **subprocess import test** asserting that neither the LLM facade nor its underlying provider
  library appears in `sys.modules` after importing the MCP layer — the mechanical enforcement of
  "the tool layer never imports the model-access layer";
- a **public-repo hygiene check**, mirroring the companion repo's equivalent, run in CI over code,
  fixtures, prompts and docs.

### 6. The MCP tool surface (Phase 1)

Nineteen tools, eleven minimum viable, over a core of plain deterministic functions that know
nothing about MCP. Every issue carries its determinism justification, because that is the property
under pressure. Two granularities stay separated on purpose: *generation* granularity is one cell
per generation (the prompt's business), *write* granularity accepts a batch (the tool's business).

The minimum viable set is `analysis_open`, `analysis_get`, `corpus_add`, `corpus_search`,
`frame_set`, `alternatives_set`, `criteria_set`, `frame_confirm`, `plan_traversal`,
`measures_write`, `analysis_validate` — plus `check_citations`, which is not in the count but is not
cuttable either, because it is the product.

**One known divergence to close inside this epic.** `rubricator/tools/citations.py` ships three
rungs of the ADR-0014 ladder under its own status names — `verified` / `normalised` / `partial` /
`not-found` / `empty` — while ADR-0014 and tool 13 publish the verdict enum
`exact` / `normalised` / `fuzzy` / `moved` / `stale` / `unresolvable`, and ADR-0014's 2026-08-21
amendment retires `verified` outright. The names are not the whole of it: `verbatim_rate` there
counts only the strictest rung, where ADR-0008's `quote_verbatim_rate` gate counts
`verdict ∈ {exact, normalised}`; and `moved` / `stale` cannot be reached at all until the drift
step has document and quote hashes to compare. Closing it is a rename **plus** the missing rungs,
and until it closes the module's doctests assert a verdict the ADR no longer recognises.

### 7. Prompts (Phase 2)

Ten prompt files as versioned content. `propose-criteria` is drafted first and hardest: it is the
highest-leverage prompt in the system, and the criteria discussion is the part of the product users
actually value. `score-cell` is the default and `score-column` is demoted to a harness arm; the prompts
README has been corrected to say so, and the prompt table in
`docs/research/sections/r6-mcp-and-agent-architecture.md` is left as the evidence trail.

Medium detail from here: the deliverables are known, the wording is not.

### 8. The connector (Phase 3)

MCP server, both transports, prompts and resources served from the same files, the step-4
confirmation checkpoint with its degraded path, and analyses that survive a session boundary.
Placeholder-level detail — enough to be a real placeholder, not enough to pretend we know.

### 9. Evaluation (Phase 4)

ADR-0008's six checks, as amended. Two of the six are, as originally written, passed perfectly by a
degenerate agent: "stability" by one that always returns 3, "refusal to guess" by one that always
returns `unknown`. Each needs a paired discrimination counter-metric. And the calibration item is
**not computable as written** — no proper scoring rule exists over an ordinal evidence-quality
label — so it splits into discrimination over `confidence` and proper scoring over an optional
`certainty` measure elicited only in evaluation runs.

### 10. Variance and uncertainty (Phase 4)

Its own epic, not a corner of evaluation. Three jobs: **mitigate** traversal and sampling variance,
**quantify** what remains, and **disclose** it honestly per runtime. The deployed agent can spend
calls (k=5, adaptive early stop); the connector cannot and falls back to structural mitigations —
seeded traversal, server-side isolation, value-of-information re-scoring — plus a stated limit.

The traversal-comparison harness is a shippable seven-arm evaluation, not a one-off script. The
user-facing warning text is content, not code, and must say that human panels show the same effects
— otherwise it reads as "machines are uniquely bad", which is false and, because it invites
dismissal, useless.

### 11. Deployed agent and CLI (Phase 5)

All model access through the local `aix` facade; the connector installs with no LLM dependency at
all. Then a CLI, and the offline corpus-preparation step that is the only place an embedding index
is allowed to exist.

---

## What we would cut under time pressure

`BRIEF.md` asks for this by name. In cut order — first to go at the top.

1. **`fit_bradley_terry` and `compute_coupling_matrix`.** Both are already marked cut-first in the
   research. Pairwise is an escalation that is not built in v1 at all; coupling probes cost `3n²`
   judgements and are opt-in even when they exist.
2. **The deployed agent and the CLI (Phase 5 entirely).** The connector is the product for the
   primary user. Stopping after it is a legitimate outcome, and ADR-0007 says so.
3. **`score-column` and the harness arms that only exist to validate it.** Keep the default;
   defer the comparison that might overturn it.
4. **The `certainty` measure and Family-B proper scoring.** Evaluation-run-only already; the
   discrimination family (Family A) carries the release gate on its own.
5. **`disclose_variance` — but only if k > 1 is always used.** It is most needed at k = 1, which is
   the connector's normal case, so in practice this cut is unavailable.
6. **`stability_report` and `aggregate_assertions`, together.** Only if there are never repeats.
   Cutting one without the other leaves a reduction nobody can interpret.
7. **`measures_mark_missing`.** Only if you are willing to drop partial-fill instructions ("fill
   these two criteria, mark the rest pending"), which is a visible product regression.
8. **`report_weaknesses` — cut last.** Without it, ADR-0006's "self-critique is part of the
   deliverable" degrades to unaided model opinion, which is exactly the failure the evaluation suite
   exists to catch.

**Never cut**, whatever the schedule:

- `check_citations`. A citation nobody can check is not a citation, and a well-formatted matrix
  with wrong citations is worse than one with none, because the format certifies the content.
- The step-4 confirmation checkpoint. It is where the analysis becomes the user's rather than the
  model's, and it is the item under permanent pressure to remove.
- The refusal-to-guess evaluation. It is the behaviour most likely to erode under prompt edits, and
  it is the product's whole claim.
- The two boundary tests in epic 5. They cost nothing to keep and they are what makes the
  architecture survive a refactor by someone who has not read the ADRs.
