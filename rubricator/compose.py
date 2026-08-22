"""The composition root: where the seams are wired, and the only place they are.

Three seams, each **one keyword argument** with a default that genuinely works:

===============  ==============================================  =========================
seam             v1 default (no new dependency)                  replacement to point at
===============  ==============================================  =========================
``blobs``        ``dol.Files(root)`` over a local directory      a GitHub-backed store, so
                                                                 a team shares one repo
``now``          :func:`rubricator.clock.system_clock`           a fixed clock, for a
                                                                 reproducible fixture
``schema``       the vendored published contract                 a newer published version
===============  ==============================================  =========================

**Not seams, on purpose.** The scale table, the missingness vocabulary and the
reduction table are *data* -- rows in a frozen mapping and rows in the document
-- not keyword arguments. A criterion's scale travels inside the analysis so that
a reader who never heard of it can still degrade honestly, and building them as
interfaces would buy indirection over data the document already carries.

**Model access is not a seam either**, and that is the architectural rule rather
than a scoping decision: no tool may call a model at all, because the connector
runtime has no API key. Where a step needs judgement it is a prompt the caller's
model runs plus a deterministic verb that validates the result (ADR-0003).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rubricator.clock import Clock, system_clock
from rubricator.schema.source import SchemaSource
from rubricator.store import AnalysisStore, BytesStore, file_store, memory_store

__all__ = ["Runtime", "build_runtime"]

#: The vendored published contract, relative to the schema package. Named here
#: so the composition root reads as one place where a version is chosen.
_PUBLISHED = "comparanda/comparanda.v1.json"


@dataclass(frozen=True)
class Runtime:
    """Everything the verbs need, wired once."""

    store: AnalysisStore
    now: Clock
    schema: SchemaSource

    def caveat(self) -> str | None:
        """Whatever the user should be told about this configuration.

        Currently only the provisional-schema warning. It exists as a method
        rather than as something a caller assembles so that a new caveat reaches
        every surface at once.
        """
        return self.schema.caveat()


def build_runtime(
    *,
    root: str | None = None,
    blobs: BytesStore | None = None,
    now: Clock = system_clock,
    schema: SchemaSource | None = None,
) -> Runtime:
    """Wire a runtime.

    ``root`` is the convenience for the common case -- a directory on disk.
    ``blobs`` is the seam underneath it, and passing one wins: it is how a
    GitHub-backed store, an in-memory store or anything else a ``dol`` decorator
    produces gets in without a call site changing.

    >>> rt = build_runtime(blobs={}, now=lambda: '2026-08-22T12:00:00Z')
    >>> rt.now()
    '2026-08-22T12:00:00Z'
    >>> rt.schema.origin
    'published'
    >>> rt.caveat() is None
    True
    """
    if blobs is None:
        blobs = file_store(root) if root else memory_store()
    if schema is None:
        schema = _published_schema()
    return Runtime(store=AnalysisStore(blobs=blobs), now=now, schema=schema)


def _published_schema() -> SchemaSource:
    """The vendored contract, or the sketch if it is somehow absent.

    The fallback is deliberate and is *not* silent: ``SchemaSource.origin`` says
    which one is in use and ``caveat()`` returns a line for the user, so a build
    that has quietly been validating against a stand-in can be found out by
    asking rather than by noticing a bug months later.
    """
    from pathlib import Path

    import rubricator.schema as schema_pkg

    path = Path(schema_pkg.__file__).parent / _PUBLISHED
    if path.exists():
        return SchemaSource.published(path)
    return SchemaSource.sketch()


def _describe(value: Any) -> str:  # pragma: no cover - display only
    return getattr(value, "__name__", type(value).__name__)
