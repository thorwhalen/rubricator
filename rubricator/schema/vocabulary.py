"""The companion repository's vocabularies, vendored and read from an artifact.

`comparanda` emits two files: a JSON Schema for the document, and a **vocabulary
manifest** carrying what a JSON Schema cannot say. The schema can state that a
missingness code is a string; it cannot state that ``withheld`` is terminal and
**not** informative, and that fact is exactly what this package needs in order to
compute ``silenceRate`` the way the renderer will.

**Why a vendored copy rather than a constant.** Re-typing the tables here would
give two sources of truth that both look right and can disagree for months. The
manifest is a build artifact of the repository that owns the vocabulary, so
reading it is the only way this package's tables *cannot* be wrong about theirs.
ADR-0004 puts the cross-language parity test in the dependent -- here -- for that
reason: `comparanda` must never need to know this package exists.

**Why it lives under `rubricator/schema/`.** Nothing outside this package may
open a JSON file (ADR-0010's boundary test), so that adopting a new version of
the contract stays a file swap rather than a sweep through every consumer.

>>> v = vocabulary()
>>> v.facts('withheld').terminal, v.facts('withheld').informative
(True, False)
>>> v.facts('not-evidenced').informative
True
>>> v.resolve('paywalled').source
'undeclared'
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from rubricator.interpret.resolution import Resolution, resolve_declaration

__all__ = ["Vocabulary", "MissingCodeFacts", "vocabulary", "VOCABULARY_VERSION"]

#: The manifest version this build reads. Bumped deliberately, never inferred:
#: a silent upgrade is a silent change to what `silenceRate` counts.
VOCABULARY_VERSION = 1

_MANIFEST = Path(__file__).parent / "comparanda" / f"vocabularies.v{VOCABULARY_VERSION}.json"


@dataclass(frozen=True)
class MissingCodeFacts:
    """What a missingness code means, in the three flags analyses key on.

    Never the literal code: a deployment may declare its own, and every rate in
    this package is computed over the flags so that it keeps working when one
    does.
    """

    structural: bool
    terminal: bool
    informative: bool
    means: str


@dataclass(frozen=True)
class Vocabulary:
    """The core vocabularies of one version of the companion contract."""

    version: int
    missing_codes: Mapping[str, MissingCodeFacts]
    reductions: Mapping[str, Mapping[str, Any]]
    scales: Sequence[str]
    closed_enums: Mapping[str, Sequence[str]]

    def facts(self, code: str) -> MissingCodeFacts | None:
        """The facts for a core code, or ``None``. Prefer :meth:`resolve`."""
        return self.missing_codes.get(code)

    def resolve(
        self, code: str, declarations: Sequence[Mapping[str, Any]] = ()
    ) -> Resolution[MissingCodeFacts]:
        """Resolve a code through the one resolver, honouring declarations.

        A declared extension carries its own flags, so it never degrades -- which
        is the return on the companion repo carrying facts in the document rather
        than in an interpreter. An **undeclared** code resolves to nothing rather
        than defaulting: guessing ``informative`` would put an invention
        underneath the metric the honesty claim is measured by.
        """
        def facts_of(decl: Mapping[str, Any], base: MissingCodeFacts) -> MissingCodeFacts:
            return MissingCodeFacts(
                structural=bool(decl.get("structural", base.structural)),
                terminal=bool(decl.get("terminal", base.terminal)),
                informative=bool(decl.get("informative", base.informative)),
                means=str(decl["means"]),
            )

        return resolve_declaration(code, self.missing_codes, declarations, facts_of)

    def is_informative(self, code: str, declarations: Sequence[Mapping[str, Any]] = ()) -> bool:
        """Whether a blank with this code says something about the *subject*.

        ``False`` for an unresolvable code, which is the cautious direction: an
        unknown blank must not inflate ``silenceRate``, the one number a careless
        agent would otherwise move for free.
        """
        facts = self.resolve(code, declarations).facts
        return bool(facts and facts.informative)


@lru_cache(maxsize=None)
def vocabulary(version: int = VOCABULARY_VERSION) -> Vocabulary:
    """Load the vendored manifest.

    Cached because it is a frozen artifact read many times per analysis, and
    re-parsing 5 KB of JSON per cell is the kind of cost that is invisible until
    a matrix has five hundred of them.
    """
    path = _MANIFEST if version == VOCABULARY_VERSION else _MANIFEST.with_name(
        f"vocabularies.v{version}.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    vocabs = raw["vocabularies"]
    return Vocabulary(
        version=raw["schemaVersion"],
        missing_codes={
            code: MissingCodeFacts(
                structural=f["structural"],
                terminal=f["terminal"],
                informative=f["informative"],
                means=f["means"],
            )
            for code, f in vocabs["missingCode"]["facts"].items()
        },
        reductions=dict(vocabs["reduction"]["facts"]),
        scales=tuple(vocabs["scale"]["core"]),
        closed_enums={
            name: tuple(entry["core"])
            for name, entry in raw["closedEnums"].items()
            if name != "$comment"
        },
    )
