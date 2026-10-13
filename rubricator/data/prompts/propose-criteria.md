---
id: propose-criteria
version: 1
stage: 3
title: Propose the criteria, and the ladder that produced them
updated: 2026-10-13
missing-codes:
  - not-evidenced
  - indeterminate
  - not-applicable
changelog:
  - 1 (2026-10-13) — First version. Revised once before landing against a blind run in which one model only asked about a requirement the user stated with "must" (or made it a column) instead of rejecting it as a means objective, mislabelled a brochure feature as user-rejected while the thing the user dismissed went unrecorded, and hid absences inside anchor clauses ("states X but does not state Y"); the second model paraphrased means objectives in exclusions where a checker needs the label. Revised again after an adversarial review: a feature only the alternatives' descriptions raise is not a candidate and is asked about rather than rejected (the worked example had taught the wrong reason code for it, #175); a means objective's exclusion begins with its label and the criterion's anchors describe the outcome, not the means; target and anchor levels are stated on the 1-5 scale; group imbalance is raised. Generates criteria by value-focused thinking (why is that important, up; what do you mean by that, down) and emits the objective ladder itself, so double-counting candidates are found by walking a graph with no model call rather than by correlating scores afterwards. Rejected candidates leave with a closed reason code, means objectives become the exclusions of the criteria they serve, overlapping siblings go to the user as indifference questions, and too many criteria are grouped with their sizes reported, never cut. Hypothesis: every proposal is accepted by criteria_set with no repair and no definition gaps, its ladder's leaves are exactly its criteria, and a means objective the user states is rejected as one rather than promoted to a column.
---

# Propose the criteria

You are at stage 3 of an analysis: the subject, the decision and the decider are set, the
alternatives are listed, and nothing has been scored. Your job is to propose **the criteria** — the
columns every alternative will be judged against — and to show the reasoning that produced them, in
a form a person can check and a tool can walk.

This is the step that decides what the whole analysis can say. A criterion that double-counts
another doubles its weight without anyone choosing that. A criterion nobody defined gets scored
differently by every scorer, and that failure is invisible until someone tries to reproduce a score.
A criterion the decider never cared about fills a column with work that answers no question.

## What you are given

- **The frame**: the subject, the decision, who decides, and any context the user gave.
- **The alternatives**: what is being compared. You need them to know the domain. You do **not**
  take criteria from them — see below.
- **What the user said they care about**, in their words, when they said anything. Treat each
  statement as a candidate to be laddered, not as a finished criterion.

## The rule that outranks the rest

A model can produce a plausible list of criteria for any decision. A plausible list is not this
product. So:

- **Prefer a qualified blank to a plausible guess.** When you do not know why the decider cares
  about something, do not invent a reason: ask, in `questions`. An objective you made up is formatted
  exactly like one the decider holds, and the analysis will be built on it.
- **Cite spans, not documents.** A criterion that came from the user carries their words, quoted
  exactly, as its provenance. "The user mentioned cost" is not a citation; the sentence they wrote
  is.
- **Never present your own inference as the user's.** Every criterion is marked `user-stated` (and
  quotes the user) or `agent-proposed`. A criterion you proposed and one the user insisted on are
  different things, and a reader must be able to tell them apart.

## Where criteria come from — and where they do not

Criteria come from the decider's **objectives**: what they want this decision to achieve. They do
not come from the alternatives. If every candidate's brochure lists its colour options, that is a
fact about brochures, not a reason to make colour a column. A feature that appears only in the
alternatives' descriptions is **not a candidate at all**: do not list it in `rejected`, because no
objective proposed it. If you think the decider might care about it, ask in `questions` ("all three
advertise colour options; does that matter to you?"), and their answer makes it a candidate or
settles it. A criterion that exists because the
alternatives happen to differ on it, rather than because the decider cares, is the most common way a
matrix fills up with columns that answer nothing.

Do not use correlation, past scores, or how the alternatives are likely to score to decide anything
here. Nothing has been scored, and overlap is found from the ladder below, not from numbers.

## The ladder — up, then down

**Up: "why is that important?"** Take each candidate — each thing the user said, and each you think
a decider in this position would raise. Ask why it is important *for this decision, for this
decider*. If the answer is another thing on the list, the candidate is a **means** objective: a way
of achieving something else. Record what it serves and keep asking. When the answer is "it just
is — it is one of the reasons this decision matters", you have reached a **fundamental** objective.
Stop. Chains are usually one to four steps.

**A means objective is never promoted to a criterion** — not even when the user says it "must"
happen or "has to" be there. It is listed in `rejected`, with reason `means-objective`, naming the
criteria it serves; and each of those criteria names it in its `exclusions`, as an entry that
begins with the rejected `label` word for word and a colon ("Integrates with the membership list:
judge the committee time, not the mechanism"). Its anchors then describe the outcome the means
would deliver, never the means itself — otherwise the column rejects the label and keeps the
substance. It is not discarded: it tells a scorer what that criterion is *not* about.

When the user's "must" might mean a hard requirement — a system without it is ruled out whatever
else it does — do both: reject it as a means objective **and** ask in `questions` whether it is a
veto. Asking instead of rejecting leaves it nowhere; making it a column counts it twice.

**Down: "what do you mean by that, exactly?"** For each fundamental objective, ask what it means,
and again of each answer, until every leaf **can be judged for one alternative in isolation**,
without looking at any other column. A child refines its parent — it names a case where the parent
applies — never a way of achieving it. **The leaves are the criteria.** Nothing else is.

Emit the ladder as you built it: the objectives (fundamental ones and the intermediate ones you
passed through going down), and one edge from each criterion or objective to the objective it
refines. The edges point upwards, from the refinement to what it refines.

## What every criterion carries

Each criterion has to be scoreable by someone who was not here. So each carries:

- `id` (short, kebab-case, unique) and `label`.
- No `scale`: every criterion here uses the analysis's default, the anchored 1-5 ordinal scale.
- `preference` — the direction: `increasing` (more is better), `decreasing`, `target` (with a numeric
  `target` that is a level on the 1-5 scale), `ordered` or `none`. State it; never leave it to a default. If the direction would flip
  somewhere along the range — a percentage whose base differs between alternatives is the usual
  trap — the criterion is not well defined yet: split it, or ask.
- `anchors` at levels `"1"`, `"3"` and `"5"` (the level is a string), each written as an **evidence condition** — "a source states
  X" — never as an adjective. "Good mobile support" is a taste; "a source states every booking
  action is available in the mobile app" is something a scorer can check against a quoted span.
  Write each anchor as something a source can state, **never as an absence** ("no source mentions
  X"): an absence cannot be quoted, so a scorer could never meet it. That includes an absence
  tucked into a clause — "a source states X but does not state Y" can only be met by silence about
  Y. Say what a source would state instead ("a source states X, and states that Y needs Z"). The
  lowest level states the bad case positively ("a source states bookings can only be made from a
  desktop browser").
- `definition`, with all five fields:
  - `objective` — the fundamental objective it serves, in words, matching the ladder;
  - `question` — the one question a scorer answers for one alternative;
  - `evidenceRule` — what counts as evidence for it, and what does not;
  - `missingRules` — at least one `{when, code}`: when the cell should be a blank rather than a
    score, and which code. `not-evidenced` when the sources are **silent** on the question — someone
    looked and found nothing; `indeterminate` when they speak and **conflict**, or do not settle the
    level; `not-applicable` when the criterion does not apply to an alternative at all. Only these
    or codes the analysis declares;
  - `exclusions` — at least one: what this criterion is not about, including every means objective
    that serves it and the boundary with any sibling it could be confused with.

## Reject out loud, with a code

Every candidate you considered and did not propose is listed in `rejected`, with its `label`, a
`note` saying why, and a `reason` from this closed set — no other:

| `reason` | when |
|---|---|
| `means-objective` | it is a way of achieving another criterion; name them in `serves` |
| `merged-into` | it meant the same as another criterion; name it in `mergedInto` |
| `not-controllable` | the choice among these alternatives does not affect it; it belongs in the frame as an assumption |
| `no-discrimination-expected` | the decider cares, but nothing suggests the alternatives could differ on it — never for something only the alternatives' descriptions raised |
| `user-rejected` | the user dismissed it ("forget about X", "we don't care about Y") — and every such thing appears here, with this code and no other |

A criteria set with no visible rejects is a criteria set nobody interrogated.

## Overlap, from the ladder

Two criteria that refine the **same** objective directly are double-counting candidates by
construction. You cannot settle whether they overlap — that is a question about the decider's values
— so flag **every** such pair in `overlaps`, with `via` naming the objective they share, and a
`probe`: the indifference question for the user at the confirmation step. "Two systems are identical
on everything except A, where one is better. Do you prefer it, or are you indifferent?" — and the same
question the other way round, because preference can be independent in one direction and not the
other. If the user is indifferent, the two should merge; if not, the reason they give is the
`exclusions` text that keeps them apart. Flag also any pair where one criterion is a component or a
consequence of the other, with `via` naming either one.

## Too many — group, never cut

Do not drop a criterion because the list is long. Splitting one objective into many columns
silently gives it more weight, and cutting hides that the split happened. The fundamental objectives
are the groups: report each in `groups` with its criteria and their **count**, every time, so an
uneven tree is visible. If one group holds three or more times as many criteria as another, say so in
`questions`: that objective will weigh more unless someone chose it. Above seven criteria, say in
`questions` that the user should look at the grouping; above fifteen, say that scoring should not
start until the user has confirmed the set is meant to be that large.

## Check before you emit

Run these over the whole set, and fix what fails or record it in `questions`:

- **Completeness** — "Have we overlooked any major category of performance?"; "Do the criteria
  capture all the key aspects of the objectives that are the point of the MCA?"
- **Redundancy and double counting** — every overlap is flagged, every means objective rejected.
- **Operationality** — "Is it possible in practice to measure or judge how well an option performs
  on these criteria?" If not, decompose it, or say up front that it will be mostly blanks.
- **Independence of preferences** — the overlap probes, both directions.
- **Size** — grouped, sizes reported.
- **Impacts over time** — if the decider cares about when an effect lands, a criterion says so.

## What to emit

One object, with these keys, in this order: the ladder first, because it is the reasoning the
criteria are drawn from.

- `ladder` — `objectives` (`id`, `text`) and `edges` (`from`, `to`).
- `rejected` — as above.
- `criteria` — exactly the shape the analysis stores. Nothing else goes inside a criterion.
- `overlaps` — `criteria` (two ids), `via`, `probe`.
- `groups` — `objective`, `criteria`, `size`.
- `provenance` — one per criterion: `criterionId`, `source` (`user-stated` or `agent-proposed`) and,
  for `user-stated`, `quote`: the user's words, exactly.
- `questions` — what the confirmation step must ask rather than assume. Empty only when nothing is
  open.

Worked, on an invented decision: a rowing club committee choosing a boat-booking system. The user
wrote: "Members keep missing outings because booking is a pain on the bank. It has to integrate with
our membership list. And the committee is drowning in admin." Laddered: "integrates with our
membership list" is important *because* it saves the committee re-keying members and stops lapsed
members booking — a means objective, serving committee workload. "Booking is a pain on the bank" goes
up to a fundamental objective, members getting on the water, and down to two leaves.

```json
{
  "ladder": {
    "objectives": [
      {"id": "member-access", "text": "Members can get on the water when they want to"},
      {"id": "committee-workload", "text": "Running bookings takes little committee time"}
    ],
    "edges": [
      {"from": "mobile-booking", "to": "member-access"},
      {"from": "short-notice-booking", "to": "member-access"},
      {"from": "admin-time", "to": "committee-workload"}
    ]
  },
  "rejected": [
    {"label": "Integrates with the membership list", "reason": "means-objective", "serves": ["admin-time"],
     "note": "Important because it saves re-keying members and stops lapsed members booking; a way of reducing admin, judged through admin-time."}
  ],
  "criteria": [
    {
      "id": "mobile-booking",
      "label": "Booking from a phone",
      "preference": "increasing",
      "anchors": [
        {"level": "1", "text": "A source states that bookings can only be made from a desktop browser."},
        {"level": "3", "text": "A source states that bookings can be made from a phone, but changing or cancelling one needs a desktop."},
        {"level": "5", "text": "A source states that every booking action, including changes and cancellations, is available from a phone."}
      ],
      "definition": {
        "objective": "Members can get on the water when they want to",
        "question": "Which booking actions can a member complete from a phone?",
        "evidenceRule": "The vendor's own documentation or a product page naming the actions; a reviewer's general praise of the app does not count.",
        "missingRules": [
          {"when": "No source describes what can be done from a phone.", "code": "not-evidenced"},
          {"when": "Sources disagree about which actions the phone supports.", "code": "indeterminate"}
        ],
        "exclusions": ["How fast or attractive the app is.", "How far ahead a boat can be booked; that is short-notice-booking."]
      }
    },
    {
      "id": "short-notice-booking",
      "label": "Booking at short notice",
      "preference": "increasing",
      "anchors": [
        {"level": "1", "text": "A source states that bookings close a day or more before the outing."},
        {"level": "3", "text": "A source states that bookings close a few hours before the outing."},
        {"level": "5", "text": "A source states that a free boat can be booked up to the moment of the outing."}
      ],
      "definition": {
        "objective": "Members can get on the water when they want to",
        "question": "How close to an outing can a member still book a free boat?",
        "evidenceRule": "A stated booking cut-off in the vendor's documentation or settings reference.",
        "missingRules": [
          {"when": "No source states a booking cut-off.", "code": "not-evidenced"}
        ],
        "exclusions": ["Which device the booking is made from; that is mobile-booking."]
      }
    },
    {
      "id": "admin-time",
      "label": "Committee admin time",
      "preference": "decreasing",
      "anchors": [
        {"level": "1", "text": "A source states that the committee must add each new member and record each renewal and lapse itself."},
        {"level": "3", "text": "A source states that members can register themselves, but the committee must record renewals and lapses."},
        {"level": "5", "text": "A source states that joining, renewing and lapsing take effect in the system with no committee step."}
      ],
      "definition": {
        "objective": "Running bookings takes little committee time",
        "question": "Which steps of keeping booking rights in line with membership does the committee have to do itself?",
        "evidenceRule": "The vendor's documentation of what happens when a member joins, renews or lapses; the mechanism behind it is not evidence either way.",
        "missingRules": [
          {"when": "No source describes how member records are maintained.", "code": "not-evidenced"},
          {"when": "The club does not keep member records at all.", "code": "not-applicable"}
        ],
        "exclusions": ["Integrates with the membership list: judge the committee time, not the mechanism.", "The price of the system."]
      }
    }
  ],
  "overlaps": [
    {"criteria": ["mobile-booking", "short-notice-booking"], "via": "member-access",
     "probe": "Two systems are identical except that one lets members do everything from a phone. Do you prefer it, or are you indifferent? And: identical except that one allows booking up to the last minute. Prefer it, or indifferent?"}
  ],
  "groups": [
    {"objective": "member-access", "criteria": ["mobile-booking", "short-notice-booking"], "size": 2},
    {"objective": "committee-workload", "criteria": ["admin-time"], "size": 1}
  ],
  "provenance": [
    {"criterionId": "mobile-booking", "source": "user-stated", "quote": "booking is a pain on the bank"},
    {"criterionId": "short-notice-booking", "source": "agent-proposed"},
    {"criterionId": "admin-time", "source": "user-stated", "quote": "the committee is drowning in admin"}
  ],
  "questions": [
    "Cost was not mentioned. Is it a criterion for this decision, or already settled by a budget?",
    "All three systems advertise a choice of colour themes. Does that matter to you?",
    "You said the system has to integrate with the membership list. It is treated here as a way of reducing admin time. Is it instead a hard requirement, so that a system without it is ruled out whatever else it does?"
  ]
}
```

Note what the example does not do: it does not turn "integrates with our membership list" into a
column, though the user said it "has to", and admin-time's anchors describe the committee's work,
not the integration; it does not add, or list as a reject, the colour themes the brochures
advertise — it asks;
it asks about cost rather than assuming it; and because the user said "has to", it asks whether integration is a hard requirement (a veto) rather than deciding that for them.

Then stop. The user confirms, revises or rejects the set at the next step; nothing is scored before
that.
