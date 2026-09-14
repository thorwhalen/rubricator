# Changelog

Nothing is released yet, so this file is not a release log. It exists for one narrower purpose:
**to record the boundaries across which a number stops meaning the same thing.** A renamed metric or
a renamed stored value is not a cosmetic change — it is a point after which two figures that carry
the same label are measuring different things, and the failure mode is silent.

---

## 2026-09-14 — Missingness reason codes, and the metric named after one

Absorbs the companion repository's 2026-08-21 amendment to its ADR-0009
([thorwhalen/comparanda#15](https://github.com/thorwhalen/comparanda/issues/15)), settled here in
[#109](https://github.com/thorwhalen/rubricator/issues/109).

### The renames

| Retired | Current | |
|---|---|---|
| `pending` | `deferred` | same meaning, clearer word |
| `unknown` | `indeterminate` | **narrowed** — see below |
| — | `not-evidenced` | **new** |

`unknown` → `indeterminate` is the one that is not a rename. The old `unknown` covered two findings
at once: *the sources are silent on this cell*, and *the sources speak and do not agree*. Those are
split now. `not-evidenced` is the first; `indeterminate` is the second and only the second.

**So an old `unknown` and a new `indeterminate` are not the same population.** Any count, rate or
comparison that spans 2026-08-21 is comparing a superset with a subset. `not-evidenced` has no
predecessor at all.

Both new codes are `terminal` and `informative`: someone looked, and the blank says something about
the subject rather than about our process. Both therefore count toward `silenceRate`, which
`withheld` — known but not shown — does not.

### The metric rename

`unknown_preference_rate` → **`blank_inflation_rate`**, settled in ADR-0008's 2026-08-21 amendment,
which names the old spelling and supersedes it. `docs/research/` still spells it the old way,
deliberately.

The new name is not a translation of the old one. The old name pointed at a reason code; the new one
points at the behaviour — *blanks emitted where evidence was in fact available* — and its companion
`qualified_blank_rate` counts blanks that carry a reason and a record of what was searched. ADR-0008
also rules that `not-evidenced` and `indeterminate` are **counted separately and never pooled**, so
neither metric can be reconstructed from the other side of the boundary by addition.

Naming a metric after a reason code makes the next code rename a metric rename. That is the mistake
this entry records, and the behaviour-first naming is the fix that stops it recurring.

### Is any existing number affected? No — and this was checked, not assumed

**No evaluation run has ever happened in this repository.** The ADR-0008 suite is a decision, not
yet an implementation: there is no evaluation module, no harness, no fixture corpus with recorded
answers, and no stored results — not in the working tree and not anywhere in the git history. The
only artifacts carrying these metric names are the ADR that defines them and the research that
recommended them.

So **no figure in existence spans this boundary**, and there is nothing to re-baseline. The whole
cost of the rename was paid in documents.

That is a fact with a shelf life. The first evaluation run is the first number that could be
compared wrongly, and from that point:

- **every recorded evaluation result carries the vocabulary manifest version it was computed
  against** (`rubricator/schema/comparanda/vocabularies.v1.json`, `schemaVersion`), and
- **no blank-related figure is compared across a manifest version bump** without saying so.

`VOCABULARY_VERSION` in `rubricator/schema/vocabulary.py` is bumped deliberately and never inferred,
for exactly this reason: a silent upgrade is a silent change to what `silenceRate` counts.

### What changed in the repository

- `rubricator/data/prompts/score-cell.md` — the first shipped prompt. It teaches `not-evidenced`
  apart from `indeterminate`, which is the half of #109 that was never a rename: a vocabulary the
  agent cannot apply is decoration.
- `rubricator/prompts.py`, `rubricator/tools/prompts.py` — the prompt bundle, served from the one
  ADR-0003 registry so both runtimes hand out the same file.
- `tests/test_prompts.py` — the tripwire. A prompt's `missing-codes` are checked against the live
  vocabulary manifest and against its own prose, and the retired spellings are banned outright, so
  the next upstream rename fails the suite instead of shipping.

### What was deliberately not changed

`docs/research/` keeps the pre-amendment reason-code spellings. That is ADR-0011's own settled rule —
*"`docs/research/` keeps the original spelling because it is the evidence trail, not the
specification"*, written about reason codes and applied here to the metric name on the same
reasoning — and rewriting a dated finding to match a later decision falsifies the record of what was
actually known when. `docs/research/findings-method.md` now opens with a note saying so, so
a reader who lands there first is not misled.

The accepted ADRs that still contain `unknown` in their decision bodies — ADR-0006's *Decision*,
ADR-0008's refusal-to-guess bullet, ADR-0012's enforcement rule 1 — are likewise left intact.
ADR-0001 forbids editing an accepted decision, and ADR-0012's 2026-08-22 amendment already
discharges every such conditional in this repository by name. Each of those ADRs carries an
amendment a reader reaches before acting on the body.

Not every `unknown` in the tree is a missingness code, and the ones that are not were never in
scope: ADR-0022 uses it for an `independence` rung, ADR-0024 and ADR-0002 for how a *suggested*
assertion is typed in the shipped schema, and `rubricator/tools/traversal.py` for the English word
in an error message about traversal order. A search-and-replace would have rewritten all four,
which is why the sweep was done per site.
