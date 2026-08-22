# ADR-0025: The `rubricator` application — Preact, one data port, text-only encoding

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
The second v1 surface is a deployed web application, both to contribute opinions and to read the
analysis. It is named after the **dependent**, not the dependency: `rubricator` depends on
`comparanda`, so the application takes rubricator's name.

`comparanda` owns the view and has decided how to build one, in an ADR whose scope is `comparanda`:
Preact over React on measured bundle arithmetic, `zod/mini`, and registries populated explicitly by
the composition root rather than by self-registering modules. Its view module is currently an
eight-line placeholder and its matrix is a later-phase epic behind an accessibility merge gate, so
nothing on this repository's critical path may depend on it.

The owner is a deep Python and architecture expert and a complete frontend novice, so every choice
here is stated in terms that can be evaluated on architecture grounds rather than on familiarity.

## Decision

**Adopt `comparanda`'s view-stack ADR by reference for the framework, the schema authoring style and
the no-self-registration rule.** Preact, because the application will mount `comparanda`'s
components and running two virtual DOMs in one page to avoid it is strictly worse. Explicit
registration, because a bundler was demonstrated deleting a module whose only purpose was its
module-scope registration call, from the bundle that needed it, with no error.

**Data flow is one-directional and there is exactly one loop.** Files own everything durable. The
backend reads them through **the same store object the MCP tools use** — not a parallel
implementation — and serves JSON. One adapter turns that endpoint into a `DataProvider<Analysis>`.
The application calls `getOne(id)`, receives an analysis, and hands it to components as plain props.
Editing a cell mutates nothing: it calls a callback, which posts, which writes a contributor file,
which invalidates the read. **There is no client-side model that can drift out of agreement with the
server, because there is no client-side model** — only a cached copy of one response.

**The browser owns exactly two things, both disposable:** the in-flight copy of the analysis, and a
small bag of view preferences in browser storage. Losing either loses nothing. The moment the
browser owns something that is not in a file, "files are the single source of truth" stops being
true.

**One port, not five.** `DataProvider<Analysis>` plus an identity function and a clock.
`comparanda`'s persistence ADR fixes a five-port set with a capability report as its single source
of truth; four of the five are view-state conveniences, and splitting a port set before any of them
has two implementations freezes a guess. **This narrowing requires a dated amendment to that ADR in
`comparanda`** — a silent divergence is exactly the failure the supersede-rather-than-edit rule
prevents, and it is not ours to write. The capability report stays the single source of truth for
what the UI enables, and the application never invents a parallel flag.

**`getCapabilities()` is the honest part, and it is the reason this port is worth more than a bare
`fetch`.** The adapter *declares* what it can really do; the UI reads the declaration rather than
guessing. v1 declares everything client-side — which is true and correct for a handful of
contributors — and moving sorting or filtering to the server later is a change to a declaration,
with **zero component changes**. This is the same bet `dol` makes in Python, plus the one thing
`dol` does not have.

**Components depend on one plain data shape** — an analysis, a measure name, a vocabulary, an
encoding and two callbacks — defined in `comparanda` so that both consume the same type. They import
no provider, no HTTP client and no store. Consequently: swapping the backend is one function in one
file; and when `comparanda`'s matrix ships, it consumes the **same** props and rubricator's
placeholder table is **deleted rather than refactored**.

**v1's only encoding is `text-only`, and it is not a shortcut.** `comparanda`'s planned colour
encoding hardcodes nine colours for five score levels by three confidence levels — exactly what a
pluggable scale breaks, so a money column would have no correct ramp. Text-only renders the value as
text and every absence as the vocabulary's own `means` string, resolved through ADR-0021's resolver
and never from a literal. It has no arity problem, it passes the accessibility gate by construction
rather than by a contrast test, and it lets ADR-0012's seam land without a palette redesign on the
critical path.

**The view renders a citation check's standing, and a test fails if it does not.** ADR-0014's
2026-08-22 amendment requires a defined caveat on an aged check. `comparanda` already ships the pure
function that computes it, taking `now` as a parameter, so the view owns no clock and no policy —
it injects the function and renders what it returns.

**Identity comes from the platform, not from the application.** The session issued by the deployment
platform's auth layer is the principal; the application may attach a persona to it (ADR-0022) and
may never invent the principal.

**Analysis files are declared as platform data from the first deploy**, outside the application
directory. The deploy tooling hard-fails a deploy that leaves data inside its delete blast radius,
and retrofitting that declaration means discovering it by losing files.

**A schema change is a compile error, not a production surprise.** The Zod source in `comparanda` is
the single origin; TypeScript types are inferred from it; the same source is emitted to JSON Schema
in a build step and validated in Python at the boundary. The application hand-writes no schema
shapes at all.

## Consequences
The application is small enough to be honest about: one port, one throwaway table, no state the
files do not own. It ships before `comparanda`'s matrix and does not block on it, and it deletes
code rather than accumulating it when that matrix arrives.

**The known limitation is that `update` is last-write-wins with no version field.** That is safe
**only** because one file per contributor keeps writes disjoint (ADR-0023), which is why the
multi-writer capability is gated on the per-contributor one. A single shared-document write path
would silently lose contributions.

`comparanda` stays headless and never names a data provider; the boundary check that forbids network
access outside its store module keeps holding, because the application does the fetching and hands
it an already-loaded analysis.

**This is a second surface competing for the same attention**, which ADR-0007's amendment accepts
explicitly. The mitigation is the thinness above: stopping after it costs a component, not an
architecture.

## Alternatives considered
- *React, for ecosystem familiarity.* Two virtual DOMs in one page, to avoid the framework the
  components we are mounting are written in.
- *`comparanda`'s five ports as specified.* Four have one implementation and no second axis.
  Deferred, with an amendment recording the narrowing rather than a divergence.
- *Just call `fetch`.* Works until the second backend, at which point every component knows about
  HTTP. The port is what makes the local, hosted and offline cases one code path — and it is what
  makes the honest capability declaration possible at all.
- *Waiting for `comparanda`'s matrix.* It sits behind an accessibility merge gate in a later phase.
  Waiting makes this repository's v1 depend on another repository's phase 3.
- *Colour encoding in v1.* Its palette arity contradicts the scale seam landing the same week.
