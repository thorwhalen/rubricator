# ADR-0016: Criteria are revisable, and the step-4 checkpoint is a gate, not a one-way door

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0005 settles the frame before the matrix is populated, which is correct. Read linearly, it also
implies criteria are final at step 4. They are not. Criteria drift is documented: users need
criteria to grade outputs, but grading outputs is how users work out what their criteria are, and
some criteria only become sayable once particular outputs have been seen [1]. This does not
contradict value-focused thinking — which forbids deriving the *structure* of a criteria set from
the alternatives while explicitly endorsing alternatives as *stimuli* [2] — but it does contradict
step 4 read as a one-way door.

Left unhandled, drift produces a matrix whose criteria were scored against different rubrics. That
is the worst-of-both outcome: the analysis is wrong in a way that is completely invisible in the
output, because nothing in the document records which definition a given measure was scored
against.

The force pulling the other way is cost. Scored work is expensive, and a rule that discards it on
any edit at all would make the criteria discussion — the part ADR-0005 exists to protect — the most
expensive thing a user can do.

## Decision

**Criteria sets carry a version, and every measure records the criterion version it was scored
against.** This is the load-bearing half: without the stamp, nothing downstream can tell one rubric
from another, and no later repair can recover the fact.

**A version bump declares whether it is material.** A material bump is a change to a criterion's
`question`, `scale`, `range`, `preference` or `exclusions` that changes what a score *means*. An
editorial bump — a typo, a rephrasing that moves no boundary — re-stamps the affected measures to
the new version, records the edit in the criterion's history, and invalidates nothing. `material`
defaults to true: the caller must claim an edit is editorial, and the claim ships with the analysis.
The declaration is an input to the tool, never a judgement inside it (ADR-0010).

**A material change invalidates every cell scored under the old definition. This is mandatory, not
advisory.** The criteria tool bumps the version and applies the invalidation as a deterministic
field diff; it does not offer retention as an option, and neither does any prompt.

**An invalidated cell becomes `missing` with a contingent reason code of its own —
`superseded-by-revision` — carrying the superseded criterion version as a structured field** rather
than as a free-text note. Under comparanda's parented missingness model the code declares `broader:
not-assessed`, `structural: false`, so it needs no change to comparanda's core set. The reason to
give it its own code is queryability: a resuming session must be able to separate *needs a cheap
re-score against a revised anchor* from *nobody has looked yet*, and a note cannot be counted or
filtered.

**Superseded measures are retained.** comparanda's ADR-0011 keeps every assertion with its author
and timestamp; invalidation changes the cell's *current* state, not the record. Each retained
measure keeps the version it was scored against, so the prior work stays readable and attributable.

**Criteria that rubricator proposes and then removes are recorded with a reason code**
(`merged-into`, `means-objective`, `not-controllable`, `no-discrimination-expected`,
`user-rejected`) and ship with the analysis. This is ADR-0006's discipline applied one level up: a
criteria set with no visible rejects is a criteria set nobody interrogated.

None of this supersedes ADR-0005. The frame is still settled before the matrix is populated. What
changes is that reopening it afterwards is a supported operation with a stated, visible cost, rather
than something users do outside the tool where it goes unrecorded.

## Consequences
Revising a criterion is visibly expensive, which is honest — it *is* expensive — and the materiality
declaration keeps the expense proportionate to the change rather than punishing a typo fix with an
emptied criterion. Users will sometimes watch a scored criterion empty itself, and the reason code,
the superseded version and the retained prior measures are all part of the deliverable.

Two requests to `comparanda` follow, and per ADR-0002 they are requests, never changes this
repository can make:

- **Criteria sets are versioned, and every measure records the criterion version it was scored
  against** — issue #28.
- **Criteria carry provenance, and rejected criteria with reason codes ship with the analysis** —
  issue #29.

Neither can be retrofitted honestly later: once measures exist with no version stamp, no subsequent
pass can say which rubric produced them, and a rejected criterion nobody wrote down is gone.

Downstream statistics gain the ability to filter by criterion version, and the coverage metrics of
ADR-0008 count an invalidated cell as outstanding, which is correct — work genuinely remains.

## Alternatives considered
- *Freeze criteria at step 4.* Contradicts observed practice [1] and pushes revision outside the
  tool, where it goes unrecorded.
- *Keep old scores after a material definition change.* Silently mixes rubrics; invisible in the
  output.
- *Invalidate on any field change, with no materiality test.* Mechanically destroys a scored
  criterion on an editorial edit, in a pipeline whose whole premise is that the criteria discussion
  is the valuable part.
- *Let the tool decide materiality by inspecting the edit.* That is a judgement, and ADR-0010
  forbids a tool that needs a model to reach one.
- *Record the invalidation reason in a free-text note against `not-assessed`.* Reuses a code whose
  meaning is "nobody has looked yet" for a cell that was assessed, and puts the distinguishing fact
  somewhere no query can reach.

## Evidence
Question row 6 of [`docs/research/findings-method.md`](../research/findings-method.md) § 1, and its
ADR-0016 entry under "Recommended ADR actions"; the elicitation working notes in
[`docs/research/sections/r1-criteria-elicitation.md`](../research/sections/r1-criteria-elicitation.md)
§ 7 ("VFT versus criteria drift") carry the invalidation rule as first drafted, and § 5 the
reject-reason vocabulary.

The materiality clause, the dedicated reason code and the retention sentence were added when this
ADR was settled, on findings from the adversarial review in `comparanda: docs/research/phase0-review.md`
("Partly real" — *mandatory cell invalidation … has no material-change test*, and *rubricator writes
invalidated cells as `not-assessed` …*). The inclusion of `range` in the trigger list follows the
same review's note that comparanda's ADR-0018 makes a declared range required on every ordinal
criterion, so changing it changes what every stored score means.

1. [Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences — Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran & Arawjo (2024), UIST '24](https://arxiv.org/abs/2404.12272)
2. [Value-Focused Thinking: A Path to Creative Decisionmaking — Keeney (1992)](https://www.hup.harvard.edu/books/9780674931985)
