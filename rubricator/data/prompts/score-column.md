---
id: score-column
version: 1
stage: 5
title: Score one criterion across every alternative (harness arm 2, not the default)
updated: 2026-10-20
missing-codes:
  - not-evidenced
  - indeterminate
  - not-applicable
changelog:
  - 1 (2026-10-20) — First version (#73). One criterion, every alternative, one pass: the cheaper mode, and arm 2 of the ADR-0008 harness against `score-cell` (arm 1, the default by ADR-0011). It adds only what changes when a column is scored together: the anchors are read once and held fixed, each alternative is judged against them on its own spans only, the alternatives are never ranked against each other, and the output is one `score-cell` emission per alternative. Every per-cell rule is `score-cell`'s, read first. Hypothesis: on the same cells it matches `score-cell` on refusal to guess, the right blank and writes with no repair; whether it holds the scale better or drifts is what the harness is for, and nothing here claims either.
---

# Score one column

You are scoring **one criterion for every alternative** in a single pass: one column of the matrix.
This is **not the default**. The default is `score-cell`, one cell per generation, because scoring
several things in one pass pulls them toward each other and a thing's position in a prompt moves its
score. A column is cheaper, and it may hold a scale steadier across alternatives; which effect wins is
what the evaluation harness measures. Until it has, this prompt is the harness's second arm and a cheap
mode a user can choose, and you do not present its output as the default protocol's.

## Read `score-cell` first

Every rule for a single cell is `score-cell`'s, and it holds here for each cell, word for word: when to
score and when to blank, which blank, confidence as evidence quality, which other criteria a cell turns
on, describing the pass, and the exact object to emit. If `score-cell` is not already in your context,
get it (`prompts_get`, id `score-cell`) before you start. This prompt says only what changes when the
cells of one column are judged together.

## The honesty rule, for a column

- **Prefer a qualified blank to a plausible guess**, in every cell. A column invites filling: once
  three alternatives have levels, the fourth "should" have one too. It should not, unless its own spans
  meet an anchor. A column where most cells are blanks is a correct answer when the sources are thin.
- **Cite spans, not documents**, and only the spans handed for **that** alternative. A span read for
  one alternative is never evidence for another, however much it says about both.
- **Never present your own inference as a source.** Comparing alternatives in your head is inference;
  it never becomes a level, a justification or an evidence entry.

The two blanks stay apart in a column exactly as in a cell:

- **`not-evidenced`** when that alternative's sources are **silent** on the question;
- **`indeterminate`** when they speak and **conflict**, or do not settle the level;
- `not-applicable` for an alternative the criterion does not apply to at all.

## What changes in a column

1. **Read the anchors once, before any alternative.** Write down (in your plan, which you do not emit)
   what a span would have to state to meet levels 1, 3 and 5. That reading is fixed for the whole
   column: you do not reinterpret an anchor because of what the next alternative's spans say.
2. **Judge each alternative alone, against that fixed reading.** In the order given. A level comes from
   the anchors, never from being better or worse than a neighbour. Two alternatives may get the same
   level, and all of them may be blanks.
3. **Do not rank, and do not spread.** Never move a level to separate two alternatives that the anchors
   do not separate, and never compress a column because the levels "look too far apart". The
   justification of each cell speaks only about that alternative.
4. **Confidence and `dependsOn` are per cell**, as `score-cell` defines them, not per column.
5. **The pass is one pass.** The procedure facts are the same for every cell of the column, as
   `score-cell` says to state them; if the plan you were given names a traversal, copy it.

## What to emit

A JSON array with one element per alternative, in the order you were given them. Each element is
exactly the object `score-cell` emits for one cell, with its `cell` naming that alternative and this
criterion. Nothing else is added to the elements or wrapped around the array.
