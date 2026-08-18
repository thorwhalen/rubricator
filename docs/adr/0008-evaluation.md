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
