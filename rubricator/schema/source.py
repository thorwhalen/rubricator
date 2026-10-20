"""The boundary with the companion repository's published schema.

`rubricator` depends on `comparanda` for the analysis schema and validates at the
boundary (ADR-0002). The dependency never runs the other way.

**Why this facade exists at all.** The companion repo's schema was frozen as v1
only after most of this package was built, and the BRIEF anticipated exactly
this: build against the domain model and a hand-written sketch until the real one lands. The danger is that the sketch
*works*, so nothing forces the swap, and eighteen tools quietly grow their own
embedded copies of the shape. Then adopting the published artifact stops being a
one-line change and becomes a sweep.

So: every tool that validates does it through a :class:`SchemaSource`. No module
outside this one loads a schema, and a test enforces that. The swap is then a
constructor argument and a test run.

The facade also carries the version declaration ADR-0002 requires -- "rubricator
declares the schema versions it can emit" -- because that declaration has to live
somewhere a caller can read it, not in a comment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

__all__ = [
    "SchemaSource", "SchemaProblem", "SUPPORTED_SCHEMA_VERSIONS", "SchemaOrigin", "VENDORED_PATH",
    "explain", "published_schema_text", "EMITS", "emit_version", "vendored_schema",
]

#: The schema versions this build can read and emit. Declared, not inferred, so
#: a consumer can check compatibility before handing us a document.
#: The version handshake's explicit set (#127; comparanda ``cross-repo-coordination``
#: §3.3). A set, never a range: a range silently claims a version nobody tested.
#: Adding a version means vendoring and pinning its file (:mod:`rubricator.schema.pins`),
#: which :func:`published_schema_text` and a test hold to this set.
EMITS: frozenset[int] = frozenset({1})

SUPPORTED_SCHEMA_VERSIONS: tuple[int, ...] = tuple(sorted(EMITS))

def published_schema_text(version: int) -> str:
    """The vendored comparanda JSON Schema at ``version``, byte-checked against its pin.

    An unsupported version is refused, listing the versions this build can emit.

    >>> published_schema_text(1)[:1]
    '{'
    >>> published_schema_text(2)
    Traceback (most recent call last):
        ...
    ValueError: no comparanda schema version 2 in this build; it supports 1.
    """
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"no comparanda schema version {version} in this build; "
            f"it supports {', '.join(map(str, SUPPORTED_SCHEMA_VERSIONS))}."
        )
    from rubricator.schema.pins import read_pinned

    return read_pinned(f"comparanda.v{version}.json").decode("utf-8")


SchemaOrigin = Literal["sketch", "published"]

_SKETCH_PATH = Path(__file__).parent / "sketch.json"

#: The companion's published contract, vendored into the wheel. The one place a
#: version is chosen; the composition root and the write-path check both read it.
VENDORED_PATH = Path(__file__).parent / "comparanda" / "comparanda.v1.json"


@dataclass(frozen=True)
class SchemaProblem:
    """One validation failure, in a shape a caller can act on."""

    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.path or '(root)'}: {self.message}"


@dataclass
class SchemaSource:
    """Where the analysis schema comes from, and validation against it.

    ``origin`` is always visible. A caller that has silently been validating
    against a stand-in for six months should be able to find that out by asking,
    and the connector should be able to say so in its output.

    >>> src = SchemaSource.sketch()
    >>> src.origin
    'sketch'
    >>> src.is_provisional
    True
    >>> src.validate({"schemaVersion": 1, "id": "x",
    ...               "subject": {"question": "which?"}}).ok
    True
    """

    #: The JSON Schema document itself.
    schema: dict[str, Any]
    origin: SchemaOrigin
    #: Where it came from, for the record. A path or a URL, never secret.
    located_at: str
    supported_versions: tuple[int, ...] = field(default=SUPPORTED_SCHEMA_VERSIONS)

    @classmethod
    def sketch(cls) -> "SchemaSource":
        """The hand-written stand-in that ships with this package.

        Provisional by construction. It existed so the tool layer could be built
        and tested before the companion repo froze v1, and now serves only as the
        fallback when the vendored contract is missing. **It is not narrower than
        the frozen schema**: the sketch's objects are open where v1's are closed,
        and it still declares ``definition.anchors`` and ``definition.missingRule``,
        which v1 refuses. A document valid here can be refused there -- which is
        why the caveat below is never suppressed.
        """
        return cls(
            schema=json.loads(_SKETCH_PATH.read_text(encoding="utf-8")),
            origin="sketch",
            located_at=str(_SKETCH_PATH.name),
        )

    @classmethod
    def published(cls, path_or_schema: str | Path | dict[str, Any]) -> "SchemaSource":
        """The companion repository's published JSON Schema artifact.

        Takes a path or an already-parsed document rather than a URL: fetching is
        not this package's job, and a tool that reaches the network to validate
        would not work offline in the connector.
        """
        if isinstance(path_or_schema, dict):
            return cls(schema=path_or_schema, origin="published", located_at="(in memory)")
        p = Path(path_or_schema)
        return cls(
            schema=json.loads(p.read_text(encoding="utf-8")),
            origin="published",
            located_at=p.name,
        )

    @classmethod
    def vendored(cls) -> "SchemaSource":
        """The vendored published contract, parsed once per process.

        Shared rather than re-read, because the tool layer checks every write
        against it (#136) and a write should not cost a parse of the whole schema.
        """
        return _vendored()

    @property
    def is_provisional(self) -> bool:
        """True while validating against the sketch rather than the real contract."""
        return self.origin == "sketch"

    def caveat(self) -> str | None:
        """A line to show the user when validation is against a stand-in.

        Returns ``None`` once the published artifact is in use, so a caller can
        surface it unconditionally without special-casing.
        """
        if not self.is_provisional:
            return None
        return (
            "Validated against a provisional local sketch of the analysis schema, not the "
            "published contract. A document that passes here may still be rejected by the "
            "renderer."
        )

    @cached_property
    def _validator(self) -> Any:
        # Imported lazily and by name so that importing this module -- and so the
        # whole tool layer -- does not require jsonschema to be installed for
        # callers who only need the non-validating tools.
        from jsonschema import Draft202012Validator

        return Draft202012Validator(self.schema)

    def refusals(self, value: Any, *, pointer: str = "", root: str = "$") -> list[str]:
        """Every way ``value`` breaks the schema at ``pointer``, as readable lines.

        ``pointer`` is a JSON Pointer into the schema (``/properties/cells``), so
        a fragment -- one contributor's cells, say -- is checked against exactly
        the shape it will occupy in the document. ``root`` is how the fragment's
        own location is spelled in the lines, so the caller can say where the
        problem is in what *it* passed. An empty list means the value fits.

        >>> src = SchemaSource.vendored()
        >>> src.refusals([{"id": "x", "label": "X", "url": "u"}],
        ...              pointer="/properties/alternatives", root="$.alternatives")
        ["at $.alternatives[0]: Additional properties are not allowed ('url' was unexpected). Allowed here: description, groupIds, id, label, supersededBy, tombstoned"]
        """
        return [line for line, _ in self.identified_refusals(value, pointer=pointer, root=root)]

    def identified_refusals(
        self, value: Any, *, pointer: str = "", root: str = "$"
    ) -> list[tuple[str, str]]:
        """:meth:`refusals`, each paired with an identity that survives a move.

        The identity is the problem's *content* -- the rule broken, the path
        with its indices dropped, and the offending value -- so one problem is
        recognised as the same problem after a list around it was reordered,
        and a new value breaking the same rule at the same place is not.
        """
        import json

        validator = self._fragment_validator(pointer)
        errors = sorted(validator.iter_errors(value), key=lambda e: [str(p) for p in e.path])
        return [
            (
                explain(e, root=root),
                json.dumps(
                    [[p for p in e.absolute_path if not isinstance(p, int)], e.validator,
                     e.message, e.instance],
                    sort_keys=True, default=repr,
                ),
            )
            for e in errors
        ]

    def unknown_keys(self, value: Any, *, pointer: str = "") -> list[tuple[tuple[Any, ...], str]]:
        """Each key a closed object in ``value`` does not allow, as ``(path, key)``.

        Only the objects the schema closes outright: a key refused inside an
        ``anyOf`` branch is not named, because which branch the value meant is
        a judgement, not a lookup. :meth:`refusals` still reports it.

        >>> SchemaSource.vendored().unknown_keys(
        ...     [{"id": "x", "label": "X", "url": "u"}], pointer="/properties/alternatives")
        [((0,), 'url')]
        """
        validator = self._fragment_validator(pointer)
        found = {
            (tuple(e.path), key)
            for e in validator.iter_errors(value)
            if e.validator == "additionalProperties" and isinstance(e.instance, dict)
            for key in e.instance
            if key not in e.schema.get("properties", {})
            and not any(re.search(p, key) for p in e.schema.get("patternProperties", {}))
        }
        return sorted(found, key=repr)

    def _fragment_validator(self, pointer: str) -> Any:
        # Evolved from the whole-schema validator rather than built on the bare
        # node, so a ``$ref`` inside the fragment (``#/$defs/author``) still
        # resolves against the document it was written in.
        cache = self.__dict__.setdefault("_fragments", {})
        if pointer not in cache:
            node: Any = self.schema
            for part in filter(None, pointer.split("/")):
                node = node[part.replace("~1", "/").replace("~0", "~")]
            cache[pointer] = self._validator.evolve(schema=node)
        return cache[pointer]

    def validate(self, document: Any) -> "ValidationResult":
        """Validate a document, returning every problem rather than the first.

        A caller fixing an agent's output wants the whole list in one pass; an
        exception on the first failure turns one round-trip into five.
        """
        problems = [
            SchemaProblem(
                path=".".join(str(p) for p in err.absolute_path),
                message=err.message,
            )
            for err in sorted(self._validator.iter_errors(document), key=str)
        ]
        version = document.get("schemaVersion") if isinstance(document, dict) else None
        if isinstance(version, int) and version not in self.supported_versions:
            problems.append(
                SchemaProblem(
                    path="schemaVersion",
                    message=(
                        f"document declares schema version {version}; this build supports "
                        f"{', '.join(map(str, self.supported_versions))}"
                    ),
                )
            )
        return ValidationResult(ok=not problems, problems=tuple(problems), source=self)


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating one document."""

    ok: bool
    problems: tuple[SchemaProblem, ...]
    source: SchemaSource

    def __bool__(self) -> bool:
        return self.ok

    def report(self) -> str:
        """A human-readable summary, carrying the provisional caveat if it applies."""
        lines: list[str] = []
        if self.ok:
            lines.append("valid")
        else:
            lines.append(f"{len(self.problems)} validation problem(s):")
            lines.extend(f"  {p}" for p in self.problems)
        caveat = self.source.caveat()
        if caveat:
            lines.append(f"note: {caveat}")
        return "\n".join(lines)


def explain(error: Any, *, root: str = "$") -> str:
    """One ``jsonschema`` error as a line a caller can act on: where, what, and the fix.

    For an unknown key the fix is the list of keys that *are* allowed there --
    the one thing a model that invented a key needs to correct itself.
    """
    path = root + "".join(
        f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path
    )
    line = f"at {path}: {error.message}"
    properties = error.schema.get("properties") if isinstance(error.schema, dict) else None
    if error.validator == "additionalProperties" and properties:
        line += f". Allowed here: {', '.join(sorted(properties))}"
    return line


@lru_cache(maxsize=None)
def vendored_schema(version: int) -> SchemaSource:
    """The vendored contract at one emittable ``version``, parsed once per process."""
    return SchemaSource(
        schema=json.loads(published_schema_text(version)),
        origin="published",
        located_at=f"comparanda.v{version}.json",
        supported_versions=(version,),
    )


def _vendored() -> SchemaSource:
    return vendored_schema(1)


def emit_version(document: dict[str, Any]) -> int:
    """The lowest emittable version whose schema expresses ``document``.

    Lowest, never newest: a document that uses nothing a later version added is
    readable by the widest set of companion builds (§3.3). The document is judged
    as it would be emitted at that version, so its own ``schemaVersion`` is
    replaced, not trusted. Pure: vendored files only, no network.

    >>> emit_version({"id": "x", "subject": {"question": "which?"}})
    1
    >>> emit_version({"id": "x", "subject": {"question": "which?"}, "bogus": 1})
    Traceback (most recent call last):
        ...
    ValueError: no emittable schema version (1) expresses this document; against 1: $: Additional properties are not allowed ('bogus' was unexpected)
    """
    refused: list[str] = []
    for version in sorted(EMITS):
        found = vendored_schema(version).validate({**document, "schemaVersion": version})
        if found.ok:
            return version
        refused.append(f"against {version}: " + "; ".join(f"{p.path or '$'}: {p.message}" for p in found.problems[:3]))
    raise ValueError(
        f"no emittable schema version ({', '.join(map(str, sorted(EMITS)))}) expresses this document; "
        + " | ".join(refused)
    )


def iter_problems(results: Iterable[ValidationResult]) -> list[SchemaProblem]:
    """Flatten problems across several documents, preserving order."""
    return [p for r in results for p in r.problems]
