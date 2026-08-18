# Eliciting criteria well — the highest-leverage question in rubricator

**Research question(s):** How should `rubricator` elicit criteria? Specifically: what is the actual
procedure of value-focused thinking (Keeney) and PrOACT/*Smart Choices* (Hammond, Keeney & Raiffa),
detailed enough to become a prompt; where do the criteria-hygiene properties (completeness,
non-redundancy, operability, decomposability, minimum size, preferential independence) come from and
how do you *test* each; how do you detect overlapping criteria **before** scoring; how many criteria
before a matrix stops being usable; and what must a criterion definition contain to be scoreable?

**Brief section:** `docs/research/method.md` §1 — "How to elicit criteria well".

**Evidence grade:** **strong** for the normative decision-analysis core — four independent sources
(Keeney's own work, a UK government manual, a UK government analytical guide, and an ISPOR health
task-force report) converge on the same property list and, more usefully, on the same *tests*, and
the UK manual states them precisely enough to implement verbatim. **Moderate** for the
number-of-criteria range (practitioner convergence plus a solid experimental literature on
*splitting bias*, but no controlled study of matrix usability as a function of criteria count).
**Moderate** for the LLM-specific redundancy machinery — the papers are 2026, the validations are
small, but the direction is unambiguous and independently replicated across three groups.

**Citation audit (2026-08-18):** every reference resolves; all DOI metadata was checked against
Crossref. Quotations from [5], [6], [10], [13]–[17] and [20]–[24] were verified against the sources
character-for-character. Quotations from [7], [8], [11], [12], [19] and the body of [3] sit behind
paywalls and are marked **UNVERIFIED** at the point of use. One attribution was corrected (PrOACT
belongs to *Smart Choices* [25], not to the 1998 HBR article [8]) and one section pointer was
corrected ([5] has no §8).

---

## Bottom line

Build `propose-criteria` on **Keeney's value-focused thinking for generation** and on the **DCLG
*Multi-criteria analysis: a manual* §5.4.4 for checking** [1][5]. The brief's guess that *Smart
Choices* is "probably the best single source for the elicitation prompt" is **half right and worth
correcting**: PrOACT is the right *pipeline* frame — ADR-0005's six stages already are PrOACT plus a
checkpoint — but *Smart Choices*' distinctive contribution is **even swaps**, a trade-off method
that `rubricator` deliberately does not perform (comparanda ADR-0015: no aggregation by default).
The operational content for the criteria prompt lives in Keeney 1992 (objective-generation devices,
the WITI ladder, the nine properties) [1], Keeney & Gregory 2005 (the five attribute properties and
the natural/constructed/proxy decision) [3], and DCLG §5.4.4 (seven testable checks, including a
worked double-counting probe you can lift almost verbatim into a prompt) [5].

Four things an implementer should take away. **First**, criteria must be derived from *objectives*,
and the "why is that important?" ladder must be *emitted*, not just used — the ladder is what makes
overlap detectable and what makes a definition scoreable. **Second**, the classic overlap defect has
a structural signature: a means objective and the fundamental objective it serves, sitting side by
side as two columns. Detect it in the ladder, for free, before any scoring. **Third**, do **not**
test for redundancy by correlating scored columns. The DCLG manual gives an explicit counterexample —
"[m]utual preference independence can hold even when options are correlated in their measures on
real-world criteria provided that the criteria express separate aspects of value" [5] — and for an
LLM rater the test is worse than useless, because the judge's own halo inflates inter-criterion
correlation from a human r = 0.315 to r = 0.979 — measured on one SummEval attribute pair, so treat
the magnitude as indicative rather than general [17]. Use the **indifference probe** (conceptual) and
**synthetic-probe coupling** (computable, pre-scoring) instead [5][14]. **Fourth**, target **5–9
criteria**, warn above 7, require **groups** above 9 — and when the set is too large, *group*, never
silently *cut*; a dropped criterion is a qualified missing at the criteria level (ADR-0006 applied
one level up).

One finding contradicts the current pipeline framing and needs a new ADR: **criteria drift** [13].
Users cannot fully settle criteria before seeing scored outputs — "users need criteria to grade
outputs, but grading outputs helps users define criteria." ADR-0005's step 4 must be a gate that
opens in both directions, with explicit invalidation of cells scored under a since-changed
definition.

---

## Findings

### 1. Value-focused thinking: the generative procedure, in enough detail to be a prompt

**EVIDENCE.** Keeney's central claim is that objectives should precede alternatives. The DCLG manual
states the consequence in one sentence: "The failure to be explicit about objectives, to evaluate
options without considering what is to be achieved, led Keeney to propose that starting with options
is putting the cart before the horse. Options are important only for the value they create by
achieving objectives." [5, §5.3] This is exactly ADR-0005's stated motivation, arrived at
independently — which is a useful validation of ADR-0005 rather than a coincidence.

#### 1a. Devices for generating objectives

**EVIDENCE.** Keeney gives a set of prompts a facilitator uses when a decision maker cannot produce
objectives on demand. Reported from the standard summary of *Value-Focused Thinking* [1, via 20]:
"They might ask for a wish list, where they imagine how they would rank alternatives if constraints
were discarded; for alternatives that are particularly good or particularly bad, and what makes them
good or bad; for what problems or shortcomings the status quo has, and why these are problems; for
what consequences might determine the desirability of alternatives; for the objectives that they
think other stakeholders might have; or many others."

The DCLG manual supplies the single best opening question for a group, and it should be the literal
first move of the prompt: "brainstorm responses to the question **'What would distinguish between a
good choice and a bad one in this decision problem?'** Responses should all be noted down
uncritically" [5, §5.4.2]. It also names three ways to get stakeholder perspectives in: involve them,
mine their published statements, or **role-play** them [5, §5.4.2] — the third is directly available
to an LLM and is cheap.

**REASONING, not evidence.** For `rubricator` the highest-yield devices, in order, are: (i) the
good-choice/bad-choice question; (ii) the "particularly good / particularly bad alternative, and
what makes it so" device; (iii) shortcomings of the status quo; (iv) role-played stakeholder
perspectives. Note that (ii) uses the alternatives as *stimuli* for surfacing values without letting
them supply the *structure* — this is the resolution of the apparent conflict between VFT and
criteria drift, discussed in §7 below.

#### 1b. The WITI ladder, and the two directions of questioning

**EVIDENCE.** Keeney's "Why Is That Important?" (WITI) test discriminates the two kinds of objective.
For each stated objective, ask *why is that important?* Two answer shapes are possible: the objective
is one of the essential reasons for caring about this situation at all — a **fundamental objective**;
or it is important *because* it advances some other objective — a **means objective**. Means
objectives are linked to each other and to fundamental objectives in a **means-ends objective
network** [1]. Fundamental objectives are arranged in a **fundamental objectives hierarchy**,
elaborated downwards by asking *what do you mean by that?* rather than *how could that be achieved?*
The UK Government Analysis Function guide states the practical consequence: criteria must reflect
"fundamental objectives to ensure all options can be fairly compared. This means they relate to
what is needed, rather than how to achieve it," and in a hierarchy "the 'child' objectives represent
the different cases where the 'parent' objective applies, rather than the ways the objective could be
achieved" [6].

**The procedure, written for a prompt:**

1. For each candidate criterion `C`, ask **"Why is that important — for this decision, for this
   decider?"** Record the answer as `parent`.
2. If `parent` is another candidate criterion or another objective already on the list, `C` is a
   **means** objective. Record the edge `C → parent` and do **not** promote `C` to a criterion.
3. If the answer is "it just is — it is one of the reasons this decision matters," `C` is
   **fundamental**. Stop laddering.
4. Repeat until every chain terminates. The chain lengths are usually 1–4.
5. For each fundamental objective, elaborate downwards with **"What do you mean by that, exactly?"**
   until each leaf can be judged for one alternative in isolation. **The leaves are the criteria.**
6. Emit both structures: the `objective_ladder` (edges `criterion → objective`, and
   `objective → objective`) and the `means_edges` (rejected means objectives and what they served).
   The rejected means objectives are *not* discarded silently — they become the `exclusions` text of
   the criteria they serve (see §6).

**REASONING, not evidence.** Emitting the ladder is the single cheapest structural win available.
Two criteria whose ladders meet at the same fundamental objective within one hop are double-counting
candidates by construction, and this is computable with no model call — a deterministic tool, in the
ADR-0003 sense.

#### 1c. The nine desirable properties of a fundamental objectives set

**EVIDENCE.** Keeney gives nine, verbatim (Keeney 1992, p. 92, quoted in an accessible secondary
source [21]; the list is reproduced here with Keeney's own gloss for each):

| # | Property | Keeney's gloss |
|---|---|---|
| 1 | **Essential** | "to indicate consequences in terms of the fundamental reasons for interest in the decision situation" |
| 2 | **Controllable** | "to address consequences that are influenced only by the choice of alternatives in the decision context" |
| 3 | **Complete** | "to include all fundamental aspects of the consequences of the decision alternatives" |
| 4 | **Measurable** | "to define objectives precisely and to specify the degrees to which objectives may be achieved" |
| 5 | **Operational** | "to render the collection of information required for an analysis reasonable considering the time and effort available" |
| 6 | **Decomposable** | "to allow the separate treatment of different objectives in the analysis" |
| 7 | **Nonredundant** | "to avoid double-counting of possible consequences" |
| 8 | **Concise** | "to reduce the number of objectives needed for the analysis of a decision" |
| 9 | **Understandable** | "to facilitate generation and communication of insights for guiding the decision making process" |

Two of these are underrated for our purposes. **Controllable** is the check nobody runs: a criterion
that measures something the choice among *these* alternatives cannot influence is a fact about the
world, not a column. **Measurable** is stated by Keeney as a property of *the objective*, not merely
of the scale — "to define objectives precisely" — which is the literature's own statement of the
brief's point that undefined criteria get scored inconsistently.

#### 1d. Attributes: natural, constructed, proxy, and the five properties of a good one

**EVIDENCE.** Keeney & Gregory 2005, abstract, verbatim: "The foundation for any decision is a clear
statement of objectives. Attributes clarify the meaning of each objective and are required to
measure the consequences of different alternatives. Unfortunately, insufficient thought typically is
given to the choice of attributes. […] **We define five desirable properties of attributes: they
should be unambiguous, comprehensive, direct, operational, and understandable.** […] We also present
a decision model for selecting among the different types of natural, proxy, and constructed
attributes." [3]

The three types, as standardly defined [1][3]: a **natural** attribute is in general use and directly
measures the objective (annual cost in currency); a **constructed** attribute is built for this
decision, typically an ordered set of described levels; a **proxy** attribute measures something
correlated with the objective but not the objective itself. The recommended order is natural →
constructed → proxy: "If neither good natural attributes nor good constructed attributes are
available, then a proxy attribute should be chosen." (That sentence is from the body of [3], which is
paywalled — **UNVERIFIED**; the abstract quoted above *is* verified.)

**This maps directly onto our schema.** A `constructed` attribute *is* an anchored ordinal scale with
per-level descriptors — which is exactly what the rubric literature independently says produces
consistent scoring (§6). And `proxy` is the type that most needs a stated `evidence_rule`, because a
proxy is the case where a reader can most easily mistake the measure for the objective.

---

### 2. PrOACT, consequence tables and even swaps — confirm the frame, correct the source claim

**EVIDENCE.** PrOACT is **Pr**oblem, **O**bjectives, **A**lternatives, **C**onsequences,
**T**rade-offs. It is the framing device of *Smart Choices* (1999) [25]; it is **not** from the 1998
HBR even-swaps article [8], which predates the acronym and presents even swaps and the consequence
table only. The **consequence table** lists alternatives against objectives with the consequences
stated "using consistent terms" for each objective; its stated function is that it "makes all the
information visible simultaneously, preventing important information from being overlooked and
trade-offs from being made haphazardly" [8] **(UNVERIFIED — the HBR full text is paywalled; these
two fragments could not be checked against the source in this pass)**. In comparanda's vocabulary the consequence table
*is* the matrix — comparanda's own terminology research already records "consequence table" as the
decision-analysis name for it.

**EVIDENCE — the even swaps algorithm**, quoted from the clearest formal statement [7] **(UNVERIFIED
— [7] is paywalled and the quoted wording could not be checked against the source in this pass; the
reference itself is confirmed)**: "In an even
swap, the DM changes the consequence of an alternative on one attribute, and compensates this change
with a preferentially equal change in the consequence of another attribute. This creates a new
virtual alternative with revised consequences." The process aims "to carry out even swaps that either
make attributes irrelevant or alternatives dominated. **An attribute is irrelevant if all the
alternatives have equal consequences on this attribute. Alternative x dominates alternative y if x is
better than or equal to y on every attribute and better at least on one attribute.** Irrelevant
attributes and dominated alternatives can both be eliminated, and the process continues until only
the most preferred alternative remains." Plus **practical dominance**: "Alternative x practically
dominates alternative y if y is slightly better than x on only one or few attributes but x clearly
outranks y on several other attributes."

**Verdict on the brief's claim.** *Smart Choices* is the best single source for the **pipeline**, and
ADR-0005 is already that pipeline: Frame ≈ Problem, Enumerate alternatives ≈ Alternatives, Propose
criteria ≈ Objectives, Populate ≈ Consequences, plus a confirmation checkpoint and a review stage
that PrOACT does not have and should. It is **not** the best source for the `propose-criteria` prompt
itself: even swaps is a trade-off elicitation method operating on an already-populated consequence
table, and trade-offs are precisely what `rubricator` hands back to the user rather than resolving
(comparanda ADR-0015). **Recommendation: keep PrOACT as the stage frame; take one thing from the
consequence-table discipline into `propose-criteria` — that every criterion must be expressible "using
consistent terms" across every alternative, which is the operationality check in its most usable
form; leave even swaps out of v1.**

**REASONING, not evidence.** Two even-swaps primitives nonetheless earn their place. *Irrelevance*
has a **pre-scoring** analogue that DCLG states as a redundancy check: "The MCA team may also wish to
delete a criterion if it seems that all the available options are likely to achieve the same level of
performance when assessed against it" — with the manual's own caveat that "omission on these grounds
should be approached with care" because nothing has been scored yet and new alternatives may arrive
[5, §5.4.4.2]. So: **flag, propose, never auto-delete.** *Dominance* is already comparanda's
(ADR-0015) and needs nothing from us.

---

### 3. Criteria hygiene: provenance of the properties, and a test for each

#### Provenance

**EVIDENCE.** The lineage runs: Keeney & Raiffa 1976 [4] → Keeney 1992 (the nine properties above)
[1] → Keeney & Gregory 2005 (the five *attribute* properties) [3], with a parallel European tradition
in Roy's **coherent family of criteria** — exhaustive, cohesive, and non-redundant [12] — and an
operational restatement in the DCLG manual's seven checks [5, §5.4.4] and the ISPOR MCDA task-force
report [11].

**Two honest caveats.** (a) The specific five-item list often attributed to Keeney & Raiffa 1976
(complete, operational, decomposable, non-redundant, minimum size) is widely repeated but I could
**not verify it verbatim against the primary text** in this pass — the book is not openly available.
Treat the *verified* Keeney 1992 nine and Keeney & Gregory 2005 five as the citable lists. (b) I
found no evidence that von Winterfeldt & Edwards originate any of these properties; the brief's
suggestion that they might is **not supported by anything I could verify**, and the claim should be
dropped rather than repeated.

#### The testable checklist

The DCLG manual is the source to lift from, because unlike the others it states each check as a
question a practitioner asks. Its seven are Completeness, Redundancy, Operationality, Mutual
independence of preferences, Double counting, Size, and Impacts over time [5, §5.4.4]. Merged with
Keeney's nine, here is the implementable set. Every test in the **Pre-scoring test** column runs with
no cell scored.

| Property | Source | Pre-scoring test | Action on failure |
|---|---|---|---|
| **Essential** | Keeney 1992 [1] | Does any alternative plausibly differ on this? Is it one of the reasons the decider cares? | Demote to context note, or merge |
| **Controllable** | Keeney 1992 [1] | Is this influenced by the choice among *these* alternatives, or by the world regardless? | Demote to a stated assumption of the frame |
| **Complete** | Keeney 1992 [1], DCLG 5.4.4.1 [5] | Three questions, verbatim from DCLG: "Have we overlooked any major category of performance?"; "With regard to this area of concern, have we included all the criteria necessary to compare the options' performance?"; "Do the criteria capture all the key aspects of the objectives that are the point of the MCA?" | Add criterion, or record the gap explicitly |
| **Measurable** | Keeney 1992 [1] | Does the criterion carry a scale whose levels are described in observable terms? | Blocking — write the anchors (§6) |
| **Operational** | Keeney 1992 [1], DCLG 5.4.4.3 [5] | DCLG, verbatim: "Is it possible in practice to measure or judge how well an option performs on these criteria?" And: "the criterion must be defined clearly enough to be assessed." | Decompose into sub-criteria, or accept a high `missing` rate and say so up front |
| **Decomposable** | Keeney 1992 [1] | Can one alternative be judged on this criterion **without reading any other column**? | Blocking — see §4 |
| **Nonredundant** | Keeney 1992 [1], Roy [12], DCLG 5.4.4.2/5.4.4.5 [5] | The overlap battery of §4 | Merge, or add mutual `exclusions` text |
| **Concise / Size** | Keeney 1992 [1], DCLG 5.4.4.6 [5] | Count leaves; check group sizes | Group (§5) — do not cut silently |
| **Understandable** | Keeney 1992 [1] | Can a second reader restate the criterion and predict which of two described alternatives scores higher? | Rewrite the definition |
| **Preference direction unambiguous** | DCLG 7.3.4.7 [5] | Is `preference` one of increasing / decreasing / target / ordered — and is it *stable* across the whole range? | Blocking — see the percentage trap below |
| **Preferentially independent** | Keeney & Raiffa [4], DCLG 5.4.4.4 [5], ISPOR [11] | The indifference probe of §4 | Merge, add a veto threshold, or declare the set non-additive |

**EVIDENCE — the percentage trap**, worth encoding as a lint rule because an LLM will walk into it:
"Care must attend the use of percentages in any MCDA for if both numerator and denominator can
change, preferences may be undefined. […] Preference may also be undefined for a criterion that
captures the percent change in some quantity when the base is different from one option to the next.
In general, criteria should be operationalised with measures for which the direction of preference is
unambiguous." [5, §7.3.4.7]

**EVIDENCE — veto thresholds are a hygiene instrument, not just a user preference.** DCLG gives the
minimum-acceptable-level device as one of two repairs when preferential independence fails: "options
often have to satisfy a minimum acceptable level of performance for them to be considered; options
falling below any minimum level are rejected outright because better performance on other criteria
can't compensate. **This hurdle usually guarantees preference independence of the criteria**" [5,
§5.4.4.4]. This is a stronger justification for comparanda's veto screening (ADR-0015) than "it
matches ELECTRE" — vetoes *repair* an otherwise-broken additive frame. The other repair is to merge
the two dependent criteria into one "which captures the common dimension of value" [5, §5.4.4.4].

---

### 4. Detecting overlapping criteria — before scoring

This is the question the brief is most right to single out, and the literature answers it better than
expected. Four tests, in increasing cost. Run them in this order.

#### 4a. The structural test — free, deterministic, no model call

**REASONING (grounded in EVIDENCE).** The overlap defect has a small number of recurring shapes. Six
patterns, each with a source:

| Pattern | Signature | Source |
|---|---|---|
| **Means/end** | A is a way of achieving B; both are columns | WITI test, Keeney [1] — this is what `nonredundant` "avoid double-counting" means |
| **Composite/component** | C is a function of A and B; A and B are also columns | ISPOR: "including cost-effectiveness as a criterion alongside cost and/or effectiveness criteria" [11] |
| **Causal** | A causes B; both scored | ISPOR: "discontinuation events and safety events in the same analysis, if discontinuation events may be caused by the safety events" [11] |
| **Nested scale** | Two cut-points on the same underlying quantity | ISPOR: two response scales where one "would double count the patients achieving a 20% improvement" [11] |
| **Synonym** | Different words, same value dimension | DCLG: "if two criteria really mean the same thing, but have been described in a way that apparently is different" [5, §6.2.12]; 1000minds' worked example is having both "attractiveness" and "beauty" as car criteria [10] |
| **Bundled** (the dual defect) | *One* criterion conflating two value dimensions | RRD: LLM-generated rubrics "conflate dimensions" [15] |

Patterns 1 and 2 are detectable purely from the objective ladder emitted in §1b, with no inference:
flag any pair of criteria where one appears on the other's ladder, or where two ladders converge on a
common objective within one hop. Pattern 6 is the inverse failure — under-decomposition — and its fix
is RRD's decompose-then-filter cycle [15], not a merge.

#### 4b. The conceptual test — the indifference probe

This is the sharpest single item in the whole literature and it is directly promptable. DCLG's worked
version, verbatim [5, §5.4.4.5] (their pharmaceutical example):

> "A good test is to ask the following question: 'Two compounds, A and B, will cost the same to
> develop, are expected to yield the same financial return, and are identical on all other criteria
> except that A meets a greater unmet medical need than B. Do you prefer A or B, or are you
> indifferent?' If the answer is a preference for A, then there must be more to the value associated
> with A than its expected commercial value. Exploring the reasons for the preference will uncover
> additional criteria."

Generalised template, for a public, self-explanatory domain (choosing a programming language for a
new service; candidate overlap between *ecosystem maturity* and *hiring pool*):

> Consider two hypothetical languages, P and Q. They are identical on every criterion except
> **ecosystem maturity**. On **hiring pool**, both sit at exactly the same level: about the same
> number of available engineers, at the same salary. On **ecosystem maturity**, P has mature
> libraries for everything we need and Q does not. Do you prefer P, prefer Q, or are you indifferent?

If the answer is **indifferent**, *ecosystem maturity* carries no value beyond *hiring pool* in this
decision, and the two should be merged. If the answer is a **preference**, they express separate
aspects of value — and the *reason given* is exactly the text that belongs in both criteria's
`exclusions` fields.

**Two procedural details that are easy to get wrong.** (i) **Run it in both directions.** DCLG's
glossary is explicit: "Mutual independence of preferences needs to be checked in both directions. For
example, in choosing the best meal option from a menu, the relative preferences for main dishes are
usually independent of the diner's preferences for wine, but the relative preferences for wine are
often not independent of the preferences for main dishes, so mutual independence fails." [5,
glossary] (ii) **Route the probe to the human at the ADR-0005 step-4 checkpoint**, not only to the
model. The probe interrogates a *value function*; the value function that matters is the user's. The
model's answer is a useful pre-filter that decides which probes are worth a human's attention, and
nothing more (REASONING).

#### 4c. The self-report probe — cheap, and currently unexploited

**EVIDENCE.** DCLG describes how preference dependence is usually caught in practice: "Failure of
mutual preference independence, if it hasn't been caught when the criteria are being formed, usually
is discovered when scoring the options. **If the assessor says that he or she can't judge the
preference scores on one criterion without knowing the scores on another criterion, then preference
dependence has been detected.** This often happens because of double counting […] when the scores are
elicited the assessor will often refer back to the first criterion when assessing the second. That is
a signal to find a way to combine the two criteria into just one that covers both meanings." [5,
§6.2.12] The UK guide says the same from the other side: "Do not ignore a stakeholder's reluctance to
offer a preference judgement, especially if they say 'it depends' on another criterion." [6]

**REASONING.** This is trivially operationalisable in an LLM pipeline and nobody does it: make the
"it depends" response a **first-class emittable outcome** of the scoring prompt. Add to `score-cell`
a required field `depends_on: CriterionId[]` — "which other criteria, if any, you had to consult to
answer this." A non-empty value is a preference-dependence signal against the criterion pair, and it
costs zero extra calls. It also converts a failure the model would otherwise commit silently into a
declared one, which is the same move ADR-0006 makes for evidence.

#### 4d. The computable pre-scoring test — synthetic probes

**EVIDENCE.** There is now a published method that does exactly what the brief asks for: a redundancy
test that runs **before** the real matrix is scored. RADAR [14], abstract verbatim: "Rubric-based
LLM-as-judge pipelines often assume that evaluation criteria provide independent signals. In
practice, however, criteria can be behaviorally coupled: improving one criterion may systematically
change scores on another, distorting aggregate scores […] We introduce RADAR, a lightweight preflight
diagnostic framework for estimating such coupling before large-scale evaluation. **Given a rubric,
RADAR generates targeted synthetic probes, scores each probe on all criteria, and produces a
directional coupling matrix that shows which criteria co-score and how.** […] Using only a small
number of probes per criterion, RADAR recovers human inter-criterion correlation structure (Pearson
r > 0.84) and provides practitioners with concrete audit signals about redundancy, hierarchy, and
aggregation sensitivity before committing to large-scale judging."

Adapted for `rubricator`: for each criterion `k`, generate 3 **synthetic alternatives** that differ
from a neutral baseline **only** on `k` (one high, one low, one mid), score all `n` criteria on each
probe, and compute the directional matrix `M[j][k]` = how much criterion `j`'s score moves when only
`k` is varied. Off-diagonal mass is coupling. This is *pre-scoring* in the sense that matters: no real
alternative and no real document is involved, so it can run the moment the criteria set exists.

**This is the textbook ADR-0003 shape and should be built as the worked example of it.** Probe
generation and probe scoring are inference; the coupling computation and the flagging are arithmetic.
So: two prompts (`generate-coupling-probes`, `score-coupling-probes`) plus one deterministic tool
(`compute_coupling_matrix`) that takes the probe scores as input and emits flags. **No tool requires a
model** — the connector runtime survives.

Cost is real: `3 × n` probes × `n` criteria scored = `3n²` judgements. At `n = 8` that is 192
single-criterion calls. Make it **opt-in**, and default it on only when the structural and
indifference tests have already flagged something.

#### 4e. Why the obvious test — correlating scored columns — is wrong

**EVIDENCE, and this is the most load-bearing negative finding in the section.** Two independent
reasons.

*Reason one: correlation is not redundancy, and the manual says so with a worked counterexample.*
DCLG, glossary, verbatim: "**Mutual preference independence can hold even when options are correlated
in their measures on real-world criteria provided that the criteria express separate aspects of
value.**" [5] Their pharmaceutical case makes it concrete: commercial value and unmet medical need are
strongly correlated across compounds, and are nonetheless separate criteria, because a decider who is
indifferent on return still prefers the compound that meets greater need. The manual's conclusion:
"a judgement about double counting cannot be made on an objective basis. It is necessary to
understand the values that the organisation brings to the appraisal." [5, §5.4.4.5]

*Reason two: for an LLM-scored matrix, observed column correlation measures the rater, not the
criteria.* When GPT-4 scores the four SummEval attributes in one generation, the consistency score is
strongly conditioned on the coherence score emitted just before it: "Human scores are correlated by
Pearson's r = 0.315, while GPT-4 scores are correlated by r = 0.979" [17, Fig. 4]. **Scope that
honestly** — it is one attribute pair in one dataset, not a general inter-criterion figure; what
generalises is the direction and the order of magnitude, not the constant. Rubric interference is the
same effect measured from the other side: a verdict on one criterion "shifts depending on which other
rubrics are co-present," and under rubric-set expansion, subsetting, reordering and noise injection
"only one-third of samples receive fully consistent verdicts" [16]. So a
correlation computed over an LLM-scored matrix is confounded with the judge's own halo by an amount
larger than the signal being looked for. The synthetic-probe design avoids the confound by
construction: it *varies one criterion and holds the rest fixed*, so co-movement is attributable.

**REASONING.** Post-hoc column correlation is still worth **reporting** in the review stage
(ADR-0005 step 6) as a *diagnostic of the scoring run* — an unexpectedly high value is evidence that
the traversal leaked context between cells, which is an ADR-0008 stability concern — but it must
never be labelled a redundancy finding.

#### 4f. An LLM will in fact reproduce this defect — it is measured

**EVIDENCE.** The brief predicted this; it is now documented. RRD [15]: "rubric generation remains
hard to control: rubrics often lack coverage, **conflate dimensions**, misalign preference direction,
and **contain redundant or highly correlated criteria, degrading judge accuracy** and producing
suboptimal rewards." Their fix — a recursive decompose-then-filter cycle, where filtering "removes
misaligned and redundant rubrics" and a correlation-aware weighting scheme "prevents
over-representing highly correlated criteria" — improved preference-judgment accuracy by up to
**+17.7 points on JudgeBench** for GPT-4o and Llama3.1-405B judges. Note that three of their four
named failure modes are on our checklist already (coverage = completeness; conflate dimensions =
bundling; misaligned preference direction = the polarity check), which is a satisfying convergence
between the 1976 decision-analysis literature and 2026 LLM evaluation practice.

---

### 5. How many criteria before the matrix stops being usable

#### What is actually known

**EVIDENCE — the practitioner numbers.** Three independent sources, converging:

- DCLG, verbatim: "The number of criteria should be kept as low as is consistent with making a
  well-founded decision. **There is no 'rule' to guide this judgement** and it will certainly vary
  from application to application. Large, financially or otherwise important choices with complex
  technical features (such as a decision on where to locate a nuclear waste facility) may well have
  upwards of a hundred criteria. **More typical, however, is a range from six to twenty.**" [5,
  §5.4.2] And on grouping: it is "particularly helpful if the emerging decision structure contains a
  relatively large number of criteria (**say eight or more**)." [5, §5.4.3]
- UK Government Analysis Function, verbatim: "**If there are more than around seven, consider
  producing a hierarchy of objectives or criteria.**" [6]
- 1000minds, verbatim: "For most applications, **fewer than a dozen criteria is usually sufficient,
  with 5-8 fairly typical.**" [10]

**EVIDENCE — Miller is folklore here, and should be dropped from the reasoning.** Miller 1956 is
about immediate memory span and absolute-judgement channel capacity for unidimensional stimuli [9];
Cowan's reconsideration puts the pure capacity limit nearer four [18]. Neither studies a *visible*
matrix, which is not a memory task at all. **REASONING:** cite the MCDA practitioner range on its own
authority; invoking 7±2 as its justification is a citation that does not support the claim, which is
exactly the failure mode both repos exist to prevent.

**EVIDENCE — the real reason to care, and it is not legibility.** Splitting bias. Weber, Eisenführ &
von Winterfeldt 1988, abstract verbatim: "This study examined how weights in multiattribute utility
measurement change when objectives are split into more detailed levels. Subjects were asked to weight
attributes in value trees containing three objectives which were specified by either three, four,
five, or six attributes. **The robust finding was that the more detailed parts of the value tree were
weighted significantly higher than the less detailed ones.** This overweighting bias was found for
several weighting techniques […]" [22] Jacobi & Hobbs 2007 explain it as anchor-and-adjust — the
subject "starts with an equal allocation of weight among attributes in each tree partition and then
adjusts the weights to reflect his or her innate preferences", and "[a]djustments tend to be
insufficient" — and show it changes rankings [23]. Rezaei et al. 2022 confirm a related family
effect — *equalizing* bias, the tendency to assign equal weights — across AHP, BWM, PA, SMART and
Swing, and find that "hierarchical problem structuring leads to a reduction in the equalizing bias in
all five methods" [24]. (Equalizing bias is not splitting bias; [24] is corroborating evidence for
hierarchical structuring as a debiaser, not a replication of [22].) DCLG's own field case observes it
live: "only two criteria fell under the node whose weight was increased, while six criteria fell
under the node whose weight was decreased, **illustrating the effect of just the number of criteria
under a node**." [5, §7.4.5 — the Nirex site-appraisal case study]

**The implication is the important part (REASONING, well grounded).** The number of criteria in a
group is *itself a smuggled value judgement*: splitting one objective into four columns silently
raises its importance relative to an objective left as one column. This means:

1. `rubricator` must **report group sizes**, not just the total count — an imbalanced tree is a
   finding, and it belongs in the ADR-0005 step-6 review.
2. Grouping is the **correct** response to too many criteria, both because it is the response the
   evidence supports as a debiaser — hierarchical structuring reduced weighting bias in all five
   methods tested [24] — and because deleting a criterion destroys information. ("Only one that
   works" would overstate [24]: no study compared grouping against deletion.)
3. Any weighting the user later applies in comparanda inherits this bias, so the warning belongs in
   the analysis output, not only in the agent's head.

**EVIDENCE — the LLM-side limit is a different limit, and must not be confused with this one.** More
criteria in a *single call* degrades LLM judgement: rubric interference shifts verdicts as co-present
criteria change, and only about a third of samples keep fully consistent verdicts across varying
rubric-set composition [16]; the companion research in this
repo records the same from the batching literature. But the recommended traversal for `rubricator` is
**one criterion per call** (see the sibling section on scoring order), so criteria-per-call is 1 by
construction and the LLM limit does not constrain matrix width at all. **Do not cap the matrix for
LLM reasons.** The binding constraints are human legibility and splitting bias.

#### The recommendation

| Threshold | Value | Behaviour |
|---|---|---|
| `CRITERIA_TARGET_RANGE` | 5–9 leaves | No action |
| `CRITERIA_WARN_UNGROUPED` | > 7 with no groups | Warn; propose a grouping in the step-4 confirmation |
| `CRITERIA_REQUIRE_GROUPS` | > 9 | Emit a proposed grouping as part of the criteria set; the user may reject it |
| `CRITERIA_HARD_CAP` | > 15 without groups | Refuse to proceed to scoring without an explicit user override; state why |
| `GROUP_SIZE_RANGE` | 2–7 per group | Report every group size and flag imbalance ≥ 3× between sibling groups |

**Never silently drop a criterion.** ADR-0006's rule applies one level up: a criterion that
`rubricator` proposes and then removes is recorded with a reason (`merged-into`, `means-objective`,
`not-controllable`, `no-discrimination-expected`, `user-rejected`). The removed set ships with the
analysis. A criteria set with no visible rejects is a criteria set nobody interrogated.

---

### 6. Definitions: why undefined criteria score inconsistently, and what a definition must contain

**EVIDENCE.** The clearest empirical statement comes from educational assessment, not decision
analysis. Jonsson & Svingby 2007 reviewed 75 empirical studies and concluded: "**the
reliable scoring of performance assessments can be enhanced by the use of rubrics, especially if they
are analytic, topic-specific, and complemented with exemplars and/or rater training**" [19]
**(UNVERIFIED — [19] is paywalled; the reference resolves and its metadata is confirmed, but neither
the study count nor the wording of this sentence could be checked against the source in this pass)**.
All three
qualifiers matter for us, and each has a design consequence:

- **analytic** (score each criterion on its own scale, rather than holistically) → one anchored scale
  per criterion, never a shared generic 1–5;
- **topic-specific** (written for *this* assessment, not reusable boilerplate) → generic level
  descriptors like "excellent / good / fair" are a known reliability loss, not a stylistic choice;
- **exemplars** → the level descriptors must be *observable conditions*, and where possible each
  should name a concrete case.

This lines up exactly with Keeney's **measurable** ("to define objectives precisely and to specify
the degrees to which objectives may be achieved") [1], with Keeney & Gregory's **unambiguous** [3],
and with DCLG's "the criterion must be defined clearly enough to be assessed" [5, §5.4.4.3].

#### The minimum contents of a scoreable criterion definition

Required (a criterion missing any of these is not scoreable and `propose-criteria` must not emit it):

| Field | What it is | Source of the requirement |
|---|---|---|
| `id`, `name` | Stable identifier and a short noun phrase | — |
| `objective` | The fundamental objective it measures, phrased as an objective ("minimise time-to-first-deploy"). The top of the WITI ladder. | Keeney [1] |
| `question` | The single question a scorer answers about **one** alternative, phrased so it is answerable without reading any other column | Keeney *decomposable* [1]; DCLG operationality [5] |
| `level` | nominal / ordinal / interval / ratio | comparanda ADR-0003 |
| `preference` | increasing / decreasing / target / ordered / none — stable across the whole range | DCLG §7.3.4.7 [5]; comparanda |
| `attribute_type` | `natural` \| `constructed` \| `proxy`, and `proxy_of` when proxy | Keeney & Gregory [3] |
| `scale` | For ordinal: one descriptor per level, each an **observable condition**, no bare value words | Jonsson & Svingby [19]; Keeney *measurable* [1] |
| `evidence_rule` | What counts as support for a score on this criterion, and what does not | ADR-0006 |
| `missing_rule` | The condition under which the correct answer is a qualified `unknown` rather than a score | ADR-0006 (see below) |
| `exclusions` | What this criterion explicitly does **not** cover, naming the sibling criteria it is most likely to be confused with | DCLG double counting [5]; §4b output |

Optional: `veto` (threshold + reason), `group`, `provenance` (user-stated / derived-from-span /
agent-proposed — ADR-0006's source-type distinction applies to criteria as much as to cells).

**`missing_rule` is our own addition and it matters (REASONING, motivated by ADR-0006 and [19]).** The
rubric literature's finding is that reliability comes from making expectations explicit. ADR-0006's
central behaviour — prefer a qualified blank to a confident guess — is an expectation, and a criterion
definition that never states *when to give up* leaves that expectation implicit, which is precisely
the condition under which it erodes. Concretely: "score `unknown` if no source states the deployment
target explicitly; do not infer it from the presence of a Dockerfile."

#### Worked example (public domain, self-explanatory)

```yaml
id: ecosystem-maturity
name: Ecosystem maturity
objective: Minimise the amount of infrastructure we have to build ourselves
question: >
  For the libraries this service needs — HTTP server, database driver, background jobs,
  observability — how much of that is available as a maintained third-party library?
level: ordinal
preference: { kind: increasing }
attribute_type: constructed
scale:
  5: All four needs met by libraries with a release in the last 6 months and >1 maintainer.
  4: All four met; at least one is single-maintainer or last released 6-18 months ago.
  3: Three of four met by maintained libraries; one would have to be built.
  2: Two of four met; two would have to be built.
  1: One or none met.
evidence_rule: >
  A package registry entry showing the last release date, or the library's own repository.
  A blog post asserting that "the ecosystem is mature" is a secondary summary, not support.
missing_rule: >
  If the source set does not enumerate this service's actual library needs, score `unknown`.
  Do not substitute a general impression of the language's popularity.
exclusions: >
  Does NOT cover how many engineers we can hire (see `hiring-pool`), and does NOT cover
  runtime performance (see `throughput`). A large ecosystem with a small hiring pool
  scores high here and low there; we confirmed that trade-off matters (indifference probe, 2026-08-18).
```

Note the last line: the `exclusions` field records the *outcome of the indifference probe*, with a
date. That is what makes a merge decision auditable a month later.

---

### 7. VFT versus criteria drift — and why ADR-0005 needs a small change

**EVIDENCE.** Shankar et al. 2024, abstract verbatim: "we identify a phenomenon we dub *criteria
drift*: **users need criteria to grade outputs, but grading outputs helps users define criteria.**
What is more, some criteria appears *dependent* on the specific LLM outputs observed (rather than
independent criteria that can be defined *a priori*), **raising serious questions for approaches that
assume the independence of evaluation from observation of model outputs.**" [13]

Read naively this contradicts value-focused thinking, which says do not let the alternatives in front
of you determine your criteria. It does not. **REASONING:** VFT forbids *deriving* the criteria set's
*structure* from the alternatives; it explicitly endorses using alternatives as *stimuli* for
surfacing values — Keeney's own generation devices include "alternatives that are particularly good
or particularly bad, and what makes them good or bad" [1, via 20]. Criteria drift is an empirical
observation about *when* people can articulate what they value, not a claim about where value comes
from. The two are compatible, and the synthesis is a three-move design:

1. **Generate from objectives** (VFT), before looking closely at the alternatives' details.
2. **Stress-test against the alternatives** — the `essential` and `controllable` checks require them,
   and Keeney's good/bad-alternative device uses them productively.
3. **Allow revision after scoring begins** (criteria drift), with explicit invalidation.

Move 3 is what ADR-0005 does not currently provide for. Its step 4 reads as a one-way gate. What is
needed is small but architecturally real: when a criterion's `question`, `scale`, `preference` or
`exclusions` changes after cells have been scored against it, **every cell scored under the old
definition must be invalidated** — set to `missing` with reason `not-assessed` and a note naming the
definition version — rather than silently retained. A criteria set therefore needs a **version**, and
every measure needs to record the criterion version it was scored against. Without this, criteria
drift produces a matrix whose columns were scored against different rubrics, which is the
worst-of-both outcome and completely invisible in the output.

---

## What this means for the schema / the view / the agent

### The `propose-criteria` prompt — what it must PRODUCE

Ten phases, in order. Phases A–E are inference; F–I are checks the model runs and a deterministic
tool verifies.

| Phase | Job | Output |
|---|---|---|
| **A. Restate** | Restate the subject, the decision and the decider from the frame stage; name any ambiguity rather than resolving it | `frame_restatement`, `open_questions[]` |
| **B. Generate objectives** | "What would distinguish between a good choice and a bad one here?" [5], then Keeney's devices: wish list; a particularly good and a particularly bad alternative and what makes them so; shortcomings of the status quo; role-played stakeholder perspectives [1] | `candidate_objectives[]`, each with `source_device` |
| **C. Ladder** | WITI on every candidate: *why is that important?* Classify means vs fundamental. Elaborate fundamentals downwards with *what do you mean by that?* | `objective_ladder` (edges), `means_edges[]` |
| **D. Prune** | Leaves of the fundamental hierarchy become criteria. Means objectives are **not** promoted; they are recorded and become `exclusions` text | `criteria[]`, `rejected[]` with reason codes |
| **E. Attribute** | Per criterion, choose natural → constructed → proxy, in that order [3]; write the full definition of §6 | Each criterion fully populated |
| **F. Hygiene** | The eleven checks of §3, each answered explicitly per criterion | `hygiene_report` |
| **G. Overlap** | Structural test (§4a) over all pairs; indifference probes (§4b) for every flagged pair, **run in both directions**; optionally coupling probes (§4d) | `overlap_findings[]` with `pattern`, `pair`, `probe`, `verdict` |
| **H. Size** | Count leaves; propose groups if over threshold; report group sizes and imbalance | `size_report`, `proposed_groups[]` |
| **I. Honesty** | State ADR-0006 in the prompt's own words. Name the criteria whose definitions are weakest and what would improve them | `weakest[]` |
| **J. Confirm** | Emit for the ADR-0005 step-4 checkpoint: criteria, definitions, overlaps found and their probes, rejects and why, groups, open questions — with the unresolved indifference probes surfaced as **questions for the user**, not decisions taken | The confirmation payload |

### The `propose-criteria` prompt — what it must CHECK

Deterministic, model-free, and therefore tools in the ADR-0003 sense:

- `validate_criteria_set(criteria) -> ValidationReport` — every required field of §6 present and
  well-typed; `level: nominal` with `preference: increasing|decreasing` rejected (comparanda's rule);
  ordinal scales have a descriptor for **every** level; `attribute_type: proxy` requires `proxy_of`;
  every criterion has a non-empty `missing_rule`.
- `check_ladder(ladder, criteria) -> LadderReport` — every criterion is a leaf of the fundamental
  hierarchy; no criterion appears on another criterion's ladder; report pairs converging on a common
  objective within one hop.
- `check_size(criteria, groups) -> SizeReport` — the thresholds of §5; group sizes and imbalance.
- `compute_coupling_matrix(probe_scores) -> CouplingReport` — arithmetic over probe scores supplied by
  the model; flags off-diagonal mass above `COUPLING_FLAG_THRESHOLD`.
- `lint_scale(criterion) -> Finding[]` — the percentage trap [5, §7.3.4.7]; bare value words
  ("excellent", "good") in level descriptors; descriptors that are not observable conditions.

Prompts that pair with them, because they need inference and therefore cannot be tools:
`generate-coupling-probes`, `score-coupling-probes`, `indifference-probe`.

**Named thresholds, all keyword-only config with these defaults, none hardcoded:**
`CRITERIA_TARGET_RANGE = (5, 9)`; `CRITERIA_WARN_UNGROUPED = 7`; `CRITERIA_REQUIRE_GROUPS = 10`;
`CRITERIA_HARD_CAP = 15`; `GROUP_SIZE_RANGE = (2, 7)`; `GROUP_IMBALANCE_RATIO = 3.0`;
`PROBE_COUNT_PER_CRITERION = 3`; `COUPLING_FLAG_THRESHOLD = 0.7`. The last is **REASONING, not
evidence** — RADAR reports recovery quality, not an operating threshold — so it must be tuned by the
ADR-0008 evaluation suite rather than trusted.

### Schema asks for comparanda

Four, in descending order of importance. None are breaking.

1. **A criterion carries a structured `definition`, not free text** — the ten required fields of §6.
   Today the domain model gives criteria a level of measurement and (from comparanda's own
   terminology research) a `preference`; it does not give them a `question`, `scale` anchors,
   `evidence_rule`, `missing_rule` or `exclusions`. Without those the honesty guarantee of ADR-0006
   is not expressible at the criterion level, only at the cell level, which is the wrong place —
   ADR-0006 behaviour is *defined* by the criterion and *exercised* by the cell.
2. **Criteria sets are versioned, and every measure records the criterion version it was scored
   against.** Required by §7. Cheap now, impossible to retrofit honestly later.
3. **A criterion carries `provenance`** — user-stated / derived-from-span / agent-proposed — the same
   three-way source-type distinction ADR-0006 already mandates for values. A criterion the agent
   invented and a criterion the user insisted on are different objects and a reader must be able to
   tell.
4. **Rejected criteria are part of the analysis**, with a reason code. This is the criteria-level
   application of comparanda's missingness discipline; `merged-into`, `means-objective`,
   `not-controllable`, `no-discrimination-expected`, `user-rejected` are the initial vocabulary.

### View asks for comparanda

The `objective_ladder` is worth rendering: a column header that can be expanded to show the objective
it serves and the criteria it was distinguished from is the cheapest available defence against a
reader silently re-interpreting a criterion. And group sizes should be *visible* in the header,
because splitting bias is invisible otherwise.

### Agent behaviour to hold

- `score-cell` gains a required `depends_on: CriterionId[]` field (§4c). Non-empty is a
  preference-dependence signal and belongs in the ADR-0005 step-6 review.
- Post-hoc column correlation may be **reported** as a scoring-run diagnostic and must **never** be
  labelled a redundancy finding (§4e).
- Every unresolved indifference probe goes to the user as a question at step 4, never resolved
  silently by the model.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0005 | confirm | Its six stages are PrOACT plus a checkpoint and a review; the decision-analysis literature independently arrives at the same order, including the objectives-before-alternatives rule the DCLG manual attributes to Keeney [1][5][7]. |
| ADR-0003 | confirm | The coupling-probe design is the canonical prompt + deterministic-tool split: probe generation and probe scoring are prompts, `compute_coupling_matrix` is arithmetic. No criteria-hygiene check needs a model inside a tool. |
| ADR-0006 | confirm | Extends cleanly one level up: rejected criteria are qualified missings with reason codes, and `missing_rule` moves the honesty guarantee into the criterion definition where it can actually be tested. |
| new ADR (0009) | new ADR | **Criteria are revisable; the step-4 checkpoint is a gate, not a one-way door.** Criteria drift is documented [13]; ADR-0005 reads as linear. Needs: criteria-set versioning, per-measure record of the criterion version scored against, and mandatory invalidation of cells scored under a changed definition. Cannot be an edit — ADR-0001 makes accepted ADRs immutable. |

---

## Open questions

- **Matrix usability as a function of criteria count has not been measured.** The 5–9 target is
  practitioner convergence across three sources [5][6][10] plus the splitting-bias literature
  [22][23][24]; no study measures reader comprehension or decision quality against column count.
  What would settle it: an ADR-0008 fixture family at n = 5, 9, 15, 25 with the same underlying
  content, and a human read-and-answer task.
- **Whether synthetic coupling probes work when alternatives are documents.** RADAR's probes are
  generated *responses* [14]; our alternatives are real things described by real sources, and the
  probes would be described alternatives with no evidence behind them. Whether coupling measured on
  evidence-free probes predicts coupling on evidence-backed cells is untested. What would settle it:
  run both on one fixture and correlate.
- **Whether a model interrogating its own value function via the indifference probe has any
  validity.** The probe asks about preferences; the preferences that matter are the user's. The
  recommendation above (model as pre-filter, human decides) is a hedge, not an answer. What would
  settle it: agreement between model probe verdicts and user probe verdicts across a fixture set —
  a straightforward ADR-0008 addition.
- **Keeney & Raiffa 1976's exact list of desirable properties of an attribute set** could not be
  verified against the primary text (the book is not openly available). The 1992 nine and the 2005
  five are verified and sufficient; if the 1976 five are wanted verbatim, someone with library access
  should check §2.4 rather than repeat the secondary attributions.
- **ISPOR Report 2's full criteria checklist** was reachable only through search snippets; the full
  text was not retrievable in this pass. The three overlap examples quoted in §4a come from those
  snippets and are attributed to [11]; the report's complete good-practice checklist should be read
  directly before the prompt is finalised.
- **Four sources are cited from behind a paywall and their quoted wording is unverified**: [7]
  (even-swaps definitions, §2), [8] (consequence-table fragments, §2), [19] (the rubric-reliability
  conclusion and the "75 studies" count, §6), and the Keeney & Gregory body sentence on the
  natural → constructed → proxy ordering (§1d; the *abstract* of [3] is verified). Their bibliographic
  metadata is confirmed via Crossref, so the references resolve — but the quotations should be
  checked against the primary texts by someone with library access before this section is treated as
  citable. Everything quoted from [5], [6], [10], [13], [14], [15], [16], [17], [20], [21], [22],
  [23] and [24] **was** verified against the source in this pass.

---

## REFERENCES

1. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985) — the nine desirable properties are at p. 92; the verbatim list used here was verified via the accessible secondary source [21].
2. [Value-focused thinking: Identifying decision opportunities and creating alternatives — Keeney (1996), European Journal of Operational Research 92(3):537–549](https://doi.org/10.1016/0377-2217%2896%2900004-5) — background; not cited inline in this section.
3. [Selecting Attributes to Measure the Achievement of Objectives — Keeney & Gregory (2005), Operations Research 53(1):1–11](https://doi.org/10.1287/opre.1040.0158)
4. [Decisions with Multiple Objectives: Preferences and Value Tradeoffs — Keeney & Raiffa (1976; Cambridge University Press edition 1993)](https://doi.org/10.1017/CBO9781139174084)
5. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf) — all §5.4.x, §6.2.12, §7.3.4.7 and glossary quotations are verbatim from this PDF.
6. [An Introductory Guide to Multi-Criteria Decision Analysis (MCDA) — UK Government Analysis Function](https://analysisfunction.civilservice.gov.uk/policy-store/an-introductory-guide-to-mcda/)
7. [Smart-Swaps — A decision support system for multicriteria decision analysis with the even swaps method — Mustajoki & Hämäläinen (2007), Decision Support Systems 44(1):313–325](https://doi.org/10.1016/j.dss.2007.04.004) — the formal statement of even swaps, dominance, practical dominance and irrelevance quoted in §2. Metadata confirmed via Crossref; the article is paywalled and the **quoted wording was not verified against the source** in this pass.
8. [Even Swaps: A Rational Method for Making Trade-offs — Hammond, Keeney & Raiffa (1998), Harvard Business Review, March–April 1998](https://hbr.org/1998/03/even-swaps-a-rational-method-for-making-trade-offs) — the consequence table. Paywalled; the two consequence-table fragments quoted in §2 **were not verified against the source** in this pass. This article is **not** the source of PrOACT — see [25].
9. [The magical number seven, plus or minus two: Some limits on our capacity for processing information — Miller (1956), Psychological Review 63(2):81–97](https://doi.org/10.1037/h0043158)
10. [Multi-Criteria Decision Analysis (MCDA/MCDM) — 1000minds](https://www.1000minds.com/decision-making/what-is-mcdm-mcda)
11. [Multiple Criteria Decision Analysis for Health Care Decision Making—Emerging Good Practices: Report 2 of the ISPOR MCDA Emerging Good Practices Task Force — Marsh, IJzerman, Thokala, Baltussen et al. (2016), Value in Health 19(2):125–137](https://doi.org/10.1016/j.jval.2015.12.016) — quotations in §4a were obtained via search snippets; the full text was not retrievable in this pass.
12. [Multicriteria Methodology for Decision Aiding — Roy (1996), Springer](https://doi.org/10.1007/978-1-4757-2500-1) — the "coherent family of criteria" (exhaustivity, cohesiveness, non-redundancy). The three property names are widely attributed to this work but were **not verified against the primary text** in this pass.
13. [Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences — Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran & Arawjo (2024), arXiv:2404.12272 / UIST '24](https://arxiv.org/abs/2404.12272)
14. [RADAR: Rubric-Aware Dependency and Redundancy Analysis for LLM-as-Judge Evaluation — Singh, Davari & Mashhadi (2026), arXiv:2608.01810](https://arxiv.org/abs/2608.01810)
15. [Rethinking Rubric Generation for Improving LLM Judge and Reward Modeling for Open-Ended Tasks (RRD) — Shen, Qiu, Whitehouse, Alazraki, Goel, Barbieri, Willi, Mathur & Leontiadis (2026), arXiv:2602.05125](https://arxiv.org/abs/2602.05125)
16. [Mitigating Rubric Interference in LLM Judges via On-Policy Self-Distillation — Yu, Zhang, Mou, Zhang, Ye & Zhang (2026), arXiv:2608.14684](https://arxiv.org/abs/2608.14684)
17. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024), arXiv:2405.01724](https://arxiv.org/abs/2405.01724)
18. [The magical number 4 in short-term memory: A reconsideration of mental storage capacity — Cowan (2001), Behavioral and Brain Sciences 24(1):87–114](https://doi.org/10.1017/S0140525X01003922)
19. [The use of scoring rubrics: Reliability, validity and educational consequences — Jonsson & Svingby (2007), Educational Research Review 2(2):130–144](https://doi.org/10.1016/j.edurev.2007.05.002) — metadata confirmed via Crossref; paywalled, so the "75 studies" count and the conclusion sentence quoted in §6 **were not verified against the source** in this pass.
20. [Value-Focused Thinking: a chapter-by-chapter summary — LessWrong](https://www.lesswrong.com/posts/CQHZZWZt99An8fmpT/value-focused-thinking-a-chapter-by-chapter-summary) — secondary; used only for the verbatim objective-generation-device passage attributed to [1].
21. [Objective Organization — *Systemic Decision Making* (accessible excerpt)](https://ebrary.net/48868/economics/objective_organization) — secondary; the source through which Keeney's nine properties (1992, p. 92) were verified verbatim.
22. [The Effects of Splitting Attributes on Weights in Multiattribute Utility Measurement — Weber, Eisenführ & von Winterfeldt (1988), Management Science 34(4):431–445](https://doi.org/10.1287/mnsc.34.4.431)
23. [Quantifying and Mitigating the Splitting Bias and Other Value Tree-Induced Weighting Biases — Jacobi & Hobbs (2007), Decision Analysis 4(4):194–210](https://doi.org/10.1287/deca.1070.0100)
24. [Equalizing bias in eliciting attribute weights in multiattribute decision-making: experimental research — Rezaei, Arab & Mehregan (2022), Journal of Behavioral Decision Making 35(2)](https://doi.org/10.1002/bdm.2262) — studies *equalizing* bias, not splitting bias; see the caveat in §5.
25. [Smart Choices: A Practical Guide to Making Better Decisions — Hammond, Keeney & Raiffa (1999), Harvard Business School Press; ISBN 9780875848570](https://openlibrary.org/isbn/9780875848570) — the source of the **PrOACT** frame. Not consulted directly in this pass; cited for correct attribution of the acronym, which does **not** originate in [8].
