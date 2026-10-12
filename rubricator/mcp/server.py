"""The connector: the same verbs, over MCP, advertising the frozen contract.

Built with ``py2mcp`` from the one registry in :mod:`rubricator.surface`, so the
CLI and the connector cannot expose different sets. That is not tidiness: an
in-house post-mortem in this ecosystem found twelve handlers across eight
capability families out of step between two surfaces that claimed to "stay
aligned by construction", and the verdict was that by construction was not a
mechanism -- no test, no shared registry, no codegen. This is the shared
registry.

**What the model reads is the frozen row, not a derived guess.** The builder
derives an ``inputSchema`` from each verb's Python signature, and a signature
cannot say what ADR-0013 requires -- a ``Mapping[str, Any]`` derives to an open
object, and the subset closes every object. So after the builder has done its
work, every tool's ``inputSchema``, ``outputSchema`` and description are
replaced with the row from :mod:`rubricator.surface.frozen`, and the human-
readable content of every result is the row's ``summary`` field. The bound verb
underneath has already validated the call against the same row.

**No model access anywhere in this path.** The connector's intelligence is the
caller's model, reading prompts and calling these verbs; the verbs themselves
are deterministic and would run with no API key at all (ADR-0003). That is the
whole reason the tool layer is denied a model client by a test.
"""

from __future__ import annotations

from typing import Any

from rubricator.compose import Runtime, build_runtime
from rubricator.surface import bind, describe, frozen

__all__ = ["make_server", "main"]

_INSTRUCTIONS = """\
Turns a pile of context into a defensible comparison: alternatives x criteria,
with scores, confidence, justifications and citations back to spans in the
source.

Two rules matter more than the rest, and both are enforced rather than asked for:
prefer a qualified blank to a plausible guess, and cite a span rather than a
document. A blank names WHICH kind it is -- `not-evidenced` when the sources are
silent, `indeterminate` when they conflict, `not-assessed` when nobody has looked
-- because those lead to different next actions and only the first two say
anything about the subject.
"""


def _summary(result: Any) -> str:
    """The human-readable content of a result: its ``summary`` field, verbatim."""
    return result["summary"]


def make_server(runtime: Runtime | None = None, **kwargs: Any):
    """Build the MCP server over the bound verbs, advertising the frozen rows.

    ``runtime`` is the seam: pass one built against a GitHub-backed store and the
    connector serves a shared team repository instead of a local directory, with
    no handler changing.
    """
    from py2mcp import mk_mcp_server

    runtime = runtime or build_runtime(**kwargs)
    server = mk_mcp_server(
        list(bind(runtime).values()),
        name="rubricator",
        instructions=_INSTRUCTIONS,
    )
    _advertise_frozen(server)
    return server


def _advertise_frozen(server: Any) -> None:
    """Replace every derived tool definition with its frozen row.

    Three fields, all from :mod:`rubricator.surface.frozen`: the description the
    model reads, the ``inputSchema`` it is held to, and the ``outputSchema`` the
    server is held to -- plus the serializer that makes ``summary`` the text
    content beside the structured result.
    """
    import asyncio

    rows = frozen()
    for tool in asyncio.run(server._list_tools()):
        spec = rows[tool.name]
        tool.description = describe(spec)
        tool.parameters = dict(spec.input_schema)
        tool.output_schema = dict(spec.output_schema)
        tool.serializer = _summary


def main() -> None:  # pragma: no cover - process entry point
    """Serve over stdio, which is how a desktop client attaches."""
    import argparse

    parser = argparse.ArgumentParser(prog="rubricator-mcp")
    parser.add_argument("--root", default=None, help="directory to store analyses in")
    args = parser.parse_args()
    make_server(root=args.root).run()
