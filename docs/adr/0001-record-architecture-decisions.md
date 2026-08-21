# ADR-0001: Record architecture decisions

- **Status:** accepted
- **Date:** 2026-08-18

## Context
Specified before implementation, and executed largely by agents across sessions with no shared
memory. Decisions must survive the session that made them.

## Decision
Nygard-format ADRs, numbered, immutable once accepted. Supersede rather than edit. An ADR marked
**proposed** is a live question whose Decision section is a recommendation, not a ruling — settle
it during implementation and change the status with reasoning.

## Consequences
`docs/adr/` read in order tells a newcomer both what was decided and what is still open.

## Amendments

### 2026-08-21 — Confirmed by round-1 research (no change to the decision)

Round-1 research reviewed this ADR and confirms it. Nothing above changes; this note records that
someone looked, so a later session can tell agreement from inattention.

The numbering discipline is what let seven independently written research sections converge without
collision. Collisions did occur — the sections proposed overlapping ADR numbers for different
decisions — and the rule is what made them a renumbering rather than an argument: the new ADRs were
consolidated into one sequence from 0009.

Every escape valve has now been exercised, which is the better evidence. ADR-0004 was **superseded**
by ADR-0009 rather than edited, once reading the code showed its premise was false. ADR-0007 was
**settled in place** from `proposed` to `accepted` with the reasoning recorded — exactly the path the
Decision above reserves for a live question. Accepted ADRs that needed a correction or an addition
short of a reversal, this one included, carry a dated `## Amendments` section instead, leaving the
original Context, Decision and Consequences untouched.

Evidence: [`docs/research/findings-method.md`](../research/findings-method.md), § "Recommended ADR
actions" and § 7 ("Conflicts between sections, resolved").
