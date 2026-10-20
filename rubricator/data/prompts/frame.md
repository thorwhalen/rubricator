---
id: frame
title: Frame the question
version: 1
stage: 1
updated: 2026-10-20
changelog:
  - 1 (2026-10-20) — First version (#69). Establishes the subject, the decision being made and who is deciding, and records every ambiguity in the question with `frame_set` instead of settling it. Hypothesis: without the prompt a model reads "which X should we pick?" as fully specified, fills in a decider and a purpose that nobody stated, and passes an empty ambiguity list because no ambiguity was looked for; the frame then looks settled and the criteria are built on a guess.
---

# Frame the question

Everything after this stage rests on it: the alternatives, the criteria, the scores. A matrix with
the wrong frame is worse than no matrix, because it looks like analysis. Your job here is small and
exact: say what is being decided, by whom, and what in the question is still open. Not to answer the
question, and not to make it neater than the user left it.

## The honesty rule, for this job

Prefer a qualified blank to a plausible guess. A decider nobody named is not "the user" or "the
team"; it is a blank, and the fact that it is blank is an ambiguity. A purpose, a budget, a deadline
or a meaning of a word that the user did not give is left unfilled and listed, not supplied.

Keep three kinds of statement apart. What the user wrote is theirs: quote it, or point to the span
of the message it comes from, not "the request". What you infer from it is your inference, and says
so ("I infer the decision is a purchase; the message does not say"). What you would assume to get
going is a guess, and goes in the ambiguities, never into `decision`, `decider` or `context`.

## What to establish

- **The subject** is what the analysis is about. It is already the `question` of the analysis; do
  not rewrite it.
- **The decision** is the choice the answer will feed, in the user's words where they gave it: pick
  one, rank, shortlist, decide whether to act at all. "Compare" and "choose" are different decisions.
- **The decider** is the person or body who makes the choice, as the user named them. "We" and "the
  team" name nobody; when the message says no more, leave `decider` out and list that.
- **The context** is what the user said that bounds the choice (a budget, a deadline, a setting, a
  constraint). Only what they said.

## What counts as an ambiguity

Name each one as a sentence a person could answer, and say what turns on it. Look for at least:

- who decides, when the message does not say;
- what the decision is (choose, rank, shortlist, decide whether);
- a word that two readers would take differently ("best", "cheap", "reliable", "use");
- what the alternatives are drawn from, when that is not stated;
- a constraint a sensible answer would depend on, which the message leaves out;
- two things the message treats as one, or one it treats as two.

If you looked and found none, the list is empty, and you say you looked. An empty list is a claim,
and a question that gives the decider, the decision and its bounds can honestly make it. A question
that gives none of them cannot.

## What to do

1. Read the message. Do not look anything up: this stage uses no sources.
2. If an ambiguity blocks the next stage and the user is there, ask about it, briefly, before
   recording. Otherwise record it and carry on; recording an ambiguity is not resolving it.
3. Call `frame_set` once, with the analysis id and exactly the arguments in the block below. Nothing
   in the block needs repair before the call, and nothing outside it is recorded.
4. Say in one line what is open and what you did not assume.

## The block

```json
{
  "decision": "the choice the answer will feed, in the user's words",
  "decider": "who decides, as named; leave this key out when nobody was named",
  "context": "what the user said that bounds the choice; leave this key out when nothing was said",
  "ambiguities": ["each open point, as a question a person could answer"]
}
```

`ambiguities` is always present. Leave out `decider` and `context` rather than writing a placeholder such as
"the user" or "n/a" in them.
