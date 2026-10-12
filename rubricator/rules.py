"""The honesty rules this package mirrors from the companion repository.

JSON Schema carries the *shape* of an analysis. It cannot carry the rules that
make one honest, because every one of them is cross-field: an independence claim
against the other assertions in its cell, a missingness code against the codes
the document defines. `comparanda` enforces those in its own validator, and
ADR-0031 there (clause 6) asks every producer to mirror them -- a document that
passes the vendored schema here and is refused by the renderer is the failure
that clause exists to prevent.

The record follows ADR-0024: a problem carries ``path``, ``message``,
``family``, ``severity``, ``fix`` and ``rule_id``, and **the family fixes the
severity**. Only the honesty family lives here, and honesty can never be
suppressed: there is no flag on :func:`honesty_problems` that drops a rule, only
a ``rules`` sequence, so a caller adding a rule is easy and a caller removing
one has to write that down. The completeness family and ``analysis_validate``
belong to #61, which composes over this module rather than beside it.

Each rule is a plain function ``(document) -> Iterable[Problem]`` over a
**merged** analysis. A rule that needed a model, a clock or the network would
break the connector runtime (ADR-0003), so none does.

>>> doc = {'cells': [{'alternativeId': 'a', 'criterionId': 'c', 'measure': 'score',
...         'assertions': [{'id': 's1', 'authorId': 'ana', 'value': 4},
...                        {'id': 's2', 'authorId': 'ben', 'value': 2,
...                         'independence': 'independent'}]}]}
>>> [p.rule_id for p in honesty_problems(doc)]
['independence-recorded']
>>> honesty_problems(doc)[0].path
'cells[a/c/score].assertions[s1].independence'
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

__all__ = [
    "Problem",
    "Rule",
    "HONESTY_RULES",
    "honesty_problems",
    "independence_recorded",
    "unique_ids",
    "missing_rule_code_defined",
    "supersession_resolves",
    "live_assertions",
    "SCHEMA_RULES",
    "schema_problems",
    "structural_refines_not_applicable",
    "no_redeclaring_core",
    "unique_declarations",
]

#: ``honesty``: the document lies. ``schema``: it is malformed -- it declares
#: something it may not, or twice -- which `comparanda` also refuses, as an error.
Family = Literal["honesty", "schema"]


@dataclass(frozen=True)
class Problem:
    """One way a document fails a rule, with the path and the fix (ADR-0024)."""

    path: str
    message: str
    fix: str
    rule_id: str
    family: Family = "honesty"

    @property
    def severity(self) -> str:
        """Derived from the family, never chosen by a rule: both families here reject."""
        return "error"

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.path}: {self.message} Fix: {self.fix} [{self.rule_id}]"


Rule = Callable[[Mapping[str, Any]], Iterable[Problem]]


def _cell_path(cell: Mapping[str, Any]) -> str:
    return f"cells[{cell['alternativeId']}/{cell['criterionId']}/{cell.get('measure', 'score')}]"


def live_assertions(cell: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The assertions of a cell that nothing has superseded.

    Absences count: a qualified blank beside a score is two claims about one cell,
    and which of them a reader sees depends on whether they were independent.
    """
    return [a for a in cell.get("assertions", []) if not a.get("supersededBy")]


def independence_recorded(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A cell holding two or more live assertions records ``independence`` on each.

    Mirrors `comparanda`'s ``independence-recorded`` (its ADR-0031, ADR-0022).
    Without the rung, five draws of one model and five people who argued in a
    room are the same bytes, and the reader is shown "5 raters" for both. A
    single assertion is exempt: there is nothing to be independent *of*.
    """
    for cell in document.get("cells", []):
        live = live_assertions(cell)
        if len(live) < 2:
            continue
        for assertion in live:
            if assertion.get("independence"):
                continue
            yield Problem(
                path=f"{_cell_path(cell)}.assertions[{assertion['id']}].independence",
                message=(
                    f"this cell holds {len(live)} live assertions and assertion "
                    f'"{assertion["id"]}" (author "{assertion.get("authorId")}") records no '
                    "independence, so a reader cannot tell raters from repeated draws."
                ),
                fix=(
                    'the author of that assertion records its rung: "shared-context" if they '
                    'saw the others\' scores or share a session, "resampled" for another draw '
                    'of the same model, "perturbed" (with a perturbation record) for a '
                    'deliberately varied draw, "independent" for a separate assessor. When '
                    'unsure, "shared-context" is the honest choice.'
                ),
                rule_id="independence-recorded",
            )


def unique_ids(document: Mapping[str, Any]) -> Iterable[Problem]:
    """No two assertions in one cell share an id (`comparanda`'s ``unique-ids``).

    A duplicate makes every ``supersededBy`` naming that id ambiguous.
    """
    for cell in document.get("cells", []):
        seen: set[str] = set()
        for assertion in cell.get("assertions", []):
            if assertion["id"] in seen:
                yield Problem(
                    path=f"{_cell_path(cell)}.assertions[{assertion['id']}]",
                    message=f'duplicate assertion id "{assertion["id"]}" in this cell.',
                    fix="give one of them a different id.",
                    rule_id="unique-ids",
                )
            seen.add(assertion["id"])


def supersession_resolves(document: Mapping[str, Any]) -> Iterable[Problem]:
    """``supersededBy`` names another assertion in the same cell, without a cycle.

    Mirrors `comparanda`'s ``supersession-resolves`` and ``supersession-acyclic``.
    Unchecked, a reference to nothing switches an assertion off -- it stops being
    live -- and so exempts its cell from ``independence-recorded``: the escape
    `comparanda` closed in its #165.
    """
    for cell in document.get("cells", []):
        by_id = {a["id"]: a for a in cell.get("assertions", [])}
        for assertion in cell.get("assertions", []):
            target = assertion.get("supersededBy")
            if not target:
                continue
            path = f"{_cell_path(cell)}.assertions[{assertion['id']}].supersededBy"
            if target == assertion["id"] or target not in by_id:
                yield Problem(
                    path=path,
                    message=(
                        f'assertion "{assertion["id"]}" is superseded by "{target}", which is '
                        + ("itself." if target == assertion["id"] else "not an assertion in this cell.")
                        + " It no longer counts as live, and nothing replaced it."
                    ),
                    fix="name the assertion in this cell that replaced it, or remove supersededBy.",
                    rule_id="supersession-resolves",
                )
                continue
            seen = {assertion["id"]}
            nxt = target
            while nxt in by_id and nxt not in seen:
                seen.add(nxt)
                nxt = by_id[nxt].get("supersededBy")
            # Flag only the members of the cycle, as the companion does: an
            # assertion that merely leads into one is reported by its members.
            if nxt == assertion["id"]:
                yield Problem(
                    path=path,
                    message=f'assertion "{assertion["id"]}" is on a supersession cycle, so no assertion in it is live.',
                    fix="break the cycle: the latest assertion carries no supersededBy.",
                    rule_id="supersession-acyclic",
                )


def missing_rule_code_defined(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A criterion's missing rule names a code someone defines.

    Mirrors `comparanda`'s ``missing-rule-code-defined`` (its ADR-0030): the
    code is a core one, or declared on the analysis, or on the criterion. A rule
    naming anything else is one nobody can follow, because nothing says what
    its blank means.
    """
    from rubricator.schema.vocabulary import vocabulary

    analysis_codes = list(document.get("missingCodes", []))
    for i, criterion in enumerate(document.get("criteria", [])):
        # Nearest scope first, as the companion's makeVocabulary orders it.
        declarations = [*criterion.get("missingCodes", []), *analysis_codes]
        rules = (criterion.get("definition") or {}).get("missingRules", [])
        for k, rule in enumerate(rules):
            code = rule.get("code", "")
            if vocabulary().resolve(code, declarations).source != "undeclared":
                continue
            yield Problem(
                path=f"criteria[{i}].definition.missingRules[{k}].code",
                message=(
                    f'criterion "{criterion.get("id")}" tells raters to record "{code}", but that '
                    "code is neither a core code nor declared in this document or on this criterion."
                ),
                fix=(
                    "name a core code, or declare this one in missingCodes (on the analysis or on "
                    "the criterion) with a broader parent and what it means."
                ),
                rule_id="missing-rule-code-defined",
            )


def _declaration_lists(
    document: Mapping[str, Any],
) -> Iterable[tuple[Sequence[tuple[int, Mapping[str, Any]]], str, Mapping[str, Any], str]]:
    """Every declaration list -- its vocabulary, the core it extends, its path -- as the companion walks them.

    One walk over (list, core, field) rather than one per rule and vocabulary,
    because the companion's own comment on its loop holds here too: three copies
    is how the fourth vocabulary gets forgotten. Criterion overlays are included
    -- missing them would let a criterion redeclare a core code, which is the one
    thing ``no-redeclaring-core`` stops.
    """
    from rubricator.schema.vocabulary import vocabulary

    def declarations(value: Any) -> list[tuple[int, Mapping[str, Any]]]:
        # Over documents from disk: a list that is not a list, an entry that is
        # not an object or an id that is not a string is a shape problem, the
        # schema's to report. Skipped here, so a rule never raises on one.
        if not isinstance(value, (list, tuple)):
            return []
        return [
            (i, d) for i, d in enumerate(value)
            if isinstance(d, Mapping) and isinstance(d.get("id"), str)
        ]

    core = vocabulary()
    yield declarations(document.get("missingCodes")), "missingCode", core.missing_codes, "missingCodes"
    yield declarations(document.get("reductions")), "reduction", core.reductions, "reductions"
    criteria = document.get("criteria")
    for i, criterion in enumerate(criteria if isinstance(criteria, (list, tuple)) else []):
        if isinstance(criterion, Mapping):
            yield (declarations(criterion.get("missingCodes")), "missingCode", core.missing_codes,
                   f"criteria[{i}].missingCodes")


def structural_refines_not_applicable(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A declaration with ``structural: true`` refines the one structural core code.

    Mirrors `comparanda`'s ``structural-refines-not-applicable`` (its ADR-0009,
    clause 3). Structural absence leaves every denominator and every dominance
    comparison, so a code that claims it while refining, say, ``withheld`` would
    silently remove cells somebody deliberately declined to show. The core code
    is found by its facts, not by its spelling.
    """
    from rubricator.schema.vocabulary import vocabulary

    structural = sorted(c for c, f in vocabulary().missing_codes.items() if f.structural)
    for decls, kind, _core, field in _declaration_lists(document):
        if kind != "missingCode":
            continue
        for i, d in decls:
            if d.get("structural") is True and d.get("broader") not in structural:
                yield Problem(
                    path=f"{field}[{i}]",
                    message=(
                        f'"{d.get("id")}" declares structural: true but refines '
                        f'"{d.get("broader")}". Structural absence leaves every denominator and '
                        f'every comparison, which only "{" or ".join(structural)}" means.'
                    ),
                    fix=f'set broader to "{structural[0]}", or drop structural: true.',
                    rule_id="structural-refines-not-applicable",
                    family="schema",
                )


def no_redeclaring_core(document: Mapping[str, Any]) -> Iterable[Problem]:
    """No declaration reuses a core id (`comparanda`'s ``no-redeclaring-core``, ADR-0009).

    A core code redeclared with other flags or another parent would mean one
    thing to this build -- which resolves the core first -- and another to any
    reader that took the declaration, so the same blank would count differently.
    """
    for decls, _kind, core, field in _declaration_lists(document):
        for i, d in decls:
            if d.get("id") in core:
                yield Problem(
                    path=f"{field}[{i}]",
                    message=f'"{d.get("id")}" is a core member and cannot be redeclared.',
                    fix="use the core member as it is, or give the extension a different id.",
                    rule_id="no-redeclaring-core",
                    family="schema",
                )


def unique_declarations(document: Mapping[str, Any]) -> Iterable[Problem]:
    """No id is declared twice in one list (`comparanda`'s ``unique-declarations``).

    Which one applies would then depend on the reader: this package's own
    counts take the first (``declarations_for``), and nothing says another
    reader does.
    """
    for decls, _kind, _core, field in _declaration_lists(document):
        seen: set[Any] = set()
        for i, d in decls:
            if d.get("id") in seen:
                yield Problem(
                    path=f"{field}[{i}]",
                    message=(
                        f'"{d.get("id")}" is declared more than once, so which declaration '
                        "applies depends on the reader (this package's counts take the first)."
                    ),
                    fix="remove the duplicate, or give it a different id.",
                    rule_id="unique-declarations",
                    family="schema",
                )
            seen.add(d.get("id"))


#: The structural rules over declarations, in the companion's order.
SCHEMA_RULES: Sequence[Rule] = (
    structural_refines_not_applicable,
    no_redeclaring_core,
    unique_declarations,
)


def schema_problems(
    document: Mapping[str, Any], *, rules: Sequence[Rule] = SCHEMA_RULES
) -> list[Problem]:
    """Every declaration problem in an analysis, across every rule, in one pass.

    >>> doc = {'criteria': [{'id': 'c', 'missingCodes': [
    ...     {'id': 'not-evidenced', 'broader': 'withheld', 'means': 'mine'},
    ...     {'id': 'gone', 'broader': 'withheld', 'means': 'left out', 'structural': True}]}]}
    >>> [(p.path, p.rule_id) for p in schema_problems(doc)]
    [('criteria[0].missingCodes[1]', 'structural-refines-not-applicable'), ('criteria[0].missingCodes[0]', 'no-redeclaring-core')]
    """
    return [p for rule in rules for p in rule(document)]


#: The honesty rules, in the order their problems are reported.
HONESTY_RULES: Sequence[Rule] = (
    unique_ids,
    supersession_resolves,
    independence_recorded,
    missing_rule_code_defined,
)


def honesty_problems(
    document: Mapping[str, Any], *, rules: Sequence[Rule] = HONESTY_RULES
) -> list[Problem]:
    """Every honesty problem in a merged analysis, across every rule, in one pass."""
    return [p for rule in rules for p in rule(document)]
