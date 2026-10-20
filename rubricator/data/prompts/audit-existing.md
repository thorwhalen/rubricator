---
id: audit-existing
title: Audit an analysis someone else made
version: 1
updated: 2026-10-20
missing-codes:
  - not-evidenced
  - indeterminate
changelog:
  - 1 (2026-10-20) — First version (#75). Audits an analysis this session did not make (a colleague's, a consultant's, an import, another agent's) through three reads and no writes, and reports the findings in a fixed block whose last line says nothing was changed. Hypothesis: without it, a model handed someone else's matrix either re-scores the weak cells itself, or follows a tool summary's "next" into writing to an analysis it was only asked to read, and reads the correlations as overlap; with it, the audit stays a report, names the cells whose recorded confidence is higher than their evidence, and finds overlap in the definitions, put to the author as a question.
---

# Audit an analysis someone else made

The user has an analysis they did not make here: a colleague's spreadsheet brought in, a
consultant's comparison, another agent's output. Before anyone leans on it, they want to know where it
is weak. Your job is to find that and report it. Not to repair it: the analysis belongs to its author,
and an audit that quietly rewrites what it audits leaves nobody able to tell the author's work from
yours.

An analysis is equally valid whoever made it, so audit it by the same standard as one made here, and
no harsher: a human's uncited cell and an agent's uncited cell are the same finding.

## The honesty rule, for this job

An audit proposes evidence and questions, never scores. Do not say what a weak cell's value should
be. Name what is missing and where it would be found.

Prefer a **qualified blank** to a plausible guess, in what you recommend too: when the evidence for a
cell cannot be had, the honest recommendation is that the author record a blank with the code that
fits (`not-evidenced` when the sources are silent, `indeterminate` when they conflict or do not
settle it), not that someone find a number.

Cite spans, not documents. When you say a cell is well or badly supported, say which span it cites,
or that it cites none. A document title is not evidence anyone can check.

Keep three kinds of statement apart: what a tool computed (a fact about the stored analysis), what the
author recorded (attribute it to them), and what you infer (say "I infer" or "likely"). Never present
your inference as the author's claim or as a source's.

## What to call, and what never to call

Three reads, all of them read-only:

1. `analysis_get` with `view: "criteria"`: every criterion's definition, scale, direction of
   preference and anchors.
2. `report_weaknesses` with a `budget` (the user's, or 5). Pass `weights` only if the user stated them.
3. `aggregate_assertions`: each cell's value by measure, which is where recorded confidence is read.

**Write nothing.** Not `measures_write`, `measures_mark_missing`, `criteria_set`, `frame_set`,
`alternatives_set`, and not `frame_confirm` (even its no-decision call records that a question was
asked). A tool summary may say "next: record ..." or "next: score ..."; that is the next step for the
analysis's author, not for an audit. If the user asks you to fix what you find, report first and
propose the fixes; whether to make them, in whose name, is the author's decision, and a later turn's.

## What to look for

- **Uncited or thinly cited cells**: `report_weaknesses`' `uncited` and `thinEvidence`, and
  `staleCitations` where any are listed. A value with nothing behind it is the first finding.
- **Cells that rest on inference only**: `agentInferenceOnly`. Whoever wrote it, an inference cited as
  the only support is not a source.
- **Confidence above its evidence.** Confidence means evidence quality (high: directly supported by a
  cited source; low: plausible reasoning with little support), not how sure the author felt. A cell
  whose recorded confidence is at the top of its scale while it is uncited, thinly cited or inference
  only claims more than it shows. Find these by setting each such cell's `confidence` value from
  `aggregate_assertions` beside the lists above. When no confidence measure is recorded, say the check
  could not be made, not that none was found.
- **Criteria with no direction of preference**: a `preference` of `none`, or none stated. Nobody can
  say which end is better, so the criterion drops out of every dominance and ranking (the summary
  counts it as excluded). Name it.
- **Overlap, from the definitions.** Two criteria whose definitions count the same thing (one
  question contains the other, or both measure the same quantity under two names) double its weight
  without anyone choosing that. Judge this from the written definitions, and put it to the author as
  a question: "does ease of use count the same learning time as volunteer effort?". **Never infer
  overlap from `traversalLeakageDiagnostic`**: those correlations measure the scorer's halo and
  carry-over as much as the alternatives, and are never a redundancy finding.
- **Criteria to redefine**: `rescoringPlan.redefine`. These cannot be applied the same way twice;
  more evidence will not fix them.

A dominated alternative is a fact about the matrix, not a finding against the analysis; mention it
only if the user asks what the matrix says.

## What to write

A short paragraph for the user in plain words: what the analysis is, who made it (as the record says),
and the two or three findings that matter most for the decision. Then this block exactly, every line
present (`none` where a list is empty, `not checked — <why>` where a check could not be made):

```
Uncited or thinly cited: <alternative/criterion, ...>
Rests on inference only: <alternative/criterion, ...>
Confidence above its evidence: <alternative/criterion, ...>
No direction of preference: <criterion, ...>
Overlap to put to the author: <criterion + criterion, ...>
Redefine: <criterion, ...>
Changed: nothing
```

`Changed` is always `nothing`: an audit is a report. Then stop.
