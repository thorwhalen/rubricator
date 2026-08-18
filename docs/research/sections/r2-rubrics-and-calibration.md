# Rubric design, anchored scales, and making confidence mean something

**Research question(s):** What makes a 1–5 scale produce consistent scores across raters and
sessions (analytic vs holistic rubrics, BARS, described levels vs bare numbers)? Should criteria
definitions carry per-level descriptors, and what does that cost? What scale granularity should the
stored `score` measure use, given that the LLM-judge literature pushes *wider* and the human
rating-scale literature pushes *narrower*? What exactly should `confidence` mean, is there
established prior art for an evidence-quality scale, should evidence quality and model certainty be
two measures, and which calibration metrics belongs in the ADR-0008 evaluation suite?

**Brief section:** `docs/research/method.md` §2 — "Scoring, calibration and bias", excluding the
column-wise vs row-wise question, which is settled in
[the scoring-order document in `docs/research/`](../scoring-order-effects.md)
[1] and is built on rather than repeated here.

**Evidence grade:** **moderate.** The scale-granularity question has two directly relevant primary
studies read in full — Stureborg et al. [2] and Li et al. [3] — and they disagree, so the
recommendation is a reasoned reconciliation rather than a finding. The per-level-descriptor
question has one strong review [4] and one well-designed recent experiment [5] that between them
support "helps, modestly, and is not sufficient". The prior art for evidence-quality scales
(GRADE, GRADE-CERQual, IPCC, ICD 203, the Admiralty code) is strong and directly on point. The
calibration-metric recommendations are strong on the statistics and weak on the specific thresholds,
which are my own choices. Four cited pages could not be fetched — the IPCC uncertainty guidance note
and ICD 203 (both primary), the Jonsson & Svingby abstract (paywalled, and elided by the publisher
from every aggregator tried), and the CDC GRADE handbook page — and are described from verified
secondary sources or flagged as unverified, inline and in REFERENCES.

---

## Bottom line

Keep the stored `score` at **1–5 ordinal** and buy discrimination with repeats rather than with a
wider scale: the one study that measured *absolute agreement* between human and LLM raters across
six benchmarks found 0–5 beats both 0–10 and 0–100 [3], and Stureborg's own table shows that
averaging ten samples of a 1–5 scale recovers roughly two thirds of the gap to 1–10 without changing
what the reader sees [2]. **Per-level descriptors are required, but only at levels 1, 3 and 5** — the
evidence for anchoring is real but modest (in a 274-essay study, mean inter-rater ICC rose from 0.459
with holistic descriptors to 0.569 with analytic ones, but the reported ranges overlap: 0.425–0.490
against 0.439–0.646 [5]), and a five-descriptor elicitation cost per criterion is not worth the
marginal two levels. Write anchors as **evidence conditions** ("a source
states X") rather than evaluative adjectives ("excellent"), which is the transferable half of the
BARS retranslation idea. **Keep `confidence` at three levels and keep it meaning evidence quality**
— ADR-0006 is right, it has excellent prior art (GRADE-CERQual, ICD 203, the Admiralty code all
separate source quality from the judgement itself), and comparanda's value-suppressing palette is
already built for 5 score levels × 3 confidence levels. But ADR-0006 is **under-specified in the one
place that matters**: it does not say what stops `low` from becoming the place a guess goes to hide.
Add the decision rule *no citable span → `unknown`, never a low-confidence score*, and add
**`certainty` as a second, optional, probability-valued measure**, because you cannot compute a
Brier score on an evidence-quality label and ADR-0008's calibration item silently assumes you can.
Ship two metric families: a **discrimination** suite over `confidence` (accuracy-by-level with
Wilson intervals, a monotone-trend test, confidence-inflation rate, `unknown`-preference rate) and a
**proper-scoring** suite over `certainty` (Brier with Murphy's three-component decomposition, Brier
skill score against the fixture base rate, an equal-mass reliability diagram, ECE reported second
and never without its bin count, AUROC). Restrict `certainty` to a fixed set of allowed
probabilities, which makes the binning problem disappear by construction.

---

## Findings

### 1. What actually makes a rubric produce consistent scores

**Analytic beats holistic, but the margin is smaller than the folklore.** The standard citation is
Jonsson & Svingby's review of 75 rubric studies, which concludes that reliable scoring of
performance assessments "can be enhanced by the use of rubrics, especially if they are analytic,
topic-specific, and complemented with exemplars and/or rater training" — while also reporting that
many of the assessments they reviewed fell *below* the threshold for acceptable reliability [4].
(UNVERIFIED — could not locate source text. The bibliographic record is confirmed via Crossref and
OpenAlex, *Educational Research Review* 2(2):130–144, but ScienceDirect returns HTTP 403 and the
publisher elides the abstract from OpenAlex, Crossref, Semantic Scholar and Europe PMC, so neither
the quotation nor the "below acceptable" clause could be checked against the source.) If that second
clause holds it is the important one and it is usually dropped in citation: rubrics raise reliability
without necessarily raising it to an acceptable level.

A 2026 within-subjects experiment puts numbers on the components. Across 274 final-year bioscience
essays, each independently marked by two of seven assessors, a three-way linear mixed model found
scoring approach (holistic vs analytic) **not** significant (p = 0.541), while **assessor
experience** (p = 0.006) and **scale descriptor type** (p = 0.010) both were. Inter-rater ICC was
0.425–0.490 with a holistic scale descriptor and 0.439–0.646 with an analytic one; accuracy against
the true grade was r = 0.85–0.93 for experienced assessors and r = 0.63–0.66 for inexperienced ones
[5]. (EVIDENCE.) Read those ICC ranges carefully, because they overlap. The analytic descriptor's
gain sits almost entirely in the experienced-vs-experienced pairings (0.489 → 0.646); the
experienced-vs-inexperienced pairings gain little or nothing (0.432 → 0.439 under holistic marking,
0.425 → 0.550 under analytic marking). Averaged over the four reported pairings the gain is +0.11
ICC; stated as a range it is barely a gain at all, and every reported interval is wide. The authors' own summary is that "simply providing analytical scale descriptors is
insufficient to reduce the variation in scores and accuracy between inexperienced and experienced
scorers."

The relevant translation for rubricator (REASONING, not evidence): the model is a fixed "assessor"
of fixed experience, so the one lever the study says matters most is unavailable to us; the lever we
*do* have — descriptor type — is worth about +0.11 ICC *averaged across rater pairings*, with wide
and overlapping intervals. That is a real but fragile gain on a metric where 0.43 is "poor" and 0.55
is "moderate", so take it, but do not expect anchors to carry the analysis.
The heavier lever available to rubricator is not descriptor prose at all: it is the *evidence
requirement* (ADR-0006), which converts a judgement call into a lookup, and the *criteria
elicitation* checkpoint (ADR-0005), which is the analogue of the rater-training and topic-specificity
factors Jonsson & Svingby identify.

**BARS: the evidence is more equivocal than the HR literature claims.** Behaviourally anchored
rating scales (Smith & Kendall, 1963) anchor each scale point with a concrete narrative example of
behaviour at that level, developed through a "retranslation of expectations" procedure in which a
second group of judges must re-sort the anchors back onto the dimensions they came from [6].
(EVIDENCE for the method.) Two cautions matter here:

- Even sympathetic reviews note that "BARS may still suffer from unreliability, leniency bias and
  lack of discriminant validity between performance dimensions" [6], and that the strength of the
  format may lie primarily in the *dimensions* the retranslation process produces rather than in the
  distinction between behavioural and numerical anchors. (EVIDENCE, from a review; I could not
  retrieve the primary meta-analytic comparison and do not assert a specific effect size.)
- New data reported in 2025 by Wiesen, on 22 police promotional exercises each graded by two
  independent three-rater BARS panels, found within-panel reliability averaging **0.91** but
  between-panel correlation averaging only **0.60** — a 34% shrinkage — despite all panellists
  receiving the same thorough training. The conclusion is that "individual rater panels develop their
  own idiosyncratic grading criteria" [7]. (EVIDENCE.)

The direct lesson (REASONING): anchors reduce *within-session* drift much more than they reduce
*between-session* drift. That is exactly rubricator's failure mode — the same criterion scored in
two different analyses, or in two runs of the same analysis. Anchors alone will not fix it; the fix
is to **version the anchors with the criterion and reuse the exact text**, so that two sessions are
literally the same panel. This is cheap and it is the single highest-value implication of the BARS
literature for this project.

**Anchored levels beat bare numbers in LLM judging specifically.** Prometheus is built on rubrics in
which every score from 1 to 5 carries its own written description; the published example descriptors
are graded prose ("Score 1: the model neglects to identify or react to…", …, "Score 5: the model
excels in…"), and the 13B model reaches 0.897 Pearson correlation with human evaluators using those
rubrics, against 0.882 for GPT-4 and 0.392 for ChatGPT [8][9]. (EVIDENCE that anchored rubrics
support high human correlation; NOT evidence of an ablation isolating the anchors — no such ablation
is reported, and I checked.) Autorubric is more direct about the mechanism: it "deliberately
excludes continuous (real-valued) criteria" because "LLM judges exhibit poor calibration when asked
to produce unbounded numeric scores". Its ordinal type is defined only as criteria that "use ordered
levels, typically expressed as Likert scales", and it separately urges practitioners "to use narrower
scales (e.g., 1-5) as opposed to broad scales (e.g., 1-10 or 1-100) and to provide a clear
description of the scale in the rubric" [10]. (EVIDENCE for the design choice, and for the narrow
scale independently of §3; the paper backs the decomposition claim by citation rather than new data,
which it says so itself.) Stureborg's winning recipe likewise
includes the criterion *definition* pasted verbatim into the prompt, alongside the evaluation steps
a human annotator would follow [2].

### 2. Verdict on per-level descriptors

**Required — at levels 1, 3 and 5. Levels 2 and 4 are defined structurally as "between", and get no
prose.** (REASONING over the evidence above.)

The reasoning, laid out so an implementer can disagree with a specific step:

1. Descriptors demonstrably help by roughly +0.1 ICC [5], and every LLM-judge system with strong
   human correlation that I could inspect uses them [8][10]. So some descriptors are non-optional.
2. The marginal return on descriptors 2 and 4 is the smallest — they are the levels a rater reaches
   by *interpolation* anyway, and the human literature's warning is that raters cluster at the
   midpoint and at the ends regardless (central tendency and extreme response styles, §5). Writing
   prose for them mostly produces near-duplicate text, which is worse than no text because it invites
   the model to distinguish on wording rather than on evidence.
3. Three descriptors per criterion is an elicitation cost of about three sentences, drafted by the
   `propose-criteria` prompt and *confirmed by the user at the ADR-0005 step-4 checkpoint*. Five is
   the point where the checkpoint stops being read.
4. **Write anchors as evidence conditions, not evaluative adjectives.** "5 — at least one source
   states a figure above the threshold and no source contradicts it" is checkable; "5 — excellent"
   is not. This is the transferable core of BARS retranslation: the anchor describes an *observable*,
   which is what makes two panels agree. (REASONING, strongly suggested by [6][7].)
5. Anchors are part of the criterion, versioned with it, and reused byte-identically across sessions
   and across re-scoring of a single column (§1, the between-panel result).

**Cost control.** Anchor drafting is one prompt, not a separate elicitation stage. A criterion whose
anchors cannot be written as evidence conditions is a signal that the criterion is not operable —
which is a finding worth surfacing at the confirmation checkpoint rather than a cost to be absorbed.
That turns the cost into a diagnostic. Anchors can also be omitted for criteria whose level of
measurement is already self-anchoring (a nominal category, a ratio-level cost); the requirement
binds on ordinal `score` criteria only.

### 3. Scale granularity: 1–5, and the honest reconciliation

There is a genuine conflict in the literature and it is worth stating precisely rather than
splitting the difference.

**The LLM-judge side (widen).** Stureborg et al. instructed GPT-4 to score SummEval summaries on
several scales and measured Kendall's τ against human expert scores [2]:

| Method | effective granularity | Coh | Con | Flu | Rel | **Avg τ** |
|---|---|---|---|---|---|---|
| 1–5 star | 5 | .332 | .362 | .325 | .337 | **.339** |
| 1–5, 10-sample average | 41 | .422 | .370 | .356 | .439 | **.397** |
| 1–10 score | 10 | .450 | .433 | .366 | .462 | **.428** |
| 1–10, 10-sample average | 91 | .424 | .366 | .332 | .435 | **.389** |
| 1–100 score | 100 | .463 | .423 | .308 | .339 | **.383** |
| 1–100, 10-sample average | 991 | .406 | .351 | .343 | .414 | **.379** |

(EVIDENCE.) Their Table 6 recipe therefore says "widen scores to 1–10 star scale". Two details the
recipe line hides. First, the curve is **not monotone**: 1–100 is worse than 1–10, and the paper's
own Figure 3 shows why — across 64,000 predictions on the 1–100 scale, models pile mass on 90 and 95,
almost never use 1–60, and show clear round-number peaks at 60/70/75/80/85/90/95. Stureborg names
this **round number bias** and connects it explicitly to the human literature on the same [2].
Second, **1–5 with sample-averaging (τ = .397) recovers roughly two thirds of the 1–5 → 1–10 gap**
without changing the scale the reader sees, and the same averaging *hurts* 1–10 and 1–100.

**The absolute-agreement side (narrow).** Li et al. (2026) collected fully crossed ratings from 12
human annotators and six LLM judges on six benchmarks, on 0–5, 0–10 and 0–100 scales, and measured
absolute-agreement intraclass correlation rather than rank correlation [3]:

| Scale | ICC_human | ICC_LLM | **ICC_human-LLM** | nMAE |
|---|---|---|---|---|
| 0–5 | 0.957 | 0.944 | **0.853** | **0.111** |
| 0–10 | 0.941 | 0.950 | 0.805 | 0.122 |
| 0–100 | 0.953 | 0.947 | 0.840 | 0.115 |

(EVIDENCE.) 0–5 wins on both agreement and error, and **0–10 is the worst of the three** — the exact
scale Stureborg recommends. Their framing: "the choice of scale substantially shifts human-LLM
agreement, even when within-group panel reliability is high."

**The human rating-scale side (5 to 7).** Preston & Colman had 149 respondents rate the same objects
on scales from 2 to 11 points plus a 101-point scale: two-, three- and four-point scales performed
poorly on reliability, validity and discriminating power; indices rose up to about seven points; and
test–retest reliability *declined* above ten points [11]. (EVIDENCE.) The finding from that study
that cuts the other way, and that is usually dropped: *respondent preferences* were highest for the
10-point scale, closely followed by the seven- and nine-point scales. [11] supports "not fewer than
about five", not "as narrow as possible". Simms et al. randomly assigned 1,358 respondents to response
scales from 2 to 11 options plus a visual analogue and found attenuated psychometric precision below
6 options and **no psychometric advantage for any scale beyond 6 options**, visual analogues
included [12]. (EVIDENCE.)

**Reconciliation.** The two literatures are not measuring the same thing, and rubricator's product
determines which one binds.

- Stureborg optimises **rank correlation against a gold label** — i.e. tie-breaking and
  discrimination. Widening helps because more distinct values means fewer ties, up to the point where
  token-level round-number priors take over.
- Li et al. and the psychometric literature optimise **absolute agreement between raters** — does a
  4 from the model mean the same thing as a 4 from a person. That is a different quantity and it
  peaks lower.
- **rubricator does not ship a ranking by default.** comparanda ADR-0015 declines default
  aggregation, and the scoring-order document's own decision rule ends with "if median τ < 0.7, stop
  trusting the matrix as a ranking device" [1]. The deliverable is a matrix a team argues over,
  cell by cell, with a value-suppressing palette built for 5 score levels × 3 confidence levels
  (comparanda ADR-0010 and its research section on views and uncertainty). So the binding quantity is
  **absolute level agreement and human legibility**, not tie-breaking — which is precisely where 0–5
  wins [3][11][12]. (REASONING, resting on evidence at each step.)
- Where discrimination *is* wanted, buy it the way Stureborg's own table says you can: **k repeats,
  aggregated**. Store the median (not the mean — a 1–5 rating is ordinal, comparanda ADR-0003) and
  report the dispersion separately. This is also already the recommended mitigation in the
  scoring-order document [1] for a different reason (run-to-run variance), so it costs nothing new.

**Decision: `score` is a 1–5 integer, declared ordinal, with anchors at 1/3/5.** Do not offer 1–10,
1–7 or 0–100 as configuration; a per-analysis scale choice would make two analyses incomparable and
would break the palette. If a criterion genuinely needs more resolution it is a ratio-level criterion
(a cost, a count, a latency) and should be typed as such rather than squeezed into a wider ordinal.

### 4. Calibration: what Hubbard gives us, and what he does not

**The equivalent-bet test.** Hubbard's device for eliciting a 90% interval: ask the estimator to
choose between (a) winning a prize if the true value falls inside their stated interval, and (b)
winning the same prize on a spinner that pays 90% of the time. Preferring the spinner means the
interval is too narrow; preferring the question means it is too wide; indifference means the stated
90% is a real 90% [13]. (EVIDENCE that the technique exists and is described this way; it is a
mechanism for exposing the meaning of a probability, not itself a validated intervention.)

**Calibration training.** Hubbard reports that people asked for a 90% interval hit the true value
far less than 90% of the time before training, and that about half a day of training brings most
subjects close to calibration. (UNVERIFIED — could not locate source. The specific before/after
percentages previously given here (≈55% → ≈85%) do not appear on the cited secondary page [13], and I
could not check them against *How to Measure Anything* itself. Vendor-reported in any case.) A critical reading of the calibration-training evidence base on
the EA Forum concludes that the published improvements — including Rieber's summaries and the
frequently cited Shell geologists example — are **within-domain**, that Hubbard's own data is "not a
controlled trial and he doesn't provide the underlying data", and that cross-domain transfer from
trivia calibration to substantive forecasting is not convincingly demonstrated [14]. (EVIDENCE
against overclaiming — but the source is a forum post plus one commenter's analysis, not a
peer-reviewed review, so it is weak evidence for a strong conclusion.)

**What this means for rubricator** (REASONING): the transferable part of Hubbard is not the training
programme — you cannot train a fixed model on trivia questions and expect transfer, and even for
humans the transfer is unproven. The transferable parts are two:

1. **The elicitation discipline.** A confidence claim must be stated in a form that has an
   operational meaning — the equivalent-bet framing is the cleanest known way to force that, and it
   translates into a prompt instruction rather than a training regime.
2. **The scoring discipline.** A confidence claim is only worth storing if something later checks it
   against outcomes. That is ADR-0008's calibration bullet, and it is the part that must be built.

**The critical, unaddressed problem.** ADR-0008 says: "on fixtures with known answers, do
high-confidence cells outperform low-confidence ones?" That is a **discrimination** test, and an
ordinal evidence-quality label can pass it. It is *not* a calibration test, and none of the classical
calibration machinery — Brier, reliability diagrams, ECE — can be computed on an evidence-quality
label at all, because those require a number that claims to be a probability of an outcome. As
written, ADR-0008's calibration item is not implementable with ADR-0006's confidence definition.
This is the sharpest finding in this section.

Evidence that filling the gap is cheap: verbalised confidences emitted as output tokens are
typically *better* calibrated than a model's conditional token probabilities, "often reducing the
expected calibration error by a relative 50%" for RLHF-tuned models across TriviaQA, SciQ and
TruthfulQA [15]. (EVIDENCE.) So simply asking is a defensible elicitation method — which matters
doubly here, because ADR-0003 forbids any tool that requires a model call, and token log-probabilities
are unavailable in the connector runtime anyway.

Evidence that it will need checking: ClimateX asked LLMs to classify the confidence level that IPCC
authors had assigned to climate statements — a four-level qualitative scale grounded in an
evidence-and-agreement framework, i.e. structurally the same task as assigning rubricator's
`confidence`. GPT-4 managed **44.3% accuracy zero-shot and 47.0% few-shot**, against 36.3% for a
small sample of non-expert humans; all tested models "consistently over-estimate confidence in the
'low' and 'medium' categories"; and models expressed a knowledge limitation ("I don't know") on
between none and 4% of prompts [16]. (EVIDENCE.) That is the exact failure mode ADR-0006 exists to
prevent — grade inflation at the bottom of the confidence scale, plus near-total unwillingness to
decline — measured on a near-identical task. It is the strongest single argument in this document for
building the evaluation suite before shipping prompts.

### 5. Anchoring, order effects and scale-use bias in human raters (background)

The scoring-order document covers order effects, halo, joint-vs-separate evaluation and sequential
contrast in depth [1]; this section adds only what it does not.

- **Anchoring is not fixable by warning people.** Tversky & Kahneman's anchoring-and-adjustment
  finding survives transparently irrelevant anchors (a spun roulette wheel shifted estimates of
  African UN membership from 25% to 45%), monetary incentives, explicit forewarning, and expert
  judges — real-estate agents anchored on listing price as strongly as novices while denying any
  influence [17]. (EVIDENCE.) The implication for a rubric is that whatever number is in front of the
  rater *is* an anchor, including the numbers in the anchor descriptors themselves; keep numeric
  values out of anchor prose unless they are the actual thresholds.
- **Scale-use biases are rater-level, not item-level.** Acquiescence ("yea-saying"), extreme response
  style, and midpoint/central-tendency preference are documented response biases that shift a rater's
  whole distribution rather than any single rating [18]. (EVIDENCE for the existence of the three
  biases. The cited overview does *not* characterise them as stable individual traits — it treats
  them as situational — and I did not verify that stronger claim against a primary source, so treat
  "rater-level" as a working assumption, not a finding.) The LLM analogues are
  well documented and are the same shape: Stureborg's round-number clumping and the near-total
  avoidance of the 1–60 range on a 1–100 scale [2], and the ceiling effects reported for judges whose
  scores concentrate near the top.
- **The double-counting trap.** A rater who is unsure can express it twice: by hedging the score
  toward the midpoint *and* by lowering the confidence. ADR-0006 forbids the hedge only in the
  *no-evidence* case ("emit `unknown` with a note, not a hedged 3"); nothing in it forbids the hedge
  in the *thin-evidence* case, and central-tendency bias makes it the default behaviour. It corrupts the matrix in the most
  damaging possible way, because the blended encoding then suppresses an already-suppressed value.
  (REASONING, resting on the central-tendency literature [18].) The rule below fixes it in one line.

### 6. Prior art for an evidence-quality scale — and the case for two measures

ADR-0006's choice ("confidence means evidence quality, not model certainty") is not idiosyncratic. It
is the mainstream position in four independent fields, all of which reached it by the same route:
somebody kept confusing "how sure am I" with "how good is my source", and it caused harm.

| Framework | What is rated | Levels | Note |
|---|---|---|---|
| **GRADE** [19] | certainty that the observed effect reflects the true effect | high / moderate / low / very low | Starts at a level set by study design, then five explicit domains (risk of bias, inconsistency, indirectness, imprecision, publication bias) each rate it down 1–2 levels. |
| **GRADE-CERQual** [20] | confidence in a finding of a *qualitative* evidence synthesis | high / moderate / low / very low | Four components: methodological limitations, coherence, adequacy of data, relevance. This is the closest structural analogue to rubricator: a judgement synthesised from a document corpus rather than from trials. |
| **IPCC** [21][22] | confidence in a finding | very low / low / medium / high / very high | Explicitly the **product of two dimensions**: *evidence* (type, amount, quality, consistency) and *agreement*. Where a confidence level cannot be assigned, authors may report evidence and agreement separately. Confidence is qualitative and is kept distinct from the separate, quantified *likelihood* scale. |
| **ICD 203** (US intelligence analytic standards) [23] | analytic confidence, separately from source credibility | high / moderate / low | Confidence rests on quantity and quality of sources plus depth of understanding; the directive explicitly forbids combining a confidence level and a likelihood term in the same sentence, because it confuses the reader about what is uncertain. |
| **Admiralty / NATO code** [24] | source reliability (A–F) **×** information credibility (1–6) | two independent letters/digits | "Each descriptor is considered in isolation to ensure that the reliability of the source does not influence the assessed accuracy of the report." |

(All EVIDENCE. The IPCC guidance note PDF and the ICD 203 PDF both returned HTTP 403; their content
here is taken from two independent secondary descriptions each, and the IPCC framework description is
corroborated by the ClimateX paper's own account of the scheme [16].)

Three conclusions follow.

**(a) Do not adopt an established scale wholesale.** GRADE and CERQual are four-level and are
designed to be *argued* — each level comes with a written rationale over four or five named domains.
That is right for a systematic review and wrong for a cell in a matrix that must render in a 40×30 px
box. IPCC's five levels are also too many: ClimateX shows that even the four-level version is
classified at 44–47% accuracy by frontier models, with systematic inflation at the bottom [16], and
comparanda's palette is built for three. **Adopt the *structure* — a named, closed set of downgrade
reasons — at three levels.**

**(b) Every one of these frameworks separates two things, and rubricator currently stores one.** The
Admiralty code's independence principle is the crispest statement of why. rubricator's `confidence`
is the *source* half (Admiralty's letter, ICD 203's source credibility, IPCC's *evidence*). The other
half — how sure the assessor is that the judgement is right — is currently nowhere. This is not a
theoretical gap: it is why ADR-0008's calibration bullet cannot be implemented (§4).

**(c) Therefore: two measures.** comparanda's data model makes this nearly free — the matrix is a
tensor of `alternatives × criteria × measures`, measures is a real dimension, and the level of
measurement is declared per `(criterion, measure)` pair (comparanda ADR-0003). Adding a third measure
requires no schema change there, only a new encoding if you want to *see* it — and you mostly do not.

---

## What this means for the schema / the view / the agent

### The confidence scale rubricator should use (this is the deliverable)

`confidence` — **stored measure, ordinal, exactly three levels**, declared
`{"level": "ordinal", "values": ["low", "medium", "high"]}` in the comparanda type declaration.

| Level | Definition | The test a reader can apply |
|---|---|---|
| **high** | The claim in the justification is **stated, or directly entailed, by the text inside at least one cited span**, and no cited span contradicts it. | Open the span. If you would write the same justification from that text alone, it is `high`. |
| **medium** | No single cited span states the claim. It follows by **short inference over one or more cited spans**, or rests on a cited **secondary summary** of a primary source rather than the primary source itself. | Open the spans. You should be able to name the inferential step in one sentence. |
| **low** | The claim rests on **reasoning over cited context that is only indirectly related** — an adjacent product, an earlier period, a comparable alternative — and a reasonable reader could reach a different score from the same spans. | Open the spans. If you cannot see how the score follows, the cell is wrong, not merely low. |

Three rules make the scale mean something. Two are absent from ADR-0006; the third sharpens a rule it
already states. Together they matter more than the level definitions.

1. **No citable span → `unknown`, not `low`.** If the agent cannot attach at least one evidence
   reference, it must emit a qualified missing with reason `unknown` (comparanda ADR-0009), not a
   scored cell at `low` confidence. `low` means *thin evidence*, never *no evidence*. Without this
   rule `low` becomes the laundering channel for exactly the guesses ADR-0006 exists to prevent, and
   ClimateX shows the model will take that route by default [16].
2. **The score is never hedged.** `score` is the best estimate given the available evidence. It is
   never pulled toward 3 because the evidence is thin. All uncertainty lives in `confidence`. This
   *extends* ADR-0006's existing "not a hedged 3" rule — which binds only in the no-evidence case —
   to the thin-evidence case; it forbids the double-counting trap of §5 and is one line in the
   scoring prompt.
3. **Contradiction is a downgrade with a named reason.** If two cited spans disagree, drop one level
   and record the reason. Adopt a closed set of downgrade reasons, CERQual-style, on the cell:
   `secondary-source`, `inference-required`, `indirect-context`, `sources-disagree`, `stale-source`,
   `single-source`. These are a small nominal measure or a per-cell annotation, they are countable,
   and they are what makes a confidence label auditable instead of a vibe.

### The second measure

`certainty` — **stored measure, optional, ratio level, values drawn from a fixed closed set**
`{0.5, 0.6, 0.7, 0.8, 0.9, 0.95}`, declared per `(criterion, "certainty")`.

- **Definition to put in the prompt:** *the probability that an expert with full access to this
  corpus, scoring this cell independently, would assign the same `score` level.* Elicit it with the
  equivalent-bet framing [13]: "would you rather be paid if that expert agrees, or on a spinner that
  pays with this probability?"
- **Why a fixed closed set and not a free number.** Autorubric excludes unbounded numeric criteria
  because "LLM judges exhibit poor calibration when asked to produce unbounded numeric scores" [10],
  and Stureborg's round-number clumping shows what a free 0–100 elicitation actually produces [2]. A
  fixed set also has a large, underrated benefit for the evaluation suite: **every allowed value is
  its own bin, so the reliability diagram and ECE have no binning choice to make**, which removes the
  single largest source of estimator bias (§ next).
- **Why optional.** It is a second judgement per cell — another anchoring surface (scoring-order
  document [1]) and another token cost. Make it required only when the analysis is being run against
  a fixture with known answers, or when the user asks. Everything in the discrimination suite below
  works without it.
- **View impact:** none by default. comparanda's value-suppressing palette consumes `score` ×
  `confidence` and should keep doing so; `certainty` gets a plain single-measure encoding and a line
  in the cell detail panel. Do **not** blend three measures into one colour.

### Criteria carry anchors

Extend the criterion definition emitted by `propose-criteria` with:

```
criterion:
  key, label, definition, polarity, level_of_measurement, veto        # ADR-0005 step 3
  anchors:                                                            # new
    "1": "<evidence condition that would make this cell a 1>"
    "3": "<evidence condition for the midpoint>"
    "5": "<evidence condition for a 5>"
  anchors_version: <content hash>                                     # new
```

`anchors_version` is a hash of the three strings. Two analyses that share a criterion key but not an
anchors hash are **not comparable on that criterion**, and the tooling should say so rather than
letting the reader assume otherwise. This is the direct operational response to the between-panel
drift result [7].

A deterministic MCP tool (no model call, ADR-0003):

```
validate_criteria(criteria) -> CriteriaReport
```

checking, per ordinal criterion: all three anchors present and non-empty; pairwise distinct after
normalisation; each within a length bound; anchor keys consistent with the declared polarity; and —
the useful one — flagging any anchor that contains no concrete, checkable noun phrase by a simple
lexical heuristic, reported as a warning for the human checkpoint, never as a hard failure.

### Calibration metrics for the ADR-0008 evaluation suite

Two families, because there are two measures. All of these are pure functions over an
already-schema-valid analysis plus a gold fixture, so all of them are deterministic tools.

**Family A — discrimination of `confidence` (always computed).**

| Function | Reports | Why |
|---|---|---|
| `accuracy_by_confidence(analysis, gold)` | exact-match and within-1-level accuracy per confidence level, each with a **Wilson score interval** and its `n` | ADR-0008's actual question. Wilson because bins will be small and the normal-approximation interval is wrong near 0 and 1. |
| `confidence_monotonicity(analysis, gold)` | one-sided trend test that acc(high) ≥ acc(medium) ≥ acc(low), with a bootstrap p-value | Turns "do high-confidence cells outperform low ones" into a pass/fail gate. |
| `somers_d(analysis, gold)` / `kendall_tau_b(...)` | rank association between confidence and correctness | The right substitute for AUROC when confidence has three levels and therefore enormous tie mass. Report AUROC too if you like, but tau-b is the honest number. |
| `confidence_inflation_rate(analysis)` | share of `high` cells whose cited span **fails the citation-faithfulness check** of ADR-0008 | The single most actionable metric in the suite, and it needs no gold labels — it composes two checks ADR-0008 already requires. Set a release gate on it. |
| `unknown_preference_rate(analysis, gold)` | on no-evidence fixtures, share of cells emitted as qualified-missing `unknown` | ADR-0008's "refusal to guess", made numeric. |
| `low_confidence_laundering_rate(analysis, gold)` | on no-evidence fixtures, share of cells **scored at `low`** instead of `unknown` | Directly measures rule (1) above. ClimateX predicts this will be the failing metric [16]. |

**Family B — calibration of `certainty` (computed when the measure is present).**

| Function | Reports | Pitfall it is designed around |
|---|---|---|
| `brier(analysis, gold)` | mean squared error of `certainty` against the 0/1 indicator "score level correct" | A Brier score alone is uninterpretable — always pair it with the two below. |
| `brier_decomposition(...) -> (reliability, resolution, uncertainty)` | Murphy's three-component partition, BS = REL − RES + UNC [26] | Separates "my probabilities are honest" (reliability) from "my probabilities are informative" (resolution). A confident-and-useless forecaster and a hedging-but-honest one have very different profiles and the same Brier score. |
| `brier_skill_score(..., baseline="fixture-base-rate")` | 1 − BS/BS_ref [25] | Without a baseline, a low Brier may just mean the fixture set is easy. |
| `reliability_curve(..., binning="value")` | observed accuracy vs stated certainty, one point per **allowed certainty value**, with Wilson intervals and `n` printed on each point | Because `certainty` is drawn from a fixed set, there is no binning decision. This is the whole reason for the closed set. |
| `expected_calibration_error(..., min_n=100)` | ECE, **secondary**, always printed with its binning scheme and bin count | ECE's value depends on bin number and boundaries, with a classic bias–variance trade-off: too few bins hides discrepancies, too many gives sparse bins and unstable estimates [27]. Equal-mass bins have lower bias than equal-width [28]. Never compare two ECEs computed with different schemes. Refuse to print a headline number below `min_n`. |
| `auroc_certainty_vs_correct(...)` | AUROC | Discrimination is orthogonal to calibration: a perfectly calibrated constant forecaster scores AUROC 0.5. Report both or neither. |

**Pitfalls to hard-code into the harness, not into a docstring.**

- **Small n.** With fewer than ~100 scored cells, report the reliability curve and the Brier
  decomposition and suppress the headline ECE. Binning bias dominates at small sample sizes [28].
- **Cells are not independent.** Cells inside one analysis share a corpus, a frame and a criterion
  anchor set. **Bootstrap by analysis, not by cell**, or every interval will be far too narrow.
- **Never average `confidence`.** It is ordinal (comparanda ADR-0003). Report the distribution, or
  the median with the level counts. A "mean confidence of 2.4" is a category error and the tooling
  should refuse it.
- **Report per criterion as well as pooled.** ADR-0008's fixtures deliberately mix evidence-rich and
  evidence-absent cells; pooling hides exactly the contrast the suite exists to measure.
- **Stability interacts with all of this.** Run the calibration suite over the k-repeat aggregate,
  and report the repeat dispersion beside it — a confidence label that moves between runs is not
  calibrated, it is noise (scoring-order document §6 [1]).

### Scoring-loop consequences (the agent, not the tools)

- Score cell-wise, one criterion per generation, per the scoring-order document [1]. Nothing here
  changes that; per-level anchors make it cheaper, because the anchor text is short and can be sent
  with every isolated call.
- Default **k = 3** repeats, aggregated by **median** (odd k, ordinal data). Use k = 5 in the
  evaluation harness. Diminishing returns set in around 3–5 [1].
- Send with every scoring call: the criterion definition, the three anchors, the polarity, the source
  spans, and the confidence rule. Stureborg's recipe includes the criterion definition verbatim and
  keeping the source document in context even for attributes that appear not to need it [2].
- The `review` stage (ADR-0005 step 6) should list the cells whose confidence is `high` but whose
  span is short or whose justification paraphrases heavily — that is `confidence_inflation_rate`
  turned into prose, and it is the self-critique ADR-0006 asks for.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0005 | confirm | Step 3 already demands definitions and polarity; anchors are an addition to the same step and the step-4 checkpoint is where they get confirmed. No change of substance. |
| ADR-0006 | amend | The evidence-quality definition of confidence is right and well supported, but the ADR omits the rule that makes it enforceable: *no citable span → `unknown`, never a low-confidence score*. It already forbids "a hedged 3" in the no-evidence case; extend that to the thin-evidence case so *the score is never hedged toward the midpoint* at all. Mechanically this means a superseding ADR, since ADR-0006 is accepted. |
| ADR-0008 | amend | Its calibration bullet names a **discrimination** test, not a calibration test, and no proper scoring rule can be computed on an ordinal evidence-quality label. Split the item into the two metric families above and state which measure each scores. |
| — | new ADR | **"Measurement scales and the meaning of confidence"**: `score` is 1–5 integer ordinal with required anchors at 1/3/5 written as evidence conditions and versioned by content hash; `confidence` is 3-level ordinal evidence quality with the three enforcement rules and a closed set of downgrade reasons; `certainty` is an optional ratio measure drawn from a fixed set of allowed probabilities. Explicitly rejects a configurable scale width. |
| — | new ADR | **"Calibration and confidence-quality metrics"**: the Family A / Family B metric lists, the `min_n` gate on ECE, bootstrap-by-analysis, the ban on averaging `confidence`, and `confidence_inflation_rate` as a release gate. |
| comparanda ADR-0003 | confirm | No schema change needed for a third measure — measures is already a dimension and the level of measurement is declared per `(criterion, measure)`. Worth confirming with that repo before relying on it. |

---

## Open questions

- **Does anchoring help LLM judges, specifically?** Every strong LLM-judge system I found uses
  per-level descriptors [8][10], and none publishes an ablation isolating them. The +0.1 ICC figure
  is from human assessors, is a mean across rater pairings, and rests on overlapping ranges [5]. This
  is directly testable on rubricator's own fixtures — same
  criteria, same corpus, anchors on vs off, measure inter-run agreement and accuracy — and it is the
  cheapest experiment in this document. Run it before writing five descriptors per criterion for
  anything.
- **Is 1–5 with k repeats really as good as 1–10 for us?** The reconciliation in §3 is reasoning over
  two studies that measured different quantities. The decisive local test is Stureborg's comparison
  re-run on rubricator's fixtures with rubricator's anchored 1–5: does median-of-3 on the anchored
  1–5 match or beat a bare 1–10 on agreement with the gold fixture? Add it as a further arm to the
  five already specified in the scoring-order document's experiment [1].
- **Does the `unknown`-vs-`low` rule survive contact with a real corpus?** ClimateX [16] predicts the
  model will resist emitting `unknown`. Whether the rule is followable, or produces an unusably
  sparse matrix, is an empirical question the fixture suite answers.
- **Are three confidence levels enough to calibrate against?** With three levels and a fixture set of
  realistic size, the per-level cells will be small and the Wilson intervals wide. If they are too
  wide to gate on, the answer is more fixtures, not more levels — but that is an assertion I have not
  tested.
- **The IPCC's second dimension.** IPCC crosses evidence with *agreement* [21][22]. rubricator's
  single-agent case has no agreement dimension, but a multi-run or multi-model configuration does,
  and comparanda already supports multi-rater spread. Whether repeat-dispersion should be surfaced as
  an IPCC-style agreement measure — rather than only as an evaluation statistic — is unresolved and
  interacts with comparanda's own work on rater agreement.
- **Two primary sources unread.** The IPCC uncertainty guidance note and ICD 203 both returned HTTP
  403 to automated fetching. Their frameworks are described here from corroborating secondary sources
  and, for IPCC, from a paper that operationalised the scheme [16]. Someone should read both directly
  before the confidence ADR is accepted; neither is long.

---

## REFERENCES

1. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Thor Whalen (2026)](../scoring-order-effects.md) — in this repository, `docs/research/`
2. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
3. [Grading Scale Impact on LLM-as-a-Judge: Human-LLM Alignment Is Highest on 0-5 Grading Scale — Li et al. (2026)](https://arxiv.org/abs/2601.03444)
4. [The use of scoring rubrics: Reliability, validity and educational consequences — Jönsson & Svingby (2007), *Educational Research Review* 2(2):130–144, doi:10.1016/j.edurev.2007.05.002](https://doi.org/10.1016/j.edurev.2007.05.002) — *bibliographic record verified via Crossref and OpenAlex; ScienceDirect returns HTTP 403 and the publisher elides the abstract from OpenAlex, Crossref, Semantic Scholar and Europe PMC, so the wording attributed to it above is **unverified***
5. [Assessor experience, not rubric type, determines grading reliability in biosciences coursework — Chamberlain, Francis & Herrick (2026), *Frontiers in Education*](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2026.1729644/full) — *ICC values above are from its Table 2; verified*
6. [Behaviorally anchored rating scales — Wikipedia, summarising Smith & Kendall (1963)](https://en.wikipedia.org/wiki/Behaviorally_anchored_rating_scales)
7. [New data on Behaviorally Anchored Rating Scales (BARS): Vanishing high inter-rater reliability — Wiesen, APA Division 5 *Score* (2025)](https://www.apadivisions.org/division-5/publications/score/2025/10/data-scales-reliability)
8. [Prometheus: Inducing Fine-grained Evaluation Capability in Language Models — Kim et al. (2023)](https://arxiv.org/abs/2310.08491)
9. [prometheus-eval — reference implementation and score-rubric format](https://github.com/prometheus-eval/prometheus-eval)
10. [Autorubric: A Unified Framework for Rubric-Based LLM Evaluation — Rao & Callison-Burch (2026)](https://arxiv.org/abs/2603.00077)
11. [Optimal number of response categories in rating scales: reliability, validity, discriminating power, and respondent preferences — Preston & Colman (2000), *Acta Psychologica* 104:1–15](https://www.sciencedirect.com/science/article/abs/pii/S0001691899000505)
12. [Does the number of response options matter? Psychometric perspectives using personality questionnaire data — Simms, Zelazny, Williams & Bernstein (2019), *Psychological Assessment* 31(4):557–566](https://pubmed.ncbi.nlm.nih.gov/30869956/)
13. [Improve Your Estimations with the Equivalent Bet Test — Martin-Vegue (2019), describing Hubbard, *How to Measure Anything*](https://www.tonym-v.com/blog/2019/10/2/improve-your-estimations-with-the-equivalent-bet-test) — *verified for the equivalent-bet mechanism only; this page reports **no** calibration-training statistics*
14. [Does "calibrated probability assessment" training work? — EA Forum question post (2022); the critical analysis quoted here is in the comment by user Tyner, not the post body](https://forum.effectivealtruism.org/posts/qFkEhW7Hn2mkJvjNv/does-calibrated-probability-assessment-training-work)
15. [Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback — Tian et al. (2023)](https://arxiv.org/abs/2305.14975)
16. [ClimateX: Do LLMs Accurately Assess Human Expert Confidence in Climate Statements? — Lacombe et al. (2023)](https://arxiv.org/abs/2311.17107)
17. [Judgment under Uncertainty: Heuristics and Biases — Tversky & Kahneman (1974), *Science* 185(4157):1124–1131; anchoring persistence summarised at](https://en.wikipedia.org/wiki/Anchoring_effect)
18. [Response bias: acquiescence, extreme response style and midpoint preference — Wikipedia overview](https://en.wikipedia.org/wiki/Response_bias)
19. [GRADE Criteria: Determining Certainty of Evidence — ACIP GRADE Handbook, CDC](https://www.cdc.gov/acip-grade-handbook/hcp/chapter-7-grade-criteria-determining-certainty-of-evidence/index.html) — *returned HTTP 403 to automated fetch; the GRADE row in the table above states the framework's standard published form and should be re-checked against the handbook by a human*
20. [GRADE & GRADE-CERQual — Mayo Clinic Evidence Synthesis Guide](https://libraryguides.mayo.edu/c.php?g=1136733&p=8514645) — *verified: names the four CERQual components (methodological limitations, coherence, adequacy, relevance) and the four confidence levels. It does **not** cite or summarise Lewin et al.; the primary CERQual series introduction is [Lewin, Booth, Glenton, Munthe-Kaas, Rashidian et al. (2018), "Applying GRADE-CERQual to qualitative evidence synthesis findings: introduction to the series", *Implementation Science* 13(Suppl 1)](https://doi.org/10.1186/s13012-017-0688-3), which is unread here*
21. [Guidance Note for Lead Authors of the IPCC Fifth Assessment Report on Consistent Treatment of Uncertainties — Mastrandrea et al. (2010)](https://www.ipcc.ch/site/assets/uploads/2017/08/AR5_Uncertainty_Guidance_Note.pdf) — *primary PDF returned HTTP 403 to automated fetch; framework described here from [16] and [22]*
22. [In-depth Q&A: the IPCC's sixth assessment report on climate science — Carbon Brief (2021)](https://www.carbonbrief.org/in-depth-qa-the-ipccs-sixth-assessment-report-on-climate-science)
23. [Intelligence Community Directive 203: Analytic Standards — ODNI](https://www.intel.gov/assets/documents/intelligence-community-directives/ICD_203.pdf) — *primary PDF returned HTTP 403 to automated fetch; content described from two independent secondary summaries*
24. [Admiralty code (NATO source reliability × information credibility) — Wikipedia](https://en.wikipedia.org/wiki/Admiralty_code)
25. [Verification of forecasts expressed in terms of probability — Brier (1950), *Monthly Weather Review* 78(1):1–3, doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2; definitions and skill score summarised at](https://en.wikipedia.org/wiki/Brier_score)
26. [A new vector partition of the probability score — Murphy (1973), *Journal of Applied Meteorology* 12(4):595–600, doi:10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2](https://en.wikipedia.org/wiki/Brier_score)
27. [Understanding Model Calibration: a gentle introduction and visual exploration of calibration and the expected calibration error — Pavlovic (2025)](https://arxiv.org/abs/2501.19047)
28. [Mitigating Bias in Calibration Error Estimation — Roelofs, Cain, Shlens & Mozer (2022), AISTATS](https://arxiv.org/abs/2012.08668)
