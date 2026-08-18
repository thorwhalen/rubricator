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

## Where things live

    docs/adr/                decisions; `proposed` means genuinely open
    docs/adr/PENDING-ACTIONS.md  ADR changes the research recommends, not yet settled
    docs/research/README.md  the research ledger — start here to find out what is known
    docs/research/           the method brief, sections/ (working notes), findings-method.md
    docs/prompts/            prompts as versioned content, served by both runtimes
    skills/                  dev skills — tooling for the agent building this repo

## Dev skills

Real files in `skills/`, surfaced through relative symlinks in `.claude/skills/`. These are for
the agent *building* rubricator, not for end users. (End-user skills — run an analysis, add a
criterion, re-score a column, audit an existing analysis — ship as MCP prompts instead; see
ADR-0003 and ADR-0007.)

- **`rubricator-dev-tool-contract`** — read before adding or changing any tool. Owns the one
  architectural rule (tools are deterministic, the loop is not), the concrete tests that enforce
  it, and the tool-vs-prompt-vs-resource decision.
- **`rubricator-dev-prompt-change`** — read before editing any prompt. Owns the honesty clause
  every prompt must restate, the version-and-changelog requirement, and the rule that a prompt
  change does not land without an evaluation run.

## Companion repo

`comparanda` owns the schema and the UI. This repo depends on its published JSON Schema and
validates at the boundary; the dependency never runs the other way.

## Local ecosystem

`aw_agents` is the declarative agent framework to build the deployed runtime on — find it in the
local package ecosystem and read it before designing. `oa` and neighbours may already have the LLM
access patterns you need.
