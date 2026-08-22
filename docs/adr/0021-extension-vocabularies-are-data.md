# ADR-0021: Extension vocabularies are data — one resolver, `broader` degradation, reported

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
Three decisions of 2026-08-22 each ask for the same thing on a different axis. ADR-0012's amendment
makes the measurement scale a per-criterion declaration with the anchored 1–5 ordinal as default and
explicitly defers the *shape* of that declaration — "the protocol in Python, the type in TypeScript,
where it is wired" — to the v1 seam-architecture work. **This ADR is where that deferral lands.**
The missingness vocabulary must be extensible per criterion and context. Aggregation across
contributors must be pluggable on a default or a custom parametrisation. A fourth axis — the
normaliser version of ADR-0014 — has the same shape and an opposite discipline.

`comparanda` has already built one of these correctly, and it is the template rather than the
problem: a closed core enum, an open `string` at the point of use, a declaration in the document
carrying `broader` plus overrides, exactly one resolver, and every consumer keying on flags rather
than on a literal code.

What the version shipped when this was decided lacked is the part that makes it safe across builds.
`resolveMissingCode` returned `undefined` for a code it did not know — correctly, since defaulting
an unknown absence to "outstanding work" or to "correctly nothing" are both wrong and both invisible
— and then **nothing recorded that it happened**. A reader whose build predates a declaration
renders a document it has silently misunderstood. That gap is what this ADR closes, and `comparanda`
landed the substrate for it — `Resolution`, `Degradation`, one generic resolver — on the same day.

## Decision

**Every extensible axis takes one shape.** A closed **core enum**; an open `string` at the point of
use; a **declaration** in the document — `{ id, broader: <core member>, means, params }` — and
**one resolver** that every consumer must call. A declaration is a row. A row travels through JSON
Schema, through git, and through time to a reader running an older build; an interface does not.

**No `MeasurementScale` protocol is introduced**, which is the concrete answer ADR-0012's amendment
was waiting for. Everything that varies about a Stevens-family scale is already a field of
`comparanda`'s shipped `Measurement`: `level`, `preference`, `range`, `thresholds`, `acceptability`,
`levels`. A scale is a row that expands into one of those; a rubricator-side **preset** is an
authoring shorthand for writing that row, and it has no methods.

**Reading never raises on an unknown id.** It degrades through `broader` to the core member the
declaration names, and it appends a `Degradation` record naming the axis, the id, the JSON path
where it was used, and the declaration's own `means` string as the reason.

**Authoring raises.** `expand_scale('typo')` raises, naming every known preset id. At authoring time
you are *choosing*, and a silent default is the failure. This asymmetry is the entire repair for the
failure a plain registry has — that a document written under a locally-registered name is
unreadable elsewhere.

**Degradation is reported, never stored.** A `Degradation` is a fact about **this build**, not about
the analysis. It is accumulated on read and returned alongside the document. Storing it would make
one reader's limitation look like a property of the data, and the next reader would inherit a
warning that is false for them.

**An absent declaration is not the same as a default.** Where a document carries no `scale` at all,
it means "Stevens, as declared by `level` / `preference` / `range`" — which is what it meant before
the field existed. Stamping an absent field with the ordinal default would silently retype a
criterion that validates cleanly today, and would hand back an interpreter that rejects its values
and forbids its legal reductions. The default belongs to the authoring path, never to the read path.

**Strictness is asymmetric, and the asymmetry is the rule that stops this mechanism becoming a hole
through which unverifiable claims travel:**

| Situation | Family | Why |
|---|---|---|
| Unknown missingness code | completeness `info` | Degrade, count as outstanding. Over-report work, never under-report it. |
| Unknown reduction name | completeness `info` | Degrade; the reduction is disclosed either way. |
| Unknown scale on a cell claiming **high confidence** | **honesty error** | We cannot check admissibility, and the document asserts checkability. |
| Unknown normaliser on a reference carrying a check | **honesty error** | The verdict is not reproducible, so it is not a verdict. |

**Three vocabularies are core and must not drift between the two languages**: the missingness codes,
the reduction names, and the scale family. There is no codegen in this ecosystem in either
direction, so `comparanda` emits a `vocabularies.v1.json` artifact beside its JSON Schema, this
repository **vendors** it, and one command refreshes the schema and the vocabulary file **together**
so they can never be half-updated. The parity test runs in **this** repository — the dependent —
because ADR-0002 forbids `comparanda` needing to know we exist.

**The normaliser table is the one axis with the opposite discipline: append-only, never resolved
through `broader`.** ADR-0014's 2026-08-22 amendment owns it. A caller *records* which normaliser it
used; it does not choose an interpretation at read time. Degrading an unknown normaliser would mean
claiming a quote was checked against text we cannot reproduce.

**What this asks of `comparanda`, and what it does not.** Requests 11, 13 and 14 of ADR-0002's
register carry the schema half — widening `Reduction`, adding `Measurement.scale` / `.anchors` /
`Analysis.scales`, and the criterion-scoped missingness overlay. Request 11 is the time-critical one:
widening a closed enum costs one line before v1 freezes and a migration through every stored analysis
afterwards, which is why it was disposed first. None of it is ours to write, per ADR-0002 — and the
declaration shape this ADR fixes is what those requests are requests *for*.

## Consequences
Adding a scale, a missingness code or a reduction becomes a row plus, at most, one function — and in
the two purest cases, a JSON edit with no code change in either repository. A request that would
have been a schema-major change becomes a declaration. The cost is paid in v1 and the benefit
arrives later: every read goes through a resolver, every consumer handles the unknown case, the
document grows three arrays, and for a solo user with one scale it is pure overhead.

**Two residual risks, unrepaired and recorded rather than hidden.** `broader` degradation can be
honestly wrong: a future latent-strength scale degrading to ordinal renders a computed quantity as
though a rater chose it, and the high-confidence case is a rejection but the medium-confidence case
degrades quietly-but-loudly and somebody will not read the banner. And `params` is typed as an open
object, so scale and reduction parameters are validated only by an interpreter that already knows
them — which is exactly the point at which the JSON-Schema contract ADR-0002 rests on stops being
load-bearing. Both are unavoidable if declarations are open.

The parity test catches **key** drift, not **semantic** drift: both repositories can register a
`lower-median` and disagree about ties, and nothing here notices. The real defence is golden
fixtures run through both implementations with byte-compared output, and that is deliberately not in
v1 — so the green checkmark is weaker protection than it looks.

## Alternatives considered
- *A `MeasurementScale` protocol dispatching the five scale-dependent functions.* Every one of them
  is already a pure function of `level` and `preference`, which the document already carries as
  required fields. The protocol would rewrite working code to add indirection over data, and would
  force a lockstep two-language release every time someone adds a scale — the exact cost the
  add-not-redo directive exists to avoid.
- *A module-level mutable registry with `register_scale(...)`.* Forbidden by ADR-0020, and it
  produces documents readable only where the registration ran.
- *Returning `undefined` and saying nothing, as shipped.* Correct not to default; incomplete not to
  report. The whole of this ADR's addition to `comparanda`'s design is the report.
- *Storing the degradation in the document.* Makes one reader's limitation permanent and travelling.
- *Defaulting an absent `scale` field to the ordinal preset.* Silently retypes criteria that are
  valid today. Rejected above, and it is the single most tempting shortcut here.
