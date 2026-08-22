# Findings — comparison method and prompting

**Deliverable for** [`docs/research/method.md`](./method.md). **Read with** [BRIEF.md](../../BRIEF.md)
and [`docs/adr/`](../adr/).

This is the synthesis of eight inputs: the repository owner's prior document on scoring order
[1] — treated here as a first-class input, built on rather than repeated — and seven research
sections that remain in [`sections/`](./sections/) as the working notes. Each section carries its own
evidence audit, its own reference list and its own open questions; this document states what to
**do**, resolves the places where the sections disagree, proposes the MCP tool surface, and
consolidates the ADR actions.

**Conventions.** Claims the literature supports are marked EVIDENCE and cited; claims that are
inference over evidence are marked **(reasoning, not evidence)**. Vocabulary is comparanda's:
**alternatives** (rows), **criteria** (columns), **subject**, **measure** (stored: score,
confidence), **encoding** (derived, view-layer), **missing** (always with a reason). Where an ADR
number is ambiguous it is prefixed — `rubricator ADR-0006`, `comparanda ADR-0015`.

**Evidence grades** used in the summary table: **strong** = multiple primary sources, replicated or
converging; **moderate** = one or two directly relevant primary studies, or primary studies that
disagree and are reconciled by reasoning; **weak** = practitioner convergence, single preprint, or
reasoning over adjacent evidence. A grade of **reasoning** means no literature exists on the exact
question and the recommendation is engineering judgement, falsifiable by the evaluation suite.

---

## Summary of decisions

An implementer should be able to read only this table and start work.

| # | Question | Recommendation | Evidence | ADR action |
|---|---|---|---|---|
| **Criteria** |
| 1 | What method generates criteria? | Keeney's value-focused thinking for generation; the DCLG manual §5.4.4 for checking. PrOACT is the right *pipeline* frame — ADR-0005 already is PrOACT plus a checkpoint — but *Smart Choices*' distinctive method (even swaps) is a trade-off procedure comparanda refuses to perform. Do not build the prompt on it. [2][3][4][5] | strong | ADR-0005 confirm |
| 2 | How is overlap detected before scoring? | Four tests in cost order: (a) structural, over an **emitted objective ladder** — free, deterministic; (b) the DCLG indifference probe, routed to the *user* at the step-4 checkpoint; (c) a required `depends_on` field on every scored cell (the "it depends" signal, made first-class); (d) optional RADAR-style synthetic coupling probes [2][7] | strong (a,b); moderate (c,d) | ADR-0005 confirm; new **ADR-0016** |
| 3 | Is correlating scored columns a redundancy test? | **No — affirmatively wrong.** The DCLG manual gives a worked counterexample; and for an LLM rater the judge's own halo inflates inter-criterion correlation from human r ≈ 0.32 to r ≈ 0.98 [2][21]. Report it as a *traversal-leakage diagnostic* of the scoring run, never label it a redundancy finding | strong | ADR-0008 amend |
| 4 | How many criteria? | Target 5–9 leaves; warn above 7 ungrouped; require a proposed grouping above 9; hard-stop above 15 without groups. The binding constraint is **splitting bias** [9], not Miller 7±2 (that citation does not support the claim). When there are too many, **group** — never silently cut. Report group sizes | moderate | ADR-0005 confirm |
| 5 | What must a criterion definition contain? | Ten required fields: `id`, `name`, `objective`, `question`, `level`, `preference`, `attribute_type`, `scale` (anchors), `evidence_rule`, `missing_rule`, `exclusions`. `missing_rule` is the one that makes ADR-0006 testable at the criterion level | strong | comparanda schema ask |
| 6 | Can criteria change after scoring starts? | Yes — criteria drift is documented [6]. The step-4 checkpoint is a gate that opens both ways. Requires criteria-set **versioning**, a per-measure record of the criterion version scored against, and **mandatory invalidation** of cells scored under a changed definition | moderate | new **ADR-0016** |
| **Scales and confidence** |
| 7 | Score scale? | **1–5 integer, declared ordinal**, not configurable. Buy discrimination with repeats, not width: 0–5 beats 0–10 and 0–100 on absolute human–LLM agreement [20], and rubric position bias is non-monotone in scale length, lowest at 3 or 5 points [22]. **This overrides the "widen to 1–10" recommendation carried in [1] §6** | moderate | new **ADR-0012** |
| 8 | Per-level descriptors? | Required at levels **1, 3 and 5** only; 2 and 4 are structurally "between". Write anchors as **evidence conditions**, never evaluative adjectives. Version them by content hash with the criterion; two analyses sharing a criterion key but not an anchor hash are **not comparable on that criterion** [13][14][15] | moderate | new **ADR-0012** |
| 9 | What does `confidence` mean? | **Evidence quality, three ordinal levels** — ADR-0006 is right and has excellent prior art (GRADE-CERQual, ICD 203, the Admiralty code all separate source quality from the judgement) [26][27][28]. Add the three rules ADR-0006 omits: no citable span → `unknown` **never** a low-confidence score; the score is **never hedged** toward the midpoint; contradiction is a downgrade with a named reason from a closed set | strong | ADR-0006 confirm; new **ADR-0012** |
| 10 | Can ADR-0008's calibration item be computed? | **Not as written.** "Do high-confidence cells outperform low-confidence ones" is a *discrimination* test; no proper scoring rule (Brier, ECE, reliability diagram) can be computed on an ordinal evidence-quality label. Split into two metric families and add an optional probability-valued `certainty` measure — **elicited only in evaluation runs**, never in a delivered analysis | strong | ADR-0008 amend; new **ADR-0012** |
| **Scoring protocol** |
| 11 | Pointwise or pairwise? | **Pointwise, and do not build a pairwise pipeline for v1.** Forced choice structurally manufactures a winner — judges flip 13.6% on average while their own scalar gaps are not significant [36] — which is the exact opposite of ADR-0006. It is also 7–20× more expensive per criterion at the reliability comparative judgement requires [37] | moderate | new **ADR-0011** |
| 12 | When may pairwise be used at all? | Per-criterion escalation only, under four conditions: column compressed **and/or** unstable, **and** decision-relevant, **and** ≥70% evidence-backed (hard veto). Fit **Bradley–Terry by MLE with Davidson ties, bootstrap the interval — never online Elo**, whose ratings depend on comparison arrival order [38][39][40] | moderate (rule: reasoning) | new **ADR-0011** |
| 13 | Traversal order? | **Cell-wise, one criterion per generation**, with a **tool-supplied seeded permutation**. This adopts [1]'s primary recommendation. Criterion order inside a prompt shifts a criterion's mean by up to 0.80 points on a 5-point scale [22]; scoring attributes together collapses them into one [21] | strong | new **ADR-0011** |
| 14 | Evidence first or score first? | **`extract_evidence` before `score_cell`, and `score_cell` receives the span, not the corpus.** Reference-guided judging beat chain-of-thought by more than 2× on MT-Bench (3/20 vs 6/20 failures) [33]. Scoring-then-citing is both the worse protocol and the one that produces post-hoc citation | strong | new **ADR-0011** |
| 15 | Does structured output damage reasoning? | **No.** The paper claiming it does not survive reading its own body — 100% of its degraded responses put the answer key before the reason key [42]; with real constrained decoding the gap reverses [43][44]. Use grammar-constrained sampling with the **reasoning field declared before the value fields**, and let deliberation happen *outside* the constrained region | strong | new **ADR-0013** |
| 16 | How many repeats? | Connector `k=1` + targeted re-elicitation; deployed `k=5` with adaptive early stop (halt at 3 on agreement, escalate to 9 only on flagged cells). The knee is at 5; past 9 you buy decimal places on a 5-level scale [58][59][60] | moderate | new **ADR-0018** |
| 17 | How are repeats reduced? | **Lower median only** — for even k take the lower central order statistic so the result is a level a rater could have chosen. `reduction="mean"` **raises**, naming the level of measurement [53]. A trimmed range is legal; a trimmed mean is not | strong | new **ADR-0011** |
| 18 | What about a bimodal cell? | **Refuse to emit a point reduction.** For a cell split 2/4 at p=.45 each, the median lands on 3 — a level almost nobody chose — with probability rising from .10 at k=1 to .36 at k=21. More repeats make the point estimate *monotonically more misleading* | reasoning (simulation, see [r4](./sections/r4-variance-mitigation.md)) | new **ADR-0011** |
| 19 | What is the headline stability statistic? | **Dominance survival rate** — the fraction of repeated matrices in which an alternative remains non-dominated — plus Pareto-set churn. It needs no weights, which is what makes it compatible with comparanda ADR-0015's refusal to aggregate. Kendall's tau-b and top-1 churn are the weighted secondary report | reasoning over [1] §8 | new **ADR-0018** |
| 20 | Confidence vs stability | Two different quantities; never collapse them. Evidential confidence is **stored** (ADR-0006, tool-verifiable). Procedural stability is **derived** from the assertion set and reported `n=1, unmeasured` when unmeasured — never estimated, never self-reported: verbalised self-confidence is systematically overconfident [54] and sampled agreement correlates only weakly with correctness [55] | strong | ADR-0006 confirm; new **ADR-0012** |
| **Evidence and citation** |
| 21 | Locator format? | A narrowed **W3C Web Annotation selector profile**, stored as an **array**, with a `TextQuoteSelector` **mandatory** wherever a text layer exists. Positions are hints; quotes are truth. Reject `CssSelector`, `XPathSelector`, `DataPositionSelector`, `RangeSelector` [70][71][72] | strong | new **ADR-0014** |
| 22 | Text Fragments (`#:~:text=`)? | Not a competing format — the grammar is **isomorphic** to a `TextQuoteSelector`. Store the selector, *derive* the deep link at render time [73] | strong | new **ADR-0014** |
| 23 | Chunking? | Keep it entirely **out of the citation path**. Every chunk carries `source_uri` + char offsets into the normalised full document; the model quotes text; the tool re-locates the quote in the **full** document. Then a boundary cutting the evidence costs recall, never a broken citation. Chunk overlap is not the fix people assume — the 800/400 default scored below average [84] | strong | new **ADR-0014** |
| 24 | How is a citation checked without a model? | A deterministic **eight-step ladder**: normalise (versioned) → resolvability → exact containment → bounded-edit-distance containment → drift classification → span-size sanity → **numeric-claim agreement** → polarity trap. Returns a graded verdict, never a model call [70][71][92] | strong | new **ADR-0014** |
| 25 | And with a model? | Evaluation suite only. Decompose into atomic claims, run a small NLI checker per (claim, span) with ALCE's precision/recall definitions [78][93]. A 100M–770M checker matches GPT-4-level grounding accuracy [81][82]. Treat it as a **regression detector, not an oracle** — the ceiling is ~80% macro-F1 [80] | strong | ADR-0008 amend |
| 26 | Source typing? | Five members: `primary`, `secondary`, `tertiary`, `agent-inference`, `user-assertion` — on the **reference**, not the document, because classification is relational to use [90]. Plus an orthogonal `stance`: `supports | contradicts | qualifies | background` [89]. Without `stance`, contradicting evidence is unrepresentable and therefore uncountable | strong | new **ADR-0015** |
| 27 | What actually prevents inference being presented as source? | **A constraint, not an enum.** `agent-inference` requires non-empty `derived_from`; `agent-inference` and `user-assertion` can never carry `confidence: high`; any document produced by an agent run is forced to `secondary` at best. Enforced by a deterministic tool, because ADR-0008 correctly predicts prompt-level honesty rules erode [88] | strong | new **ADR-0015** |
| **Architecture** |
| 28 | Host language and framework? | **Python confirmed. `aw_agents` rejected as host.** It contains no agent loop and no model client; its MCP adapter wires exactly `list_tools` and `call_tool` over the low-level SDK, stringifies results, and cannot serve prompts, resources or elicitation — which is the one sentence in ADR-0003 that makes one spec serve two runtimes | strong (source read) | **ADR-0004 supersede** → new **ADR-0009** |
| 29 | What to build the MCP surface on? | **Official MCP Python SDK v2 / FastMCP 4**, over a core of plain deterministic Python functions that know nothing about MCP. FastMCP 4 is the first version implementing modern-protocol elicitation via `InputRequiredResult` [106], which ADR-0005 step 4 needs | strong | new **ADR-0009** |
| 30 | MCP sampling as an escape hatch? | **No — deprecated in revision 2026-07-28**, migration path "integrate directly with LLM provider APIs" [95]. The question is settled without a judgement call. Extend the rule: no in-tool model calls **and no embedding calls** — an embedding model is a model | strong | new **ADR-0010** |
| 31 | Retrieval? | **Lexical: BM25 + normalised substring**, fixed tokenizer, fixed tie-break. Deterministic, key-free, dependency-light. Contextual/late-chunked embedding indexes belong to an **offline corpus-preparation step** whose output is a static index the connector reads [86][87] | strong | new **ADR-0010** |
| 32 | Long context or retrieval? | Retrieve by default. There is **no long-context pricing surcharge** on current models, so the 2025-era cliff is gone [105]; the crossover is ~20k–40k corpus tokens when you control caching and ~5k when you do not — and in the connector you control neither | strong (arithmetic over published prices) | new **ADR-0010** |
| 33 | How is the step-4 checkpoint implemented? | MCP **elicitation** where the client supports it — but `requestedSchema` is restricted to a **flat object of primitives** [97], so the rich criteria discussion stays in the chat turn and the elicitation is the *record of the decision*. Documented degraded path where the capability is absent. Confirmation stored as authored, timestamped provenance | strong | ADR-0005 amend |
| 34 | How does a checkpoint survive a session boundary? | **MCP gives you nothing here** — neither `requestState` nor a Tasks `taskId` survives a new chat. Own a store whose record **is a partial comparanda analysis**, using `not-assessed` / `pending` / `unknown` exactly as comparanda ADR-0009 intends. A half-finished analysis is a finished document about an unfinished analysis | strong | new **ADR-0017** |
| 35 | Tool count and granularity? | **19 tools, 11 minimum viable.** Comfortably under the 30–50 band where tool selection degrades [102]. Separate **generation granularity** (prompt: one cell per generation) from **write granularity** (tool: accepts a batch) — conflating them costs 56 round trips for no benefit | strong | new **ADR-0009** |
| 36 | Prompt bundle vs MCP server? | **One artifact, not two.** Claude clients surface MCP prompts as slash commands and resources as `@` mentions [112], so serving the prompts *is* the prompt bundle | strong | ADR-0007 amend |
| 37 | LLM access in the deployed runtime? | All of it through the local `aix` facade, never a raw provider SDK. `rubricator.mcp` must never import `rubricator.agent`, asserted by a subprocess import test. Six concrete facade gaps must be filed and closed before ADR-0008's variance work can start | strong (source read) | new **ADR-0019** |

---

## What the owner's scoring-order document settles, and what this document changes

[1] is the direct predecessor of §3 and §4 below and is not repeated here. Its recommendations are
adopted or overridden as follows, explicitly:

| [1]'s recommendation | Status | Why |
|---|---|---|
| **Cell-wise / one-criterion-per-call scoring as the default** | **Adopted**, and now triple-corroborated: a second research group measured criterion-order effects of up to 0.80 points on a 5-point scale, with 56 of 60 (judge, criterion) tests significant [22] | The single most important decision it makes |
| **Multiple repeats + aggregate** | **Adopted, with the reduction pinned**: lower median, never mean [53], and **refused entirely for a polarised cell** — an addition [1] does not make | A central reduction over a bimodal cell is monotonically more misleading as k grows |
| **Randomise traversal order per run** | **Adopted and strengthened**: the seed comes from a *tool*, not the model, so the run is replayable and the seed enters provenance. And it pays even at `k=1`, which is the connector's normal case | A random error is honest; a systematic error attached to criterion identity is not |
| **Swap-and-average for pairwise** | **Adopted, but demoted** — pairwise is an escalation, not a step, and the correct handling of a swap disagreement is to declare a tie, not to average [33] | See summary row 11 |
| **Calibration anchors in the rubric** | **Adopted and specified**: anchors at 1/3/5 only, written as evidence conditions, versioned by content hash | [14][15] |
| **Temperature 0** | **Adopted for the deployed runtime only.** It does not exist in the connector; a parameter that silently no-ops in one of two first-class runtimes is a bug in the specification | ADR-0003 |
| **Widen the scale to 1–10 (Stureborg's Table 6)** | **NOT adopted.** Two later results contradict it: 0–5 wins on absolute human–LLM agreement with 0–10 the *worst* of three scales tested [20], and rubric position bias is non-monotone in scale length, roughly doubling from n=5 to n=9 [22] | Summary row 7 |
| **Remove chain-of-thought (same recipe)** | **NOT adopted.** Unimplementable on a reasoning model, and now contradicted: reasoning augmentation improves judge accuracy substantially while worsening superficial-quality bias, which is repaired by *structuring* the reasoning (plan-before-judge), not removing it [47] | Summary row 15 |
| **The §8 experiment (five arms, τ decision rule)** | **Adopted as an ADR-0008 deliverable**, with two arms added that exist only because rubricator has two runtimes: `in_session_isolated` and `in_session_visible` | See §4.4 |
| **`scipy` in the protocol** | **NOT adopted as a dependency.** A 21-line pure-Python Kendall tau-b matched `scipy.stats.kendalltau` to 2.2×10⁻¹⁶ on this project's data shape; vendor it and make `scipy` a test-only extra | The MCP server must install fast and light |

One framing in [1] is also updated: its primary statistic is Kendall's τ over the *induced ranking*,
which requires **weights** — and comparanda ADR-0015 refuses a weighted total by default. A stability
report whose headline number needs the thing the companion tool refuses to compute is
architecturally wrong. The weight-free **dominance survival rate** replaces it as the headline;
τ stays as the secondary report, computed only when the user has declared weights (summary row 19).

---

## 1. Eliciting criteria

Working notes: [`sections/r1-criteria-elicitation.md`](./sections/r1-criteria-elicitation.md).

**Finding.** The brief's guess that *Smart Choices* is "probably the best single source for the
elicitation prompt" is half right and worth correcting. PrOACT is the right pipeline frame — ADR-0005's
six stages already *are* PrOACT plus a confirmation checkpoint and a review stage — but the book's
distinctive contribution is **even swaps**, a trade-off elicitation method operating on an
already-populated consequence table [11][12], and trade-offs are precisely what rubricator hands back
to the user rather than resolving (comparanda ADR-0015). The operational content belongs to Keeney
1992 (objective-generation devices, the WITI ladder, the nine properties) [3], Keeney & Gregory 2005
(the five attribute properties and the natural → constructed → proxy ordering) [4], and DCLG §5.4.4,
which states seven checks precisely enough to lift into a prompt verbatim [2].

**Recommendation.** `propose-criteria` runs ten phases (A–J in the section notes) and must *emit*,
not merely use, the **objective ladder**: for each candidate criterion, "why is that important?"
until the chain terminates, then "what do you mean by that, exactly?" downwards until each leaf can
be judged for one alternative in isolation. The leaves are the criteria; the rejected means
objectives become the `exclusions` text of the criteria they serve.

Emitting the ladder is the cheapest structural win available **(reasoning, not evidence)**: two
criteria whose ladders meet at the same fundamental objective within one hop are double-counting
candidates *by construction*, computable with no model call. That is the textbook ADR-0003 shape.

**The most load-bearing negative finding in the whole research round** is that the obvious redundancy
test — correlating scored columns — is affirmatively wrong, for two independent reasons. First, the
DCLG manual states verbatim that "[m]utual preference independence can hold even when options are
correlated in their measures on real-world criteria provided that the criteria express separate
aspects of value", with a worked pharmaceutical counterexample, and concludes that "a judgement about
double counting cannot be made on an objective basis" [2]. Second, for an LLM-scored matrix the
observed correlation measures the *rater*, not the criteria: when GPT-4 scores several attributes in
one generation the inter-attribute correlation inflates from a human r = 0.315 to r = 0.979 [21] —
one attribute pair in one dataset, so treat the magnitude as indicative and the direction as
transferable. The confound is larger than the signal. Correlation may be **reported** as a
scoring-run diagnostic — an unexpectedly high value is evidence the traversal leaked context between
cells, which is an ADR-0008 stability concern — and must **never** be labelled a redundancy finding.

That an LLM will in fact reproduce the overlap defect is no longer a prediction but a measurement:
LLM-generated rubrics "often lack coverage, **conflate dimensions**, misalign preference direction,
and contain redundant or highly correlated criteria, degrading judge accuracy", and a recursive
decompose-then-filter cycle that removes them improved preference-judgment accuracy by up to +17.7
points on JudgeBench [8]. Three of those four named failure modes are already on the DCLG/Keeney
checklist — coverage is completeness, conflated dimensions is bundling, misaligned direction is the
polarity check — which is a satisfying convergence between the 1976 decision-analysis literature and
2026 LLM evaluation practice.

Two smaller findings with direct design consequences:

- **`depends_on` on every scored cell.** DCLG describes how preference dependence is actually caught
  in practice: "If the assessor says that he or she can't judge the preference scores on one
  criterion without knowing the scores on another criterion, then preference dependence has been
  detected" [2]. Making that a required emittable field costs zero extra calls and converts a failure
  the model would otherwise commit silently into a declared one — the same move ADR-0006 makes for
  evidence **(reasoning, grounded in [2])**.
- **The number-of-criteria limit is not a legibility limit.** Miller 7±2 is about immediate memory
  span for unidimensional stimuli and does not support the claim; citing it would be exactly the
  failure both repositories exist to prevent. The real driver is **splitting bias**: attributes in
  the more detailed parts of a value tree are weighted significantly higher, robustly across
  weighting techniques [9]. So the number of criteria in a group is itself a smuggled value
  judgement, the correct response to too many is to **group**, and group sizes must be *reported*
  because the bias is invisible otherwise.

**And one contradiction with the current pipeline framing.** Criteria drift is documented: "users
need criteria to grade outputs, but grading outputs helps users define criteria", with some criteria
dependent on the specific outputs observed, "raising serious questions for approaches that assume the
independence of evaluation from observation of model outputs" [6]. This does not contradict
value-focused thinking — VFT forbids deriving criteria *structure* from the alternatives while
explicitly endorsing alternatives as *stimuli* — but it does contradict ADR-0005's step 4 read as a
one-way gate. The fix is small and architecturally real, and it is new ADR-0016.

---

## 2. Rubrics, scales, and what confidence means

Working notes: [`sections/r2-rubrics-and-calibration.md`](./sections/r2-rubrics-and-calibration.md).

**Finding — anchors help, less than the folklore claims.** The standard citation is Jonsson &
Svingby's review, which concludes that reliable scoring "can be enhanced by the use of rubrics,
especially if they are analytic, topic-specific, and complemented with exemplars and/or rater
training" [13] *(UNVERIFIED — paywalled; the bibliographic record resolves but the wording could not
be checked)*. A 2026 within-subjects experiment over 274 essays puts numbers on it: scoring approach
(holistic vs analytic) was **not** significant, while assessor experience and scale descriptor type
both were; inter-rater ICC rose from 0.425–0.490 to 0.439–0.646 with analytic descriptors — an
average gain of about +0.11 ICC across rater pairings, on overlapping intervals [14]. The lever the
study says matters most (assessor experience) is unavailable to us; the lever we have is worth
roughly +0.1.

**Finding — anchors reduce within-session drift far more than between-session drift.** New BARS data
across 22 exercises found within-panel reliability averaging 0.91 but **between-panel correlation
averaging only 0.60**, despite identical thorough training, concluding that "individual rater panels
develop their own idiosyncratic grading criteria" [15]. That is exactly rubricator's failure mode:
the same criterion scored in two sessions.

**Recommendation.** Per-level descriptors at **1, 3 and 5 only**, written as **evidence conditions**
("a source states a figure above the threshold and no source contradicts it"), not evaluative
adjectives ("excellent"). Levels 2 and 4 are structurally "between" and get no prose — writing it
produces near-duplicate text that invites the model to distinguish on wording rather than on
evidence **(reasoning)**. Keep numeric values out of anchor prose unless they are the actual
thresholds: whatever number sits in front of a rater *is* an anchor, and anchoring survives
transparently irrelevant values, monetary incentives, explicit forewarning and expert judges [32].
Anchors are versioned with the criterion by content hash, and **two
analyses sharing a criterion key but not an anchor hash are not comparable on that criterion**; the
tooling says so rather than letting the reader assume otherwise. That is the direct operational
response to [15].

**Recommendation — the scale is 1–5 and not configurable.** The literature genuinely conflicts and
the conflict is worth stating rather than splitting. Stureborg optimises *rank correlation against a
gold label* and finds widening helps up to 1–10, then reverses at 1–100 with visible round-number
clumping [21]. Li et al. optimise *absolute agreement between raters* across six benchmarks and find
0–5 wins on both ICC and error, with **0–10 the worst of the three** [20]. The psychometric
literature finds attenuated precision below about six options and **no advantage beyond six** [18][19].
rubricator does not ship a ranking by default (comparanda ADR-0015), so the binding quantity is
absolute level agreement and human legibility, not tie-breaking — which is where 0–5 wins
**(reasoning, resting on evidence at each step)**. Where discrimination is wanted, buy it the way
Stureborg's own table permits: k repeats aggregated, which recovers roughly two thirds of the
1–5 → 1–10 gap without changing what the reader sees [21].

**Finding — ADR-0006's confidence definition is right, and under-specified in the one place that
matters.** The evidence-quality choice is the mainstream position in four independent fields, all of
which reached it by the same route: somebody kept confusing "how sure am I" with "how good is my
source", and it caused harm. GRADE-CERQual rates confidence in a finding of a qualitative synthesis
over four named components [26]; ICD 203 separates analytic confidence from source credibility and
explicitly forbids combining a confidence level and a likelihood term in one sentence [27]; the
Admiralty code keeps source reliability and information credibility as two independent characters so
that "the reliability of the source does not influence the assessed accuracy of the report" [28].
*(ICD 203 and the IPCC guidance note both returned HTTP 403 to automated fetching and are described
from corroborating secondary sources.)*

What ADR-0006 does not say is what stops `low` from becoming the channel a guess hides in. Three
rules fix it, and they matter more than the level definitions:

1. **No citable span → `unknown`, never `low`.** `low` means thin evidence, never no evidence.
   ClimateX shows the model will take the other route by default: on a structurally identical task
   (classify the confidence IPCC authors assigned), frontier models managed 44.3% zero-shot accuracy,
   **consistently over-estimated confidence in the "low" and "medium" categories**, and expressed a
   knowledge limitation on between none and 4% of prompts [25].
2. **The score is never hedged.** `score` is the best estimate given available evidence; it is never
   pulled toward 3 because the evidence is thin. All uncertainty lives in `confidence`. This extends
   ADR-0006's existing "not a hedged 3" rule from the no-evidence case to the thin-evidence case and
   forbids double-counting uncertainty — which central-tendency bias otherwise makes the default, and
   which is maximally damaging because comparanda's blended encoding then suppresses an
   already-suppressed value.
3. **Contradiction is a downgrade with a named reason**, from a closed CERQual-style set:
   `secondary-source`, `inference-required`, `indirect-context`, `sources-disagree`, `stale-source`,
   `single-source`. Countable, and what makes a confidence label auditable rather than a vibe.

**Finding — ADR-0008's calibration item is not implementable as written.** "Do high-confidence cells
outperform low-confidence ones" is a *discrimination* test, which an ordinal label can pass; none of
the classical calibration machinery (Brier [29], Murphy's decomposition [30], reliability diagrams,
ECE) can be computed on an evidence-quality label, because those require a number claiming to be a
probability. The gap is cheap to fill — verbalised confidences are often better calibrated than the
model's own token probabilities, "often reducing the expected calibration error by a relative 50%"
for RLHF-tuned models [24], and log-probabilities are unavailable in the connector anyway. So: an
optional `certainty` measure, ratio level, drawn from a **fixed closed set**
`{0.5, 0.6, 0.7, 0.8, 0.9, 0.95}` — which removes the binning decision by construction and therefore
the largest source of ECE estimator bias [31]. Elicit it with the equivalent-bet framing — would
you rather be paid if an independent expert agrees, or on a spinner that pays with this probability
— which is the cleanest known way to force a probability claim to carry an operational meaning [23].
Its scope is deliberately narrow; see the conflict
resolved in §7.3.

---

## 3. LLM-as-judge: the scoring protocol

Working notes: [`sections/r3-llm-as-judge.md`](./sections/r3-llm-as-judge.md).

**Finding — the brief's expectation about pairwise does not survive.** The brief says pairwise is
"worth considering, especially for criteria where absolute anchors are hard". The pairwise win is
real — PAIRS improves Spearman correlation with human labels almost everywhere, most dramatically for
weaker judges [34] — but it was measured on tasks where every alternative *has* a quality and a
winner always exists. rubricator's product is the opposite. Three findings make it the wrong default:

- **Forced choice manufactures differences.** Across 29 tasks × 50 trials × 2 judges, pairwise
  preferences flip 13.6% of the time on average, 28% of questions exceed a 20% flip rate and one
  reaches 56% — while the *same judges'* mean pointwise gaps are 0.19–0.36 on a 10-point scale and not
  statistically significant in aggregate [36]. A protocol whose defining behaviour is "always produce
  a winner" is the wrong instrument for a product whose defining behaviour is "sometimes decline to
  produce a score" **(reasoning)**. Ties in Bradley–Terry are a *modelled outcome*, not an abstention:
  nothing in a tie distinguishes "genuinely equal" from "evidence genuinely absent", which are the two
  states ADR-0006 exists to keep apart.
- **Pairwise is more gameable.** With embedded distractor features, pairwise preferences flip in ~35%
  of cases against ~9% for absolute scores [35].
- **Cost.** A usable pairwise scale for one criterion over A alternatives costs ≈20A calls at the
  reliability the comparative-judgement meta-analysis requires (NCR ≥ 20 per object for SSR ≥ .8)
  [37], against 3A for pointwise at k=3 — a 7–20× multiplier, for a latent scale that still has to be
  mapped back onto five rubric levels before comparanda can render it.

**Recommendation.** Pointwise, cell-wise, 5-point anchored, median-of-K with randomised presentation
order. Escalate to pairwise per-criterion only when **(evidence coverage ≥70%) AND (decision-relevant)
AND (compressed OR unstable)** — and then only within the tied cluster. Encode the negative case too:
when a column is compressed and unstable but has no evidence, the correct output is **not** a pairwise
ranking; it is `missing` with reason `insufficient_evidence_to_discriminate` plus a note in the review
stage saying what evidence would resolve it. That is the product. The escalation thresholds are
**reasoning, not evidence**, and are the first thing an evaluation run should tune.

If escalation ever happens: **Bradley–Terry by MLE with Davidson's tie model, bootstrapped.** Never
online Elo — its ratings are volatile whenever win rates are near 50%, stability requires averaging
over ≥100 random orderings of the same fixed outcomes, and transitivity is not preserved [38]; the
Chatbot Arena leaderboard moved off online Elo for exactly this reason [39]. Davidson's ν parameter
is itself reportable: a high ν on a criterion is direct evidence the criterion does not discriminate
among these alternatives, which is precisely what ADR-0005 step 6 should surface [40][41].

**Finding — the structured-output scare is a field-ordering artifact.** The paper claiming format
restriction degrades reasoning reports in its own body that **100% of the degraded GPT-3.5 JSON-mode
responses placed the "answer" key before the "reason" key**, turning zero-shot chain-of-thought into
direct answering; its own gpt-4o-mini results with a real constrained decoder show structured
*winning* on one of three tasks (86.07 vs 83.11) [42]. An independent rebuttal identifies non-equivalent
prompts between conditions and the conceptual error of conflating fine-tuned "JSON mode" with
constrained decoding [43], and an independent benchmark finds constrained decoding **improves**
accuracy on all three reasoning tasks by 3–4 points [44]. Cite the paper for its field-order finding;
do not cite its abstract.

The practical consequence is a two-stage shape that maps cleanly onto both runtimes: **reason in
prose (or in the thinking block), then emit through a constrained schema with the reasoning field
declared first.** In the connector the judgement arrives as tool-call arguments under `strict: true`
[45], which is the right enforcement point for ADR-0003 — the schema is content we ship, the
constraint is applied by the caller's model, and our side stays deterministic. The supported JSON
Schema subset is load-bearing and constrains the tool surface before Phase 1 freezes it: a 1–5 score
must be `{"type": "integer", "enum": [1,2,3,4,5]}`, not `minimum`/`maximum`; no recursion; no numeric
or string-length constraints; `additionalProperties: false` everywhere [46]. Range-checking a span
offset moves into the deterministic validator, which is where it belongs anyway.

**Finding — the single most important amendment this research produces.** The largest LLM-judge
meta-evaluation to date (21 judges, 118 runs, ~541k judgements) names the trap: **reliability without
validity**. Two judges achieved near-perfect test–retest (0.992, 0.988) while showing severe position
bias (0.192, 0.125) [48]. ADR-0008's **Stability** criterion, as written, is passed perfectly by a
degenerate agent that emits `3` for every cell; its **Refusal to guess** criterion is passed perfectly
by one that emits `missing` everywhere. Both need a paired counter-metric, and the build should fail
when stability is high *and* discrimination is low, or when the missing rate is high *and* evidence
availability is also high. Add the same source's Minimum Viable Validation Protocol — chance-corrected
κ rather than raw exact match, AB/BA position-swap testing, ≥3 runs, ≥2 contrasting corpora, and the
paradox audit [48]. The complementary warning is that judge preferences do not correlate with measured
safety, world knowledge or instruction-following, and judges prioritise style over factuality [49]:
agreeing with a judge — including with yourself — is not evidence of being right. Two related biases
constrain the design rather than the metrics: judges favour their own generations in proportion to
their ability to recognise them [50], which is exactly why the agent must never score its own
generated summaries as if they were sources; and models bend toward stated preferences [51], which
makes the ADR-0005 confirmation checkpoint the exposure point for sycophancy. Panels of diverse
judges mitigate both at lower cost [52] — but only in the deployed runtime, since the connector has
exactly one model and no key.

---

## 4. Variance, and the uncertainty that remains

Working notes: [`sections/r4-variance-mitigation.md`](./sections/r4-variance-mitigation.md).

### 4.1 Two uncertainties, kept apart

**Recommendation.** Split the problem in two and never let the halves touch.

- **Evidential confidence** (ADR-0006: is there a citable span?) is epistemic, checkable by a
  deterministic tool, and belongs in the schema as a stored measure.
- **Procedural stability** (does the judgement survive re-elicitation?) is a property of the
  *procedure*, derivable only from repeated assertions, and must be reported `n = 1, unmeasured` when
  it has not been measured — never estimated, never inferred from the model's own say-so.

The evidence vindicates ADR-0006 emphatically. Verbalised self-confidence is systematically
overconfident, "potentially imitating human patterns of expressing confidence", and no elicitation
technique consistently outperforms the others on hard tasks [54]; sampled self-consistency correlates
only weakly with correctness (ρ ≈ 0.20–0.59, with the highest-agreement model showing the *lowest*
ρ and being wrong 48% of the time even at agreement ≥ 0.8) [55]. By defining confidence as evidence
quality, ADR-0006 picked the one signal a deterministic tool can verify. Add the corollary it does
not state: **sampled consistency is admissible evidence about the procedure and inadmissible as
evidence about correctness.** Never let a stability number colour a cell as if it were confidence.

The dissociation is not hypothetical. The diagnostic case — high confidence, unstable — is the most
*actionable* output this product can produce, because the fix is not "find more documents", it is
"define the criterion better", which is exactly where ADR-0005 says the value lives. Stureborg found
Krippendorff's α of only ≈0.51 between a single-attribute and a multi-attribute template on the same
data, below human inter-annotator agreement: the evidence did not change, only the procedure did [21].
Self-inconsistency across repeats is itself well measured [68][69].

### 4.2 Ordinal reductions, and what repeats cannot fix

Stevens's framework permits the median for location and percentiles for dispersion on an ordinal
scale; the mean and standard deviation appear only from the interval scale upward [53] *(paywalled;
paraphrased from secondary summaries, not quoted)*. comparanda ADR-0003 has already committed to
this. Concrete rules, all enforced at the tool boundary:

- Reduction is **lower median** — for even k, the lower of the two central order statistics, so the
  result is always an observed level. Never `(3+4)/2 = 3.5`.
- Report the **mode** alongside; for k ≤ 9 on a 5-level scale the mode *is* the majority vote, which
  is what the self-consistency literature actually studies [58][59][60].
- A trimmed **range** is a percentile statistic and is legal; a trimmed **mean** is still a mean and
  is not. The honest dispersion report is the interquartile level range plus `n`.
- `reduction="mean"` **raises**, naming the level of measurement. Silent illegal reductions are how
  the category error gets back in.

**And a rule nobody had stated.** For a genuinely contested cell — levels 2 and 4 at p = .45 each —
the lower median lands on **3, a level chosen by only 10% of draws**, with probability rising
monotonically from .10 at k=1 to .36 at k=21. More repeats make the point estimate monotonically more
*misleading*. This is not a defect of the median; any central reduction does it. **Sampling cannot
rescue a bimodal cell; it can only reveal that the cell is bimodal.** Therefore `aggregate_assertions`
must **refuse to emit a point reduction for a polarised cell** unless explicitly overridden, and
instead emit the level multiset plus a `contested` marker. *(This is a simulation run for the section,
not a published finding — reasoning, not evidence — but it reproduces an exact multinomial computation
to ±0.003 and it restates comparanda ADR-0011's objection to a mean of 3.5 over raters who said 2 and 5.)*

### 4.3 What the connector can do with no budget

No literature exists on mitigating evaluation variance inside a single chat session with no sampling
budget. Everything here is **reasoning grounded in evidence**, stated so that ADR-0008 can falsify it.

1. **Deterministic traversal isolation** — one criterion per tool round-trip, with the tool
   *swallowing* each judgement into server-side state and returning only an acknowledgement plus the
   next work item. This implements Stureborg's explicit recipe at zero marginal cost. **The honest
   limit, which must be stated in the docs and not glossed:** in the connector the entire analysis is
   one conversation, so prior judgements remain in the transcript and this is *attenuation*, not
   elimination. Call it `in-session isolation`, one rung below `fresh-call isolation`. How much
   survives is the single highest-value unknown in the project and it is cheap to measure.
2. **A tool-supplied seeded permutation.** You cannot seed the model, but you can seed the *protocol*,
   and the protocol is where the order bias lives. The tool is a pure function of `(seed, items)`, so
   it is deterministic, replayable and auditable, and the seed enters provenance. **Do not ask the
   model to shuffle** — it will produce a distribution with its own priors and it will not be
   reproducible. This pays even at k=1: without shuffling, whichever criterion is listed first always
   receives the un-anchored judgement, a bias perfectly confounded with criterion identity; with a
   seeded shuffle the same total assimilation is present but no longer attached to particular criteria.
   The underlying positional effects are well measured — option-order reordering changes accuracy by
   13–75% across benchmarks [65], long-context recall is U-shaped over position [64], and judges show
   large order-flip rates with a first-shown preference [33].
3. **Targeted re-elicitation driven by a deterministic value-of-information proxy.** Uncertainty
   sampling spends the budget where the model is unsure; value-of-information says spend it where
   being wrong would **change the decision**. For a comparison matrix that is computable exactly, with
   no model call: **a cell is pivotal if perturbing it by ±1 level changes the non-dominated set**
   (or, when weights exist, the top-1 or top-3 set). Priority order: pivotal → thin evidence →
   observed instability → wide conformal set → *criterion-level instability, which routes to
   **redefinition**, not re-scoring*. That last one is a negative recommendation and it matters:
   re-scoring cells in an under-defined criterion spends budget on a problem re-scoring cannot solve.
   ADR-0005 step 6 already asked for exactly this; here is its deterministic implementation.
4. **Blind re-scoring, named honestly.** The anchoring literature predicts a second judgement is
   pulled toward a visible first [66][67], and models asked to revise without external feedback often
   degrade [66]. But "blind" overstates it in-session — the prior score is still in the transcript —
   so the parameter is `withhold_prior=True`, and **whether it works is measurable and must not be
   assumed**.
5. **An explicit independence ladder**, carried on every assertion:
   `in-session < fresh-session < distinct-model < distinct-human`. Do not label two fresh-session runs
   "two raters" and do not compute an inter-rater coefficient over them; confident errors are partly
   shared even across providers [55]. A statistic over rung-1 assertions is **test–retest
   reliability**, not inter-rater reliability, and the report must say so. Getting this label wrong
   would be exactly the manufactured rigour ADR-0006 exists to prevent.
6. **Honest disclosure as the fallback**, rendered from what the `procedure` record says actually
   happened — and citing the human halo, joint-vs-separate and sequential-contrast literature
   [61][62][63], so it does not read as "LLMs are uniquely bad", a framing that is both false and,
   because it invites dismissal, useless.

**Conformal prediction is genuinely applicable and is the only technique that buys a per-cell interval
from a single run** — exactly the connector's constraint. Split conformal over LLM-judge scores
"constructs continuous prediction intervals from a single evaluation run" with an ordinal boundary
adjustment [56], and prediction-set width predicts judge error (pooled ρ = +0.576, p < 10⁻¹⁰⁰) while
reflecting *item* difficulty rather than judge noise [57]. It needs an exchangeable calibration set,
which rubricator does not have for real analyses — so it is an ADR-0008 fixture deliverable, deferred
past v1. In the meantime use the width-predicts-error finding in the cheap form it permits: as a
**ranking** signal for the re-scoring allocator, where nothing is being claimed, only prioritised.

### 4.4 The harness

[1] §8's five arms become an ADR-0008 deliverable, plus two arms that exist only because rubricator
has two runtimes: `in_session_isolated` (one growing session, each turn returning only an
acknowledgement) and `in_session_visible` (the same session with prior scores restated). Arms 6 vs 1
measure how much of cell-wise isolation survives a shared transcript; arms 6 vs 7 measure whether
withholding works. Neither question has an answer in the literature and both cost a few dollars.

---

## 5. Evidence and citation

Working notes: [`sections/r5-evidence-citation.md`](./sections/r5-evidence-citation.md).

**How bad is the failure mode?** An audit of four generative search engines found only **51.5% of
generated sentences fully supported by their associated citations**, and only **74.5% of citations
actually supporting their paired statement**, characterising the systems as offering a "facade of
trustworthiness" [79]. One in four citations wrong, in a well-formatted matrix, is worse than no
citations, because the format certifies the content. That is the empirical case for ADR-0006 and for
ADR-0008's treatment of citation faithfulness as the most damaging failure class.

**Recommendation — the locator profile.** Adopt a narrowed W3C Web Annotation selector set, stored as
an **array**, with a `TextQuoteSelector` mandatory wherever a text layer exists. Two normative points
from the specification make this the model's own intent rather than a compromise: it *recommends* a
State alongside a `TextPositionSelector` for robustness, and it says "Multiple Selectors SHOULD select
the same content" [70]. Hypothesis stores three selectors per target and tries four reattachment
strategies in production [71]. The generalisable lesson is one sentence: **positions are a cache,
quotes are the truth** — a quote with prefix and suffix survives edits, re-pagination, re-extraction
with a different PDF library, and, critically for us, **re-chunking**, which is the change most likely
to happen in this system.

Where W3C has no selector, adopt Hypothesis's de-facto extensions verbatim (`PageSelector`,
`MediaTimeSelector`, `ShapeSelector`) [72]; where a real fragment standard exists, reach it through
`FragmentSelector` + `conformsTo` — RFC 5147 for character and line ranges *with* its integrity
checks [74], RFC 8118 for PDF [75], Media Fragments for time and rectangles [76]. Two off-by-one traps
to document rather than discover: `PageSelector.index` and `PageSelector.label` are different numbers
and both are needed (a journal PDF has label "iv" at index 3), and RFC 5147 line positions are the
*boundaries between* lines, so `line=40,58` denotes lines 41–58 [74]. Where the connector runs inside
Claude, the native Citations API is a first-class ingestion path rather than a special case — it
guarantees its returned pointers are valid, and maps cleanly onto this profile [77].

**Text Fragments are not a competing option.** The grammar `prefix-,textStart,textEnd,-suffix` is
*exactly* `TextQuoteSelector{prefix, exact, suffix}` [73]. Store the selector; derive the
`#:~:text=` URL in comparanda's view layer. One canonical form, many renderings.

**Recommendation — keep chunking out of the citation path.** Both known chunking failures — boundary
loss and context loss — are *retrieval* failures and must never become *citation* failures. Four rules
guarantee it: every chunk carries `source_uri` plus char offsets into the normalised full document;
retrieve small and present wide; **the model returns a quote and the tool relocates it in the full
document**; and contextual preambles are prepended to the *embedded* text only, never to the document
text that quotes resolve against — or the agent will eventually cite its own preamble as a primary
source, which is ADR-0006's damaging error class arriving through the back door of the retrieval
layer. Note that chunk overlap is not the mitigation it is assumed to be: the widely-copied
800-token/400-overlap default scored below average on token-level recall and worst on every other
metric [84], and semantic chunking's costs "are not justified by consistent performance gains" [85].

**Recommendation — split citation checking in two, exactly as ADR-0003 demands.**

The **tool** is a deterministic ladder and needs no model: (0) versioned normalisation — NFC, strip
zero-width, fold typographic variants and ligatures, repair PDF line-break hyphenation, collapse
whitespace; (1) resolvability, which alone catches hallucinated documents; (2) exact containment;
(3) bounded approximate containment via bit-parallel Myers search [92]; (4) drift classification into
`verified` / `moved` / `stale` / `unresolvable` using stored document and quote hashes; (5) span-size
sanity — below ~40 characters a quote matches in too many places to be a locator, above ~1500 it is a
document, not a span; (6) **numeric-claim agreement**, the highest-yield check for a comparison matrix
because justifications here are dense with numbers, requiring every figure in the justification to
match one in some cited span after magnitude/percentage/separator/date normalisation; (7) a lexical
overlap floor used *only* as a weak on-topic signal, with the docstring stating plainly that lexical
overlap is not a faithfulness measure; (8) a **polarity trap** comparing negation and hedge markers,
which catches the classic contradiction case for zero model calls.

The **judge** is evaluation-only. Follow ALCE's definitions verbatim — concatenate cited passages as
premise, citation recall binary per statement, citation precision binary per citation with the
irrelevance test [78] — with RAGAS-style atomic-claim decomposition [93] and AttrScore's third label
(*contradictory*) kept, because binary entailment throws away the one that matters most here. Run it
on a small checker: HHEM-2.1-Open (100M, 74.28% balanced accuracy on RAGTruth-QA against GPT-4's
74.11%) [82], AlignScore (355M) [83], or MiniCheck-FT5 (770M, "GPT-4-level performance but for 400×
lower cost") [81]. All run on CPU with no API key, which matters given the public-repository
constraint. And treat the judge as a **regression detector, not an oracle**: even a fine-tuned GPT-3.5
reaches only ~80% macro-F1 on attribution [80], so track deltas between prompt versions and never gate
a release on a judge score without a deterministic check underneath it.

**Finding — the schema cannot currently express the most damaging citation failure.** comparanda
ADR-0014's evidence reference has no field for a citation's **stance**. With only "supports"
representable, an agent that finds contradicting evidence can either cite it misleadingly or drop it,
and the omission becomes uncountable. The single most damaging citation failure in a decision matrix
is not a wrong span — it is a right span cited alongside a silently discarded contradicting one. Add
`stance: supports | contradicts | qualifies | background`, modelled on CiTO's citation-intent
properties [89], orthogonal to `source_type`. A cell scored 4 that carries a `contradicts` reference
is the most interesting cell on the page.

**Finding — the enum will not save you; the constraint will.** Source type belongs on the *reference*,
not the document, because classification is relational to use — the same PDF is primary for what its
authors measured and secondary for its literature review [90]. PROV-O supplies the formal anchor
(`hadPrimarySource`, `wasQuotedFrom`, `wasDerivedFrom`, `wasAttributedTo`) but not the member we need,
because no external vocabulary was designed for a producer that manufactures plausible-looking sources
at scale [88]. So: five members (`primary`, `secondary`, `tertiary`, `agent-inference`,
`user-assertion`), plus three hard constraints enforced by a deterministic tool rather than a prompt —
`agent-inference` requires non-empty `derived_from`; `agent-inference` and `user-assertion` can never
carry `confidence: high`; and any document produced by an agent run and re-ingested is forced to
`secondary` at best, never `primary`. ADR-0008 correctly predicts that prompt-level honesty rules
erode; a model that wants a clean citation will set the enum to `primary`.

**A gap worth naming.** No benchmark I could locate measures *omission* of contradicting evidence in a
decision-matrix setting *(UNVERIFIED — could not locate a source; treat as a gap, not a negative
result)*. The adjacent fact-checking literature shows the shape of the problem: every surveyed dataset
fails at least one of the two requirements realistic evidence must meet, and models trained on such
data rely on leaked evidence [91]. The recommendation is an adversarial probe at the release tier
only — retrieve a second time with a query built *against* the asserted direction and ask the judge
whether anything contradicts — reported as `counter_evidence_missed@k` and never gated. It is the only
test that catches confident cherry-picking, which is the failure a well-cited matrix is best at hiding.

---

## 6. Architecture, runtimes and the local ecosystem

Working notes: [`sections/r6-mcp-and-agent-architecture.md`](./sections/r6-mcp-and-agent-architecture.md)
and [`sections/r7-local-ecosystem.md`](./sections/r7-local-ecosystem.md).

**Finding — ADR-0004's premise does not survive reading the code.** The local `aw_agents` package
contains **no agent loop and no model client whatsoever**: `AgentBase` is an abstract class with two
methods returning hand-written dicts. Its MCP adapter registers exactly two handlers, `list_tools` and
`call_tool`, over the *low-level* SDK server — no `prompts/list`, no `prompts/get`, no
`resources/list`, no `resources/read`, no elicitation, and no seam through which a consumer could
supply them. Tool results are stringified into emoji-decorated human-readable text rather than
structured content; the OpenAPI adapter silently drops nested input sub-schemas, which is precisely
where every rubricator tool's contract lives; and zero tests touch either adapter. Since "prompts ship
as **content the runtime can serve**" is the sentence in ADR-0003 that makes one tool specification
serve two runtimes, that single fact decides the question. ADR-0004 also assumed `aw_agents` would
supply the deployed agent's "own model access" — it does not, so the runtime work is unchanged
whichever framework is picked.

**Finding — MCP sampling is settled without a judgement call.** The current specification revision
is `2026-07-28` [94], and it is not a minor increment on the 2025 revisions. Sampling was
**deprecated in it**, with migration path "integrate directly with LLM provider APIs" and new implementations
told they SHOULD NOT adopt it [95]. Roots and protocol-level logging are deprecated too, and
server-initiated requests were removed outright in favour of the new multi-round-trip retry pattern —
a breaking change [96]. Even setting deprecation aside, sampling would have been wrong: ADR-0003's
rule is not "the server must not hold a key", it is "tools are deterministic". A tool that sampled the
client's model would be untestable by ADR-0008's stability check and invisible in the transcript,
which is where ADR-0006's whole posture lives. **Extend the rule to embeddings**: an embedding model
is a model, and a bundled local one is a heavy non-deterministic dependency whose version silently
changes results between runs.

**Finding — elicitation's schema restriction reshapes the step-4 checkpoint.** `requestedSchema` is
restricted to a **flat object of primitives**; "complex nested structures, arrays of objects (beyond
enums), and other advanced JSON Schema features are intentionally not supported" [97]. So you cannot
elicit "here are seven proposed criteria, edit their definitions". What you *can* elicit is a flat
confirmation: an enum `approve | approve-with-notes | revise`, a free-text `notes`, and a multi-select
of criteria to drop. The rich discussion — the part ADR-0005 says is the valuable part — stays in the
chat turn driven by a prompt, and the elicitation becomes the **record of the decision**. That is a
better design anyway: it keeps the argument in the transcript where the user can see it
**(reasoning)**.

**Finding — MCP prompts are a better fit than expected, and collapse two deliverables into one.**
Prompts are user-controlled and typically surfaced as slash commands; a `prompts/get` returns messages
whose content may be text, a `resource_link`, or an **embedded resource** [98]. Claude Code surfaces
them as `/mcp__servername__promptname` and resources as `@server:protocol://resource/path` [112]. So
`propose-criteria(analysis_id)` can return the method text *and* the current analysis state in one
call, prompt files stay versioned markdown on disk with a thin assembler in front of them, and
ADR-0007 items 1 and 2 are **the same artifact**. Prompt arguments are untyped strings on the wire, so
pass handles, not payloads. And prompt count does not degrade tool selection, because prompts are not
in the model's tool list. Resources are application-driven and tools are model-controlled [100][99],
which gives the allocation rule: **if the model decides to fetch it, it is a tool; if the user or the
host decides to surface it, it is a resource** — and some things are legitimately both.

**Finding — nothing in MCP survives a session boundary.** `requestState` dies with the request by
design [96]; a Tasks `taskId` is durable across disconnects but is scoped to one operation and held by
the *client*, so a new chat has no idea it exists [101]; prompt caching is a cost optimisation, not
state [105]. The comparable prior art separates a checkpointer scoped to a thread from a durable store
across threads, and is explicit that cross-session resume needs a real backend [109]. The
recommendation is the cleanest available: **the state record IS a partial comparanda analysis**, not a
bespoke checkpoint format that must later be converted. comparanda ADR-0009's closed missingness set
already carries the resume semantics — `not-assessed` = nobody has looked; `pending` = deliberately
deferred by instruction; `unknown` = someone looked and could not determine — and that last
distinction is the ADR-0006 distinction the whole product rests on. Record the step-4 confirmation as
authored, timestamped provenance so a resuming session does not re-ask, and so "the criteria were
confirmed by a human on this date" is auditable.

**Finding — retrieval-vs-long-context is no longer a pricing question.** There is no long-context
surcharge on current models: a 900k-token request bills at the same per-token rate as a 9k one [105].
The crossover is ~20k–40k corpus tokens when you control caching, ~5k when you do not — and in the
connector the host owns the cache breakpoints and the context budget, and truncates tool responses at
25,000 tokens by default [103]. Always build the span index (you need it for citations regardless, and
ADR-0006 says pointing at a whole document is not a citation), retrieve by default, and implement the
inline case as one documented behaviour rather than a branch in the model's head. On tool-list size,
the independent evidence agrees with the vendor guidance in shape if not in level: retrieval over a
large candidate tool set beats putting them all in the prompt, with accuracy degrading as the
candidate count grows [104][102].

**Finding — the local `aix` facade is the right chokepoint and is not currently sufficient.**
`chat()` returns `response.choices[0].message.content` and discards everything else, so `n`-sampling
is billed and thrown away, `usage`/`finish_reason`/`logprobs` are unreachable, `seed` passes through
undocumented, and there is no provider-enforced JSON schema — even though LiteLLM underneath supports
every one of them [110][111]. Every gap is a facade gap, not a capability gap, which makes fixing it
in `aix` obviously correct rather than wrapping around it. One defect lands directly on rubricator:
`constrained_answer` type-coerces its answer but never checks membership in `valid_answers` or range
bounds, so an out-of-set answer passes silently — and anchored criterion levels are exactly that case.
Six issues are enumerated in [r7](./sections/r7-local-ecosystem.md); none is large, and ADR-0008's
variance work is blocked on two of them.

**One constraint neither repository has recorded.** If corpus ingestion normalises documents into
clean markdown, character-range spans index the *cleaned* text, not the source a reader opens — which
is exactly the uncheckable citation ADR-0006 forbids. Decide early whether rubricator cites into a
normalised, persisted rendition (shipped as an MCP resource so the span is resolvable) or maintains an
offset map back to the source. This is a Phase 1 schema decision, not a Phase 3 detail.

---

## 7. Conflicts between sections, resolved

Where two sections recommend incompatible things, this is the resolution and the reason.

### 7.1 Cell-wise vs column-wise traversal

**The disagreement.** [1], r2 and r3 all recommend cell-wise, one criterion per generation. r4 §2.6
argues the boundary condition is *criteria*, not alternatives — a criterion is a scale, and holding a
scale fixed across alternatives is what column-wise scoring is for, the same reason essays are marked
question-by-question rather than script-by-script. r6's prompt table names `score-column` "the
default, per the sibling scoring-order research", and [`docs/prompts/README.md`](../prompts/README.md)
says column-wise is "likely better than cell-at-a-time".

**Resolution: cell-wise is the default. `score-column` is demoted to a cheaper arm awaiting harness
validation, and the two documents that say otherwise are wrong and should be corrected.** r6's
attribution is a misreading — [1] recommends cell-wise explicitly — and the prompts README predates
the evidence. The direct measurements all point one way: criterion position inside a prompt shifts a
criterion's mean by up to 0.80 points with 56/60 tests significant [22], and attributes sharing a
generation collapse toward each other [21]. r4's scale-drift argument is real but is **reasoning, not
evidence**, and it is exactly what harness arms 1 vs 2 exist to settle. Until they do, the default
follows the measurements. *(Action: fix the prompts README line and r6's prompt table.)*

### 7.2 Is `stability` a stored measure?

**The disagreement.** r3 says `stability` is NEW and "must be a separate field" on the measure object.
r4 says explicitly do **not** add a stored stability measure — by comparanda's own domain model,
measures are stored and encodings are derived, stability is derived from the assertion set, and
comparanda already ships that encoding under the name `disagreement`.

**Resolution: r4's mechanism, r3's intent.** Adopt r4 — stability is derived, not stored — because the
schema is comparanda's under ADR-0002 and its own model settles the question. But r3's substantive
requirement is honored in full and is the reason both sections raised it: **the number must never be
collapsed into `confidence`.** What rubricator asks comparanda for instead is the metadata that makes
the derived encoding honest when the "raters" are runs of one model: `authorKind`, `independence`,
`perturbation` on the assertion, and a `procedure` record on the analysis. Without `independence`,
five draws of one model render as five raters and the `disagreement` encoding tells a lie.

### 7.3 Does an optional `certainty` measure belong at all?

**The disagreement.** r2 wants a probability-valued `certainty` measure, because ADR-0008's
calibration item is otherwise not implementable — no proper scoring rule can be computed on an ordinal
label. r4 argues verbalised self-confidence is systematically overconfident [54] and inadmissible as
evidence about correctness.

**Resolution: `certainty` exists, but only in evaluation runs.** It is elicited when the analysis runs
against a fixture with known answers, or when the user explicitly asks; it is **never required in a
delivered analysis**, never encoded in the view, and never blended into the score×confidence palette.
r2's need is real and specific — you cannot compute a Brier score on a label — and it is a need of the
*evaluation suite*, which is where a model's self-report can be checked against outcomes rather than
trusted. r4's objection binds wherever nothing checks it, which is every production run. Both are
satisfied by restricting the scope, and the fixed closed set of allowed probabilities removes the
binning decision that would otherwise dominate the estimator's bias [31].

### 7.4 ADR-0006: confirm or amend?

**The disagreement.** r3, r4 and r5 all say confirm — emphatically, in r4's case. r2 says amend,
because ADR-0006 omits the rule that makes its own definition enforceable, and notes that mechanically
this means a superseding ADR since ADR-0006 is accepted.

**Resolution: confirm ADR-0006; put the enforcement rules in the new measurement-scales ADR.** Every
decision ADR-0006 makes stands and is strengthened by the evidence. What is missing is not a changed
decision but an unstated *consequence* — and ADR-0001's "supersede rather than edit" rule makes
superseding an accepted ADR expensive. A new ADR that states the three enforcement rules, cites
ADR-0006 as its parent, and is testable by ADR-0008 achieves the same outcome without rewriting a
correct decision.

### 7.5 py2mcp vs the official SDK / FastMCP 4

**The disagreement.** r7 recommends building on the local `py2mcp`: it returns a live `FastMCP` object
whose `.prompt`, `.resource` and `.add_resource` were verified on the installed versions, and it ships
stdio, Streamable HTTP with OAuth 2.1 resource-server auth, and a middleware seam for free. r6 says
build on the official MCP Python SDK v2 / FastMCP 4 directly, because `py2mcp` is tools-only and
bolting prompts onto the object it returns defeats the point of the facade.

**Resolution: build on the official SDK v2 / FastMCP 4. The deciding fact is a version floor, not
aesthetics.** FastMCP 4.0.0 is the first release implementing modern-protocol elicitation via
`InputRequiredResult` under revision 2026-07-28 [106], and elicitation is the mechanism for ADR-0005
step 4 — the checkpoint the BRIEF says must not be removed. `py2mcp` pins `fastmcp` unbounded and
resolves to a 3.x release today, so adopting it would make the load-bearing checkpoint depend on an
upstream upgrade outside this project's control. r7's verification stands and its recommendation
should be revisited once `py2mcp` carries a FastMCP 4 floor; contribute `prompts=` / `resources=`
kwargs and that floor upstream. Meanwhile `py2mcp` keeps a real role on the CLI/OpenAPI line of
ADR-0007. Note also that dual-era support is **not** a freebie in either case: FastMCP rejects a tool
returning an `InputRequiredResult` on a handshake-era connection, and the fallback branch is our code
to write [106][107][108].

### 7.6 Embedding-based retrieval

**The disagreement.** r6's proposed determinism ADR forbids in-tool embedding calls outright. r5
recommends Late Chunking as "the model-free alternative" and "the default for the connector path".

**Resolution: r6 wins for the tool surface; r5's characterisation is wrong on one word.** Late Chunking
needs an embedding pass, and an embedding model is a model — either a key (no connector) or a bundled
local model (a heavy dependency whose version silently changes results). `corpus_search` is BM25 plus
normalised substring, with a fixed tokenizer, a fixed stopword list and tie-breaking fixed by
`(score, document_id, start)`, because a retrieval change that silently reorders spans would look
exactly like a prompt regression to ADR-0008. Late Chunking [87] and Contextual Retrieval [86] belong
to an **offline corpus-preparation step** run by the deployed agent or the CLI, producing a static
index the connector reads — which is what r5 already says about Contextual Retrieval, and the same
argument applies to both.

### 7.7 Column correlation in `report_weaknesses`

**The disagreement.** r6's tool 14 returns `criterion_correlations` and describes them as "the
post-hoc evidence of the double-counting `criteria_set`'s hygiene could only guess at". r1 §4e shows
that is precisely wrong.

**Resolution: r1 wins.** The field stays but is renamed and re-contracted: it is a
`traversal_leakage_diagnostic`, an ADR-0008 stability signal, and the tool's own output must carry the
sentence that it is not a redundancy finding. Redundancy findings come from the objective ladder, the
indifference probe and (optionally) the coupling probes — never from a correlation over LLM-scored
columns, where the judge's halo is larger than the signal [2][21].

### 7.8 ADR-0004: amend or supersede?

**The disagreement.** r7 says amend; r6 says supersede.

**Resolution: supersede.** ADR-0001 permits settling a *proposed* ADR in place, and ADR-0004 is
proposed — so amending is legal. But the decision inverts rather than refines: the framework changes,
the "if `aw_agents` can host the MCP surface directly, use it" clause is answered "it cannot and it
should not try", and the premise about model access is factually wrong. A superseding ADR leaves a
cleaner record of *why* — which is the whole point of ADR-0001 — and keeps ADR-0004 readable as the
question that was asked. Either is defensible; a human settles it.

### 7.9 A separate calibration-metrics ADR, or an ADR-0008 amendment?

**The disagreement.** r2 proposes two new ADRs, one of which is "Calibration and confidence-quality
metrics". r5, r3 and r4 all route their evaluation findings into ADR-0008 amendments instead.

**Resolution: fold the metric families into the ADR-0008 amendment.** Evaluation is already ADR-0008's
remit, the metric lists are consequences of the measurement decisions rather than independent
decisions, and eleven new ADRs is already at the edge of what a newcomer can read in order. The
substance — Family A discrimination over `confidence`, Family B proper scoring over `certainty`, the
`min_n` gate on ECE, bootstrap-by-analysis, the ban on averaging `confidence`, and
`confidence_inflation_rate` as a release gate — is preserved in full.

---

## Proposed MCP tool surface

The BRIEF calls this "the core artifact of the whole project". This is r6's proposal reconciled with
r4's variance tools, r5's citation ladder and r1's criteria checks.

**The invariant.** Every tool is deterministic: the same arguments and the same store state produce
the same result, with no model call, no embedding call, and no network call except reading local
sources through the injected resolver. Judgement is never a tool; where a step needs inference it is a
**prompt** the caller's model runs, plus a deterministic tool that validates the result.

**Two granularities, deliberately separated.** *Generation* granularity is one cell per generation
(the prompt's business). *Write* granularity accepts a batch (the tool's business). Conflating them
would cost 56 round trips on an 8×7 matrix for no benefit.

**Count.** 19 tools; **11 minimum viable**. Under the 30–50 band at which tool-selection accuracy
degrades [102], and with definitions well under the 10k tokens at which deferred loading starts to pay
[102] — measure it with `count_tokens` rather than trusting the estimate. Names are `snake_case`,
noun-first (`analysis_*`, `corpus_*`, `frame_*`, `alternatives_*`, `criteria_*`, `measures_*`,
`report_*`), with no server prefix because clients already namespace by server. Every tool declares
`outputSchema` and returns `structuredContent` plus a short human-readable `content` summary [99].
Validation and business-rule failures return `isError: true` with a message carrying the fact needed
to fix it; unknown tool or malformed request is a JSON-RPC error [99].

`analysis_id` is an opaque handle per the specification's own Stateful Tools guidance, with its
retention window stated in `analysis_open`'s description and an expiry error the model can recover
from [99].

| # | Tool | Signature (abbreviated) | Contract | Determinism | Stage | Cut |
|---|---|---|---|---|---|---|
| 1 | `analysis_open` | `(analysis_id?, subject?, aliases?, allow_skip_confirmation?=false) -> {analysis_id, stage, summary, next_actions}` | Creates a new in-progress analysis — a valid, minimal comparanda document with zero rows and columns — or reopens one. Unknown/expired id ⇒ `isError` naming the retention window | Store read/write only | 1, resume | **keep** |
| 2 | `analysis_get` | `(analysis_id, view: summary\|frame\|criteria\|outstanding\|full = summary) -> projection` | Reads durable state. `outstanding` returns only cells that are not yet settled — `not-assessed`/`deferred`, and any deployment code that is non-terminal — with counts by code. The resume affordance. `full` returns a `resource_link`, never the document body | Pure projection | all | **keep** |
| 3 | `corpus_add` | `(analysis_id, sources[], chunking?) -> {document_ids, span_count, token_estimate, warnings}` | Normalises with the **versioned normaliser**, assigns stable ids, records char offsets **into the normalised full document**. Idempotent on content hash. Records whether a source was cleaned, and keeps the offset map — the ADR-0006 constraint of §6 | Fixed chunker, versioned normaliser | 2, 5 | **keep** |
| 4 | `corpus_search` | `(analysis_id, query, k=8, document_ids?, must_include?, window_chars=600) -> [{span_id, document_id, start, end, text, score}]` | **BM25 + normalised substring. No embeddings** (ADR-0010). Empty query returns the whole corpus under the inline threshold, else an actionable `isError`. Retrieve small, present wide | Fixed tokenizer, fixed stopword list, tie-break `(score, document_id, start)` | 2, 3, 5 | **keep** |
| 5 | `frame_set` | `(analysis_id, subject, decision, decider, ambiguities[], instructions?) -> {stage, validation}` | Requires at least one entry in `ambiguities` **or** an explicit `"none"`, so ADR-0005's "surface ambiguity rather than resolving it silently" is mechanical rather than aspirational | Validated write | 1 | **keep** |
| 6 | `alternatives_set` | `(analysis_id, alternatives[], mode=merge) -> {added, updated, near_duplicates[], unsourced[]}` | Writes rows. **Flags** near-duplicates above a named threshold; never merges. Flags alternatives sourced from inference with no evidence | Normalisation + fixed threshold | 2 | **keep** |
| 7 | `criteria_set` | `(analysis_id, criteria[], ladder?, groups?, mode=merge) -> {validation, hygiene, ladder_report, size_report}` | **Rejects any criterion missing a required definition field** (§1): `objective`, `question`, `level`, `preference`, `attribute_type`, anchors at 1/3/5 for ordinal, `evidence_rule`, `missing_rule`, `exclusions`. Runs the §1 structural overlap test over the emitted ladder; lints the percentage trap and bare value words in anchors; reports group sizes and imbalance. **Bumps the criteria-set version and returns the cells invalidated** by any changed definition (ADR-0016). Diagnostics only — the model and the user decide | Schema validation, graph walk over the ladder, lexical lint | 3 | **keep** |
| 8 | `frame_confirm` | `(analysis_id, scope=all, confirmed_by?, confirmation_text?) -> {confirmed, mechanism, record}` | **The ADR-0005 step-4 gate.** Where the client declared elicitation, returns an `InputRequiredResult` with a **flat** form (`decision` enum, `notes` string, multi-select of criteria to drop) — the protocol forbids nested schemas [97]. Where it did not, returns `mechanism: "out-of-band"` with instructions to ask in chat and call again. **The tool never confirms on its own behalf.** Writes the confirmation as authored, timestamped provenance | It records a decision; it does not make one | **4** | **keep** |
| 9 | `plan_traversal` | `(analysis_id, *, strategy=cell, seed, repeat_index=0, only?) -> TraversalPlan` | Pure function of `(seed, items)`. The model receives the order; it never chooses it. The seed enters provenance and the run replays exactly. Strategy `column` and `single-pass` exist for the harness arms | Pure function | 5 | **keep** |
| 10 | `measures_write` | `(analysis_id, plan_id?, cells[], on_uncited=downgrade) -> {written, rejected[], citation_checks[], next_items}` | **The most important tool.** Validates against the comparanda schema; runs the §5 deterministic ladder inline on each cited quote; enforces *no `high` confidence without a verified `primary`/`secondary` span*, *`agent-inference` requires `derived_from`*, and *`score` present ⇒ at least one evidence ref or an explicit `missing`*. Requires the `depends_on` field (§1). **Never echoes a previously written score** — that is the in-session isolation mechanism of §4.3 and it is why the tool must own the state rather than the transcript. Refuses to write scores at all when the analysis is unconfirmed and `allow_skip_confirmation` was not set | String containment, approximate search, schema validation | 5 | **keep** |
| 11 | `measures_mark_missing` | `(analysis_id, selector, code, note) -> {marked, skipped}` | Bulk qualified blanks. What makes "fill these two criteria, mark the rest deferred" a first-class instruction rather than a prompt hope, and what makes a partial analysis a valid resumable document. `code` is validated against the analysis's own vocabulary — core six plus declared extensions — never against a literal list here | Set operations | 5, resume | **keep** |
| 12 | `analysis_validate` | `(analysis_id, strict=true, schema_version?) -> {valid, schema_version, errors, warnings, consistency_violations}` | Validates against the published comparanda JSON Schema at the ADR-0002 boundary — non-negotiable per ADR-0008 — **and** runs the confidence/source-type consistency rules of ADR-0015 over the whole analysis | JSON Schema validation + rule set | 5, 6 | **keep** |
| 13 | `check_citations` | `(justification, evidence_refs, *, resolve, max_error_rate=0.02, min_span_chars=40, max_span_chars=1500, normaliser=DEFAULT) -> CitationReport` — plus an analysis-wide fan-out mode | The full eight-step ladder of §5, returning a graded verdict per reference (`exact`/`normalised`/`fuzzy`/`moved`/`stale`/`unresolvable`), `numeric_support_rate`, unmatched numeric claims, and flags. Cell-level granularity so the connector can repair a bad citation **inside** the scoring loop; an analysis-level checker only tells you afterwards | Deterministic string algorithms; the normaliser is versioned and pins `quote_hash` semantics | 5, 6 | **keep** |
| 14 | `aggregate_assertions` | `(analysis, *, reduction=median, allow_contested_reduction=false, polarised_gap=1) -> ReducedMatrix` | Per cell: `{reduction, n, levels, min, max, span, modes, polarised, contested}`. `reduction="mean"` **raises**, naming the level of measurement [53]. A polarised cell yields **no point value** unless explicitly overridden (§4.2) | Order statistics | 5 | keep (no-op at k=1) |
| 15 | `stability_report` | `(analysis, *, weights?, tau_bands=(0.7, 0.9)) -> StabilityReport` | **Weight-free primary:** dominance survival rate per alternative, Pareto-set churn, per-cell shape statistics. **Weighted secondary, only when weights are declared:** tau-b distribution, top-1/top-3 churn, band verdict. **Per criterion:** test–retest agreement, labelled by the lowest independence rung present. Also returns the column histograms and compression fraction that power the §3 escalation trigger and ADR-0008's discrimination counter-metric | Vendored `kendall_tau_b`, Pareto computation, histograms — no `scipy` | 6 | **keep** |
| 16 | `report_weaknesses` | `(analysis_id, top_k=10, budget?, weights?) -> {uncited, thin_evidence, low_confidence, stale_citations, agent_inference_only, traversal_leakage_diagnostic[], dominated_alternatives, veto_flags, completeness, rescoring_plan?}` | The deterministic half of ADR-0005 step 6. With `budget`, returns the value-of-information plan of §4.3: **pivotal** cells first (±1 flips the non-dominated set), then thin evidence, then observed instability — with under-defined criteria routed to a **redefine** bucket rather than a rescore bucket. `traversal_leakage_diagnostic` carries column correlations **explicitly labelled as a scoring-run diagnostic, never a redundancy finding** (§7.7) | Rank statistics and exact perturbation over stored values | 6 | **keep** |
| 17 | `disclose_variance` | `(analysis_id) -> Disclosure` | Renders the §4.3 disclosure content file against what the `procedure` record says actually happened. **The text is content, not code** (ADR-0003), so a reviewer edits the wording without a release. Names what was and was not measured, and cites the human halo / joint-vs-separate / sequential-contrast literature so it does not read as "machines are uniquely bad" | Template substitution over a provenance record | 6 | **keep** |
| 18 | `compute_coupling_matrix` | `(probe_scores) -> CouplingReport` | Arithmetic over probe scores supplied by the model (probe generation and probe scoring are **prompts**). Flags off-diagonal mass above a named threshold. The canonical worked example of the ADR-0003 split. Cost is real — `3n²` judgements, 192 calls at n=8 — so it is **opt-in**, default-on only when the structural or indifference tests already flagged something | Arithmetic | 3 | **cut first** |
| 19 | `fit_bradley_terry` | `(comparisons, *, tie_model="davidson", bootstrap=1000) -> {strengths, tie_parameter, intervals}` | Reached only through the §3 four-condition escalation. Returns latent strengths with percentile intervals; the caller must map back to rubric levels via a monotone anchor map and mark the cell's derivation explicitly, because a BT-derived score is not the same kind of object as a directly judged one | Pure numeric optimisation | 5 | **cut / defer** |

**Minimum viable set (11):** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12. `plan_traversal` (9) is in the minimum
set even though it looks optional: it is free, and it is the connector's strongest available
mitigation. Cut 18 and 19 first. Cut 17 next only if k > 1 is always used — it is most needed at k=1,
which is the connector's normal case. Cut 15 and 14 together if there are never repeats. **Cut 16
last**: without it, ADR-0006's "self-critique is part of the deliverable" degrades to unaided model
opinion, which is exactly the failure ADR-0008 exists to catch. Cut 11 only if you are willing to drop
partial-fill instructions, which is a visible product regression. **13 is not cuttable** — it is the
product.

**Deliberately absent, and why.**

- No `propose_criteria`, `score_cell`, `review` or `detect_overlap` tool. These are judgement. They
  are prompts. ADR-0003, enforced.
- No embedding-backed semantic search (§7.6).
- No aggregate or total tool. comparanda ADR-0015 is explicit that no aggregate is computed by
  default; a tool returning one would make it the path of least resistance.
- No `analysis_list` tool. It is a resource — the *host* lists, the model does not browse.
- No `temperature` or `seed` parameter on any scoring tool. Neither exists in the connector, and a
  parameter that silently no-ops in one of two first-class runtimes is a bug in the specification.
  Seed the **traversal**, not the model.
- No `conformal_interval` in v1 (§4.3). When it lands it reads a stored calibration table produced by
  an offline evaluation run, so the tool itself still never calls a model.

**Prompts (ten).** `run-analysis`, `frame`, `enumerate-alternatives`, `propose-criteria`,
`confirm-frame`, **`score-cell` (the default)**, `score-column` (the harness arm and the cheap mode),
`review`, `audit-existing`, `resume`. Every one takes string arguments only and embeds state as
resource content blocks. Every one restates the ADR-0006 honesty rule in its own words. Per §7.1 the
default flips from the current README.

**Resources (eight).** `rubricator://method`, `://confidence-rubric`, `://missingness-codes`
(all `audience: ["assistant"]`, high priority), `://schema/comparanda/{version}`, `://analyses`,
`://analysis/{id}`, `://analysis/{id}/document/{document_id}`, and — the one that earns its keep —
`://analysis/{id}/span/{span_id}`, which makes rubricator's evidence references **resolvable URIs**,
exactly what comparanda's host-supplied `EvidenceResolver` needs.

---

## Recommended ADR actions

ADRs are immutable once accepted; nothing here edits one. New ADRs are numbered from 0009 in a single
consolidated sequence, because the sections proposed overlapping numbers independently.

| ADR | Action | Reason |
|---|---|---|
| ADR-0001 | confirm | The numbering discipline is what let seven independent sections converge without collision; the collisions that did occur are resolved in §7. |
| ADR-0002 | confirm | The boundary held under pressure. Every schema need this research found is a *request* to comparanda, and the mechanism (`jsonschema` against a published schema, validated at the boundary) is unchanged. |
| ADR-0003 | confirm | Its central mechanism is now verified end to end: MCP prompts surface as slash commands and resources as `@` mentions [112]; every mitigation, check and statistic in this document is a deterministic tool plus a prompt; and the deprecation of MCP sampling [95] removes the only tempting exception to "no tool may require a model". |
| **ADR-0004** | **supersede** (by ADR-0009) | Its premise does not survive reading the code: `aw_agents` has no agent loop and no model client, and its MCP adapter cannot serve prompts, resources or elicitation. See §6 and §7.8. |
| ADR-0005 | **amend** | The six stages stand and are independently arrived at by the decision-analysis literature [2][3]. Two things must be specified that the ADR leaves open: the **mechanism** of step 4 (MCP elicitation with a flat-primitive form where supported [97]; a chat-plus-record path where not; confirmation stored as authored provenance either way), and the fact that step 4 is a gate that opens **both** ways (see ADR-0016). |
| ADR-0006 | **confirm** | Strengthened from four directions: deployed-system citation support rates of 51.5%/74.5% [79] are the empirical case for the whole policy; verbalised self-confidence is overconfident [54] and sampled agreement correlates weakly with correctness [55], so evidence quality is the one signal a tool can verify; and the enum/constraint analysis of §5 shows the policy needs enforcement, not revision. Its missing enforcement rules go into ADR-0012, not into a superseding ADR — see §7.4. |
| ADR-0007 | **amend** | Deliverables (1) and (2) are **one artifact**: serving MCP prompts *is* the prompt bundle [98][112]. The sequence stands; the item count does not. `py2mcp` moves to the CLI/OpenAPI line rather than the connector (§7.5). |
| ADR-0008 | **amend** | Four changes. (a) **Stability** and **Refusal to guess** as written are both passed by a degenerate agent; each needs a paired discrimination counter-metric, plus chance-corrected κ, AB/BA swap testing and the paradox audit [48]. (b) The **calibration** bullet names a discrimination test; split it into Family A (discrimination over `confidence`: accuracy-by-level with Wilson intervals, a monotone-trend test, `confidence_inflation_rate` as a release gate, `unknown_preference_rate`, `low_confidence_laundering_rate`) and Family B (proper scoring over `certainty`: Brier with Murphy decomposition, skill score, value-binned reliability curve, ECE reported second with a `min_n` gate, AUROC) — bootstrapping by analysis, never by cell, and never averaging `confidence` (§7.9). (c) Add the citation metric table with explicit tiers, separating citation precision from recall and adding `counter_evidence_missed@k` as report-only. (d) Add the three new fixture families (moved-text, paraphrase, contradiction) and the two connector-shaped harness arms. |

### New ADRs

**ADR-0009 — Python, the official MCP SDK, and the rejection of `aw_agents` as host (supersedes ADR-0004).**
Python is confirmed for both runtimes: the schema tooling, the LLM facade and every project convention
are already Python, and a JS/TS runtime would share a language with the UI and nothing else. The MCP
surface is built on the **official MCP Python SDK v2 / FastMCP 4**, over a core of plain deterministic
functions in `rubricator.tools` that know nothing about MCP; FastMCP 4 is the first release
implementing modern-protocol elicitation via `InputRequiredResult`, which ADR-0005 step 4 requires
[106], and dual-era fallback is our code to write. `aw_agents` is rejected as host: reading its source
settled the fork ADR-0004 posed — its MCP adapter registers exactly `list_tools` and `call_tool` over
the low-level SDK with no seam for prompts or resources, its results are stringified rather than
structured, its OpenAPI adapter drops nested input sub-schemas, its adapters carry no tests, and it
contains no model client, loop, session or streaming, so it does not supply the "deployed agent owning
its own model access" this ADR assumed either. It is not rejected forever: if a non-MCP chatbot surface
is ever wanted, its OpenAPI adapter becomes a candidate **second consumer of the same functions**,
never the host, and the sub-schema flattening must be fixed first. `py2mcp` keeps a real role on the
CLI/OpenAPI line; contribute `prompts=`/`resources=` kwargs and a FastMCP 4 floor upstream and revisit.
The tool surface stays under 20 tools with generation granularity separated from write granularity.
No JS/TS runtime in v1; reserve the npm name.

**ADR-0010 — The determinism boundary.**
No MCP sampling: it was deprecated in revision 2026-07-28 with the migration path "integrate directly
with LLM provider APIs" [95], and it would in any case produce judgements that are untestable by
ADR-0008 and invisible in the transcript where ADR-0006's posture lives. No in-tool model calls of any
kind — **and no embedding calls**, because an embedding model is a model: it needs either a key (no
connector) or a bundled local model whose version silently changes results between runs. Retrieval is
therefore **lexical**: BM25 plus normalised substring matching, with a fixed tokenizer, a fixed
stopword list, a versioned chunker and tie-breaking fixed by `(score, document_id, start)`, so that a
retrieval change cannot masquerade as a prompt regression. This is sufficient because the model does
the semantic work in its own loop and can issue several queries. Contextual and late-chunked embedding
indexes are permitted only in an **offline corpus-preparation step** run by the deployed agent or the
CLI, producing a static index the connector reads. Retrieve by default; inline the whole corpus only
under ~25k tokens and only at the enumeration stage, implemented as one documented behaviour of
`corpus_search` rather than a branch in the model's head.

**ADR-0011 — The scoring protocol.**
Score **pointwise, cell-wise, one criterion per generation**, against a 5-point anchored rubric, with
the traversal order supplied by a seeded tool permutation and the rubric level order randomised per
read. `extract_evidence` runs **before** `score_cell` and `score_cell` receives the span, not the
corpus, because reference-guided judging halves chain-of-thought's failure rate again on MT-Bench [33]
and because scoring-then-citing is the arrangement that produces post-hoc citation. Prompt shape per
cell is **plan → judge → emit**, with the plan persisted as provenance [47]. Repeats aggregate by
**lower median**; `mean` is refused at the tool boundary, naming the level of measurement [53]; a
trimmed range is legal and a trimmed mean is not; and **no point reduction is emitted for a polarised
cell** — the level multiset and a `contested` marker are emitted instead. Pairwise comparison is
**not** the default and is not built in v1: forced choice manufactures winners where the judge's own
scalar reading contains no significant difference [36], has no natural abstention, and costs 7–20×
[37]. It may be escalated per criterion only under all of: evidence coverage ≥70% (hard veto),
decision relevance, and compression or instability — and then only within the tied cluster, fitted by
**Bradley–Terry MLE with Davidson ties and a bootstrap interval, never online Elo** [38][39][40][41],
with the resulting cell marked as derived. The escalation thresholds are explicitly reasoning, not
evidence, and are the first thing ADR-0008 tunes.

**ADR-0012 — Measurement scales, the meaning of confidence, and the two uncertainties.**
`score` is a **1–5 integer, declared ordinal, not configurable**; a criterion needing more resolution
is a ratio-level criterion and must be typed as such. Ordinal criteria carry required anchors at
levels **1, 3 and 5**, written as **evidence conditions** rather than evaluative adjectives, versioned
by content hash: two analyses sharing a criterion key but not an anchor hash are **not comparable on
that criterion** and the tooling says so [15]. `confidence` is a **three-level ordinal evidence-quality**
measure exactly as ADR-0006 defines it, with three enforcement rules that ADR-0006 leaves unstated:
**no citable span ⇒ `unknown`, never a low-confidence score**; **the score is never hedged toward the
midpoint** (all uncertainty lives in `confidence`, closing the double-counting trap); and
**contradiction is a downgrade with a named reason** from a closed CERQual-style set. `certainty` is an
**optional** ratio measure drawn from a fixed closed set of allowed probabilities, elicited **only** in
evaluation runs against fixtures with known answers or on explicit request, never encoded in the view
and never blended into the score×confidence palette — it exists because no proper scoring rule can be
computed on an ordinal label, and it is restricted because verbalised self-confidence is unreliable
wherever nothing checks it [54]. Finally, the two uncertainties are separated permanently: **evidential
confidence is stored** and tool-verifiable; **procedural stability is derived** from the assertion set,
reported `n = 1, unmeasured` when unmeasured, never estimated and never self-reported — and sampled
consistency is admissible evidence about the *procedure* and inadmissible as evidence about
*correctness*.

**ADR-0013 — Structured output and the JSON Schema subset.**
Judgements are emitted through grammar-constrained sampling in both runtimes — `strict: true` tool
definitions in the connector [45], the same JSON Schema through the provider's constrained decoder in
the deployed agent — with the **reasoning field declared before the value fields** and the
deliberation happening *outside* the constrained region, in prose or in the model's thinking block.
The claim that format restriction degrades reasoning does not survive reading the paper's own body
[42]; constrained decoding done properly improves accuracy [43][44]. The supported JSON Schema subset
is a hard constraint on the tool surface and must be honoured before Phase 1 freezes it: scores are
`enum`, not `minimum`/`maximum`; no recursion; no external `$ref`; no string-length constraints;
`additionalProperties: false` everywhere [46]. Range checks move into the deterministic validator,
which is where they belong. Every structured result passes through the same deterministic validator
before it becomes part of an analysis, and every tool declares `outputSchema` and returns
`structuredContent` — the two enforcement points are distinct and both are needed: `inputSchema` plus
strict mode constrains what the *model* may say, `outputSchema` plus our validator constrains what the
*server* may return [99].

**ADR-0014 — The evidence-reference locator profile.**
Evidence references carry a **flat array of selectors**, all of which select the same span, with a
`TextQuoteSelector` **mandatory** wherever a text layer exists. Adopted from the W3C Web Annotation
Data Model verbatim: `TextQuoteSelector`, `TextPositionSelector` (a **hint**, allowed to go stale),
and `FragmentSelector` + `conformsTo` as the sanctioned extension point [70]. Rejected for storage:
`CssSelector`, `XPathSelector`, `DataPositionSelector` and `RangeSelector`, all of which bind to a DOM
the producer never had. Adopted verbatim from Hypothesis where W3C has no selector: `PageSelector`
(index **and** label — they are different numbers and both are needed), `MediaTimeSelector`,
`ShapeSelector` (deferred out of v1) [72]. Text Fragments are a **rendering** of the quote, not a
competing locator, and are derived at render time [73]. Every typed selector has a documented lossless
serialisation to a `FragmentSelector` (RFC 5147, RFC 8118, Media Fragments) so a reference can
round-trip to a standard annotation [74][75][76]. Chunking is kept **out of the citation path**:
chunks are addresses into a document, every chunk carries `source_uri` and char offsets into the
normalised full text, and quotes always resolve against the full document, so a chunk boundary costs
recall and never a broken citation. The **normalisation function is versioned**, because changing it
silently invalidates every stored quote hash; and citation checking is the deterministic eight-step
ladder, whose verdict field is **written by the tool and never by the model**.

**ADR-0015 — Source type, stance, and the derived-from constraint.**
Every evidence reference carries `source_type` — `primary | secondary | tertiary | agent-inference |
user-assertion` — **on the reference, not on the document**, because classification is relational to
use [90]; and an orthogonal `stance` — `supports | contradicts | qualifies | background` — modelled on
CiTO [89], without which contradicting evidence is unrepresentable and therefore uncountable. The enum
alone does not prevent the failure ADR-0006 names, because a model that wants a clean citation will
set it to `primary`. Three structural constraints do, enforced by a deterministic tool: `agent-inference`
**requires** a non-empty `derived_from` (an inference that cannot name what it was inferred from is not
evidence, it is a justification); `agent-inference` and `user-assertion` can **never** carry
`confidence: high`; and any document produced by an agent run and re-ingested carries a marker that
forces every reference targeting it to `secondary` at best, closing the loop through which the most
damaging error class arrives. Time-based media require a `MediaTimeSelector` **and** a quote over a
registered transcript, because a citation nobody can check is not a citation.

**ADR-0016 — Criteria are revisable; the step-4 checkpoint is a gate, not a one-way door.**
Criteria drift is documented: users need criteria to grade outputs and grading outputs helps them
define criteria, and some criteria are dependent on the outputs observed [6]. This does not contradict
value-focused thinking — VFT forbids deriving criteria *structure* from the alternatives while
endorsing them as *stimuli* — but it does contradict ADR-0005 read linearly. Therefore: criteria sets
carry a **version**; every measure records the criterion version it was scored against; and when a
criterion's `question`, `scale`, `preference` or `exclusions` changes after cells have been scored,
**every cell scored under the old definition is invalidated** — set to `missing` with reason
`not-assessed` and a note naming the definition version — rather than silently retained. Without this,
criteria drift produces a matrix whose columns were scored against different rubrics, which is the
worst-of-both outcome and completely invisible in the output. Criteria that rubricator proposes and
then removes are recorded with a reason code (`merged-into`, `means-objective`, `not-controllable`,
`no-discrimination-expected`, `user-rejected`) and ship with the analysis: ADR-0006's discipline
applied one level up, because a criteria set with no visible rejects is a criteria set nobody
interrogated.

**ADR-0017 — In-progress analyses are durable partial comparanda documents.**
No MCP mechanism survives a session boundary — `requestState` dies with the request by design [96],
a Tasks `taskId` is held by the client and scoped to one operation [101], and prompt caching is a cost
optimisation [105]. rubricator therefore owns a store, keyed by an **opaque `analysis_id`** whose
retention window is stated in the creating tool's description and whose expiry produces a recoverable
error [99]. **The stored record is itself a schema-valid comparanda analysis**, not a bespoke
checkpoint format that must later be converted: a half-finished analysis is a finished document about
an unfinished analysis. comparanda ADR-0009's closed missingness set carries the resume semantics —
`not-assessed` = nobody has looked, `pending` = deliberately deferred by instruction, `unknown` =
someone looked and could not determine — and that last distinction is the one the whole product rests
on. The step-4 confirmation is stored as **authored, timestamped provenance**, not a flag, so a
resuming session does not re-ask and so the confirmation is auditable. Resumption is exposed three
ways: a `rubricator://analyses` resource for the host, `analysis_open` with an existing id, and a
`resume` prompt. The store lives in the platform user-data directory behind a Mapping interface,
never inside the package.

**ADR-0018 — Variance-mitigation policy per runtime, and the independence ladder.**
**Deployed default:** cell-wise traversal, a seeded permutation per repeat, `k = 5` with adaptive early
stopping (halt at 3 on agreement, escalate to 9 only for cells the review flags), lower-median
reduction, and a full stability report. **Connector default:** cell-wise, seeded permutation, `k = 1`,
then review → value-of-information budget allocation over pivotal cells → re-score with
`withhold_prior=True` → render the disclosure; with a fresh-session pass on the top pivotal cells
offered as an explicit optional upgrade whose independence rung is recorded. **Both:** never a mean,
never a reduction over a polarised cell, and never a reliability coefficient over in-session
assertions labelled as inter-rater agreement. Every assertion carries its rung on the ladder
`in-session < fresh-session < distinct-model < distinct-human`; each rung removes a class of shared
cause and none removes them all except the last, and a statistic over rung-1 assertions is
**test–retest reliability**, not inter-rater reliability. Every analysis carries a `procedure` record
(traversal, k, seeds, prompt versions, model id, whether re-scoring withheld the prior) and a rendered
disclosure. The connector's isolation is honestly labelled **in-session isolation** — attenuation, not
elimination, because the transcript is shared — and the disclosure text is content, not code. The
headline stability statistic is the weight-free **dominance survival rate**, with τ and top-1 churn
secondary and computed only when weights have been declared.

**ADR-0019 — All LLM access goes through the local `aix` facade.**
The deployed runtime never touches a provider SDK directly; `aix` is the single chokepoint for model
configuration, credential resolution, aliases and scoped overrides. `rubricator.mcp` must **never**
import `rubricator.agent`, and a subprocess import test asserts that neither `aix` nor `litellm`
appears in `sys.modules` after importing the MCP layer — that test is the mechanical enforcement of
ADR-0003's "no tool may require a model", and it is worth more than the rule written in prose. The
connector installs with no LLM dependency; `pip install "rubricator[agent]"` adds `aix`. Six facade
gaps must be filed against `aix` and two of them closed before ADR-0008's variance work is possible:
a completion primitive that does not discard the response, a concurrent sampling primitive, membership
enforcement in `constrained_answer`, provider-enforced structured output, documented seed support with
capability probing, and error propagation in `batch_chat`. Every one is a facade gap, not a capability
gap — LiteLLM underneath already supports all of it [110][111] — which is what makes fixing them in
`aix` rather than wrapping around them obviously correct.

### Schema requests to comparanda (per ADR-0002, requests — not changes rubricator can make)

| Request | Why | From |
|---|---|---|
| Criteria carry a **structured definition** (objective, question, scale anchors, `evidence_rule`, `missing_rule`, `exclusions`), not free text | ADR-0006's honesty guarantee is *defined* by the criterion and *exercised* by the cell; today it is only expressible at the cell level, which is the wrong place | §1 |
| Criteria sets are **versioned**, and every measure records the criterion version it was scored against | ADR-0016. Cheap now, impossible to retrofit honestly later | §1 |
| Criteria carry **provenance** (user-stated / derived-from-span / agent-proposed), and **rejected** criteria with reason codes are part of the analysis | The criteria-level application of the discipline the schema already applies to values and to missing cells | §1 |
| Assertions carry `authorKind`, `independence`, `perturbation`; analyses carry a `procedure` record; `'mode'` joins the reduction enum | Five draws of one model must never render as five raters. `independence` is the single most important field in this table | §4 |
| Evidence references carry `stance` and `sourceType`, plus `derivedFrom`, `quoteHash` and a tool-written `check` | Contradicting evidence is currently unrepresentable and therefore uncountable — the most damaging citation failure in a decision matrix | §5 |
| Confirm the criterion `preference` (direction) field, and the `rounds` proposal from comparanda's own agreement research | Dominance and veto screening are not definable without a direction of preference; a replication pass maps onto a round exactly | §1, §4 |
| A `missing` reason for `insufficient_evidence_to_discriminate` | The negative case of the pairwise escalation rule (§3) has no existing code | §3 |

---

## Open questions

What the research did not settle, and what would settle it. Ordered by value.

1. **How much of cell-wise isolation survives a shared transcript?** The connector cannot make a
   genuinely fresh call, so §4.3's flagship mitigation has an unknown magnitude, and this limit is
   nowhere in the current ADRs. **Settled by** harness arms `cellwise` vs `in_session_isolated`. This
   is the highest-value unknown in the project and it costs a few dollars.
2. **Does withholding the prior score actually reduce anchoring in-session?** Predicted by the
   anchoring and self-correction literature [66][67], untested. **Settled by** arms
   `in_session_isolated` vs `in_session_visible`. If it does not reduce the exact-repeat rate, the
   mitigation is theatre and should be dropped rather than shipped.
3. **Does traversal order flip the non-dominated set on a real matrix?** [1] notes nobody has
   published τ on induced rankings; the weight-free version — Pareto-set churn — is even less studied.
   **Settled by** running the harness on the public fixtures.
4. **Does anchoring help *LLM* judges specifically?** Every strong LLM-judge system inspected uses
   per-level descriptors [16][17] and none publishes an ablation isolating them; the +0.1 ICC figure
   is from human assessors on overlapping ranges [14]. **Settled by** the cheapest experiment in this
   document: same criteria, same corpus, anchors on vs off, measure inter-run agreement and accuracy.
   Run it before writing anchors at scale for anything.
5. **Is 1–5 with k repeats really as good as a bare 1–10 for us?** §2's reconciliation is reasoning
   over two studies that measured different quantities [20][21]. **Settled by** a sixth harness arm:
   does median-of-3 on the anchored 1–5 match or beat a bare 1–10 against the gold fixture?
6. **Does the `unknown`-vs-`low` rule survive contact with a real corpus?** ClimateX predicts the
   model will resist emitting `unknown` [25]. Whether the rule is followable, or produces an unusably
   sparse matrix, is an empirical question the fixture suite answers — and it is the behaviour BRIEF.md
   says is most likely to erode under prompt edits.
7. **Which core MCP client features are actually supported by the target clients?** The docs site's
   per-client matrix for prompts / resources / elicitation could not be obtained; the surviving matrix
   covers only extensions. **Settled by** a throwaway server that logs `clientCapabilities` from Claude
   Desktop, Claude Code and a claude.ai connector — a one-afternoon experiment that should be the
   first thing Phase 3 does, because the `frame_confirm` fallback path either matters enormously or
   not at all depending on the answer.
8. **Where does a citation `check` live when an analysis is shared?** A check is only meaningful
   relative to a resolver and a moment; a stale one travelling inside the JSON to a reader with a
   different corpus will mislead. This is comparanda's call and it interacts with their persistence
   ADR. The lean here is *persisted, with `checkedAt` and `checkerVersion` shown in the UI*, because a
   standalone bundle with no resolver still needs to show something.
9. **Do the escalation thresholds and the fuzzy-match threshold hold?** 60% compression, 1-level
   spread on 30% of cells, 70% evidence coverage, and a 2% edit-rate budget are all **reasoning, not
   findings**. **Settled by** the fixture corpus: for the escalation rule, keep the threshold below
   which pairwise stops changing the induced ranking; for the fuzzy threshold, measure false-anchor
   rate as it rises.
10. **Do synthetic coupling probes work when alternatives are documents?** RADAR's probes are generated
    *responses* [7]; our alternatives are real things described by real sources, so the probes would be
    described alternatives with no evidence behind them. Whether coupling measured on evidence-free
    probes predicts coupling on evidence-backed cells is untested. **Settled by** running both on one
    fixture and correlating.
11. **Does a model interrogating its own value function via the indifference probe have any validity?**
    The probe asks about preferences; the preferences that matter are the user's. The
    model-as-pre-filter recommendation is a hedge, not an answer. **Settled by** agreement between model
    probe verdicts and user probe verdicts across a fixture set.
12. **Does adaptive early stopping distort the ordinal distribution?** Stopping rules are validated
    against accuracy on tasks with a single correct answer [58][59]. Stopping early on agreement
    systematically under-samples the tail of a cell's level distribution — precisely the part that
    determines the `polarised` flag. Needs its own harness arm before the deployed default is fixed.
13. **How many fixtures does conformal calibration need at 5 levels?** Neither available paper reports
    a minimum calibration size for a 5-level ordinal [56][57]. A pilot on 100 fixture cells determines
    whether per-cell intervals are a phase-4 or a phase-6 feature.
14. **Is sycophancy a real risk at the step-4 checkpoint?** It is where the user states preferences,
    and models bend toward stated preferences [51]. No study of sycophancy in *rubric* judging was
    found. **Settled by** a cheap ADR-0008 test: identical corpus, two confirmation transcripts
    expressing opposite priors, measure score divergence.
15. **Does corpus normalisation break span checkability?** If ingestion cleans documents, offsets index
    the cleaned text and not the source a reader opens (§6). **Settled by** a Phase 1 decision, not an
    experiment — cite into a persisted normalised rendition served as an MCP resource, or maintain an
    offset map back to the source. Either is fine; leaving it undecided is not.
16. **Sources that could not be verified.** Several load-bearing quotations sit behind paywalls or bot
    protection and are marked at the point of use in the section files: Jonsson & Svingby's
    rubric-reliability conclusion and study count [13], Stevens 1946 (paraphrased, not quoted) [53],
    ICD 203 and the IPCC uncertainty guidance note (both HTTP 403, described from corroborating
    secondary sources) [27], Keeney & Raiffa 1976's exact property list, the ISPOR checklist [10], and
    the even-swaps and consequence-table fragments [11][12]. Their bibliographic metadata is confirmed;
    someone with library access should check the quotations before these are treated as citable.

---

## REFERENCES

1. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](./scoring-order-effects.md) — in this repository
2. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf)
3. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985)
4. [Selecting Attributes to Measure the Achievement of Objectives — Keeney & Gregory (2005), Operations Research 53(1):1–11](https://doi.org/10.1287/opre.1040.0158)
5. [An Introductory Guide to Multi-Criteria Decision Analysis (MCDA) — UK Government Analysis Function](https://analysisfunction.civilservice.gov.uk/policy-store/an-introductory-guide-to-mcda/)
6. [Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences — Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran & Arawjo (2024), UIST '24](https://arxiv.org/abs/2404.12272)
7. [RADAR: Rubric-Aware Dependency and Redundancy Analysis for LLM-as-Judge Evaluation — Singh, Davari & Mashhadi (2026)](https://arxiv.org/abs/2608.01810)
8. [Rethinking Rubric Generation for Improving LLM Judge and Reward Modeling for Open-Ended Tasks — Shen, Qiu, Whitehouse et al. (2026)](https://arxiv.org/abs/2602.05125)
9. [The Effects of Splitting Attributes on Weights in Multiattribute Utility Measurement — Weber, Eisenführ & von Winterfeldt (1988), Management Science 34(4):431–445](https://doi.org/10.1287/mnsc.34.4.431)
10. [Multiple Criteria Decision Analysis for Health Care Decision Making — Emerging Good Practices: Report 2 of the ISPOR MCDA Task Force — Marsh, IJzerman, Thokala, Baltussen et al. (2016), Value in Health 19(2):125–137](https://doi.org/10.1016/j.jval.2015.12.016) — *full text not retrievable; quoted material obtained via search snippets*
11. [Smart-Swaps — A decision support system for multicriteria decision analysis with the even swaps method — Mustajoki & Hämäläinen (2007), Decision Support Systems 44(1):313–325](https://doi.org/10.1016/j.dss.2007.04.004) — *paywalled; quoted wording unverified*
12. [Smart Choices: A Practical Guide to Making Better Decisions — Hammond, Keeney & Raiffa (1999), Harvard Business School Press](https://openlibrary.org/isbn/9780875848570) — the source of the PrOACT frame
13. [The use of scoring rubrics: Reliability, validity and educational consequences — Jonsson & Svingby (2007), Educational Research Review 2(2):130–144](https://doi.org/10.1016/j.edurev.2007.05.002) — *record confirmed via Crossref; publisher returns HTTP 403 and elides the abstract, so quoted wording is **UNVERIFIED***
14. [Assessor experience, not rubric type, determines grading reliability in biosciences coursework — Chamberlain, Francis & Herrick (2026), Frontiers in Education](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2026.1729644/full)
15. [New data on Behaviorally Anchored Rating Scales (BARS): Vanishing high inter-rater reliability — Wiesen (2025), APA Division 5 *Score*](https://www.apadivisions.org/division-5/publications/score/2025/10/data-scales-reliability)
16. [Prometheus: Inducing Fine-grained Evaluation Capability in Language Models — Kim et al. (2023)](https://arxiv.org/abs/2310.08491)
17. [Autorubric: A Unified Framework for Rubric-Based LLM Evaluation — Rao & Callison-Burch (2026)](https://arxiv.org/abs/2603.00077)
18. [Optimal number of response categories in rating scales — Preston & Colman (2000), Acta Psychologica 104:1–15](https://www.sciencedirect.com/science/article/abs/pii/S0001691899000505)
19. [Does the number of response options matter? — Simms, Zelazny, Williams & Bernstein (2019), Psychological Assessment 31(4):557–566](https://pubmed.ncbi.nlm.nih.gov/30869956/)
20. [Grading Scale Impact on LLM-as-a-Judge: Human–LLM Alignment Is Highest on 0-5 Grading Scale — Li et al. (2026)](https://arxiv.org/abs/2601.03444)
21. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
22. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2) — *cite v2 specifically*
23. [Improve Your Estimations with the Equivalent Bet Test — Martin-Vegue (2019), describing Hubbard, *How to Measure Anything*](https://www.tonym-v.com/blog/2019/10/2/improve-your-estimations-with-the-equivalent-bet-test) — *verified for the mechanism only; reports no calibration-training statistics*
24. [Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback — Tian et al. (2023), EMNLP](https://arxiv.org/abs/2305.14975)
25. [ClimateX: Do LLMs Accurately Assess Human Expert Confidence in Climate Statements? — Lacombe et al. (2023)](https://arxiv.org/abs/2311.17107)
26. [GRADE & GRADE-CERQual — Mayo Clinic Evidence Synthesis Guide](https://libraryguides.mayo.edu/c.php?g=1136733&p=8514645)
27. [Intelligence Community Directive 203: Analytic Standards — ODNI](https://www.intel.gov/assets/documents/intelligence-community-directives/ICD_203.pdf) — *HTTP 403 to automated fetch; described from two independent secondary summaries*
28. [Admiralty code (source reliability × information credibility)](https://en.wikipedia.org/wiki/Admiralty_code)
29. [Verification of forecasts expressed in terms of probability — Brier (1950), Monthly Weather Review 78(1):1–3; definitions and skill score summarised at](https://en.wikipedia.org/wiki/Brier_score)
30. [A new vector partition of the probability score — Murphy (1973), Journal of Applied Meteorology 12(4):595–600](https://en.wikipedia.org/wiki/Brier_score)
31. [Mitigating Bias in Calibration Error Estimation — Roelofs, Cain, Shlens & Mozer (2022), AISTATS](https://arxiv.org/abs/2012.08668)
32. [Judgment under Uncertainty: Heuristics and Biases — Tversky & Kahneman (1974), Science 185(4157):1124–1131; anchoring persistence summarised at](https://en.wikipedia.org/wiki/Anchoring_effect)
33. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — Zheng, Chiang, Sheng et al. (2023), NeurIPS](https://arxiv.org/abs/2306.05685)
34. [Aligning with Human Judgement: The Role of Pairwise Preference in Large Language Model Evaluators — Liu, Zhou, Guo et al. (2024), COLM](https://arxiv.org/abs/2403.16950)
35. [Pairwise or Pointwise? Evaluating Feedback Protocols for Bias in LLM-Based Evaluation — Tripathi, Wadhwa, Durrett et al. (2025)](https://arxiv.org/abs/2504.14716)
36. [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation — Yagubyan (2026)](https://arxiv.org/abs/2606.13685)
37. [Comparative judgement as a research tool: A meta-analysis of application and reliability — Kinnear, Jones & Davies (2025), Behavior Research Methods 57(8):222](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246014/)
38. [Elo Uncovered: Robustness and Best Practices in Language Model Evaluation — Boubdir, Kim, Ermis, Hooker & Fadaee (2023)](https://arxiv.org/abs/2311.17295)
39. [Chatbot Arena leaderboard updates: from online Elo to Bradley–Terry MLE — LMSYS (2023)](https://lmsys.org/blog/2023-12-07-leaderboard/)
40. [On Extending the Bradley-Terry Model to Accommodate Ties in Paired Comparison Experiments — Davidson (1970), JASA 65:317–328](https://doi.org/10.1080/01621459.1970.10481082)
41. [MM algorithms for generalized Bradley–Terry models — Hunter (2004), Annals of Statistics 32(1):384–406](https://projecteuclid.org/journals/annals-of-statistics/volume-32/issue-1/MM-algorithms-for-generalized-Bradley-Terry-models/10.1214/aos/1079120141.full)
42. [Let Me Speak Freely? A Study On The Impact Of Format Restrictions On Large Language Model Performance — Tam, Wu, Tsai, Lin, Lee & Chen (2024), EMNLP Industry Track](https://aclanthology.org/2024.emnlp-industry.91/)
43. [Say What You Mean: A Response to 'Let Me Speak Freely' — .txt Engineering (2024)](https://blog.dottxt.ai/say-what-you-mean.html)
44. [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models — Geng, Cooper, Moskal et al. (2025)](https://arxiv.org/abs/2501.10868)
45. [Strict tool use — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
46. [Structured outputs — Anthropic developer documentation (2026)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
47. [Reasoning Model Is Superior LLM-Judge, Yet Suffers from Biases — Huang, Wu, Yang & Arase (2026)](https://arxiv.org/abs/2601.03630)
48. [Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models — Norman, Rivera & Hughes (2026)](https://arxiv.org/abs/2606.19544)
49. [Style Outweighs Substance: Failure Modes of LLM Judges in Alignment Benchmarking — Feuer, Goldblum, Datta et al. (2024), ICLR 2025](https://arxiv.org/abs/2409.15268)
50. [LLM Evaluators Recognize and Favor Their Own Generations — Panickssery, Bowman & Feng (2024)](https://arxiv.org/abs/2404.13076)
51. [Towards Understanding Sycophancy in Language Models — Sharma, Tong, Korbak et al. (2023)](https://arxiv.org/abs/2310.13548)
52. [Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models — Verga, Hofstatter, Althammer et al. (2024)](https://arxiv.org/abs/2404.18796)
53. [On the Theory of Scales of Measurement — Stevens (1946), Science 103(2684):677–680](https://doi.org/10.1126/science.103.2684.677) — *paywalled; paraphrased from secondary summaries, not quoted*
54. [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs — Xiong et al. (2024), ICLR](https://arxiv.org/abs/2306.13063)
55. [When LLMs Agree, Are They Right? Auditing Self-Consistency and Cross-Model Agreement as Confidence Signals — Ding (2026)](https://arxiv.org/abs/2607.08065) — *single-author preprint; weak evidence*
56. [Analyzing Uncertainty of LLM-as-a-Judge: Interval Evaluations with Conformal Prediction — Sheng, Liu, He, Zhao & Kang (2025), EMNLP](https://aclanthology.org/2025.emnlp-main.569/)
57. [Diagnosing LLM Judge Reliability: Conformal Prediction Sets and Transitivity Violations — Gupta & Kumar (2026)](https://arxiv.org/abs/2604.15302)
58. [Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs — Aggarwal, Madaan, Yang & Mausam (2023), EMNLP](https://arxiv.org/abs/2305.11860)
59. [Escape Sky-high Cost: Early-stopping Self-Consistency for Multi-step Reasoning — Li et al. (2024), ICLR](https://arxiv.org/abs/2401.10480)
60. [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs — Loo (2025)](https://arxiv.org/abs/2511.00751)
61. [Is there a general factor in ratings of job performance? A meta-analytic framework — Viswesvaran, Schmidt & Ones (2005)](https://pubmed.ncbi.nlm.nih.gov/15641893/)
62. [The Evaluability Hypothesis: An Explanation for Preference Reversals between Joint and Separate Evaluations of Alternatives — Hsee (1996)](https://pages.ucsd.edu/~cmckenzie/Hsee1996OBHDP.pdf)
63. [Sequential contrast effects in hiring and admission interviews — Radbruch & Schiprowski, CEPR/VoxEU (2024)](https://cepr.org/voxeu/columns/sequential-contrast-effects-hiring-and-admission-interviews)
64. [Lost in the Middle: How Language Models Use Long Contexts — Liu et al. (2024), TACL](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)
65. [Large Language Models Sensitivity to The Order of Options in Multiple-Choice Questions — Pezeshkpour & Hruschka (2023/2024)](https://arxiv.org/abs/2308.11483)
66. [Large Language Models Cannot Self-Correct Reasoning Yet — Huang et al. (2024), ICLR](https://arxiv.org/abs/2310.01798)
67. [Anchoring Bias in Large Language Models: An Experimental Study — Lou & Sun (2024)](https://arxiv.org/abs/2412.06593)
68. [Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks (2025)](https://arxiv.org/abs/2510.27106)
69. [Can LLM-as-a-Judge Reliably Verify Rubrics in Agentic Scenarios? (RuVerBench) (2026)](https://arxiv.org/pdf/2606.29920)
70. [Web Annotation Data Model — Sanderson, Ciccarese & Young, W3C Recommendation (2017)](https://www.w3.org/TR/annotation-model/)
71. [Fuzzy Anchoring — Hypothesis (2013)](https://web.hypothes.is/blog/fuzzy-anchoring/)
72. [Hypothesis client — selector type definitions in `src/types/api.ts` (2024)](https://github.com/hypothesis/client/blob/main/src/types/api.ts)
73. [Text Fragments — WICG Draft Community Group Report (2023)](https://wicg.github.io/scroll-to-text-fragment/)
74. [RFC 5147: URI Fragment Identifiers for the text/plain Media Type — Wilde & Duerst, IETF (2008)](https://www.rfc-editor.org/rfc/rfc5147.html)
75. [RFC 8118: The application/pdf Media Type — IETF (2017)](https://www.rfc-editor.org/rfc/rfc8118.html)
76. [Media Fragments URI 1.0 (basic) — W3C Recommendation (2012)](https://www.w3.org/TR/media-frags/)
77. [Citations — Claude Platform documentation, Anthropic (2025)](https://platform.claude.com/docs/en/build-with-claude/citations)
78. [Enabling Large Language Models to Generate Text with Citations (ALCE) — Gao et al. (2023), EMNLP](https://aclanthology.org/2023.emnlp-main.398/)
79. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
80. [AttributionBench: How Hard is Automatic Attribution Evaluation? — Li et al. (2024)](https://arxiv.org/abs/2402.15089)
81. [MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents — Tang, Laban & Durrett (2024)](https://arxiv.org/abs/2404.10774)
82. [HHEM-2.1-Open hallucination evaluation model — Vectara (2024)](https://huggingface.co/vectara/hallucination_evaluation_model)
83. [AlignScore: Evaluating Factual Consistency with a Unified Alignment Function — Zha et al. (2023), ACL](https://arxiv.org/abs/2305.16739)
84. [Evaluating Chunking Strategies for Retrieval — Chroma Research (2024)](https://www.trychroma.com/research/evaluating-chunking)
85. [Is Semantic Chunking Worth the Computational Cost? — Qu, Tu & Bao (2024)](https://arxiv.org/abs/2410.13070)
86. [Introducing Contextual Retrieval — Anthropic (2024)](https://www.anthropic.com/news/contextual-retrieval)
87. [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models — Günther et al. (2024)](https://arxiv.org/abs/2409.04701)
88. [PROV-O: The PROV Ontology — Lebo, Sahoo & McGuinness (eds.), W3C Recommendation (2013)](https://www.w3.org/TR/prov-o/)
89. [CiTO, the Citation Typing Ontology — Peroni & Shotton, SPAR Ontologies](https://sparontologies.github.io/cito/current/cito.html)
90. [Introduction to Primary Sources — History, Philosophy and Newspaper Library, University of Illinois](https://www.library.illinois.edu/hpnl/tutorials/primary-sources/)
91. [Missing Counter-Evidence Renders NLP Fact-Checking Unrealistic for Misinformation — Glockner, Hou & Gurevych (2022), EMNLP](https://arxiv.org/abs/2210.13865)
92. [approx-string-match-js: bit-parallel approximate string matching (Myers) — Knight](https://github.com/robertknight/approx-string-match-js)
93. [RAGAS: Automated Evaluation of Retrieval Augmented Generation — Es et al. (2023)](https://arxiv.org/abs/2309.15217)
94. [Model Context Protocol — Specification, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/)
95. [MCP — Deprecated Features registry, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
96. [MCP — Multi Round-Trip Requests (MRTR), revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
97. [MCP — Elicitation, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)
98. [MCP — Prompts, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)
99. [MCP — Tools, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
100. [MCP — Resources, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
101. [MCP — Tasks extension overview (2026)](https://modelcontextprotocol.io/extensions/tasks/overview)
102. [Tool search tool — Anthropic (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
103. [Writing effective tools for agents — with agents — Anthropic Engineering (2025)](https://www.anthropic.com/engineering/writing-tools-for-agents)
104. [RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation — Gan & Sun (2025)](https://arxiv.org/abs/2505.03275)
105. [Pricing — Anthropic (2026)](https://platform.claude.com/docs/en/about-claude/pricing)
106. [FastMCP — Elicitation (2026)](https://gofastmcp.com/servers/elicitation)
107. [FastMCP — Prompts (2026)](https://gofastmcp.com/servers/prompts)
108. [MCP Python SDK — official repository (2026)](https://github.com/modelcontextprotocol/python-sdk)
109. [LangGraph — Persistence (checkpointers, threads, stores) (2026)](https://docs.langchain.com/oss/python/langgraph/persistence)
110. [LiteLLM — Input Params for completion()](https://docs.litellm.ai/docs/completion/input)
111. [LiteLLM — JSON Mode and Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode)
112. [Connect Claude Code to tools via MCP — Anthropic Claude Code documentation](https://code.claude.com/docs/en/mcp)
