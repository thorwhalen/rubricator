---
id: rescore-criterion
version: 1
stage: 5
title: Re-score one criterion against new evidence
updated: 2026-11-02
missing-codes:
  - not-evidenced
  - indeterminate
  - not-applicable
  - not-assessed
  - deferred
changelog:
  - 1 (2026-11-02) — First version (#129). Re-scores one existing criterion, for the alternatives the user names or all of them, after the evidence changed. The earlier scores are withheld from the re-scoring generation by default, so the new level is not anchored on the old one: the prompt names the reads that would show them, reads instead only what carries no earlier value (`analysis_get` criteria and outstanding views), and says that an earlier score already in the conversation makes the pass shown whatever the model now does. The earlier claim is replaced through `measures_write` with `supersedes`, never written beside it, and its id is found without reading it, from the tools' default id and their refusals, which name an owner or a successor and never a value. Evidence is a fresh retrieval over the corpus as it now stands, not the new documents alone. Every per-cell rule is `score-cell`'s. Hypothesis: without it a model re-reads the earlier scores to "update" them (a shown prior, recorded as withheld), retrieves from the new document only, writes the new claim beside the old one, or routes a blank through `measures_mark_missing`, which cannot replace a claim; with it, each re-scored cell is one accepted write that names the claim it replaces and states the prior truthfully.
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
  the anchors, `criteriaVersion`) and with `view: "outstanding"` (which cells have never been written:
  `recorded: false`). Neither shows a score.
- **Do not read anything that returns this criterion's stored cells**: the analysis document itself,
  `report_weaknesses`, `aggregate_assertions`, `stability_report`. If you are unsure whether a read
  shows a value, do not make it until the writes are done.
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

`not-assessed` and `deferred` say nobody looked, and a re-score is someone looking, so neither is the
outcome of a re-scored cell.

## Writing it

One `measures_write` call per cell, as the same `contributor_id` and author that wrote the earlier
claim, with `expected_criteria_version` set to the `criteriaVersion` you read. The cell is the one
`score-cell` emits, plus `supersedes`. `confidence` and `dependsOn` stay beside it, as `score-cell`
says. A blank is a cell with `missing`, written the same way: `measures_mark_missing` cannot replace a
claim, so it is never used here.

**`supersedes` names your own live earlier claim in that cell**, which then stays in the record,
marked as replaced. You find its id without reading it:

- A cell `analysis_get` lists as outstanding with `recorded: false` has never been written. There is
  nothing to replace: write it without `supersedes`.
- Otherwise name the id the tools give a first claim: `<alternativeId>-<criterionId>-score`
  (alternative `vendor-b`, criterion `support-window`: `vendor-b-support-window-score`).
- If the write is refused because that claim "was already replaced by" another id, name that id
  instead: it is the live one. If it is refused because the claim is someone else's, you cannot
  replace it: write your cell without `supersedes`, so it stands beside theirs as a second claim,
  and tell the user whose it was. If it is refused because you have no assertion with that id, you
  have no claim there: write without `supersedes`. These refusals name an owner or a successor, never
  a value, so following them keeps the prior withheld. Nothing is written by a refused call.

Pass `procedure` on every write, stating only what is true of this pass:

- `round` — this sweep's number: the next after the sweeps that scored this analysis. Use the number
  the harness gives you; with none, the sweeps you know of plus one. Every cell of this re-score shares it.
- `session` — `"fresh"` if no earlier pass of these cells is anywhere in this conversation, `"same"` if one is.
- `prior` — `"withheld"` by default; `"shown"` when the earlier claims were in your context, by request
  or because they were already in the conversation.
- `traversal`, `reduction`, `seed` — the harness's, copied, or left out. Never invented.

## What to emit

When the request is not a re-score (the user wants the criterion itself changed), say so in one or
two sentences and ask; write nothing. When the earlier scores are in this conversation and the user
has not said to go ahead here, say so and ask; write nothing yet.

Otherwise, the writes, then a reply that ends with this block, one line each:

    Re-scored: <criterion id> — <n> of <m> alternatives: <alternative ids>
    Prior: withheld | shown — <one clause: why>
    Evidence: fresh retrieval over the corpus as it now stands
    Written: <k> scored, <j> blank (<codes>)
    Replaced: <cells whose earlier claim of yours was superseded, or "none">
    Beside another's claim: <cells, and whose, or "none">
    Next: <one step, e.g. compare with the earlier scores, or review>

Comparing with the earlier scores is a legitimate next step once every write is done: the pass is
recorded, so reading them then does not change what it was. Say that any further re-score of these
cells in this conversation would then be `"shown"`.

Worked, on an invented comparison of support vendors, criterion `support-window`, after the user
added a vendor's new lifecycle page and asked for the criterion to be re-scored for every vendor.
Nothing about the earlier scores was in the conversation. For `vendor-b`, the fresh retrieval
returned its new lifecycle page and nothing that contradicts it; the write, with the cell as
`score-cell` emits it and the claim it replaces named by the default id:

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

Its reply's `Prior` line reads `withheld — the earlier scores were not read and were not in this
conversation`.
