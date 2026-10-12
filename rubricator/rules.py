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
    "live_assertions",
]

Family = Literal["honesty"]


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
        """Derived from the family, never chosen by a rule: honesty rejects."""
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


#: The honesty rules, in the order their problems are reported.
HONESTY_RULES: Sequence[Rule] = (independence_recorded,)


def honesty_problems(
    document: Mapping[str, Any], *, rules: Sequence[Rule] = HONESTY_RULES
) -> list[Problem]:
    """Every honesty problem in a merged analysis, across every rule, in one pass."""
    return [p for rule in rules for p in rule(document)]
