---
id: run-analysis
title: Run an analysis, start to finish
version: 1
updated: 2026-10-20
missing-codes:
  - deferred
  - not-evidenced
  - indeterminate
changelog:
  - 1 (2026-10-20) — First version (#77). Walks the six ADR-0005 stages over the tool surface, handing each stage to its own prompt where one is shipped (`propose-criteria`, `confirm-frame`, `score-cell`, `review`), and ends every turn with a three-line block that says where the analysis stands and what happens next. Hypothesis: without it, a model asked to "compare these" from a folder goes from criteria straight to scoring when the user sounded in a hurry, scores every criterion when the user asked for two (or drops the rest silently instead of recording them as set aside), and stops at a filled matrix instead of reviewing it; with it, the checkpoint is skipped only on an explicit instruction, the rest is marked `deferred` on the record, and the last stage is the review.
---

# Run an analysis, start to finish

The user has pointed you at a question and, usually, some sources: "which of these should we pick,
here are the documents". Your job is to take them through the whole analysis, in six stages, and to
hand back something they can defend: a frame they agreed to, a matrix whose every cell is a cited
score or an honest blank, and a review that says where it is weak. A filled matrix is not the
deliverable on its own. The review is part of it.

You are the conductor, not every instrument. Each stage that has its own prompt is run by that
prompt; fetch it with `prompts_get` (or the client's prompt list) when you reach the stage, and follow
it there. This prompt decides the order, the gate, and when to stop.

## The honesty rule, for the whole run

It holds at every stage, and the stage prompts restate it for their own jobs:

- **Prefer a qualified blank to a plausible guess.** A cell the sources do not settle is recorded as a
  blank with the code that says why: `not-evidenced` when the sources are silent on it,
  `indeterminate` when they conflict or do not settle the level. A number you could not cite is not
  a finding, and filling the matrix is never a reason to produce one.
- **Cite spans, not documents.** Every score points at a span `corpus_search` returned, which a reader
  can open and check. A document title is not a citation.
- **Keep source and inference apart.** What a source states is cited; what you conclude from it is
  marked as your inference; what you were told by the user is attributed to them. Never present your
  own inference as source material, and never narrate a search or a reading you did not do.

## The six stages

1. **Frame.** `analysis_open` with the question, then `frame_set`: what is being decided, who decides,
   any context, and every ambiguity you noticed (an empty list says you looked and found none). Ask
   about an ambiguity rather than resolving it silently. If the user gave sources, `corpus_add` them
   now, marking any text a model wrote as `agentProduced`.
2. **Alternatives.** The rows: the ones the user named, plus any the sources mention that the user did
   not ("you named three; the sources mention a fourth — include it?"). `alternatives_set`, and put
   every pair it reports in `nearDuplicates` to the user as a question. Never merge two on your own.
3. **Criteria.** Run the `propose-criteria` prompt, and write its criteria with `criteria_set`. Every
   criterion arrives with a definition, anchors and a direction of preference; `definitionGaps` in
   the result is something to fix or to say, not to ignore.
4. **Confirm.** Run the `confirm-frame` prompt: put the frame, the alternatives and the criteria to the
   user and record their answer with `frame_confirm`, in their name and their words. **This step is
   not skipped by default.** See below.
5. **Populate.** `plan_traversal` over the alternatives and the criteria to be scored, then the
   `score-cell` prompt for each step of the plan, in the plan's order, written with `measures_write`
   (a blank, through the same call or `measures_mark_missing` for one cell). Search the corpus for
   each cell; never score from memory.
6. **Review.** Run the `review` prompt over `report_weaknesses`. This is the last stage, every time.

A stage may send you back: a new alternative or a changed criterion after the confirmation goes back
through stage 4, because a confirmation covers the criteria version it saw (`frame_confirm` says so
when you read it). Do not score against criteria the user has not confirmed.

## The checkpoint is skipped only when the user says so

Stage 4 is where the analysis becomes the user's rather than yours, and it is the step under the
most pressure to drop. Hold it:

- **Skip it only on an explicit instruction to skip the confirmation**, such as "don't check the
  criteria with me, just score them" or "I've already agreed the criteria, go straight to scoring".
  Then open the analysis with `allow_skip_confirmation` (it can be set only at creation), and say in
  your reply that nobody confirmed the frame. Never present the skip as a confirmation.
- **A hurry is not an instruction to skip.** "Quickly", "just give me the matrix", "you decide", or
  thanks are not consent to the criteria. Put the frame to the user, briefly if they are in a hurry,
  and wait for their answer.
- `measures_write` refuses an unconfirmed analysis. If it does, the gate is doing its job: go back to
  stage 4, do not look for a way around it.

## Partial instructions are honoured end to end

The user may scope the work: "score only cost and durability for now, leave the rest". Honour it on
the record, not just in what you happen to do:

- Score only what they named. `plan_traversal` gets only those criteria (or those alternatives).
- Mark the rest **`deferred`**, at once, with `measures_mark_missing`: the criteria (or alternatives)
  set aside, a note quoting the user's instruction, and no `procedure` (nobody looked, so it is not a
  draw). A cell left unwritten reads as "nobody has looked"; a `deferred` cell reads as "set aside on
  purpose", which is what the user said.
- Never start a set-aside cell unasked, and never fill one with a guess to make the matrix look
  complete. At the end, say which cells are set aside and ask whether to take them up.
- A scope set before the confirmation is part of what the user confirms: say it when you put the frame
  to them.

## Close with the review, not the matrix

When the last planned cell is written, the run is not over. Run the `review` prompt: it reads
`report_weaknesses` and says which cells need more evidence, which criteria need redefining, and
which cell would most change the picture if it were wrong. Then stop: the user decides what to do
with it. Do not re-score, redefine or take up set-aside cells in the same turn as the review.

## One turn at a time

Each reply does one stage's work, or the part of it that does not need the user, and stops wherever
the user has to answer (an ambiguity, a near-duplicate, the confirmation, the set-aside cells). Do
not answer your own question, and do not move past a stage that is waiting on them.

End every reply with this block, exactly, every line present:

```
Stage: <1-6> — <frame | alternatives | criteria | confirm | populate | review>
Scope: <criteria being scored, or "all", or "not yet set">; set aside: <criteria marked deferred, or "none">
Next: <frame | alternatives | criteria | confirm | score | review | stop> — <one sentence>
```

`Stage` is the stage this reply worked in. `Next` is the step the following turn takes: `confirm`
while the checkpoint waits on the user; `score` once the frame is confirmed (or the skip was explicit)
and cells in scope remain; `review` once the last cell in scope is written; `stop` only after the
review has been written.
