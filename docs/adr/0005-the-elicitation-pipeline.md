# ADR-0005: Elicit the frame before scoring anything

- **Status:** accepted
- **Date:** 2026-08-18

## Context
The tempting design takes a prompt and returns a filled matrix. It is also the design that produces
confident, useless comparisons, because the hard part is not scoring — it is deciding *what* is
being compared and *against what*. A matrix with the wrong criteria is worse than no matrix,
because it looks like analysis.

Experience from the originating work: the criteria were the subject of an extended discussion
before any cell was filled, and that discussion determined everything downstream. The single
biggest failure mode was scoring against criteria nobody had interrogated.

## Decision
A staged pipeline, with the frame settled before the matrix is populated:

1. **Frame** — establish the subject, the decision being made, and who is deciding. Surface
   ambiguity rather than resolving it silently.
2. **Enumerate alternatives** — from context, with explicit gaps ("you named six; sources mention
   three more — include them?"). Deduplicate near-identical entries and say so.
3. **Propose criteria** — with definitions, polarity (is higher better?), level of measurement,
   and any veto status. Every criterion arrives with a *definition*, because undefined criteria get
   scored inconsistently. Flag overlapping criteria explicitly: double-counting is the classic
   defect of hand-built matrices.
4. **Confirm with the user** — a checkpoint before the expensive step. Skippable by explicit
   instruction, never by default.
5. **Populate** — score, confidence, one-line justification and citations per cell. Honour partial
   instructions ("fill these two criteria, mark the rest pending").
6. **Review** — self-critique: which scores rest on thin evidence, which criteria overlap, which
   cells would most change the picture if wrong.

Step 4 is the one under pressure to remove. Keep it. It is where the analysis becomes the user's
rather than the model's.

## Consequences
Slower than one-shot generation, and produces something defensible. The pipeline is also the
natural tool decomposition for ADR-0003: each stage is one or more MCP tools plus a prompt.

## Amendments

### 2026-08-21 — The mechanism of the step-4 checkpoint

**Deciders:** Thor Whalen

Round-1 research confirmed the six stages and settled two things this ADR deliberately left open:
how step 4 is actually performed, and whether it may be reopened. Nothing decided above changes, so
this is an amendment rather than a superseding ADR — and it is the whole of what a separate child
ADR would have said, which is why no number was allocated for one.

**The six stages are confirmed, and were arrived at independently.** The pipeline above is PrOACT
plus a confirmation checkpoint and a review stage — a frame the decision-analysis literature reaches
on its own [1][2]. The one correction worth recording: the operational content of step 3 belongs to
Keeney's objective-generation devices and to the DCLG checks, not to *Smart Choices*, whose
distinctive contribution (even swaps) operates on an already-populated matrix and is exactly the
trade-off work rubricator hands back to the user rather than resolving. See
`docs/research/findings-method.md` § 1.

**Step 4 runs as an MCP elicitation where the client declares the capability.** The gate is one
tool, `frame_confirm`. Under specification revision 2026-07-28 the server does not send an
`elicitation/create` request; it returns an `InputRequiredResult`, and the client gathers the input
and retries the original `tools/call` [3][4].

The elicited form is a **flat object of primitives** — the protocol forbids nested structures and
arrays of objects outright [3] — so it carries exactly three fields:

- `decision` — single-select enum, `approve | approve-with-notes | revise`
- `notes` — free text
- `drop_criteria` — optional multi-select over the proposed criteria

That restriction is load-bearing rather than merely tolerated. It makes the rich criteria discussion
— the part this ADR calls the valuable part — stay in the chat turn driven by the `confirm-frame`
prompt, where the user can read the argument and the transcript keeps it. The elicitation is then
the **record** of the decision, not the venue for it.

Three protocol obligations bind the implementation: the server MUST NOT request input for a
capability the client did not declare, MUST NOT assume the retry ever arrives, and MUST handle
`decline` and `cancel` [3]. Neither `decline` nor `cancel` confirms anything. `requestState` carries
nothing but an opaque `analysis_id`; the real state lives in rubricator's own store keyed by that
id, which collapses the integrity requirements on attacker-controlled state to "a random opaque
token with a bounded lifetime".

**The degraded path is specified, not left to the implementer.** Where the client declares no
elicitation capability, `frame_confirm` returns success with `mechanism: "out-of-band"` and
instructions to put the confirmation to the user in chat — the same `confirm-frame` prompt — and
call again with `confirmed_by` and `confirmation_text`. **In neither path does the tool confirm on
its own behalf.** An unconfirmed analysis still refuses scoring: `measures_write` writes no measures
until the gate has been passed or `allow_skip_confirmation` was set when the analysis was opened.
Skippable by explicit instruction, never by default, is unchanged.

**The confirmation is stored as authored, timestamped provenance, not a boolean flag.** Who
confirmed, when, the verbatim confirmation text, which mechanism carried it, and the criteria-set
version it applies to. A resuming session reads it and does not re-ask, and "the criteria were
confirmed by a named human on this date" becomes auditable — which is most of what makes the
analysis defensible.

**Step 4 is a gate that opens both ways.** Read linearly, the pipeline above implies criteria are
final once confirmed. They are not: criteria drift is documented, and some criteria only become
statable once outputs are observed. Reopening the frame after scoring has begun is expected
behaviour, not a failure of step 4. What it costs — criteria-set versioning, and invalidating
measures scored against a superseded definition — is decided in ADR-0016, not here.

**Evidence.** `docs/research/findings-method.md` — decision summary row 33, § 1, and § 6;
`docs/research/sections/r6-mcp-and-agent-architecture.md` § 1 (the protocol constraints) and
§ 7 (the confirmation as provenance).

1. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf)
2. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985)
3. [MCP — Elicitation, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)
4. [FastMCP — Elicitation (2026)](https://gofastmcp.com/servers/elicitation)
