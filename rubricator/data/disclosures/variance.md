---
id: variance
title: How this comparison was produced, and what that means for reading it
version: 1
updated: 2026-10-13
placeholders:
  - scorings
  - traversal
  - order
  - independence
changelog:
  - 1 (2026-10-13) — first text (#101). States the procedure as recorded, what each step does and does not remove, the in-session limit, the test–retest label, and the human parallel with its sources. Claims no size for any mitigation, because none has been measured for this tool yet; the hypothesis is that a reader told the same effects bias human panels weighs the comparison instead of dismissing it.
---

## How this comparison was produced, and what that means for reading it

**What was done.** As recorded for this analysis:

- Scorings per cell: {scorings}
- Traversal: {traversal}
- Order: {order}
- Independence between the scorings of one cell: {independence}

Where nothing was recorded, a line reads "not recorded", and then nothing is known about this analysis's stability.

**What that removes, and what it does not.**

- A cell-wise traversal, where one was used, keeps a criterion from being scored in the same breath as the others. It does not stop the earlier scores from being in view: a judgement made after them can still lean on them.
- A shuffled order, where one was used, spreads whatever advantage comes from being judged first or last across the criteria, instead of handing it to the same one every time. It does not remove that advantage; it moves it around.
- When cells are scored inside one conversation, as they are when an assistant runs this analysis in your own session (rung `shared-context`), the isolation between them is **in-session isolation**. It attenuates carry-over from one cell to the next. It does not eliminate it, because every earlier cell is still in the shared transcript.
- With a single scoring per cell, this analysis carries **no measurement of its own stability**. With several, the spread between them measures how consistently one model repeats itself — **test–retest reliability**, not agreement between independent raters — and any agreement figure shown is labelled by the weakest independence rung among the scorings it was computed from.
- The size of what each of these steps changes in the scores has **not yet been measured** for this tool. Nothing here should be read as a claim that it has.

**Why it matters.** Scoring is a measurement, and a measurement made once is a single reading. Published work on model evaluators finds that scoring several criteria in one pass pulls the later ones toward the earlier ones, so that distinct criteria look more alike than they are [1], and that repeat runs of the same evaluator disagree with themselves [2].

**Human panels show the same effects, and have been measured doing so for decades.** When one rater scores someone on every dimension, the correlations between those dimensions come out inflated — the halo effect — by roughly a third in supervisors' ratings and by more in peers' [3]. Which of two options people prefer can reverse depending on whether they see the options side by side or one at a time [4]. An interviewer's recommendation for a candidate depends on how strong the candidate just before was, and moves away from it — a contrast effect [5]. This is not a claim that a machine evaluator is uniquely unreliable. It is a claim that any single pass of any evaluator is a single measurement.

**How to read it anyway.** Treat a one-level difference on a single criterion as not meaningful. Read the shape of a row — where the highs and lows fall — rather than any total. A blank cell says why it is blank: "the sources are silent" is a finding about the sources, not a middling score.

### Sources

1. Stureborg, Alikaniotis & Suhara (2024). [Large Language Models are Inconsistent and Biased Evaluators](https://arxiv.org/abs/2405.01724).
2. [Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks](https://arxiv.org/abs/2510.27106) (2025).
3. Viswesvaran, Schmidt & Ones (2005). [Is there a general factor in ratings of job performance? A meta-analytic framework for disentangling substantive and error influences](https://pubmed.ncbi.nlm.nih.gov/15641893/). Journal of Applied Psychology.
4. Hsee (1996). [The Evaluability Hypothesis: An Explanation for Preference Reversals between Joint and Separate Evaluations of Alternatives](https://pages.ucsd.edu/~cmckenzie/Hsee1996OBHDP.pdf). Organizational Behavior and Human Decision Processes.
5. Radbruch & Schiprowski (2024). [Sequential contrast effects in hiring and admission interviews](https://cepr.org/voxeu/columns/sequential-contrast-effects-hiring-and-admission-interviews). CEPR VoxEU.
