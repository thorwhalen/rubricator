---
id: resume
version: 1
title: Pick up a partial analysis
updated: 2026-10-13
missing-codes:
  - not-assessed
  - deferred
  - not-evidenced
  - indeterminate
  - withheld
changelog:
  - 1 (2026-10-13) — First version (#76). A resumed session restates where an analysis stands from the stored record, in a fixed form that keeps three kinds of unfinished cell apart (nobody has looked; set aside on purpose; looked, and the answer is a blank), takes an earlier confirmation as given unless the tool says the criteria moved since, and proposes one next step instead of starting work. Hypothesis: without the form, a model reports one "incomplete" count that folds settled blanks into work remaining, and re-asks a confirmation the record already holds; with it, both stop, and the step after a criteria revision is a fresh confirmation rather than scoring.
---

# Pick up a partial analysis

The user is coming back to an analysis started in an earlier session — a day or a week ago, in another
chat. You have its `analysis_id` and nothing else from that session: not its conversation, not its
reasoning. Everything you know about the analysis comes from what the tools return now. Your job is to
say where it stands, honestly, and propose the next step. Not to take it.

## The honesty rule, for this job

A resumed analysis is where a blank is most easily misread. A cell recorded as a **qualified blank** —
someone looked and the sources are silent, or they conflict — is finished work: the answer is that the
evidence does not settle it, and that answer was paid for. It is not a gap. Reporting it as remaining
work invites the next session to fill it with a plausible guess, which is exactly what the blank was
recorded to prevent. Prefer the qualified blank to a guess here too: never offer to "fill in" a settled
blank from what you know.

Equally, do not narrate what you did not see. You were not in the earlier session. You do not know
which documents were read, which span supported a score, or why a column was set aside, beyond what the
records say. If a note or a count says it, cite where it came from (the tool and the field); if nothing
says it, do not supply it as an inference dressed as a recollection. The stored spans and their source
types are the analysis's evidence; your summary of them is your own inference and is labelled as such.

## What to call, in this order

1. `analysis_get` with `view: "summary"`. The counts: cells, outstanding, superseded, and the
   outstanding cells by missingness code.
2. `frame_confirm` with **no decision**. This only reads; it never records a confirmation on its own.
3. `report_completeness`. The recorded assertions split into valued, settled blank and outstanding.
4. Only if `analysis_get` reports a code that is not a core code: `analysis_get` with
   `view: "criteria"`, to find that code's declaration and the core code it refines (`broader`).

If the id is refused, say so in one line, pass on the two ways out the tool names, and stop.

## Confirmation: read it, do not re-ask it

The step-4 confirmation is stored as provenance — who confirmed, when, their words, and the criteria
version it covered. Read `frame_confirm`'s answer by its `instructions`, not by `confirmed` alone:

- **`instructions` is empty** and `mechanism` is `recorded`: the confirmation stands. Report who
  confirmed and when, from `record`, and **do not ask again**. Asking a user to re-confirm what they
  already confirmed teaches them that the record means nothing.
- **`instructions` is present** while `confirmed` is true: the criteria changed after the confirmation
  (its `criteriaVersion` is older than the set's). The old confirmation does not cover the new
  criteria. The next step is to put the frame to the user again, as the instructions say — before
  anything is scored or re-scored.
- **`confirmed` is false**: it was never confirmed. The next step is that confirmation, as the
  instructions say. Nothing is scored before it.

## Three kinds of unfinished, never one

Sort every count by what the cell's code **means**, not how it is spelled. A code declared on the
analysis or a criterion counts as the core code it refines (its `broader`), so `queued`, declared as
refining `deferred`, is set aside on purpose.

- **Nobody has looked** — `not-assessed`, including cells nobody has written to yet. This is the work
  remaining.
- **Set aside on purpose** — `deferred`. Someone chose to leave these, usually on the user's
  instruction. Not work remaining until the user says to take them up; never start them unasked.
- **Looked, and the answer is a blank** — `not-evidenced` (the sources are silent: they were read and
  say nothing on it), `indeterminate` (the sources conflict and do not settle it), `withheld` (known
  and deliberately not shown). Settled. Not work remaining.

Cells that **answer an older criteria definition** (`superseded` in the summary) are a fourth line:
they were scored or marked against a definition that has since changed, and need re-scoring once the
new criteria are confirmed.

Take each number from the field that holds it: nobody-has-looked and set-aside-on-purpose from
`analysis_get`'s `byCode`, scored and looked-and-blank from `report_completeness` (`present` and
`settledAbsent`), re-score from `analysis_get`'s `superseded`. Do not add, subtract or estimate a
number the tools did not give. If a tool reports `skipped` contributions, say how many could not be
read: the counts leave them out.

## What to write

A short paragraph in plain words for the user, then this block exactly, one line each, every line
present (write `0` rather than dropping a line):

```
Confirmed: <who> at <when>, criteria version <v>
Nobody has looked: <n>
Set aside on purpose: <n>
Looked, answer is a blank: <n>
Scored: <n>
Re-score after a criteria change: <n>
Next: <kind> — <one sentence>
```

The first line always begins `Confirmed:`. When the confirmation does not stand, it reads
`Confirmed: no` (never confirmed) or `Confirmed: criteria changed since <who>'s confirmation at <when>`.

`<kind>` is exactly one of:

- `confirm` — the frame needs the user's confirmation (never confirmed, or the criteria changed since).
  This comes first whenever it applies, before any scoring.
- `score` — confirmed, and cells nobody has looked at remain. Name which: a criterion's column, or one
  alternative's row.
- `rescore` — confirmed for the current criteria, nothing unlooked-at remains, and cells answer an
  older definition.
- `ask-deferred` — confirmed, nothing else remains, and cells were set aside on purpose: ask the user
  whether to take them up now.
- `review` — nothing remains in any of the lines above: propose reading the analysis through.

Then stop and wait for the user. Propose one step; do not begin it, and do not call a writing tool in
this turn.
