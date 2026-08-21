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

## Amendments

### 2026-08-21 — Confirmed by round-1 research (no change to the decision)

Round-1 research reviewed this ADR and confirms it. Nothing above changes. One section of the
research argued for amendment; the resolution was to confirm, and to put what was missing into new
ADRs — see below.

The evidence strengthened it from three directions.

**The failure mode is measured, not feared.** An audit of four deployed generative search engines
found only 51.5% of generated sentences fully supported by their associated citations, and only
74.5% of citations supporting the sentence that cited them [1]. Those are shipped systems whose
whole premise is citation. That is the empirical case for this entire policy.

**"Confidence means evidence quality, not model certainty" is the only defensible reading.** Asking
a model how sure it is yields systematically overconfident answers [2], and agreement across sampled
draws correlates only weakly with correctness [3] (single-author preprint; treat as weak evidence).
Evidence quality is the one uncertainty signal a deterministic tool can check — which is what makes
this definition testable rather than declarative.

**What the policy lacked was enforcement, not revision.** A rule with no stated consequence is a
statement of intent, and an agent under pressure satisfies intent with a low-confidence 3. The
missing consequences are now stated where they can be tested, as new ADRs citing this one as parent
rather than as a superseding ADR: **ADR-0012** (three enforcement rules — no citable span means
`missing` rather than a low-confidence score, the score is never hedged toward the midpoint, and
contradiction is a downgrade with a named reason — plus the permanent separation of evidential
confidence from procedural stability) and **ADR-0015** (`sourceType`, `stance` and `derivedFrom` —
the machinery that makes "distinguish source types" above checkable rather than merely instructed).

1. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
2. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
3. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065)

Evidence: [`docs/research/findings-method.md`](../research/findings-method.md) § 5, § 7.4, and
§ "Recommended ADR actions".
