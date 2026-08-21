# ADR-0008: The agent needs an evaluation suite, and it is not optional

- **Status:** accepted
- **Date:** 2026-08-18

## Context
"Did the agent do a good job?" is nearly unfalsifiable for this task — there is no ground-truth
matrix for most real questions. That is precisely why it will otherwise be assessed by vibes, and
regressions will ship unnoticed.

## Decision
Build an evaluation suite alongside the agent, not after it. Evaluate what can actually be checked:

- **Schema validity** — does the output validate, every time. Deterministic, cheap, non-negotiable.
- **Citation faithfulness** — does each evidence span actually contain what the justification
  claims? Checkable by string containment and by an LLM-judge for paraphrase, and it catches the
  single most damaging failure mode.
- **Calibration** — on fixtures with known answers, do high-confidence cells outperform
  low-confidence ones? A model whose confidence does not track accuracy is worse than one with no
  confidence field at all.
- **Instruction adherence** — when told to leave criteria pending, does it? When told to use given
  criteria, does it invent extras?
- **Stability** — same input twice: how much do scores move? Report it; users need to know whether
  a one-point difference means anything.
- **Refusal to guess** — on fixtures with deliberately absent evidence, does it emit `unknown`
  rather than a plausible number? Test this explicitly; it is the behaviour most likely to erode.

Fixtures use public domains only, mirroring `comparanda`'s ADR-0016 — and are a shared asset
between the repos.

## Consequences
Meaningful cost, and it is what makes the prompts improvable rather than merely changeable. Without
it, prompt edits are indistinguishable from prompt churn.

## Amendments

### 2026-08-21 — What the suite actually measures

**Deciders:** Thor Whalen

Round-1 research left the decision above intact — the suite is mandatory, and it evaluates what can
be checked — and found four defects in the *list*. Two of the six checks are passed perfectly by the
worst possible agent, one of them cannot be computed at all, the citation check has no tiers and no
fixtures, and the harness that would produce the numbers was never specified. All four are additions
and corrections inside this ADR's own remit, so this is an amendment rather than a superseding ADR.

**Every check below is a metric, not a vibe, and each names the tier it runs at:** *CI* on every
commit and every prompt edit (deterministic, no model, no network); *nightly* on the fixture corpus
with a small CPU checker; *release* on the full corpus, reported against the previous release.

---

**1. Two checks are passed by a degenerate agent, and each gains a counter-metric.**

**Stability** as written is maximised by an agent that emits `3` for every cell. **Refusal to guess**
is maximised by one that leaves every cell `missing`. This is not a hypothetical: the largest
LLM-judge meta-evaluation to date (21 judges, 118 runs, ~541k judgements) names the trap
*reliability without validity* and reports two judges with near-perfect test–retest (0.992, 0.988)
and severe position bias (0.192, 0.125) [1]. As written, two release gates certify the worst agent
we could ship.

Each gains a paired discrimination counter-metric, and **the build fails on the pair, never on the
member**: high stability *and* low discrimination fails; a high blank rate *and* high evidence
availability fails. `stability_report` returns the per-criterion level histogram, the compression
fraction and the blank density, so both counter-metrics are computed from what the tool already
emits rather than from a second pass.

Three method corrections come with it, all from the same source [1]: **chance-corrected agreement**
(κ) rather than raw exact match, **AB/BA position-swap testing** on every stability arm, and a
**paradox audit** — any run whose reliability rises while its discrimination falls is reported, not
averaged away. The protocol's floor is **≥3 runs over ≥2 contrasting corpora**; a single corpus
measures the corpus.

**Blank metrics are named for the behaviour, not for the reason code.** `qualified_blank_rate` counts
blanks that carry a reason and a record of what was searched; `blank_inflation_rate` counts blanks
emitted where evidence was in fact available. `not-evidenced` and `indeterminate` are **counted
separately and never pooled** — a searched-and-silent cell and an assessor who could not determine
are two different observations, and the counter-metric defends against their union, not against
either alone. Naming a metric after a reason code makes the next code rename a metric rename;
naming it after the behaviour does not.

**2. The calibration check is split, because as written it is not calibration.**

"Do high-confidence cells outperform low-confidence ones" is a *discrimination* test. No proper
scoring rule can be computed on `confidence`, which is an ordinal evidence-quality label (ADR-0012).
Two families replace the one bullet.

**Family A — discrimination over `confidence`** (delivered measure; this family carries the release
gate):

- accuracy by confidence level, each with a **Wilson interval** — three levels means small per-level
  n, and a bare proportion will read as precision it does not have;
- a **monotone-trend test** across the three levels, which is the actual claim being made;
- **`confidence_inflation_rate`** — cells at `high` whose evidence does not support the level — as a
  release gate;
- **`blank_inflation_rate`** — defined above, and Family A's degradation in the blank direction; the
  research spells it `unknown_preference_rate`, and the behaviour-first name supersedes that
  spelling — together with **`low_confidence_laundering_rate`**, which is the same rule degrading in
  the opposite direction.

**Family B — proper scoring over `certainty`** (evaluation-run measure, per ADR-0012; it never
appears in a delivered analysis): **Brier** [6] with **Murphy's decomposition** into reliability,
resolution and uncertainty [7] — the decomposition is the informative part, not the scalar; a
**skill score** against a base-rate forecast; a **reliability curve binned on the allowed values**,
which the closed value set makes exact; **ECE reported second**, behind a minimum-n gate, because
ECE's binning is the largest source of estimator bias [5]; and **AUROC** as the discrimination
companion. Family B is a report, not a gate — a self-reported probability is admissible evidence
about the procedure only where something checks it [4].

Three rules bind both families. **Bootstrap by analysis, never by cell** — cells within one analysis
are not independent draws, and cell-level resampling manufactures intervals. **Never average
`confidence`**; report the distribution. **Family A is the regression detector for the shipped
product**, because it runs over a measure delivered analyses actually carry.

**3. Citation checking gets tiers, and precision is separated from recall.**

The empirical case is not in doubt: an audit of four generative search engines found 51.5% of
generated sentences fully supported by their citations and 74.5% of citations supporting their
paired statement [9]. One wrong citation in four, inside a well-formatted matrix, is worse than none,
because the format certifies the content.

| Metric | Tier | Gate |
|---|---|---|
| `citation_resolvability` | CI, deterministic | must be 1.0 |
| `quote_verbatim_rate` (verdict ∈ {exact, normalised}) | CI, deterministic | 1.0 for text sources |
| `numeric_support_rate` | CI, deterministic | 1.0 on fixtures |
| `unsupported_high_confidence_rate` | CI, deterministic | must be 0 — this *is* ADR-0006 |
| `citation_precision`, `citation_recall`, `contradiction_rate` | nightly, small NLI checker | no regression vs previous release |
| `source_type_accuracy` | nightly, fixtures with labelled provenance | no regression |
| `counter_evidence_missed@k` | release, adversarial retrieval + judge | report, never gate |

Precision and recall are **separate numbers**, per ALCE's definitions verbatim — cited passages
concatenated as premise, recall binary per statement, precision binary per citation with the
irrelevance test [8] — over atomic-claim decomposition [11]. Collapsing them hides the failure that
matters: a cell can cite three spans, one of which carries the claim.

The model-based checker is a **regression detector, not an oracle**. The published ceiling on
automatic attribution evaluation is roughly 80% macro-F1 [10], so it tracks deltas between prompt
versions and **never gates a release without a deterministic check underneath it**. It runs on a
small CPU model with no API key [12][13] — which is what lets it run in a public repository's CI
without secrets.

`counter_evidence_missed@k` is report-only by construction: it is the only probe that catches
confident cherry-picking, and it is also the noisiest thing in the suite. Gating on it would trade
the failure a well-cited matrix hides for a failure the harness invents.

**4. Three fixture families and seven harness arms.**

Fixtures, public-domain as required above: a **moved-text** fixture — the same document with a
paragraph inserted above the cited span, which must resolve to `moved`, never `stale`; a
**paraphrase** fixture — a faithful paraphrase, which the deterministic ladder must *not* mark
`exact` and the checker must mark supported, proving the two layers do different jobs; and a
**contradiction** fixture — a span saying the opposite, which the polarity trap should flag and the
checker should score as contradicted.

The harness has seven arms: the five of the owner's scoring-order document § 8 — cell-wise,
column-wise, row-wise, single-pass, and cell-wise shuffled — plus two that exist only because
rubricator has two runtimes. `in_session_isolated` runs one growing session where each turn returns
only an acknowledgement; `in_session_visible` runs the same session with the prior measures
restated. Arms 6 vs 1 measure how much of cell-wise isolation survives a shared transcript; arms
6 vs 7 measure whether withholding the prior actually works. **Neither question has an answer in the
literature, and both cost a few dollars** — which is the whole argument for running them.

---

**Two corrections recorded here because this ADR is where they bind.**

**Column correlation is a `traversal_leakage_diagnostic`, never a redundancy finding**, and the
tool's own output must carry that sentence. Correlated criteria are not redundant criteria:
preference independence can hold while measures covary, and the DCLG manual gives the worked
counterexample [3]. For an LLM-scored matrix the judge's own halo inflates inter-criterion
correlation from a human r ≈ 0.32 to r ≈ 0.98 [2], so an unexpectedly high value is evidence that
the traversal leaked context between cells — a fact about the *run*, not about the criteria. Shipping
the number without the sentence invites exactly the inference it disproves.

**`scipy` is a test-only extra, never a runtime dependency.** A 21-line pure-Python Kendall tau-b
reproduces `scipy.stats.kendalltau` to 2.2 × 10⁻¹⁶ on this project's data shape, so the coefficients
are vendored in `rubricator.stats` and `scipy` is used only to cross-check them in the test suite.
The MCP server installs fast and light; the evaluation suite's weight stays out of it.

**Evidence.** `docs/research/findings-method.md` — decision summary rows 3, 10 and 25, § 2, § 3,
§ 4.4, § 5 and § 7.9 (which settles this as an amendment rather than a separate metrics ADR);
`docs/research/sections/r5-evidence-citation.md` § 5.3 for the metric table and the fixture families;
`docs/research/sections/r4-variance-mitigation.md` § 5 for the `scipy` cross-check;
`docs/research/scoring-order-effects.md` § 8 for the five original harness arms.

1. [Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models — Norman, Rivera & Hughes (2026)](https://arxiv.org/abs/2606.19544)
2. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724)
3. [Multi-criteria analysis: a manual — Dodgson, Spackman, Pearman & Phillips (2009), Department for Communities and Local Government](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/7612/1132618.pdf)
4. [Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback — Tian et al. (2023), EMNLP](https://arxiv.org/abs/2305.14975)
5. [Mitigating Bias in Calibration Error Estimation — Roelofs, Cain, Shlens & Mozer (2022), AISTATS](https://arxiv.org/abs/2012.08668)
6. [Verification of forecasts expressed in terms of probability — Brier (1950), Monthly Weather Review 78(1):1–3](https://en.wikipedia.org/wiki/Brier_score)
7. [A new vector partition of the probability score — Murphy (1973), Journal of Applied Meteorology 12(4):595–600](https://en.wikipedia.org/wiki/Brier_score)
8. [Enabling Large Language Models to Generate Text with Citations (ALCE) — Gao et al. (2023), EMNLP](https://aclanthology.org/2023.emnlp-main.398/)
9. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
10. [AttributionBench: How Hard is Automatic Attribution Evaluation? — Li et al. (2024)](https://arxiv.org/abs/2402.15089)
11. [RAGAS: Automated Evaluation of Retrieval Augmented Generation — Es et al. (2023)](https://arxiv.org/abs/2309.15217)
12. [HHEM-2.1-Open hallucination evaluation model — Vectara (2024)](https://huggingface.co/vectara/hallucination_evaluation_model)
13. [MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents — Tang, Laban & Durrett (2024)](https://arxiv.org/abs/2404.10774)
