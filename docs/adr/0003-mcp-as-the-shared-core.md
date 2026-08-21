# ADR-0003: One MCP tool specification, two runtimes

- **Status:** accepted
- **Date:** 2026-08-18

## Context
Two deployment shapes are required: a Claude connector needing no API key, and an independently
deployed agent with its own model access. The naive approach builds these twice and lets them
diverge within a month.

## Decision
The **MCP tool specification is the shared core**. Define the capability surface once — the tools,
their schemas, their contracts, their prompts — and give it two thin runtimes:

- **Connector runtime.** An MCP server. Claude (Desktop, Code, or a connector) supplies the
  intelligence and the loop; we supply tools, schema, prompts and method. No model access, no API
  key, no inference cost borne by us.
- **Agent runtime.** A process that owns a model client and drives the *same* tools through its own
  loop, for scheduled and unattended work.

The division of responsibility that makes this work: **tools are deterministic, the loop is not.**
Anything that must be reproducible — schema validation, evidence extraction, citation resolution,
completeness checks, agreement statistics — is a tool. Judgement stays in the model. A tool that
embeds a model call inside itself breaks the connector case, because there is no key there.

Prompts ship as **content the runtime can serve**, not as strings baked into a Python loop, so the
connector can hand Claude the same elicitation and scoring guidance the deployed agent uses.

## Consequences
- Connector-first is achievable quickly and is the cheapest path to a usable product.
- Both runtimes benefit from every tool improvement.
- Constraint to hold: no tool may require a model. Where a step genuinely needs inference, expose
  it as a *prompt* the caller's model executes, plus a deterministic tool that validates the result.

## Alternatives considered
- *Build the deployed agent first.* Slower to value, and would have grown model calls into the
  tool layer, foreclosing the connector.
- *Two independent implementations.* Guaranteed drift.

## Amendments

### 2026-08-21 — Confirmed by round-1 research (no change to the decision)

Round-1 research reviewed this ADR and confirms it. Nothing above changes.

The central mechanism is now verified end to end rather than assumed. Claude clients surface MCP
prompts as slash commands and MCP resources as `@` mentions [1], so "prompts ship as content the
runtime can serve" is a shipping path, not an aspiration — and it is the sentence that decided
ADR-0004's supersession, because the framework ADR-0004 named cannot serve prompts, resources or
elicitation at all (ADR-0009). It also collapses a deliverable: serving the prompts *is* the prompt
bundle, and ADR-0007 was settled accordingly.

Every mitigation, check and statistic the research recommends decomposes into a deterministic tool
plus a prompt. Nothing in a round of research covering elicitation, scoring, variance, evidence and
packaging needed a tool that thinks.

The one tempting exception is closed. **MCP sampling** — a tool asking the caller's model for a
judgement — was deprecated in specification revision 2026-07-28, with the migration path "integrate
directly with LLM provider APIs" and new implementations told they SHOULD NOT adopt it [2]. So no
judgement call is required. ADR-0010 draws the resulting boundary explicitly, extends it to
embedding calls, and states where model-based checking is still allowed (the offline evaluation
harness, never a tool).

1. [Connect Claude Code to tools via MCP — Anthropic Claude Code documentation](https://code.claude.com/docs/en/mcp)
2. [MCP — Deprecated Features registry, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)

Evidence: [`docs/research/findings-method.md`](../research/findings-method.md) § 6 and § "Recommended
ADR actions".
