# ADR-0002: Separate repository, joined only by the schema

- **Status:** accepted
- **Date:** 2026-08-18

## Context
Producing a comparison and presenting one are different problems with different dependencies,
different release rhythms and different languages. Bundling them would force an LLM dependency on
anyone who only wants to render a table, and a UI toolchain on anyone running a headless agent.

## Decision
Two repositories. The only coupling is the **comparanda analysis schema**, consumed here as a
published JSON Schema artifact and validated at the boundary.

`rubricator` depends on `comparanda` for the schema. `comparanda` never depends on `rubricator`.
An analysis is equally valid whether a human, this agent, or a script produced it — and
`comparanda` must not be able to tell the difference except through the authorship metadata that
every value carries.

Schema changes are coordinated: a breaking change is a versioned release of `comparanda` plus a
matching bump here. `rubricator` declares the schema versions it can emit.

## Consequences
Clean, testable boundary — this repo's output can be validated with no UI present, and the UI can
be developed against fixtures with no agent present. The cost is release coordination, which is
the correct cost to pay.

## Amendments

### 2026-08-21 — Confirmed by round-1 research (no change to the decision)

Round-1 research reviewed this ADR and confirms it. Nothing above changes.

The boundary held under pressure, which is the only test worth reporting. The research found seven
schema needs — structured criterion definitions, versioned criteria sets, criterion provenance,
`independence` and the `procedure` record, evidence-reference `stance` / `sourceType` /
`derivedFrom`, the criterion `preference` direction, and an
`insufficient_evidence_to_discriminate` missing reason — and filed every one of them as a **request**
to `comparanda`, not as a change this repository could make. The largest of them, the
evidence-reference locator profile of ADR-0014, is precisely the case a merged repository would have
absorbed silently.

The mechanism is unchanged: validate against the published JSON Schema at the boundary, and declare
the schema versions this repository can emit.

Evidence: [`docs/research/findings-method.md`](../research/findings-method.md), § "Schema requests to
comparanda" and § "Recommended ADR actions".
