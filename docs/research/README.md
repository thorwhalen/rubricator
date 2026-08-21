# Research

This folder is the project's evidence base: the questions rubricator asked before writing code, the
working notes that answered them, and the synthesis that turned answers into decisions. A research
question is **not done** until it has an entry in a `findings-*.md` document *and* a recommended ADR
action — an answer nobody acted on is an answer the next session will ask again.

## How this works

```
briefs (the questions)  ->  sections/ (the working notes, one per question)
                        ->  findings-*.md (the synthesis)
                        ->  ADR actions (the decisions)
```

Briefs pose questions and name candidate sources. Sections do the reading — each carries its own
evidence grade, its own citation audit and its own open questions, and each is written to be
readable alone. A findings document reconciles the sections where they disagree, states what to
**do**, and lists ADR actions. ADRs are immutable once accepted (ADR-0001), so research never edits
one: it recommends *confirm*, *amend*, *supersede*, or *new*, and a human settles it. All round-1 actions have been applied; the settled set is indexed at
[`docs/adr/README.md`](../adr/README.md).

Two conventions apply everywhere in this folder. Claims the literature supports are marked EVIDENCE
and cited to a span-checkable source; claims that are inference over evidence are marked
**(reasoning, not evidence)**. Vocabulary is comparanda's: **alternatives** (rows), **criteria**
(columns), **subject**, **measure** (stored: score, confidence), **encoding** (derived, view-layer),
**missing** (always with a reason).

**Evidence grades.** **strong** = multiple primary sources, replicated or converging. **moderate** =
one or two directly relevant primary studies, or primary studies that disagree and are reconciled by
reasoning. **weak** = practitioner convergence, a single preprint, or reasoning over adjacent
evidence. **reasoning** = no literature exists on the exact question; the recommendation is
engineering judgement, falsifiable by the ADR-0008 evaluation suite.

## Ledger

Round 1 (2026-08-18). `Brief` cites the question's origin; `Findings` cites where the answer lives.
All findings rows resolve to [`findings-method.md`](./findings-method.md) unless stated otherwise —
the § numbers are its sections, and the summary-table row numbers are given as `row N`.

| # | Question | Brief | Status | Findings | Evidence | ADR action |
|---|---|---|---|---|---|---|
| R0 | Does scoring order (column-wise vs row-wise vs cell-wise vs single-pass) change multi-criteria evaluations, for humans and for LLMs? | owner-initiated, predates `method.md` | **complete** | [`scoring-order-effects.md`](./scoring-order-effects.md) [1]; adopted and partly overridden in §"What the owner's scoring-order document settles" | strong (order changes scores); moderate (assimilation is the direction); weak (order flips the induced ranking) | new **ADR-0011**, new **ADR-0018**; **ADR-0008 amend** (its §8 experiment becomes an eval deliverable) |
| R1 | What method generates criteria? | `method.md` §1 | complete | §1, row 1 | strong | ADR-0005 **confirm** |
| R2 | How is criteria overlap detected *before* scoring? | `method.md` §1 | complete | §1, row 2 | strong (structural ladder, indifference probe); moderate (`depends_on`, coupling probes) | ADR-0005 confirm; new **ADR-0016** |
| R3 | Is correlating scored columns a redundancy test? | `method.md` §1 | **complete (negative result)** | §1, row 3 | strong | **ADR-0008 amend** — rename to a traversal-leakage diagnostic |
| R4 | How many criteria before a matrix stops being usable? | `method.md` §1 | complete | §1, row 4 — the binding constraint is splitting bias [8], not Miller 7±2 | moderate | ADR-0005 confirm |
| R5 | What must a criterion definition contain to be scoreable? | `method.md` §1 | complete | row 5 | strong | comparanda **schema request** (structured criterion definition) |
| R6 | Can criteria change after scoring has started? | emergent (not in the brief) | complete — criteria drift is documented [7] | §1, row 6 | moderate | new **ADR-0016** |
| R7 | What scale should the stored `score` measure use? | `method.md` §2 | complete | §2, row 7 | moderate | new **ADR-0012** (overrides [1] §6's "widen to 1–10") |
| R8 | Should criteria carry per-level descriptors? | `method.md` §2 | complete, with an open ablation | §2, row 8 | moderate | new **ADR-0012**; open Q4 |
| R9 | What does `confidence` mean? | `method.md` §2 | complete | §2, row 9 | strong | ADR-0006 **confirm**; enforcement rules into new **ADR-0012** |
| R10 | Is ADR-0008's calibration item computable as written? | `method.md` §2 | **complete (negative result)** | §2, row 10 | strong | **ADR-0008 amend** (split into two metric families); new **ADR-0012** |
| R11 | Pointwise or pairwise scoring? | `method.md` §3 | complete | §3, row 11 | moderate | new **ADR-0011** |
| R12 | When may pairwise be escalated at all, and how is it aggregated? | `method.md` §3 | partial — thresholds are reasoning | §3, row 12 | moderate (aggregation); reasoning (thresholds) | new **ADR-0011**; open Q9 |
| R13 | What traversal order should the agent use? | `method.md` §2 + [1] | complete | §3, row 13 | strong | new **ADR-0011** |
| R14 | Evidence first or score first? | `method.md` §3–§4 | complete | §3, row 14 | strong | new **ADR-0011** |
| R15 | Does structured output damage reasoning quality? | `method.md` §3 | **complete (negative result)** | §3, row 15 | strong | new **ADR-0013** |
| R16 | How many repeats, per runtime? | `method.md` §3 | complete | §4, row 16 | moderate | new **ADR-0018** |
| R17 | How are repeats reduced to one level? | `method.md` §2 | complete | §4.2, row 17 | strong | new **ADR-0011** |
| R18 | What is done with a polarised (bimodal) cell? | emergent | complete (simulation) | §4.2, row 18 | reasoning ([r4](./sections/r4-variance-mitigation.md) simulation) | new **ADR-0011** |
| R19 | What is the headline stability statistic? | `method.md` §2 + [1] §8 | complete | §4, row 19 | reasoning over [1] §8 | new **ADR-0018** |
| R20 | Are evidential confidence and procedural stability the same quantity? | `method.md` §2 | **complete (they are not)** | §4.1, row 20 | strong | ADR-0006 confirm; new **ADR-0012** |
| R21 | What locator format should an evidence reference use? | `method.md` §4 | complete | §5, row 21 | strong | new **ADR-0014** |
| R22 | Are Text Fragments (`#:~:text=`) a competing locator? | `method.md` §4 | **complete (no — isomorphic)** | §5, row 22 | strong | new **ADR-0014** |
| R23 | How should a corpus be chunked when the output must be cited? | `method.md` §4 | complete | §5, row 23 | strong | new **ADR-0014** |
| R24 | How is a citation checked with no model call? | `method.md` §4 | complete | §5, row 24 | strong | new **ADR-0014** |
| R25 | How is a citation checked *with* a model? | `method.md` §4 | complete | §5, row 25 | strong | **ADR-0008 amend** |
| R26 | What vocabulary distinguishes primary, secondary and own inference? | `method.md` §4 | complete | §5, row 26 | strong | new **ADR-0015** |
| R27 | What actually prevents inference being presented as source? | `method.md` §4 | complete | §5, row 27 | strong | new **ADR-0015** |
| R28 | Does ADR-0004 survive reading `aw_agents`? | `method.md` §5; BRIEF deliverable 4 | **complete (it does not)** | §6, row 28; [r7](./sections/r7-local-ecosystem.md) | strong (source read) | **ADR-0004 supersede** → new **ADR-0009** |
| R29 | What should the MCP surface be built on? | `method.md` §5 | complete | §6, row 29; §7.5 | strong | new **ADR-0009** |
| R30 | Is MCP sampling a legitimate escape hatch from "no tool may require a model"? | `method.md` §5 | **complete (no — deprecated in revision 2026-07-28 [12])** | §6, row 30 | strong | new **ADR-0010** |
| R31 | What retrieval mechanism is compatible with a key-free connector? | `method.md` §5 | complete | §6, row 31; §7.6 | strong | new **ADR-0010** |
| R32 | Long context or retrieval, and where is the crossover? | `method.md` §5 | complete | §6, row 32 | strong (arithmetic over published prices) | new **ADR-0010** |
| R33 | How is the ADR-0005 step-4 checkpoint implemented? | `method.md` §5 | complete, pending client-capability check | §6, row 33 | strong | **ADR-0005 amend**; open Q7 |
| R34 | How does a checkpoint survive a session boundary? | `method.md` §5 | complete | §6, row 34 | strong | new **ADR-0017** |
| R35 | How granular should the tool surface be, and how many tools? | `method.md` §5; BRIEF deliverable 2 | complete | §"Proposed MCP tool surface", row 35 | strong | new **ADR-0009** |
| R36 | Prompt bundle and MCP server — one artifact or two? | `method.md` §5 | **complete (one)** | §6, row 36 | strong | **ADR-0007 amend** |
| R37 | How does the deployed runtime reach a model? | `method.md` §5 | complete | §6, row 37; [r7](./sections/r7-local-ecosystem.md) | strong (source read) | new **ADR-0019** |
| R38 | Which agent-facing dev skills does the recurring work need? | `method.md` §6 | **partial** — 2 of 6 written (`rubricator-dev-prompt-change`, `rubricator-dev-tool-contract`); the four analysis-workflow skills the brief names are not written | — | — | none yet; carried as an open question below |

**Not yet asked.** `method.md` §6 is the only brief section without a section file. Every other brief
section has one, and every section has landed in [`findings-method.md`](./findings-method.md).

## Briefs

- [`method.md`](./method.md) — comparison method and prompting. Six numbered questions: criteria
  elicitation, scoring/calibration/bias, LLM-as-judge practice, evidence and citation, agent
  architecture, dev skills. Names candidate sources; the sections decide whether they hold up.

## Findings

- [`findings-method.md`](./findings-method.md) [2] — the synthesis of round 1. Opens with a 37-row
  summary table an implementer can work from alone, states what [1] settles and what this document
  overrides, resolves nine inter-section conflicts, proposes the MCP tool surface (19 tools, 11
  minimum viable), and consolidates every ADR action and schema request. 112 references.
- [`scoring-order-effects.md`](./scoring-order-effects.md) — **Thor Whalen (2026)**, *"Does Scoring
  Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs?"*
  [1]. A completed research result that predates the brief and is treated as a first-class input, not
  a note. Establishes cell-wise / one-criterion-per-generation scoring as the default, catalogues
  mitigations by evidence strength, and specifies a five-arm measurement experiment with a decision
  rule stated in advance. Evidence: **strong** that order and grouping change LLM scores;
  **moderate-to-strong** that the direction is assimilation toward earlier scores; **weak/absent**
  that order flips the ranking of alternatives on a decision matrix specifically — which is why the
  experiment exists. Produced new ADR-0011 (scoring protocol) and new ADR-0018 (variance-mitigation
  policy per runtime), and its §8 experiment becomes an ADR-0008 deliverable, extended from five arms
  to seven because rubricator has two runtimes. Its central finding is now triple-corroborated: a
  second group measured criterion-order effects of up to 0.80 points on a 5-point scale, with 56 of
  60 (judge, criterion) tests significant [4]. Its follow-up work is
  [`sections/r4-variance-mitigation.md`](./sections/r4-variance-mitigation.md). Seven of its
  recommendations are adopted, three are not — see §"What the owner's scoring-order document settles"
  in the findings for the itemised list. *(Renamed from a filename carrying the full title, spaces
  and an em-dash; the title is unchanged and the original filename is recorded in the document.)*

## Sections (working notes)

One per brief question. Each is self-contained: research questions, evidence grade, citation audit,
bottom line, findings, and its own open questions and references.

- [`r1-criteria-elicitation.md`](./sections/r1-criteria-elicitation.md) — value-focused thinking [6]
  for generating criteria, the DCLG manual §5.4.4 [5] for checking them, the emitted objective ladder, why
  correlating scored columns is the wrong redundancy test, and the ten fields a criterion definition
  needs. *Evidence: strong core, moderate on the criteria-count range.*
- [`r2-rubrics-and-calibration.md`](./sections/r2-rubrics-and-calibration.md) — scale granularity
  (1–5 ordinal, buy discrimination with repeats not width), per-level descriptors at 1/3/5 written as
  evidence conditions, what `confidence` means and its prior art, and which calibration metrics are
  computable on an ordinal label. *Evidence: moderate — its two primary sources disagree and are
  reconciled by reasoning.*
- [`r3-llm-as-judge.md`](./sections/r3-llm-as-judge.md) — pointwise vs pairwise, the bias catalogue,
  Bradley–Terry aggregation, self-consistency economics, and structured output without losing
  reasoning quality. *Evidence: strong on biases and structured output, moderate on
  pointwise/pairwise, weak on the escalation thresholds.*
- [`r4-variance-mitigation.md`](./sections/r4-variance-mitigation.md) — the follow-up to [1]: what
  each runtime should actually do about traversal and sampling variance, ordinal reduction rules, the
  independence ladder, the polarised-cell refusal, and the seven-arm harness. *Evidence: moderate;
  the connector-specific design is engineering reasoning, and two results are simulations run for the
  section rather than published findings.*
- [`r5-evidence-citation.md`](./sections/r5-evidence-citation.md) — the W3C Web Annotation selector
  profile [11], keeping chunking out of the citation path, the deterministic eight-step citation
  check, and the source-type plus stance vocabulary. The empirical case for the whole policy: an
  audit of four deployed generative search engines found only 74.5% of citations actually supported
  their paired statement [9]. *Evidence: strong — primary specifications and a large
  attribution-metrics literature; moderate on chunking.*
- [`r6-mcp-and-agent-architecture.md`](./sections/r6-mcp-and-agent-architecture.md) — what the
  current MCP revision offers, tool granularity, prompts-as-content, retrieval vs long context, and
  checkpoints across a session boundary. *Evidence: strong — read from the specification rather than
  summaries; weakest on per-client feature support.*
- [`r7-local-ecosystem.md`](./sections/r7-local-ecosystem.md) — reading the local `aw_agents`, `aix`,
  `py2mcp` and `oa` packages. ADR-0004 survives on language and fails on framework. *Evidence: strong
  — every claim comes from reading source, tests and packaging metadata.*

## Review

- **Phase 0 review candidates** — an **incomplete** adversarial review of the round-1
  recommendations across both repositories. Canonical copy lives in the companion repo at
  `comparanda: docs/research/phase0-review-candidates.md`; there is deliberately no second copy
  here to drift. 77 candidates raised, 21 adjudicated and all 21 refuted, 56 never adjudicated.
  Its measured precision is low — entries are questions to check, not findings.

## Open questions

Carried forward. Ordered by value; the first three are the cheap experiments that unblock the most.

1. **How much of cell-wise isolation survives a shared transcript?** The connector cannot make a
   genuinely fresh call, so the flagship connector mitigation has unknown magnitude. *Settled by*
   harness arms `cellwise` vs `in_session_isolated`. Highest-value unknown in the project; costs a
   few dollars.
2. **Does withholding the prior score reduce anchoring in-session?** Predicted, untested. *Settled
   by* arms `in_session_isolated` vs `in_session_visible`. If it does not reduce the exact-repeat
   rate, the mitigation is theatre and should be dropped rather than shipped.
3. **Does traversal order flip the non-dominated set on a real matrix?** [1] notes nobody has
   published Kendall's tau on induced rankings; the weight-free version (Pareto-set churn) is less
   studied still. *Settled by* running the harness on the public fixtures.
4. **Does anchoring help *LLM* judges specifically?** Every strong LLM-judge system inspected uses
   per-level descriptors; none publishes an ablation isolating them. *Settled by* the cheapest
   experiment available — same criteria, same corpus, anchors on vs off. Run it before writing
   anchors at scale.
5. **Is 1–5 with k repeats really as good as a bare 1–10 here?** The reconciliation is reasoning over
   two studies that measured different quantities [3][10]. *Settled by* a harness arm.
6. **Does the `unknown`-vs-low-confidence rule survive a real corpus?** The rule may be unfollowable,
   or may produce an unusably sparse matrix. This is the behaviour BRIEF.md says is most likely to
   erode under prompt edits.
7. **Which core MCP client features do the target clients actually support?** The per-client matrix
   for prompts / resources / elicitation could not be obtained. *Settled by* a throwaway server that
   logs client capabilities — one afternoon, and it should be the first thing the connector phase
   does, because the checkpoint fallback path either matters enormously or not at all.
8. **Where does a citation check live when an analysis is shared?** A check is meaningful only
   relative to a resolver and a moment. **comparanda's call**, and it interacts with their
   persistence ADR.
9. **Do the escalation and fuzzy-match thresholds hold?** 60% compression, 1-level spread on 30% of
   cells, 70% evidence coverage, a 2% edit-rate budget — all reasoning, not findings. *Settled by*
   the fixture corpus.
10. **Do synthetic coupling probes work when alternatives are documents?** The published probes are
    generated responses; rubricator's alternatives are real things described by real sources.
11. **Does a model interrogating its own value function via the indifference probe have any
    validity?** The probe asks about preferences; the preferences that matter are the user's.
12. **Does adaptive early stopping distort the ordinal distribution?** Stopping early on agreement
    under-samples the tail — precisely the part that determines the polarised flag.
13. **How many fixtures does conformal calibration need at five levels?** Determines whether per-cell
    intervals are an early or a late feature.
14. **Is sycophancy a real risk at the step-4 checkpoint?** It is where the user states preferences.
    *Settled by* one cheap test: identical corpus, two confirmation transcripts expressing opposite
    priors, measure score divergence.
15. **Does corpus normalisation break span checkability?** *Settled by* a Phase 1 decision, not an
    experiment — cite into a persisted normalised rendition served as a resource, or maintain an
    offset map back to the source. Either is fine; leaving it undecided is not.
16. **Which quotations remain unverified?** Several load-bearing quotations sit behind paywalls or
    bot protection and are marked at the point of use in the section files. Bibliographic metadata is
    confirmed in every case; the wording is not. Someone with library access should check them before
    they are treated as citable. This is the one open question the project can close without spending
    a single model call.
17. **Which dev skills does the analysis workflow need (R38)?** `method.md` §6 asks for four
    agent-facing skills — running an analysis end to end, adding a criterion to an existing analysis,
    re-scoring one criterion against new evidence, auditing an existing analysis for overlap and thin
    evidence. None is written; the two skills that exist cover changing a prompt and changing a tool
    contract. *Settled by* doing the work, and best written after the first real end-to-end analysis
    so they describe a workflow that exists.

---

## REFERENCES

1. [Does Scoring Order (Column-wise vs Row-wise) Change Multi-Criteria Evaluations — for Humans, and for LLMs? — Whalen (2026)](./scoring-order-effects.md) — in this repository
2. [Findings — comparison method and prompting (2026)](./findings-method.md) — in this repository
3. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
4. [Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge — Xu, Hirasawa, Kozuno & Ushiku (2026)](https://arxiv.org/abs/2602.02219v2)
5. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf)
6. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985)
7. [Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences — Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran & Arawjo (2024), UIST '24](https://arxiv.org/abs/2404.12272)
8. [The Effects of Splitting Attributes on Weights in Multiattribute Utility Measurement — Weber, Eisenführ & von Winterfeldt (1988), Management Science 34(4):431–445](https://doi.org/10.1287/mnsc.34.4.431)
9. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
10. [Grading Scale Impact on LLM-as-a-Judge: Human–LLM Alignment Is Highest on 0-5 Grading Scale — Li et al. (2026)](https://arxiv.org/abs/2601.03444)
11. [Web Annotation Data Model — Sanderson, Ciccarese & Young, W3C Recommendation (2017)](https://www.w3.org/TR/annotation-model/)
12. [MCP — Deprecated Features registry, revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
