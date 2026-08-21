# ADR-0007: Deliverables and packaging

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
Several distinct things could be shipped, and shipping all of them at once is how nothing gets
finished. The original recommendation named four: an MCP server, a skill / prompt bundle, a Python
package, and a CLI. Whether those four are really four is the question this ADR settles.

## Decision

Ship in this order.

1. **MCP server, prompts included** — the tool surface of ADR-0003 *and* the elicitation, scoring
   and review prompts, served as MCP prompts and resources from the same server. MCP prompts are a
   user-controlled feature that clients surface as slash commands [1], and Claude clients surface
   server resources as `@` mentions [2]. Serving the prompts therefore **is** the prompt bundle:
   there is no second artifact to build, package, or keep in sync. Usable from Claude Desktop and
   Claude Code with no API key. This is the minimum viable product and it validates the tool
   decomposition.
2. **Python package** — the deployed agent of ADR-0009, for scheduled and unattended runs.
3. **CLI** — `rubricator analyse ./docs --subject "..."` → a comparanda JSON file. A thin wrapper
   over the same tools; disproportionately useful for testing and for users who want no chat at
   all. The local `py2mcp` belongs on this line, generating the CLI/OpenAPI surface — not in the
   connector, whose host is settled by ADR-0009.

Deferred: a hosted service, a JS/TS runtime (ADR-0009), and any UI — the UI is `comparanda`.

Reserve the npm name even though nothing publishes there initially.

## Consequences
Each stage is independently useful and each validates the layer beneath. One fewer artifact means
one fewer place for the method to drift: the prompts stay versioned markdown on disk with a thin
assembler in front of them, and every runtime reads the same files.

The risk is stopping after stage 1, because it is sufficient for the primary user. Folding the
prompts in strengthens that risk rather than removing it — the connector now *is* the product, and
stages 2 and 3 are reach rather than completion. That remains a legitimate outcome, worth
recognising rather than resisting.

What becomes hard: anyone wanting the method without an MCP client has no packaged path to it until
stage 3. Accepted; the prompt files are readable on their own.

## Alternatives considered
- *A separate skill bundle shipped alongside the server.* Two copies of the same prompts, two
  release cadences, and guaranteed drift — for a convenience the client already provides.
- *`py2mcp` as the connector's builder.* It is tools-only today, and the connector needs prompts,
  resources and elicitation. It keeps its role on the CLI/OpenAPI line. See ADR-0009.

## Settlement
Settled from `proposed` to `accepted` under ADR-0001, which permits closing a proposed ADR by
changing its status with reasoning. The Phase 0 research (`docs/research/findings-method.md` § 6,
and the working notes in `docs/research/sections/r6-mcp-and-agent-architecture.md` § 3) confirms the
sequence and collapses the item count: **deliverables (1) and (2) are one artifact, not two.** Two
further corrections come with it — `py2mcp` moves from the connector to the CLI/OpenAPI line, and
the deployed agent's runtime is supplied by ADR-0009, not by the superseded ADR-0004 the original
text cited.

One scope note, so the collapse is not over-read later: the artifact dissolved here is a *shipped,
end-user* prompt bundle. Agent-facing dev skills inside this repository are a separate category and
are untouched by this decision.

## References
1. [MCP — Prompts, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)
2. [Connect Claude Code to tools via MCP — Anthropic Claude Code documentation](https://code.claude.com/docs/en/mcp)
