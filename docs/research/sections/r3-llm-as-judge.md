# LLM-as-judge practice: pointwise vs pairwise, aggregation, structured output

**Research question(s):** What is current (2025–2026) best practice for structured evaluation with an
LLM — rubric-in-prompt, reference-free vs reference-based, pointwise vs pairwise? Is pairwise
comparison more reliable for LLMs the way it is for humans, and what aggregation turns pairwise
judgements into a scale with a confidence interval? When is pairwise worth it, per criterion? When
are self-consistency and ensembling worth the tokens? How do you guarantee schema-valid output
without destroying reasoning quality? How do you know your judge is any good?

**Brief section:** `docs/research/method.md` §3 — LLM-as-judge practice.

**Evidence grade:** **strong** for the bias catalogue, the structured-output question and the
aggregation mathematics (multiple primary papers, replicated, plus vendor specs); **moderate** for
the pointwise-vs-pairwise decision (the literature is genuinely split and the two sides measure
different things); **weak** for the specific escalation thresholds I propose, which are reasoned
from the evidence rather than measured.

---

## Bottom line

**Score pointwise, one cell per generation, against a 5-point anchored rubric — and do not build a
pairwise pipeline for v1.** The pairwise literature's win (better correlation with human labels
[1]) is real but was measured on a task where every alternative *has* a quality and a winner always
exists. `rubricator`'s product is the opposite: a qualified blank when the evidence does not
support a judgement (ADR-0006). Forced-choice pairwise structurally manufactures a distinction —
judges pick a winner 86% of the time (a 13.6% flip rate) while their own scalar scores show gaps of
0.19–0.36 on a 10-point scale that are not statistically significant [2] — and it is 7–20× more
expensive per criterion at the reliability the comparative-judgement literature says you need [3].
Escalate to
pairwise only per-criterion, only when a cheap deterministic trigger fires (defined below), and
only within the criterion's tied cluster. When you do escalate, fit **Bradley–Terry by MLE with an
explicit tie model and bootstrap the fit for the interval — never online Elo**, whose ratings
depend on the order the comparisons happened to arrive in [4,5]. For repeated pointwise samples,
take the **median of K=3 reads with randomised presentation order** and report the spread as a
*stability band that is a different field from ADR-0006 confidence*; K=5 buys about 85% of the
K=10 benefit and K=3 about two-thirds [6]. For structured output: the paper claiming format
restriction degrades reasoning [7] does not survive reading — its headline effect is a field-order
artifact, and constrained decoding done properly *improves* accuracy by 3–4 points [8]. Use
grammar-constrained sampling in both runtimes (`strict: true` tool definitions in the connector
[9], the same JSON Schema through the provider's constrained decoder in the deployed agent), with
the reasoning field declared **before** the value fields, and let the model deliberate in prose or
in its thinking block *before* it calls the tool.

---

## Findings

### 1. Rubric-in-prompt, and the rubric is itself a multiple-choice question

**EVIDENCE.** A 2026 study reframes rubric-based judging as structurally a multiple-choice problem
and finds the expected pathology: judges over-select score options at particular *positions in the
rubric list*, independent of content [6]. Measured against a 20% uniform baseline on a 5-point
rubric, across the paper's four datasets Gemma-3-27B selects the last option 25.1–31.4% of the time
and the first 11.5–20.6% (the gap is widest on the two human-annotated sets: 29.3–31.4% vs
11.5–13.9% on HANNA and SummEval); GPT-OSS-20B leans the other way (23.5–25.3% on the first
option). Direction is a property of the model, not the rubric layout — the same prompt produces
opposite biases across model families [6].

Two consequences matter directly for `rubricator`:

- **Scale granularity is not free.** Repeating the experiment at n ∈ {2, 3, 5, 9} points, bias
  (Cramér's V) is **not monotone**: on 5 of 6 judges the *lowest* bias sits at an intermediate
  scale (n=3 or n=5), and both extremes are worse. Gemma-3-27B roughly doubles from V=0.114 at n=5
  to V=0.220 at n=9 [6]. **This contradicts Stureborg et al.'s recommendation to widen the scale to
  1–10** (reported in the repo's scoring-order document [10]). Given `comparanda` renders an
  ordinal measure and users argue about it, **5 anchored points is the right default** and the
  evidence now points the same way.
- **Criterion order inside a prompt is a second, orthogonal bias axis.** When several criteria are
  scored in one prompt, 56 of 60 (judge, criterion) tests show a significant position effect, with
  the worst cell shifting a criterion's mean score by **0.80 points on a 5-point scale** purely by
  where the criterion sat in the list [6]. This independently corroborates the repo's scoring-order
  finding [10] and its cell-wise recommendation, from a different research group and a different
  method.

**REASONING (not evidence).** The practical reading is that an anchored rubric does not remove bias
— it *relocates* it from "what does a 4 mean" to "which slot is the 4 in". Anchors are still worth
it (they are what makes a score defensible and re-checkable by a human), but they must be
accompanied by presentation randomisation, not treated as a fix on their own.

### 2. Reference-free vs reference-based — and why `rubricator` is already reference-based

**EVIDENCE.** MT-Bench's clearest single result on judge quality is not about pointwise vs pairwise
at all; it is about references. On 10 math questions with position swaps, GPT-4 as judge fails
14/20 with the default prompt, 6/20 with chain-of-thought, and **3/20 when first given a
reference answer to grade against** [11]. Reference-guided judging halves CoT's failure rate again,
and cuts the default prompt's by more than 4×.

**REASONING (not evidence).** `rubricator` gets this for free if the pipeline is ordered correctly.
ADR-0006 already requires an evidence span per cell. If the agent **extracts the span first and
scores against the extracted span**, rather than scoring against the whole corpus and citing
afterwards, the span *is* the reference and the judgement is reference-based rather than
reference-free. Scoring-then-citing is the arrangement that produces post-hoc citation — the most
damaging failure mode in ADR-0006 and ADR-0008 — and it is also the arrangement that gets the worse
number in [11]. This is a sequencing constraint on the tool surface, not a prompt tweak: an
`extract_evidence` step must be able to run and be validated *before* a `score_cell` step, and
`score_cell`'s input should carry the span, not the corpus.

### 3. Pointwise vs pairwise: what the evidence actually shows

The literature is split, and the split is informative because the two camps measure different
things.

**The case for pairwise (EVIDENCE).** PAIRS [1] formulates evaluation as ranking and beats direct
scoring on human correlation almost everywhere. On NewsRoom coherence, Spearman ρ goes from 0.44
(direct scoring) and 0.45 (G-Eval) to 0.56 (PAIRS); on SummEval coherence from 0.32/0.30 to 0.42;
on HANNA complexity from 0.37/0.39 to 0.47 — all with GPT-3.5-turbo. The gain is largest for weaker
models: Llama-2-chat-7B moves from ρ = 0.02 to 0.43 on NewsRoom coherence [1]. Averaging both
permutations of each comparison (swap-and-average) improves it further, e.g. Mistral-7B on SummEval
from 25.6 to 32.9 [1]. (An earlier draft of this section credited [6] with finding rubric-based
*pairwise* prompts more resilient to score-option position bias than pointwise ones. **That claim is
withdrawn — [6] runs no pairwise-vs-pointwise experiment at all**; its title is a rhetorical framing
of rubric judging as a multiple-choice task, and its position-bias results are entirely within the
rubric-based pointwise setting.)

**The case against pairwise (EVIDENCE), and it is the case that binds here.**

- **Pairwise is far more gameable.** When generator models embed distractor features, **pairwise
  preferences flip in ~35% of cases versus ~9% for absolute scores** [12]. Relative judgement
  amplifies the influence of anything superficially differentiating.
- **Forced choice manufactures differences.** Across 29 tasks × 50 trials × 2 judges, pairwise
  preferences flip 13.6% of the time on average, 28% of questions exceed a 20% flip rate, and one
  reaches 56% — while the *same judges'* mean pointwise score gaps are 0.19–0.36 on a 10-point
  scale and not statistically significant in aggregate [2]. The paper names this the
  "pairwise–pointwise gap": the judge names a winner where its own scalar reading contains no
  evidence of a real difference.
- **Pairwise fails exactly where the field is flat.** PAIRS' clearest loss — the paper's own named
  exception — is SummEval consistency, and the authors diagnose it precisely: 86.7% of summaries
  carry a human score of 5, so "These characteristics make it difficult for pairwise comparisons to
  yield meaningful comparisons and consequent rankings." [1].
- **On a strong judge with a real rubric, pairwise buys little.** GPT-4 pairwise and GPT-4
  single-answer grading agree **97%** of the time on non-tied votes, and single-answer grading's
  agreement with human experts is essentially the same as pairwise's 85% [11].

**REASONING (not evidence).** Point 2 is disqualifying for `rubricator` specifically. The repo's
central claim (BRIEF.md; ADR-0006) is that it will emit `missing` with a reason rather than a
confident guess. A protocol whose defining behaviour is "always produce a winner" is the wrong
default instrument for a product whose defining behaviour is "sometimes decline to produce a
score". Pairwise does not have a natural `unknown`; ties in Bradley–Terry are a *modelled outcome*,
not an abstention, and nothing in a tie tells you whether the alternatives are genuinely equal or
the evidence is genuinely absent — which are the two states ADR-0006 exists to keep apart.

**The cost argument is independent and also decisive (EVIDENCE + arithmetic).** The
comparative-judgement literature now has firm numbers. Kinnear, Jones & Davies' meta-analysis of
101 CJ sessions recommends **NCR ≥ 20 comparisons per object for SSR ≥ .8**, and recommends raising
the working threshold from .7 to .8; the neighbouring figures it reports — ~10–14 comparisons per
object for SSR ≥ .7 and 26–37 for SSR ≥ .9 — are prior guidance from Verhavert et al., not this
meta-analysis's own estimates [3]. So a usable pairwise
scale for **one** criterion over A alternatives costs ≈ 20A/2 = 10A comparisons (each comparison
serves two objects), or 20A model calls if you swap-and-average for position bias [1,11]. Pointwise
cell-wise costs A calls, or 3A with K=3 repeats. That is a **7–20× multiplier per criterion**, for
a scale that still has to be mapped back onto the 5-point rubric before `comparanda` can render it.
PAIRS' sorting-based search recovers some of this — it needs about 30% of the comparisons that Elo
aggregation needs for equal correlation, with complexity between O(N log N) and O(N²) [1] — but
sorting-based aggregation gives you an *order*, not a calibrated score, and it presumes transitivity
that LLM judges do not reliably have [1,4].

### 4. The bias catalogue and what each one costs you

| Bias | Best evidence | Magnitude | Mitigation that actually works |
|---|---|---|---|
| **Position (pairwise order)** | MT-Bench [11] | GPT-4 consistent on only **65.0%** of swaps; GPT-3.5 46.2%; Claude-v1 **23.8%** (and favours the *name* "Assistant A") | Swap-and-average, or declare a tie on disagreement [11]. Few-shot lifts GPT-4 to 77.5% but costs 4× tokens and may add new biases [11] |
| **Position (rubric score option)** | Rubric-as-MCQ [6] | Up to 31.4% selection on one option vs 20% uniform; direction is model-specific | Randomise option order across K reads; exact balance buys nothing over random shuffling (paired CI contains 0 in 11/12 cells) [6] |
| **Position (criterion order)** | [6], corroborating [10] | Up to **0.80 points on a 5-point scale** from list position alone; 56/60 tests significant | One criterion per generation (cell-wise) [10]; randomise criterion order if you must batch |
| **Verbosity / length** | MT-Bench "repetitive list" attack [11]; length-controlled AlpacaEval [13] | Attack succeeds on **91.3%** of Claude-v1 and GPT-3.5 judgements, 8.7% for GPT-4 [11]. Regression-based length control raises Spearman with Chatbot Arena from **0.94 to 0.98** [13] | Score against an extracted span of bounded length, not against whatever prose the corpus offers; length-normalise if you ever rank |
| **Self-preference / self-enhancement** | MT-Bench [11]; Panickssery et al. [14] | GPT-4 favours itself with a **10%** higher win rate, Claude-v1 **25%** [11]; self-recognition ability correlates linearly with self-preference strength [14] | Never let the same model both write and judge a justification. Relevant here: the agent must not score its own generated summaries as if they were sources — precisely ADR-0006's authorship rule |
| **Style over substance** | SOS-Bench [15] | LLM-judge preferences **do not correlate** with measured safety, world knowledge or instruction following; judges prioritise style over factuality | Bind every score to a checkable span; meta-evaluate against something other than judge preference (§8) |
| **Sycophancy** | Sharma et al. [16]; SycEval [17] | Humans and preference models prefer convincingly-written sycophantic responses over correct ones a non-negligible fraction of the time [16]; sycophantic behaviour appears in 58.19% of tested *cases* across the three models SycEval evaluates — 43.52% progressive, 14.66% regressive [17] | ADR-0005's confirmation checkpoint is the exposure point: after the user confirms criteria, the agent must not treat confirmation as endorsement of a *direction*. Keep the frame elicitation and the scoring in separate calls so the user's stated preference is not in the scoring context |
| **Anchoring / halo across cells** | Stureborg et al., via [10] | Inter-attribute r inflates from 0.32 (human) to **0.98** (GPT-4) when attributes share a generation | Cell-wise scoring [10]. Already settled by the repo's own research; do not re-litigate |

### 5. If and when you do go pairwise: the aggregation machinery

**Do not use online Elo. EVIDENCE.** Elo is a sequential update rule; its output depends on the
order the comparisons arrived in, which is meaningless when the entities have fixed quality.
Boubdir et al. quantify this: with a single ordering (N_perms = 1), Elo ratings are volatile
whenever win rates are close to 50%, and volatility is *worse* at higher K-factors; stability
requires averaging over **N_perms ≥ 100** random orderings of the same fixed set of outcomes. They
also show transitivity is not preserved: "A beats B and B beats C implies A > C" fails, especially
between similar-strength entities, and whether it fails depends on the K-factor [4]. LMSYS reached
the same conclusion operationally and switched the Chatbot Arena leaderboard from online Elo to
**Bradley–Terry MLE** precisely because "player's performance does not change (i.e., game order
does not matter)" and the full comparison history is available [5].

**The recipe, if you escalate:**

1. **Fit Bradley–Terry by maximum likelihood.** BT is logistic regression on comparison outcomes
   with one parameter per alternative and no intercept; the MLE exists and is unique under a
   connectivity condition on the comparison graph, and MM algorithms give a simple, monotone,
   globally convergent fit [18]. In Python this is a few lines of `scipy.optimize` or a
   `statsmodels` logit on the pair-indicator design matrix — a **deterministic tool**, which keeps
   it on the right side of ADR-0003.
2. **Model ties explicitly, do not discard them.** Discarding ties throws away the information
   `rubricator` most needs (that two alternatives are indistinguishable on this criterion). Three
   options, in increasing fidelity: count a tie as half a win and half a loss (what Chatbot Arena
   does [5]); Rao & Kupper's threshold model [19]; or Davidson's tie model, which adds a single
   tie-propensity parameter and is the standard choice when ties are frequent and informative [20].
   **Recommendation: Davidson.** Its ν parameter is itself a reportable quantity — a high ν on a
   criterion is direct evidence that the criterion does not discriminate among these alternatives,
   which is exactly the kind of finding ADR-0005 step 6 is supposed to surface.
3. **Get the interval two ways and report the wider one.**
   - *Bootstrap* (the Arena method [5]): resample the comparison set with replacement B = 1000
     times, refit BT each time, take the 2.5th/97.5th percentiles of each alternative's parameter.
     Assumption-light, handles the tie model without extra derivation, and is what a reader can
     reproduce.
   - *Asymptotic* (REASONING, standard statistical practice, not a finding): because the BT fit is
     a GLM, standard errors are the square roots of the diagonal of the inverse observed Fisher
     information, and a Wald interval follows. Cheap, and a sanity check on the bootstrap. This is
     textbook GLM inference applied to the paired-comparison likelihood reviewed in [21].
   - Both intervals are on the latent-strength scale. To put a number in a `comparanda` cell you
     must map back to the 5-point rubric — use a **monotone anchor map** fitted from the two or
     three alternatives that also received a confident pointwise score, and record that the cell's
     value is derived. Do not invent a linear rescaling.
4. **Alternatives to BT worth knowing.** *Rank Centrality* [22] treats the comparison graph as a
   Markov chain and takes the stationary distribution as the score; it recovers BTL parameters with
   near-order-optimal sample complexity given a spectral-gap condition on the comparison graph, and
   is a good fallback when the comparison graph is sparse and irregular. *Thurstone–Mosteller*
   [21] is the probit twin of BT and gives materially the same ordering; the comparative-judgement
   tradition in education assessment is built on it, which is where the reliability numbers in [3]
   come from. **Do not use adaptive pair selection** to hit a reliability target: adaptive CJ
   inflates SSR (mean .92 across 19 adaptive sessions vs .85 across 32 non-adaptive sessions, both
   at NCR < 52) [3], so you would be reporting a reliability you did not earn.

**Cost, restated concretely.** For 8 alternatives on one criterion at SSR ≥ .8: ≈ 20 × 8 / 2 = 80
comparisons, ×2 for swap-and-average = **160 model calls for one column**. The same column
pointwise at K=3 with randomised presentation is **24 calls**. This is why pairwise is an
escalation, not a default.

### 6. The escalation rule (the deliverable the brief asked for)

**REASONING (not evidence) — thresholds are reasoned from §3 and §5, and are the first thing an
evaluation run should tune.** Escalate criterion *c* from pointwise to pairwise if and only if, after
the pointwise pass with K=3:

1. **The column is compressed.** ≥ 60% of scored cells in column *c* fall on the same rubric level,
   *and* that level is not an endpoint (an endpoint pile-up usually means the criterion is a filter,
   not a scale). — The flat-field condition that makes pointwise uninformative.
2. **The column is unstable.** The median across-repeat spread in column *c* exceeds 1 rubric level
   on ≥ 30% of cells. — The judge cannot hold the absolute anchor, which is the condition PAIRS was
   designed for [1].
3. **The column is decision-relevant.** Perturbing column *c* by ±1 level changes the top-ranked
   alternative or the top-3 set under the user's weighting. — Do not pay 7–20× for a column that
   does not move the answer.
4. **The column has evidence.** ≥ 70% of cells in column *c* are backed by a cited span. — Pairwise
   on a column that is mostly `missing` produces a beautifully calibrated ranking of guesses. Hard
   veto; this one is not negotiable against the others.

Fire only when **(4) AND (3) AND (1 OR 2)**. And when it fires, run pairwise **only within the tied
cluster** identified by (1), not over the whole column — this cuts the comparison count roughly by
the square of the cluster fraction and is where all the discriminative information is anyway.

Encode the negative case too: if (1) and (2) hold but (4) fails, the correct output is **not a
pairwise ranking — it is `missing` with reason "insufficient evidence to discriminate"**, plus a
note in the review stage (ADR-0005 step 6) saying what evidence would resolve it. That is the
product.

### 7. Self-consistency, ensembling, and the diminishing-returns curve

**EVIDENCE.** The curve is steep then flat, and the flattening point depends on what you are trying
to recover.

- **For a stable point estimate:** aggregating K distinct randomised orderings, roughly
  **two-thirds of the K=1 → K=10 improvement is reached by K=3 and about 85% by K=5** [6]. Also
  from the same study: the gain comes from *aggregating distinct orderings*, i.e. variance
  reduction, not from exact balance — the paired CI for (balanced − random) Pearson r contains 0 on
  11 of 12 (judge, dataset) cells, with differences between −0.008 and +0.015 [6]. And crucially,
  de-biasing only improves human
  correlation for judges that were strongly biased to begin with (5 of 12 cells) [6]. So: shuffle
  randomly, aggregate, do not build a balanced-design generator.
- **For recovering a *verdict* on a contested item:** much more expensive. Recovering the 50-trial
  reference verdict with 95% probability needs **11 repeated trials on average, 15 for
  high-variance questions** [2]. This is the honest number for "is alternative X really better than
  Y here", and another reason not to make that the default question.
- **Across judges rather than across samples:** a Panel of LLM evaluators (PoLL) of smaller models
  from disjoint families outperforms a single large judge across 6 datasets and 3 settings, at
  **over 7× lower cost**, with less intra-model bias [23]. For `rubricator` this is only available
  in the deployed runtime — in the connector there is exactly one model and no key (ADR-0003).
- **Batching criteria to save money loses more than it saves** — negative evidence from RuVerBench
  and Stureborg, already assembled in the repo's scoring-order document [10]; do not re-derive.

**Recommendation.** `K = 1` while exploring; **`K = 3` for a delivered analysis**; `K = 5` for cells
the review stage flags as decision-critical. Aggregate by **median**, not mean — the score is
ordinal, and the median of an odd K lands on a real rubric level so the cell renders in `comparanda`
without a fractional artefact. Report the min–max across repeats as the **stability band**. In the
connector runtime, K > 1 costs the user's session tokens and latency directly, so K must be a
parameter the user sets, defaulting to 1 with an explicit prompt-level recommendation to raise it
before anyone acts on the matrix.

### 8. Structured-output enforcement

#### 8.1 The paper claiming format restriction degrades reasoning does not survive reading

The paper is Tam et al., *Let Me Speak Freely? A Study On The Impact Of Format Restrictions On
Large Language Model Performance.* (EMNLP 2024 Industry Track) [7]. Its abstract reports "a
significant decline in LLMs' reasoning abilities under format restrictions". Three things in the
paper's own body undercut that headline:

1. **The headline effect is a field-order artifact.** On Last Letter Concatenation, "we found that
   **100% of GPT 3.5 Turbo JSON-mode responses placed the 'answer' key before the 'reason' key**,
   resulting in zero-shot direct answering instead of zero-shot chain-of-thought reasoning" [7].
   That is not a cost of structure; it is a cost of putting the answer field first. The authors say
   so: "The order of keys in structured outputs and the decoupling of reasoning from format
   adherence emerge as important factors in maintaining LLM capabilities while providing structured
   responses."
2. **It is not parsing errors either.** On Last Letter with LLaMA-3-8B the JSON parsing error rate
   is 0.148% against a 38.15% performance gap [7].
3. **With real constrained decoding the gap mostly vanishes and sometimes reverses.** Their own
   gpt-4o-mini results with the Structured Output API (context-free-grammar-backed JSON Schema):
   GSM8K 91.71 (schema) vs 94.57 (natural language); Shuffled Objects 81.77 vs 82.85; **Last Letter
   86.07 vs 83.11 — structured wins** [7]. Note also that JSON-mode is worse than JSON-Schema on
   all three, which is the distinction the critique below turns on.

**The rebuttal.** The .txt team's response identifies non-equivalent prompts between conditions
(the structured prompts omit the schema and never mention JSON), an AI-parser confound, and the
core conceptual error: **"JSON-mode" (a fine-tune-level behaviour with no format guarantee) is not
"structured generation" (constrained decoding with a hard guarantee)**. Re-running with matched
prompts on Llama-3-8B-Instruct they get GSM8K 77% → 78%, Last Letter 73% → 77%, Shuffle Object
41% → 44%, structured ahead in every case [24].

**The independent replication.** JSONSchemaBench evaluates six constrained-decoding engines and
includes a downstream-quality study on Llama-3.1-8B-Instruct. Constrained decoding **improves**
accuracy on all three reasoning tasks: Last Letter 50.7% (unconstrained) → 51.2–54.0%; Shuffled
Objects 52.6% → 52.6–55.9%; GSM8K 80.1% → 81.6–83.8% [8]. The same benchmark documents the real
engineering risks, which are not about reasoning: coverage varies enormously (empirical coverage
0.03–0.96 depending on engine and schema family), engines differ in whether they over-constrain
(blocking valid outputs) or under-constrain (silently delegating validation back to the model), and
closed-source providers achieve near-100% compliance by supporting only a conservative subset of
JSON Schema [8].

**Assessment (REASONING).** Format restriction per se does not degrade reasoning. What degrades
reasoning is (a) making the model emit its conclusion before its reasoning, and (b) changing the
prompt when you change the format. Both are avoidable by construction. Keep [7] cited — for its
field-order finding, which is genuinely useful — and do not cite its abstract.

#### 8.2 The pattern: reason in prose, then emit through a constrained schema

The convergent recommendation across [7], [24] and [8] is a two-stage shape, and it maps cleanly
onto `rubricator`'s two runtimes.

**Connector runtime.** The model's judgement arrives as **tool-call arguments**. Anthropic's
`strict: true` on a tool definition guarantees the tool `input` matches the declared `input_schema`
via grammar-constrained sampling, and guarantees the tool `name` is valid [9]. This is exactly the
right enforcement point for ADR-0003: the schema lives in the tool definition (content we ship),
the constraint is applied by the caller's model, and our side stays deterministic. The reasoning
happens *before* the tool call — in prose or in the model's thinking block — so the constrained
region contains only the structured verdict, never the deliberation.

The JSON Schema subset is load-bearing and must be checked against the `comparanda` schema before
Phase 1 freezes the tool surface. Supported: object/array/string/integer/number/boolean/null,
`enum` (scalars only), `const`, `anyOf`, `allOf`, `$ref`/`$defs`, `required`, string `format`
(date-time, date, uri, uuid, …), `default`, and `minItems` **only for the values 0 and 1**. Not
supported: recursive schemas, external `$ref`, numeric constraints (`minimum`/`maximum`/
`multipleOf`), string length constraints, and `additionalProperties` set to anything but `false`
[25]. Practical consequences for `rubricator`'s tool schemas:

- A 1–5 score must be `{"type": "integer", "enum": [1,2,3,4,5]}`, not `minimum`/`maximum`.
- A span offset pair cannot be range-constrained in the schema — validate it in the deterministic
  `validate_*` tool instead, which is where it belongs anyway.
- Nothing recursive: no self-referential criterion trees in a tool schema.
- `additionalProperties: false` everywhere, which is good hygiene and required for strict mode.
- Grammar compilation adds latency on first use of a schema and is cached for 24 h, invalidated by
  a schema-structure change but not by a `name`/`description` change [25]. Keep the tool schemas
  stable across a session; iterate on descriptions freely.

**Deployed runtime.** Same JSON Schema, same reason-then-emit ordering, through whichever
constrained decoder the provider offers. JSONSchemaBench is the right shortlist and the right
warning: pick an engine by *compliance rate* (empirical ÷ declared coverage) rather than by
declared feature list, and treat under-constraining engines as requiring the same post-validation
as an unconstrained one [8].

**Both runtimes, non-negotiable:** every structured result passes through the same deterministic
validator before it becomes part of an analysis. MCP's own contract says the same thing from the
other direction — if a tool declares an `outputSchema`, "Servers **MUST** provide structured results
that conform to this schema" and "Clients **SHOULD** validate structured results against this
schema", and the spec is explicit that `structuredContent` "is server-produced result data and is
unrelated to LLM 'structured outputs' (schema-constrained model generation)" [26]. So the two
schema enforcement points are distinct and both are needed: `inputSchema` + strict mode constrains
what the *model* may say; `outputSchema` + our validator constrains what the *server* may return.

#### 8.3 Reconciling "remove chain-of-thought" with the reasoning-model era

Stureborg et al. recommend removing CoT from judge prompts, alongside temperature 0 and one
attribute per generation (reported in [10]). Taken literally in 2026 that advice is unimplementable
— a reasoning model's thinking is not a prompt option — and taken as written it is now
contradicted.

**EVIDENCE.** A controlled comparison holding architecture fixed and varying only reasoning
augmentation (DeepSeek-V3 vs R1, Qwen2.5-32B vs QwQ-32B, Qwen3 Instruct vs Thinking variants) finds
reasoning models are **better** judges on accuracy — e.g. JudgeBench 60.40 → 79.75 for
Qwen2.5-32B → QwQ-32B, 74.00 → 83.87 for Qwen3-30B Instruct → Thinking — and markedly better at
following evaluation instructions (the paper's RR instruction-adherence metric on Helpsteer2-Trivial:
83.19 → 91.11 for Qwen2.5-32B → QwQ-32B, 87.80 → 95.24 for DeepSeek-V3 → R1) [27]. But the
same models are **more** vulnerable to superficial-quality bias: BiasBench drops from 81.25 to
65.00 (V3 → R1) and 82.50 to 67.50 (Qwen2.5-32B → QwQ-32B) [27].

**The reconciliation.** Stureborg's finding was about *unstructured* CoT sharing a generation with
several attribute scores — the same context that produced the r = 0.98 anchoring collapse [10].
The 2026 evidence says the fix is not to remove reasoning but to **structure it**: the paper's
`PlanJudge` prompts the model to emit an explicit evaluation plan before executing the judgement,
recovering bias robustness by **+10.0 to +32.5 points on BiasBench while preserving or improving
accuracy** [27]. So the surviving, updated recipe is:

> **one criterion per generation** (from [10]) + **plan before judging** (from [27]) +
> **reasoning field before value fields in the emitted schema** (from [7]) + **randomised
> presentation order across K reads** (from [6]).

Note what this means for prompt design under ADR-0003: the "plan" step is a *prompt* the caller's
model runs, and the plan is worth capturing as part of the cell's provenance — it is the most
auditable artefact the judgement produces, and it is what makes a disputed cell arguable rather
than merely re-runnable.

### 9. Meta-evaluation: how do you know the judge is any good?

**EVIDENCE, and this is the section ADR-0008 should absorb.** The largest systematic
meta-evaluation to date — 21 judges from 9 providers across MT-Bench, JudgeBench and RewardBench,
118 runs, ~541,000 individual judgements — names the trap precisely: **reliability without
validity** [28]. Two judges achieved near-perfect test–retest reliability (Qwen 3 8B at 0.992,
Gemini 2.5 Flash at 0.988) while showing severe position bias (0.192 and 0.125 respectively). A
judge can be perfectly reproducible and systematically wrong. Chance-corrected agreement with
humans is only moderate throughout: Cohen's κ from 0.376 to 0.511 across 21 models on MT-Bench, and
exact-match scores of 80–85% correspond to κ ≈ 0.48 — meaning raw agreement rates *substantially
overstate* how much the judge and the human actually concur [28].

The same source proposes a **Minimum Viable Validation Protocol**: (1) chance-corrected metrics
(Cohen's κ) rather than raw exact match; (2) position-swap testing via paired AB+BA evaluation;
(3) test–retest across ≥ 3 independent runs at temperature 0; (4) cross-benchmark validation on ≥ 2
contrasting datasets; (5) a **paradox audit** — verify that high test–retest (> 0.95) is not masking
severe position bias (> 0.10) [28].

The complementary warning is SOS-Bench [15]: judge preferences do not correlate with measured
safety, world knowledge or instruction-following, and judges systematically prioritise style over
factuality. Agreeing with a judge — including agreeing with yourself — is not evidence of being
right about anything.

**REASONING — the direct implication for ADR-0008.** ADR-0008's **Stability** criterion, as
written, is exactly the metric [28] shows is gameable. A degenerate agent that emits `3` for every
cell scores perfectly on stability. Stability must therefore be reported **jointly with a
discrimination check** (does the column have variance? does the score distribution differ from a
constant?) and a **position-swap check**, and the suite should fail a build where stability is high
*and* discrimination is low. The same logic applies to ADR-0008's **Refusal to guess**: a degenerate
agent that emits `missing` everywhere passes it. Both criteria need a paired counter-metric, and
that pairing is the single most valuable amendment this research suggests.

---

## What this means for the schema / the view / the agent

**Scoring protocol (agent).**
- Default: `score_cell(alternative, criterion, evidence_spans) -> measure`. One generation per
  cell. 5-point anchored rubric with per-level descriptors carried on the criterion definition
  (ADR-0005 step 3 already requires definitions; the level descriptors belong in the same object).
- Presentation order of rubric levels randomised per read; criterion order randomised whenever more
  than one criterion is in context. Random shuffle, not balanced design [6].
- `K` repeats, default 1 (exploration) / 3 (delivered) / 5 (decision-critical). Aggregate by
  **median**. This makes `K` and the aggregation rule prompt-and-tool parameters, not constants.
- Reference-based by construction: `extract_evidence` runs before `score_cell`, and `score_cell`'s
  input carries the span, not the corpus [11].
- Prompt shape per cell: plan → judge → emit. The plan step is `PlanJudge`-style [27] and is worth
  persisting as provenance.

**Schema / the `measure` object (coordinate with `comparanda`).**
- `score` — the aggregated ordinal level (integer, `enum [1..5]`, for strict-mode compatibility
  [25]).
- `confidence` — **unchanged from ADR-0006**: evidence quality (high = directly supported by cited
  span; medium = inferred from adjacent evidence; low = plausible reasoning with little support).
- `stability` — **NEW, and it must be a separate field**: `{samples: K, spread: [min, max],
  method: "median-of-K"}`. Collapsing sampling dispersion into `confidence` would destroy exactly
  the distinction ADR-0006 exists to protect. A cell can be perfectly stable and evidentially
  worthless — that is [28]'s finding restated at cell granularity.
- `missing` — unchanged, always with a reason. Add a reason enum value for the §6 negative case:
  `insufficient_evidence_to_discriminate`.
- If a pairwise escalation ever produces a value, mark the cell's derivation explicitly:
  `derivation: {method: "bradley-terry-davidson", comparisons: N, interval: [lo, hi],
  anchor_map: ...}`. A BT-derived score is not the same kind of object as a directly-judged score
  and the view must be able to tell.

**Deterministic tools (all model-free, satisfying ADR-0003).**
- `validate_analysis(analysis)` — JSON Schema validation at the `comparanda` boundary.
- `check_citation(span, claim)` — string containment first; the paraphrase case is a *prompt* plus a
  validating tool, never a tool that calls a model.
- `column_stats(analysis, criterion)` — level histogram, compression fraction, spread across
  repeats, discrimination flag. Powers both the §6 escalation trigger and the ADR-0008
  discrimination counter-metric.
- `fit_bradley_terry(comparisons, *, tie_model="davidson", bootstrap=1000)` — pure numeric, returns
  strengths, tie parameter and percentile intervals [5,18,20]. Only reached via escalation.
- `agreement_stats(runs)` — Cohen's κ, position-swap consistency, test–retest, per [28].

**Structured output (both runtimes).**
- Tool schemas declare the reasoning/justification field **before** the score field [7].
- Connector: `strict: true` on every tool that receives a judgement [9]; schemas restricted to the
  supported subset [25] (scores as `enum`, no `minimum`/`maximum`, no recursion,
  `additionalProperties: false`).
- Deployed: same schema through provider-native constrained decoding; select the engine by
  compliance rate, not declared coverage [8].
- MCP tools declare `outputSchema` and return `structuredContent`; the server validates on the way
  out because the spec requires it [26].

**Evaluation suite (ADR-0008).** Add the [28] protocol: chance-corrected κ against a small
human-labelled fixture set; AB/BA position-swap consistency; ≥ 3 runs at temperature 0; ≥ 2
contrasting fixture corpora; and the paradox audit — **fail the build when stability is high and
discrimination is low**, and when `missing`-rate is high and evidence-availability is also high.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0006 | confirm | The evidence strengthens it. Add nothing, but note that `confidence` (evidence quality) and sampling `stability` must remain separate fields — collapsing them is the likeliest accidental regression. |
| ADR-0008 | amend | **Stability** and **Refusal to guess** as written are both passed by a degenerate agent; [28] shows reliability without validity is the dominant failure mode. Each needs a paired discrimination counter-metric, plus chance-corrected κ, AB/BA swap testing, and the paradox audit. |
| ADR-0005 | confirm | Step 3 (definitions with every criterion) and step 6 (self-critique) are both independently supported: undefined criteria are what makes anchors fail, and §6's negative case is a step-6 output. |
| ADR-0003 | confirm | Grammar-constrained sampling lives in the *caller's* model via the tool `input_schema` [9] and the deterministic validator lives in the tool — the rule "no tool may require a model" survives structured-output enforcement intact. |
| ADR-0009 (new) | new ADR | **The scoring protocol.** Pointwise cell-wise on a 5-point anchored rubric as the default; median-of-K aggregation with randomised presentation; the four-condition pairwise escalation rule of §6 with Bradley–Terry+Davidson and bootstrap intervals; and the explicit rejection of online Elo. This is a real decision with real alternatives and it should not be buried in a research file. |
| ADR-0010 (new) | new ADR | **Structured-output strategy.** Reason-first field ordering, strict tool use in the connector, the JSON Schema subset constraint on the tool surface, and the rule that the deliberation is never inside the constrained region. Worth an ADR because the schema-subset limits [25] constrain the `comparanda` boundary design and a future maintainer will otherwise reintroduce `minimum`/`maximum`. |

---

## Open questions

- **The escalation thresholds in §6 (60% compression, 1-level spread on 30% of cells, 70% evidence
  coverage) are reasoned, not measured.** What would settle them: run the ADR-0008 fixture corpora
  through pointwise-K3 and through the full pairwise pipeline, and measure the rank correlation
  between the two columns as a function of each threshold. The threshold to keep is the one below
  which pairwise stops changing the induced ranking. This is a small extension of the experiment
  already designed in the repo's scoring-order document [10] §8 and should reuse its harness.
- **Whether the "flat column" condition and the "no evidence" condition are separable in practice.**
  They may be the same phenomenon: a column may look compressed *because* every cell rests on the
  same thin secondary summary. If they correlate above ~0.7 on real corpora, condition (1) is
  redundant with condition (4) and the rule simplifies.
- **No published study measures pairwise vs pointwise on a multi-criteria decision matrix and
  reports the effect on the induced ranking of alternatives** — the same gap the repo's
  scoring-order document identifies for traversal order [10]. Every number in §3 comes from
  single-dimension text-quality evaluation.
- **Anchor mapping from a Bradley–Terry latent scale back to 5 rubric levels is unsolved here.** The
  monotone-map-from-confident-cells approach in §5 is a proposal, not a method with a citation. If
  the escalation path is ever built, this deserves its own investigation; the comparative-judgement
  literature anchors scales with pre-scored exemplars [3], which may transfer.
- **Sycophancy in the ADR-0005 confirmation checkpoint is unmeasured.** The checkpoint is where the
  user states preferences, and [16,17] say models bend toward stated preferences. The test —
  identical corpus, two confirmation transcripts expressing opposite priors, measure score
  divergence — is cheap and belongs in ADR-0008. I could not find a study of sycophancy in
  *rubric* judging specifically, only in open-ended response evaluation.
- **The connector runtime cannot ensemble across model families**, so PoLL-style panels [23] are
  available only to the deployed agent. Whether that produces a measurable quality gap between the
  two runtimes — and whether users should be told about it — is unresolved and is a product
  question as much as a technical one.

---

## REFERENCES

1. [Aligning with Human Judgement: The Role of Pairwise Preference in Large Language Model Evaluators — Liu, Zhou, Guo et al. (2024), COLM](https://arxiv.org/abs/2403.16950)
2. [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation — Yagubyan (2026)](https://arxiv.org/abs/2606.13685)
3. [Comparative judgement as a research tool: A meta-analysis of application and reliability — Kinnear, Jones & Davies (2025), Behavior Research Methods 57(8):222](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246014/)
4. [Elo Uncovered: Robustness and Best Practices in Language Model Evaluation — Boubdir, Kim, Ermis, Hooker & Fadaee (2023)](https://arxiv.org/abs/2311.17295)
5. [Chatbot Arena leaderboard updates: from online Elo to Bradley–Terry MLE — LMSYS (2023)](https://lmsys.org/blog/2023-12-07-leaderboard/)
6. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2) — **cite v2 specifically**: v1 evaluates a different model set and contains neither the criterion-order axis nor the scale-granularity (Cramér's V) experiment relied on above.
7. [Let Me Speak Freely? A Study On The Impact Of Format Restrictions On Large Language Model Performance. — Tam, Wu, Tsai, Lin, Lee & Chen (2024), EMNLP Industry Track, pp. 1218–1236](https://aclanthology.org/2024.emnlp-industry.91/)
8. [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models — Geng, Cooper, Moskal et al. (2025)](https://arxiv.org/abs/2501.10868)
9. [Strict tool use — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
10. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Thor Whalen (2026)](../scoring-order-effects.md)
11. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — Zheng, Chiang, Sheng et al. (2023), NeurIPS](https://arxiv.org/abs/2306.05685)
12. [Pairwise or Pointwise? Evaluating Feedback Protocols for Bias in LLM-Based Evaluation — Tripathi, Wadhwa, Durrett et al. (2025)](https://arxiv.org/abs/2504.14716)
13. [Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators — Dubois, Galambosi, Liang & Hashimoto (2024)](https://arxiv.org/abs/2404.04475)
14. [LLM Evaluators Recognize and Favor Their Own Generations — Panickssery, Bowman & Feng (2024)](https://arxiv.org/abs/2404.13076)
15. [Style Outweighs Substance: Failure Modes of LLM Judges in Alignment Benchmarking — Feuer, Goldblum, Datta et al. (2024), ICLR 2025](https://arxiv.org/abs/2409.15268)
16. [Towards Understanding Sycophancy in Language Models — Sharma, Tong, Korbak et al. (2023)](https://arxiv.org/abs/2310.13548)
17. [SycEval: Evaluating LLM Sycophancy — Fanous, Goldberg, Agarwal et al. (2025)](https://arxiv.org/abs/2502.08177)
18. [MM algorithms for generalized Bradley–Terry models — Hunter (2004), The Annals of Statistics 32(1):384–406](https://projecteuclid.org/journals/annals-of-statistics/volume-32/issue-1/MM-algorithms-for-generalized-Bradley-Terry-models/10.1214/aos/1079120141.full)
19. [Ties in Paired-Comparison Experiments: A Generalization of the Bradley-Terry Model — Rao & Kupper (1967), JASA 62:194–204](https://doi.org/10.1080/01621459.1967.10482901)
20. [On Extending the Bradley-Terry Model to Accommodate Ties in Paired Comparison Experiments — Davidson (1970), JASA 65:317–328](https://doi.org/10.1080/01621459.1970.10481082)
21. [Models for Paired Comparison Data: A Review with Emphasis on Dependent Data — Cattelan (2012), Statistical Science 27(3)](https://projecteuclid.org/journals/statistical-science/volume-27/issue-3/Models-for-Paired-Comparison-Data--A-Review-with-Emphasis/10.1214/12-STS396.full)
22. [Rank Centrality: Ranking from Pair-wise Comparisons — Negahban, Oh & Shah (2012)](https://arxiv.org/abs/1209.1688)
23. [Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models — Verga, Hofstatter, Althammer et al. (2024)](https://arxiv.org/abs/2404.18796)
24. [Say What You Mean: A Response to 'Let Me Speak Freely' — .txt Engineering (2024)](https://blog.dottxt.ai/say-what-you-mean.html)
25. [Structured outputs — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
26. [Model Context Protocol specification, Tools (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
27. [Reasoning Model Is Superior LLM-Judge, Yet Suffers from Biases — Huang, Wu, Yang & Arase (2026)](https://arxiv.org/abs/2601.03630)
28. [Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias — Norman, Rivera & Hughes (2026)](https://arxiv.org/abs/2606.19544)
