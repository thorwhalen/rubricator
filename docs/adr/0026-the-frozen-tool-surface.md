# ADR-0026: The frozen tool surface — names, signatures, envelope, errors, and the cut order

- **Status:** accepted
- **Date:** 2026-10-12
- **Deciders:** Thor Whalen

## Context
Phases 2–5 all bind to the tool surface, and ADR-0013 warned that retrofitting its JSON Schema subset across a settled surface is pure rework. The research proposed nineteen tools (`docs/research/findings-method.md` § "Proposed MCP tool surface"); ADR-0009 adopted that count as a judgement call and asked for the definitions to be *measured* with the provider's token counter rather than estimated. Issue #49 asked for the surface to be written down and pinned before more of it was built.

By the time it was, ten verbs existed and had been through five reviewed changes against comparanda schema v1. Three of them are not among the research's nineteen (`report_completeness`, `prompts_list`, `prompts_get`); seven of the nineteen's names are implemented, with signatures that drifted from the proposal where the comparanda contract forced them to. None declared an `outputSchema`. The connector derived every `inputSchema` from a Python signature, and a signature cannot say what ADR-0013 requires: `Mapping[str, Any]` derives to an *open* object, and the subset closes every object. Two tuple-shaped inputs used `prefixItems` and `minItems: 2`, which the subset forbids. So the implemented surface violated the subset at every object-valued argument, silently, and an MCP client in strict mode would have refused to call it.

One more force. The closed comparanda v1 schema refuses unknown keys, and the write tools copied caller dicts verbatim (#136): an extra key offered by a model — which is what a model does — landed in the store as a document the contract rejects. A surface that advertises closed shapes and validates against them closes that at the boundary.

## Decision

**The surface is twenty tools plus two transitional verbs, listed in `rubricator/surface/frozen.py`, and that module is the single source of truth.** Every row carries the name, the family, the ADR-0005 stage, the status (`implemented`, `planned`, `transitional`), whether it is in the minimum viable set, its cut rank, a one-paragraph contract, a one-line determinism justification, a one-line failure mode, the `inputSchema`, the `outputSchema`, and — for anything not yet implemented — the issue that tracks it. The research's nineteen all have rows, mapped by `research_row`; `report_completeness` is the twentieth; `prompts_list` and `prompts_get` are transitional, retired when native MCP prompts land (#80). The rows:

| # | Tool | Family | Stage | Status | MVP | Cut | Research row |
|---|---|---|---|---|---|---|---|
| 1 | `analysis_open` | analysis | 1, resume | implemented | yes | — | 1 |
| 2 | `analysis_get` | analysis | all | implemented (#52) | yes | — | 2 |
| 3 | `corpus_add` | corpus | 2, 5 | implemented (#53) | yes | — | 3 |
| 4 | `corpus_search` | corpus | 2, 3, 5 | planned (#54) | yes | — | 4 |
| 5 | `frame_set` | frame | 1 | implemented | yes | — | 5 |
| 6 | `alternatives_set` | alternatives | 2 | implemented (checks: #55) | yes | — | 6 |
| 7 | `criteria_set` | criteria | 3 | implemented | yes | — | 7 |
| 8 | `frame_confirm` | frame | 4 | implemented (#57) | yes | — | 8 |
| 9 | `plan_traversal` | plan | 5 | implemented | yes | — | 9 |
| 10 | `measures_write` | measures | 5 | implemented | yes | — | 10 |
| 11 | `measures_mark_missing` | measures | 5, resume | implemented | no | 4 | 11 |
| 12 | `analysis_validate` | analysis | 5, 6 | planned (#61) | yes | — | 12 |
| 13 | `check_citations` | citations | 5, 6 | implemented | yes | — | 13 |
| 14 | `aggregate_assertions` | measures | 5 | implemented (#97) | no | 3 | 14 |
| 15 | `stability_report` | report | 6 | planned (#98) | no | 3 | 15 |
| 16 | `report_weaknesses` | report | 6 | planned (#64) | no | 5 | 16 |
| 17 | `disclose_variance` | report | 6 | planned (#100) | no | 2 | 17 |
| 18 | `compute_coupling_matrix` | criteria | 3 | planned (#65) | no | 1 | 18 |
| 19 | `fit_bradley_terry` | measures | 5 | planned (#65) | no | 1 | 19 |
| 20 | `report_completeness` | report | 5, 6, resume | implemented | yes | — | — |
| 21 | `prompts_list` | prompts | all | transitional (#80) | yes | — | — |
| 22 | `prompts_get` | prompts | all | transitional (#80) | yes | — | — |

**Cut order.** 1 is cut first. Rank 1: the two deferred tools. Rank 2: `disclose_variance`, only if k > 1 is always used — it is most needed at k = 1, the connector's normal case. Rank 3: `aggregate_assertions` and `stability_report` together, if there are never repeats. Rank 4: `measures_mark_missing`, only at the price of partial-fill instructions, a visible product regression. Rank 5, cut last: `report_weaknesses`, without which "self-critique is part of the deliverable" (ADR-0006) degrades to unaided opinion. Everything with no rank is the minimum viable set and is not cut. The research listed `check_citations` outside its minimum set while calling it "not cuttable — it is the product"; the second statement is the decision, so it is in the minimum set here. Fifteen tools are minimum viable: the research's eleven, plus `check_citations`, `report_completeness` and the two transitional verbs.

**Naming.** `snake_case`, no server prefix. Everything that acts on a stored analysis is noun-first — family, then verb: `analysis_*`, `corpus_*`, `frame_*`, `alternatives_*`, `criteria_*`, `measures_*`, `report_*`, `prompts_*`. Pure functions over caller-supplied data keep the research's names, which the ADRs already cite verbatim — ADR-0011's `plan_traversal`, ADR-0014's `check_citations`, and the five analytic tools of rows 14–19. Renaming those to satisfy a convention would cost every citation for no gain in selection accuracy.

**What is frozen and what may grow.** Names and `inputSchema`s are frozen: changing either is an amendment to this ADR with its reason recorded, and a test holds every implemented verb's Python signature — parameter names, which are required — to its row. `outputSchema`s may grow additively: a new optional field is a row edit, because an output field constrains what the *server* returns, never what a model may say, and grammar compilation is keyed on the input side. A planned tool's row is its specification; when it lands, the signature test starts holding it.

**The envelope.** Every tool declares an `outputSchema` and every result is `structuredContent` conforming to it, with a required `summary` string that the connector also emits as the human-readable `content` — one field, two renderings, so a client that reads only text and a client that reads only structure see the same fact. The surface validates every result against its row before returning it and raises `ContractViolation` otherwise, because MCP says a server MUST conform to its declared `outputSchema` and a silent mismatch is the one failure a client cannot detect.

**The error convention.** Arguments are validated against the frozen `inputSchema` *before the verb runs*, in every surface that dispatches through `bind` — the connector, and the CLI's commands; the CLI's `demo` calls the verbs directly on purpose, as the Python-level chain — and a failure raises `ValueError` naming the JSON path, what was found, and which keys are allowed there. A verb refuses with `ValueError` (a rule), `KeyError` (an unknown id or code) or `TypeError` (a shape), and the message carries the fact needed to fix it, stating "nothing was written" when that is so. Over MCP every such exception is a tool result with `isError: true` whose text is the message. An unknown tool or a malformed request is a protocol-level error, raised by the host, never by a verb. Nothing a verb does produces a JSON-RPC error, and nothing the host does produces a tool error; the two layers do not share failures.

**Reasoning before value, and the digest sees order.** ADR-0013 says every emitted judgement schema declares its reasoning field before its value fields, because property order is generation order under constrained decoding. In the connector the `cells` argument of `measures_write` *is* the judgement, so its shape declares `justification` and `evidence` before `value` and `missing`, a test holds that order, and the measurement digest is taken over the definitions in insertion order rather than sorted, so a reorder is a change the pin notices.

**What `measures_write` checks that no schema can.** Four refusals read the frame: a `measure` the analysis does not declare, a row or column that is tombstoned, a missingness code that neither the core vocabulary nor the analysis nor the criterion declares (the same rule `measures_mark_missing` applies), and an unknown `alternativeId` (as an unknown `criterionId` already was). A **confidence** on each assertion — ADR-0006's requirement — has no slot in comparanda v1 and no row here; it is the open schema request #126, and when it lands it is an amendment to this ADR adding a field to the cell shape, recorded now so the amendment is expected rather than a surprise. `check_citations` carries no threshold argument: the fuzzy threshold is a harness knob on the Python `report_citations`, because a model that could set it to zero could grade a fabricated quote `fuzzy` on the one tool that is the product.

**The ADR-0013 subset is enforced by a checker, not a reviewer.** `rubricator/surface/subset.py` is the seven-point checklist as a function, on an allowlist: the seven types, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, `anyOf`, `allOf`, internal `$ref` and `$defs`, `default`, `format`, `title`, `description`, `minItems`. Anything else — `minimum`, `maxLength`, `pattern`, `oneOf`, `prefixItems`, `maxItems`, `patternProperties`, `propertyNames` — is a violation at the path where it occurs, and `additionalProperties` must be *exactly* `false` on every object, not merely absent. The conformance test runs it over all forty-four schemas, and runs it first over one deliberate violation of each kind, per ADR-0020's rule that a guard is shown failing before it is believed.

**Three consequences the subset forced on the implemented signatures, and one it did not.** Anchors are a list of `{level, text}` rows rather than an object keyed by level, because a dynamic-key object cannot be closed; the verb accepts both shapes and stores comparanda's mapping. `check_citations` takes `{quote, source, evidenceId?}` objects rather than tuples. `criteria_set` reports revisions and definition gaps as lists rather than id-keyed objects. And `measures_write`'s `value` is the comparanda union of number, string and boolean rather than an `enum` of 1–5: the score scale is *data* (ADR-0021) and is not known at schema-authoring time, so no tool schema bounds it. The bound is enforced where ADR-0013 put range checks — in the deterministic validator — and it is enforced *now*, at write time: `measures_write` refuses a value that is not one of the `levels` the criterion's scale declares, or that falls outside its `range`, naming the cell and the scale. The per-scale emission schema the score-cell prompt will hand a constrained decoder, where the 1–5 `enum` belongs, is #72's work and does not exist yet; #61's `analysis_validate` repeats the same check over a whole document.

**`analysis_id` is minted, opaque, and never overwritten.** A new seam at the composition root, `new_id`, supplies one when the caller gives none — the same shape as the clock, for the same reason: `secrets` is denied to the tool layer, so a verb that minted an id would not be a tool. Reopening an existing id returns `created: false` with what is there and writes nothing, so a retry cannot reset a matrix. The retention window of ADR-0017 is a stated constant, `RETENTION_DAYS = 30` from last write, quoted in `analysis_open`'s description where the model reads it; a test keeps the two in step. It is stated before it is enforced — no store expires anything yet (#51) — which errs in the safe direction.

**`frame_set` writes the frame; `alternatives_set` writes the rows.** The implemented `frame_set` had taken the alternatives, conflating ADR-0005's stages 1 and 2. They are now the research's two tools: a frame can be settled before anything is enumerated, and `alternatives_set` refuses to drop a row that cells refer to, as `criteria_set` already did for columns. Both input shapes carry `tombstoned` and `supersededBy`, because a refusal that says "tombstone it" must be followable through the surface. A caller-supplied id — analysis, contributor, rendition — is confined to `[A-Za-z0-9_-]{1,64}` by the store, because it becomes part of a path. Its near-duplicate and unsourced flags are #55's work and will grow its output additively.

**What the model reads is the row, not the docstring.** The connector registers each tool from its row — description, `inputSchema`, `outputSchema` — over an untyped wrapper, so the host coerces nothing before the bound verb validates the raw arguments against the same row, and returns `summary` as the text content beside the structured result. Nothing in that path awaits, so the server can be built inside a running event loop. The connector tests run in CI with the `mcp` extra installed; the bare test matrix skips them. The description is rendered from the row's contract, stage, determinism and failure fields, because a docstring written for the developer maintaining a verb and a description written for the model choosing one have different readers — and only the second has a measured cost. The Python docstring stays the developer's.

**The token cost is measured, and re-measured whenever the definitions change.** `scripts/measure_tool_tokens.py` sends the exact definitions a client sends — name, description, `inputSchema` — to the provider's token counter and prints the block recorded as `MEASURED`. Measured on 2026-10-12 against `claude-sonnet-5-5`:

| Definitions | Tools | Tokens | Bytes |
|---|---|---|---|
| advertised today | 11 | 6,692 | 15,611 |
| the whole frozen surface | 22 | 10,542 | 25,461 |

A test pins the SHA-256 of both lists as canonical JSON to the recorded digests, so a changed description or schema — even a same-length one — fails until the measurement is redone. The whole surface sits *at* the 10k-token line the research names as the point where deferred tool loading starts to pay, not comfortably under it. That is a finding, not a problem to solve here: it says that when the planned rows land, either the descriptions are trimmed under the same measurement or the connector adopts the host's deferred loading, and the measurement is what decides which.

**Deliberately absent, carried over and tested.** No `propose_criteria`, `score_cell`, `review` or `detect_overlap` tool — judgement, so prompts (ADR-0003). No embedding-backed search (ADR-0010), under any name: `corpus_embed`, `semantic_search`. No aggregate or total tool — `aggregate_total`, `compute_total` — because comparanda computes none by default and a tool returning one would make it the path of least resistance. No `analysis_list` tool: it is a resource; the host lists, the model does not browse. No `conformal_interval` in v1; when it lands it reads a stored calibration table. And no `temperature` or model-seed parameter on any tool: neither exists in the connector, and a parameter that silently no-ops in one of two first-class runtimes is a bug in the specification. The `seed` on `plan_traversal` and `fit_bradley_terry` is an input to a pure function — seed the traversal, not the model. A test asserts none of the absent names is ever a row or a registry entry and none of the forbidden parameters appears in any `inputSchema`.

**The measurement script is the one direct use of a provider SDK in the repository.** ADR-0019 routes all LLM access through the `aix` facade; counting tokens is not inference, the facade has no counter, and the script ships no part of the package. The exception is stated in the script and filed against the facade's gap list (#34).

## Consequences
The surface is reviewable as a file rather than by reading nine modules: what exists, what is planned, what is cut first, what the model reads, and what it costs. An extra key from a model is refused at the boundary with its path, in the CLI and the connector alike, which closes the first bullet of #136 for every implemented write path; the second bullet — `score-cell` asking for fields the closed assertion has no slot for — stays open there, because it is a prompt change. The connector now advertises closed schemas a strict-mode client will accept, and declares an `outputSchema` on every tool, which it did not before.

The cost is a second description of every verb — the row beside the docstring — and a byte pin that makes every wording change a measurement. Both are the point: the row is what the model reads and the pin is what keeps "measured" true. A planned row is a specification that may prove wrong when its tool is built; changing it then is an amendment here, which is cheaper than the alternative of a surface nobody wrote down. The naming rule has a stated exception, and exceptions are what conventions die of; the test lists the seven names so that an eighth has to be added deliberately.

Six choices in this ADR reconcile the research with the reviewed implementation and are the owner's to ratify, each reversible by amendment: the `frame_set` / `alternatives_set` split, `report_completeness` as a twentieth tool rather than a view of `analysis_get`, the two transitional prompt verbs, the naming exception, the freeze policy on outputs, and the minted id with `check_citations` in the minimum set. They are filed with a recommendation in #144. The second checkout of this repository that the editable install resolves to is not this ADR's business but was found by its measurement script, and is reported with it.

## Alternatives considered
- *Freeze the research's nineteen verbatim and rework the implementation to match.* The implemented signatures were forced by the comparanda v1 contract (`contributor_id`, `author`, `at`, closed cell shapes); the research's were sketches. Freezing the sketch would have frozen the thing that had not been tested.
- *Derive `inputSchema` from typed Python signatures (TypedDict with `extra="forbid"`).* Puts pydantic in the tool layer, which must import bare, and still cannot express the subset's exclusions. A row is data; a type is not.
- *Validate inputs only in the connector.* Then the CLI and any later surface accept what the connector refuses, which is two surfaces again. The surface binder validates, so every dispatcher inherits it.
- *Fold `report_completeness` into `analysis_get(view=outstanding)`.* The outstanding view returns cells; the report returns rates, degradations and stored honesty problems. One tool returning either shape by a `view` argument would need a union envelope, and the subset has no discriminated unions.
- *Estimate tokens from bytes and skip the pin.* ADR-0009 asked for a measurement; a ratio drifts with every description edit, and nobody would notice.
- *Docstrings as descriptions, per #49's wording.* The docstrings are developer essays, several hundred tokens each; the model needs the contract. The row is the description, and the measurement is taken over it.

### 2026-10-12 — `aggregate_assertions` lands (#97)

- **Deciders:** Thor Whalen

Row 14 is implemented. Its `outputSchema` changed in three ways, all before any client bound to it, since the row was planned until now:
- `min` and `max` widen from number to the comparanda scalar union, because a scale's levels are data (ADR-0021) and may be strings. They, and `span`, are `null` for a nominal measure, which has no order.
- A `levels` multiset (`[{level, count}]`) is added. It is what ADR-0011 says a polarised cell carries instead of a point value.
- `offScale` is added, so a value the scale cannot take is counted rather than silently dropped.

**Its contract text was corrected.** It had described polarisation as "modes further apart than polarised_gap" and the level of measurement as always ordinal. Polarised is now stated as the rule that is implemented, mirrored from comparanda's `cellShape`: two or more occupied levels, separated by at least `polarised_gap` empty levels, with no single dominant mode. The level of measurement is read per measure, through comparanda's `measurementFor`.

**How each level of measurement is reduced.** `median` is the lower median on an ordinal measure, and the conventional median on an interval or ratio one (averaging only numbers). An ordinal integer range with no declared levels has its steps derived from the range, so a bimodal cell there is still caught. A nominal measure gets modes and counts only.

**A mean is refused naming the level of measurement, at the surface as well as in the verb.** The frozen enum alone would only have said "not one of". So the surface gains a small pre-schema refusal hook, `_PRECHECKS`. It runs before the input schema check, for the one case where the contract owes the caller a reason the schema cannot carry.

Re-measured on 2026-10-12 against `claude-sonnet-5-5`:
- the advertised definitions: 12 tools, 7,039 tokens, 16,522 bytes;
- the whole surface: 22 tools, 10,574 tokens, 25,572 bytes. It moved because the row's description changed.

### 2026-10-12 — `analysis_get` lands, and `analysis_open` reports the stage (#52)

- **Deciders:** Thor Whalen

Row 2 is implemented, in `rubricator/tools/views.py`. Every view is a pure projection of the merged document and writes nothing. Its `outputSchema` grew before any client bound to it:
- `stage` (required, on every view): the earliest ADR-0005 stage whose work is not on record — 1 until `frame_set` has recorded ambiguities, 2 until a live alternative exists, 3 until a live criterion does, 5 while any cell is outstanding *or* holds a score answering an older definition of its criterion, 6 after. Stage 4 is reported once `frame_confirm` exists to pass it (#57).
- `counts.superseded` (required): the cells whose live scores answer an older definition (ADR-0016). They hold the stage at 5 — ADR-0016 says work genuinely remains there — but they are not `outstanding` rows, because they are not blanks; whether they should *also* be listed there is #138's question.
- `frame` adds `subject` and `alternatives`; `criteria` adds `criteria` and `criteriaVersion`. Both are the frozen *input* shapes, so a model can read a view and hand it straight back to `alternatives_set` or `criteria_set`; a test holds the criteria round trip to "no revision, same version".
- An `outstanding` row gains `measure` and `recorded`. A live cell nobody has written is `not-assessed` with `recorded: false` — comparanda's default for a new cell — so "nobody wrote anything" is told apart from "somebody marked it not-assessed", and both from `deferred`. A cell is settled when a live assertion carries a value or a terminal or structural blank; a code this build cannot resolve counts as outstanding, as in `report_completeness`. Retired rows and columns are not in the matrix.
- `full` returns `rubricator://analysis/{id}`, never the body. The connector now serves that one resource template, the merged document read fresh, so the link resolves; the rest of the resource surface stays #66's.

**A projection never turns a data problem into a server bug.** Stored data is not guaranteed to fit the closed output shapes — a document written before a rule existed, or edited by hand in a shared repository. Each projected row is cut down to what its frozen fragment admits (`views.conform`), and the required `omitted` field lists every path that was left out, with the summary warning not to hand that view back to the writing verb, which would delete or rewrite what was dropped; returning it as stored would have raised `ContractViolation`. A contribution that cannot be merged makes `analysis_get` refuse naming the cause, but `analysis_open` still reopens from the frame alone and says so, so the resume entry point is never locked by one bad file. Open blanks are ordered by instant, never by string. The resource is served as `application/json`.

`analysis_open` gains `stage` on its output (required) and reads the whole document on reopen, in one read, to compute it. Its failure text changed: an unknown or expired id with no question is refused naming the retention window, because a caller passing an id expected to find it. A call with neither an id nor a question is refused by a `_PRECHECKS` entry before an id is minted, so the caller hears what is missing rather than that a handle it never chose is unknown.

Re-measured on 2026-10-12 against `claude-sonnet-5-5`:
- the advertised definitions: 13 tools, 7,325 tokens, 17,308 bytes;
- the whole surface: 22 tools, 10,582 tokens, 25,601 bytes. It moved because `analysis_open`'s failure text changed.

### 2026-10-12 — `frame_confirm` lands, and scoring waits for it (#57)

- **Deciders:** Thor Whalen (three of the choices below are filed for ratification in #152)

Row 8 is implemented, in `rubricator/tools/confirm.py`, as ADR-0005's out-of-band path. Wiring real elicitation in the connector stays #81's: the verb exposes no way to *claim* an elicited answer, and the connector — the only party that can know a form reached a person — will record one through `record_decision`, which is not on the surface.

**Two input amendments.** `analysis_open` gains `allow_skip_confirmation` (ADR-0005: "until the gate has been passed or `allow_skip_confirmation` was set when the analysis was opened") and `at`, which dates the skip and sets the document's `createdAt`. `frame_confirm` gains `at`, like `measures_write`. Both verbs join `NEEDS_CLOCK`. The skip can only be set at creation, and is stored as a record attributed to the agent (`authorId: agent`, `mechanism: skip-at-open`), never as a human confirmation.

**What cannot be fabricated, and how that is tested.** A `confirm` is recorded only when it answers a question asked since the last decision — the first call, with no decision, returns the instructions and notes that the question was asked — and only with `confirmed_by` and `confirmation_text` both non-blank. Otherwise the result is `confirmed: false` with instructions and nothing is written. A test runs every combination of decision, scope, author and text, and no single call passes the gate. After the question, exactly one combination does: `confirm`, scope `all`, a name and words. `revise` and `reject` need no fresh question, because they can only close the gate. The out-of-band channel still trusts the caller's model to relay the user truthfully; that is the degraded path ADR-0005 specifies, and elicitation (#81) is the stronger one.

**The gate.** For each of the frame, the alternatives and the criteria, the latest decision covering it must be `confirm` (or the skip). `measures_write` — and so `measures_mark_missing` — refuses with nothing written until then, naming the parts still open. A later `revise` or `reject` closes the gate again. A criteria revision does not: ADR-0005 says the gate opens both ways, and ADR-0016 owns what a revision costs. The record keeps the criteria version it was given against, and `frame_confirm` says when the set has moved since, so a session can choose to re-ask (#152).

**Resume.** A call with no decision on an open gate returns the deciding record with `mechanism: recorded` and writes nothing — unless the criteria have moved since, when it notes the question and returns instructions to ask again. `analysis_open` refuses `allow_skip_confirmation` on reopen unless it is a retry of the create that skipped and nothing has closed the gate since. `analysis_get` and `analysis_open` now report stage 4 while the gate is closed. `stage_of` takes `confirmed` as a required argument, because the records live outside the document.

**Where the records live.** Beside the frame and inside the same retention window, not in the document. Comparanda v1 is closed and has no slot for them, and writing one would make the stored analysis invalid; a test holds the document schema-valid after a confirmation. #152 recommends asking comparanda for the slot, by the same route as #126. They are **one file per record**, `analyses/{id}/confirmations/{sequence}-{digest}.json`, never a shared file: ADR-0017's invariant is that no two contributors write the same key. Two branches answering the gate leave two files, and a `revise` cannot be lost to a conflict resolution. Order is write order — one past the highest sequence on the writing branch, never a count, which would repeat once a record is removed — and never the caller's `at`, which a model could set in the future to outrank a later human `revise`. Two branches can still write the same sequence; between those, a closing or unreadable record sorts last, so a merged `confirm` and `revise` leave the gate closed instead of letting a content digest, which a caller can steer, decide. The store reads a file it cannot parse as an `unreadable` record rather than skipping it, which could drop a `revise`. The gate reads any record that is not a well-formed request, skip or authored decision as closing every part until it is repaired, so a hand-edited record can never be what opens it. A new analysis clears records left under its id. Asking again after the criteria moved is a call with no decision: the gate stays open, the question is noted, and a fresh `confirm` of the new version can be recorded.

**Fixtures.** Tests that score but are not about the gate open with the explicit skip; the CLI demo does too, with a comment, since a scripted demo has no user to ask. The store's stage-chain test gains a real stage-4 step.

Re-measured on 2026-10-12 against `claude-sonnet-5-5`:
- the advertised definitions: 14 tools, 7,917 tokens, 18,897 bytes;
- the whole surface: 22 tools, 10,792 tokens, 26,207 bytes.

### 2026-10-13 — `analysis_get` counts settled cells by kind, and `report_completeness` leaves removed rows out (#186)

- **Deciders:** Thor Whalen (the second change moves published rates; recorded here so it can be reversed)

`analysis_get`'s `counts` gains `byKind` (required: an output-only addition, like `stage` and `superseded` before it, so an amendment recorded here rather than the optional-field row edit the freeze policy allows by itself): `scored`, `settledBlank` and `notApplicable`, in **cells**. A live cell with a live value is scored whatever else it holds; otherwise a terminal blank makes it a settled blank, otherwise a structural one makes it not applicable; anything else is outstanding. So `byKind` plus `outstanding` adds up to `cells`, which is what a resuming reader needs: one unit, checkable against one total. `rubricator.tools.views.cells_by_kind` owns the rule and `outstanding_cells` is a filter over it. The outstanding rows and their codes are unchanged.

`report_completeness` now leaves out the claims on a tombstoned alternative or criterion. They already left every comparison and every `analysis_get` count, and three scores on a removed row were still counted as `present`. This moves `total`, `present`, `settledAbsent`, `structural`, `applicable`, `informativeAbsent`, `outstanding`, the rates and the degradations found in those claims for an analysis with removed rows; for any other analysis nothing changes. It still counts claims, not cells: two raters on one cell count twice, and a superseded claim still counts, so its numbers are not cells and the resume prompt no longer reads it.

### 2026-10-13 — `corpus_add` lands, and every source says whether a model wrote it (#53)

- **Deciders:** Thor Whalen (the input amendment and the unmeasured definitions are recorded here so they can be reversed; the measurement is owed in #199)

Row 3 is implemented, in `rubricator/tools/corpus.py`. A source's text is normalised once under the current normaliser (`nfc-v1`) and stored as a comparanda `Rendition` whose `content` is exactly that normalised text: no title or preamble is prepended, because it is what quotes resolve against. Its id is derived from the normaliser and the hash of the text as supplied, so the same text twice is one document, and the same text under a later normaliser is a second document rather than a rewrite of the first's offsets. A normaliser whose output no longer matches its pin refuses the call. The chunker is versioned too (`chunk-v1`): it records `[start, end)` offsets into `content` and never re-chunks a stored document.

**One input amendment.** Each source gains `agentProduced`, required. ADR-0015 says the marker is applied at ingestion and that no path leaves it unset; a required boolean is how a caller cannot leave it unset. The description asks for `true` when unsure. The verb also marks, whatever the caller says, any text it recognises as rubricator's own output (a comparanda analysis document, for now). It never clears a marker: re-adding a marked document undeclared keeps it marked and says so.

**Outputs added.** `documents` (one row per source, in order: the id, whether it was added or already present, whether normalisation changed it, whether it is marked, its span count and token estimate) and `corpusTokenEstimate`, the estimate for the whole corpus, which is the number the inline-or-retrieve threshold reads. Token figures are estimates at four characters a token and are called estimates in the summary.

**Where what v1 has no slot for lives.** The spans, `cleaned`, and the marker sit beside the rendition as corpus records, `analyses/{id}/corpus/{renditionId}/{ingest,agent-produced}.json`, as the step-4 confirmations did (#152). The marker is a file whose presence is the fact, so two branches merge to "marked". #200 asks whether to request a slot for the marker on comparanda's `Rendition`.

**Secondary at best, at the write path.** `measures_write` (and so `measures_mark_missing`) refuses, with nothing written, an evidence reference of `sourceType: primary` whose `renditionId` or `target` is a marked document. Assertions written before a document was marked are not rewritten; `corpus_add` names them in a warning when it marks the document. The marker also spreads by content: a source whose normalised text is that of a marked document is marked, so a trailing newline cannot make an unmarked copy. Re-checking stored assertions against the marker belongs to `analysis_validate` (#61).

**Not re-measured.** These definitions were changed on a machine with no provider key. `MEASURED` below is still the 2026-10-12 count; `AWAITING_MEASUREMENT` in `frozen.py` pins the digest and byte size of what is now served (15 advertised tools, 20,213 bytes; the whole surface, 22 tools, 26,426 bytes) and names #199, which owes the count. The test accepts that pin only while #199 is named here, and any further definitions change still fails it. No estimate is recorded as a count.
