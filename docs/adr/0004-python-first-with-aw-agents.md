# ADR-0004: Python for the agent runtime, on aw_agents; JS/TS deferred

- **Status:** proposed
- **Date:** 2026-08-18

## Context
The deployed-agent runtime needs a host language. The surrounding ecosystem has an existing
declarative agent framework — **`aw_agents`** ("AI Agents for Agentic Workflows": write an agent
once, deploy to several chatbot platforms, with pluggable adapters including MCP for Claude and
OpenAPI for ChatGPT). Locate it in the local package ecosystem and read it before deciding; also
check `oa` and the other AI-adjacent packages there for LLM access patterns already in use.

The consumer of the output, `comparanda`, is TypeScript. So a JS/TS agent runtime would share a
language with the UI but not with the existing agent tooling.

## Decision (recommendation — confirm after reading `aw_agents`)
**Python for the agent runtime**, built on `aw_agents`, because the declarative-spec-to-agent
machinery and the multi-platform adapters already exist there and match this problem exactly.

**The MCP server should be reachable from both.** If `aw_agents` can host the MCP surface directly,
use it and ship one process. If not, the MCP layer is a thin standalone server and `aw_agents`
consumes the same tool implementations.

**No JS/TS agent runtime in v1.** File an issue for it. Revisit only if a concrete deployment
target requires it — running inside a browser extension, or an npm-only distribution. The schema
and the MCP surface are language-neutral, so this stays cheap to add later.

If no adequate JS/TS equivalent of `aw_agents` exists, that is itself worth an issue in the
ecosystem: the declarative-agent-spec-to-deployment gap is real and would be reusable well beyond
this project.

## Consequences
Python packaging for the agent, npm for nothing initially. Reserve the npm name anyway (it is free)
to keep the option open. The team's Python conventions apply — check the ecosystem's project
scaffolding conventions before creating the package layout.
