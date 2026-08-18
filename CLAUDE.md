# rubricator — agent guide

The agent that produces `comparanda` analyses. Read `BRIEF.md`, then `docs/adr/` in order.

## The shape of it

One **MCP tool specification**, two runtimes: a connector (Claude supplies the intelligence, no API
key) and a deployed agent (owns its own model access). Tools are deterministic; judgement lives in
the model. **No tool may require a model call** — that would break the connector, where no key
exists.

## Vocabulary

Use `comparanda`'s: **alternatives** (rows), **criteria** (columns), **subject**, **measure**
(stored: score, confidence), **encoding** (view-layer, derived), **missing** (always with a reason).
Never "items" or "features".

## Standing constraints

- **Public repo.** No content from the private analysis this originated in — fixtures included.
- **Prefer a qualified blank to a confident guess.** ADR-0006. This is the product.
- **Cite spans, not documents.** A citation nobody can check is not a citation.
- **Elicit the frame before scoring.** ADR-0005. The criteria discussion is the valuable part.
- **Prompts are content, not code.** Both runtimes serve the same files.
- **Distinguish primary source, secondary summary, and own inference** in every output.

## Companion repo

`comparanda` owns the schema and the UI. This repo depends on its published JSON Schema and
validates at the boundary; the dependency never runs the other way.

## Local ecosystem

`aw_agents` is the declarative agent framework to build the deployed runtime on — find it in the
local package ecosystem and read it before designing. `oa` and neighbours may already have the LLM
access patterns you need.
