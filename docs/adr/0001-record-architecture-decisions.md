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
