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

## Amendments

### 2026-08-22 — the headline stands, and all three reports ship behind one seam

- **Deciders:** Thor Whalen

**The override is granted.** The Decision above replaces the owner's own headline statistic, and this
ADR was marked `decision-needed` on the grounds that a human should agree before it landed. He agreed.
The **weight-free dominance survival rate** is the headline, with Pareto-set churn beside it and blank
density as its discrimination counter-metric; **Kendall's tau-b and top-1 churn remain secondary,
computed only when the user has declared weights.** The reasoning that carried it is the one the
*Alternatives considered* section already gives: a stability report whose headline number requires the
weighted total `comparanda` declines to produce is architecturally wrong, and a number that quietly
invents the weights the user never gave is a confident guess wearing a statistic's clothes.

**And then the same generalisation the scale took.** Asked to choose one, the owner asked for all
three:

> "All three should be possible. Again, this should be a parameter/strategy-pattern. By default I'll
> go with your recommendation."

So the stability report is computed by a **selectable strategy with the dominance survival rate as its
default**, and three implementations ship:

| report | needs declared weights | availability |
|---|---|---|
| **dominance survival rate** + Pareto churn + blank density | no | **default** |
| Kendall's tau-b, top-1 churn | yes | live the moment weights exist |
| **per-cell wobble** | no | always |

**Per-cell wobble is promoted to a peer, not kept as a debugging view**, and it earns that on this
ADR's own evidence. The Decision records that a contingently missing cell widens to the criterion's
declared range, so a single blank in a row makes that alternative both undominatable and unable to
dominate — **blank density inflates the survival rate**. That is why the headline ships with a
counter-metric. Per-cell wobble has no such failure: it aggregates nothing, so nothing can be inflated
away, and it answers a question the headline cannot — *which specific scores moved, and by how much*,
which is the question that tells a reader what to go re-check. The two are complementary, and the
report that is immune to the headline's known distortion should not have been the one left out.

What per-cell wobble cannot do is answer "is this analysis trustworthy" in one line, which is why it is
not the default. A report with no headline is a report nobody quotes.

**The seam is subject to the same rule as ADR-0012's scale seam.** No consumer may assume the default
strategy, and any consumer that does needs a test that **fails** when a non-default strategy is
selected. A strategy interface whose default leaks through it is not a seam.

**One consequence the ladder did not have yesterday.** The independence ladder
`in-session < fresh-session < distinct-model < distinct-human` was written with rung 4 as a
possibility. A separate decision of 2026-08-22 puts **a team arguing over a shared document into v1**,
with human and agent contributors as peers, each contribution signed and optionally under a declared
persona. Rung 4 is now routine, and two rules follow that were previously academic:

- **A mixed assertion set is labelled by its lowest rung, exactly as the Decision states** — so four
  in-session agent draws plus one human assertion is labelled *in-session*, i.e. agent
  self-consistency, and **not** inter-rater agreement. The presence of one genuinely independent rater
  does not launder four dependent draws. This is the rule most likely to be quietly broken now that
  mixed sets are common, and it is the one that would manufacture exactly the rigour ADR-0006 exists
  to prevent.
- **A persona is not an independence rung.** One person signing under three declared personas is one
  human, at whatever rung the *sessions* were run; the personas are attribution and framing, not
  evidence of independence. A statistic must never read a persona as a rater.

**What does not change.** Both runtime budgets stand as decided — deployed `k = 5` with adaptive early
stopping and lower-median reduction, connector `k = 1` then review → value-of-information allocation →
re-score with the prior withheld → disclosure. Never a mean; never a point reduction over a polarised
cell; never a reliability coefficient over in-session assertions labelled as inter-rater agreement.
The `procedure` record and the rendered disclosure are still required on every analysis.

And the honest admission stands unchanged: **the connector's flagship mitigation has unknown magnitude
until the ADR-0008 harness runs.** A strategy seam does not measure anything. It remains the
highest-value open question in the project, and it still costs a few dollars.

Refs #24.

## References
1. [Findings — comparison method and prompting (2026)](../research/findings-method.md) — in this repository, § 4.3
2. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](../research/scoring-order-effects.md) — in this repository, § 8
3. [Mitigating evaluation variance and quantifying the uncertainty that remains (2026)](../research/sections/r4-variance-mitigation.md) — in this repository, § 2.3
4. [Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs — Aggarwal, Madaan, Yang & Mausam (2023), EMNLP](https://arxiv.org/abs/2305.11860)
5. [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs — Loo (2025)](https://arxiv.org/abs/2511.00751)
6. [Escape Sky-high Cost: Early-stopping Self-Consistency for Multi-step Reasoning — Li et al. (2024), ICLR](https://arxiv.org/abs/2401.10480)
7. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
8. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065) — *single-author preprint; weak evidence*
