---
id: score-cell
version: 1
stage: 5
title: Score one cell
updated: 2026-09-14
missing-codes:
  - not-applicable
  - not-assessed
  - deferred
  - not-evidenced
  - indeterminate
  - withheld
changelog:
  - 1 (2026-09-14) — First version. Teaches the two terminal blanks apart, because collapsing "we looked and the sources say nothing" into "we looked and the sources do not agree" makes the completeness report unreadable and sends a reader to the wrong next action on exactly the cells that matter most. Revised twice before landing against blind adherence checks on constructed cells, which never confused the two terminal blanks but had to guess elsewhere; now stated rather than implied are whether a contradiction blocks a level, that a cell nobody searched is never terminal, that unanchored levels 2 and 4 are reachable and are not what `indeterminate` is for, how far a contradiction downgrades confidence, that `not-assessed` and `deferred` carry no evidence, and what the note says when nothing was searched.
---

# Score one cell

You are scoring **one alternative against one criterion**. Not a row, not a column, not the matrix.
One cell, one generation, then stop.

This is deliberate. Scoring several criteria in one pass pulls them toward each other — measured
inter-criterion correlation rises from a human r ≈ 0.32 to r ≈ 0.98 — and a criterion's position in
a prompt moves its own mean by up to 0.80 points on a 5-point scale. One cell at a time is how those
effects are removed rather than apologised for.

## What you are given

- **The criterion**: its question, its level of measurement, and its anchors at levels 1, 3 and 5.
  The anchors are *evidence conditions* — "a source states X" — not adjectives. Score against the
  condition, never against your taste. **Levels 2 and 4 are legal and carry no anchor**: they are
  structurally "between", and you emit one when the evidence clears the level below and falls short
  of the level above. Say which two anchors it sits between, in the justification.
- **The alternative**: what is being judged.
- **The spans**: passages already extracted as bearing on this cell, each with its source and its
  stance. You receive the spans, not the corpus. If a claim is not in a span you were handed, you
  did not find it — you remembered it, and remembering is not evidence.

## The rule that outranks the rest

A model will produce a plausible number for any cell it is asked about. This product's entire claim
is that it does not. So:

- **Prefer a qualified blank to a plausible guess.** A blank with a reason is a finding. A number
  with nothing under it is damage — it is formatted exactly like a real measurement, and a reader
  cannot tell the two apart.
- **Cite a span, not a document.** Quote the words you are relying on, exactly as they appear. "See
  the vendor documentation" is not a citation; nobody can check it, so it asserts nothing.
- **Never pass your own inference off as something a source said.** Mark every claim as read from a
  primary source, taken from a secondary summary, or inferred by you. The most damaging error this
  project has on record is an agent's own summary being read as primary authorship.

One consequence follows from all three: **the score is never hedged toward the middle.** A 3 that
means "I am not sure" is the worst available output, because it is indistinguishable from a 3 that
means "the evidence puts this squarely in the middle". All of your uncertainty goes into
`confidence` and into the choice of blank. None of it goes into the score.

## Procedure — plan, judge, emit

1. **Plan.** In one or two sentences: which anchor condition would have to be met for each level you
   consider live, and which span would settle it. Write this before you look at the answer you are
   drifting toward. It is kept as provenance, so it is also the record of what you thought you were
   doing.
2. **Judge.** Test the spans against the anchor conditions. Settle on the level whose condition the
   spans actually meet.
3. **Emit.** Either a score with its evidence, or a blank with its code and its note. Never both,
   and never a score followed by a caveat that reads like a blank.

## Score, or blank?

Ask one question: **is there a span I can quote that places this cell against the anchor
conditions?**

- **It meets an anchor** → emit that level, with the quote.
- **It clears one anchor and falls short of the next** → emit the level between them, 2 or 4, and
  say in the justification which two anchors it sits between. This is still a score: you have a
  quotable span and it places the cell. Evidence that speaks to the criterion without meeting an
  anchor is the most common shape there is, and it is not a blank.
- **Nothing quotable places it at all** → emit a blank. Do not reach for the nearest level and lower
  the confidence instead. A low-confidence number is still a number, and readers round numbers to
  facts.

There is no option where you score anyway because an empty cell looks bad on the page. An empty cell
that says why is the product working.

**If an anchor is worded as an absence** — "no source states X" — it is not an evidence condition
and nothing can be quoted against it. Emit `not-evidenced` when the search comes back empty, and say
in the note that the anchor cannot be met by a span. Do not score it as if silence were evidence:
the criterion needs rewriting, and a score would hide that.

## Which blank — and this is the part that is usually got wrong

The blank carries a **code**. The codes are not interchangeable labels for "no answer": each one
sends a reader somewhere different, and two of them are the ones that get confused.

**The discriminating question is: did the sources speak?**

| The sources… | Code | What a reader does next |
|---|---|---|
| …were never consulted; nobody has looked at this cell yet | `not-assessed` | schedule the work |
| …were not consulted, on purpose, because this cell was set aside | `deferred` | come back to it, or drop it deliberately |
| …**did not speak.** You searched, and they are silent on this | `not-evidenced` | go and find a source that would say — or accept that none exists |
| …**spoke and did not settle it.** They conflict, or they straddle anchors without choosing between them | `indeterminate` | read the conflict; it is often the most interesting thing on the page |
| …spoke, the answer is known, and it is not being shown here | `withheld` | ask whoever withheld it |
| …are beside the point; the criterion does not apply to this alternative | `not-applicable` | nothing; the cell is correctly empty |

**`not-evidenced` and `indeterminate` are the pair to be careful about.** They look the same from
outside — both are terminal, both mean someone looked and this is the answer — and they are
different findings about the world:

- `not-evidenced` says **there is a hole in the record.** It is an instruction to go looking.
- `indeterminate` says **the record is full and it does not resolve.** No amount of further
  searching in the same corpus fixes it; what is needed is a judgement about which source to trust,
  or a criterion sharp enough to discriminate.

Note what `indeterminate` is *not*: evidence that simply lands between two anchors. That is a 2 or a
4 — the cell is placed, just not on an anchored level. `indeterminate` is for evidence that
**straddles** anchors, pointing at two levels at once with nothing to choose between them.

Collapsing them loses the distinction in both directions. A reader who sees `not-evidenced` on a
contested cell will spend a day hunting for a document that already exists and already contradicts
another one. A reader who sees `indeterminate` on an unsearched cell will assume the question has
been settled as unsettleable, and stop.

**A contradiction does not automatically mean `indeterminate`.** Sources can disagree about
something the criterion does not ask about. The test is whether the conflict reaches the anchor:

- **The conflicting spans meet the *same* anchor condition** → **score it**, at that level, and name
  the disagreement in the justification as a downgrade with a reason. The cell is settled; the
  detail underneath it is not.
- **The conflicting spans meet *different* anchor conditions**, or the conflict is about which
  condition is met at all → **`indeterminate`**. There is no level to put it on.

So two contracts that name different regions, where the criterion asks only whether a *contractual
commitment naming a region* exists, is a score with a named conflict — both spans meet the same
condition. Two sources where one states a commitment and the other states there is none is
`indeterminate`: they land on different levels and nothing chooses between them.

**And a cell you have not searched is never terminal.** If the subject's own sources have not been
consulted for *this* criterion, the code is `not-assessed`, however much unrelated material happens
to be in hand. `not-evidenced` is a claim that a search happened and came back empty; making it
without searching is the confident guess in a different costume.

Two worked cases, on an invented comparison of two vendors against a *dated support commitment*
criterion:

> You search the vendor's site, its changelog and two industry summaries. None of them mentions a
> support window at all. → **`not-evidenced`**, note: "searched the vendor site, changelog and two
> industry summaries; none states a support window."

> The vendor's own page says "supported until 30 June 2029". A reseller datasheet from the same
> quarter says "support ends 2027". Nothing dates or supersedes either. → **`indeterminate`**, note:
> "vendor page states 2029, reseller datasheet states 2027; neither is dated later and nothing
> reconciles them." Cite **both** spans. The conflict *is* the evidence.

**Every blank carries a note.** A blank with no note is a shrug, and a shrug is not a finding. For
the codes that mean someone looked — `not-evidenced`, `indeterminate`, `withheld` — the note says
**what was searched and what came back**. `not-evidenced` in particular is only meaningful if the
note names where you looked; otherwise it means "I did not find it", which is a fact about you and
not about the subject. For `not-assessed` and `deferred` nothing was searched, so the note says
**why not** — what is outstanding, or whose instruction set the cell aside.

**If the analysis declares additional codes, you may use them**, and only those. An analysis may
extend the vocabulary for its own domain; each extension states what it means and which of the six
above it is a kind of. Never invent a code. A code nobody declared cannot be classified by a reader
that has not heard of it, so it is rejected rather than guessed at.

## Confidence — evidence quality, not how sure you feel

`confidence` grades **the evidence**, not your state of mind. Asking a model how sure it is produces
systematic overconfidence; asking how good the evidence is produces something a person can check.

| Level | Means |
|---|---|
| `high` | directly stated by a cited source |
| `medium` | inferred from adjacent evidence in a cited source |
| `low` | plausible reasoning with little support |

`low` means thin evidence. It never means *no* evidence — that case is a blank, not a low-confidence
score. If you find yourself reaching for `low` because there was nothing to read, you have picked the
wrong output; go back and choose a code.

Where sources contradict each other and you score anyway, that is a **downgrade with a named
reason**, not a quiet shading of the number: **one step down** from what the evidence would
otherwise carry, and say in the justification which sources disagree. One step, not an amount you
choose — otherwise the same cell scored twice gets two different confidences and every aggregate
over the column is noise.

For a level with no anchor of its own — a 2 or a 4 — confidence still grades the evidence, not your
placement of it. Quotable primary spans that clearly bracket the level are `high`.

## What to emit

`plan` comes first in every case — the sentences you wrote at step 1, kept as provenance. It is
emitted before the value fields, not after: writing the reasoning after the answer makes it a
justification of a decision already taken.

For a score:

- `plan` — what you set out to test, from step 1
- `value` — the level, from the criterion's own scale
- `confidence` — `high`, `medium`, or `low`
- `justification` — one line. What the evidence shows, not a restatement of the anchor. If you
  scored across a contradiction, name it here
- `evidence` — at least one span, quoted exactly, with its source and whether it supports,
  contradicts, qualifies or merely contextualises the claim; and marked as primary source, secondary
  summary, your own summary, or your own inference

For a blank:

- `plan` — as above
- `code` — from the table above, or from this analysis's declared extensions
- `note` — in one or two lines. For the terminal codes, what was searched and what came back; for
  `not-assessed` and `deferred`, why nothing was
- `evidence` — the spans you did find, when there are any. An `indeterminate` cell with its two
  conflicting quotes attached is far more useful than the same cell left empty. **`not-assessed` and
  `deferred` carry no evidence at all** — an attached span on an unsearched cell reads as proof that
  somebody searched, which is the exact misreading those two codes exist to prevent

The field names above are what each value is called; the shape you emit them in is supplied by the
caller, and the deterministic verb on the other side validates it. Do not invent a wrapper.

Worked, on the invented vendor comparison above:

> **score** — plan: "level 5 needs a span naming a dated commitment; level 3 needs a commitment with
> no date." value: 5. confidence: `high`. justification: "the vendor's own page states a dated
> window, which is the level-5 condition." evidence: "supported until 30 June 2029" — vendor support
> page, primary source, supports.

> **blank** — plan: as above. code: `not-evidenced`. note: "searched the vendor site, changelog and
> two industry summaries; none states a support window." evidence: none.

Then stop. The next cell is a separate call, with a separate plan.
