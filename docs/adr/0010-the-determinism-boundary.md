# ADR-0010: The determinism boundary — no model calls, no embedding calls, lexical retrieval

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0003 says no tool may require a model, because the connector runtime has no key. It says it as
prose, and prose does not survive contact with a plausible exception. Two looked legitimate: **MCP
sampling** — a tool asking the client's model for a judgement — and **embedding-based retrieval**, a
"small" model that does not feel like a model call.

Both reintroduce the dependency the architecture exists to avoid, and both do worse than that. A
judgement made inside a tool never reaches the transcript, which is where ADR-0006's posture lives
and the only place a user can check it. And a tool whose output moves between runs is untestable by
ADR-0008's stability check — worse, a retrieval change that silently reorders spans is
indistinguishable, from the evaluation suite's side, from a prompt regression.

This ADR turns the prose rule into a boundary with named exclusions, so a reviewer can apply it to a
diff.

## Decision

**No MCP sampling.** It was deprecated in specification revision 2026-07-28, with the migration path
"integrate directly with LLM provider APIs" and new implementations told they SHOULD NOT adopt it
[1]. No judgement call is required. Sampling would have been rejected anyway: ADR-0003's rule is not
"the server holds no key", it is "tools are deterministic".

**No in-tool model calls of any kind, and no embedding calls** — an embedding model is a model. It
needs either a key, which the connector does not have, or a bundled local model, which is a heavy,
non-deterministic dependency whose version silently changes results between runs.

The boundary is drawn at the **tool**, not at the repository. Model-based checkers may run in the
evaluation harness — ADR-0008's citation judge is one — because a harness is offline, has a key, and
is a regression detector rather than an oracle. What may not happen is inference inside a tool the
connector calls.

**Retrieval is lexical.** `corpus_search` is BM25 plus normalised substring matching, with a fixed
tokenizer, a fixed stopword list, a versioned chunker, and ties broken by `(score, document_id,
start)`. Each of those four is named here because each is a place where a change would reorder spans
without announcing itself. This is judged sufficient — a judgement, not a measurement — because the
model does the semantic work in its own loop and can issue several queries.

**Contextual and late-chunked embedding indexes are permitted only in an offline corpus-preparation
step** [2][3], run by the deployed agent or the CLI, producing a static index the connector *reads*.
What the connector cannot do is build one over a corpus ingested mid-session.

**Retrieve by default; inline the corpus only at the enumeration stage, under roughly 25k tokens.**
The two numbers in that sentence come from different places and must not be conflated:

- **~25k is a client ceiling, not a cost figure.** Claude Code truncates tool responses at 25,000
  tokens by default [5]. Returning more than that does not cost more; it silently loses content.
- **The cost crossover is ~20k–40k corpus tokens when you control caching, and ~5k when you do not**
  — arithmetic over published prices, since current models carry no long-context surcharge [4] and
  the 2025-era pricing cliff is gone. In the connector runtime we control neither the cache
  breakpoints nor the context budget, so ~5k is the connector's crossover.

Inlining at the enumeration stage therefore sits deliberately *above* the cost crossover: proposing
alternatives and criteria is the one stage where global recall matters more than precision, and the
recall is worth the tokens. We do not take the minimum of the two figures — in the connector that
resolves to ~5k and cancels the exception this rule exists to state.

The threshold is a named parameter, and the behaviour is **one documented behaviour of
`corpus_search`** — an empty query returns the whole corpus when it is under the threshold and
refuses with an actionable `isError` above it — rather than a branch in the model's head.

## Consequences
Every tool is testable offline, deterministically, byte-for-byte, which is what makes ADR-0008's
stability arm mean anything. Retrieval quality is lower than an embedding index would give; that is
accepted, because the alternative breaks the connector, and anyone wanting better recall runs the
offline preparation step. The four named retrieval components become versioned surface: changing the
stopword list is a release-note event, not a refactor.

## Alternatives considered
- *MCP sampling for the hard cases.* Deprecated [1], and it would hide judgement from the transcript.
- *A bundled small embedding model.* Heavy, non-deterministic dependency; version drift silently
  changes results between runs.
- *Semantic chunking.* Costs compute and does not reliably beat fixed-size chunking.
- *Setting the inline threshold to `min(cost crossover, client cap)`.* In the connector it resolves
  to ~5k and deletes the enumeration-stage exception.

## Evidence
Question rows 30–32 and § 7.6 of [`docs/research/findings-method.md`](../research/findings-method.md);
the pricing arithmetic and the inlining recommendation are in
[`docs/research/sections/r6-mcp-and-agent-architecture.md`](../research/sections/r6-mcp-and-agent-architecture.md) § 6.

1. [MCP — Deprecated Features registry, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
2. [Introducing Contextual Retrieval — Anthropic (2024)](https://www.anthropic.com/news/contextual-retrieval)
3. [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models — Günther et al. (2024)](https://arxiv.org/abs/2409.04701)
4. [Pricing — Anthropic (2026)](https://platform.claude.com/docs/en/about-claude/pricing)
5. [Writing effective tools for agents — with agents — Anthropic Engineering (2025)](https://www.anthropic.com/engineering/writing-tools-for-agents)

## Amendments

### 2026-08-22 — the clock is injected, and the boundary grows two denylists

- **Deciders:** Thor Whalen

**A wall clock is a nondeterminism the boundary does not currently see.** The Decision forbids MCP
sampling, in-tool model calls, embedding calls and hidden network access, and the test that enforces
it intersects each tool module's imports against three denylists. The nondeterministic one is
`{random, secrets, uuid}`; `datetime` and `time` are in none of them. A decision of 2026-08-22
requires every persisted citation check to carry `checkedAt` and `checkerVersion` (ADR-0014's
amendment of the same date), and the first naive implementation of `checkedAt` reaches for
`datetime.now()` inside a tool. That would make the tool layer's output non-reproducible in the one
place the product's whole claim rests.

**The clock becomes an injected dependency.** `rubricator/clock.py` is the only module in this
repository permitted to import `datetime`, and it exports one thing:
`Clock = Callable[[], str]` returning ISO-8601 UTC, with `utc_now` as the real implementation. Every
tool that needs a timestamp takes `now: Clock` as a **required keyword-only argument with no
default**, so the boundary cannot be crossed by forgetting. Determinism is preserved rather than
weakened: identical input *plus identical clock* gives byte-identical output, and a test supplying a
frozen clock is byte-reproducible forever.

**`datetime` and `time` join the `NONDETERMINISTIC` denylist**, with `rubricator/clock.py` as the
single allowlisted module.

**A fourth denylist: the host must not reach the tools.** `{fastmcp, mcp, py2mcp, enlace_connector,
fastapi, starlette, aix, openai, anthropic, litellm}` applied to `rubricator/tools/**` and
`rubricator/schema/**`. This costs exactly what the three existing denylists cost and buys two
things: ADR-0003's "tools know nothing about MCP" becomes mechanical, and the choice of MCP builder
— reopened the same day by ADR-0009's amendment — becomes a one-file change rather than a
commitment.

**And one existing guard is repaired, because it cannot currently fail.**
`test_only_the_schema_facade_loads_a_schema` asserts that the literal string `sketch.json` does not
appear outside the schema package. A module loading a schema by any other filename passes it — and a
second filename is about to exist, because the published artifact and the vocabulary parity file
both land under `rubricator/schema/`. The check becomes: **no module outside `rubricator/schema/`
opens a `.json` file under `rubricator/`.**

**A rule about rules, earned by this repair.** ADR-0012's 2026-08-22 amendment already counted the
guards in this repository that could not fail and warned that a scale seam would be the next place
one hid. Two of them are named above — the filename grep, and a nondeterminism denylist with no
clock in it — and a third is not a guard at all but a test enforcing a retired contract: the
citation module's doctests, which pin a verdict enum ADR-0014 has already retired (see that ADR's
2026-08-22 amendment). The rule that follows is general: **a boundary test must be demonstrated
failing against a deliberate violation before it is believed**, and demonstrating it is part of the
change that introduces it. ADR-0020 restates this as a standing discipline for every seam, not only
for boundary tests.

Refs #46, #48, #63.
