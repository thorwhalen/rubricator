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
