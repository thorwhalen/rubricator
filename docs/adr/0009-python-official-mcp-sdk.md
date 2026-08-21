# ADR-0009: Python, the official MCP SDK, and the rejection of aw_agents as host

- **Status:** accepted (supersedes ADR-0004)
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0004 recommended Python on the local `aw_agents` framework, conditional on reading its source.
The source was read.

`aw_agents`' MCP adapter registers exactly two handlers — `list_tools` and `call_tool` — over the
low-level MCP SDK server. There is no prompts capability, no resources capability, and no seam
through which a consumer could supply either. Tool results are stringified into human-readable text
rather than returned as structured content; the OpenAPI adapter silently drops nested input
sub-schemas, which is precisely where every rubricator tool's contract lives; and no test touches
either adapter. It also contains no model client, no loop, no session and no streaming, so it does
not supply the "own model access" ADR-0004 assumed it would.

ADR-0003 requires the MCP layer to serve prompts and resources — "prompts ship as content the
runtime can serve" is the one sentence that makes one specification serve two runtimes — and
ADR-0005 step 4 requires elicitation. `aw_agents` can do none of it. See
`docs/research/findings-method.md` § 6 and `docs/research/sections/r7-local-ecosystem.md`.

## Decision
**Python for both runtimes.** The schema tooling, the LLM facade and every project convention are
already Python; a JS/TS runtime would share a language with the UI and nothing else. No JS/TS
runtime in v1 — reserve the npm name and revisit only when a concrete deployment target demands it.

**Build the MCP surface on the official MCP Python SDK v2 / FastMCP 4** [1][2], over a core of plain
deterministic functions in `rubricator.tools` that know nothing about MCP. The deciding fact is a
version floor, not aesthetics: FastMCP 4.0.0 is the first release implementing modern-protocol
elicitation via `InputRequiredResult` under specification revision 2026-07-28 [1], and elicitation
is the mechanism for the ADR-0005 step-4 checkpoint. Dual-era support is ours to write and to test —
FastMCP rejects a tool returning an `InputRequiredResult` on a handshake-era connection, so the
fallback branch is our code, not a freebie.

**Reject `aw_agents` as host** — not forever. If a non-MCP chatbot surface is ever wanted, its
OpenAPI adapter becomes a candidate *second consumer of the same functions*, never the host, and its
sub-schema flattening must be fixed first. The local `py2mcp` keeps a real role on the CLI/OpenAPI
line of ADR-0007: it returns a live FastMCP object carrying `.prompt` and `.resource`, but it is
tools-only by design and pins `fastmcp` unbounded, resolving to 3.x today — so adopting it as the
builder would make the load-bearing checkpoint depend on an upstream upgrade outside this project's
control. Contribute `prompts=` / `resources=` kwargs and a FastMCP 4 floor upstream, then revisit.

**Tool surface: 19 tools, 11 minimum viable**, enumerated in `docs/research/findings-method.md`
§ "Proposed MCP tool surface". The 30–50 band at which tool selection degrades counts tools
*available in the session* [3], so 19 plus a host's built-ins sits inside that band rather than
comfortably under it. Adopting 19 is a judgement call, not a clean pass *(reasoning, not evidence)*:
the definitions stay far under the 10k tokens at which deferred loading starts to pay, the research
names a cut order that gives a reduction path, and the surface is revisited if it grows. Measure the
definitions with `count_tokens` rather than trusting the estimate.

**Generation granularity is separated from write granularity.** The prompt asks for one criterion
per generation; the tool accepts a batch. Conflating them would cost 56 round trips on an 8×7 matrix
for no benefit.

## Consequences
The connector installs with no LLM dependency, and the tool core is testable with no MCP present and
no key — which is what keeps ADR-0003's two runtimes honest. The cost is that dual-protocol-era
support and the elicitation fallback are ours to write and to test, and that the tool surface has
less headroom against tool-selection degradation than a first reading of the band suggests; both are
tracked work, not surprises. Rejecting a local framework also leaves an ecosystem gap open —
`aw_agents` still cannot serve prompts, resources or elicitation, and that is worth an issue there
rather than silent absorption here.

## Alternatives considered
- *`aw_agents` as host.* Cannot serve prompts, resources or elicitation, and supplies no model
  access. This ADR exists because ADR-0004 assumed otherwise.
- *`py2mcp` as the builder.* Verified to return a live FastMCP object carrying `.prompt` and
  `.resource`, but tools-only by design and without a FastMCP 4 floor. Revisit after both land.
- *A JS/TS runtime, to share a language with `comparanda`.* The coupling to `comparanda` is the
  schema (ADR-0002), not a language; sharing one buys nothing and costs a second implementation.
- *Amend ADR-0004 in place.* Legal — it was `proposed`, and ADR-0001 permits settling a proposed ADR
  during implementation. Rejected because the decision inverts rather than refines: the framework
  changes, the "if `aw_agents` can host the MCP surface directly, use it" clause is answered "it
  cannot and should not try", and the premise about model access is factually wrong. Superseding
  leaves ADR-0004 readable as the question that was asked.

## References
1. [FastMCP — Elicitation (2026)](https://gofastmcp.com/servers/elicitation)
2. [MCP Python SDK — official repository (2026)](https://github.com/modelcontextprotocol/python-sdk)
3. [Tool search tool — Anthropic (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
