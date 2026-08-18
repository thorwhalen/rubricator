# ADR-0007: Deliverables and packaging

- **Status:** proposed
- **Date:** 2026-08-18

## Context
Several distinct things could be shipped, and shipping all of them at once is how nothing gets
finished.

## Decision (recommendation — sequence to be confirmed)

Ship in this order:

1. **MCP server** — the tool surface of ADR-0003. Usable from Claude Desktop and Claude Code with
   no API key. This is the minimum viable product and validates the tool decomposition.
2. **Skill / prompt bundle** — the elicitation, scoring and review prompts as content, usable
   directly in a Claude session even without the MCP server running. Nearly free once the prompts
   exist, and the fastest possible path to first value.
3. **Python package** — the deployed agent, on `aw_agents` (ADR-0004), for scheduled and unattended
   runs.
4. **CLI** — `rubricator analyse ./docs --subject "..."` → a comparanda JSON file. Thin wrapper over
   the same tools; disproportionately useful for testing and for users who want no chat at all.

Deferred: a hosted service, a JS/TS runtime (ADR-0004), and any UI — the UI is `comparanda`.

Reserve the npm name even though nothing publishes there initially.

## Consequences
Each stage is independently useful and each validates the layer beneath. The risk is stopping after
(1) and (2) because they are sufficient for the primary user — which would be a legitimate outcome
worth recognising rather than resisting.
