# Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs?

**Author: Thor Whalen**

## 1. Bottom line

Yes: for an LLM scoring a criteria × alternatives matrix, the traversal order will systematically change both the cell scores and — in a poorly-conditioned matrix — the induced ranking of alternatives, and the single strongest piece of direct evidence (Stureborg et al., 2024) shows that when GPT-4 scores multiple attributes in one generation, later attributes are pulled toward earlier ones so strongly that the inter-attribute correlation inflates from a human r ≈ 0.32 to r ≈ 0.98 and accuracy on later-positioned attributes degrades. The best-supported default is **cell-wise / one-criterion-per-call scoring** (isolate each judgment, then aggregate in code), which removes cross-cell anchoring by construction and is the explicit recommendation of both the most on-point academic paper and multiple eval-tooling teams. Confidence: **moderate** — the mechanism (autoregressive self-conditioning) and the direction (assimilation) are well-established, but no published study directly compares all four of your specific traversals on a business-use-case matrix and measures ranking stability, so the local experiment in Section 8 is essential.

## 2. Direct LLM evidence

The direct question — "does grouping/ordering of items in an LLM scoring task change scores or rankings?" — is **partially studied but not settled**. There is strong evidence for the component mechanisms and one paper almost exactly on point, but no study that varies column-wise vs row-wise vs cell-wise vs single-pass traversal on a decision matrix and reports Kendall's tau on the resulting alternative ranking.

**The most on-point study: Stureborg, Alikaniotis & Suhara (2024), "Large Language Models are Inconsistent and Biased Evaluators" (arXiv:2405.01724) [1].** Using the SummEval summarization dataset, they had GPT-4 score four attributes (Coherence, Consistency, Fluency, Relevance) in a single generation, in that order. Findings:
- **Anchoring / assimilation is real and large.** Earlier scores pull later scores toward them. The inter-attribute correlation between Consistency and Coherence was **r = 0.979 for GPT-4 vs r = 0.315 for human raters** — i.e., the model collapses distinct dimensions into one when they share a generation context. They write: "LLM evaluators tend to overrely on this adjustment of its priors—experiencing an anchoring effect. This is unsurprising due to LLM's auto-regressive generation."
- **Position within the generation degrades accuracy.** Predicting Coherence first gave Kendall's τ = 0.400 against human experts; predicting it 3rd or 4th dropped it to τ ≈ 0.359–0.368. Their conclusion: "the judgment for the target attribute (i.e., Coherence) was influenced by the previous judgments for the other attributes."
- **Scoring separately vs together changes the scores materially.** Krippendorff's α between the single-attribute template and the multi-attribute template was only ~0.51 on average — below human inter-annotator agreement (~0.66).
- **Their explicit recipe (Table 6): "Predict only one attribute per generation."** Plus: widen to a 1–10 scale, remove chain-of-thought and set temperature 0, keep the source document in context even for attributes that don't require it.
- Caveats: models are GPT-3.5-turbo-0301 / GPT-4-0613 / GPT-4-Turbo; the order-degradation table uses GPT-3.5 while the r = 0.979 figure uses GPT-4; generalization to other model families (Llama, Vicuna, etc.) is explicitly untested. Note also that r-values are Pearson inter-attribute correlations while τ-values are Kendall correlations with human ground truth — don't conflate them.

**Supporting mechanism evidence (strong, but one step removed from your matrix):**
- **Position bias in LLM-as-a-judge is pervasive.** The Lechmazur LLM Position-Bias Benchmark (193 verified story pairs across 36 models) reports a **model-average order-flip rate of 43.0%** and a **model-average first-shown pick rate of 64.3%** (about +14.3 percentage points over chance); the most order-sensitive model, Mistral Medium 3.5, flips 72.5% of the time and picks the first-shown option 82.8% of the time [2]. Stronger models (e.g., Gemini 2.5 Pro) are markedly more robust; several models show consistent recency bias.
- **Multiple-choice option-order sensitivity.** Reordering answer options changes accuracy by 13–75% across benchmarks (Pezeshkpour & Hruschka, 2024) [3]; shuffling MMLU options produced accuracy drops of ~10–43% depending on model [4]. Mechanism: uncertainty about the answer × a positional/token-ID prior toward certain slots (e.g., "A" or first position).
- **"Lost in the middle" (Liu et al., 2024, TACL) [5].** Models use information at the beginning/end of a long context better than the middle (a U-shaped curve). In a single-pass matrix, where an alternative or criterion sits in a long prompt affects how well it is attended to.
- **Self-inconsistency across repeats.** LLM judges have low intra-rater reliability; the same input yields different scores across runs. Rating Roulette (arXiv:2510.27106) reports that on MT-Bench "Llama 3.1 had a Krippendorff's Alpha of 0.265 across its 3 runs" and "Qwen 3 gave the same judgment on all 3 runs for only 61.3% of cases" [6]. Per the "Reliability without Validity" survey (arXiv:2606.19544), "same-verdict rates are above 95% when temperature is set to 0, but fall to as low as 70% when temperature is increased to 1" [7]. temperature = 0 can paradoxically reduce agreement with humans even as it reduces variance.
- **Batching degrades accuracy in a domain-dependent way.** RuVerBench (Peng, Qi et al., 2026; arXiv:2606.29920), across 2,458 instances in deep-research and agentic-coding domains, finds that "batched verification presents a trade-off between accuracy and efficiency, and majority voting yields effective but diminishing returns"; once a call contains 4–5 rubrics, every tested model loses accuracy versus single-rubric calls — small in one domain, double-digit in agentic coding [8].

**Weight this evidence as:** strong for "order and grouping change LLM scores," moderate for "the direction is assimilation toward earlier scores," and weak/absent for "this flips the ranking of alternatives on a business-case matrix specifically."

## 3. Human evidence

The human effect is **robust and long-established**, though the literature is scattered and the mechanisms are debated.

- **Halo effect** (rating all dimensions of one ratee together makes those dimensions correlate more than they should) is one of the oldest findings in performance-appraisal psychology. In the meta-analysis by Viswesvaran, Schmidt & Ones (2005), integrating roughly 90 years of studies, "construct-level correlations among rated dimensions of job performance were substantially inflated by halo for both supervisory (33%) and peer (63%) intrarater correlations" [9]. Rating-criteria order modulates halo: a many-facet Rasch study of L2 writing found the magnitude of the group-level halo effect changed with the order in which criteria were rated [10].
- **Joint vs separate evaluation (Hsee's evaluability hypothesis) [11].** Whether options are evaluated side-by-side (joint) or in isolation (separate) reverses preferences when one attribute is hard to evaluate in isolation. This is a genuine **rank reversal**, not just a level shift — the rank order of options changes depending on evaluation mode. This is the human analogue of your column-wise (joint, comparative) vs cell-wise (separate, isolated) choice.
- **Alternative-based vs attribute-based processing [12].** Process-tracing (eye-tracking, mouse-tracking) shows people spontaneously switch between processing by option (row-wise) and by attribute (column-wise), and this changes choices, especially for cognitively involving compromise/tradeoff choices. Attribute-based processing tends to be used under time/complexity pressure and can change context effects (e.g., the compromise effect).
- **Sequential contrast/assimilation effects.** In sequential evaluation, the current judgment is pulled toward the previous response (assimilation) or pushed away from the previous stimulus (contrast) [13]. Documented in Idol singing, Olympic diving/gymnastics, speed dating, and — most relevant to you — **real hiring/admission interviews**, where recommendations react strongly to the previous candidate's quality, especially when candidates share characteristics and interviews are close in time [14].
- **Essay marking order.** Marker drift and fatigue over a stack of scripts; a strong/weak answer affects the next. Standard pedagogical advice is to grade question-by-question (column-wise) rather than script-by-script (row-wise) to hold the standard fixed per criterion [15].
- **MCDA weight elicitation.** Anchoring, splitting bias, range insensitivity, and equalizing bias all show that how you elicit and order attribute weights changes the weights; Rezaei et al. (2024) found SMART vs Swing produce systematically different weights due to their different anchors [16].

**Effect size / rankings summary:** In humans, order/mode effects are large enough to reverse rankings (Hsee JE/SE reversals; interview contrast effects change individual recommendations). Halo primarily distorts the *covariance structure* (inflates correlations) and level, but combined with tradeoffs this can change which alternative wins.

**Comparative judgement as the human "gold standard" for reliability:** rank-then-rate / pairwise comparative judgement produces highly reliable rank orders. Writing-assessment work finds that "to achieve a satisfactory reliability of 0.7, each text must be compared 10 to 14 times on average" [17]; a 2025 meta-analysis (Behavior Research Methods) now finds as few as 10 comparisons per item can suffice and recommends raising the reliability threshold to SSR ≥ .8 [18]. It works precisely because it sidesteps absolute-scale calibration differences across raters — relevant to your mitigation options.

## 4. Transfer analysis

*This section mixes evidence with reasoning; I mark which is which.*

**Human mechanisms that plausibly transfer to LLM raters:**
- **Halo → cross-attribute assimilation (EVIDENCE).** Directly demonstrated by Stureborg: scoring attributes together inflates inter-attribute correlation to r ≈ 0.98. This is the LLM analogue of halo, and it is *stronger* in GPT-4 than in humans (r ≈ 0.98 vs 0.32).
- **Anchoring (EVIDENCE).** LLMs shift estimates toward earlier/irrelevant numeric values (Lou & Sun, 2024) [19]. Crucially, when GPT-4 generates several attribute scores in sequence, later ratings are disproportionately biased by earlier ones — the same autoregressive dependency.
- **Joint vs separate evaluation reversals (REASONING).** No LLM study directly replicates Hsee JE/SE preference reversals on a decision matrix. But since LLMs show both comparative-framing effects (pairwise ≠ pointwise) and evaluability-type sensitivity, it is plausible the JE/SE reversal transfers. This is inference, not evidence.
- **Sequential contrast/assimilation (MIXED).** Position bias and the Stureborg anchoring result are consistent with assimilation toward recent context; contrast effects (pushing away) are less clearly documented in LLM raters. Reasoning: the dominant LLM effect appears to be assimilation, not contrast.

**LLM-specific mechanisms with no clean human analogue:**
- **Autoregressive self-conditioning (EVIDENCE).** Each generated token conditions on all prior tokens, so any earlier score literally enters the context for later scores. Humans have working-memory carryover, but not this exact mechanism. This is the core reason single-pass and row-wise/column-wise traversals will differ from cell-wise.
- **"Lost in the middle" positional attention (EVIDENCE).** A largely architectural effect (positional encodings, attention decay). No human analogue in this form. Implies that in a single-pass matrix, cells in the middle of a long prompt are attended to less well.
- **Token-level option-ID priors (EVIDENCE).** Models favor "A" or the first slot at the token level regardless of content — a training-artifact bias, not a cognitive one.
- **Sampling stochasticity (EVIDENCE).** Run-to-run variance even at fixed prompt; no human single-session analogue.

**Net transfer judgment:** The human halo/anchoring/JE-SE literature is a strong *prior* that traversal order matters, and the LLM-specific mechanisms (autoregression, lost-in-the-middle) mean order effects would exist *even if no human analogue applied*. Both point the same direction: isolate judgments to remove cross-cell contamination.

## 5. Practitioner signal (weak-to-moderate; labelled as such)

Eval-tooling teams and practitioner blogs are **broadly consistent** on the operational recommendation, though this is weak evidence (marketing-adjacent, rarely with published ablations):
- **Score one criterion per call, aggregate in code.** Galtea's guide states plainly: "A single prompt that scores faithfulness, relevance, fluency, and format compliance in one pass produces correlated, unreliable scores. The model anchors on the first dimension and lets that anchor bleed into the others. Score one criterion at a time, in separate calls, and average or aggregate at the application layer" [20]. This mirrors Stureborg's academic recipe exactly.
- **Autorubric** (academic, 2026) evaluates each criterion in a separate LLM call via `asyncio.gather()`, explicitly to prevent "context from other criteria from influencing the judgment," and shuffles rubric options per instance to reduce position-bias variance [21].
- **Randomize / swap-and-average for position bias** is near-universal advice (MT-Bench lineage; W&B and other tooling guidance). Pairwise judges: evaluate both orders and average [22].
- **Majority voting / self-consistency across repeats** is standard for reducing run-to-run variance, with diminishing returns (RuVerBench [8]; Rating Roulette [6]).
- **Disagreement exists on batching:** many practitioners batch criteria for cost/latency, but the research signal (RuVerBench, Stureborg) says batching criteria degrades quality. So the practitioner instinct "batch to save money" conflicts with the reliability evidence — flag this tension and resolve it in favor of isolation for the scoring step.

## 6. Mitigations (ranked by evidence strength, with implementation cost)

| Mitigation | Evidence | Cost | Notes |
|---|---|---|---|
| **Cell-wise / one-criterion-per-call scoring** | Strong (Stureborg recipe [1]; Autorubric [21]; practitioner consensus [20]) | Medium (≈ n_alt × n_crit calls) | Removes cross-cell anchoring by construction. The recommended default. |
| **Multiple repeats + aggregate (mean/median/majority vote)** | Strong (Rating Roulette [6]; many judge papers) | Medium–High (× k calls) | Directly reduces run-to-run variance; diminishing returns after ~3–5. |
| **Temperature 0** | Strong for variance reduction; mixed for human alignment [7] | Free | Cuts variance but can slightly reduce validity; combine with repeats if you sample. |
| **Randomize traversal order per run / shuffle option order** | Strong (position-bias literature [2][3]) | Free | Turns systematic order bias into averageable noise. |
| **Swap-and-average (for any pairwise step)** | Strong (MT-Bench lineage [22]) | Low (×2) | Only if you use pairwise/comparative steps. |
| **Rank-then-rate / comparative judgement within a criterion** | Moderate (human CJ reliability [17][18]; LLM pairwise > pointwise) | Medium–High | Comparative framing is more reliable than absolute scoring; but batch ranking has its own position bias. |
| **Calibration anchors in the rubric (define what 1 and 5 mean)** | Moderate (rubric-decomposition literature [21]) | Low | Reduces scale drift; does not by itself fix anchoring across cells. |
| **Ensembling across traversals (run column-, row-, cell-wise; compare)** | Reasoning + weak | High | This is essentially your Section 8 experiment; use it to *measure* then pick. |
| **Stronger judge model** | Moderate (position bias lower for Gemini 2.5 Pro etc. [2]) | Varies | Bigger models are more robust to order but not immune. |
| **Batching many criteria per call** | Negative evidence [8] | Cheapest | Saves cost but degrades quality; avoid for the scoring step. |

## 7. Open questions (what nobody has checked)

- No published study compares **column-wise vs row-wise vs cell-wise vs single-pass** on a decision matrix and reports **Kendall's τ / Spearman on the induced ranking of alternatives** (as opposed to per-cell correlation with a gold label).
- Whether LLM **JE/SE preference reversals** occur on multi-criteria alternative rankings (the Hsee analogue) is untested.
- Whether **contrast** (as opposed to assimilation) ever dominates in LLM matrix scoring, and under what prompt conditions.
- How the effect scales with **matrix size** (more alternatives/criteria → longer context → more lost-in-the-middle).
- Interaction between traversal and **reasoning/CoT** in current (2025–2026) reasoning models, which may self-anchor differently.
- Whether cell-wise isolation *hurts* on criteria that are inherently comparative (e.g., "moat relative to the others"), where joint context is informative rather than contaminating.

## 8. Proposed experiment (executable on your own matrix)

**Decision rule up front.** Compute, across repeats and across traversals, the distribution of Kendall's τ between induced rankings of alternatives.
- If **median cross-traversal τ ≥ 0.9** AND **within-traversal τ across repeats ≥ 0.9**: the matrix is robust; pick the cheapest traversal (single-pass) and move on.
- If **0.7 ≤ τ < 0.9**: order matters; adopt cell-wise + repeats and re-test.
- If **median τ < 0.7**: **stop trusting the matrix as a ranking device.** The scores are dominated by traversal/sampling artifacts rather than signal. Fall back to comparative judgement (pairwise) on the top cluster, or redesign criteria for evaluability.

(τ = 0.7 corresponds to fairly frequent adjacent swaps; τ < 0.7 on a short list means the top choice itself is unstable.)

**Conditions to compare (5 arms):**
1. **Cell-wise:** one call per (alternative, criterion) cell, no other cells in context.
2. **Column-wise:** one call per criterion, scoring all alternatives on that criterion.
3. **Row-wise:** one call per alternative, scoring it on all criteria.
4. **Single-pass:** whole matrix in one generation.
5. **Cell-wise + shuffled order** (control for any residual ordering in how you present criteria/alternatives inside a call).

**Hold fixed:** the model and version, the system prompt / rubric text (including 1–5 anchor definitions), temperature, the set of alternatives and criteria, the aggregation/weighting formula applied *after* scoring, and the random-seed policy. Only the traversal (and, for arm 5, the internal shuffle) varies.

**Repeats:** R = 10 independent repeats per arm. Use temperature 0.7 for the variance study (so you can measure run-to-run instability); additionally run R = 3 at temperature 0 to see the floor. For column-wise and row-wise, randomize the within-call order of items on each repeat.

**What to measure:**
- **Per-cell score deltas:** for each cell, mean and SD of the 1–5 score across repeats and across traversals. Report mean absolute deviation between traversals per cell.
- **Ranking stability:** for each (arm, repeat), compute the weighted-sum score per alternative and its ranking. Compute **Kendall's τ (and Spearman ρ)** (a) between repeats within an arm (stability) and (b) between arms (traversal sensitivity). Report the full τ distribution, not just the mean.
- **Top-1 / top-3 churn:** fraction of repeats in which the #1 alternative (and the top-3 set) changes. Often more decision-relevant than τ.
- **Inter-criterion correlation inflation:** compute the correlation between criteria columns within each arm. If single-pass/row-wise show much higher inter-criterion correlation than cell-wise (à la Stureborg's r 0.98 vs 0.32), that is direct evidence of halo/anchoring contamination in your own data.

**Python protocol (concrete, drop-in skeleton):**

```python
import itertools, statistics
from scipy.stats import kendalltau, spearmanr

alternatives = [...]        # list of use-case dicts
criteria      = [...]       # ["market_pain", "technical_fit", ...]
weights       = {...}       # criterion -> weight
R             = 10
TEMPERATURE   = 0.7

def score_cell(alt, crit, temperature) -> int: ...        # 1 isolated call
def score_column(crit, alts, temperature) -> dict: ...    # all alts on one crit
def score_row(alt, crits, temperature) -> dict: ...       # one alt on all crits
def score_single_pass(alts, crits, temperature) -> dict: ...

def matrix_from(strategy, temperature, shuffle=False):
    # returns {alt_id: {crit: score}}
    ...

def ranking(matrix):
    totals = {a: sum(weights[c] * matrix[a][c] for c in criteria) for a in matrix}
    return [a for a, _ in sorted(totals.items(), key=lambda kv: -kv[1])]

def _rankvec(order):                     # ordering -> per-alternative rank int
    return [order.index(a) for a in alternatives_ids]

def _mean_matrix(mats):                  # average cell scores across repeats
    return {a: {c: statistics.mean(m[a][c] for m in mats) for c in criteria}
            for a in mats[0]}

arms = ["cellwise", "columnwise", "rowwise", "singlepass", "cellwise_shuffled"]
runs = {arm: [matrix_from(arm, TEMPERATURE, shuffle=("shuffled" in arm))
              for _ in range(R)] for arm in arms}

# within-arm stability
for arm in arms:
    ranks = [ranking(m) for m in runs[arm]]
    taus = [kendalltau(_rankvec(a), _rankvec(b)).statistic
            for a, b in itertools.combinations(ranks, 2)]
    print(arm, "within-arm median tau:", statistics.median(taus))

# cross-arm sensitivity (use mean-aggregated matrix per arm)
agg = {arm: _mean_matrix(runs[arm]) for arm in arms}
for a, b in itertools.combinations(arms, 2):
    tau = kendalltau(_rankvec(ranking(agg[a])),
                     _rankvec(ranking(agg[b]))).statistic
    print(a, b, "cross-arm tau:", tau)
```

**Cost estimate:** with A alternatives and C criteria, per repeat cell-wise costs A×C calls, column-wise C calls, row-wise A calls, single-pass 1 call. For a 6×6 matrix at R = 10 that is ~360 (cell) + 60 (col) + 60 (row) + 10 (single) + 360 (shuffled) ≈ 850 calls — a few dollars on a frontier model. Cheap enough to run in an afternoon.

**Interpretation guide:** If cell-wise is the most stable across repeats *and* single-pass/row-wise show inflated inter-criterion correlation, you have locally reproduced Stureborg's anchoring finding and should default to cell-wise + repeats. If all arms agree (τ ≥ 0.9), traversal doesn't matter for your matrix and you can use the cheapest.

## 9. Overall evidence grade

- Order/grouping changes LLM scores: **strong.**
- Direction is assimilation toward earlier scores (halo/anchoring): **moderate-to-strong** (one very on-point paper + consistent mechanism literature).
- Order flips the *ranking of alternatives* on a decision matrix specifically: **weak/absent** (must be established locally — hence Section 8).
- Human order effects are robust and can reverse rankings: **strong.**
- Best mitigation (cell-wise isolation + repeats): **moderate-to-strong**, converging across academic and practitioner sources.

## REFERENCES

1. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
2. [LLM Position-Bias Benchmark — Lechmazur (GitHub)](https://github.com/lechmazur/position_bias)
3. [Large Language Models Sensitivity to The Order of Options in Multiple-Choice Questions — Pezeshkpour & Hruschka (2023/2024)](https://arxiv.org/abs/2308.11483)
4. [Changing Answer Order Can Decrease MMLU Accuracy](https://arxiv.org/pdf/2406.19470)
5. [Lost in the Middle: How Language Models Use Long Contexts — Liu et al. (2024), TACL](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)
6. [Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks](https://arxiv.org/abs/2510.27106)
7. [Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models](https://arxiv.org/html/2606.19544v1)
8. [Can LLM-as-a-Judge Reliably Verify Rubrics in Agentic Scenarios? (RuVerBench)](https://arxiv.org/pdf/2606.29920)
9. [Is there a general factor in ratings of job performance? A meta-analytic framework — Viswesvaran, Schmidt & Ones (2005)](https://pubmed.ncbi.nlm.nih.gov/15641893/)
10. [Effects of rating criteria order on the halo effect in L2 writing assessment — a many-facet Rasch measurement analysis](https://link.springer.com/article/10.1186/s40468-020-00115-0)
11. [The Evaluability Hypothesis: An Explanation for Preference Reversals between Joint and Separate Evaluations of Alternatives — Hsee (1996)](https://pages.ucsd.edu/~cmckenzie/Hsee1996OBHDP.pdf)
12. [Attribute-based choice — NSF Public Access Repository](https://par.nsf.gov/biblio/10211592-attribute-based-choice)
13. [Sequential biases on subjective judgments: Evidence from face attractiveness and ringtone agreeableness judgment — PLOS One](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0198723)
14. [Sequential contrast effects in hiring and admission interviews — CEPR](https://cepr.org/voxeu/columns/sequential-contrast-effects-hiring-and-admission-interviews)
15. [The Marking System in Education: Strengths, Weaknesses, and Errors — Teachers Institute](https://teachers.institute/instruction-in-higher-education/marking-system-education-strengths-weaknesses-errors/)
16. [Analyzing anchoring bias in attribute weight elicitation of SMART, Swing, and best-worst method — Rezaei et al. (2024)](https://onlinelibrary.wiley.com/doi/10.1111/itor.13171)
17. [Comparative approaches to the assessment of writing: Reliability and validity of benchmark rating and comparative judgement](https://www.jowr.org/index.php/jowr/article/view/867)
18. [Comparative judgement as a research tool: A meta-analysis of application and reliability](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12246014/)
19. [Anchoring Bias in Large Language Models: An Experimental Study — Lou & Sun (2024)](https://arxiv.org/abs/2412.06593)
20. [LLM as a Judge prompts: templates, rubrics, and best practices — Galtea](https://galtea.ai/blog/llm-as-a-judge-prompts-templates-rubrics-and-best-practices)
21. [Autorubric: A Unified Framework for Rubric-Based LLM Evaluation](https://arxiv.org/html/2603.00077v1)
22. [Exploring LLM-as-a-Judge — Weights & Biases](https://wandb.ai/site/articles/exploring-llm-as-a-judge/)