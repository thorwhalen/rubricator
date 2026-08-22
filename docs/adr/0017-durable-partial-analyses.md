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

## Amendments

### 2026-08-21 — the missingness rename has landed; the conditional is discharged

- **Deciders:** Thor Whalen

The Decision and Consequences above write the missingness rename as prospective — "when
comparanda's closed set is amended" — and so does ADR-0012's enforcement rule 1 ("when
`comparanda`'s missingness reason set splits"). It has been amended. `comparanda`'s ADR-0009 carries
a 2026-08-21 amendment landing `pending` → `deferred`, `unknown` → `indeterminate` and the new
`not-evidenced`, and the six-code core set ships in that repository's code and in its
`docs/domain-model.md`. Read every such conditional in this repository as discharged, and the
mappings already stated as the current spelling:

- **resume semantics** — `not-assessed` unchanged; `pending` is **`deferred`**; the "someone looked
  and could not determine" branch is **`indeterminate`**;
- **ADR-0006's honesty rule**, no citable span ⇒ never a low-confidence score — **`not-evidenced`**.

What does not change is that replacing the `unknown` literal is a per-site mapping and never a
search-and-replace: the two destinations mean different things, and `comparanda`'s ADR-0009
amendment § 8 says so in the same words. Prose in this repository that still reads `unknown` is
corrected site by site, and `docs/ROADMAP.md` § 2 tracks that sweep.

### 2026-08-22 — the stored record splits into a frame and N contributions, merged on read

- **Deciders:** Thor Whalen

**What this narrows.** The Decision states: "**The stored record is itself a schema-valid comparanda
analysis** — not a bespoke checkpoint format that must later be converted", and fixes the physical
layout as "one record per analysis plus a corpus-index sidecar". A decision of 2026-08-22 puts a
team arguing over one analysis into v1, with files as the single source of truth and **one file per
contributor per analysis, so that two people editing never collide**. A contributor's file is a
fragment of an analysis, not a whole one. Both clauses as written are therefore no longer true of
the bytes on disk.

**Their reasoning is preserved exactly, which is why this is an amendment and not a supersession.**
The clause exists to rule out a second schema and a conversion step. There is still exactly one
schema. Each contributor file validates against it as a fragment; `read()` returns one whole,
schema-valid `comparanda` analysis; every intermediate state is still renderable with no special
handling; and nothing anywhere converts between two formats. What changed is the *granularity* of a
record, not its kind.

**The layout, which is the whole of the collision-freedom argument:**

    {analysis_id}/frame.json                     subject, criteria, alternatives, groups,
                                                 declared vocabularies, salt
    {analysis_id}/contributors/{author_id}.json  ONE FILE PER CONTRIBUTOR
    {analysis_id}/corpus/index.json              the rendition records
    {analysis_id}/corpus/{sha256}                the normalised renditions
    {analysis_id}/projection/                    generated, one-way, never read back

Two contributors never write the same key. That single invariant is what makes a
`git pull --rebase && git push` safe with no locking protocol, and it is the only reason a
last-write-wins provider is safe on the browser side. It is load-bearing, so it is recorded as a
capability and tested, never left as folklore.

**The merge happens on read and is never written back.** `read()` reconstitutes one analysis from
the frame plus N contributor files, deterministically: cells keyed on
`(alternativeId, criterionId, measure)`, assertions unioned rather than concatenated, authors
deduplicated on id, and a genuine same-version conflict **refused** — both assertions retained, the
cell marked refused — rather than resolved by timestamp. Last-write-wins is precisely the failure
the per-contributor layout exists to prevent, and reintroducing it inside the merge would be
silent. Never writing the merged document back is what keeps contributor writes disjoint.

**The Mapping interface this ADR mandated is now named.** "The store lives in the platform user-data
directory, behind a Mapping interface, and never inside the package directory" stands verbatim and
is honoured as `MutableMapping[str, bytes]` — `collections.abc`, nothing invented — with `dol`
supplying the implementations. The user-data location stands, and it now has a second reason: the
deploy tooling for the application of ADR-0025 hard-fails a deploy that leaves data inside its
delete blast radius. What this ADR did not contemplate is a **second target**: a shared GitHub
repository, reached by the same code path with a different root. That, and the write-only
Discussions/Issues projection generated from the files and never read back as truth, are
**ADR-0023**.

**What does not change.** The opaque unguessable `analysis_id`; resume semantics read entirely off
missingness codes with nothing branching on a literal; the step-4 confirmation stored as authored,
timestamped provenance rather than a flag; retention running from last write with its window stated
verbatim in `analysis_open`'s description; the server not distinguishing expired from never-existed;
and export defeating retention.

**One consequence worth stating before it is discovered.** Every read is now a merge, and v1
deliberately caches nothing. That is free at fixture scale and O(contributors × cells) at fifty
contributors and five hundred cells. The fix, when it hurts, is one caching decorator at the
composition root keyed on the content hash of the contributor set — no interface changes. Naming
the deferral is the point: an uncached merge nobody wrote down becomes a mysterious slowness six
months from now.

Refs #51, #82.
