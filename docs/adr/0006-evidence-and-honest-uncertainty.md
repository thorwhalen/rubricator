# ADR-0006: Cite spans, and prefer a qualified blank to a confident guess

- **Status:** accepted
- **Date:** 2026-08-18

## Context
An LLM will produce a plausible number for any cell you ask about, whether or not anything supports
it. That is the central risk of this entire product: it manufactures the *appearance* of rigour at
scale, and a well-formatted matrix is unusually persuasive.

## Decision

**Every asserted value carries a confidence and, where possible, evidence.** Evidence references
point at **spans** — a character range, a page region, a line range — not whole documents. A
citation nobody can check is not a citation.

**No-evidence is a first-class outcome.** When the context does not support a judgement, emit
`unknown` with a note, not a hedged 3. The schema has qualified missingness precisely so the agent
can be honest, and the agent must prefer it.

**Confidence means evidence quality, not model certainty.** Define it concretely — high means
directly supported by cited source, medium means inferred from adjacent evidence, low means
plausible reasoning with little support — and hold to it. A calibration check belongs in the
evaluation suite.

**Distinguish source types.** Primary sources, secondary summaries, and the agent's own inference
must be distinguishable in the output. The originating work found *agent-generated summaries being
mistaken for primary authorship* to be the most damaging error class it encountered; that is a
general hazard, not a local accident, and the schema's authorship metadata exists to prevent it.

**Self-critique is part of the deliverable**, not an optional extra: which cells are weakest, which
criteria overlap, what evidence would most change the picture.

## Consequences
The output will be visibly less complete than a naive tool's, and it will be right more often. That
trade is the product. The UI supports it directly: `comparanda` distinguishes missingness kinds and
encodes confidence, so an honest agent produces a *better-looking* result there, not a worse one.
