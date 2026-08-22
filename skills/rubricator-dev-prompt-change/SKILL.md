---
name: rubricator-dev-prompt-change
description: Use when creating or editing any prompt in rubricator's docs/prompts/ — the elicitation, scoring, review and audit prompts. Covers the mandatory honesty clause every prompt must state in its own words, the version-and-changelog requirement, the rule that a prompt change requires an evaluation run before it lands, what the evaluation suite must check, and the review checklist for a prompt diff. Trigger on any edit under docs/prompts/, on "improve the propose-criteria prompt", on adding a new prompt, or when a prompt change is about to be committed.
metadata:
  audience: developers
---

# Changing a rubricator prompt

Prompts are **content, not code** (ADR-0003). Both runtimes serve the same files: the MCP layer
exposes them, the deployed agent loads them. Editing one changes the product's behaviour for
every user of both runtimes at once.

## The rule that makes prompts improvable rather than merely changeable

> When a prompt changes, the evaluation suite runs. That is the whole reason it exists.
> — `docs/prompts/README.md`, ADR-0008

Without an evaluation run, a prompt edit and prompt churn are indistinguishable. **Do not land a
prompt change with no evaluation evidence in the PR body**, even a partial one. If the suite
cannot run yet, say so explicitly in the PR and record what you checked by hand instead.

## Every prompt must state the honesty rule in its own words

Not by reference — in the prompt text, phrased for that prompt's job. From ADR-0006:

- **Prefer a qualified blank to a plausible guess.** The model will produce a number for any
  cell you ask about. The product's entire claim is that it doesn't.
- **Cite spans, not documents.** A citation nobody can check is not a citation.
- **Never present the agent's own inference as source material.** Mark authorship and source
  type — primary source, secondary summary, own inference — on everything.

This is stated as a hard requirement precisely because it is the behaviour most likely to erode
under prompt edits. A prompt that "cleaned up the boilerplate" by dropping the honesty clause is
a regression, whatever else it improved.

## Confidence means evidence quality, not model certainty

Hold to the ADR-0006 definitions in every prompt that touches confidence:

| Level | Means |
|---|---|
| high | directly supported by a cited source |
| medium | inferred from adjacent evidence |
| low | plausible reasoning with little support |

A prompt that lets "confidence" drift toward "how sure the model feels" breaks calibration
testing, because it is then measuring a different quantity than the one the fixtures score.

## Mechanics of a change

1. **Bump the version** in the prompt file's front matter and add a changelog entry saying what
   changed and *why* — a behavioural hypothesis, not a description of the diff
   ("expected to reduce invented criteria on sparse corpora").
2. **Run the evaluation suite** (ADR-0008) and paste the before/after into the PR:
   - **schema validity** — does output still validate, every time;
   - **citation faithfulness** — does each evidence span actually contain what the justification
     claims;
   - **calibration** — do high-confidence cells still outperform low-confidence ones;
   - **instruction adherence** — told to leave criteria pending, does it; told to use given
     criteria, does it invent extras;
   - **stability** — same input twice, how much do scores move;
   - **refusal to guess** — on fixtures with deliberately absent evidence, does it still emit
     a qualified blank rather than a plausible number, and does it still pick the *right* one
     (`not-evidenced` for silence, `indeterminate` for sources that conflict)?
3. **Read the refusal-to-guess number first.** If it moved down, the change is a regression no
   matter what else improved. That metric is the product.
4. **Check both runtimes.** A prompt tuned against one model's behaviour in the deployed agent
   still has to work when the connector hands it to whatever model the user's session is running.

## Reviewing a prompt diff

- Did the honesty clause survive, in this prompt's own words?
- Did the domain vocabulary survive — alternatives, criteria, subject, measure, missing? Never
  "items" or "features".
- Does it still elicit **definitions** alongside criteria? Undefined criteria get scored
  inconsistently, and that failure is invisible until someone tries to reproduce a score.
- Does it still surface ambiguity rather than resolving it silently?
- For scoring prompts: does it still ask for a span, and still permit "no span, therefore
  `not-evidenced`" as a first-class answer? And does it still distinguish that from
  `indeterminate`, which is what a cell with conflicting sources degrades to?
- Is any example in the prompt drawn from a **public** domain? ADR-0016 hygiene applies to
  prompt text exactly as it applies to fixtures, and prompts are where realistic examples get
  pasted in "just to make it concrete".

## Where things are

    docs/prompts/README.md                    the expected prompt set and their jobs
    docs/adr/0005-the-elicitation-pipeline.md  the stages
    docs/adr/0006-evidence-and-honest-uncertainty.md  the honesty rule, verbatim
    docs/adr/0008-evaluation.md               what the suite checks and why
    docs/research/findings-method.md          the research behind the elicitation design
