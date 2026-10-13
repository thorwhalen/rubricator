---
id: resume
version: 2
title: Pick up a partial analysis
updated: 2026-10-13
missing-codes:
  - not-applicable
  - not-assessed
  - deferred
  - not-evidenced
  - indeterminate
  - withheld
changelog:
  - 2 (2026-10-13) — One unit, and the cells named (#186, #188). The block counts cells on every line, from `analysis_get`'s `counts` (`byKind`, `outstanding`, `byCode`, `superseded`), and the lines add up to `counts.cells`; `report_completeness` is no longer read, because it counted claims (two raters on one cell twice, superseded claims, claims on a removed row). The session reads `analysis_get` with `view: "outstanding"` instead of `summary`, so a `score` step names a column or row that really has cells nobody has looked at. Hypothesis: with one unit a reader can check the block against `counts.cells`, and with the cell list the proposed step names a real column or row instead of saying the records do not say.
  - 1 (2026-10-13) — First version (#76). A resumed session restates where an analysis stands from the stored record, in a fixed form that keeps three kinds of unfinished cell apart (nobody has looked; set aside on purpose; looked, and the answer is a blank), takes an earlier confirmation as given unless the tool says the criteria moved since, and proposes one next step instead of starting work. Hypothesis: without the form, a model reports one "incomplete" count that folds settled blanks into work remaining, and re-asks a confirmation the record already holds; with it, both stop, and the step after a criteria revision is a fresh confirmation rather than scoring. Revised once before landing, after an adversarial review found the draft wrong about the tools in common states: a no-decision frame_confirm records that the question was asked, so the reply now asks it; a skipped, revised or partly-scoped confirmation is reported from the record rather than as given or never asked; the block keeps cells and claims in separate, labelled lines; not-applicable has its own line.
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

1. `analysis_get` with `view: "outstanding"`. `counts` has the live cells (`cells`), how many are
   scored, settled blanks or not applicable (`byKind`), how many are outstanding, the outstanding
   ones by missingness code (`byCode`), and the cells that answer an older definition
   (`superseded`). Beside it, one row per outstanding cell: its alternative, its criterion and its
   code.
2. `frame_confirm` with **no decision**. When a confirmation stands, this only reads it. When none
   stands, the same call records that the question is being put to the user and returns
   `instructions` — so in that case you put it, in this reply (below). It never records a
   confirmation on anyone's behalf.
3. Only if `analysis_get` reports a code that is not a core code: `analysis_get` with
   `view: "criteria"`, to find that code's declaration and the core code it refines (`broader`).

Do not call `report_completeness` to resume. It counts recorded claims, not cells — two people on one
cell count twice — so its numbers cannot be set beside these.

If the id is refused, say so in one line, pass on the two ways out the tool names, and stop.

## Confirmation: read it, do not re-ask it

The step-4 confirmation is stored as provenance — who decided, what, when, their words, and the
criteria version it covered. Read `frame_confirm`'s answer by its `instructions` and its `record`,
not by `confirmed` alone:

- **`instructions` is empty and `record.decision` is `confirm`**: the confirmation stands. Report who
  confirmed and when, from `record`, and **do not ask again**. Asking a user to re-confirm what they
  already confirmed teaches them that the record means nothing.
- **`instructions` is empty and `record.decision` is `skip`**: nobody confirmed. The checkpoint was
  skipped at the caller's request when the analysis was opened. Say so plainly, and never present it
  as a person's confirmation; scoring may go on.
- **`instructions` is present**: the confirmation does not stand, whatever `confirmed` says. Say why
  from `record`, never by guessing: no record — it was never put to anyone; a `confirm` whose
  `criteriaVersion` is older than the set's — the criteria changed after it; a `confirm` whose `scope`
  is not `all` — only that part was confirmed; a `revise` — the user asked for changes (quote their
  words) that have not been put back to them; a `reject` — the user rejected the frame. The call you
  just made recorded that the question is being asked, so ask it in this reply as the instructions
  say — or, after a `revise`, ask whether to make the changes the user asked for first. Then stop for
  their answer. Nothing is scored or re-scored before it.

## Three kinds of unfinished, never one

Every code in `analysis_get`'s `byCode` is outstanding. Sort each by what it **means**, not how it is
spelled: a code declared on the analysis or a criterion counts as the core code it refines (its
`broader`), so `queued`, declared as refining `deferred`, is set aside on purpose.

- **Nobody has looked** — `not-assessed`, including cells nobody has written to yet. This is the work
  remaining. A code you cannot place (not core, no declaration in the criteria view) goes here too,
  named: over-reporting work remaining is the safe direction.
- **Set aside on purpose** — `deferred`. Someone chose to leave these, usually on the user's
  instruction. Not work remaining until the user says to take them up; never start them unasked.
- **Looked, and the answer is a blank** — `not-evidenced` (the sources are silent: they were read and
  say nothing on it), `indeterminate` (the sources conflict and do not settle it), `withheld` (the
  answer is known and deliberately not shown). Settled. Not work remaining.

`not-applicable` is neither: the criterion does not apply to that alternative, so the cell leaves
every count and comparison. It has its own line.

Cells that **answer an older criteria definition** (`counts.superseded`) need re-scoring once
the new criteria are confirmed. A cell can be on two lines: a settled blank that answers an older
definition is settled under the old criteria and due a fresh look under the new.

## One unit: cells

Every line of the block counts **cells**, and each number comes from its field in `counts`; do not
add, subtract or estimate one the tool did not give. Nobody has looked + set aside on purpose +
scored + looked-and-blank + not applicable add up to `counts.cells`. Re-score is the exception: it is
a subset, the cells that answer an older definition and so can also be on a scored or blank line. If
a tool reports `skipped` contributions, say how many could not be read: every count leaves them out.

## What to write

A short paragraph in plain words for the user, then this block exactly, one line each, every line
present (write `0` rather than dropping a line):

```
Confirmed: <who> at <when>, criteria version <v>
Nobody has looked: <n> cells
Set aside on purpose: <n> cells
Re-score after a criteria change: <n> cells
Scored: <n> cells
Looked, answer is a blank: <n> cells
Not applicable: <n> cells
Next: <kind> — <one sentence>
```

The lines come from `analysis_get`: `byCode` and `superseded` as before, and `byKind` for scored
(`scored`), looked-and-blank (`settledBlank`) and not applicable (`notApplicable`).

The first line always begins `Confirmed:`. When no person's confirmation stands, it reads
`Confirmed: skipped at <when>, nobody confirmed`, or
`Confirmed: criteria changed since <who>'s confirmation at <when>`, or `Confirmed: no — <what the
record says>` (`never put to anyone`, `<who> asked for changes at <when>`, `<who> rejected it at
<when>`, `only the <scope> confirmed`).

`<kind>` is exactly one of:

- `confirm` — `instructions` is present: the frame needs the user's decision. This comes first
  whenever it applies, before any scoring, and the question is asked in this reply.
- `score` — cells nobody has looked at remain. Name which, from the outstanding rows: a criterion's
  column, or one alternative's row. Name only a column or row that has such a cell.
- `rescore` — nothing unlooked-at remains, and cells answer an older definition.
- `ask-deferred` — nothing else remains, and cells were set aside on purpose: ask the user whether
  to take them up now.
- `review` — nothing remains in any of the lines above: propose reading the analysis through.

Then stop and wait for the user. Propose one step, or ask the one question; do not begin the work,
and do not call a writing tool in this turn.
