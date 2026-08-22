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

### 2026-08-21 — the registered request is re-spelled kebab-case

- **Deciders:** Thor Whalen

The amendment above registers a missing reason named `insufficient_evidence_to_discriminate`. The
request stands; the spelling does not. It is **`insufficient-evidence-to-discriminate`**, per
ADR-0011's second amendment, which rules kebab-case for every reason code and gives the reasons.
Nothing else about the request or the boundary changes.

### 2026-08-22 — the request register grows from seven to sixteen, and four of the nine block

- **Deciders:** Thor Whalen

The Decision above fixes the protocol — every schema need this repository finds is a **request**
across the boundary, never a change it can make — and the register of those requests lives in
`comparanda: docs/cross-repo-coordination.md` § 7. Seven requests were filed under it. The eight
decisions of 2026-08-22 generate nine more, and this note records them here so a reader of the ADR
set can see the register's true size without opening the other repository.

| # | Request | Blocking |
|---|---|---|
| 8 | `Author.principalId`, `Author.actingAs`, `Author.attestation`; `effectiveIndependence`, `distinctPrincipals` | yes — the contributor filename of ADR-0023 |
| 9 | `EvidenceRef.renditionId`; a `Rendition` record with `originalLocator`, `originalSha256`, `normaliserId`; `quoteHash` → `excerptHash` | yes — ADR-0014's amendment |
| 10 | Reconcile the three live citation-verdict spellings onto ADR-0014's enum | yes — before the schema freezes |
| 11 | `Reduction` widened to `string` + `ReductionDeclaration` + `Analysis.reductions` | yes — one line now, a migration through every stored analysis later |
| 12 | Uniqueness on `(alternativeId, criterionId, measure)` | yes — a live bug the moment ADR-0023's merge lands |
| 13 | `Measurement.scale` (optional), `Measurement.anchors`, `Analysis.scales` | yes — ADR-0012's seam |
| 14 | `Criterion.missingCodes` overlay and a scope-aware vocabulary facade | no — analysis scope is sufficient for v1 |
| 15 | `validateAnalysis` takes injected rule families; problems gain `family`, `fix`, `rule_id` | yes — ADR-0024 |
| 16 | `Suggestion.proposed` typed as a partial assertion rather than `unknown` | no — before suggestion mode ships |

Each of the nine was read against the companion repository's source before being written down,
because a request for something that already ships is how a register loses its authority. **Several
were then disposed the same day**, in `comparanda` and by `comparanda` — the contributor fields, the
rendition and excerpt-hash fields, the widened reduction vocabulary with its declaration array, the
scale declaration and anchor set, and the duplicate-cell defect all landed in its source on
2026-08-22. That is the protocol working at speed, not the register being bypassed; the disposition
belongs in the register, and the request stays on the list with its disposition recorded rather than
being deleted from it.

**Request 12 is not a field request but a defect report**, which is why it reads differently from
its neighbours. Two readers of the same document disagreed: the indexed reader kept the **last**
duplicate `(alternativeId, criterionId, measure)` triple, the scanning reader kept the **first**.
Benign while nothing writes documents, and a live bug the instant a merge produces a duplicate
triple — which is exactly what ADR-0023's merge can do.

**Two clarifications the register needs and did not have.**

**Request 11 is time-critical in a way the others are not.** Widening a closed enum costs one line
before v1 freezes and a migration through every stored analysis afterwards, so it takes priority
over requests that are larger but cheaper to defer. It was filed and disposed first, which is the
order this clause exists to produce.

**A request may be answered by the document rather than by the schema, and that is a disposition.**
Request 7 — a missingness reason for insufficient evidence to discriminate — needs no schema change
at all once `comparanda`'s missingness declarations are read the way they were built: it is a row in
`Analysis.missingCodes` with `broader: 'indeterminate'`. Recording *that* as the disposition is the
protocol working, not being bypassed. The boundary rule this ADR states is unchanged: we still may
not write it into `comparanda`; we write it into **our own analysis document**, which is ours.

All seven original requests still carry an empty disposition in the register, so the intake gate is
formally open even where the shipped schema visibly satisfies the request. Recording those
dispositions is a reading of existing code, not a feature, and it should not wait on the nine new
ones.

Refs #27, #28, #29, #30, #31, #32, #33.
