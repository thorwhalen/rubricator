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

>>> cited = [{'id': 'e1', 'sourceType': 'primary', 'excerpt': 'as stated'}]
>>> why = 'the manual states it'
>>> people = [{'id': 'ana', 'displayName': 'Ana', 'kind': 'human'},
...           {'id': 'ben', 'displayName': 'Ben', 'kind': 'human'}]
>>> doc = {'authors': people, 'cells': [{'alternativeId': 'a', 'criterionId': 'c', 'measure': 'score',
...         'assertions': [{'id': 's1', 'authorId': 'ana', 'value': 4, 'evidence': cited,
...                         'justification': why},
...                        {'id': 's2', 'authorId': 'ben', 'value': 2, 'evidence': cited,
...                         'justification': why, 'independence': 'independent'}]}]}
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
    "RULE_SOURCES",
    "HONESTY_RULES",
    "honesty_problems",
    "independence_recorded",
    "independent_is_distinct",
    "procedure_and_round_resolve",
    "unique_ids",
    "missing_rule_code_defined",
    "declaration_entries",
    "value_cites_evidence",
    "blank_has_a_note",
    "unsearched_blank_cites_nothing",
    "cite_a_span",
    "inference_names_its_sources",
    "external_support_required",
    "check_dated_and_attributed",
    "score_has_a_reason",
    "derived_from_resolves",
    "unique_evidence_ids",
    "EXTERNAL_SOURCE_TYPES",
    "declarations_for",
    "supersession_resolves",
    "live_assertions",
    "drawn_assertions",
    "SCHEMA_RULES",
    "schema_problems",
    "structural_refines_not_applicable",
    "no_redeclaring_core",
    "unique_declarations",
    "cell_coordinates_exist",
    "blank_is_defined",
    "assertion_attributed",
    "agent_is_typed",
    "persona_keeps_kind",
    "disclosure_flag_is_projection_only",
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

    @property
    def citation(self) -> str:
        """The rule and the decision it comes from, as every refusal ends (#171)."""
        source = RULE_SOURCES.get(self.rule_id)
        return f"[rule {self.rule_id}" + (f"; {source}]" if source else "]")

    def __str__(self) -> str:
        return f"{self.path}: {self.message} Fix: {self.fix} {self.citation}"


#: Where each rule was decided. A bare ``ADR-`` is this repository's; the
#: companion's are prefixed, because the two number their ADRs independently.
RULE_SOURCES: Mapping[str, str] = {
    "unique-ids": "comparanda ADR-0031",
    "supersession-resolves": "comparanda ADR-0011",
    "supersession-acyclic": "comparanda ADR-0011",
    "independence-recorded": "ADR-0022",
    "independent-is-distinct": "ADR-0018",
    "procedure-and-round-resolve": "ADR-0018",
    "missing-rule-code-defined": "comparanda ADR-0030",
    "unique-evidence-ids": "ADR-0015",
    "value-cites-evidence": "ADR-0006",
    "blank-has-a-note": "ADR-0006",
    "unsearched-blank-cites-nothing": "ADR-0006",
    "cite-a-span": "ADR-0014",
    "inference-names-its-sources": "ADR-0015",
    "derived-from-resolves": "ADR-0015",
    "derived-from-acyclic": "ADR-0015",
    "external-support-required": "ADR-0006",
    "check-dated": "ADR-0014",
    "check-attributed": "ADR-0014",
    "score-has-a-reason": "comparanda ADR-0031",
    "structural-refines-not-applicable": "comparanda ADR-0009",
    "no-redeclaring-core": "comparanda ADR-0009",
    "unique-declarations": "comparanda ADR-0030",
    "cell-coordinates-exist": "comparanda",
    "blank-is-defined": "comparanda ADR-0030",
    "assertion-attributed": "comparanda ADR-0012",
    "agent-is-typed": "comparanda ADR-0012",
    "persona-keeps-kind": "comparanda ADR-0012",
    "disclosure-flag-is-projection-only": "comparanda ADR-0021",
}


Rule = Callable[[Mapping[str, Any]], Iterable[Problem]]


def _cell_path(cell: Mapping[str, Any]) -> str:
    return f"cells[{cell['alternativeId']}/{cell['criterionId']}/{cell.get('measure', 'score')}]"


def live_assertions(cell: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The assertions of a cell that nothing has superseded.

    Absences count: a qualified blank beside a score is two claims about one cell,
    and which of them a reader sees depends on whether they were independent.
    """
    return [a for a in cell.get("assertions", []) if not a.get("supersededBy")]


def drawn_assertions(
    cell: Mapping[str, Any], document: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """The live assertions of a cell that are draws: every one but a placeholder blank.

    A blank whose code is not terminal (``not-assessed``, ``deferred``, or a declared
    code that refines one) says nobody has looked yet. It is not a second claim
    about the cell, so it is nothing a score beside it could be independent *of*
    (#225). A terminal blank (``not-evidenced``, ``indeterminate``) is a finding and
    counts. Found by the code's ``terminal`` fact, never its spelling.
    """
    from rubricator.schema.vocabulary import vocabulary

    declarations = declarations_for(document, cell.get("criterionId"))

    def is_placeholder(assertion: Mapping[str, Any]) -> bool:
        missing = assertion.get("missing")
        code = missing.get("code") if isinstance(missing, Mapping) else None
        if not isinstance(code, str) or assertion.get("value") is not None:
            return False
        facts = vocabulary().resolve(code, declarations).facts
        return facts is not None and not facts.terminal

    return [a for a in live_assertions(cell) if not is_placeholder(a)]


def independence_recorded(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A cell holding two or more drawn assertions records ``independence`` on each.

    Mirrors `comparanda`'s ``independence-recorded`` (its ADR-0031, ADR-0022).
    Without the rung, five draws of one model and five people who argued in a
    room are the same bytes, and the reader is shown "5 raters" for both. A
    single assertion is exempt: there is nothing to be independent *of*; so is a
    placeholder blank, which is no draw (:func:`drawn_assertions`).
    """
    for cell in document.get("cells", []):
        live = drawn_assertions(cell, document)
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


def independent_is_distinct(document: Mapping[str, Any]) -> Iterable[Problem]:
    """An agent that records ``independent`` differs, by a recorded model, from every other agent beside it.

    This repository's own rule (ADR-0018), not a mirror: the companion stores the
    rung and cannot see whether two agents were one model. A fresh session of the
    same model is ``resampled``; labelling it ``independent`` is how five draws
    of one model come to read as five raters. Only a cell holding two or more
    drawn assertions can fail, as for ``independence-recorded``.
    """
    from rubricator.independence import distinct_model_problem

    authors = {a.get("id"): a for a in document.get("authors", []) if isinstance(a, Mapping)}
    for cell in document.get("cells", []):
        live = drawn_assertions(cell, document)
        if len(live) < 2:
            continue
        for assertion in live:
            why = distinct_model_problem(assertion, live, authors)
            if why is None:
                continue
            yield Problem(
                path=f"{_cell_path(cell)}.assertions[{assertion['id']}].independence",
                message=f'assertion "{assertion["id"]}" claims "independent", but {why}.',
                fix=(
                    'record "resampled" (or "perturbed" with a perturbation record) for another '
                    'draw of the same model, or record the distinct model on the author.'
                ),
                rule_id="independent-is-distinct",
            )


def procedure_and_round_resolve(document: Mapping[str, Any]) -> Iterable[Problem]:
    """An assertion's ``procedureId`` and ``roundId`` name entries the document has (ADR-0018, #99).

    A reference to a procedure or round the document lacks would send a reader of
    the disclosure to a record that is not there.
    """
    known = {
        "procedureId": {p.get("id") for p in document.get("procedures", []) if isinstance(p, Mapping)},
        "roundId": {r.get("id") for r in document.get("rounds", []) if isinstance(r, Mapping)},
    }
    where = {"procedureId": "procedures", "roundId": "rounds"}
    for cell in document.get("cells", []):
        for assertion in cell.get("assertions", []):
            for field, ids in known.items():
                ref = assertion.get(field)
                if ref is None or ref in ids:
                    continue
                yield Problem(
                    path=f"{_cell_path(cell)}.assertions[{assertion['id']}].{field}",
                    message=f'assertion "{assertion["id"]}" names {field} "{ref}", which {where[field]}[] does not hold.',
                    fix=f"write the pass through measures_write's procedure argument, which records the {field[:-2]} it names.",
                    rule_id="procedure-and-round-resolve",
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

    analysis_codes = declaration_entries(document.get("missingCodes"))
    for i, criterion in _objects(document.get("criteria")):
        # Nearest scope first, as the companion's makeVocabulary orders it.
        declarations = [*declaration_entries(criterion.get("missingCodes")), *analysis_codes]
        definition = criterion.get("definition")
        rules = definition.get("missingRules") if isinstance(definition, Mapping) else None
        for k, rule in _objects(rules):
            code = rule.get("code", "")
            # A code that is not a string names nothing anyone declares (#169).
            if isinstance(code, str) and vocabulary().resolve(code, declarations).source != "undeclared":
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


def blank_is_defined(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A blank's code is one the document defines (`comparanda`'s ``blank-is-defined``, its ADR-0030).

    Distinct from :func:`missing_rule_code_defined`, which is about a *rule* naming a
    code. This is a stored blank whose code is neither core nor declared on the
    analysis or its criterion: nothing anywhere says what the blank means, which no
    reader can repair. A code a build merely does not implement degrades through
    ``broader`` and is not a problem here.
    """
    from rubricator.schema.vocabulary import vocabulary

    for cell, assertion, path in _assertions(document):
        missing = assertion.get("missing")
        if not isinstance(missing, Mapping):
            continue
        code = str(missing.get("code", ""))
        declarations = declarations_for(document, cell["criterionId"])
        if vocabulary().resolve(code, declarations).source != "undeclared":
            continue
        yield Problem(
            path=f"{path}.missing.code",
            message=(
                f'the code "{code}" is neither a core code nor declared in this document or on '
                "this criterion, so nothing anywhere says what this blank means."
            ),
            fix=(
                "use a core code, or declare this one in missingCodes (on the analysis or on the "
                "criterion) with a broader parent and what it means."
            ),
            rule_id="blank-is-defined",
        )


def assertion_attributed(document: Mapping[str, Any]) -> Iterable[Problem]:
    """Every assertion names an author the document lists (`comparanda`'s ``assertion-attributed``, its ADR-0012).

    An assertion nobody is named for cannot be weighed, and an agreement statistic over
    it cannot know how many heads produced it.
    """
    known = {a.get("id") for a in document.get("authors", []) if isinstance(a, Mapping)}
    for _cell, assertion, path in _assertions(document):
        if assertion.get("authorId") in known:
            continue
        yield Problem(
            path=f"{path}.authorId",
            message=(
                f'unknown author "{assertion.get("authorId")}". An assertion nobody is named for '
                "cannot be weighed, and an agreement statistic over it cannot know how many heads "
                "produced it."
            ),
            fix="add the author to authors, or attribute the assertion to an existing one.",
            rule_id="assertion-attributed",
        )


def agent_is_typed(document: Mapping[str, Any]) -> Iterable[Problem]:
    """An author carrying an agent run is not of kind ``human`` (`comparanda`'s ``agent-is-typed``, its ADR-0012).

    A model dressed as a person is the lie; an import or a derivation that records the run
    behind it is not.
    """
    for author in document.get("authors", []):
        if isinstance(author, Mapping) and author.get("agent") and author.get("kind") == "human":
            yield Problem(
                path=f"authors[{author.get('id')}]",
                message=(
                    f'author "{author.get("id")}" carries an agent run but is of kind "human", so a '
                    "model's assertions would read as a person's."
                ),
                fix=(
                    'set kind to "agent", or remove the agent record if a person or import really '
                    "made these assertions."
                ),
                rule_id="agent-is-typed",
            )


def persona_keeps_kind(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A persona has its principal's kind (`comparanda`'s ``persona-keeps-kind``, its ADR-0012).

    A persona never changes who made the assertion.
    """
    kinds = {a.get("id"): a.get("kind") for a in document.get("authors", []) if isinstance(a, Mapping)}
    for author in document.get("authors", []):
        if not isinstance(author, Mapping) or author.get("principalId") is None:
            continue
        principal_kind = kinds.get(author["principalId"])
        if principal_kind is None or principal_kind == author.get("kind"):
            continue
        yield Problem(
            path=f"authors[{author.get('id')}]",
            message=(
                f'persona "{author.get("id")}" is of kind "{author.get("kind")}" but its principal '
                f'"{author["principalId"]}" is "{principal_kind}"; a persona never changes who made '
                "the assertion."
            ),
            fix=f'give the persona its principal\'s kind, "{principal_kind}".',
            rule_id="persona-keeps-kind",
        )


def disclosure_flag_is_projection_only(document: Mapping[str, Any]) -> Iterable[Problem]:
    """``withheldFromReader`` is true only of an assertion with nothing left in it (`comparanda`'s rule, its ADR-0021).

    The flag records what a projection removed. On an assertion that still carries a value,
    a justification, a note or evidence it is either a producer mistaking it for a request to
    withhold, or an attempt to inflate the widened-cell count.
    """
    for _cell, assertion, path in _assertions(document):
        disclosure = assertion.get("disclosure")
        if not (isinstance(disclosure, Mapping) and disclosure.get("withheldFromReader") is True):
            continue
        missing = assertion.get("missing")
        # The companion's own test of content (``trim()`` truthiness): looser than
        # _is_blank_text on purpose. A flag that is true of anything but an emptied
        # assertion is a lie, so a zero-width note still counts as content here.
        def said(value: Any) -> bool:
            return isinstance(value, str) and bool(value.strip())

        has_content = (
            assertion.get("value") is not None
            or said(assertion.get("justification"))
            or bool(assertion.get("evidence"))
            or (isinstance(missing, Mapping) and said(missing.get("note")))
        )
        if not has_content:
            continue
        yield Problem(
            path=f"{path}.disclosure.withheldFromReader",
            message=(
                "marked as projected out for its reader, but it still carries a value, a "
                "justification, a note or evidence. The flag records what a projection removed; "
                "it is not a request to withhold, and it cannot be true of an assertion with content."
            ),
            fix=(
                "remove withheldFromReader and let projectForReader decide what this reader sees; "
                "to keep the value from every reader, record a withheld absence instead."
            ),
            rule_id="disclosure-flag-is-projection-only",
        )


def declarations_for(document: Mapping[str, Any], criterion_id: str) -> list[Mapping[str, Any]]:
    """The missingness declarations in scope for one criterion, nearest first.

    The criterion's own codes come before the analysis's, as in the companion's
    ``makeVocabulary``: the resolver takes the first match, so a criterion-scoped
    redefinition wins inside that criterion and nowhere else.
    """
    criterion = next(
        (c for _, c in _objects(document.get("criteria")) if c.get("id") == criterion_id), {}
    )
    return [
        *declaration_entries(criterion.get("missingCodes")),
        *declaration_entries(document.get("missingCodes")),
    ]


def declaration_entries(value: Any) -> list[Mapping[str, Any]]:
    """The declarations in a ``missingCodes`` list as read from disk: its object entries only.

    A hand edit can leave ``null``, a number or an object where the list should
    be, or junk among its entries (#169). Those are shape problems, the schema's
    to report; a reader walks past them rather than raising, as
    :func:`_declaration_lists` does for the schema-family rules. What is lost is
    only a declaration nobody could have read, so a blank or rule naming it
    resolves as undeclared -- reported, and counted as outstanding, the cautious
    direction.

    >>> declaration_entries(None), declaration_entries(5), declaration_entries({"id": "x"})
    ([], [], [])
    >>> declaration_entries([None, {"id": "x"}, "y"])
    [{'id': 'x'}]
    """
    return [d for _, d in _objects(value)]


def _objects(value: Any) -> list[tuple[int, Mapping[str, Any]]]:
    """``(index, entry)`` for each object in a list from disk; anything that is not a list is empty."""
    if not isinstance(value, (list, tuple)):
        return []
    return [(i, d) for i, d in enumerate(value) if isinstance(d, Mapping)]


#: The source types that are someone else's words rather than the agent's own
#: output. Mirrors `comparanda`'s ``isExternalSupport``: the manifest publishes
#: the closed ``sourceType`` enum but not this fact about its members, so it is
#: stated once here and a parity test holds it to the enum.
EXTERNAL_SOURCE_TYPES = frozenset({"primary", "secondary"})


def _assertions(
    document: Mapping[str, Any],
) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any], str]]:
    """Every assertion of every cell, with its cell and its path."""
    for cell in document.get("cells", []):
        for assertion in cell.get("assertions", []):
            yield cell, assertion, f"{_cell_path(cell)}.assertions[{assertion.get('id')}]"


def _spans(assertion: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The evidence references of an assertion that are objects (the schema reports the rest)."""
    evidence = assertion.get("evidence")
    return [r for r in evidence if isinstance(r, Mapping)] if isinstance(evidence, list) else []


def _is_blank_text(value: Any) -> bool:
    """Not a string, or one with nothing visible in it (:func:`rubricator.locators.is_blank_text`)."""
    from rubricator.locators import is_blank_text

    return not isinstance(value, str) or is_blank_text(value)


def value_cites_evidence(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A value rests on at least one evidence reference that supports it (#59, ADR-0006).

    The honesty-family twin of `comparanda`'s completeness rule
    ``value-has-evidence``: that one tolerates a considered human judgement with
    nothing cited, and a renderer may. A producer whose claim is "cite spans,
    not documents" may not -- a value with nothing under it is the confident
    guess ADR-0006 replaces with a qualified blank.

    **Rests on** means a reference whose ``stance`` is ``supports`` (absent
    means ``supports``, the schema's default). A top score whose only citations
    contradict it, qualify it or give context is cited, and nothing under it
    says it is so (#195, from #178).
    """
    for _cell, assertion, path in _assertions(document):
        if assertion.get("value") is None:
            continue
        spans = _spans(assertion)
        if spans and not any(r.get("stance", "supports") == "supports" for r in spans):
            stances = ", ".join(sorted({str(r.get("stance")) for r in spans}))
            yield Problem(
                path=f"{path}.evidence",
                message=(
                    f"a value whose every evidence reference is {stances}, so nothing cited "
                    "supports it."
                ),
                fix=(
                    'cite the span the value rests on with stance "supports", or record a '
                    'qualified blank instead ("indeterminate" if the sources conflict, '
                    '"not-evidenced" if none bears on it).'
                ),
                rule_id="value-cites-evidence",
            )
        elif not spans:
            yield Problem(
                path=f"{path}.evidence",
                message="a value with no evidence reference, so nothing a reader can check supports it.",
                fix=(
                    "cite the span the value rests on, or record a qualified blank instead "
                    '("not-evidenced" if the sources are silent, "indeterminate" if they conflict).'
                ),
                rule_id="value-cites-evidence",
            )


def blank_has_a_note(document: Mapping[str, Any]) -> Iterable[Problem]:
    """Every qualified blank says, in its ``note``, why this cell is blank (ADR-0006).

    The code classifies the blank; the note is what makes it checkable -- which
    sources were read, what they said, what was left for later.
    """
    for _cell, assertion, path in _assertions(document):
        missing = assertion.get("missing")
        if not isinstance(missing, Mapping):
            continue
        if _is_blank_text(missing.get("note")):
            yield Problem(
                path=f"{path}.missing.note",
                message=f'a "{missing.get("code")}" blank with no note, so nothing says why this cell is blank.',
                fix="write one line in missing.note: what was searched and what it showed, or why it was left.",
                rule_id="blank-has-a-note",
            )


def unsearched_blank_cites_nothing(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A blank whose code is not terminal carries no evidence (ADR-0006).

    A non-terminal code (``not-assessed``, ``deferred``, and any declared code
    that refines one) says nobody has looked yet. A span beside it reads as
    proof that someone searched. Found by the code's ``terminal`` fact, never
    its spelling; an undeclared code is ``missing-rule-code-defined``'s to report.
    """
    from rubricator.schema.vocabulary import vocabulary

    for cell, assertion, path in _assertions(document):
        missing = assertion.get("missing")
        if not isinstance(missing, Mapping) or not _spans(assertion):
            continue
        code = missing.get("code")
        resolved = vocabulary().resolve(code, declarations_for(document, cell.get("criterionId")))
        if resolved.facts is not None and not resolved.facts.terminal:
            yield Problem(
                path=f"{path}.evidence",
                message=(
                    f'a "{code}" blank says nobody has looked yet, but it carries evidence, which '
                    "reads as proof that someone searched."
                ),
                fix=(
                    "drop the evidence, or, if the sources were read, record the blank the search "
                    'supports ("not-evidenced" if silent, "indeterminate" if they conflict) or a value.'
                ),
                rule_id="unsearched-blank-cites-nothing",
            )


def cite_a_span(document: Mapping[str, Any]) -> Iterable[Problem]:
    """An evidence reference locates a span: a selector or an excerpt (ADR-0014).

    Mirrors `comparanda`'s ``cite-a-span``. A reference with nothing to locate
    is a citation of a whole document, which nobody can check.
    """
    for _cell, assertion, path in _assertions(document):
        for ref in _spans(assertion):
            if not ref.get("selectors") and _is_blank_text(ref.get("excerpt")):
                yield Problem(
                    path=f"{path}.evidence[{ref.get('id')}]",
                    message=(
                        f'evidence "{ref.get("id")}" names a source but no span in it: no selector '
                        "and no excerpt. Pointing at a whole document is not evidence."
                    ),
                    fix="add a TextQuoteSelector with the quoted words, or an excerpt.",
                    rule_id="cite-a-span",
                )


def inference_names_its_sources(document: Mapping[str, Any]) -> Iterable[Problem]:
    """The agent's own summary or inference names what it was derived from (ADR-0015).

    Mirrors `comparanda`'s ``inference-names-its-sources``. An inference citing
    nothing is the agent's output filed as a citation -- the failure ADR-0006
    names.
    """
    for _cell, assertion, path in _assertions(document):
        for ref in _spans(assertion):
            if ref.get("sourceType") in EXTERNAL_SOURCE_TYPES or ref.get("derivedFrom"):
                continue
            yield Problem(
                path=f"{path}.evidence[{ref.get('id')}].derivedFrom",
                message=(
                    f'evidence "{ref.get("id")}" has sourceType "{ref.get("sourceType")}", the '
                    "agent's own output, and names no reference it was derived from. An inference "
                    "citing nothing is not a citation."
                ),
                fix=(
                    "list in derivedFrom the ids of the references this was derived from, or "
                    "record the cell as a qualified blank instead."
                ),
                rule_id="inference-names-its-sources",
            )


def external_support_required(document: Mapping[str, Any]) -> Iterable[Problem]:
    """Something other than the agent's own output supports the assertion (ADR-0006).

    Mirrors `comparanda`'s ``external-support-required``: when every reference
    whose stance is ``supports`` (absent means ``supports``, the schema's
    default) is an ``agent-summary`` or ``agent-inference``, the agent's
    reasoning has been filed as the citation. ``inference-names-its-sources``
    and ``derived-from-resolves`` hold each inference to a chain; this holds the
    assertion to an external source it rests on directly.
    """
    for _cell, assertion, path in _assertions(document):
        supporting = [r for r in _spans(assertion) if r.get("stance", "supports") == "supports"]
        if supporting and not any(r.get("sourceType") in EXTERNAL_SOURCE_TYPES for r in supporting):
            yield Problem(
                path=f"{path}.evidence",
                message=(
                    "every supporting reference is the agent's own summary or inference, so "
                    "nothing external supports this assertion."
                ),
                fix=(
                    "cite the primary or secondary span the inference rests on, with stance "
                    '"supports", or record a qualified blank instead ("not-evidenced" if the '
                    'sources are silent, "indeterminate" if they conflict).'
                ),
                rule_id="external-support-required",
            )


def check_dated_and_attributed(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A citation check with a verdict records when it ran and what ran it (ADR-0014).

    Mirrors `comparanda`'s ``check-dated`` and ``check-attributed``. A verdict
    with no date reads as current forever, and one with no checker cannot be
    re-run to see whether today's checker agrees. ``unchecked`` is exempt: it is
    the absence of a verdict, not an undated one.
    """
    for _cell, assertion, path in _assertions(document):
        for ref in _spans(assertion):
            check = ref.get("check")
            if not isinstance(check, Mapping) or check.get("status") == "unchecked":
                continue
            where = f"{path}.evidence[{ref.get('id')}].check"
            status = check.get("status")
            if _is_blank_text(check.get("checkedAt")):
                yield Problem(
                    path=f"{where}.checkedAt",
                    message=f'a check with status "{status}" records no checkedAt, so the verdict reads as current forever.',
                    fix='set checkedAt to the moment the check ran, or set status to "unchecked".',
                    rule_id="check-dated",
                )
            if _is_blank_text(check.get("checkerVersion")):
                yield Problem(
                    path=f"{where}.checkerVersion",
                    message=(
                        f'a check with status "{status}" records no checkerVersion, so a reader '
                        "cannot tell whether the current checker would still agree."
                    ),
                    fix="set checkerVersion to the identifier of the checker that produced this verdict.",
                    rule_id="check-attributed",
                )


def score_has_a_reason(document: Mapping[str, Any]) -> Iterable[Problem]:
    """A value carries a ``justification`` (`comparanda`'s ``score-has-a-reason``).

    The justification is the most-read field of a cell and the only part of it
    a reader can argue with; a number without one is unarguable except on taste.
    """
    for _cell, assertion, path in _assertions(document):
        if assertion.get("value") is not None and _is_blank_text(assertion.get("justification")):
            yield Problem(
                path=f"{path}.justification",
                message="a value with no justification, so a reader has nothing to disagree with but the number.",
                fix="write one line saying what the cited evidence shows, or record a qualified blank instead.",
                rule_id="score-has-a-reason",
            )


def _ids(value: Any, *, keep_blank: bool = False) -> list[Any]:
    """The entries of a ``derivedFrom`` list; anything else is the schema's to report."""
    if not isinstance(value, list):
        return []
    return [d for d in value if keep_blank or (isinstance(d, str) and not _is_blank_text(d))]


def derived_from_resolves(document: Mapping[str, Any]) -> Iterable[Problem]:
    """``derivedFrom`` names other references of the same assertion, with no cycle (ADR-0015).

    ``inference-names-its-sources`` only asks that the list be non-empty, which
    ``[""]``, an id naming nothing, or the reference's own id would satisfy.
    ADR-0015 makes the evidence array a small graph, and an edge to nowhere or
    back to itself names no source. Stricter than `comparanda`, which checks the
    length only. A chain that resolves and does not cycle ends at a reference
    with no ``derivedFrom``, which ``inference-names-its-sources`` holds to be
    someone else's words.
    """
    for _cell, assertion, path in _assertions(document):
        spans = _spans(assertion)
        edges = {r.get("id"): _ids(r.get("derivedFrom")) for r in spans}
        for ref in spans:
            where = f"{path}.evidence[{ref.get('id')}].derivedFrom"
            dangling = [d for d in _ids(ref.get("derivedFrom"), keep_blank=True)
                        if _is_blank_text(d) or d == ref.get("id") or d not in edges]
            if dangling:
                yield Problem(
                    path=where,
                    message=(
                        f'evidence "{ref.get("id")}" is derived from '
                        f'{", ".join(repr(d) for d in dangling)}, which is not another reference '
                        "of this assertion, so it names no source."
                    ),
                    fix="name the ids of the other references in this cell's evidence it was drawn from.",
                    rule_id="derived-from-resolves",
                )
                continue
            seen, frontier = set(), list(edges.get(ref.get("id"), []))
            while frontier:
                nxt = frontier.pop()
                if nxt == ref.get("id"):
                    yield Problem(
                        path=where,
                        message=(
                            f'evidence "{ref.get("id")}" is on a derivedFrom cycle, so the '
                            "chain never reaches a source."
                        ),
                        fix="break the cycle: the chain must end at a primary or secondary reference.",
                        rule_id="derived-from-acyclic",
                    )
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.extend(edges.get(nxt, []))


def unique_evidence_ids(document: Mapping[str, Any]) -> Iterable[Problem]:
    """No two evidence references of one assertion share an id.

    A duplicate makes every ``derivedFrom`` naming that id ambiguous. Scoped to
    the assertion, not the cell: two contributors' references to the same
    passage may well both be called ``e1``.
    """
    for _cell, assertion, path in _assertions(document):
        seen: set[Any] = set()
        for ref in _spans(assertion):
            if ref.get("id") in seen:
                yield Problem(
                    path=f"{path}.evidence[{ref.get('id')}]",
                    message=f'duplicate evidence id "{ref.get("id")}" in this assertion.',
                    fix="give one of the references a different id, and point derivedFrom at the one meant.",
                    rule_id="unique-evidence-ids",
                )
            seen.add(ref.get("id"))


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
def cell_coordinates_exist(document: Mapping[str, Any]) -> Iterable[Problem]:
    """Every cell names an alternative and a criterion the document declares.

    Mirrors `comparanda`'s ``cell-coordinates-exist``. The write path refuses an
    undeclared row or column, but a read keeps any schema-valid file (#159), and a
    hand edit, an import or a branch merge can leave a cell naming nothing (#166):
    a measure on no alternative, which no view can place.
    """
    for axis, key, verb in (
        ("alternative", "alternativeId", "alternatives_set"),
        ("criterion", "criterionId", "criteria_set"),
    ):
        declared = {
            row.get("id") for row in document.get(f"{axis}s" if axis == "alternative" else "criteria", [])
            if isinstance(row, Mapping)
        }
        for i, cell in enumerate(document.get("cells", [])):
            if not isinstance(cell, Mapping) or cell.get(key) in declared:
                continue
            yield Problem(
                path=f"cells[{i}].{key}",
                message=f'unknown {axis} "{cell.get(key)}": the cell names a {axis} the analysis does not declare.',
                fix=f"declare the {axis} with {verb}, or correct the cell's {key}.",
                rule_id="cell-coordinates-exist",
                family="schema",
            )


SCHEMA_RULES: Sequence[Rule] = (
    structural_refines_not_applicable,
    no_redeclaring_core,
    unique_declarations,
    cell_coordinates_exist,
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
    independent_is_distinct,
    procedure_and_round_resolve,
    missing_rule_code_defined,
    unique_evidence_ids,
    value_cites_evidence,
    score_has_a_reason,
    blank_has_a_note,
    unsearched_blank_cites_nothing,
    cite_a_span,
    inference_names_its_sources,
    derived_from_resolves,
    external_support_required,
    check_dated_and_attributed,
    blank_is_defined,
    assertion_attributed,
    agent_is_typed,
    persona_keeps_kind,
    disclosure_flag_is_projection_only,
)


def honesty_problems(
    document: Mapping[str, Any], *, rules: Sequence[Rule] = HONESTY_RULES
) -> list[Problem]:
    """Every honesty problem in a merged analysis, across every rule, in one pass."""
    return [p for rule in rules for p in rule(document)]
