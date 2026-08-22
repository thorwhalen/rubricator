"""Resolving an extensible vocabulary, with degradation that is reported.

The Python half of the substrate the companion repository defines in
``src/core/schema/declarations.ts``. The semantics are deliberately identical,
because the two halves resolve the same documents and a difference between them
is a document that means one thing here and another there.

Three vocabularies are open-ended -- missingness reason codes, reductions and
measurement scales -- and each varies for the same reason: a deployment's
criteria are not ours to enumerate. The extension point is the **document**, not
the process. A registry keyed by name means nothing outside the process that
registered it, so a shared analysis becomes unreadable somewhere else and nobody
finds out until they open it. A declaration inside the document travels.

**Reading never raises; authoring does.** An id nobody declared, or one this
build cannot interpret, degrades through ``broader`` and records that it did.
Authoring with an unknown name raises and names every known one, because at
authoring time you are choosing and a silent default is a typo becoming a scale
nobody meant.

**A degradation is a fact about this build, never about the analysis.** It is
handed back beside the document and never written into it -- storing one would
make one reader's gap look like a property of the data, and the next reader, who
may implement the thing perfectly well, would inherit a complaint that was never
true for them.

>>> CORE = {'alpha': 'the first', 'beta': 'the second'}
>>> resolve_declaration('beta', CORE, []).source
'core'
>>> r = resolve_declaration('alpha-prime', CORE,
...     [{'id': 'alpha-prime', 'broader': 'alpha', 'means': 'a sharper alpha'}])
>>> r.source, r.facts
('degraded', 'the first')
>>> resolve_declaration('unheard-of', CORE, []).facts is None
True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Literal, Mapping, Sequence, TypeVar

__all__ = ["Resolution", "Degradation", "resolve_declaration", "require_known"]

F = TypeVar("F")

#: Where a resolution came from. ``degraded`` still carries facts -- the
#: parent's -- so everything downstream keeps computing; ``undeclared`` does not,
#: because there is nothing to fall back to and inventing one is the guess this
#: whole package refuses.
ResolutionSource = Literal["core", "declared", "degraded", "undeclared"]

#: Which vocabulary a degradation is about.
DegradationAxis = Literal["missing-code", "reduction", "scale", "normaliser", "stability"]


@dataclass(frozen=True)
class Resolution(Generic[F]):
    """What a resolver returns: an answer, and how confident the build is in it."""

    id: str
    facts: F | None
    source: ResolutionSource
    broader: str | None = None
    because: str = ""

    def __bool__(self) -> bool:
        """True when this build genuinely understands the id.

        ``bool(resolution)`` is deliberately *not* "did we get facts": a degraded
        resolution has facts and is still something the reader should be told
        about.
        """
        return self.source in ("core", "declared")


@dataclass(frozen=True)
class Degradation:
    """One thing this build could not interpret, and where it was used."""

    axis: DegradationAxis
    id: str
    at: str
    because: str
    broader: str | None = None


def resolve_declaration(
    id: str,
    core: Mapping[str, F],
    declarations: Sequence[Mapping[str, Any]] = (),
    facts_of: Callable[[Mapping[str, Any], F], F | None] | None = None,
) -> Resolution[F]:
    """Resolve an id against a closed core plus the document's declarations.

    ``facts_of`` says how to build this vocabulary's facts from a declaration
    this build *can* interpret. Returning ``None`` -- or passing no callable at
    all -- means "declared, but I do not interpret it", which degrades.
    """
    if id in core:
        return Resolution(id=id, facts=core[id], source="core")

    decl = next((d for d in declarations if d.get("id") == id), None)
    if decl is None:
        return Resolution(
            id=id,
            facts=None,
            source="undeclared",
            because="no declaration for this id in the document, and nothing to fall back to",
        )

    broader = decl.get("broader")
    if broader not in core:
        # A declaration whose parent is not a core member. The document is
        # internally inconsistent; say so rather than picking a core member.
        return Resolution(
            id=id,
            facts=None,
            source="undeclared",
            because=f'declared with broader "{broader}", which is not a core member',
        )

    base = core[broader]
    facts = facts_of(decl, base) if facts_of else None
    if facts is not None:
        return Resolution(id=id, facts=facts, source="declared")

    return Resolution(
        id=id,
        facts=base,
        source="degraded",
        broader=broader,
        because=str(decl.get("means", "")),
    )


def degradation_of(
    resolution: Resolution[Any], axis: DegradationAxis, at: str
) -> Degradation | None:
    """A record for the caller's list, or ``None`` when nothing needs reporting."""
    if resolution:
        return None
    return Degradation(
        axis=axis,
        id=resolution.id,
        at=at,
        because=resolution.because,
        broader=resolution.broader,
    )


def require_known(id: str, table: Mapping[str, F], what: str) -> F:
    """The authoring half: choose a name, or fail naming every name.

    Never used on a read path. See the module docstring for why the two
    directions must behave differently.
    """
    try:
        return table[id]
    except KeyError:
        known = ", ".join(sorted(table))
        raise KeyError(
            f'unknown {what} "{id}". Known {what}s: {known}. To use a new one, declare it in '
            f'the analysis with a "broader" parent, so that a reader which does not implement '
            f"it can still classify it."
        ) from None
