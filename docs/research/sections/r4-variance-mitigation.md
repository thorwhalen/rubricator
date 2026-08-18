# Mitigating evaluation variance and quantifying the uncertainty that remains

**Research question(s):** Given that traversal order and sampling demonstrably change LLM
evaluations, what should `rubricator` *do* about it — in the deployed-agent runtime, which can spend
model calls, and in the connector runtime, which cannot? Which variance-reduction techniques are
worth their cost? How should the residual uncertainty be turned into something a human can act on,
for an **ordinal** score? Which of those mitigations survive with no API key, no temperature knob,
no seed, and a human waiting? And what tool surface, harness and disclosure text follow?

**Brief section:** `docs/research/method.md` §2 (scoring, calibration and bias) and §3 (LLM-as-judge
practice: self-consistency, ensembling, when they are worth the tokens); the direct predecessor is
the companion document [*"Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria
Evaluations — for Humans, and for LLMs"*](../scoring-order-effects.md), whose §6 mitigation table and §8
experiment this section turns into product decisions.

**Evidence grade:** **moderate.** Strong for the component claims — cross-attribute assimilation in
single-generation scoring [1], position bias [2][12], self-inconsistency across repeats [3][4],
diminishing returns from self-consistency [5][6], overconfidence of verbalised confidence [8], the
level-of-measurement constraint on ordinal reductions [16], and the applicability of conformal
prediction to ordinal judge scores [11][13]. Weak-to-absent for the connector-specific design: no
literature exists on mitigating evaluation variance inside a single chat session with no sampling
budget, so §4 is engineering reasoning on top of evidence, and the two Monte-Carlo results in §2.3
and §2.4 are simulations I ran for this section, not published findings. Marked throughout.

---

## Bottom line

Split the problem in two and never let the halves touch. **Evidential confidence** (ADR-0006: is
there a citable span?) is epistemic, checkable by a deterministic tool, and belongs in the schema as
a stored measure. **Procedural stability** (does the judgement survive re-elicitation?) is a
property of the *procedure*, is derivable only from repeated assertions, and must be reported as
`n = 1, unmeasured` when it has not been measured — never estimated, never inferred from the model's
own say-so, because verbalised self-confidence is systematically overconfident [8] and within-model
agreement correlates only weakly with correctness [10]. That is ADR-0006's own rule applied one
level up: prefer a qualified blank to a confident guess, including about your own uncertainty.

For the **deployed agent**, the policy is: one criterion per generation (never batch criteria), a
tool-supplied seeded permutation of the traversal, `k = 5` repeats with adaptive early stopping, and
reduction by **lower median** (never mean — a 1–5 score is ordinal [16], and the reduction must
return a level a rater could actually have chosen). For the **connector**, where there is no
sampling budget, the four mitigations that survive cost nothing but structure: deterministic
traversal isolation via one tool round-trip per criterion; a tool-supplied seeded permutation, which
converts a *systematic* order confound into a random one even at `k = 1`; targeted re-elicitation of
a handful of cells chosen by a deterministic value-of-information proxy — cells where a one-level
change would flip the non-dominated set; and, when even that is unaffordable, an explicit
disclosure that names what was and was not measured and states that human panels show the same
effects [18][19][20].

Report at the rank level, not only the cell level. The decision-relevant statistic is not per-cell
variance but **dominance survival rate**: over perturbed or repeated matrices, the fraction in which
an alternative remains non-dominated. It requires no weights, which is what makes it compatible with
`comparanda` ADR-0015's refusal to aggregate by default. Kendall's tau-b and top-1 churn are the
weighted counterparts and are secondary. Conformal prediction is genuinely applicable and gives a
per-cell interval from a *single* run [11] — which is exactly the connector's constraint — but it
needs a labelled calibration set, so it is an ADR-0008 fixture deliverable, not a v1 feature.

Two things are cheap and should not be deferred: vendor Kendall's tau-b (21 lines; verified below to
match `scipy` to 2×10⁻¹⁶), and ask `comparanda` for four small assertion fields so that five draws
of one model are never mistaken for five raters.

---

## Findings

### 1. Two uncertainties, and why conflating them would be the product's central failure

ADR-0006 already defines `confidence` precisely and correctly: "**Confidence means evidence quality,
not model certainty.** [...] high means directly supported by cited source, medium means inferred
from adjacent evidence, low means plausible reasoning with little support." That is an **epistemic**
quantity. It answers *how thin is the evidence*.

It does not answer *how repeatable is the judgement*, and those dissociate in all four combinations:

| | stable under re-elicitation | unstable |
|---|---|---|
| **high confidence** (cited span) | solid; act on it | **the diagnostic case**: the source says something, but "what counts as a 4" is not pinned down. The criterion is under-defined. |
| **low confidence** (thin evidence) | honestly thin: the evaluator reliably reports that the corpus does not say | noise. This cell should probably be `unknown` with reason, not a score. |

EVIDENCE that the top-right cell is real and common: Stureborg et al. found Krippendorff's α of only
≈0.51 between a single-attribute template and a multi-attribute template on the same data — below
human inter-annotator agreement (≈0.66) [1]. The evidence did not change between templates; only the
procedure did. REASONING: an unstable-but-well-evidenced cell is the single most *actionable* output
this product can produce, because the fix is not "find more documents" — it is "define the
criterion better", which is exactly where ADR-0005 says the value lives, and exactly what the
companion repository's agreement research independently concludes about low per-criterion agreement.

**Recommendation.** Do not overload `confidence`. Do not add a stored `stability` *measure* either —
by `comparanda`'s own domain model (Correction 1: measures are stored, encodings are derived),
stability is derived from the assertion set, so it is an **encoding over a derived statistic**, and
`comparanda` already ships exactly that under the name `disagreement`. What rubricator must add is
the *metadata that makes that encoding honest when the raters are runs of one model* — see
§"What this means for the schema".

### 2. Variance-reduction techniques, ranked

#### 2.1 The ranked table

This extends §6 of the companion scoring-order document rather than restating it. Cost is expressed
in model calls for a matrix of `A` alternatives × `C` criteria.

| Mitigation | Evidence | Cost (deployed) | Cost (connector) | Verdict |
|---|---|---|---|---|
| **One criterion per generation** (never batch criteria) | Strong [1][4] | `A·C` or `C` calls | free (structure only) | **Default in both runtimes.** Removes cross-criterion assimilation by construction. |
| **Tool-supplied seeded permutation** of traversal | Strong for the bias [2][12] | free | free | **Default in both.** Converts a systematic confound into a random one even at `k = 1`. |
| **`k` repeats + ordinal reduction** | Strong [3][5][6] | `×k` | not affordable | Deployed default `k = 5` adaptive; connector only on flagged cells. |
| **Adaptive early stopping** (stop when a majority is established) | Strong [6][7] | saves 34–84% [7] / up to 7.9× [6] | n/a | **Ship it.** Makes `k = 9` affordable on contested cells by making `k = 3` sufficient on unanimous ones. |
| **Targeted re-elicitation** of high-value cells | Moderate (VOI/active-learning framing; [13] shows a usable difficulty signal) | small, bounded | small, bounded | **The connector's flagship.** See §4.3. |
| **Blind re-scoring** (withhold the prior score) | Moderate [14][15][17] | free | partial | Ship, and *test* whether it works (§4.4). |
| **Fresh-session re-scoring** | Moderate; independence is partial [10] | n/a | 1 session | Ship as the top rung of an explicit independence ladder, not as "independent". |
| **Swap-and-reconcile** on any pairwise step (judge both orders; [2] declares a win only if it holds in both, else a tie — averaging is *not* what [2] proposes) | Strong [2] | `×2` on pairwise only | `×2` | Only if pairwise steps are used at all. |
| **Temperature 0** | Strong for variance, mixed for validity | free | **does not exist** | Deployed only. Never expose a no-op knob in the connector spec. |
| **Permutation ensembling** (several traversal seeds, aggregate) | Reasoning + [2][12] | `×k` | not affordable | Subsumed by repeats: make each repeat use a different seed. Do not budget it separately. |
| **Conformal interval from a single run** | Strong for method [11][13]; assumptions bind | 0 extra at analysis time (calibration is offline) | 0 extra | **Deferred to ADR-0008 fixtures.** The only technique that buys an interval without repeats. |
| **Comparative judgement / Bradley-Terry** within a criterion | Moderate; Elo/BT itself is order- and hyperparameter-sensitive and can violate transitivity [21][13] | `O(A²)` or sampled | prohibitive | **Do not make it the default.** Reserve for criteria whose absolute anchors demonstrably fail. |
| **Batching several criteria per call** | Negative [1][4] | cheapest | cheapest | **Reject for scoring.** Cost-driven instinct loses to the evidence here. |
| Asking the model how consistent it would be | Negative [8][10] | free | free | **Reject.** Unverifiable and overconfident. |

Note on Bradley-Terry, since the deployed runtime *could* afford it: EVIDENCE that it is not a free
upgrade — Boubdir et al. show individual Elo computations are volatile, are sensitive to
hyperparameters, and that reliability and transitivity "are not always satisfied" [21]; Gupta &
Kumar find that although aggregate transitivity-violation rates look low (0.8–4.1%), **33–67% of
documents exhibit at least one violation** [13]. Pairwise framing removes absolute-scale drift and
introduces cycle-shaped incoherence in its place. It is a research arm in the harness, not a
default.

#### 2.2 The legal reduction over an ordinal score is the median — and it must return a real level

EVIDENCE. Stevens's framework makes the constraint explicit: Table 1 of [16] lists, as the
statistics permissible on an ordinal scale, the *median* for location and *percentiles* for
dispersion — the mean and the standard deviation appear only from the interval scale upward.
(Stevens (1946) is paywalled; the bibliographic record is confirmed via Crossref, but the primary
text could not be fetched for this section, so the sentence above is a **secondary-summary
paraphrase**, not a quotation. The widely circulated gloss "the median (the mode is also allowed,
but not the mean) ... percentile or quartile (the standard deviation is not allowed)" is Wikipedia's
wording for Stevens's rule, not Stevens's own, and is not quoted here as if it were.)
`comparanda`'s domain model has already committed to this ("a 1–5 rating scale is
ordinal, not interval. Averaging it is a category error"), and ADR-0015 refuses a default total for
the same reason.

EVIDENCE for the counter-position, stated fairly: Norman argues that parametric statistics are
robust to violations of the ordinal/interval distinction and can be used with Likert data [25].
REASONING for why it does not apply here: Norman's argument is about the validity of *inference*
(are the p-values right?). rubricator's problem is the validity of a *reported value* — a number
printed in a cell that `comparanda` will encode as a colour and a label. A reported 3.4 is not a
level any evaluator chose, has no rubric anchor, and cannot be given a level descriptor. The
objection here is semantic, not statistical, and Norman does not answer it.

**Concrete rules:**

- Reduction is **lower median** — for even `k`, take the lower of the two central order statistics
  rather than their average, so the result is always an observed level. Never `(3+4)/2 = 3.5`.
- Report the **mode** alongside. For `k ≤ 9` on a 5-level scale the mode *is* the majority vote, and
  majority voting is what the self-consistency literature actually studies [5][6][7].
- **Trimmed statistics:** a trimmed *mean* is still a mean and is still illegal. A trimmed *range*
  is a percentile statistic and is legal. So the honest dispersion report is the **interquartile
  level range** `[p25, p75]` plus `n`, never `mean ± sd`.
- Ban `mean` at the tool boundary: `aggregate_assertions(..., reduction="mean")` must raise, naming
  the level of measurement in the error. Silent illegal reductions are how the category error gets
  back in.

#### 2.3 How many repeats buys how much — where the knee is

The literature gives the shape but not the number for a 5-level ordinal cell. EVIDENCE for the
shape: self-consistency gains plateau early and can *decline* — Loo reports 0.4% total gain across
20 samples on one benchmark and 1.6% on another, with performance declining beyond ~15 samples,
concluding that "additional paths introduce noise rather than signal when models already solve
problems reliably" [5]. Related work finds majority voting *reduced* per-problem accuracy on 56.6%
and 65.7% of hard problems for two small models [22]. Adaptive-Consistency cuts the sample budget by
up to 7.9× with <0.1% accuracy drop [6]; ESC cuts samples by 33.8–84.2% at comparable accuracy [7].

SIMULATION (mine, run for this section — reasoning aid, not literature). Model a cell as `k` i.i.d.
draws from a distribution over levels 1–5 and ask how often the lower median recovers the modal
level. **Generative model, stated so the table is reproducible:** the mode sits at the *centre* of
the scale (level 3) with probability `p_mode`, and the remaining mass `(1 − p_mode)` is spread
uniformly over the other four levels. This assumption is load-bearing — with an off-centre mode the
lower median recovers it far less often (for the loose row with the mode at level 4, recovery at
`k = 15` falls from .940 to ≈.76) — so read the table as the *best* case for replication, not the
typical one:

| per-call distribution | k=1 | k=3 | k=5 | k=7 | k=9 | k=11 | k=15 |
|---|---|---|---|---|---|---|---|
| tight (p_mode = .80) | .800 | .948 | .983 | .994 | .998 | 1.000 | 1.000 |
| typical (p_mode = .60) | .602 | .796 | .886 | .933 | .963 | .976 | .992 |
| loose (p_mode = .45) | .451 | .630 | .741 | .803 | .862 | .894 | .940 |

Marginal gain per two extra calls, typical case, read off the row above: `1→3` buys +19 pp, `3→5`
buys +9 pp, `5→7` buys +4.7 pp, `7→9` buys +3.0 pp, and `9→15` buys +2.9 pp *in total* across three
further steps — under +1 pp apiece.

**The knee is at k = 5.** Recommendation: `k = 3` is the floor at which a spread statistic exists at
all; `k = 5` is the deployed default; escalate to `k = 9` only for cells the review step flags. Past
`k = 9` you are buying decimal places on a 5-level scale. This agrees with the direction of [5][6]
[7] and gives a number they do not.

#### 2.4 What repeats cannot fix, and why this is the most important result here

SIMULATION (mine). Take a genuinely contested cell: the evaluator returns level 2 with p = .45,
level 4 with p = .45, level 3 with p = .10. The lower median lands on **3 — a level chosen by only
10% of draws** — with probability:

| k | 1 | 3 | 5 | 7 | 9 | 11 | 15 | 21 |
|---|---|---|---|---|---|---|---|---|
| P(reduction = 3) | .102 | .150 | .185 | .216 | .241 | .268 | .304 | .361 |

**More repeats make the point estimate monotonically more misleading.** This is not a defect of the
median; any central reduction does it. It is the same objection `comparanda` ADR-0011 makes to a
mean of 3.5 over raters who said 2 and 5, arriving from a different direction, and it means the
sampling budget cannot rescue a bimodal cell — it can only reveal that the cell is bimodal.

**Rule that follows:** `aggregate_assertions` must **refuse to emit a point reduction for a
polarised cell** unless explicitly overridden, and must instead emit the level multiset plus a
`contested` marker. `comparanda` already has the receiving end: the `polarised` flag and the rater
dot strip in its agreement research, and ADR-0011 point 4's `disagreement` encoding.

#### 2.5 Randomised traversal: turning systematic bias into averageable noise — and what it buys at k = 1

EVIDENCE that the bias is systematic and positional: option-order reordering changes accuracy by
13–75% across benchmarks [12]; judges show large order-flip rates and a first-shown preference
(Claude-v1 gave consistent verdicts on only 23.8% of swapped pairs and favoured the first answer in
75% of cases; GPT-4, the best of the three judges tested, still only reached 65.0% consistency) [2];
*performance* is U-shaped over the position of the relevant span in a long context [23] — note the
paper measures task accuracy by position, not attention weights; and in a single generation, later
attributes are pulled toward earlier ones [1].

REASONING, and the point most likely to be missed: with `k ≥ 3` repeats under different permutation
seeds, order bias averages toward zero — that is the standard argument. But **at `k = 1` a
permutation still buys something real**, and this matters because `k = 1` is the connector's normal
case. Without shuffling, whichever criterion is listed first *always* receives the un-anchored
judgement and every later criterion is assimilated toward it — a bias perfectly confounded with
criterion identity, i.e. a systematic distortion of the comparison. With a seeded shuffle, the same
total amount of assimilation is still present but is no longer attached to particular criteria. A
random error is honest; a systematic error attached to the thing you are measuring is not. This is
the strongest free mitigation available to the connector.

The seed must come **from the tool**, not from the model — see §4.2.

#### 2.6 Batching versus isolation: settled

The companion document already flagged the tension between the practitioner instinct to batch
criteria for cost and the research signal against it, and resolved it in favour of isolation. I
confirm that resolution and add the boundary condition: **isolate criteria; do not necessarily
isolate alternatives.** EVIDENCE for the first half is direct [1][4]. REASONING for the second: a
criterion is a *scale*, and holding a scale fixed across alternatives is what column-wise scoring is
for — it is the same reason essay marking is done question-by-question rather than
script-by-script. Scoring one criterion across all alternatives in one call re-introduces
within-call position bias (mitigated by the seeded shuffle) but removes scale drift between calls.
Which of column-wise and cell-wise wins on the induced *ranking* is exactly the open question the
harness (§5) exists to settle; until it is settled, default to cell-wise per the companion
document's recommendation and treat column-wise as the cheaper arm to be validated.

### 3. Quantifying the uncertainty that remains — this is the product

#### 3.1 What can honestly be reported for an ordinal score

Not a mean. Not a standard deviation. Not "3.4 ± 0.8". What *can* be reported, in increasing order
of information:

1. **`n` and the reduction used.** Always. `n = 1` is a legitimate and honest report.
2. **Modal level + `n`.** The majority vote and how many votes it had.
3. **Lower median + interquartile level range + `n`.** Percentile statistics are ordinal-legal [16].
4. **The full level multiset.** For `k ≤ 9` this is *five integers or fewer* — it fits in a cell's
   tooltip and in a JSON field, and it is strictly more informative than any summary of it. Ship
   this as the primary payload; everything above is a derived convenience.
5. **A credible/prediction set of levels** — e.g. `{3, 4}` at 90% — from conformal calibration
   (§3.3), available even at `n = 1`.

REASONING: for a 5-level scale with `k ≤ 9`, storing the raw multiset costs nothing and eliminates
the entire class of "which summary did they use?" questions. The companion repository's per-cell
statistic recommendation (n, min, max, span, modes, `polarised`, van der Eijk's A) is the right
derived set and rubricator should emit its inputs rather than duplicating its outputs.

#### 3.2 Rank-level stability, and the weight-free statistic that should lead

Per-cell variance is diagnostic; **rank-level stability is decision-relevant.** The companion
document's §8 already proposes Kendall's τ between induced rankings and top-1/top-3 churn, with a
decision rule (τ ≥ 0.9 robust; 0.7–0.9 adopt isolation and re-test; < 0.7 stop treating the matrix
as a ranking device). Adopt that rule as **configurable defaults**, not literals.

But there is a problem with leading on τ: computing a ranking requires **weights**, and
`comparanda` ADR-0015 refuses a weighted total by default precisely because it is "the least
defensible number on the page". A stability report whose headline number requires the thing the
companion tool refuses to compute is architecturally wrong.

REASONING — the fix, and I think this is the right primary statistic for this project:

> **Dominance survival rate.** Over the `R` repeated (or permuted) matrices, report for each
> alternative the fraction of matrices in which it is **non-dominated** — not worse on every
> criterion than some other alternative. And report **Pareto-set churn**: the fraction of matrices
> in which the non-dominated set differs from the modal one.

This requires no weights, no aggregation, and no value judgements; it is exactly ADR-0015's flagship
"strongest defensible reduction available"; and it answers the question a decision-maker actually
has — *is this option safely out of contention, or did it drop out by a coin flip?* An alternative
with a 0.55 survival rate is a finding. An alternative with 1.00 or 0.00 is settled.

Keep τ and top-1 churn as the **secondary, weighted** report, computed only when the user has
declared weights, and note that ADR-0015's existing sensitivity analysis ("how much must a weight
move before the ranking changes") is the same machinery driven by weight perturbation instead of
score resampling. Ship both drivers behind one report.

#### 3.3 Conformal prediction: applicable, useful, and gated on a calibration set

EVIDENCE that it works on exactly this shape of problem. Sheng et al. apply split conformal
prediction to LLM-judge scores: it "constructs continuous prediction intervals from a single
evaluation run", they "design an ordinal boundary adjustment for discrete rating tasks", they show
that "conformal prediction can provide valid prediction interval with coverage guarantees", and they
"suggest a midpoint-based score within the interval as a low-bias alternative to raw model score and
weighted average" [11]. Gupta & Kumar apply
split conformal to direct 1–5 Likert judging and find that **prediction-set width predicts judge
error**: pooling 1,918 observations, Spearman `rs = +0.576, p < 10⁻¹⁰⁰`; they also find width
reflects *item* difficulty rather than judge-specific noise (different judges assign wide sets to
the same documents, r̄ = 0.32–0.38 across judge pairs), and that the criterion matters far more than
the judge — relevance drew sets of average width ≈3.0 and coherence ≈3.9, while fluency and
consistency drew ≈4.9 out of 5 [13].

**Why this matters more here than anywhere else in this section:** conformal gives a per-cell
interval from a *single* run. That is the connector's exact constraint. It is the only technique in
this document that buys uncertainty quantification without a sampling budget.

**What it requires, and why it is not v1:**

- An **exchangeable calibration set** of (item, judge score, reference score) triples. rubricator
  has no reference scores for real analyses — ADR-0008 says so in its first sentence. The
  calibration set must therefore be built from the ADR-0008 fixtures with known answers.
- Calibration is **per (prompt version, model, criterion type)**. A prompt edit invalidates the
  table. This is a cost, and it is also a feature: it gives ADR-0008 a hard, numeric reason to
  re-run on every prompt change.
- The coverage guarantee is **marginal and conditional on exchangeability**. Public-domain fixtures
  are not exchangeable with an arbitrary user corpus. So the interval is *valid* on the fixture
  distribution and a *heuristic* elsewhere, and the UI must say so at the point of use — which is
  exactly the discipline ADR-0015 already demands of every analysis.

**Recommendation:** build it, phase it after the fixture suite exists, and in the meantime use the
*width-predicts-error* finding [13] in the cheap form it permits — as a **ranking** signal for the
re-scoring budget allocator, where no coverage guarantee is needed because nothing is being claimed,
only prioritised.

REJECT, for now: semantic entropy [24]. It is the right idea for free-text generation — cluster
samples by bidirectional entailment and take the entropy over meaning-clusters — but a 1–5 ordinal
score needs no semantic clustering; the levels *are* the clusters. Its natural application here is
to the **justification text**, not the score, and that is a later question.

#### 3.4 Verbalised confidence versus sampled consistency: neither, which vindicates ADR-0006

EVIDENCE, and it is genuinely mixed:

- Xiong et al. (ICLR 2024) benchmark verbalised, consistency-based and hybrid confidence across five
  dataset types and five models, and find that "LLMs, when verbalizing their confidence, tend to be
  overconfident, potentially imitating human patterns of expressing confidence"; that consistency
  among multiple responses and better aggregation mitigate this; and — importantly — that "none of
  these techniques consistently outperform others, and all investigated methods struggle in
  challenging tasks, such as those requiring professional knowledge". They also note the gap to
  white-box methods is narrow, 0.522 → 0.605 AUROC [8].
- Tian et al. (EMNLP 2023) find that for RLHF-tuned models "verbalized confidences emitted as output
  tokens are typically better-calibrated than the model's conditional probabilities ... often
  reducing the expected calibration error by a relative 50%" [9]. Note the comparison is verbalised
  vs *logits*, not verbalised vs sampled consistency — do not read it as a win for verbalised over
  sampling.
- Ding (2026) — single-author preprint, so **weak evidence**, but directly on the question — audits
  self-consistency as a confidence signal and finds the Spearman correlation between agreement and
  majority-correctness "is positive in every cell, but weak", ρ ≈ 0.20–0.59; that the
  highest-agreement model had the *lowest* ρ and no accuracy advantage, being wrong 48% of the time
  even at agreement ≥ 0.8; and that "confident errors are partly shared across providers" [10].

REASONING, and this is the section's cleanest conclusion: **both are weak proxies for correctness,
and ADR-0006 already refuses to use either.** By defining confidence as *evidence quality* rather
than model certainty, ADR-0006 picked the one signal on the list that a deterministic tool can
verify — does the cited span exist, and does it contain what the justification claims (ADR-0008,
citation faithfulness). That looked like a conservative definitional choice; the literature makes it
the correct one. **Confirm ADR-0006 emphatically**, and add the corollary it did not state: sampled
consistency is admissible evidence about the *procedure* and is inadmissible as evidence about
*correctness*. Never let a stability number colour a cell as if it were confidence.

### 4. Connector-mode mitigations with no API budget

No literature exists on this exact problem. Everything in §4 is REASONING grounded in the evidence
above, and each item is stated so that ADR-0008 can falsify it.

#### 4.1 Deterministic traversal isolation as the default — ACCEPT, with an honest limit

One criterion per tool round-trip: the model calls a tool, gets back exactly one work item, returns
exactly one judgement, and the tool hands back the next item. This implements Stureborg's explicit
recipe ("predict only one attribute per generation") [1] at zero marginal cost to the session — it
buys structure, not calls.

**The limit that must be stated and not glossed.** In the connector the entire analysis is one
conversation. Earlier judgements remain in the transcript, so isolation here is *attenuation*, not
elimination — unlike the deployed runtime, where a separate API call genuinely has a fresh context.
Two things reduce the residue and neither removes it:

1. The tool **swallows** each judgement into server-side state and returns only an acknowledgement
   plus the next work item. Prior scores are never re-surfaced in a tool result, so they are not
   re-attended as *salient, recently-emitted* content.
2. The `score-cell` prompt instructs derivation from the cited evidence rather than from the
   surrounding matrix.

Call it what it is in the docs: `in-session isolation`, one rung below `fresh-call isolation`. How
much of cell-wise isolation actually survives a shared transcript is measurable, and §5 adds the
arms to measure it. This is the single most valuable unknown this project can resolve for itself.

#### 4.2 Tool-supplied seeded permutation — ACCEPT

The tool takes a seed and returns a permutation. The model does not choose the order; it receives
it. The tool is a pure function of `(seed, items)`, so it is deterministic per ADR-0003, replayable,
and auditable — the seed goes in the analysis provenance and the run can be reproduced exactly.

This is the clean answer to "there is no temperature and no seed in the connector": you cannot seed
the *model*, but you can seed the *protocol*, and the protocol is where the order bias lives. See
§2.5 for why this pays even at `k = 1`.

Do **not** ask the model to shuffle. A model asked to pick a random order will produce a
distribution with its own priors and will not be reproducible, which defeats both purposes.

#### 4.3 Targeted re-elicitation with a deterministic value-of-information proxy — ACCEPT; this is the flagship

The question the brief poses — *is there literature on where to spend a limited re-scoring budget?* —
has a yes-with-caveats answer. EVIDENCE for the general principle: Adaptive-Consistency "dynamically
adjusts the number of samples per question using a lightweight stopping criterion", reducing budget
up to 7.9× for <0.1% accuracy loss [6]; ESC reduces samples 33.8–84.2% at comparable accuracy by
stopping early when a window of samples agrees [7]; Loo's recommendation is to reserve multi-path
sampling "for problems that demonstrably exceed a model's single-pass reliability" [5]. That is the
active-learning "sample where uncertain" heuristic in judge form. Gupta & Kumar supply a
per-instance difficulty signal that is *not* self-reported [13].

None of that literature is about a **decision matrix**, and that is where rubricator can do better
than uncertainty sampling. Uncertainty sampling spends the budget where the model is unsure.
Value-of-information says to spend it where being wrong would **change the decision**. For a
comparison matrix, that is computable deterministically, with no model call:

> **A cell is *pivotal* if perturbing it by ±1 level changes the non-dominated set** (or, when
> weights have been declared, changes the top-1 or the top-3 set).

That is a small, exact, deterministic computation over the matrix — precisely the kind of thing
ADR-0003 says belongs in a tool. It requires no ground truth, no calibration, and no inference.

Priority for the budget allocator, lexicographic by default and configurable:

1. **pivotal** — ±1 flips the non-dominated set;
2. **thin evidence** — `confidence = low`, or `missing` with reason `unknown` on a pivotal row;
3. **observed instability** — `polarised`, or span ≥ 2, where repeats exist;
4. **wide conformal set** — where a calibration table exists [13];
5. **criterion-level instability** — cells in a criterion whose test-retest agreement is low, since
   that criterion is probably under-defined (§1) and re-scoring it will not help until it is
   redefined. Flag these for *redefinition*, not re-scoring.

Note (5) is a *negative* recommendation and it matters: re-scoring cells in an under-defined
criterion spends budget on a problem re-scoring cannot solve. Route those to ADR-0005 step 3
instead.

This plugs directly into ADR-0005 step 6 ("Review — which scores rest on thin evidence, ... which
cells would most change the picture if wrong"). ADR-0005 already asked for exactly this; §4.3 is its
deterministic implementation. **Confirm ADR-0005.**

#### 4.4 Blind re-scoring — ACCEPT, rename it, and test it

The anchoring literature predicts the second judgement will be pulled toward the first if the first
is shown: LLMs shift estimates toward earlier numeric values [17]; models asked to revise their own
answers without external feedback often *degrade* — "LLMs struggle to self-correct their responses
without external feedback, and at times, their performance even degrades after self-correction"
[14]; and models move toward whatever the interlocutor appears to favour, a behaviour documented
across five state-of-the-art assistants [15]. All three point the same way: **withhold the prior
score on a re-scoring pass.**

Two corrections to the framing:

- **"Blind" overstates it in-session.** The prior score is still in the transcript. The tool's
  contract is `withhold_prior=True`: it does not restate the score, and the re-scoring prompt asks
  for derivation from evidence. True blinding needs a fresh session (§4.5). Name the parameter
  honestly.
- **Whether it works is measurable and should not be assumed.** ADR-0008 test: re-score `N` cells
  twice, once with the prior shown and once withheld, and measure the shift toward the prior
  (mean absolute deviation from the first score, and the fraction of re-scores that exactly repeat
  the first). If withholding does not reduce the repeat rate, the mitigation is theatre and should
  be dropped. I expect it to reduce it and I would not bet the design on it.

#### 4.5 Independent-session re-scoring — ACCEPT the mechanism, REJECT the word "independent"

A fresh session removes transcript anchoring, order carry-over and any accumulated framing. It does
not remove shared model weights, a shared prompt, or shared training data. EVIDENCE that this is not
a pedantic distinction: Ding finds confident errors are "partly shared across providers", so even
*cross-model* agreement is not clean corroboration [10]; and Xiong finds all elicitation methods
degrade together on hard, knowledge-intensive tasks [8].

So do not label two fresh-session runs "two raters" and do not compute an inter-rater reliability
coefficient over them. **Ship an explicit, ordered independence ladder** and carry it on every
assertion:

```
in-session  <  fresh-session  <  distinct-model  <  distinct-human
```

Each rung removes a class of shared cause; none removes them all except the last. A statistic
computed over rung-1 assertions is **test–retest reliability**, not inter-rater reliability, and the
report must say so. Getting this label wrong would be exactly the manufactured rigour ADR-0006 exists
to prevent — an agreement number that looks like consensus and is actually one voice repeating
itself.

#### 4.6 Honest disclosure as the fallback — ACCEPT; here is the text

When nothing else is affordable, disclosure is the mitigation. It must (a) say what was and was not
done, (b) say what to do about it, and (c) make clear that human panels show the same effects, so
that it does not read as "LLMs are uniquely bad" — a framing that is both false and, because it
invites the reader to dismiss it, useless.

**Draft — single-pass, no replication.** This is content (a prompt/resource file), not a hardcoded
string; the bracketed values are filled by the disclosure tool from what actually happened.

> **How this comparison was produced, and what that means for reading it.**
>
> Each cell was scored **once**. Criteria were scored one at a time rather than together, and the
> order was set by a seeded shuffle (seed `{seed}`) so that no criterion systematically benefited
> from being judged first. Nothing was re-scored, so **this analysis carries no measurement of its
> own stability.**
>
> That matters, because scoring is a measurement and this one has not been repeated. Published work
> on model evaluators finds that scoring several criteria in one pass pulls the later ones toward
> the earlier ones — inflating the correlation between distinct criteria far above what human
> raters show [1] — and that repeat runs of the same evaluator disagree with themselves at rates
> well above zero [3][4].
>
> **Human panels show the same effects, and have been measured doing so for the better part of a
> century.** Rating one candidate on all dimensions at once inflates the correlation between those
> dimensions — the halo effect — by roughly a third in supervisor ratings and considerably more in
> peer ratings [18]. Which of two options people prefer can *reverse* depending on whether they see
> the options side by side or one at a time [19]. Interviewers' recommendations move measurably with
> the quality of the previous candidate they saw [20]. This is not a claim that a machine evaluator
> is uniquely unreliable. It is a claim that any single pass of any evaluator is a single
> measurement.
>
> **How to read it anyway.** Treat a one-level difference on a single criterion as not meaningful.
> Read the shape of a row — where the highs and lows fall — rather than any total. Cells marked
> `unknown` mean the sources did not say, not that the answer is middling.
>
> **What would change this notice.** Re-run with replication (`repeats ≥ 3`) to replace it with a
> measured stability report, or re-score just the `{n_flagged}` cells listed under *weakest* — those
> are the ones where a second opinion would most change the picture.

**Draft — with replication, short form:**

> Each cell was scored `{k}` times, one criterion per pass, under `{k}` different seeded traversal
> orders (`{independence}` independence — see the note on what that does and does not rule out).
> Cells show the median level, the observed level range and `n`; **no cell shows an average**,
> because a 1–5 rating is an ordinal scale on which an average is not a defined operation [16].
> `{n_contested}` cells were left without a single score because the repeats split rather than
> converged; for those, the individual levels are shown. Human panels are subject to the same order
> and halo effects [18][19][20].

#### 4.7 Rejected for the connector

- **A `temperature` or `seed` parameter on any scoring tool.** They do not exist in the connector.
  A parameter that silently no-ops in one of two first-class runtimes is a bug in the specification.
  Seed the *traversal*, not the model (§4.2).
- **Whole-matrix in-session repeats treated as independent draws.** They share a transcript; label
  them rung 1 and do not compute a reliability coefficient over them (§4.5).
- **Asking the model to self-report how stable its score would be.** Verbalised meta-confidence is
  overconfident [8] and, unlike an evidence citation, unverifiable [ADR-0006].
- **Bradley-Terry over all pairs in the connector.** `O(A²)` round-trips, plus Elo/BT's own
  volatility and transitivity violations [21][13].

### 5. The measurement harness — what rubricator should ship

The companion document's §8 is a good experiment; it should become an ADR-0008 deliverable rather
than a one-off, and it needs two arms it does not currently have.

**All model access goes through `aix`** (the local facade over litellm) or through an agent object.
No provider SDK, ever. `aix` supplies `chat`, `prompt_func` (with `output_schema` for structured
output), `ChatSession` (whose `.history` is a public list), `configure` for persistent defaults and
`using` as a scoped context manager. The relevant real signatures:

```python
aix.chat(prompt, *, model=None, temperature=None, max_tokens=None,
         stream=False, api_key=None, **kwargs) -> str
aix.prompt_func(template, *, output_schema=None, egress=None, model=None,
                temperature=None, name=None, **chat_kwargs) -> Callable
aix.using(**overrides)            # e.g. using(chat_model=..., chat_temperature=0.0)
aix.configure(**overrides)        # persistent equivalent
aix.ChatSession(system_prompt=None, *, model=None, **chat_kwargs)  # .send(msg), .history
```

**Arms.** Keep the companion document's five (cell-wise, column-wise, row-wise, single-pass,
cell-wise + shuffle) and add two that exist only because rubricator has two runtimes:

6. **`in_session_isolated`** — every cell goes through one growing `ChatSession`, but each turn
   returns only an acknowledgement and the next work item, never a prior score. This is the
   connector's actual protocol.
7. **`in_session_visible`** — the same session, but prior scores are restated each turn. The control.

Arms 6 vs 1 measure *how much of cell-wise isolation survives a shared transcript* — the open
question created by §4.1. Arms 6 vs 7 measure whether withholding works — the §4.4 test. Neither
question has an answer in the literature and both are cheap to settle.

**Sketch** (real `aix` API; prompts loaded from `docs/prompts/`, not inlined):

```python
"""Traversal and replication experiment for the rubricator evaluation suite."""

import random
from itertools import combinations
from statistics import median_low

import aix
from aix import prompt_func, ChatSession

from rubricator.prompts import load_prompt          # prompts are content (ADR-0003)
from rubricator.stats import kendall_tau_b, non_dominated, pareto_churn

CELL_SCHEMA = {"score": int, "confidence": str, "justification": str}


def cell_scorer(*, model, temperature):
    """One isolated call per (alternative, criterion) — the cell-wise arm."""
    return prompt_func(
        load_prompt("score-cell"),
        output_schema=CELL_SCHEMA,
        model=model,
        temperature=temperature,
        name="score_cell",
    )


def run_cellwise(alts, crits, ctx, *, model, temperature, seed):
    score = cell_scorer(model=model, temperature=temperature)
    plan = seeded_plan(alts, crits, seed=seed)          # deterministic, see §6
    out = {a: {} for a in alts}
    for alt, crit in plan:
        out[alt][crit] = score(alternative=alt, criterion=crit, context=ctx)["score"]
    return out


def run_in_session(alts, crits, ctx, *, model, temperature, seed, show_prior):
    """Connector-shaped arm: one transcript, one criterion per turn."""
    session = ChatSession(load_prompt("score-cell.system"), model=model,
                          temperature=temperature)
    plan = seeded_plan(alts, crits, seed=seed)
    out = {a: {} for a in alts}
    for alt, crit in plan:
        turn = load_prompt("score-cell.turn").format(
            alternative=alt, criterion=crit, context=ctx
        )
        parsed = parse_cell(session.send(turn))
        out[alt][crit] = parsed["score"]
        if not show_prior:                              # the tool swallows the score
            session.history[-1] = {"role": "assistant", "content": "recorded"}
    return out


ARMS = {
    "cellwise":            lambda **kw: run_cellwise(**kw),
    "in_session_isolated": lambda **kw: run_in_session(show_prior=False, **kw),
    "in_session_visible":  lambda **kw: run_in_session(show_prior=True, **kw),
    # columnwise / rowwise / singlepass as in the companion document's §8
}

R = 10

with aix.using(chat_model=MODEL, chat_temperature=0.7):
    runs = {
        arm: [fn(alts=ALTS, crits=CRITS, ctx=CTX, model=None,
                 temperature=None, seed=1000 + r) for r in range(R)]
        for arm, fn in ARMS.items()
    }

# --- weight-free primary report (see §3.2) -------------------------------
for arm, mats in runs.items():
    fronts = [frozenset(non_dominated(m, CRITS, POLARITY)) for m in mats]
    survival = {a: sum(a in f for f in fronts) / R for a in ALTS}
    print(arm, "dominance survival:", survival,
          "| pareto churn:", pareto_churn(fronts))

# --- weighted secondary report, only if weights were declared ------------
if WEIGHTS:
    for arm, mats in runs.items():
        ranks = [rank_vector(m, WEIGHTS) for m in mats]
        taus = [kendall_tau_b(a, b) for a, b in combinations(ranks, 2)]
        print(arm, "within-arm median tau-b:", median_low(sorted(taus)))
```

**Cost.** Unchanged from the companion document's estimate (~850 calls for a 6×6 at `R = 10` across
five arms; the two new in-session arms add ~720 more but at a fraction of the token cost per call
after the first, since the context is shared and cacheable). A few dollars.

**On `scipy`.** Do not depend on it. EVIDENCE — I implemented Kendall's tau-b in 21 lines of pure
Python and compared it against `scipy.stats.kendalltau` on 300 random ordinal vectors of length
3–12 drawn from `{1..5}` (i.e. exactly this project's data shape, ties everywhere): **maximum
absolute difference 2.2 × 10⁻¹⁶**, machine epsilon. The tie-corrected formula is the whole
implementation:

```python
def kendall_tau_b(x, y):
    """Kendall's tau-b with tie correction. O(n^2); fine for n <= a few hundred."""
    n = len(x)
    if n < 2:
        return float("nan")
    conc = disc = tx = ty = 0
    for i, j in combinations(range(n), 2):
        dx = (x[i] > x[j]) - (x[i] < x[j])
        dy = (y[i] > y[j]) - (y[i] < y[j])
        if dx == 0 and dy == 0:
            tx += 1; ty += 1
        elif dx == 0:
            tx += 1
        elif dy == 0:
            ty += 1
        elif dx * dy > 0:
            conc += 1
        else:
            disc += 1
    n0 = n * (n - 1) / 2
    denom = ((n0 - tx) * (n0 - ty)) ** 0.5
    return (conc - disc) / denom if denom else float("nan")
```

Ranking-stability tools ship **inside the MCP server**, which must install fast and light in a
Claude Desktop or Claude Code environment; dragging in `numpy` + `scipy` for one coefficient is a
bad trade. **Recommendation: vendor it in `rubricator.stats`, and make `scipy` a `[test]` extra used
only to cross-check the vendored implementation in CI.** That cross-check is a three-line test and
it is the reason the vendoring is safe. Same rule for the jackknife interval and for any
ordinal-agreement coefficient rubricator ends up needing — and note that `comparanda`'s agreement
research has already specified Krippendorff's α (ordinal metric, missing-data handling) and van der
Eijk's A with a golden fixture; **reuse its specification rather than re-deriving, and do not
duplicate its implementation into the schema boundary.**

---

## What this means for the schema / the view / the agent

### A. The comparanda schema request — this crosses into the companion repository

**Stated explicitly, per ADR-0002: the following is a request to `comparanda`, not a change
rubricator can make.** It is small, and all of it is metadata on the existing multi-rater assertion
of `comparanda` ADR-0011 point 3. rubricator does **not** need a new measure.

| Field | Where | Why |
|---|---|---|
| `authorKind: 'human' \| 'agent-run' \| 'script'` | assertion | Five draws of one model must never render as five raters. Without this the `disagreement` encoding tells a lie. |
| `independence: 'in-session' \| 'fresh-session' \| 'distinct-model' \| 'distinct-human'` | assertion | Determines whether a statistic over the assertion set is *test–retest* or *inter-rater*. §4.5. The single most important field in this table. |
| `perturbation: { traversal: 'cell'\|'column'\|'row'\|'single-pass', seed: int, promptVersion: str }` | assertion | Says *what varied* between assertions. Makes a run reproducible and makes the spread interpretable. |
| `procedure` | analysis | The run's policy: traversal, `k`, seeds, prompt versions, model id, whether re-scoring was blind. Provenance for the *procedure*; today provenance exists only per value. |
| `'mode'` added to the reduction enum | analysis / view | ADR-0011 lists `single`, `latest`, `median`, `consensus`. For `k ≤ 9` on a 5-level scale the mode *is* the majority vote and is ordinal-legal [16]. |
| `rounds` (already proposed in the companion agreement research) | analysis | **Confirm it.** A replication pass maps onto a round exactly; it is the natural home for `k`. |

Two things rubricator explicitly does **not** ask for: a stored `stability` measure (derived, not
stored — `comparanda`'s own Correction 1), and any change to `missing`. The existing reason codes
are sufficient; `unknown` is what a fully-contested cell degrades to when the analysis declines to
guess.

### B. Tool surface — all deterministic, no tool calls a model (ADR-0003)

```python
plan_traversal(
    alternatives: list[AltId], criteria: list[CritId], *,
    strategy: Literal['cell', 'column', 'row', 'single-pass'] = 'cell',
    seed: int,                       # supplied by the caller or minted by the server
    repeat_index: int = 0,           # different seed-derived order per repeat
    only: list[CritId] | None = None,
) -> TraversalPlan                   # {plan_id, seed, strategy, items: [WorkItem], n_items}
```
Pure function of its arguments. The model never chooses the order (§4.2).

```python
record_assertion(
    plan_id: str, item_id: str, *,
    score: int | None, confidence: Literal['high','medium','low'] | None,
    missing_reason: MissingReason | None,
    justification: str, evidence: list[SpanRef],
    independence: IndependenceRung = 'in-session',
) -> AssertionAck                    # {accepted, next_item, progress, n_remaining}
```
Returns **only** an acknowledgement and the next work item. Never echoes a prior score — this is the
isolation mechanism of §4.1, and it is why the tool must own the state rather than the transcript.

```python
aggregate_assertions(
    analysis: Analysis, *,
    reduction: Literal['median','mode','latest','single','consensus'] = 'median',
    allow_contested_reduction: bool = False,
    polarised_gap: int = 1,          # config, not a literal (§2.4)
) -> ReducedMatrix                   # per cell: {reduction, n, levels, min, max, span,
                                     #            modes, polarised, contested}
```
`reduction='mean'` **raises**, naming the level of measurement [16]. A `polarised` cell yields no
point value unless `allow_contested_reduction=True` (§2.4).

```python
stability_report(
    analysis: Analysis, *,
    weights: dict[CritId, float] | None = None,
    tau_bands: tuple[float, float] = (0.7, 0.9),   # config default, from the companion §8 rule
) -> StabilityReport
# weight-free (primary):  dominance_survival: {AltId: float}, pareto_churn: float,
#                         per_cell: {n, span, modes, polarised, agreement_a}
# weighted (secondary):   tau_b_distribution, top1_churn, top3_churn, band
# per criterion:          test_retest_alpha (labelled by the lowest independence rung present)
```

```python
allocate_rescoring_budget(
    analysis: Analysis, *, budget: int,
    weights: dict[CritId, float] | None = None,
    priority: list[str] = ['pivotal', 'thin-evidence', 'unstable', 'wide-interval'],
    perturbation: int = 1,           # ±1 level
) -> list[BudgetItem]                # {item_id, reason, rank, would_change: [...]}
```
`pivotal` is computed by perturbing each cell ±1 and testing whether the non-dominated set changes —
a deterministic matrix computation, no inference (§4.3). Criteria whose test–retest agreement is low
are routed to a `redefine` bucket rather than a `rescore` bucket.

```python
disclose_variance(analysis: Analysis) -> Disclosure   # {level, text, filled: {...}}
```
Renders the §4.6 content file against what the `procedure` record says actually happened. The text is
content, not code (ADR-0003), so a reviewer can edit the wording without a release.

```python
conformal_interval(                                   # DEFERRED — after ADR-0008 fixtures
    analysis: Analysis, *, calibration_id: str, alpha: float = 0.1,
) -> dict[CellId, LevelSet]
```
Reads a stored calibration table produced by an offline evaluation run, so the tool itself never
calls a model — ADR-0003 holds. Emits the exchangeability caveat with every result (§3.3).

Supporting pure functions in `rubricator.stats`, vendored, no `scipy`: `kendall_tau_b`,
`non_dominated`, `pareto_churn`, `median_low`, `van_der_eijk_a` (per the companion repository's
specification, validated against its golden fixture).

### C. Runtime policies

**Deployed agent (default):** `strategy='cell'`, seeded permutation per repeat, `k=5` with adaptive
early stop (halt at `k=3` if all three draws share a level or two adjacent levels; escalate to `k=9`
only for cells flagged by `allocate_rescoring_budget`), `reduction='median'`, `temperature` from
config, full `stability_report`.

**Connector (default):** `strategy='cell'`, seeded permutation, `k=1`, then `review` (ADR-0005 step
6) → `allocate_rescoring_budget(budget=min(8, ceil(0.1 * n_cells)))` → re-score those with
`withhold_prior=True` → `disclose_variance`. Offer a fresh-session pass for the top three pivotal
cells as an explicit, optional upgrade with its independence rung recorded.

**Both:** never a mean; never a reduction over a polarised cell; never a reliability coefficient over
rung-1 assertions labelled as inter-rater agreement.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0003 | confirm | Every mitigation here is a deterministic tool plus a prompt; the seeded permutation, the VOI allocator and even the conformal interval (which reads a stored calibration table) require no model call. |
| ADR-0005 | confirm | Step 6's "which cells would most change the picture if wrong" is exactly the budget allocator; §4.3 supplies its deterministic implementation. The step 4 checkpoint is also where the disclosure belongs. |
| ADR-0006 | confirm | Confidence-as-evidence-quality is vindicated: verbalised self-confidence is overconfident [8] and sampled consistency correlates only weakly with correctness [10]; evidence quality is the one signal a tool can verify. |
| ADR-0008 | confirm | Its "Stability — same input twice" bullet stands; §5 specifies it, adds the two connector-shaped arms, and gives conformal calibration a home in the fixture suite. |
| ADR-0009 (new) | new ADR | "Two uncertainties, and ordinal reductions only": evidential confidence vs procedural stability; stability is derived, never estimated, and reported `n=1, unmeasured` when unmeasured; median/mode only, never mean; no point reduction over a polarised cell. |
| ADR-0010 (new) | new ADR | "Variance-mitigation policy per runtime": the two default policies above, the independence ladder, and the requirement that every analysis carry a `procedure` record and a rendered disclosure. |
| — | schema request to `comparanda` | Four assertion fields (`authorKind`, `independence`, `perturbation`), one analysis field (`procedure`), `'mode'` in the reduction enum, and confirmation of `rounds`. Per ADR-0002 this is a coordinated change in the other repository, not one rubricator can make. |

---

## Open questions

- **How much of cell-wise isolation survives a shared transcript?** The connector cannot make a
  genuinely fresh call, so the value of §4.1 is unknown in magnitude. Settled by harness arms 1 vs 6
  (§5). This is the highest-value unknown in the project and it is cheap to run.
- **Does withholding the prior score actually reduce anchoring in-session?** Predicted by [14][15]
  [17], untested here. Settled by arms 6 vs 7.
- **Does traversal order flip the *non-dominated set* on a real matrix?** The companion document's
  §7 notes nobody has published τ on induced rankings; the weight-free version (Pareto-set churn) is
  even less studied. Settled by the harness on public fixtures.
- **Is there an ordinal-appropriate conformal score for a 1–5 rating that beats the boundary
  adjustment of [11]?** Both available papers [11][13] treat the ordinal case with adjustments to a
  continuous method rather than natively. Not settled; not blocking.
- **How many fixtures does conformal calibration need for usable interval widths at 5 levels?**
  Neither paper reports a minimum calibration size for a 5-level ordinal. This determines whether
  §3.3 is a phase-4 feature or a phase-6 one; a pilot on 100 fixture cells would answer it.
- **Does adaptive early stopping distort the ordinal distribution?** [6] and [7] validate stopping
  rules against accuracy on tasks with a single correct answer. Stopping early on agreement
  systematically under-samples the tail of a cell's level distribution, which is precisely the part
  that matters for the `polarised` flag. Needs its own arm before the deployed default is fixed.

---

## REFERENCES

1. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
2. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — Zheng et al. (2023), NeurIPS Datasets & Benchmarks](https://arxiv.org/abs/2306.05685)
3. [Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks (2025)](https://arxiv.org/abs/2510.27106)
4. [Can LLM-as-a-Judge Reliably Verify Rubrics in Agentic Scenarios? (RuVerBench) (2026)](https://arxiv.org/pdf/2606.29920)
5. [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs — Loo (2025)](https://arxiv.org/abs/2511.00751)
6. [Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs — Aggarwal, Madaan, Yang & Mausam (2023), EMNLP](https://arxiv.org/abs/2305.11860)
7. [Escape Sky-high Cost: Early-stopping Self-Consistency for Multi-step Reasoning — Li et al. (2024), ICLR](https://arxiv.org/abs/2401.10480)
8. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
9. [Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback — Tian et al. (2023), EMNLP](https://arxiv.org/abs/2305.14975)
10. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065)
11. [Analyzing Uncertainty of LLM-as-a-Judge: Interval Evaluations with Conformal Prediction — Sheng, Liu, He, Zhao & Kang (2025), EMNLP](https://aclanthology.org/2025.emnlp-main.569/)
12. [Large Language Models Sensitivity to The Order of Options in Multiple-Choice Questions — Pezeshkpour & Hruschka (2023/2024)](https://arxiv.org/abs/2308.11483)
13. [Diagnosing LLM Judge Reliability: Conformal Prediction Sets and Transitivity Violations — Gupta & Kumar (2026)](https://arxiv.org/abs/2604.15302)
14. [Large Language Models Cannot Self-Correct Reasoning Yet — Huang et al. (2024), ICLR](https://arxiv.org/abs/2310.01798)
15. [Towards Understanding Sycophancy in Language Models — Sharma et al. (2023)](https://arxiv.org/abs/2310.13548)
16. [On the Theory of Scales of Measurement — Stevens (1946), Science 103(2684):677–680](https://doi.org/10.1126/science.103.2684.677)
17. [Anchoring Bias in Large Language Models: An Experimental Study — Lou & Sun (2024)](https://arxiv.org/abs/2412.06593)
18. [Is there a general factor in ratings of job performance? A meta-analytic framework — Viswesvaran, Schmidt & Ones (2005)](https://pubmed.ncbi.nlm.nih.gov/15641893/)
19. [The Evaluability Hypothesis: An Explanation for Preference Reversals between Joint and Separate Evaluations of Alternatives — Hsee (1996)](https://pages.ucsd.edu/~cmckenzie/Hsee1996OBHDP.pdf)
20. [Sequential contrast effects in hiring and admission interviews — Radbruch & Schiprowski, CEPR/VoxEU column (2024), summarising their own study of >35,000 interviews](https://cepr.org/voxeu/columns/sequential-contrast-effects-hiring-and-admission-interviews)
21. [Elo Uncovered: Robustness and Best Practices in Language Model Evaluation — Boubdir, Kim, Ermis, Hooker & Fadaee (2023), GEM @ EMNLP](https://arxiv.org/abs/2311.17295)
22. [When Self-Consistency Backfires: Majority Vote Hurts the Majority of Hard Science Problems for Small LLMs (2026)](https://arxiv.org/abs/2608.11403)
23. [Lost in the Middle: How Language Models Use Long Contexts — Liu et al. (2024), TACL](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)
24. [Detecting hallucinations in large language models using semantic entropy — Farquhar, Kossen, Kuhn & Gal (2024), Nature](https://ora.ox.ac.uk/objects/uuid:0653d09e-9368-4eb1-98bb-50d9dda7d3e5)
25. [Likert scales, levels of measurement and the "laws" of statistics — Norman (2010), Advances in Health Sciences Education 15(5)](https://doi.org/10.1007/s10459-010-9222-y)

**Verification note.** All 25 references have been fetched and their bibliographic details confirmed
(references 16, 19, 20, 23 and 25 sit behind paywalls or bot protection and were confirmed via
Crossref, PubMed E-utilities, an author-hosted copy, or the Wayback CDX index rather than the live
publisher page). Every direct quotation in this section has been checked character-for-character
against the source full text, with two exceptions that are marked in place: reference [16] (Stevens
1946), whose full text is paywalled and which is therefore **paraphrased, not quoted** (§2.2); and
reference [11], where the quoted fragments are inflected to fit the carrying sentence. The
load-bearing numeric claims taken from sources — [1] α = 0.513 single- vs multi-attribute against
0.659 human, [5] 0.4%/1.6%, [6] 7.9×, [7] 33.8–84.2%, [8] 0.522 → 0.605 AUROC, [10] ρ 0.20–0.59 and
48% wrong at agreement ≥ 0.8, [12] 13–75%, [13] N = 1,918 / rs = +0.576 / 0.8–4.1% / 33–67%, [18]
33% supervisory and 63% peer halo inflation, [21], [22] 56.6%/65.7% — were each read off the source
text rather than a summary. The two simulations (§2.3, §2.4) and the `scipy` cross-check (§5) were
re-run independently: §2.4 matches an exact multinomial computation to within ±0.003, and
`kendall_tau_b` reproduces `scipy.stats.kendalltau` to a maximum absolute difference of 2.220 × 10⁻¹⁶
across 50 × 300 random ordinal vectors.

**Sources consulted in the companion repositories** (not Vancouver-numbered because they are internal
documents, but load-bearing here): the scoring-order research document in this repository
([`docs/research/scoring-order-effects.md`](../scoring-order-effects.md)), and the agreement research section in the `comparanda` repository's
`docs/research/sections/`, which specifies Krippendorff's α with an ordinal metric and a golden
fixture, van der Eijk's A, the per-cell shape statistics, the rater dot strip encoding, and the
`rounds` schema proposal that §"What this means for the schema" asks to confirm.
