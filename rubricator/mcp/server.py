"""The connector: the same verbs, over MCP, advertising the frozen contract.

Built on ``py2mcp``'s server from the one registry in :mod:`rubricator.surface`,
so the CLI and the connector cannot expose different sets. That is not
tidiness: an in-house post-mortem in this ecosystem found twelve handlers
across eight capability families out of step between two surfaces that claimed
to "stay aligned by construction", and the verdict was that by construction
was not a mechanism -- no test, no shared registry, no codegen. This is the
shared registry.

**What the model reads is the frozen row, not a derived guess.** A builder
derives an ``inputSchema`` from a Python signature, and a signature cannot say
what ADR-0013 requires -- a ``Mapping[str, Any]`` derives to an open object,
and the subset closes every object. So each tool is registered from its row in
:mod:`rubricator.surface.frozen`: the row's description, ``inputSchema`` and
``outputSchema``, over a wrapper whose parameters are untyped so that the host
coerces nothing before the bound verb validates the raw arguments against the
same row. Every result is the verb's dict as ``structuredContent`` with its
required ``summary`` as the text content.

**No model access anywhere in this path.** The connector's intelligence is the
caller's model, reading prompts and calling these verbs; the verbs themselves
are deterministic and would run with no API key at all (ADR-0003). That is the
whole reason the tool layer is denied a model client by a test.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from rubricator.compose import Runtime, build_runtime
from rubricator.surface import ToolSpec, bind, describe, frozen

__all__ = ["make_server", "main"]

_JSON = "application/json"

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


def make_server(runtime: Runtime | None = None, **kwargs: Any):
    """Build the MCP server over the bound verbs, advertising the frozen rows.

    ``runtime`` is the seam: pass one built against a GitHub-backed store and the
    connector serves a shared team repository instead of a local directory, with
    no handler changing. Safe to call inside a running event loop: nothing here
    awaits.
    """
    from py2mcp import mk_mcp_server

    runtime = runtime or build_runtime(**kwargs)
    server = mk_mcp_server([], name="rubricator", instructions=_INSTRUCTIONS)
    rows = frozen()
    retention_days = runtime.store.retention_days
    for name, verb in bind(runtime).items():
        server.add_tool(_tool_from_row(rows[name], verb, retention_days=retention_days))
    server.add_template(_analysis_resource(runtime))
    return server


def _analysis_resource(runtime: Runtime):
    """The analysis document as a resource: what ``analysis_get view=full`` links to.

    A link nobody can follow is not a link, so the one resource the frozen
    surface already names is served here; the rest of the resource surface is
    #66's. The body is the merged document, read fresh, never cached: it is the
    record (ADR-0017), and a stale copy of a record is a second record.
    """
    import json

    from fastmcp.resources import ResourceContent, ResourceResult, ResourceTemplate

    from rubricator.tools.views import analysis_uri

    def analysis_document(analysis_id: str) -> ResourceResult:
        # The mime type is stated on the content, because a template's own
        # mime_type does not reach a function's plain-string result.
        # A file that cannot be merged is left out of the body and named in the
        # content's metadata (#151): the body is a closed comparanda document
        # with no slot for it, and leaving it out silently is not an option.
        document, skipped = runtime.store.read_skipping(analysis_id)
        body = json.dumps(document, ensure_ascii=False, sort_keys=True)
        meta = {"skipped": skipped} if skipped else None
        return ResourceResult([ResourceContent(body, mime_type=_JSON, meta=meta)])

    # Concrete, not the postponed strings: the host resolves annotations in this
    # module's globals, where the locally imported names do not exist.
    analysis_document.__annotations__ = {"analysis_id": str, "return": ResourceResult}

    return ResourceTemplate.from_function(
        analysis_document,
        uri_template=analysis_uri("{analysis_id}"),
        name="analysis",
        description="One analysis as a comparanda document: the frame and every contribution, merged.",
        mime_type=_JSON,
    )


def _tool_from_row(spec: ToolSpec, verb: Callable[..., Any], *, retention_days: int):
    """One MCP tool: the row's contract over the bound verb.

    The wrapper's parameters carry no annotations and default to ``None``, so
    the host's own argument model accepts exactly the row's parameter names and
    coerces nothing -- a ``"0.5"`` reaches the row validator as a string and is
    refused there with its path, rather than being quietly read as a number.
    ``parameters`` is then replaced with the row's schema, which is what the
    client sees and what a strict-mode model is held to.
    """
    from fastmcp.tools import Tool
    from fastmcp.tools import ToolResult
    from mcp.types import TextContent

    names = list(spec.input_schema["properties"])
    required = set(spec.input_schema["required"])

    def call(**arguments: Any) -> ToolResult:
        result = verb(**{k: v for k, v in arguments.items() if v is not None or k in required})
        return ToolResult(
            content=[TextContent(type="text", text=result["summary"])],
            structured_content=result,
        )

    call.__name__ = spec.name
    # The window the model reads is the window this store keeps (ADR-0017).
    description = describe(spec, retention_days=retention_days)
    call.__doc__ = description
    # Concrete, not the postponed string: the host resolves annotations in the
    # function's module globals, where a locally imported name does not exist.
    call.__annotations__ = {"return": ToolResult}
    call.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter(
                n, inspect.Parameter.KEYWORD_ONLY,
                default=inspect.Parameter.empty if n in required else None,
            )
            for n in names
        ]
    )
    tool = Tool.from_function(
        call, name=spec.name, description=description, output_schema=dict(spec.output_schema)
    )
    tool.parameters = dict(spec.input_schema)
    return tool


def main() -> None:  # pragma: no cover - process entry point
    """Serve over stdio, which is how a desktop client attaches."""
    import argparse

    parser = argparse.ArgumentParser(prog="rubricator-mcp")
    parser.add_argument(
        "--root", default=None,
        help="directory to store analyses in (default: the user-data working store, "
        "moved by RUBRICATOR_DATA_DIR)",
    )
    args = parser.parse_args()
    make_server(root=args.root).run()
