---
id: add-criterion
version: 1
stage: 3
title: Add one criterion to an existing analysis
updated: 2026-10-20
missing-codes:
  - not-evidenced
  - indeterminate
  - not-applicable
  - not-assessed
changelog:
  - 1 (2026-10-20) — First version (#128). Adds one criterion after the framing: the request is laddered against the criteria already there before anything is written, the new criterion carries every definition field `propose-criteria` asks for, the existing criteria go back to `criteria_set` exactly as `analysis_get` returned them, and nothing is written into the new column. Its cells are `not-assessed` because nobody has looked, which the record already says with no write; no existing cell is re-scored or blanked, because an addition changes what no stored score asserts (ADR-0016 as amended 2026-10-12). The user confirms the criteria again before any of the new column is scored. Hypothesis: without it a model either re-types the existing criteria (an edit that supersedes their cells) or writes placeholder blanks into the new column, and adds a criterion the set already covers, or one nobody defined, without asking; with it, a well-specified request becomes one accepted `criteria_set` call with no definition gaps on the new criterion and nothing superseded, and an ambiguous, duplicate or revising request becomes a question. Revised twice before landing against blind runs: one model put the provenance inside the criterion, which `criteria_set` refuses, so the prompt now says the provenance goes in the reply's `Added` line and nothing but the stored keys goes in the criterion; the other read a request that measures the user's own stated reason as a means objective and asked instead of adding, so the means test now names what a means serves (a different thing the decider wants judged) and what is not one (the leaf of the reason they gave).
---

# Add a criterion

The analysis already exists: the subject, the alternatives and the criteria are set, the user has
confirmed them, and some cells may already be scored. Now the user wants one more column. Your job is
to turn their request into **one well-defined criterion**, add it without disturbing anything already
recorded, and put it back to the user before any of it is scored.

## The honesty rule, for this job

- **Prefer a qualified blank to a plausible guess.** A new column starts with no scores, and that is
  the honest state of it. Do not fill it from what you know about the alternatives, and do not write
  placeholder blanks into it either: its cells are `not-assessed` — nobody has looked — and the record
  already says so without a write. When you do not know what the user means by the criterion, or why
  they care, ask; do not invent a definition. A made-up objective is formatted exactly like one the
  decider holds.
- **Cite spans, not documents.** The criterion carries the user's words, quoted exactly, as its
  provenance. "The user asked about cost" is not a citation; the sentence they wrote is.
- **Never present your own inference as the user's.** Every field you wrote without the user saying it
  is yours, and the reply says which: its `Added` line marks the criterion `user-stated` (with the
  quote) or `agent-proposed`, and anything you filled in beyond their words is listed as your proposal
  for them to confirm. That provenance goes in the reply, never inside the criterion: the stored shape
  has no slot for it, and `criteria_set` refuses a key it does not know.

## What to read first

`analysis_get` with `view: "criteria"`. It returns every criterion as the analysis stores it, the
`criteriaVersion`, and the `counts`. Keep that result: the existing criteria go back unchanged.

## Is it really a new criterion?

Ladder the request against the criteria already there before you write anything, the way
`propose-criteria` does: ask why it matters (up) and what exactly it means (down).

- **It is already covered.** If it refines the same objective as an existing criterion, or means what
  one already asks, do not add it. Name that criterion in `overlaps` with the indifference question
  for the user — "two kettles identical except on this; do you prefer one, or are you indifferent?" —
  and stop at the question. If the user is indifferent it is not a new column; if they are not, the
  reason they give becomes the `exclusions` that keep the two apart.
- **It changes an existing criterion.** "Make repair policy count the heating element too" is not an
  addition; it is a revision of that criterion's meaning. Do not add a column and do not edit the
  criterion here. Say that it is a revision, that every cell already recorded under that criterion
  would then answer the older definition and need re-scoring, and ask whether that is what they want.
- **It is a means to something else.** If it matters only as a way of achieving a *different* thing
  the decider wants judged — "it must have a descaling indicator", when what they want is little
  descaling effort — it is not a column (see `propose-criteria`): say what it serves, and ask whether
  that is the criterion they want, or whether it is a veto. A request that *is* the measure of the
  reason the user gave is not a means: "the price of replacement filters, because the office pays for
  consumables" is the leaf of that objective, laddered down. Define it, with their reason as its
  `objective`.
- **It is two criteria.** If the leaves of the ladder are two things a scorer judges separately, say
  so and propose both, each defined in full; the user chooses.
- **It is what they asked for, and you know what they mean.** Then define it.

## What the new criterion carries

Exactly the shape `criteria_set` takes, as `propose-criteria` defines it, so that someone who was not
here can score it. These keys and nothing else go inside the criterion:

- `id` (short, kebab-case, not already used) and `label`.
- `preference` — `increasing`, `decreasing`, `target` (with a numeric `target`), `ordered` (an order
  with no better end) or `none`. State it; never leave it to a default.
- No `scale` unless the analysis uses another: the default is the anchored 1-5 ordinal, which takes
  `anchors` at levels `"1"`, `"3"` and `"5"`, each written as an **evidence condition** a source can
  state ("a source states X"), never as an adjective and never as an absence.
- `definition` with all five fields: `objective` (what the decider wants, in words), `question` (the
  one question a scorer answers for one alternative), `evidenceRule`, `missingRules` and `exclusions`
  (at least one, including the boundary with any existing criterion it could be confused with).
- `missingRules` — at least one `{when, code}`. Keep the two blanks apart:
  **`not-evidenced`** when the sources are **silent** on the question (someone looked and found nothing);
  **`indeterminate`** when they speak and **conflict**, or do not settle the level;
  and `not-applicable` when the criterion does not apply to an alternative at all. These are findings about the sources; `not-assessed` is not one
  of them and never goes in a rule.

## Writing it

Call `criteria_set` with `criteria` set to **every existing criterion exactly as `analysis_get`
returned it**, in the same order, followed by the new one, and no `editorial`. `criteria_set` replaces
the whole set, so an existing criterion you re-type, tidy, reorder the anchors of, or "complete" with a
definition is an edit to it: its cells would then answer an older definition and need re-scoring. That
is a revision the user did not ask for. Copy; do not rewrite. An existing criterion's gaps are reported
in `definitionGaps`; mention them, do not fix them here.

Then read the result before saying anything:

- `revised` is empty and `supersededCells.count` is 0. If not, an existing criterion changed: say so
  plainly, name it, and do not go on to scoring.
- `definitionGaps` names no field of the new criterion. If it does, fill it, or ask.
- `criteriaVersion` is the version the addition was recorded under. Report it as returned.

**Do not write any cell.** No score and no blank goes into the new column, and no existing cell is
re-scored or blanked: adding a criterion changes what no stored score asserts. Every cell of the new
column is `not-assessed`, nobody has looked, and stays so until it is scored after the user confirms.

Then the checkpoint: `frame_confirm` with no decision. It will say the criteria changed since the last
confirmation. Put the new criterion to the user in full — definition, anchors, direction, and every
overlap probe — with `scope` set to `criteria`, and record their answer in their words, or nothing.
Nothing in the new column is scored before they confirm.

## What to emit

When you are asking instead of adding, say why in one or two sentences and ask; call nothing.

Otherwise, the `criteria_set` call, then a reply that ends with this block, one line each:

    Added: <id> — <label> (user-stated | agent-proposed)
    Criteria version: <criteriaVersion as criteria_set returned it>
    New column: <alternatives> cells, not-assessed — nobody has looked
    Existing cells: unchanged — none re-scored, none blanked, none superseded
    Yours to confirm: <each field you proposed beyond the user's words, or "nothing">
    Next: confirm the criteria (frame_confirm, scope criteria)

Worked, on an invented decision: an office choosing among three kettles, with criteria for repair
policy, spare parts and noise. The user writes: "Can we also compare how much of a hassle descaling is?
Our water is very hard." Up: descaling effort matters because hard water means it happens every week,
and the person doing it is whoever is in the kitchen: a fundamental objective about the kettle being
easy to keep running. It is not repair policy or spare parts (those are about breakdowns). Down: "how
much of a hassle" becomes how often descaling is needed and what it takes.

```json
{
  "id": "descaling-effort",
  "label": "Descaling effort",
  "preference": "decreasing",
  "anchors": [
    {"level": "1", "text": "A source states descaling needs only a rinse with no tools or chemicals, or is needed less than monthly in hard water."},
    {"level": "3", "text": "A source states descaling needs a descaling agent and a full boil cycle, about monthly in hard water."},
    {"level": "5", "text": "A source states descaling needs disassembly or a service visit, or is needed weekly in hard water."}
  ],
  "definition": {
    "objective": "The kettle is easy to keep running in very hard water",
    "question": "How much effort, and how often, does descaling this kettle take in hard water?",
    "evidenceRule": "The maker's manual or care page stating the procedure and interval; a reviewer's report of their own descaling counts as secondary; a general claim that it is 'easy to clean' does not count.",
    "missingRules": [
      {"when": "No source describes the descaling procedure or interval.", "code": "not-evidenced"},
      {"when": "The manual and the care page give different procedures or intervals.", "code": "indeterminate"}
    ],
    "exclusions": ["Breakdowns and repairs; that is repair-policy.", "Cleaning the outside of the kettle."]
  }
}
```

Its provenance, in the reply's `Added` line and not in the JSON, is `user-stated`, quoting "how much
of a hassle descaling is". The direction, the
anchor levels and the evidence rule are the agent's proposal and go under `Yours to confirm`.
