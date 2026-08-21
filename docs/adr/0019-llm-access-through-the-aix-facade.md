# ADR-0019: All LLM access goes through the local `aix` facade, and an import test enforces it

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
The deployed runtime needs model access; the connector must have none. ADR-0003 states that as
prose — "no tool may require a model" — and ADR-0010 draws the boundary it implies. Prose erodes
the first time a tool "just needs a quick classification", and a boundary nobody can run is a
boundary that is already gone by the second contributor.

The local ecosystem already has a facade over provider SDKs, `aix`. Using it rather than a provider
SDK directly is the difference between one chokepoint for model configuration and credentials, and
many. A source read found the facade to be the right chokepoint and currently insufficient for what
Phase 4 needs — see `docs/research/sections/r7-local-ecosystem.md` § 4, "`aix` — the right
chokepoint, currently insufficient for ADR-0008", together with its gap list, and
`docs/research/findings-method.md` § 6 row 37.

## Decision

**The deployed runtime never touches a provider SDK directly.** The `aix` facade is the single
chokepoint for model configuration, credential resolution, model aliases and scoped overrides. Any
model access anywhere in this repository — the agent loop, the CLI, the evaluation harness — goes
through it.

**`rubricator.mcp` must never import `rubricator.agent`**, and this is enforced as a test, not as a
convention: a subprocess runs `python -c "import rubricator.mcp"` and asserts that neither `aix` nor
the underlying provider library (`litellm`) appears in `sys.modules` afterwards. That test is the
mechanical enforcement of ADR-0003's rule and of ADR-0010's boundary, and it is worth more than
either written as prose. It fails on the import, before anyone has to reason about whether a
particular model call was justified.

**The connector installs with no LLM dependency.** `pip install rubricator` gets the tool surface,
the prompts and the schema validation; `pip install "rubricator[agent]"` adds `aix`. The extra is
what makes the import test's claim true of a real installation rather than only of a source tree.

**Six facade gaps go upstream as issues against `aix`, and two must close before the Phase 4
variance work of ADR-0008 and ADR-0018 can start.** In the research's numbering, tracked from issue
#34:

- **A1** — a completion primitive that does not discard the response, returning all `n` choices,
  `usage`, `finish_reason` and the raw response rather than one message's content. **Blocking.**
- **A2** — a concurrent sampling primitive, preferring provider-side `n` where the provider supports
  it. Today ten samples are ten blocking serial calls returning ten bare answers. **Blocking.**
- **A3** — membership and bounds enforcement in the constrained-answer helper, which type-coerces
  its answer and then never checks it against the allowed set. This is a correctness bug, not a
  gap, and anchored criterion levels are exactly the case it silently passes. Until it closes, this
  repository must not rely on that helper for scoring.
- **A4** — provider-enforced structured output. A measure with its evidence references is a nested
  object carrying a list of spans, which the current flat prompt-appended schema cannot express;
  this is also ADR-0013's second enforcement point.
- **A5** — documented `seed` support with capability probing, so a caller degrades deliberately
  instead of discovering silently. Without it, "the model is unstable" and "the provider ignored
  our seed" are the same observation.
- **A6** — error propagation in the batch chat helper, which turns exceptions into result strings.
  A harness that cannot see a rate-limit will score it.

Every one is a facade gap rather than a capability gap — the library underneath supports all of it
[1][2] — which is what makes fixing them upstream, rather than wrapping around them here, obviously
correct.

## Consequences
A cheap, fast connector install, and one place to change model configuration for the whole
repository. The import test converts the project's central architectural rule into something CI
fails on, which is the only form in which such a rule survives.

The cost is a cross-repo dependency: two `aix` fixes must land before the variance work can begin,
which is a scheduling risk on Phase 4 and the reason to file all six now rather than during it. One
design question stays open upstream and is not ours to settle — whether the facade wants a
`complete()` alongside its deliberately narrow `chat()`, or a different shape.

## Alternatives considered
- *A provider SDK directly in `rubricator.agent`.* Duplicates credential, alias and configuration
  logic that already exists one layer down, and makes the import test harder to state — the test
  works because there is exactly one import to forbid.
- *Wrapping around the facade's gaps locally.* Puts the fix in the wrong repository, where the rest
  of the ecosystem cannot use it, and leaves this repository owning a shadow facade forever.
- *Stating the rule in `CLAUDE.md` and reviewing for it.* This is what was already in place. It is
  how the rule came to be true everywhere and checked nowhere.

## References
1. [LiteLLM — Input Params for `completion()`](https://docs.litellm.ai/docs/completion/input)
2. [LiteLLM — JSON Mode and Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode)
