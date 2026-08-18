# Research brief — comparison method and prompting

**Do this before writing prompts.** Deliverable: `docs/research/findings-method.md`, plus the
prompt drafts it justifies in `docs/prompts/`. Cite sources.

The premise: structured comparison is a studied practice with known failure modes. An agent that
does it well should be applying a method, not improvising a table.

## 1. How to elicit criteria well

This is the highest-leverage question in the project — everything downstream is determined by it.

- **Value-focused thinking** (Ralph Keeney) — deriving criteria from underlying objectives rather
  than from the alternatives in front of you. Directly applicable to step 3 of ADR-0005.
- **Smart Choices** (Hammond, Keeney & Raiffa) — the PrOACT frame, consequence tables, even-swaps.
  Practitioner-level and probably the best single source for the elicitation prompt.
- Criteria hygiene: completeness, non-redundancy, operability, decomposability. What does the
  literature say about detecting **overlapping criteria**, which is the classic defect and one an
  LLM will happily reproduce?
- How many criteria before a matrix stops being usable? There is work on this.
- Eliciting *definitions* alongside criteria, and why undefined criteria get scored inconsistently.

## 2. Scoring, calibration and bias

- **Calibration training** (Hubbard, *How to Measure Anything*) — how to make confidence estimates
  mean something, and how to test whether they do.
- Anchoring, order effects and scale-use bias in human raters — do LLM raters show the same? There
  is a growing literature on LLM-as-judge; find what it says about position bias, verbosity bias
  and self-consistency.
- **Rubric design**: what makes a 1–5 scale produce consistent scores across raters and sessions?
  Anchored scales with described levels beat bare numbers. Our criteria definitions should probably
  carry per-level descriptors — investigate.
- Should the agent score one criterion across all alternatives (column-wise), or one alternative
  across all criteria (row-wise)? These give measurably different results in human raters; find out
  which is better and whether it holds for models. **This is a concrete, testable design decision.**

## 3. LLM-as-judge practice

- Current best practice for structured evaluation with an LLM: rubric-in-prompt, reference-free vs
  reference-based, pairwise vs pointwise scoring.
- **Pairwise comparison** is more reliable than absolute scoring for humans, and there are
  aggregation methods (Bradley-Terry, Elo) that turn pairwise judgements into a scale. Worth
  considering as an alternative or complement to direct 1–5 scoring, especially for the criteria
  where absolute anchors are hard.
- Self-consistency, ensembling and when they are worth the tokens.
- Structured-output enforcement: how to guarantee schema-valid output without destroying reasoning
  quality.

## 4. Evidence extraction and citation

- Span-level citation techniques and how to verify a citation actually supports its claim.
- Chunking and retrieval for a document corpus that must be *cited*, not merely summarised.
- Attribution benchmarks and metrics — how is citation faithfulness measured in the literature?

## 5. Agent architecture

- Read `aw_agents` in the local ecosystem (see ADR-0004) before designing anything. Also look at
  `oa` and the other AI-adjacent local packages for existing LLM access patterns.
- MCP server design: tool granularity, when to expose a prompt vs a tool, how to ship resources.
  Study a few well-regarded MCP servers rather than only the specification.
- Long-context vs retrieval for a large corpus, and the cost curve of each.
- Human-in-the-loop checkpointing that survives a session boundary.

## 6. Dev skills

Produce agent-facing skills for the recurring work: running an analysis end to end, adding a
criterion to an existing analysis, re-scoring one column against new evidence, auditing an existing
analysis for overlap and thin evidence. Follow the local `dev-skills-workflow` conventions.
