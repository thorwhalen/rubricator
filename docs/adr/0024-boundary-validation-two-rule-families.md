# ADR-0024: Two rule families — honesty rejects, completeness informs, and honesty cannot be switched off

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
ADR-0002 fixes *where* validation happens — at the boundary, against `comparanda`'s published JSON
Schema. ADR-0006 fixes *what* honesty means. Neither says how strict to be, and the two obvious
answers are both wrong. Strict everywhere rejects a half-finished analysis, when "not yet assessed"
is a first-class representable state the whole resume story rests on (ADR-0017). Lenient everywhere
accepts a score with no rationale, which is the product's only real claim.

The owner settled it:

> "Strict on honesty, forgiving on completeness. Reject malformed documents, and reject a score that
> lacks what makes it checkable — no rationale, no named contributor, a citation resolving to
> nothing, a confidence claim with no evidence. **Accept** merely-unfinished documents. Every
> rejection names the exact path and the fix."

JSON Schema can express none of the honesty rules. Every one is cross-field: confidence against
evidence, source type against derivation, score against missingness, an independence claim against
the author's principal.

## Decision

**Two rule *families*, not two severities of one list.** `honesty` rejects; `completeness` informs;
`schema` is the shape check underneath both. **The family determines the severity — a rule does not
choose it.** That is what stops a rule being quietly demoted in a later edit.

**A problem carries `path`, `message`, `family`, `severity`, `fix` and `rule_id`.** `fix` is
**required**: "names the exact path and the fix" is not satisfied by a message that names only the
path, and making the field required is the only way to make that true of a rule nobody has written
yet. `rule_id` is stable, so a suppression is auditable. `comparanda` landed the three fields on the same
day this was written — its problem record now carries `path`, `message`, `severity`, `family`,
`ruleId` and `fix` — with two differences to reconcile rather than request: it spells the family
`shape` where this ADR spells it `schema`, and its `fix` is optional where this ADR requires it.
Request 15 of ADR-0002's register therefore narrows from "add three fields and an injection point"
to "settle the spelling, make `fix` required, and add the injection point".

**`strict=False` drops the completeness family only. Honesty rules can never be suppressed** — not
by a flag, not by a ruleset, not by configuration, not by a deployment. That is what makes a
strictness switch meaningful without a boolean maze, and it forecloses a deployment configuring its
way out of the honesty bar, which is the product.

**Rules are a passed-in sequence, because there are two call sites with different compositions on
day one.** Write time runs honesty only, through the store's unbypassable hook (ADR-0023). Explicit
validation runs both. Four named rulesets: `draft` (honesty only — the scoring loop, where half the
matrix is legitimately unassessed), `default`, `strict-publication` (for the moment an analysis
leaves the team), and `conformance` (for the evaluation harness, where a violation is a measured
outcome rather than a refusal).

**Every rule reads one context object** carrying the resolved vocabularies, the author index, the
renditions, the clock — and **the degradations this build accumulated**. That last one is what lets
an honesty rule reject a high-confidence cell on a scale we could not interpret (ADR-0021), which is
otherwise unreachable from the document alone.

**No rule re-derives an interpreter, and no rule switches on a literal code.** A rule that hardcodes
a vocabulary member is a second source of truth for the one vocabulary the design insists must have
exactly one.

**An undated citation verdict is an honesty rejection.** `comparanda`'s citation-check validator
enforces that `checkedAt` and `checkerVersion` are present for every status except `unchecked`, and
— as of the same day this was written — files the failure as **honesty, at error severity**, which
is what this ADR requires. It filed it as a warning until then, which meant a document whose every
supporting reference was the agent's own summary validated cleanly: the exact failure ADR-0006
names, passing the boundary written to catch it. A verdict nobody can date is not a verdict.

## Consequences
`analysis_validate(strict=...)` becomes meaningful and small. A half-finished analysis returns
`ok=True` with warnings — twenty-three of twenty-four cells unassessed is a *report*, not a failure —
while a single uncited score is a rejection naming the cell and what to add. The store can never
hold a dishonest document, because the hook runs before the bytes are written.

The cost is that every honesty rule must be written twice, once per language, and kept in agreement
by fixtures rather than by a compiler. That is unavoidable: the rules are exactly the part of the
contract JSON Schema cannot carry, which is why ADR-0002's boundary needs a companion rather than a
wider schema.

Suggestion mode is currently out of reach: a proposed assertion is typed as `unknown` in the shipped
schema, so no honesty rule can inspect one. Filed as register request 16, before suggestions ship.

## Alternatives considered
- *One list with severities.* A severity is a property of the individual rule and drifts downward
  under pressure, one plausible edit at a time. A family is a property of the *kind* of claim.
- *Schema refinements expressing the honesty rules.* Not expressible in JSON Schema, and the
  language-neutral artifact is exactly what ADR-0002 makes the contract.
- *A single `strict` boolean over one list.* Either it suppresses honesty rules — the thing that
  must never be configurable — or it means nothing.
- *Validating only at explicit validation time.* Leaves a write path that stores documents the
  product's claim says cannot exist.
