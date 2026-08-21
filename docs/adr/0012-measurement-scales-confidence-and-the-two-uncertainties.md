# ADR-0012: Measurement scales, what confidence means, and the two uncertainties

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0006 is the parent of this ADR and nothing here overturns it. It defines `confidence` as
evidence quality and it prefers a qualified blank to a confident guess. What it does not say is what
happens when the model wants to hedge, what scale `score` uses, or how "this cell is uncertain"
differs from "this cell moves between runs". Those omissions are where the guarantee erodes: a rule
with no stated consequence is a statement of intent, and an agent under pressure will satisfy the
intent with a low-confidence 3.

There is a second, narrower problem. ADR-0008 asks whether high-confidence cells outperform
low-confidence ones and calls that calibration. As written it cannot be computed: no proper scoring
rule — Brier, ECE, a reliability diagram — exists over an ordinal evidence-quality label. The
metric needs either a probability to score or a different name.

This ADR states the consequences ADR-0006 left unstated, and fixes the scales they are stated over.

## Decision

**`score` is a 1–5 integer, declared ordinal, not configurable.** Buy discrimination with repeats,
not width. On absolute human–LLM agreement a narrow scale beats 0–10 and 0–100 [1], and rubric
position bias is non-monotone in scale length, lowest at 3 or 5 points [2]. A criterion that genuinely
needs more resolution is a ratio-level criterion and must be typed as one, not a wider ordinal.

**The scale has five levels, and that is a choice rather than a transcription.** The
absolute-agreement result was measured on 0–5 — six categories, not five [1] — and the psychometric
work usually cited beside it puts the floor at six response options [3], with reliability indices
rising to about seven [4]. Five is adopted anyway, on three grounds: the position-bias experiment
that varied scale length over n ∈ {2, 3, 5, 9} found n = 5 among the lowest-bias settings [2]; the
1/3/5 anchor scheme below needs an odd number of levels with a defined middle; and `comparanda`
encodes a cell as score × confidence through a merge tree built for five score levels and three
confidence levels. Six levels is considered and rejected, not overlooked.

**Every criterion declares the range its scores live in.** For the fixed ordinal scale that
declaration is the constant 1–5 and costs nothing. For a ratio-level criterion it is elicited at
ADR-0005 step 3 beside the level of measurement, and it is never inferred from the observed values:
bounds read off the data change what every stored score means each time an alternative is added.

**Ordinal criteria carry required anchors at levels 1, 3 and 5 only** — 2 and 4 are structurally
"between", and demanding text for them roughly doubles elicitation cost per criterion to describe
two levels no one can distinguish. Anchors are written as **evidence conditions** ("a source states
X"), never as evaluative adjectives ("excellent"), because an adjective is scored against the
reader's taste and a condition is scored against a document.

**Anchors are versioned by content hash with the criterion, and the hash is a comparability rule.**
Two analyses sharing a criterion key but not an anchor hash are **not comparable on that criterion**.
The tooling says so rather than silently aligning the columns, and it says so at the point of
comparison, not in a footnote.

**`confidence` is a three-level ordinal evidence-quality measure, exactly as ADR-0006 defines it.**
That definition is confirmed, not amended — separating source quality from the judgement is standard
practice in evidence grading (GRADE-CERQual, ICD 203, the Admiralty code; see
`docs/research/findings-method.md` § 2 row 9). Three enforcement rules ADR-0006 leaves unstated now
bind:

1. **No citable span ⇒ `missing`, never a low-confidence score.** A low-confidence number is still a
   number, and readers round it to a fact. ADR-0006's code for this today is `unknown`. When
   `comparanda`'s missingness reason set splits, this rule's branch is `not-evidenced` — sources
   were consulted and are silent — and `indeterminate` covers the second case, where material was
   found but does not resolve to a level.
2. **The score is never hedged toward the midpoint.** All uncertainty lives in `confidence`. Hedging
   the score double-counts it and destroys the only signal the reader has.
3. **Contradiction is a downgrade with a named reason** drawn from a closed set. "Sources disagree"
   is a finding about the evidence, and it is recorded as one.

**`certainty` is an optional ratio measure** drawn from a fixed closed set of allowed probabilities.
It is elicited **only** in evaluation runs against fixtures with known answers, or on explicit
request. It is **stored in the evaluation harness's own records, not in a delivered analysis** — no
`comparanda` document carries it, so it needs no schema request and no view encodes it. Should that
ever change, it goes through the schema-request protocol like any other field, and rubricator still
will not ask for a view encoding: blending an eval-only artefact into the score × confidence palette
would make it read as a delivered measure. It exists because a proper scoring rule needs a
probability; it is fenced because verbalised self-confidence is systematically overconfident
wherever nothing checks it [5].

**The two uncertainties are separated permanently.** *Evidential confidence* is **stored** and
tool-verifiable. *Procedural stability* is **derived** from the assertion set and reported
`n = 1, unmeasured` when unmeasured — never estimated, never self-reported. Sampled agreement across
repeats is admissible evidence about the **procedure** and inadmissible as evidence about
**correctness** [6].

## Consequences
A cell can now be wrong in a way the system can name, and the honesty guarantee has rules a tool can
enforce instead of a posture a prompt can drift away from. Prompts get longer, because anchors are
content. Criteria get more expensive to define. Analyses become incomparable across anchor revisions
— which is already true today and merely invisible, and the hash is what makes it visible. ADR-0008
gains two computable metric families, discrimination and calibration, in place of one uncomputable
one.

The scale is now fixed in a place that is expensive to move: consumers, palettes and anchor schemes
all assume five levels. That is the price of not making every downstream reader scale-aware.

## Alternatives considered
- ***Widening the scale to 1–10.*** This is the recommendation the owner's own scoring-order document
  carries (`docs/research/scoring-order-effects.md` § 6), and this ADR overrides it. The recommendation
  optimises rank correlation against a gold label, where more distinct values means fewer ties. This
  product does not ship a ranking by default; the binding quantity is absolute level agreement and
  human legibility, and 0–10 is the worst of the three widths measured on it [1]. Where discrimination
  is wanted, repeats buy it. The override is deliberate and should be revisited against measurement,
  not argument: a scale-length arm in the evaluation suite confirms or reopens it.
- *Six levels (0–5), matching the cited experiment exactly.* Costs the defined middle that the 1/3/5
  anchors and the score × confidence merge tree both rely on, for one extra category.
- *A configurable scale.* Every consumer would need scale-awareness, and cross-analysis comparison
  would break silently rather than loudly.
- *Anchors at all five levels.* Elicitation cost per criterion roughly doubles, for two levels that
  read as "between" however they are written.
- *Confidence as model certainty.* Nothing can check it, which makes it the field most likely to be
  inflated and the one a reader can least afford to be wrong about.
- *A stored `stability` measure.* Stability is derived from the assertion set; storing it invites the
  agent to report it, and a self-reported stability is a self-report about correctness.
- *Superseding ADR-0006.* Its decisions are all correct. Only their consequences were unstated, and
  an ADR is not superseded for being incomplete.

## Evidence
Rows 7–10 and 20 of [`docs/research/findings-method.md`](../research/findings-method.md) § 2; the
scale reconciliation in
[`docs/research/sections/r2-rubrics-and-calibration.md`](../research/sections/r2-rubrics-and-calibration.md) § 3;
the overridden recommendation in
[`docs/research/scoring-order-effects.md`](../research/scoring-order-effects.md) § 6.

1. [Grading Scale Impact on LLM-as-a-Judge: Human–LLM Alignment Is Highest on 0-5 Grading Scale — Li et al. (2026)](https://arxiv.org/abs/2601.03444)
2. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2) — *cite v2 specifically*
3. [Does the number of response options matter? — Simms, Zelazny, Williams & Bernstein (2019), Psychological Assessment 31(4):557–566](https://pubmed.ncbi.nlm.nih.gov/30869956/)
4. [Optimal number of response categories in rating scales — Preston & Colman (2000), Acta Psychologica 104:1–15](https://www.sciencedirect.com/science/article/abs/pii/S0001691899000505)
5. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
6. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065) — *single-author preprint; weak evidence*
