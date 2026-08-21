# ADR-0013: Structured output, and the JSON Schema subset the tool surface may use

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
Every judgement this agent makes — a measure, a missingness reason, a criterion definition — must
arrive as schema-valid structured data. The standing objection to that is a widely-cited paper
reporting that format restriction degrades reasoning [1]. It does not survive reading its own body:
**100% of its degraded responses declared the answer key before the reason key**, which turns
zero-shot chain-of-thought into direct answering, and its own results with a real constrained
decoder show the structured condition *winning* on one of three tasks. An independent rebuttal
identifies non-equivalent prompts between conditions and the conflation of fine-tuned "JSON mode"
with constrained decoding [2]; an independent benchmark finds constrained decoding *improves*
accuracy on all three reasoning tasks by three to four points [3]. The effect is a field-ordering
artifact, not a property of constrained decoding.

The real constraint is elsewhere. Providers achieve near-total schema compliance by supporting only
a conservative subset of JSON Schema in constrained mode [5], and that subset is a constraint on
**our tool signatures**, not on some later serialisation layer. It has to be honoured before Phase 1
freezes the surface: replacing `minimum`/`maximum` with `enum` across a settled surface is pure
rework.

## Decision

**Emit every judgement through grammar-constrained sampling, in both runtimes.** In the connector,
judgements arrive as tool-call arguments under `strict: true` [4] — the enforcement is applied by
the caller's model, the schema is content we ship, and our side stays deterministic, so ADR-0003's
"no tool may require a model" survives intact. In the deployed agent, the same JSON Schema goes
through the provider's constrained decoder. Choose that decoder by measured **compliance rate**
(empirical ÷ declared coverage), never by declared feature list; an under-constraining engine needs
the same post-validation as an unconstrained one [3].

**Every emitted judgement schema declares its reasoning field before its value fields.** Property
declaration order is generation order under constrained decoding, so this is the one place where
schema layout changes the answer. Deliberation happens *outside* the constrained region — in prose,
or in the model's thinking block — and the constrained region carries the verdict only.

**The supported subset is a hard constraint on the tool surface.** A tool author runs this against a
signature before it ships:

1. Is every bounded numeric an `enum`? A 1–5 score is `{"type": "integer", "enum": [1,2,3,4,5]}`.
   `minimum`, `maximum` and `multipleOf` are unavailable.
2. Are there no string-length constraints? `minLength`/`maxLength` are unavailable.
3. Is `additionalProperties: false` on every object? Anything else is rejected in strict mode.
4. Is every `$ref` **internal** — `$defs` and `#/…` only? Internal references are fully supported and
   are how a nested-but-bounded structure is expressed. External `$ref` is not.
5. Is the schema non-recursive? No self-referential criterion trees in a tool schema.
6. Is every `minItems` either 0 or 1? Other values are unavailable.
7. Is every `enum` over scalars? `enum` of objects is not supported.

Everything else the surface needs is available: the seven types, `const`, `anyOf`, `allOf`,
`required`, `default`, and string `format` (`date-time`, `date`, `uri`, `uuid`, …) [5].

**Range checks move into the deterministic validator.** A span offset pair cannot be
range-constrained in the schema; it is checked in `analysis_validate` and the other deterministic
checkers, which is where it belonged anyway. The subset is a constraint on what the model may *say*,
and the validator carries the rest.

**Two enforcement points, both required, and they are not the same mechanism.** `inputSchema` plus
strict mode constrains what the **model** may say. `outputSchema` plus our own validator constrains
what the **server** may return — MCP states that a server MUST return structured results conforming
to a declared `outputSchema`, and is explicit that `structuredContent` is server-produced data
"unrelated to LLM 'structured outputs'" [6]. Every tool declares an `outputSchema` and returns
`structuredContent`, and every structured result passes the same deterministic validator before it
becomes part of an analysis.

Two limits worth stating so nobody has to rediscover them. `additionalProperties: false` constrains
object **keys**, not the values of a property — it does not freeze the missingness reason-code set,
and nothing here says reason codes are an `enum`. And the MCP elicitation `requestedSchema` used at
the ADR-0005 checkpoint is narrower still — a flat object of primitives — which is a separate
constraint on that one interaction, described in
[`docs/research/sections/r6-mcp-and-agent-architecture.md`](../research/sections/r6-mcp-and-agent-architecture.md) § 1(c).

## Consequences
Schema validity stops being an ADR-0008 metric we hope for and becomes a property of the pipeline.
The reasoning-first rule costs nothing and is invisible in the output, so it will be quietly
violated by anyone who does not know why it is there — the checklist above is what a reviewer holds
a diff against.

The subset is restrictive, and expressive schemas must be flattened; the validator carries what the
schema cannot. Grammar compilation adds latency on first use of a schema and is cached for roughly a
day, invalidated by a structural change but not by a `name`/`description` change [5] — so tool
schemas stay stable across a session while descriptions may be iterated freely.

## Alternatives considered
- *Free-text output plus a parser.* Reintroduces exactly the failure the schema exists to prevent.
- *Unconstrained JSON mode.* A weaker guarantee for no reasoning benefit, and the conflation that
  produced the objection in the first place [2].
- *Reasoning after the value.* The measured cause of the degradation the objection rests on [1].
- *Keeping `minimum`/`maximum` and validating leniently.* Defers a known rewrite past the Phase 1
  freeze, which is when it becomes expensive.

## Evidence
Question row 15 and § 3 of [`docs/research/findings-method.md`](../research/findings-method.md); the
full reading of the format-restriction paper, the subset enumeration and the two-enforcement-point
argument are in [`docs/research/sections/r3-llm-as-judge.md`](../research/sections/r3-llm-as-judge.md)
§ 8.1–8.2.

1. [Let Me Speak Freely? A Study On The Impact Of Format Restrictions On Large Language Model Performance — Tam, Wu, Tsai, Lin, Lee & Chen (2024), EMNLP Industry Track](https://aclanthology.org/2024.emnlp-industry.91/) — *cite for its field-order finding, not for its abstract*
2. [Say What You Mean: A Response to 'Let Me Speak Freely' — .txt Engineering (2024)](https://blog.dottxt.ai/say-what-you-mean.html)
3. [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models — Geng, Cooper, Moskal et al. (2025)](https://arxiv.org/abs/2501.10868)
4. [Strict tool use — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
5. [Structured outputs — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
6. [MCP — Tools, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
