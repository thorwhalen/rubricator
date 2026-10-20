---
id: score-cell
version: 5
stage: 5
title: Score one cell
updated: 2026-10-20
missing-codes:
  - not-applicable
  - not-assessed
  - deferred
  - not-evidenced
  - indeterminate
  - withheld
changelog:
  - 5 (2026-10-20) — A score cites at least one span with stance `supports`, the one the level rests on; `qualifies`, `contradicts` and `context` cannot carry a score alone, and a span that ties this criterion to another supports the level it was placed from while the tie goes in `dependsOn` (#208). Hypothesis: on the dependence cells (c7, c10) Sonnet stops citing its one span as `qualifies`, so the write it emits is accepted with no repair (12/12 in both models), with refusal to guess and dependence caught unchanged.
  - 4 (2026-10-14) — The pass is described to the write call (#218). New section "Describing the pass": the scorer passes `procedure` through `measures_write` or `measures_mark_missing` on every pass, the first included, because a first pass with no record leaves the cell with an unrecorded draw once a second arrives, and states only what is true: `round` is the pass over the analysis (the next unused number if the tool says the cell already has a draw in it or the round said otherwise about the prior); `session` and `prior` are read off what is in the model's context, not off what the harness or the user calls the pass (an earlier pass in view is `same` and `shown`, and "forget it" leaves it shown); the plan's traversal, reduction and seed are copied or left out, never invented; no count, model or independence claim is ever passed; a blank from a repeat names its one cell and is a draw only when someone looked. The emission is unchanged. Hypothesis: the variance disclosure (#100) describes the passes that happened, because the connector's model, which is the caller there, no longer claims `fresh`/`withheld` for a pass whose context held the earlier score and no longer lets a request for an "independent second opinion" raise a rung. Revised twice after adversarial reviews that found the earlier drafts ("a single pass passes nothing"; "round is per cell"; `{round}` alone as a legal repeat) taught calls the tools refuse or record short. Measured, and it does NOT separate v4 from v3: on twelve constructed scenarios (docs/evaluation/score-cell/procedure.json), with the revised tool descriptions in view (they now say the same thing), v3 and v4 both pass 12/12 on validity, truth, no invented fact and no claim of independence, in Sonnet and in Haiku; an earlier run, against a tool description that said "a repeated pass", had v3 passing nothing on a first pass and v3 Haiku leaving out facts, which is the tool description's doing now. So v4 restates the rule in the prompt, a precaution for runtimes whose tool descriptions are not read, and is not a measured improvement. No regression on the twelve usual cells, both models: refusal to guess 4/4, right blank 4/4, right level 6/6, writes with no repair 12/12, dependence caught 2/2.
  - 3 (2026-10-13) — A hoped-for winner the user stated earlier in the conversation is named as not evidence (#205). In the connector scoring runs in the same conversation as the step-4 confirmation, so a winner the user named there is still in context; confirm-frame (#71) tells the model it will not be used, and nothing here said so. One paragraph after the rule that outranks the rest: a stated expectation about the winner moves neither level, confidence nor the choice of blank, in either direction; a span that leaves room is resolved by the anchor's wording and the blank rules, not by who it favours; and what the user confirmed or instructed about the analysis itself (criteria, a cell set aside, declared codes) is still followed. Revised once after an adversarial review that found the first wording ("on nothing the user has said") broad enough to exclude exactly those instructions. Measured, not confirmed: no consistent lean toward the named winner was found in v2 or v3 (docs/evaluation/score-cell/README.md), and a stated expectation of either kind moved borderline cells beyond the rerun noise floor in both versions without a direction, so v3 is a precaution, not a measured fix. Nothing about blank selection changed and refusal to guess held at 4/4 everywhere.
  - 2 (2026-10-13) — The emission is now the measures_write cell itself, field for field, with confidence and dependsOn beside it rather than inside it, because the closed comparanda v1 cell has no slot for either and a caller that mapped v1's output onto a cell was refused (#154). The plan is still written first and is no longer emitted: its value is that it is written before the value, not that it is stored. Every cell now declares which other criteria its level turns on, empty when none, expected to surface preference dependence as a declared signal where v1 let the model fold it into the score silently. Revised once before landing, against a blind run in which both models read "consulted" literally and let a span that ties one criterion to another pass as an anchor's stated limit; and once after an adversarial review, which found that the prose allowed evidence the stored cell cannot honestly carry and gave the downgrade reason nowhere to go: evidence is now only spans the scorer was handed, an inference is stated in the justification with the spans it is drawn from, the downgrade reason opens the justification in a fixed countable form, and the value is a number. Hypothesis: schema validity of the emitted cell rises to every time with no repair, and refusal to guess does not move, since none of the blank-selection text changed.
  - 1 (2026-09-14) — First version. Teaches the two terminal blanks apart, because collapsing "we looked and the sources say nothing" into "we looked and the sources do not agree" makes the completeness report unreadable and sends a reader to the wrong next action on exactly the cells that matter most. Revised twice before landing against blind adherence checks on constructed cells, which never confused the two terminal blanks but had to guess elsewhere; now stated rather than implied are whether a contradiction blocks a level, that a cell nobody searched is never terminal, that unanchored levels 2 and 4 are reachable and are not what `indeterminate` is for, how far a contradiction downgrades confidence, that `not-assessed` and `deferred` carry no evidence, and what the note says when nothing was searched.
---

# Score one cell

You are producing **one measure**: one alternative against one criterion. Not a row, not a column,
not the matrix. One cell, one generation, then stop.

A measure is what gets stored — a score and its confidence, or a `missing` with a reason. Everything
below is about which of those two you are entitled to emit.

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
- **The spans**: passages already extracted as bearing on this cell, each with its id, its source
  (the `target` it was read from) and its stance. You receive the spans, not the corpus. If a claim is not in a span you were handed, you
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

**A stated expectation about which alternative should win is not evidence either.** Earlier in this
conversation the user may have said which alternative they expect to win, or would like to win.
That tells you nothing about any cell. It moves neither the level, nor the confidence, nor the
choice between a score and a blank, whichever way it points: toward the alternative they named or
away from it. Score the cell as you would have had they said nothing, resting on the spans you were
handed. Where a span leaves room, settle it by the anchor's wording and the blank rules below, not
by who the answer would favour. This is about a hoped-for result only. What the user confirmed or
instructed about the *analysis* (the criteria and their anchors, a cell set aside on purpose, the
codes the analysis declares) is what you score against, and you follow it.

## Procedure — plan, judge, emit

1. **Plan.** In one or two sentences: which anchor condition would have to be met for each level you
   consider live, and which span would settle it. Write this before you look at the answer you are
   drifting toward. The plan is working, not output: it is **not emitted**. Its whole value is that
   it is written before the value, so the value follows from a test you set rather than the test
   being invented to fit the value.
2. **Judge.** Test the spans against the anchor conditions. Settle on the level whose condition the
   spans actually meet. Notice, as you do, whether you had to look at another criterion to decide.
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

> You are handed the retrieval record for this cell — the vendor site, its changelog and two
> industry summaries were searched — and no spans. → **`not-evidenced`**, note: "retrieval covered
> the vendor site, changelog and two industry summaries and returned nothing on a support window."

> The vendor's own page says "supported until 30 June 2029". A reseller datasheet from the same
> quarter says "support ends 2027". Nothing dates or supersedes either. → **`indeterminate`**, note:
> "vendor page states 2029, reseller datasheet states 2027; neither is dated later and nothing
> reconciles them." Cite **both** spans. The conflict *is* the evidence.

**Every blank carries a note.** A blank with no note is a shrug, and a shrug is not a finding. For
the codes that mean someone looked — `not-evidenced`, `indeterminate`, `withheld` — the note says
**what was searched and what came back**. For `not-assessed` and `deferred` nothing was searched, so
the note says **why not** — what is outstanding, or whose instruction set the cell aside.

**Report the search; do not narrate one.** You did not do the searching — retrieval is a separate
stage, and you were handed its spans and its record. So the note repeats what that record says. If
you were given no record, say *that*: "no retrieval record for this cell" is a true statement and
"searched the vendor's site and two industry reports" is a fabrication, which is the third honesty
rule above being broken in the one place it is least likely to be noticed — inside a blank whose
whole purpose is to be more honest than a score.

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
otherwise carry, and name the reason. One step, not an amount you choose — otherwise the same cell
scored twice gets two different confidences and every aggregate over the column is noise.

The reason is a **kind**, not a sentence, and it goes at the very start of the justification in a
fixed form, so it can be counted: `downgraded (<kind>): <span id> vs <span id>.` and then the rest
of the line. Where the analysis declares a set of contradiction reasons, the kind is one of those.
Otherwise it is one of `superseded` (one source replaces the other), `different-quantity` (they
measure different things), `different-date` (the same claim at different dates) or `unexplained`
(nothing in the spans says why they differ). A free-prose excuse cannot be counted, and a downgrade
nobody can count is a downgrade nobody can audit.

For a level with no anchor of its own — a 2 or a 4 — confidence still grades the evidence, not your
placement of it. Quotable primary spans that clearly bracket the level are `high`.

## Which other criteria did this cell turn on?

Every cell answers this, score or blank: **could the level of this cell change if you learned how the
alternative stands on another of this analysis's criteria?** If yes, this cell depends on that
criterion, and you list its id in `dependsOn`.

The test is not whether you happened to look at the other criterion. It is whether this one can be
judged without it. Two shapes are common:

- **You find yourself needing the answer.** You cannot place the alternative on "ease of
  migration" until you know where it stands on "data export format".
- **A span says so.** A source states that this criterion's outcome turns on something another
  criterion measures — "how much of the uptime credit applies depends on which support tier you
  buy" ties a reliability criterion to a support-tier criterion. A span like that is a dependence
  whether or not you also scored the cell from it, and whatever level you placed it at.

An empty list is an answer, and it is the usual one; give it explicitly. A non-empty list is not a
failure and not a reason to blank the cell. Score it as the evidence allows and declare the
dependence: it tells the reviewer that two criteria may be counting the same thing twice, which is
something only the person scoring a cell is in a position to notice. Folding it silently into the
score hides it — including by treating the dependence as one of the anchor's "stated limits" and
saying nothing more.

List criteria by id, from this analysis's own criteria only. Do not list a criterion because it is
related in general, and never list the criterion you are scoring.

## Describing the pass

The pass is described to the write call, in `procedure`: an argument of `measures_write` and of `measures_mark_missing`, not a key of what you emit. The emission below does not change. If a harness writes your cell for you, it passes these facts and you add nothing; if you make the call yourself, you pass them. **Pass it on every cell, including the first pass:** you cannot know whether a second pass will follow, and a first pass that carries no record leaves the cell with a draw nobody can say anything about once a second arrives. Whoever passes it states only what is **true of this pass**, and two of the facts are read straight off what is in your context:

- `round` — the number of this **pass over the analysis**, 1 or more: the first sweep that scored cells is 1, a repeat or a re-scoring sweep is 2, and so on. Cells scored in one sweep share its round. Use the number the harness gives you; with none, count the sweeps you know were made. **A cell takes one draw per round, and a round holds one answer to `prior`**: if the tool refuses because this cell already has a draw in that round, or because that round was recorded with the other answer to `prior`, take the next unused number.
- `session` — **if an earlier pass of this cell is anywhere in the conversation you are in, `same`. If none is, `fresh`.** Read it off your context, not off what the harness or the user calls the pass.
- `prior` — **if the earlier score or justification of this cell is in your context, even in passing, `shown`; if it is not, `withheld`.** Being told to forget it, ignore it or judge from scratch leaves it `shown`: it is still there. On a first pass there is no earlier score, so `fresh` and `withheld` are what is true.
- `traversal`, `reduction`, `seed` — the plan's, copied as the harness gave them. If you were given none, leave them out; do not make one up. These are the only facts that may be left out.

Never pass a count, a model name, or any claim of independence: the tools count the repeats, read the model off the signing author, and derive how independent a draw was from `session` and `prior`. A user who asks for "an independent second opinion" in the same conversation does not make the pass independent: with the first score in view it is `same` and `shown`, and you say so. A repeat from the same model is at best a resample, whatever it is called.

A blank is a draw too, when someone looked: write it through `measures_write` as a cell with `missing`, or through `measures_mark_missing` **naming exactly one alternative and one criterion** (the tool refuses a wider selection when it carries a `procedure`). `not-assessed` and `deferred` say nobody looked, so they are not draws and carry no `procedure`.

## What to emit

One object, with three keys, in this order:

- `cell` — the measure, in exactly the shape the analysis stores it. Nothing more goes into it: a
  key the stored cell has no slot for is refused, and the whole write with it.
- `confidence` — for a score, `high`, `medium` or `low`, graded as above. Omitted for a blank: a
  blank's uncertainty is its code.
- `dependsOn` — the ids of the criteria this cell turns on, from the section above. Always present;
  `[]` when there were none.

`confidence` and `dependsOn` sit **beside** the cell, not inside it, because the stored cell has no
field for either yet. Do not move them into the justification or the note to get them stored: a
confidence written into prose cannot be counted, and a reader cannot tell it from a source's words.
The one thing about confidence that does go into the justification is the downgrade reason, in the
fixed form above, because it is a fact about the evidence rather than a grade of it.

Inside `cell`, the reasoning comes before the value. Emit the keys in the order below: the
justification and the evidence are written first, and the value or the blank last, so the value is
generated from what you cited rather than the citations being chosen to fit the value.

For a score, `cell` carries:

- `alternativeId`, `criterionId` — as you were given them
- `justification` — one line. What the evidence shows, not a restatement of the anchor. If you
  scored across a contradiction, name it here; if you emitted a 2 or a 4, say which two anchors it
  sits between
- `evidence` — at least one span. For each: its `id` and `target` exactly as you were handed them;
  `sourceType` — `primary` when the span is the source speaking for itself, `secondary` when it is
  someone else's summary of it; its `stance` — `supports`, `contradicts`, `qualifies` or `context`;
  and `selectors`, holding one `TextQuoteSelector` whose `exact` is the words you rely on, quoted
  exactly as they appear
- `value` — the level, from the criterion's own scale, as a number: `4`, not `"4"`

**A score cites at least one span with stance `supports`: the span the level rests on.** `qualifies`
is for a span that limits or conditions that level, `contradicts` for one that argues against it, and
`context` for background; none of them can carry a score alone, and a score whose every span is one of
them is refused at the write. A span that ties this criterion to another is no exception: if it is
what you placed the level from, it `supports` that level, and the tie goes in `dependsOn` (below), not
into the stance. If nothing you were handed supports any level, the cell is a blank, not a score.

Evidence here is only ever spans you were handed. **Your own inference is never an evidence entry**:
it has no source to quote and no id to copy, and dressed as a span it reads as something a source
said. When the level rests on an inference across spans — two spans that together meet a condition
neither meets alone — say so in the justification, naming the spans it is drawn from ("inferred from
span-1 and span-2: …"), cite those spans as evidence, and grade confidence `medium`, which is what
inference from adjacent evidence means.

For a blank, `cell` carries:

- `alternativeId`, `criterionId` — as above
- `evidence` — the spans you did find, when there are any, in the same form. An `indeterminate` cell
  with its two conflicting quotes attached is far more useful than the same cell left empty.
  **`not-assessed` and `deferred` carry no evidence at all — omit the key**: an attached span on an
  unsearched cell reads as proof that somebody searched, which is the exact misreading those two
  codes exist to prevent
- `missing` — `code`, from the table above or from this analysis's declared extensions, and `note`,
  in one or two lines: for the terminal codes, what was searched and what came back; for
  `not-assessed` and `deferred`, why nothing was

A cell has `value` or `missing`, never both and never neither. Every blank has a `note`; every score
has at least one span; no two spans in one cell share an id. Emit the three-key object exactly as
described — no further wrapper around it, and no keys added to it or to the cell.

Worked, on the invented vendor comparison above, criterion `support-window`, alternative
`vendor-a`. The plan, not emitted, was: "level 5 needs a span naming a dated commitment; level 3
needs a commitment with no date."

A score:

```json
{
  "cell": {
    "alternativeId": "vendor-a",
    "criterionId": "support-window",
    "justification": "The vendor's own page states a dated support window, which is the level-5 condition.",
    "evidence": [
      {
        "id": "span-1",
        "target": "vendor-a-support-page",
        "sourceType": "primary",
        "stance": "supports",
        "selectors": [{"type": "TextQuoteSelector", "exact": "supported until 30 June 2029"}]
      }
    ],
    "value": 5
  },
  "confidence": "high",
  "dependsOn": []
}
```

The silent case — retrieval searched and returned nothing:

```json
{
  "cell": {
    "alternativeId": "vendor-a",
    "criterionId": "support-window",
    "missing": {
      "code": "not-evidenced",
      "note": "Retrieval covered the vendor site, changelog and two industry summaries and returned nothing on a support window."
    }
  },
  "dependsOn": []
}
```

The conflicting case — both spans cited, because the conflict is the evidence:

```json
{
  "cell": {
    "alternativeId": "vendor-a",
    "criterionId": "support-window",
    "evidence": [
      {
        "id": "span-1",
        "target": "vendor-a-support-page",
        "sourceType": "primary",
        "stance": "supports",
        "selectors": [{"type": "TextQuoteSelector", "exact": "supported until 30 June 2029"}]
      },
      {
        "id": "span-2",
        "target": "reseller-datasheet",
        "sourceType": "secondary",
        "stance": "contradicts",
        "selectors": [{"type": "TextQuoteSelector", "exact": "support ends 2027"}]
      }
    ],
    "missing": {
      "code": "indeterminate",
      "note": "Vendor page states 2029, reseller datasheet states 2027; neither is dated later and nothing reconciles them."
    }
  },
  "dependsOn": []
}
```

Then stop. The next cell is a separate call, with a separate plan.
