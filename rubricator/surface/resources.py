"""The frozen resource surface (ADR-0026, #66): eight resources, as data.

The allocation rule is the one ADR-0003 states: **if the model decides to fetch
it, it is a tool; if the user or the host decides to surface it, it is a
resource.** That is why there is no ``analysis_list`` tool: the host lists, the
model does not browse (``DELIBERATELY_ABSENT`` in :mod:`rubricator.surface.frozen`).

Like :mod:`rubricator.surface.frozen`, this module is **data** and fixes the
contract only; serving the resources is #80. Each row has a URI template, a
media type, an audience, a priority and the reason it is a resource. Names and
URI templates are frozen (changing one is an amendment to ADR-0026); the
description may be reworded.

``audience`` and ``priority`` are MCP's resource annotations: ``assistant``
means the host should offer the content to the model (the method, the rubric,
the codes the model must score with), ``user`` that it is for the person to
browse and ``@``-mention. Priority is 0..1, 1 meaning effectively required.

The span resource is the one that earns its keep. It makes the evidence
references in an analysis **resolvable URIs**, which is what comparanda's
host-supplied evidence resolver needs. It resolves to the exact stored span, as
decided in #50: a span indexes into the document's *persisted normalised
rendition*, never into the original, so the URI names text that cannot have
moved since the quote was checked. A span id is ``{start}-{end}``: the
``[start, end)`` character offsets of the stored span in the rendition's
``content`` (:mod:`rubricator.tools.corpus`), self-describing and stable
because stored spans are never re-chunked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Mapping

__all__ = ["ResourceSpec", "FROZEN_RESOURCES", "RESOURCE_URIS", "frozen_resources", "match_resource", "span_id", "parse_span_id"]

Audience = Literal["assistant", "user"]
Status = Literal["implemented", "planned"]

JSON = "application/json"
MARKDOWN = "text/markdown"


@dataclass(frozen=True)
class ResourceSpec:
    """One row of the frozen resource surface."""

    name: str
    #: RFC 6570 level-1 template: ``{variable}`` only, so a client can match it without a library.
    uri_template: str
    mime_type: str
    #: Who the content is for (MCP annotation); a resource may have several.
    audience: tuple[Audience, ...]
    #: MCP annotation, 0..1.
    priority: float
    #: What it is and what reading it gives; the text a host shows.
    description: str
    #: Why this is a resource and not a tool.
    why_resource: str
    #: What a read of an unknown or unreadable target says.
    failure: str
    status: Status = "planned"
    #: The issue that tracks serving it.
    issue: int | None = 80
    notes: tuple[str, ...] = field(default_factory=tuple)


_UNKNOWN_ANALYSIS = (
    "An unknown or expired analysis id is refused, naming the retention window and the analyses resource."
)

FROZEN_RESOURCES: tuple[ResourceSpec, ...] = (
    ResourceSpec(
        name="method",
        uri_template="rubricator://method",
        mime_type=MARKDOWN,
        audience=("assistant",),
        priority=1.0,
        description="The method in one page: the elicitation stages, the honesty clauses and what each tool is for.",
        why_resource="The host should put it in the model's context before any tool call; the model would not know to fetch it.",
        failure="Cannot fail: it ships in the wheel.",
    ),
    ResourceSpec(
        name="confidence-rubric",
        uri_template="rubricator://confidence-rubric",
        mime_type=MARKDOWN,
        audience=("assistant",),
        priority=0.9,
        description="What each confidence level means, and the two uncertainties it must not blur (ADR-0012).",
        why_resource="Scoring reads it every time; making the model decide to fetch it would make a skipped fetch a silent change of meaning.",
        failure="Cannot fail: it ships in the wheel.",
    ),
    ResourceSpec(
        name="missingness-codes",
        uri_template="rubricator://missingness-codes",
        mime_type=JSON,
        audience=("assistant",),
        priority=0.9,
        description="The closed vocabulary of reasons a cell is blank, with the meaning of each, including the analysis's own extensions.",
        why_resource="A blank without a reason is not allowed; the codes are the vocabulary the model writes in.",
        failure="Cannot fail for the core codes; an extension is read from the analysis, so an unknown analysis id refused as below.",
    ),
    ResourceSpec(
        name="comparanda-schema",
        uri_template="rubricator://schema/comparanda/{version}",
        mime_type=JSON,
        audience=("assistant", "user"),
        priority=0.5,
        description="The comparanda JSON Schema at one version: the contract this server validates every write against.",
        why_resource="The boundary contract is published data, versioned by the companion repo; it is read, never computed.",
        failure="An unsupported version is refused, listing the versions this build can emit.",
    ),
    ResourceSpec(
        name="analyses",
        uri_template="rubricator://analyses",
        mime_type=JSON,
        audience=("user",),
        priority=0.6,
        description="The analyses this server holds: id, question, stage and last change, newest first.",
        why_resource="The host lists, the model does not browse: there is deliberately no analysis_list tool.",
        failure="An empty store is an empty list, not an error.",
    ),
    ResourceSpec(
        name="analysis",
        uri_template="rubricator://analysis/{id}",
        mime_type=JSON,
        audience=("user", "assistant"),
        priority=0.7,
        description="One analysis as a comparanda document: the frame and every contribution, merged, read fresh.",
        why_resource="It is the record (ADR-0017) and can be large; analysis_get view=full returns this link, never the body.",
        failure=_UNKNOWN_ANALYSIS,
        status="implemented",
        notes=("Served since #151; the rest of the surface is #80.",),
    ),
    ResourceSpec(
        name="document",
        uri_template="rubricator://analysis/{id}/document/{document_id}",
        mime_type="text/plain",
        audience=("user", "assistant"),
        priority=0.4,
        description="One corpus document's persisted normalised rendition: the text quotes in this analysis resolve against.",
        why_resource="Evidence is checked by reading the source; a person follows a citation to here.",
        failure=_UNKNOWN_ANALYSIS + " An unknown document id is refused, listing the ids the analysis holds.",
        notes=("The rendition, not the original (#50): the original is named by its locator and hash in the document's metadata.",),
    ),
    ResourceSpec(
        name="span",
        uri_template="rubricator://analysis/{id}/span/{span_id}",
        mime_type="text/plain",
        audience=("user", "assistant"),
        priority=0.8,
        description=(
            "One stored span of a document's normalised rendition, with its document id, offsets, normaliser id and "
            "the original's hash in the content's metadata. A span id is {start}-{end}."
        ),
        why_resource="It makes evidence references resolvable URIs, which is what the companion repo's host-supplied evidence resolver needs.",
        failure=(
            _UNKNOWN_ANALYSIS + " A span id that is not {start}-{end}, or is not a stored span of any document in the analysis, "
            "is refused saying which; it is never rounded to the nearest span."
        ),
        notes=(
            "Resolves to the exact stored text of [start, end) in the rendition (#50 option a); a span in more than "
            "one document is addressed by the document's own resource.",
        ),
    ),
)

#: Every URI template, in the table's order.
RESOURCE_URIS: tuple[str, ...] = tuple(r.uri_template for r in FROZEN_RESOURCES)


def frozen_resources() -> Mapping[str, ResourceSpec]:
    """The rows by name."""
    return {r.name: r for r in FROZEN_RESOURCES}


def _pattern(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(template)) + "$")


_PATTERNS = tuple((r, _pattern(r.uri_template)) for r in FROZEN_RESOURCES)


def match_resource(uri: str) -> tuple[ResourceSpec, dict[str, str]] | None:
    """The row a concrete URI belongs to, and its variables; ``None`` if it is none of the eight.

    >>> row, variables = match_resource("rubricator://analysis/a-1/span/10-42")
    >>> row.name, variables
    ('span', {'id': 'a-1', 'span_id': '10-42'})
    >>> match_resource("rubricator://analysis/a-1")[0].name
    'analysis'
    >>> match_resource("rubricator://nothing") is None
    True
    """
    for row, pattern in _PATTERNS:
        found = pattern.match(uri)
        if found:
            return row, found.groupdict()
    return None


def span_id(start: int, end: int) -> str:
    """The id of the stored span ``[start, end)``.

    >>> span_id(10, 42)
    '10-42'
    """
    return f"{start}-{end}"


def parse_span_id(value: str) -> tuple[int, int]:
    """The offsets a span id names; a malformed one is refused, never repaired.

    >>> parse_span_id("10-42")
    (10, 42)
    >>> parse_span_id("10:42")
    Traceback (most recent call last):
        ...
    ValueError: a span id is {start}-{end}, two whole numbers with start before end; got '10:42'.
    """
    found = re.fullmatch(r"(\d+)-(\d+)", value)
    if found and int(found[1]) < int(found[2]):
        return int(found[1]), int(found[2])
    raise ValueError(f"a span id is {{start}}-{{end}}, two whole numbers with start before end; got {value!r}.")
