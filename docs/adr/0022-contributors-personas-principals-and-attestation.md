# ADR-0022: A persona is an Author; a principal is who is behind it; an attestation is how well we know

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
The owner's directive:

> "The system is not only for agents but humans. Similar rules should apply when it makes sense.
> Each human, like each agent, should be able to contribute their opinion/rationale, and the system
> should be able to manage these, make aggregates, etc."

and, on the connector surface: a contribution is **signed by the user**, with the option of signing
under a **custom name or persona**, because one person may deliberately analyse from several
perspectives, or tell Claude to take a specific role.

Most of the first half is already true. `comparanda`'s `Author` has `kind: human | agent | imported
| derived` and an `agent` sub-object carrying model, prompt version and run id; `Assertion.authorId`
is validated against the analysis's author list. Human and agent contributors are already symmetric
and first-class.

What was unrepresentable when this was decided is the second half, and its absence was a
**correctness** problem rather than a modelling gap. ADR-0018's 2026-08-22 amendment already rules that "a persona is not an
independence rung", that a persona is "attribution and framing, not evidence of independence", and
that "a statistic must never read a persona as a rater". With no link from a persona back to the
person behind it, nothing can enforce that rule — one analyst's three perspectives count as three
raters, which is the same error as counting five draws of one model as five raters, arriving through
a new door. This ADR supplies the mechanism for a rule that already binds; ADR-0018's amendment is
its parent and is not re-decided here.

This is also the largest thing blocking elsewhere: the per-contributor filename of ADR-0023 has no
key without it. `comparanda` landed the three fields and `effectiveIndependence` on the same day this
was decided, as request 8's disposition.

## Decision

**A persona *is* an `Author`.** It has its own `Author.id`, so `Assertion.authorId`, author
validation, the annotations module and every shipped code path keep working with no change at all.
Three optional fields are added — request 8 of ADR-0002's register, and not ours to write:

- **`principalId`** — an opaque, pseudonymous handle for the real account behind the persona. Two
  personas of one person share it. Never an email, never a login name.
- **`actingAs`** — the perspective the persona is deliberately arguing from ("the sceptical CFO").
- **`attestation`** — `{ method: unverified | host-session | oauth | signature, issuer?, at? }`,
  recording **how well we know the identity**, so an offline reader knows what the claim is worth.

**`author_id` is deterministic from (principal, persona)** — a hash, prefixed and truncated. This is
load-bearing rather than tidy: it is the contributor's filename under ADR-0023, and a
nondeterministic id would fork a contributor's file the moment they resume in a new session.

**`principal_id` is salted per analysis**, so two analyses sitting in one repository cannot be
trivially joined by an outsider holding only one of them. The salt lives in the analysis frame.

**`effectiveIndependence` is a sibling of `weakestIndependence`, not a replacement.** It collapses
assertions whose authors share a `principalId`, then caps the resulting set at `resampled`. The
shipped function keeps its signature and its job.

**An attestation is never an independence rung either.** `signature` says we know who wrote it, not
that they reasoned independently of anybody. The two ladders are orthogonal and a UI that fuses them
is telling a reader something neither one claims.

**`unverified` is the honest default and is not a bug.** In the connector the caller supplies their
own identity; nothing can check it. Recording that plainly is the whole point of the attestation
field, and the honesty rule `persona-independence` catches the *representable* lie — an assertion
claiming `independent` whose author shares a principal with another contributor on the same cell.

**One vote per principal is the reduction a team will actually want**, and it is expressible only
because this split is in the document. It is not the v1 default; `single` is.

## Consequences
The independence ladder's fourth rung becomes routine rather than theoretical, and it becomes
computable. Aggregation gains a per-principal weighting it could not otherwise express. The
per-contributor file layout gets a stable key. And a contribution acquires a byline a reader can
evaluate: who, acting as what, known how well.

**`principalId` is pseudonymous, not anonymous, and it is added deliberately.** Per-analysis salting
stops an outsider correlating across analyses. It does **not** hide anything from a colleague:
inside a team repository the account set is small and known, so the persona→person mapping is
guessable, and describing salting as privacy would be false. A team needing genuinely unlinkable
personas must accept that their independence is `unknown`, which the ladder already handles
honestly.

**The ladder is a disclosure mechanism and never a control.** The system is exactly as honest as the
contributor. A careless contributor leaves `unverified` in place while claiming `independent`, and
no rule can catch a fabricated principal.

**And every cross-field rule here is invisible to JSON Schema.** "An assertion claiming
`independent` whose author shares a `principalId` with another contributor on the same cell" is not
expressible in Draft 2020-12 at all. The three new fields round-trip exactly; the rules that give
them meaning do not, which is why they are plain predicates mirrored in both languages under
ADR-0024 rather than schema refinements.

## Alternatives considered
- *A separate `Contributor` entity with authors pointing at it.* A second identity concept in a
  schema that already has one, and every shipped consumer of `Author` would need teaching.
- *Reusing the free-text `role` field.* It is display text; it ties nothing back to a person, so the
  independence computation stays impossible and the field silently acquires a second meaning.
- *Nesting contributor files by principal, so "everything X wrote" is a prefix scan.* Attractive, and
  it puts the persona→person link **in the path**, visible in a file listing without opening a file.
  The link is a real privacy cost; it belongs inside the document where only the independence
  computation reads it.
- *Verifying identity properly in v1.* The connector has no mechanism to; `unverified` recorded
  honestly is strictly better than an unrecorded assumption.
