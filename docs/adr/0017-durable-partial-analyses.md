# ADR-0017: An in-progress analysis is a durable partial comparanda document

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0005 puts a human confirmation checkpoint before the expensive step, and that checkpoint is
worthless if it does not survive a session boundary. A real analysis spans days: a user confirms the
criteria on Monday and returns on Wednesday, in a new chat, to score.

**MCP offers nothing that survives that gap, and this is by design, not an omission.** MRTR
`requestState` dies with the request and the specification urges a short TTL on it [1]. A Tasks
`taskId` is durable across disconnects, but it is scoped to one operation and the *client* holds it,
so a new session has no idea it exists [2]. Prompt caching expires in minutes and is a cost
optimisation, not state [3]. The comparable prior art separates a checkpointer scoped to one thread
from a durable store across threads, and says plainly that cross-session resume needs a real
backend [4].

So the durable record is ours to own. The only real question is what shape it takes.

## Decision

**rubricator owns a store, keyed by an opaque `analysis_id`.** The id is a random, unguessable
handle, per the specification's Stateful Tools guidance [5]. It carries no meaning and no state —
the state lives in the store behind it, which is what collapses the integrity requirements on an
id that travels through attacker-reachable places to "a random token with a bounded lifetime".

**The stored record is itself a schema-valid comparanda analysis** — not a bespoke checkpoint format
that must later be converted. A half-finished analysis is a finished document about an unfinished
analysis. Everything follows from this: no conversion step, no second schema to keep in sync with
the first, and every intermediate state renderable by comparanda without special handling.

**The closed missingness set carries the resume semantics**, so resumption needs no fields of its
own. `not-assessed` — nobody has looked, the default for a new cell. `pending` — deliberately
deferred by instruction, which is what makes "fill these two criteria, mark the rest pending" a
first-class instruction rather than a prompt hope. `unknown` — someone looked and could not
determine. That last distinction is ADR-0006's, and it is the one the whole product rests on: a
resuming session must know the difference between *not done* and *done, and the answer is that we
cannot tell*. Nothing here branches on a literal code, so a narrower code added later — ADR-0016's
cells invalidated by a criterion revision, for one — resumes correctly with no change to this
decision.

**The step-4 confirmation is stored as authored, timestamped provenance, not a flag.** Who
confirmed, when, the verbatim text, and the criteria-set version it applies to, as ADR-0005's
amendment specifies. A resuming session reads it and does not re-ask, and the confirmation stays
auditable.

**Retention is a stated contract, not an implementation detail.**

- The window runs from **last write**, not from creation. A resumed analysis is live work.
- It is a named configuration parameter with a default of 30 days, and its current value is stated
  verbatim in `analysis_open`'s description, where the model reads it [5].
- Expiry deletes the record. Any tool called with an unknown or expired id returns `isError: true`
  — a recoverable tool error, not a JSON-RPC error — naming the retention window and the two ways
  out: open a fresh analysis, or list `rubricator://analyses`.
- The server does not distinguish *expired* from *never existed*. The id is opaque and unguessable,
  so there is nothing to be learned from the difference and nothing to leak by refusing to tell.
- **Export defeats retention.** An exported analysis is a file the user owns; the window governs
  only rubricator's working store. Retention that could destroy a deliverable would be a different
  and much worse decision.

**Resumption is exposed three ways**, because the user may arrive by any of them: a
`rubricator://analyses` resource, so the *host* can list in-progress work without a tool call [6];
`analysis_open` with an existing id; and a `resume` prompt that reads the state and narrates what is
left.

**The store lives in the platform user-data directory, behind a Mapping interface, and never inside
the package directory.** One record per analysis plus a corpus-index sidecar. The location rule is
not a preference: a code directory is a build output, and a deploy that syncs it eventually deletes
everything the user was working on. The Mapping interface is what lets the store be a directory of
JSON files today and object storage later without touching a single tool implementation.

## Consequences
Every intermediate state is inspectable and renderable by comparanda with no conversion, which makes
a partial analysis a legitimate deliverable rather than a broken one. Resumption costs no schema
surface at all — it is read entirely off missingness codes that exist for other reasons.

The costs are real and named: a retention policy someone must honour, an expiry path every tool
taking an `analysis_id` must handle, and a store abstraction that must stay swappable.

**This places one structural requirement on comparanda**, which the schema request register does not
currently carry because it registers fields and this is not a field: **a document with zero
alternatives and zero criteria must validate strict**, since that is exactly what `analysis_open`
creates. Nothing in comparanda says today whether it does. Per ADR-0002 this is a request across the
boundary, and it belongs on the register as a shape requirement so it is settled before the schema
freeze rather than at it.

**A note for the missingness rename.** When comparanda's closed set is amended, `unknown` in
rubricator maps to two different codes depending on the site, and this is a per-site mapping rather
than a search-and-replace. The resume semantics above take `indeterminate` — someone looked and
could not determine. ADR-0006's honesty rule, *no citable span ⇒ never a low-confidence score*,
takes `not-evidenced`. `pending` here becomes `deferred`.

## Alternatives considered
- *A bespoke checkpoint format.* Guarantees a conversion step and a second schema to keep in sync
  with the first, and buys nothing a partial analysis does not already give.
- *Client-held state — MRTR `requestState` or a Tasks `taskId`.* Neither survives a new chat [1][2].
  Tasks remains genuinely useful for progress visibility inside one long populate run; that is a
  different problem and support for it is per-client.
- *Prompt caching.* Minutes, and a cost optimisation rather than state [3].
- *A store inside the package directory.* Data in a code directory. The deploy eventually deletes it.

## Evidence
Decision summary row 34 and § 6 of [`docs/research/findings-method.md`](../research/findings-method.md);
[`docs/research/sections/r6-mcp-and-agent-architecture.md`](../research/sections/r6-mcp-and-agent-architecture.md)
§ 7 (the mechanism table and the five-part recommendation). The zero-alternatives requirement and the
per-site missingness mapping are corrections raised in the phase-0 adversarial review.

1. [MCP — Multi Round-Trip Requests (MRTR), revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
2. [MCP — Tasks extension overview (2026)](https://modelcontextprotocol.io/extensions/tasks/overview)
3. [Pricing — Anthropic (2026)](https://platform.claude.com/docs/en/about-claude/pricing)
4. [LangGraph — Persistence: checkpointers, threads, stores (2026)](https://docs.langchain.com/oss/python/langgraph/persistence)
5. [MCP — Tools, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
6. [MCP — Resources, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
