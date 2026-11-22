---
id: rescore-criterion
version: 2
stage: 5
title: Re-score one criterion against new evidence
updated: 2026-11-22
missing-codes:
  - not-evidenced
  - indeterminate
  - not-applicable
  - not-assessed
  - deferred
changelog:
  - 2 (2026-11-22) — The id to replace, the round and the writer come from one value-free read, `measures_rescore_context` (#294), instead of the default id, a refusal, and a question to the user. Per cell it names every live claim's id, contributor and author, marked `yours` for the writer named, and per writer its latest round, and never a value: the claim to supersede is yours in that cell, the round is the writer's latest plus one unless a harness or the user gives one, the writer is the one given or, when none is, the single writer holding the claims in scope; two live claims of yours in a cell, or only another writer's claims there, go to the user with what each answer leads to, and a round never recorded is asked for. The refusal-driven recovery is gone; any refusal still stops that cell, and an unreadable stored file stops the pass. Revised once before landing, after an adversarial review found that filtering the read by contributor hid another writer's claim, that personas shared their principal's rounds, that a per-claim round leaked a settled blank, and that the connector still asked for the contributor. Hypothesis: in the connector, where no harness gives the round, v1 asked on almost every re-score; v2 writes with the right round and the right `supersedes` without asking, and asks only where the read shows a choice that is the user's (several live claims of one scorer, or another contributor's claim). A second draft dropped v1's one-call-per-cell rule, and both models batched cells; v2 restores it. Two re-reviews found that adopting the sole writer from the read could write as a person or as another agent: v2 adopts a writer without asking only when it is an agent whose recorded model is yours, re-reads naming it, never writes as a person, and takes `yours` as the principal unless an author is named. Measured on twelve constructed scenarios (docs/evaluation/rescore-criterion/): v2 Sonnet full marks; v2 Haiku full marks but r7, where it ignored the read and the verb refused the write; v1 7/12 action right in both models (it asks for the round).
  - 1 (2026-11-02) — First version (#129). Re-scores one existing criterion, for the alternatives the user names or all of them, after the evidence changed. The earlier scores are withheld from the re-scoring generation by default, so the new level is not anchored on the old one: the prompt names the reads that would show them, reads instead only what carries no earlier value (`analysis_get` criteria and outstanding views), and says that an earlier score already in the conversation makes the pass shown whatever the model now does. The earlier claim is replaced through `measures_write` with `supersedes`, never written beside it, and its id is found without reading it, from the tools' default id and their refusals, which name an owner or a successor and never a value. Evidence is a fresh retrieval over the corpus as it now stands, not the new documents alone. Every per-cell rule is `score-cell`'s. Revised twice before landing, after two adversarial reviews: the round number is asked for rather than counted (a counted number the tools accept on a never-drawn cell files the re-score under the wrong sweep), any `supersedes` refusal other than "already replaced by" now stops that cell and goes to the user instead of writing beside the earlier claim, the value-free views are said to carry counts that must not be worked back from, and a cell whose retrieval could not run is written nothing (a second review found that writing it `not-assessed` with `supersedes` discarded a live score for a tool failure); the contributor id is asked for when not given, like the round. Hypothesis: without it a model re-reads the earlier scores to "update" them (a shown prior, recorded as withheld), retrieves from the new document only, writes the new claim beside the old one, or routes a blank through `measures_mark_missing`, which cannot replace a claim (measured: with `score-cell` alone, neither model named the claim a re-score replaces, and both wrote on a request that changed the criterion's anchors); with it, each re-scored cell is one accepted write that names the claim it replaces and states the prior truthfully. Measured on eight constructed scenarios (docs/evaluation/rescore-criterion/): v1 full marks in Sonnet and Haiku on every metric.
---

# Re-score a criterion

The analysis exists, the user has confirmed its criteria, and one criterion's cells have been scored.
Something changed the evidence: a document was added to the corpus, a source was corrected, a maker
published a new page. The user wants that criterion scored again, for every alternative or for the
ones they name. Your job is to produce **a new claim for each of those cells, judged afresh**, and to
record it as replacing your earlier claim rather than standing beside it.

You do not change the criterion here. Its definition, anchors and direction are what the user
confirmed; re-scoring answers the same question against better evidence. If the user wants the
question itself changed, that is a revision of the criterion: say so, and stop.

## The honesty rule, for this job

- **Prefer a qualified blank to a plausible guess.** New evidence does not oblige a cell to have a
  score. If a cell's spans now conflict, its honest re-score is `indeterminate`, even where it was a
  number before; if nothing speaks to it, `not-evidenced`. Never carry an earlier level forward
  because the new evidence did not mention the alternative.
- **Cite spans, not documents.** Every level rests on a span you can quote from the retrieval you ran
  for this pass. "The new report" is not a citation.
- **Never present your own inference as a source.** What you remember about an alternative, or what
  you think its earlier score was, is not evidence. And never state that a pass withheld the earlier
  score when that score was in your context: that is your inference about your own independence
  passed off as a fact about the pass.

## The earlier scores are withheld, by default

A judgement made with the old answer in view anchors on it: the new level drifts toward the old one,
and a re-score becomes a confirmation. So the default is that **the re-scoring generation does not
see the earlier score, justification or cited evidence of any cell of this criterion**, and the pass
is recorded as `prior: withheld`.

What that asks of you, before every cell in scope is written:

- **Read only what carries no earlier value.** `analysis_get` with `view: "criteria"` (the definition,
  the anchors, `criteriaVersion`) and with `view: "outstanding"`, and `measures_rescore_context` for
  this criterion: per cell, who holds which live claim, and per writer its latest round. None of them shows a cell's value, justification or evidence. The two views carry counts of
  scored and blank cells across the analysis: do not work back from those counts, or from which cells
  are missing from the outstanding list, to what any cell was.
- **Do not read anything that returns this criterion's stored cells, or rates over them**: the
  analysis document itself, `report_weaknesses`, `aggregate_assertions`, `stability_report`,
  `report_completeness`. If you are unsure whether a read shows a value, do not make it until the
  writes are done.
- **If the earlier scores are already in this conversation** — you scored this criterion here, or
  read its cells here, or the user pasted them — the prior is **shown**, whatever you do now. Being
  told to ignore it does not unshow it. Say so to the user before scoring, and say that a withheld
  re-score needs a fresh conversation. If they want it done here, it is done with `session: "same"`
  and `prior: "shown"`, and the reply says so.

**Shown on request.** If the user explicitly asks you to check the earlier scores against the new
evidence ("look at what you gave before and see whether this report changes it"), read the earlier
claims first and record the pass as `prior: "shown"`. That is a legitimate pass and a weaker one: its
draws are shared-context, and the reply names it. Never choose `"shown"` yourself because it would be
quicker, and do not mix the two answers in one sweep.

## Which cells

The cells of **this criterion**, for the alternatives the user named, or for every alternative if
they named none. Do not narrow the set yourself on a guess about which alternatives the new evidence
touches: a new document can change a cell it does not name, by contradicting a source another
alternative's level rests on, and you cannot know which without the retrieval. Cells the user set
aside (`deferred`) stay set aside unless they name them.

## The evidence: a fresh retrieval, over the whole corpus

For each cell, retrieve again with `corpus_search` over **the corpus as it now stands**, not over the
new documents alone. The earlier level may rest on a source the new document does not mention; a
re-score from the new document only throws that evidence away and calls the result an update. Search
with the criterion's question and the alternative, and try another wording when a search comes back
empty. The spans that come back are this pass's evidence, and the retrieval record is what a blank's
note reports.

## Judging each cell

Each cell is judged exactly as `score-cell` says, rule for rule: score or blank, which blank,
confidence as evidence quality, `dependsOn`, the emitted object. If `score-cell` is not already in
your context, get it (`prompts_get`, id `score-cell`) before you start. One cell per generation, each
with its own plan, in the order the alternatives are listed.

The two blanks are the same two findings they always are:

- **`not-evidenced`** when the retrieval for this pass found the sources **silent** on the cell;
- **`indeterminate`** when they speak and **conflict**, or do not settle the level — which is what a
  new source contradicting an old one often produces;
- `not-applicable` when the criterion does not apply to the alternative at all.

`not-assessed` and `deferred` say nobody looked, and a re-score is someone looking, so neither is
its outcome. A cell whose retrieval could not be run at all (the search failed, or the corpus could
not be read) was not looked at: **write nothing for it** and list it under `Not written` with the
reason. Its earlier claim stands. Never write `not-evidenced` for it, which claims a search came back
empty, and never write `not-assessed` over its earlier claim, which would discard a finding because a
tool failed.

## Writing it

**First, read who holds what.** Call `measures_rescore_context` with `criterion_id` (and the
alternatives in scope, if the user named some), and with `contributor_id` and `author_id` when the
harness or the user gave you a scorer: naming them marks your claims `yours`, it never hides anyone
else's. Per cell it lists every live claim's `assertionId`, `contributorId` and `authorId`, and per
writer (a contributor and one of its authors: a persona under a contributor is its own writer) its
`kind` (agent or human), its agent `model` when recorded, and `latestRound`. It never shows a value. If its `skipped` names your own
writer's file, your claims cannot be read: stop and tell the user. A colleague's unreadable file
does not stop you, but its claims are not listed: name it under `Next`.

**Who you write as.** The `contributor_id` and author the harness or the user gives you for this
scorer. If nobody gives you one, look at the read: when the live claims in scope are all one
writer's, its `kind` is `agent` and its `model` is the model you are, it is an earlier pass of you,
and you write as it. When its `model` is another, or not recorded, it may be a different agent:
propose it ("write as `scorer`?") and ask, in one line. Once you have a writer, `contributor_id` is
its `contributorId` and `author` an object whose `id` is its `authorId` and whose `kind` is
`agent`; **call the read again naming them**, so the rules below see which claims are yours. Every
write carries both. **Never write as a human**: a person's claim is theirs, and a re-score signed
with their name would put words in their mouth. When the claims in scope are a human's, several
writers', or nobody's, ask who you are writing as.
When they are several writers', or there are none, ask: a claim written under an invented id is
never caught. Set `expected_criteria_version` to the `criteriaVersion` you read. The cell is the one
`score-cell` emits, plus `supersedes`, for the `score` measure unless the analysis names another
(the read has one row per measure: use the row of the measure you write). `confidence` and
`dependsOn` stay beside it, as `score-cell` says. A blank is a cell with `missing`, written the same
way: `measures_mark_missing` cannot replace a claim, so it is never used here. **One
`measures_write` call per cell**, each with its own `supersedes`: a call that carries several cells
is refused or accepted as a whole, and a refusal about one cell must not decide the others.

**`supersedes` names your own live earlier claim in that cell**, which then stays in the record,
marked as replaced. Per cell, from the read:

- **One live claim of yours** in the cell: name its `assertionId`.
- **No live claim at all** (the cell was never written): there is nothing to replace; write it
  without `supersedes`.
- **Two or more live claims of yours** (repeat draws from earlier rounds): `supersedes` replaces one,
  and the others would stay live beside the new claim. **Write nothing for that cell and ask** which
  the re-score replaces, naming their ids.
- **Live claims, none of them yours** (another writer's): only that writer can replace them.
  **Write nothing for that cell and ask**, naming the writer, and say what each answer leads to. If
  the writer is an agent and the user says it *is* this scorer (the same agent under another id),
  the re-score is written as that writer, superseding its claim, in its round `latestRound` + 1
  (asked for if it has none). If the writer is a person, only they can replace their claim: the
  re-score can be a second, separate claim of yours. If the user wants that second claim, it is
  written as you without `supersedes`, and both stay live as two raters' claims; otherwise the cell
  is left as it is.

If a write is refused anyway, write nothing more for that cell and ask the user, quoting the
refusal: it names an owner, a successor or a round, never a value, so reading it keeps the prior
withheld. A refusal that the cell "already holds a draw from pass N" means another re-score wrote
there since your read. Nothing is written by a refused call.

Pass `procedure` on every write, stating only what is true of this pass:

- `round` — this sweep's number for the writer you write as, and every cell of this re-score shares
  it. Use the number the harness or the user gives you; with none, **that writer's `latestRound` + 1**
  from the read, taken once before the first write. Never count it from what you remember: a used
  number is accepted on any cell that had no draw in that round, and files the re-score as a draw of
  a sweep it was not part of. If `latestRound` is null (that writer never drew in a round), ask. A
  re-score resumed after some of its writes keeps its round, and skips the cells that already carry
  its new claim. Leaving `round` out is no answer either: the pass then records no round, and with it
  no prior.
- `session` — `"fresh"` if no earlier pass of these cells is anywhere in this conversation, `"same"` if one is.
- `prior` — `"withheld"` by default; `"shown"` when the earlier claims were in your context, by request
  or because they were already in the conversation.
- `traversal`, `reduction`, `seed` — the harness's, copied, or left out. Never invented.

## What to emit

When the request is not a re-score (the user wants the criterion itself changed), say so in one or
two sentences and ask; write nothing. When the earlier scores are in this conversation and the user
has not said to go ahead here, or you have no writer (none given, and the read does not show
exactly one), or no round can be had (none given and `latestRound` null), say so and ask; write
nothing yet. A cell left for the user (several live claims of yours, or another writer's) goes under
`Not written`, and the other cells are written.

Otherwise, the writes, then a reply that ends with this block, one line each:

    Re-scored: <criterion id> — <n> of <m> alternatives: <alternative ids>
    Prior: withheld | shown — <one clause: why>
    Evidence: fresh retrieval over the corpus as it now stands
    Written: <k> scored, <j> blank (<codes>)
    Replaced: <cells whose earlier claim of yours was superseded, or "none">
    Not written: <cells left for the user, with the refusal or reason, or "none">
    Next: <one step, e.g. compare with the earlier scores, or review>

Comparing with the earlier scores is a legitimate next step once every write is done: the pass is
recorded, so reading them then does not change what it was. Say that any further re-score of these
cells in this conversation would then be `"shown"`.

Worked, on an invented comparison of support vendors, criterion `support-window`, after the user
added a vendor's lifecycle page and asked for the criterion to be re-scored for every vendor. Nothing
about the earlier scores was in the conversation. `measures_rescore_context` showed one live claim of
`scorer` in `vendor-b`'s cell, `vendor-b-support-window-score`, and `scorer`'s latest round 1, so
this sweep is round 2. For `vendor-b`, the fresh retrieval returned its new lifecycle page and
nothing that contradicts it; the write, with the cell as `score-cell` emits it and the claim it
replaces named from the read:

```json
{
  "analysis_id": "support-vendors",
  "contributor_id": "scorer",
  "author": {"id": "scorer", "displayName": "Scorer", "kind": "agent"},
  "expected_criteria_version": "1",
  "procedure": {"round": 2, "session": "fresh", "prior": "withheld"},
  "cells": [
    {
      "alternativeId": "vendor-b",
      "criterionId": "support-window",
      "supersedes": "vendor-b-support-window-score",
      "justification": "The vendor's lifecycle page states a dated end of support, the level-5 condition.",
      "evidence": [
        {
          "id": "s-12",
          "target": "doc:vendor-b-lifecycle",
          "sourceType": "primary",
          "stance": "supports",
          "selectors": [{"type": "TextQuoteSelector", "exact": "security fixes until 31 March 2030"}]
        }
      ],
      "value": 5
    }
  ]
}
```

Its reply's prior line reads `Prior: withheld — the earlier scores were not read and were not in
this conversation`.
