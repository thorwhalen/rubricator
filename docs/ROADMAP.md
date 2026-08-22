# Roadmap

**The GitHub issues are the live source of truth.** This file is the map: what the epics are, in
what order, what each unblocks, and what gets cut first when time runs out. When an issue and this
file disagree, the issue is right — and this file is corrected in the same PR.

It elaborates [`BRIEF.md`](../BRIEF.md) with what round-1 research found and what the owner settled
on 2026-08-22. The evidence is in
[`docs/research/findings-method.md`](./research/findings-method.md); the decisions are in
[`docs/adr/`](./adr/), indexed by theme in [`docs/adr/README.md`](./adr/README.md).

Anything involving both repositories — the gates, the schema-request protocol, the version
handshake, where fixtures live — is specified once, in `comparanda: docs/cross-repo-coordination.md`.
That file is canonical and is **not** copied here; where it and this map disagree, it wins. Each
epic below carries only the *value* of its gate field.

---

## What v1 is

**A team arguing over a shared document, with a working slice end to end.** Not a solo tool that
grows collaboration later. Two surfaces over one core:

1. **A connector** — installable on Claude, no API key, built from a manifest of deterministic
   functions, serving the prompts and resources from the same content files.
2. **The `rubricator` application** — deployed, both to contribute opinions and to read the
   analysis. Named after the dependent, not the dependency (ADR-0025).

Behind both: **files are the single source of truth**, one file per contributor per analysis, behind
a facade whose filesystem and GitHub targets are the same code path with a different root
(ADR-0023).

## How v1 is built

The owner's process directive is a constraint on architecture, not on scheduling:

> "Think hard about the design so that the iterations mostly happen by ADDING code, hooking them up
> to existing seams, rather than redoing anything. Ideally the whole architecture is there from v1,
> just with simple components wired in the seams."

So this roadmap is **seam-first, then slice**. Epic 12 builds the seams with one simple component in
each. Epic 13 builds persistence and identity. Epics 14 and 15 make it visible. Everything after v1
is an *addition at a named seam* — a row in a table, one new function, or one argument at the
composition root — and ADR-0020 states the discipline that keeps that true, including the rule that
**a seam ships with a test that fails when its default is replaced**, not merely one that passes
with the default in place.

Three worked proofs, checked against the code rather than asserted:

- *"Price should be dollars, not a 1–5 score."* → one preset row and one declaration row in the
  document. **Nothing edited.** A reader that has never heard of the scale still dominates, screens
  and renders it, degrading through `broader` and saying so (ADR-0021).
- *"Move the team to a shared GitHub repo."* → one new store class; **one line changed** at the
  composition root. Zero call sites touched.
- *"We declared weights; show me rank stability."* → one strategy module and one row. **Nothing
  edited** — the envelope already carries the counter-metrics, and the precondition gate is in the
  wrapper.

---

## The spine

Epics 1–11 keep their numbers; four are re-scoped by the 2026-08-22 decisions, and 12–15 are new.

| # | Epic | v1? | Unblocks | Gate |
|---|---|---|---|---|
| 1 | Settle the ADRs | done | Everything | `none` |
| 2 | Cross-repo schema requests | **v1** | The freeze that validation and the metrics depend on. **Sixteen requests now, not seven** | `none` |
| 3 | Upstream dependencies (`aix`, `py2mcp`) | tracking | Phase-4 variance work only. **Nothing in v1** | `none` |
| 4 | Open research questions | parallel | The anchors ablation before anchors are written at scale | `none` |
| 5 | Repository scaffolding and CI | **v1** | Every line of code, and the boundary tests that make the rules mechanical | `none` |
| 6 | The MCP tool surface | **v1** | The core artifact. Thirteen tools on the v1 manifest | `none` (*produces* `tool-surface`) |
| 7 | Prompts | **v1**, partly | The slice needs `score-cell`; the other nine follow | `none` at epic level |
| 8 | The connector | **v1** | Surface 1 | `none` at epic level |
| 9 | Evaluation | after v1 | Every prompt change after it | `none` at epic level; `eval-suite` on the conformance arms |
| 10 | Variance and uncertainty | after v1 | The honesty claim, and the deployed runtime's defaults | `none` |
| 11 | Deployed agent and CLI | after v1, except one verb | Unattended runs | `none` |
| **12** | **The seam substrate and the composition root** | **v1** | Everything in 13–15. Nothing else can be added without redoing | `none` |
| **13** | **Persistence, contributors and the projection** | **v1** | Both surfaces, and the whole of the team story | `none` |
| **14** | **The `rubricator` application** | **v1** | Surface 2 | `none` |
| **15** | **The v1 vertical slice** | **v1** | The demo, and the only integration test the seams have | `none` |

### Gates

Three, shared with `comparanda` and specified in `comparanda: docs/cross-repo-coordination.md` §1.
A gate is the value of an issue's or epic's `gate` field — **not a label**; neither repository's
label set contains a gate name. The legal values are `tool-surface`, `schema-v1`, `eval-suite` and
`none`, spelled exactly. There is no such value as "partly" a gate: when only some issues in an epic
are blocked, the gate goes on those issues and the epic stays `none`. Read the canonical file for
what each one means; it is not restated here.

**The gaps worth naming.** `tool-surface` gates far less here than a first reading suggests — not
prompt drafting, the corpus tools, the citation ladder, the traversal planner or the harness design.
`schema-v1` applies only to validation against the *real* schema, the schema resource, the declared
`EMITS` set and any conformance claim. And **no gate covers persistence, the application, or
contributor identity**, which are three of the four things the 2026-08-22 decisions added. That is
tracked as a cross-repo coordination gap, not silently absorbed.

**The indirection that keeps the parallel track safe.** All validation goes through one
`SchemaSource` facade, over a hand-written provisional sketch of the comparanda document in the
domain-model vocabulary, with named constructors for the sketch and the published artifact. Nothing
else in the codebase opens a schema file — a rule **owed, not yet enforced**, as "no module outside
`rubricator/schema/` opens a `.json` file under `rubricator/`", replacing a check that grepped for
one filename and therefore could not fail (ADR-0010's 2026-08-22 amendment). The swap at `schema-v1`
is one argument at the composition root, and `diff(sketch, published)` is the enumerable list of
what changed. It is the assumption most likely to be quietly dropped under pressure, so it has its
own issue.

---

## Epic by epic

Epics 1, 4, 9, 10 and 11 are unchanged in substance from the previous map and are summarised
briefly; the rest carry what the 2026-08-22 decisions changed.

### 1. Settle the ADRs — done

The ADR set is settled. Two decisions landed as amendments earlier on 2026-08-22 (the scale seam in
ADR-0012, the stability seam in ADR-0018); the rest of the settlement lands as seven further
amendments — ADR-0002, 0007, 0009, 0010, 0014, 0017, 0019 — and six new ADRs, **0020–0025**. The
amendment mechanism has now been exercised on every kind of change it exists for: one supersession
on a true inversion (0004 → 0009), one settle-in-place (0007), and a run of narrowings.
**0026 is the next free number.**

### 2. Cross-repo schema requests (v1)

**Sixteen requests now, not seven** — the register lives in
`comparanda: docs/cross-repo-coordination.md` §7 and the nine new ones are tabulated in ADR-0002's
2026-08-22 amendment. Four of the nine block. One is time-critical in a way the others are not:
widening the reduction vocabulary from a closed `z.enum` costs one line before the schema freezes and
a migration through every stored analysis after, so it goes first. **Several of the nine were
disposed the same day**, in the companion repository and by it. What remains on this epic is the rest
of the register plus the dispositions themselves — recording a disposition is what closes a request,
not the commit that satisfies it.

Two clarifications the register needed. A request may be answered by **the document** rather than by
the schema — an extension declaration in our own analysis is the protocol working, not being
bypassed (ADR-0021). And the seven existing requests all carry an **empty disposition**, so the
intake gate is formally open even though the shipped schema visibly satisfies most of them;
recording those dispositions is a reading of existing code, not a feature.

**Traffic in the other direction, which is not a request.** `comparanda`'s missingness rename —
`pending` → `deferred`, `unknown` → `indeterminate`, plus the new `not-evidenced` — is landed there
and its disposition is recorded, so ADR-0017's 2026-08-21 amendment discharges the conditionals in
this repository's ADR set. **The sweep is done for the live sites, 2026-08-22:** `BRIEF.md`,
`docs/prompts/README.md`, both dev skills and the tool-surface table in
`docs/research/findings-method.md` read the current spellings; `analysis_get`'s resume view is
renamed `pending` → **`outstanding`**, since the view selects on the `terminal` flag and naming it
after one code was the same mistake one level up; and `measures_mark_missing` no longer enumerates
codes in its signature at all, validating instead against the analysis's own vocabulary — core six
plus declared extensions — because comparanda's set is **open**. Left alone deliberately: the dated
working notes under `docs/research/sections/`, and `rubricator/tools/traversal.py`, whose only match
is the English word in `unknown traversal order`. What remains is the part that is not a rename:
**`not-evidenced` needs a prompt that teaches the distinction and a fixture that exercises it**, or
an explicit decline.

### 3. Upstream dependencies — tracking only

**Nothing in v1 blocks on these.** The v1 connector's intelligence is supplied by Claude reading the
prompt files, so no tool calls a model and none of the six `aix` facade gaps is on the critical path.
That is a happy accident of the architecture and not a position to depend on twice: three of the six
still block the Phase-4 variance work, and one is a live correctness bug — `constrained_answer`
type-coerces its answer and checks neither membership nor bounds — sitting on the path of anchored
scoring, worked around behind ADR-0019's model seam and deleted the day it lands.

The connector-side dependency question is **closed** (ADR-0009's amendment): the builder returns a
live FastMCP object we decorate ourselves, and our own pin becomes `fastmcp>=3.4` — there is no
stable 4.x to pin to, and the declared `>=4.0.0` extra cannot install today. The upstream `prompts=`
/ `resources=` kwargs are still worth contributing and stay tracked.

### 4. Open research questions — parallel

The cheap, decisive experiments. The client-capability probe should be the connector phase's first
act, because the confirmation checkpoint's fallback path either matters enormously or not at all
depending on the answer. The anchors ablation runs **before** anchors are written at scale. The
scale-width arm now compares two *presets*, which is a fixture edit rather than an experiment design.

The single highest-value unknown — how much of cell-wise isolation survives a shared transcript — is
executed by the traversal harness in epic 10, not here, because it is the same code.

### 5. Repository scaffolding and CI (v1)

Package layout, CI, and the boundary tests that turn prose into mechanism. Three things are broken
today and all three are here: a declared console script pointing at a module that does not exist
(`rubricator.cli:main`); a prompts directory that is empty and untracked while the build ships it;
and an `mcp` extra pinning `fastmcp>=4.0.0`, a release that does not exist.

Two guards get stronger and one gets repaired (ADR-0010's amendment). The determinism boundary gains
an injected clock, `datetime` / `time` on its nondeterministic list beside `random` / `secrets` /
`uuid`, and a fourth denylist keeping every host framework and model client out of the tool and
schema layers — which is what makes the choice of MCP builder a one-file change. And the
schema-facade check stops grepping for a filename.

**Guards that could not fail are this repository's recurring defect**, first counted in ADR-0012's
2026-08-22 amendment. From here, a guard is not believed until it has been demonstrated red against
a deliberate violation, in the same PR that introduces it.

### 6. The MCP tool surface (v1)

Nineteen tools in the surface ADR-0009 adopts; **thirteen on the v1 manifest** — the eleven minimum
viable, plus `check_citations`, which is not in the count and is not cuttable either because it is
the product, plus `measures_mark_missing`. All of them over a core of plain deterministic functions
that know nothing about MCP. The surface **is** a manifest of function references
(`rubricator/surface.py::TOOL_REFS`), and the determinism tests walk the manifest rather than
globbing the package — so what is on the surface is a reviewable list.

**One divergence closes inside this epic and it is not cosmetic.** `rubricator/tools/citations.py`
publishes `verified / normalised / partial / not-found / empty`, where ADR-0014 publishes
`exact / normalised / fuzzy / moved / stale / unresolvable` and its 2026-08-21 amendment retires
`verified` outright; and its `verbatim_rate` counts only the strictest rung where ADR-0008's gate
counts `verdict ∈ {exact, normalised}`. `comparanda` had a third spelling again when this was filed
and has since moved onto the ADR-0014 enum, **so this repository is now the only one out of step**.
The whole divergence is **pinned green by doctests running under `--doctest-modules`** — so the wrong
contract is currently an enforced one. Closing it is a rename, the missing ladder rungs, and a doctest rewrite,
and the two rungs that detect drift only become reachable once renditions carry two hashes
(ADR-0014's 2026-08-22 amendment). Filed as register request 10; it must land before the schema
freezes.

Two granularities stay separated on purpose: *generation* granularity is one cell (the prompt's
business), *write* granularity accepts a batch (the tool's business).

### 7. Prompts (v1, partly)

Ten prompt files as versioned content, served by both runtimes from the same directory. The slice
needs one — `score-cell`, the default scoring prompt — and it must read the criterion's declared
scale rather than assume five levels. `propose-criteria` is the highest-leverage prompt and the
hardest, because the criteria discussion is the part of the product users actually value;
`score-column` stays demoted to a harness arm.

Resolve where the files live before ten of them exist in the wrong place — the directory the build
ships is currently empty and untracked.

### 8. The connector (v1)

The tool surface built from the manifest; the returned server decorated with the prompts and
resources; both transports; the step-4 confirmation checkpoint with its degraded path and its
dual-era fallback; analyses that survive a session boundary — which now means **a second contributor
opening the same analysis**, not only one user resuming their own.

### 9. Evaluation (after v1)

ADR-0008's six checks, as amended. Two are passed perfectly by a degenerate agent — "stability" by
one that always returns 3, "refusal to guess" by one that always blanks — and each needs a paired
discrimination counter-metric; the degenerate baseline ships as a **real refusing adapter** so the
counter-metrics have something to beat. The calibration item is not computable as written and splits
into discrimination over `confidence` and proper scoring over an evaluation-only `certainty`.

### 10. Variance and uncertainty (after v1)

Mitigate, quantify, disclose. The three stability reports now sit behind the epic-12 envelope, so
this epic implements statistics rather than architecture. Per-runtime defaults are keyword arguments
at the composition root, never two code paths. The traversal-comparison harness is a shippable
seven-arm evaluation, not a one-off script. The user-facing warning text is content and must say
that human panels show the same effects — otherwise it reads as "machines are uniquely bad", which
is false and, because it invites dismissal, useless.

### 11. Deployed agent and CLI (after v1, except one verb)

Model access behind a two-adapter seam (ADR-0019's amendment): the key-holding runtimes go through
the local facade, and the connector uses the host's own sampling. Then the offline
corpus-preparation step, the only place an embedding index is allowed to exist. **One CLI verb is
v1**, because ADR-0023 invokes the projection from the CLI and never from a tool — a tool reaching
GitHub would break the determinism boundary and the connector's offline guarantee in one call.

### 12. The seam substrate and the composition root (v1) — NEW

The organising idea, in one sentence: **most of what varies is data, not behaviour, and the data
belongs in the document rather than in a registry** (ADR-0021). Every extensible axis takes one
shape — a closed core, an open string at the point of use, a declaration in the document, one
resolver, and degradation through a declared parent that is **reported rather than swallowed**.

So this epic introduces **no measurement-scale protocol and no port set**. The two seams everyone
reaches for first are the two that are already expressible as data, and building them as interfaces
would buy indirection and cost a lockstep two-language release every time someone adds a scale.

What it does build: the resolution substrate; scale presets; the missingness facade; reducers with
their invariants hoisted into one wrapper; the stability envelope with preconditions as a returned
value; the injected clock; the surface manifest; the vocabulary parity artifact; and the composition
root whose keyword arguments **are** the seam catalogue (ADR-0020).

### 13. Persistence, contributors and the projection (v1) — NEW

One interface for the whole persistence layer — `MutableMapping[str, bytes]` — chosen because it is
standard, the ecosystem already implements it, and every existing decorator applies to all of them.
A facade over exactly one injected mapping, with the codec, the key template and the unbypassable
write-time honesty validation above the seam and only the leaf bytes store varying (ADR-0023).

The key layout **is** the collision-freedom argument: one file per contributor, so two writers never
touch one key, so a pull-rebase-push needs no locking protocol and a last-write-wins browser
provider is safe. That invariant is load-bearing, so it is a declared capability and a test rather
than folklore. The merge is pure, deterministic and in the core — never in a backend, or the two
targets diverge silently.

The contributor model is the most under-specified thing in either repository and the prerequisite
for the filenames, the independence ladder and aggregation. **A persona is an author**, with a
principal behind it and an attestation saying how well we know the identity (ADR-0022).

The GitHub target is the largest single build item here: the ecosystem's GitHub-over-Mapping package
is entirely read-only. The projection ships with real projectors and a null writer — zero API calls,
fully testable offline, and the shape proved before anything is published.

### 14. The `rubricator` application (v1) — NEW

One data port, one plain props shape, one text-only encoding (ADR-0025). Files own everything
durable; the browser owns the in-flight copy and a bag of disposable view preferences, and nothing
else — the moment the browser owns something not in a file, "files are the single source of truth"
stops being true.

Text-only is not a shortcut: the planned colour encoding hardcodes a palette arity that a pluggable
scale breaks, so it would have no correct ramp for a money column. It also passes the accessibility
gate by construction rather than by a contrast test.

The v1 table is small and **deliberately throwaway**: when `comparanda`'s matrix ships it consumes
the same props and this component is deleted rather than refactored. The cost is a component; the
benefit is that v1 does not block on another repository's later phase.

### 15. The v1 vertical slice (v1) — NEW

**One contributor, signing under a persona, scores one cell against one ingested source — and the
second cell is an honest blank.** A dozen ordered steps, each printing something before the next
begins. The first ten are pure Python and depend on no frontend and no view component.

The step that matters most is the falsification test: load a document declaring a scale and a
missingness code **that v1 does not implement**, and assert it validates, dominates, screens, that
the silence rate correctly excludes the unimplemented-code cells, and that exactly two degradations
surface with the exact axes. **If that test is green, every declaration seam in this design exists.
If it cannot be written, the architecture is prose.**

Deliberately not in the slice: no GitHub backend, no second contributor, no in-process model access,
no weights, no aggregation beyond `single`, no colour encoding, no shared matrix component. Every
one of those is a later addition at a named seam.

Two dependencies on the other repository are hard: the JSON Schema artifact has never been produced,
and the messy fixture this whole design is falsified against does not exist either. Both are tracked
in `comparanda: docs/cross-repo-coordination.md`, not duplicated here.

---

## What we know this gets wrong

Recorded because a deferral nobody wrote down becomes a mystery later.

- **Every read is a merge and nothing caches it.** Free at fixture scale; visibly slow at fifty
  contributors and five hundred cells. The fix is one caching decorator at the composition root; v1
  deliberately ships without it.
- **The persona-to-person link is pseudonymous, not anonymous.** Per-analysis salting stops an
  outsider joining two analyses. Inside a team repository, the mapping is guessable, and describing
  the salt as privacy would be false.
- **Degradation through a declared parent can be honestly wrong**, and the medium-confidence case
  degrades quietly-but-loudly. The high-confidence case is a rejection; the rest is a banner
  somebody will not read. Unrepaired.
- **Declaration parameters are an open object**, so they are validated only by an interpreter that
  already knows them — which is exactly where the schema contract stops being load-bearing.
- **The parity test catches key drift, not semantic drift.** Both repositories can register the same
  reduction name and disagree about ties. Golden fixtures through both implementations are the real
  defence and are not in v1.
- **The declarations cost is paid in v1 and the benefit arrives later.** For one contributor with one
  scale, the whole apparatus buys nothing. The falsification fixture is the only thing keeping that
  honest.
- **The store has no async story** while the handlers are async. That choice belongs in the facade,
  once, and is not made in v1.
- **The magic numbers must become named keyword defaults**, not a config loader: the fuzzy threshold,
  the span-size bounds, the error rate, the tau bands, the retention window, the retrieval `k`, the
  window size, the polarised gap, the traversal seed. The staleness threshold deliberately keeps
  **no** default, because expiring a check on an age nobody can justify blinds a shared bundle whose
  recipient cannot refresh it.

---

## What we would cut under time pressure

`BRIEF.md` asks for this by name. In cut order — first to go at the top.

1. **The pairwise escalation and the coupling probes** — `fit_bradley_terry` and
   `compute_coupling_matrix`. Not built in v1 at all.
2. **The deployed agent (Phase 5), except the one CLI verb projection needs.** The connector is the
   product for the primary user, and stopping after the two v1 surfaces is a legitimate outcome —
   ADR-0007 says so.
3. **The GitHub store target.** The filesystem target is the same code path; deferring the second is
   deferring a hundred lines, not an architecture. Cut this before cutting the facade.
4. **The projection's real writer.** v1 already ships the null one. Cut the writer, keep the
   projectors, keep the protocol without a read method.
5. **`score-column` and the harness arms that exist only to validate it.**
6. **The `certainty` measure and Family-B proper scoring.** Evaluation-run-only already; Family A
   carries the release gate on its own.
7. **The two refusing stability strategies.** Keep the default and the envelope; a strategy that
   refuses is cheap, so this saves little.
8. **`disclose_variance` — but only if repeats are always used.** They are not at k=1, which is the
   connector's normal case, so in practice this cut is unavailable.
9. **`report_weaknesses` — cut last.** Without it, ADR-0006's "self-critique is part of the
   deliverable" degrades to unaided model opinion, which is the failure the evaluation suite exists
   to catch.

**Never cut**, whatever the schedule:

- **`check_citations`.** A citation nobody can check is not a citation, and a well-formatted matrix
  with wrong citations is worse than one with none, because the format certifies the content.
- **The offline-checkable rendition resource.** It is what makes the previous line true for a reader
  who is not us.
- **The step-4 confirmation checkpoint.** It is where the analysis becomes the user's rather than the
  model's, and it is under permanent pressure to remove.
- **The refusal-to-guess evaluation.** It is the behaviour most likely to erode under prompt edits,
  and it is the product's whole claim.
- **The honesty rule family, and its unsuppressibility** (ADR-0024). A deployment that can configure
  its way past it has bought a different product.
- **The falsification fixture test.** It is the only evidence that any seam in this design is a seam.
- **The boundary tests.** They cost nothing to keep and they are what makes the architecture survive
  a refactor by someone who has not read the ADRs.
