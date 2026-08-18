# Brief for the implementing agent — rubricator

Read this, then `docs/adr/` in order, then `docs/research/method.md`. Restate your understanding
of the scope before writing code.

## What you are building

An agent that turns context — a prompt, a document set, a repository, a conversation — into a
structured comparison conforming to the **comparanda** schema: alternatives, criteria, scores,
confidence, justifications, and citations back to spans in the source.

Two runtimes over one shared MCP tool specification:

- **connector** — an MCP server; Claude supplies the intelligence, no API key, no inference cost;
- **deployed agent** — Python on `aw_agents`, owning its own model access, for unattended runs.

Ship the connector first. It is the fastest path to something usable and it validates the tool
decomposition that everything else depends on.

## The one architectural rule

**Tools are deterministic; the loop is not.** Schema validation, evidence extraction, citation
checking, completeness reporting, agreement statistics — tools. Judgement — the model. A tool that
calls a model inside itself breaks the connector runtime, because there is no key there. Where a
step genuinely needs inference, expose it as a *prompt* the caller's model runs, plus a
deterministic tool that validates the result.

## Non-negotiables

- **Public repository.** Nothing from the private analysis this originated in — no company,
  product or personal names, in code, fixtures, prompts, docs or commit messages. Fixtures use
  public domains, mirroring `comparanda` ADR-0016.
- **Prefer a qualified `unknown` to a plausible guess.** ADR-0006. This is the product's whole
  claim, and it is the behaviour most likely to erode under prompt edits — which is why ADR-0008
  tests for it explicitly.
- **Cite spans, not documents.**
- **Never present the agent's own inference as source material.** Mark authorship and source type
  on everything.
- **Elicit the frame before scoring.** ADR-0005; do not remove the confirmation checkpoint.

## Order of work

**Phase 0 — research and orientation.** Work through `docs/research/method.md`. Separately: find
and read `aw_agents` in the local package ecosystem, plus `oa` and neighbouring AI packages;
confirm or amend ADR-0004 with what you find. Read the published comparanda JSON Schema — if it
does not exist yet, that repo is the blocking dependency and you should build against the domain
model and a hand-written schema sketch until it lands.

**Phase 1 — tool surface.** Define the MCP tools and their contracts. This is the core artifact of
the whole project; spend real time on granularity. Deterministic tools only.

**Phase 2 — prompts.** The elicitation pipeline of ADR-0005 as versioned content files. Draft
`propose-criteria` first and hardest — it is the highest-leverage prompt in the system.

**Phase 3 — connector.** MCP server, usable from Claude Desktop and Claude Code. Real analyses on
real (public) document sets end to end.

**Phase 4 — evaluation.** ADR-0008. Do not defer this past the point where prompts start changing;
without it, prompt edits are indistinguishable from prompt churn.

**Phase 5 — deployed agent** on `aw_agents`, then a CLI.

## What good looks like

A user points it at a folder of documents and a question. It comes back with proposed alternatives
and proposed criteria *with definitions*, flags two criteria that overlap, and asks for
confirmation. After confirmation it fills the matrix, cites a span for most cells, marks a handful
`unknown` because the documents genuinely do not say, and closes with a note on which three scores
are weakest and what evidence would most change the picture.

Then `comparanda` renders it and a team argues about it productively — which is the actual goal of
both repositories.

## First deliverable

Not code:
1. `docs/research/findings-method.md`;
2. a proposed MCP tool surface — names, signatures, contracts — with the reasoning on granularity;
3. a first draft of the `propose-criteria` prompt;
4. your reading of `aw_agents` and whether ADR-0004 survives it;
5. a phase plan with what you would cut under time pressure.

Then stop and check in.
