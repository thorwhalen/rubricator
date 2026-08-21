"""The boundary with the companion repository's published schema.

`rubricator` depends on `comparanda` for the analysis schema and validates at the
boundary (ADR-0002). The dependency never runs the other way.

**Why this facade exists at all.** The companion repo's schema is still being
frozen, and the BRIEF anticipates exactly this: build against the domain model
and a hand-written sketch until the real one lands. The danger is that the sketch
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
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Iterable, Literal

__all__ = ["SchemaSource", "SchemaProblem", "SUPPORTED_SCHEMA_VERSIONS", "SchemaOrigin"]

#: The schema versions this build can read and emit. Declared, not inferred, so
#: a consumer can check compatibility before handing us a document.
SUPPORTED_SCHEMA_VERSIONS: tuple[int, ...] = (1,)

SchemaOrigin = Literal["sketch", "published"]

_SKETCH_PATH = Path(__file__).parent / "sketch.json"


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

        Provisional by construction. It exists so the tool layer can be built and
        tested before the companion repo freezes v1, and it is deliberately
        *narrower* than the real schema will be: it asserts only what this
        package actually relies on, so that a document valid here has a good
        chance of being valid there, and never the reverse.
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


def iter_problems(results: Iterable[ValidationResult]) -> list[SchemaProblem]:
    """Flatten problems across several documents, preserving order."""
    return [p for r in results for p in r.problems]
