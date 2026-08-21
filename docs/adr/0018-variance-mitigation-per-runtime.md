# ADR-0018: Variance-mitigation policy per runtime, and the independence ladder

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0011 fixes the scoring protocol. It does not fix the *budget*, and the two runtimes have opposite
constraints. The deployed agent can spend calls and wait. The connector has one shared transcript, no
temperature knob, no sampling seed, and a human watching the cursor blink. One policy cannot serve
both: it either bankrupts the connector or wastes the deployed agent.

This is also where the honest disclosure lives. Repeating a judgement produces numbers that *look*
like rater agreement, and calling them that would be exactly the manufactured rigour ADR-0006 exists
to prevent. The reasoning — including the admission that no literature covers the connector's case —
is in `docs/research/findings-method.md` § 4.3 [1]; the repeat-count simulation is in
`docs/research/sections/r4-variance-mitigation.md` § 2.3 [3].

## Decision

**Deployed default: cell-wise traversal, a seeded permutation per repeat, `k = 5` with adaptive early
stopping** — halt at 3 when the draws agree, escalate to 9 only for cells the review step flags —
**lower-median reduction, and a full stability report.**

`k = 5` is the knee on a simulation of a 5-level ordinal cell run for the research **(reasoning, not
evidence)** [3]. That simulation centres the mode, so its recovery table is the *best* case for
replication, not the typical one. The literature supports the *shape* of the diminishing return, not
this number [4][5]. Adaptive early stopping is separately evidenced: it cuts the sample budget by up
to 7.9× at under 0.1% accuracy cost [4], and by 34–84% at comparable accuracy [6]. It is what makes
`k = 9` affordable on contested cells by making `k = 3` sufficient on unanimous ones.

**Connector default: cell-wise, seeded permutation, `k = 1`**, then review → value-of-information
budget allocation over pivotal cells → re-score with the prior withheld → render the disclosure. A
fresh-session pass over the top pivotal cells is offered as an explicit **optional upgrade** whose
independence rung is recorded.

**Both runtimes: never a mean; never a point reduction over a polarised cell; never a reliability
coefficient over in-session assertions labelled as inter-rater agreement.**

**Every assertion carries its rung on the independence ladder:**
`in-session < fresh-session < distinct-model < distinct-human`. Each rung removes a class of shared
cause; none removes them all except the last. **A statistic over rung-1 assertions is test–retest
reliability, not inter-rater reliability, and the report must say so.** More generally, an agreement
statistic is **labelled by the lowest independence rung present in the assertion set it was computed
over** — the same rule `comparanda` states for the presenting side, so the two repos say one thing. At
`in-session` the label is agent self-consistency, never "agreement".

**Every analysis carries a `procedure` record** — traversal, `k`, seeds, prompt versions, model id,
and whether re-scoring withheld the prior — **and a rendered disclosure.** The connector's isolation
is labelled **in-session isolation**: attenuation, not elimination, because the transcript is shared.
The disclosure text is content, not code (ADR-0003), so a reviewer edits the wording without a
release.

**The headline stability statistic is the weight-free dominance survival rate** — the fraction of
repeated matrices in which an alternative remains non-dominated — plus Pareto-set churn.
"Non-dominated" means **not *necessarily* dominated under `comparanda`'s ADR-0019 interval
semantics**, over a single whole-analysis scope unless alternatives groups are declared, with the
comparison basis named in the result. It is not the naive pairwise rule. Because a contingently
missing cell widens to the criterion's declared range, a single blank in a row makes that alternative
both undominatable and unable to dominate — so **blank density inflates the survival rate**, and the
stability report returns blank density alongside the compression fraction as its discrimination
counter-metric. Kendall's tau-b and top-1 churn are the **secondary** report, computed only when the
user has declared weights.

## Consequences
The two runtimes produce differently-qualified output from the same protocol, and the difference is
stated rather than hidden.

The connector's flagship mitigation has **unknown magnitude** until the ADR-0008 harness runs. Prior
judgements stay in the transcript, so how much of cell-wise isolation survives a shared session is
measurable and is not yet measured. It is the highest-value open question in the project and it costs
a few dollars.

Demoting Kendall's τ replaces the owner's own headline statistic [2] and the decision rule keyed to
τ ≥ 0.9 / 0.7 that came with it. That rule is not lost — it becomes the secondary report, live the
moment weights exist.

## Alternatives considered
- *One policy for both runtimes.* Either bankrupts the connector or wastes the deployed agent.
- *Self-reported confidence as a stability proxy.* Verbalised self-confidence is systematically
  overconfident [7], and sampled agreement correlates only weakly with correctness [8].
- *Kendall's τ over the induced ranking as the headline* [2] § 8. It needs a weighted total, which the
  companion tool refuses to compute by default. A stability report whose headline number requires the
  thing `comparanda` declines to produce is architecturally wrong.
- *Larger `k` on contested cells.* More repeats make a polarised cell's point reduction monotonically
  more misleading (ADR-0011). Sampling reveals bimodality; it cannot resolve it.

## References
1. [Findings — comparison method and prompting (2026)](../research/findings-method.md) — in this repository, § 4.3
2. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](../research/scoring-order-effects.md) — in this repository, § 8
3. [Mitigating evaluation variance and quantifying the uncertainty that remains (2026)](../research/sections/r4-variance-mitigation.md) — in this repository, § 2.3
4. [Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs — Aggarwal, Madaan, Yang & Mausam (2023), EMNLP](https://arxiv.org/abs/2305.11860)
5. [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs — Loo (2025)](https://arxiv.org/abs/2511.00751)
6. [Escape Sky-high Cost: Early-stopping Self-Consistency for Multi-step Reasoning — Li et al. (2024), ICLR](https://arxiv.org/abs/2401.10480)
7. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
8. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065) — *single-author preprint; weak evidence*
