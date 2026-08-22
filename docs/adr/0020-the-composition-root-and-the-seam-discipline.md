# ADR-0020: One composition root, and what makes a seam a seam

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
The owner's process directive for v1 is explicit and is a constraint on architecture, not on
scheduling:

> "Think hard about the design so that the iterations mostly happen by ADDING code, hooking them up
> to existing seams, rather than redoing anything. Ideally the whole architecture is there from v1,
> just with simple components wired in the seams, and then we work on getting better components."

Two ADRs already contain the sentence that makes this fail if it is left as prose. ADR-0012's
2026-08-22 amendment: "A palette, a merge tree, a completeness report or an analysis that hardcodes
five levels is a *seam that does not seam*." ADR-0018's: "A strategy interface whose default leaks
through it is not a seam." Both say the same thing twice, about different axes, which is the signal
that the rule belongs in one place.

There is a second force. This repository has shipped guards that could not fail, and ADR-0012's
amendment counted them and predicted the next. Two are named and repaired by ADR-0010's 2026-08-22
amendment — a schema-loading check that greps one filename, and a nondeterminism denylist with no
clock in it — and a third is worse than a weak guard: the citation module's doctests pin a verdict
enum ADR-0014 retired, so CI actively enforces the wrong contract. A rule with a passing test that
cannot fail is worse than no test, because it converts inattention into evidence.

## Decision

**Every seam is a keyword argument of one function: `rubricator/compose.py::build_runtime`.** It
takes the bytes store, the clock, the identity provider, the scale presets and default, the
reducers, the stability strategies and default, the normaliser table and default id, the rule set,
the projectors, the projection writer and the model access — each with a real default — and returns
a `Runtime`. `bound(TOOL_REFS, runtime)` partially applies it so that tool functions stay plain,
keyword-only and context-free in their own signatures.

**No tool constructs its own dependency.** That single rule is what makes every seam in this
repository testable with a `dict` and a frozen clock, and it is why the vertical slice needs no
network, no key and no MCP client.

**No module self-registers.** Every table — presets, reducers, strategies, normalisers, rules,
projectors — is a frozen module-level mapping *passed in* at the root. `comparanda`'s stack ADR
documents a bundler demonstrably deleting a module whose only purpose was its module-scope
registration call, with no build error; the same hazard exists in Python through import ordering and
optional extras, with the failure arriving as a missing key rather than a missing import.

**Prefer data to interfaces, and a row to a class.** Where a variation can be expressed as a row in
a table travelling in the document, it must be — because a row crosses the language boundary through
JSON Schema and reaches a reader running an older build, and an interface does not. An interface is
introduced only when behaviour genuinely varies and cannot be derived from declared data. ADR-0021
applies this to the three extension vocabularies; the concrete consequence is that v1 introduces
**no `MeasurementScale` protocol** and **no multi-port store abstraction**, because the two seams
everyone reaches for first are the two that are already data.

**A default may not leak through the interface meant to contain it, and this is tested by failure.**
Every seam ships with at least one test that **fails when the default is replaced**, not merely one
that passes with the default in place. A guard is not believed until it has been demonstrated
failing against a deliberate violation; demonstrating it is part of the change that introduces it.

## Consequences
Swapping a backend, a clock, a scale, a reducer or a model provider is an argument at one call site,
and the three add-not-redo cases the design was checked against each touch at most two files. The
cost is real and is paid in v1: an extra indirection at every construction site, a composition root
that must be kept honest, and a discipline that is invisible until someone violates it. For a solo
user with one scale and six core missingness codes, the whole apparatus buys nothing today.

The composition root is itself a place a mistake can hide. A function with a dozen keyword arguments
is easy to call wrongly and hard to review, and nothing here prevents a second construction site
appearing in a hurry. The mitigation is a test that introspects `build_runtime` against the seam
catalogue, which fails when a seam is added without a keyword argument — not when a second
construction site appears, which stays a review matter.

The failure mode this cannot prevent is a seam that is never exercised. A table with one row is
indistinguishable from a constant. That is what the falsification fixture is for, and it is why the
vertical slice includes loading a document declaring a scale and a missingness code that v1 does not
implement.

## Alternatives considered
- *A plugin registry with entry-point discovery.* The right shape where third parties ship
  strategies out of tree. Here it inverts control for no benefit and reintroduces exactly the
  self-registration hazard above.
- *A settings module or a config file.* `tomllib` is 3.11+ and CI runs a bare 3.10 leg; more
  importantly, a config file makes the wiring implicit again. The magic numbers become named
  keyword defaults with real values, which is the same win without a loader.
- *Leaving the rule as prose in each ADR.* It was prose in two ADRs and had already produced guards
  that could not fail.
