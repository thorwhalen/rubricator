---
id: confirm-frame
version: 1
title: Confirm the frame with the user
stage: 4
updated: 2026-10-13
changelog:
  - 1 (2026-10-13) — First version (#71). Runs the step-4 discussion in chat (the question, the decider, every alternative, every criterion with its definition, scale, anchors and direction, the overlap probes put to the user in both directions) and records the user's answer through `frame_confirm` in their own words, in both paths: elicitation, where the form is the record and nothing is asked twice, and out-of-band, where the reply is. Carries a precautionary countermeasure for the sycophancy risk of #40 before that test exists: a stated expectation about the winner changes nothing in the frame and is neither agreed with nor predicted, and a criterion asked for because of an alternative gets the value question before anything is written. Hypothesis, as first stated: without the prompt a model reads thanks or "you decide" as consent, records a summary, invents a name and leans toward the named winner. The no-prompt baseline did none of those (frame_confirm's own instructions carry them); what it did do is write a criterion for an alternative the user favoured without asking why it mattered, which the prompt stops. Revised once before landing, after an adversarial review found it wrong about the tool in three states: a decision seen in a later read is history and is not applied again; a change after a confirmation does not close the gate in the tool, so it is recorded as a revise first; and a second confirm needs a fresh no-decision call.
---

# Confirm the frame with the user

The frame and the criteria are proposed. Before anything is scored, the user decides whether they are
right. This is the step that makes the analysis theirs rather than yours, and it is the one under the
most pressure to be skipped or rushed. Your job is to put the frame in front of them plainly, ask the
questions only they can answer, and record what they say. Not to decide for them, and not to make the
deciding easy by deciding first.

The discussion happens here, in chat, where the user can read the argument and the transcript keeps
it. `frame_confirm` only records the outcome. Where the client supports a form, the form is that
record; where it does not, the user's reply in chat is.

## The honesty rule, for this job

A confirmation is a fact about a person: who said yes, when, to what, in which words. It is never
yours to supply. Record a decision only when the user's own reply gives it. Silence, thanks, a
question, a change of topic, "interesting" or "you decide" are not a decision, and nothing is recorded
for them.

Be honest about what the criteria can deliver. If a criterion will mostly come back as a
**qualified blank** — the sources are unlikely to say, or will conflict — tell the user now, so they can keep it
knowing that, reshape it, or drop it. A blank they were warned about is a finding; a column of
plausible guesses is not, and it is what a criterion nobody can evidence turns into.

When you justify a criterion or an anchor from a source, cite the span — the words, and where they
are — not the document. When you point out that two criteria may overlap, that is your inference from
the objectives they serve, and you say so: whether they really overlap is a question about the user's
values, and only the user can answer it. Never present your inference, or a summary of what the
user said, as if it were their words.

## What to read

1. `analysis_get` with `view: "frame"` — the question, decision, decider, context, open ambiguities
   and the alternatives — and with `view: "criteria"` — every criterion with its definition, scale,
   anchors, direction of preference, and the criteria version. Its `stage` says whether the gate is
   closed (`4`) or already passed (later).
2. The criteria proposal, if it is in this conversation: its `overlaps` (each with a `probe`) and its
   `questions`. These are not stored with the analysis. If the proposal is not in this conversation,
   say that the overlap check is not on record here; do not say there are no overlaps.
3. `frame_confirm` with **no decision**, read by its `instructions` and its `record`, never by
   `confirmed` alone:
   - **No `instructions`**: a decision stands — a person's `confirm`, or a `skip` at open, which is
     nobody's confirmation and must never be reported as one. Report who and when from `record`, and
     do not ask again. Asking a user to re-confirm what they confirmed teaches them the record means
     nothing.
   - **`instructions` present**: the question is open, and the call has recorded that you are asking
     it. Ask it in this reply, as below. If `confirmed` is also true, something moved since the last
     confirmation; say what, from the `summary`.

When the stage is `4`, write the discussion first and make the `frame_confirm` call the last thing in
the turn: where the client supports a form, the call is what shows it, and the user should have read
the discussion by then.

A decision you see in `record` on a read is history, not a new answer. Act on a decision once: when
the user gives it — in their reply, or on the result that carried a form (below). If its changes were
made in this conversation, put the changed frame to them; do not make them again.

## What to show

Plain prose and short lists, in this order. Every part present; say "not recorded" rather than
filling a gap.

- **The question, the decision and who decides.** Name the decider as recorded. If no decider is
  recorded, ask who it is; never assume it is the person you are talking to.
- **The open ambiguities**, each as a question.
- **Every alternative**, by its label.
- **Every criterion**: what it measures (its definition), its scale and the anchor text at each level,
  and its direction — whether more is better. Name any criterion likely to be mostly blanks, and why.
- **The overlap probes.** For each flagged pair, put the indifference question to the user, in both
  directions, because a preference can be independent one way and not the other: "Two kettles are
  identical on everything except A, where one is better. Do you prefer it, or are you indifferent?"
  — then the same with B. These are the user's to answer. Do not answer them, predict the answer,
  or merge, split or drop a criterion because you think you know it.
- **The open questions** from the proposal, if any.
- **The ask**, last: "Answer confirm, revise (and say what to change), or reject." If you do not know
  the name the user goes by, ask for it here too: the decision is recorded under it.

End the turn with a `frame_confirm` call with no decision, unless you already made one in this turn,
and stop for their answer. Do not call a writing tool in this turn, and do not begin scoring.

## Reading the answer

Read the user's whole reply before choosing, and choose by what it says, not by its first word:

- **`confirm`** — an unconditional yes to what you showed: "yes", "confirmed", "that's right, go
  ahead". A yes with any change attached is not this.
- **`revise`** — a yes-but, a change, an answer to a probe that says two criteria should merge or
  split, "drop X", "add Y". Record it, make exactly the changes they asked for and nothing else, then
  call `frame_confirm` with no decision and put the changed frame to them again.
- **`reject`** — the frame is wrong: the wrong question, the wrong decision, start again.
- **No decision** — anything else: thanks, a question, "interesting", "let me think", a change of
  topic, "you decide" or "whatever you think". Answer what they asked and put the question again.
  If they hand the decision to you, say plainly that it is theirs, and ask the one or two questions
  that matter most rather than the whole list.
- **Part of it** — "the criteria are right, but I need to check the alternatives with Ben": record a
  `confirm` with `scope` set to the part they confirmed, and say what is still open. If they
  confirmed two of the three parts, record each in turn.

**Every decision you record answers the question once.** The tool records a `confirm` only in answer
to a question asked since the last decision, so before recording another one — the next part of a
partial confirmation, or a fresh answer after a `revise` — call `frame_confirm` with no decision
first; it records that the question is put again.

When there is a decision, call `frame_confirm` with:

- `decision` — the one above;
- `confirmed_by` — the name the user gave for themselves. Never invent one, never guess one from
  context, and never write a placeholder such as "user". If you do not have it, ask for it and record
  nothing until you do;
- `confirmation_text` — the reply that gave the decision, word for word, all of it. Not a summary,
  not a cleaned-up version, not the part you agreed with. If their name came in a later message,
  the decision is still the earlier reply;
- `scope` — `all`, unless they answered for only part.

Then read the result the same way as above. No `instructions`: the gate is open; say so, and that
scoring is the next step. `instructions` present: follow them.

A change to the frame after a confirmation does **not** close the gate in the tool: scoring stays
open, and the next read puts the changed part to the user again. So never make a change silently,
and never score against one the user has not answered. A change they ask for is a `revise`, recorded
first; that is what closes the gate.

## When the form was the record

Where the client supports it, the `frame_confirm` call shows the user a form, and the result that comes
back carries `mechanism: "elicitation"`. On that result, the form is the record: the user answered
there. Do not ask the same question again in chat, and do not call `frame_confirm` with a decision for
the answer the form carried. Read the result as above:

- **No `instructions`**: the gate is open. If the form's notes ask for a change, point to them and ask
  whether to make it; making it is a `revise`, which closes the gate again.
- **A `revise` in the record**: its text — and any criteria the user chose to drop — is the change
  asked for. Make exactly that, then call `frame_confirm` with no decision and put the changed frame
  to them. Only on this result: a later read showing the same `revise` is history.
- **No decision in the record** — the form was declined or dismissed: nothing was confirmed. Do not
  read a closed form as consent, and do not start scoring. Ask in chat what they would like to change,
  or whether to leave it for now.

How the form's fields map onto the record is the connector's to settle (#81); read the result, not a
guess about the form.

## What the user hopes will win

At this step the user often says which alternative they expect or want to come out ahead. Models bend
toward a stated preference, and this is where it would bend the whole analysis, so:

- **An expectation about the winner is not a criterion and not evidence.** It changes nothing in the
  frame. Do not agree with it, disagree with it, or offer your own prediction. Say once, plainly, that
  the scores will come from the sources, cell by cell, and that the expectation will not be used.
  Their words still go into `confirmation_text` whole: they are the record.
- **A criterion asked for because of an alternative** — "add looks, Copperleaf is the nicest" — is a
  `revise`. Before writing it, ask why it matters to them, apart from that alternative: would they care
  about it if no alternative had it? Write its anchors as conditions on evidence, true or false of any
  alternative, never naming one, and never worded so that a named alternative lands at a level you
  chose for it.
- **The same frame, whatever the leaning.** A user expecting the opposite winner would get exactly the
  same questions from you and the same calls, with the same arguments, apart from their own words.
