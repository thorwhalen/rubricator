# ADR-0011: The scoring protocol — pointwise, cell-wise, evidence first

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
Traversal order and scoring protocol change the numbers, measurably and in a known direction. Scoring
several criteria in one generation collapses them toward each other, inflating inter-criterion
correlation from a human r ≈ 0.32 to r ≈ 0.98 [4]; a criterion's position inside a prompt shifts that
criterion's mean by up to 0.80 points on a 5-point scale, with 56 of 60 (judge, criterion) tests
significant [3]. Pairwise comparison is the human reliability gold standard, but forced choice
manufactures a winner where the same judge's own scalar reading contains no significant difference —
preferences flip 13.6% of the time on average while pointwise gaps of 0.19–0.36 on a 10-point scale
are not significant in aggregate [6]. That is the exact opposite of what ADR-0006 is for.

The whole argument, with the numbers and the dissent, is in `docs/research/findings-method.md` § 3,
§ 4.2 and § 7.1 [1], over the owner's scoring-order study [2].

## Decision

**Score pointwise, cell-wise, one criterion per generation**, against a 5-point anchored rubric. The
traversal order is supplied by a **seeded tool permutation** — not chosen by the model — so the run is
replayable and the seed enters provenance. The rubric's level order is randomised per read.

**`extract_evidence` runs before `score_cell`, and `score_cell` receives the span, not the corpus.**
Reference-guided judging beats chain-of-thought on MT-Bench by more than 2× on failure count, 3/20
against 6/20 [5]. Scoring-then-citing is both the worse protocol and the arrangement that produces
post-hoc citation.

**Prompt shape per cell is plan → judge → emit**, with the plan persisted as provenance.

**Repeats reduce by lower median** — for even k, the lower of the two central order statistics, so
the result is always a level some generation actually chose. `reduction="mean"` **raises** at the
tool boundary, naming the level of measurement [7]; a trimmed range is a percentile statistic and is
legal, a trimmed mean is not.

**No point reduction is emitted for a polarised cell.** For a cell split between levels 2 and 4 at
p = .45 each, the lower median lands on 3 — a level almost nobody chose — with probability rising
monotonically from .10 at k = 1 to .36 at k = 21. More repeats make the point estimate monotonically
more misleading; sampling cannot rescue a bimodal cell, it can only reveal that the cell is bimodal.
*(Reasoning from a simulation run for the research, not a published finding.)* What the analysis
carries in that case is the k measures themselves and the level multiset they form. The `polarised`
condition and its companions are **derived from that multiset by `comparanda`** — this repo emits the
inputs and does not write a second, differently spelled flag beside them. `aggregate_assertions` may
return a `contested` marker to its caller; a marker returned by a tool is not a stored measure, and
ADR-0002 leaves the schema to the companion repo.

**Pairwise is not the default and is not built in v1.** It may be escalated for one criterion at a
time, and only when the four conditions of `docs/research/findings-method.md` § 3 are met: the column
is **compressed**, and/or the column is **unstable**; the criterion is **decision-relevant**; and its
evidence coverage is **≥ 70%** — the last a hard veto, not a weighting. Escalation then runs
only within the tied cluster, fitted by **Bradley–Terry MLE with Davidson ties and a bootstrap
interval, never online Elo**, whose ratings are volatile near 50% win rates and depend on comparison
arrival order [8][9][10]. The resulting cell is marked as derived. Davidson's ν is itself reportable:
a high ν says the criterion does not discriminate among these alternatives, which is what ADR-0005
step 6 exists to surface.

**The negative branch is the product.** When a column is compressed and unstable but has no evidence,
the correct output is not a pairwise ranking; it is `missing` with reason
`insufficient_evidence_to_discriminate`, plus a review-stage note naming the evidence that would
resolve it.

**The escalation thresholds are reasoning, not evidence**, and they are the first thing the ADR-0008
evaluation suite tunes.

**Temperature 0 applies to the deployed runtime only.** No scoring tool exposes a model
`temperature` or a sampling `seed`: neither exists in the connector, and a parameter that silently
no-ops in one of two first-class runtimes is a bug in the specification. The one seed this protocol
does carry is the traversal permutation's — seed the traversal, not the model.

## Consequences
More calls than any batched arrangement, and the connector cannot afford the repeat schedule — which
is why ADR-0018 splits variance policy by runtime. In exchange, cross-cell contamination is removed
by construction rather than mitigated after the fact, and every number is attributable to a single
generation against a recorded seed.

`score-column` survives only as a cheaper harness arm awaiting validation. The scale-drift argument
for it is real but is reasoning against direct measurement, and arms 1 and 2 of the evaluation
harness exist to settle it. Until they do, the default follows the measurements — which makes two
documents wrong: the prompts README line calling column-wise "likely better than cell-at-a-time",
and the prompt table in `docs/research/sections/r6-mcp-and-agent-architecture.md` that names
`score-column` the default. Both need correcting, and the unit word in the surrounding prose is
**criterion**, not "column".

Cell-wise scoring also makes ADR-0006 enforceable rather than aspirational: a cell whose span was
never extracted has nothing to score against, so the blank arrives by construction.

## Alternatives considered
- *Column-wise — one criterion, all alternatives.* Holds the scale fixed across alternatives, the
  same reason essays are marked question-by-question. A real argument, and reasoning against direct
  measurement [3][4]. It is harness arm 2, not the default.
- *Single-pass — the whole matrix in one generation.* Cheapest and worst; maximally exposed to both
  the collapse effect [4] and lost-in-the-middle.
- *Pairwise throughout.* Structurally cannot abstain — a Bradley–Terry tie is a modelled outcome, not
  an abstention, and nothing in it distinguishes "genuinely equal" from "evidence genuinely absent".
  It is also the more gameable protocol when irrelevant distractors are embedded in the text [12],
  and it costs 7–20× per criterion at the reliability comparative judgement requires [11].
- *Mean of repeats.* Returns a level no generation could have chosen, on an ordinal scale [7].
- *Letting the model choose the traversal order.* Unreproducible, and it puts the one variable known
  to move scores by 0.80 points under the control of the thing being measured [3].

## References
1. [Findings — comparison method and prompting (2026)](../research/findings-method.md) — in this repository
2. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](../research/scoring-order-effects.md) — in this repository
3. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2) — *cite v2 specifically*
4. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
5. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — Zheng, Chiang, Sheng et al. (2023), NeurIPS](https://arxiv.org/abs/2306.05685)
6. [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation — Yagubyan (2026)](https://arxiv.org/abs/2606.13685)
7. [On the Theory of Scales of Measurement — Stevens (1946), Science 103(2684):677–680](https://doi.org/10.1126/science.103.2684.677) — *paywalled; paraphrased from secondary summaries, not quoted*
8. [Elo Uncovered: Robustness and Best Practices in Language Model Evaluation — Boubdir, Kim, Ermis, Hooker & Fadaee (2023)](https://arxiv.org/abs/2311.17295)
9. [Chatbot Arena leaderboard updates: from online Elo to Bradley–Terry MLE — LMSYS (2023)](https://lmsys.org/blog/2023-12-07-leaderboard/)
10. [On Extending the Bradley-Terry Model to Accommodate Ties in Paired Comparison Experiments — Davidson (1970), JASA 65:317–328](https://doi.org/10.1080/01621459.1970.10481082)
11. [Comparative judgement as a research tool: A meta-analysis of application and reliability — Kinnear, Jones & Davies (2025), Behavior Research Methods 57(8):222](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246014/)
12. [Pairwise or Pointwise? Evaluating Feedback Protocols for Bias in LLM-Based Evaluation — Tripathi, Wadhwa, Durrett et al. (2025)](https://arxiv.org/abs/2504.14716)

---

## Amendments

### 2026-08-21 — the pipeline stages are named, and which are tools

- **Deciders:** Thor Whalen

**What this replaces.** The Decision above writes `extract_evidence` and `score_cell` in
snake_case, which in this repository denotes a tool. Neither is one. Read literally, the ADR
instructs an implementer to build a tool that scores a cell — and scoring is judgement, so such a
tool would have to call a model, which ADR-0003 forbids and which would break the connector
runtime outright. This is the one architectural rule of the project, so the ambiguity is corrected
rather than left to be read charitably.

**The stages, and what each one is:**

| Stage | Kind | Why |
|---|---|---|
| `corpus_search` | **tool** | Lexical retrieval — BM25 plus normalised substring, fixed tokenizer, fixed tie-break (ADR-0010). Reproducible, so it is a tool. |
| `extract-evidence` | **prompt** | Deciding *which* returned span bears on the claim is judgement. The model does it; a tool validates that what came back is a real span in a real document. |
| `score-cell` | **prompt** | The judgement this whole ADR is about. Never a tool. |
| `check_citations` | **tool** | Whether a quote is where it claims to be is string containment. Deterministic, and therefore evidence a reader can re-run. |
| `validate_measure` | **tool** | Shape, level of measurement, and the honesty rule's structural half. |

**Naming convention, stated so it stops being implicit.** `snake_case` names a tool;
`kebab-case` names a prompt served as content. The prompt inventory in `docs/prompts/README.md`
uses kebab-case throughout and is the authority on the prompt set.

**What does not change.** Evidence before score, the seeded traversal permutation, the lower-median
reduction, and the 5-point anchored rubric all stand exactly as decided. The ordering claim —
that reference-guided judging beats scoring-then-citing, and that scoring first produces post-hoc
citation — is about the *stages*, and is unaffected by which of them are tools.

### 2026-08-21 — missingness reason codes are kebab-case

- **Deciders:** Thor Whalen

**What this replaces.** The Decision above spells the negative branch's reason code
`insufficient_evidence_to_discriminate`. The code is **`insufficient-evidence-to-discriminate`**.

Snake_case names a **tool** in the pipeline vocabulary the amendment above fixes; elsewhere it is
this repository's ordinary spelling for field names (`document_id`, `evidence_rule`) and metric
names (`quote_verbatim_rate`), and it is never the spelling of a stored *value*. A reason code is
neither a tool nor a prompt — it is a value that travels inside a `comparanda` document, and the
companion repo's core set is kebab throughout in shipped code (`src/core/schema/missingness.ts`:
`not-applicable`, `not-assessed`, `deferred`, `not-evidenced`, `indeterminate`, `withheld`) and in
`docs/domain-model.md`, which both repositories read as the shared vocabulary. Every other code this
repository has coined is already kebab — `superseded-by-revision`, `merged-into`, `means-objective`,
`not-controllable`, `no-discrimination-expected`, `user-rejected` (ADR-0016). One code in snake_case
would ship a spelling inconsistency into a cross-repo schema request, where it is expensive to
retract.

**The rule, stated once and applying everywhere in this repository:** reason codes, core and
custom, are kebab-case. The schema request registered in ADR-0002's amendment is re-spelled
accordingly. `docs/research/` keeps the original spelling because it is the evidence trail, not the
specification.

**Scope of the unit-word rule.** The Consequences above rule that "the unit word in the surrounding
prose is **criterion**, not 'column'". That governs the *unit* — a criterion is never called "a
column". It does not rename the protocols and statistics that carry "column" in their own names:
`score-column` (the prompt and harness arm 2), column-wise traversal, and the column correlation
that ADR-0008 reports as a `traversal_leakage_diagnostic` all keep their names, because each names a
procedure over the matrix rather than the unit itself.
