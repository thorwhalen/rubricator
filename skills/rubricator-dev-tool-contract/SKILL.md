---
name: rubricator-dev-tool-contract
description: Use when adding, changing, reviewing, or testing any tool in rubricator's MCP tool surface. Covers the one architectural rule — tools are deterministic, the loop is not — the concrete tests that enforce it (no model call, no embedding call, no network non-determinism, same input twice gives byte-identical output), how to decide tool vs prompt vs resource, the contract every tool must document, and the granularity heuristics. Trigger on any work under the tool layer, on a new tool proposal, on "should this be a tool or a prompt", or when a tool needs inference to do its job.
metadata:
  audience: developers
---

# rubricator tool contract

**The one architectural rule (ADR-0003): tools are deterministic; the loop is not.**

rubricator has two runtimes over one tool specification. The connector runtime has **no API
key and no model access** — Claude supplies the intelligence. Therefore:

> A tool that embeds a model call inside itself breaks the connector runtime, because there is
> no key there.

This is not a style preference. It is the property that lets one specification serve both
runtimes, and it is the first thing to erode under pressure ("just this once, the tool needs to
summarise…").

## The determinism test — run this on every tool

A tool passes only if **all** of these hold:

1. **No model call.** Not a chat completion, not a completion, not a rerank.
2. **No embedding call.** An embedding is a model call. Retrieval inside a tool must be
   lexical and reproducible (BM25 / normalised substring), with a **fixed tokenizer and a fixed
   tie-break**, or ADR-0008's stability test measures the retriever's noise instead of the
   agent's.
3. **No MCP `sampling`.** It looks like the perfect escape hatch — the *client's* model does the
   work, so the server stays key-less. It is not available: sampling was deprecated in the
   `2026-07-28` protocol revision. Do not design around it.
4. **Same input twice → byte-identical output.** No wall-clock, no `random` without an
   explicitly-passed seed, no set/dict iteration order leaking into output, no locale-dependent
   formatting.
5. **No hidden network.** If a tool must fetch, the fetch is the tool's declared purpose and its
   result is content-addressed or cached, never an invisible dependency.

Every tool module gets a test asserting (4), and the package gets one import-boundary test
asserting that the tool layer never imports the model-access layer. That boundary test is what
makes the rule survive a refactor by someone who has not read this file.

## "But this step genuinely needs judgement"

Then it is **not a tool**. Split it:

| Part | Where it goes |
|---|---|
| the judgement | a **prompt** the caller's model executes |
| the check that the judgement is well-formed | a **deterministic tool** that validates the result |

This split is the core design move of the whole project. `propose-criteria` is a prompt;
`validate_criteria` (definitions present? polarity declared? level of measurement declared?
overlapping pairs flagged?) is a tool. The model decides; the tool refuses to let a malformed
decision through.

Concretely, the pattern for a stage is: **prompt → model produces candidate → tool validates and
normalises → tool persists into the partial analysis.**

## Tool vs prompt vs resource

- **Tool** — the model calls it, it computes something checkable, it returns structured content.
- **Prompt** — the *user* selects it (surfaced as a slash command in clients); it takes
  arguments and returns messages, and may embed a resource so the method text and the current
  analysis state arrive together. This is the vehicle for "prompts are content, not code"
  (ADR-0003). Prompts live in `docs/prompts/` as versioned files and are *served*, never inlined
  into a Python string.
- **Resource** — addressable content the client can attach (the schema, a fixture, the current
  analysis). Use for things a human might want to reference directly.

## What every tool must document

In the docstring, because it becomes the tool description the model actually reads:

- **What it does**, in one line, in the domain vocabulary (alternatives, criteria, subject,
  measure, encoding, missing — never "items" or "features").
- **Which ADR-0005 stage it serves** (frame / enumerate / propose-criteria / confirm / populate /
  review).
- **Its determinism justification** — one line saying why it needs no inference.
- **Its failure mode** — what it returns when it cannot do the job. Never a silent empty result.

## Granularity

- Fewer, well-named tools beat many overlapping ones; tool-selection accuracy degrades as the
  surface grows, and the tool list itself costs context on every turn.
- Split a tool when two callers want different halves of it. Merge two when they are never
  called apart.
- A tool that is only ever called immediately after another is a sign the pair should be one
  tool — unless the model needs to *see* the intermediate result to decide.
- Mark every tool with whether it is in the minimum viable set. Under time pressure the surface
  is cut, and it should be obvious what survives.

## The honesty rule applies to tools too

ADR-0006 says prefer a qualified blank to a plausible guess. For a tool that means: when
input is insufficient, return an explicit, typed "cannot determine, because X" — never a
default, never a zero, never an empty list that reads as "nothing found" when it means "did not
look".

## Where things are

    docs/adr/0003-mcp-as-the-shared-core.md   the rule this file enforces
    docs/adr/0005-the-elicitation-pipeline.md  the stages tools serve
    docs/adr/0006-evidence-and-honest-uncertainty.md  the honesty rule
    docs/research/findings-method.md          the proposed tool surface and its reasoning
    docs/prompts/                             prompts as versioned content
