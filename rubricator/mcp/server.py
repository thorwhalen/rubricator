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
import os
import sys
from collections.abc import Sequence
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
    for template in _content_resources(runtime):
        server.add_template(template)
    for resource in _fixed_resources(runtime):
        server.add_resource(resource)
    server.add_template(_schema_resource())
    for prompt in _prompts():
        server.add_prompt(prompt)
    return server


def _prompts():
    """Every prompt file as a native MCP prompt: what a client shows as a slash command.

    Read from :func:`rubricator.prompts.prompts` at build time, the one accessor
    both runtimes share, so no prompt text lives in Python and a new ``.md`` file
    is served with no change here. The body is the message; the header is not
    (``Prompt.body``). The version rides in ``meta`` so a run can record which
    wording it was given.
    """
    from fastmcp.prompts import Prompt as McpPrompt

    from rubricator.prompts import prompts

    def serve(prompt):
        def render() -> str:
            return prompt.body

        render.__annotations__ = {"return": str}
        return McpPrompt.from_function(
            render, name=prompt.id, title=prompt.title,
            description=f"{prompt.title} (v{prompt.version}, stage {prompt.stage})"
            if prompt.stage is not None else f"{prompt.title} (v{prompt.version})",
            meta={"version": prompt.version, "stage": prompt.stage, "updated": prompt.updated},
        )

    return [serve(p) for p in prompts().values()]


def _content_resources(runtime: Runtime):
    """The document and span resources: what makes an evidence reference a followable URI."""
    from fastmcp.resources import ResourceContent, ResourceResult, ResourceTemplate

    from rubricator.mcp.resolve import read_document, read_span
    from rubricator.surface.resources import frozen_resources

    rows = frozen_resources()

    def result(found) -> ResourceResult:
        text, meta = found
        return ResourceResult([ResourceContent(text, mime_type="text/plain", meta=meta)])

    # `id` is the template variable the frozen rows name; the host binds by parameter name.
    def document(id: str, document_id: str) -> ResourceResult:
        return result(read_document(runtime.store, id, document_id))

    def span(id: str, span_id: str) -> ResourceResult:
        return result(read_span(runtime.store, id, span_id))

    templates = []
    for fn, row in ((document, rows["document"]), (span, rows["span"])):
        fn.__annotations__ = {**{k: str for k in fn.__code__.co_varnames[: fn.__code__.co_argcount]},
                              "return": ResourceResult}
        templates.append(ResourceTemplate.from_function(
            fn, uri_template=row.uri_template, name=row.name, description=row.description,
            mime_type=row.mime_type,
        ))
    return templates


def _fixed_resources(runtime: Runtime):
    """The resources with no variable in their URI: method, rubric, codes, the analyses list."""
    from fastmcp.resources import Resource, ResourceContent, ResourceResult

    from rubricator.mcp import resolve
    from rubricator.surface.resources import frozen_resources

    rows = frozen_resources()
    readers = {
        "method": lambda: resolve.read_shipped("method"),
        "confidence-rubric": lambda: resolve.read_shipped("confidence-rubric"),
        "missingness-codes": resolve.read_missingness_codes,
        "analyses": lambda: resolve.read_analyses(runtime.store),
    }

    def serve(name: str, read) -> Resource:
        row = rows[name]

        def content() -> ResourceResult:
            return ResourceResult([ResourceContent(read(), mime_type=row.mime_type)])

        content.__annotations__ = {"return": ResourceResult}
        return Resource.from_function(
            content, uri=row.uri_template, name=row.name, description=row.description,
            mime_type=row.mime_type,
            annotations={"audience": list(row.audience), "priority": row.priority},
        )

    return [serve(name, read) for name, read in readers.items()]


def _schema_resource():
    """The published comparanda schema at one version: read, never computed."""
    from fastmcp.resources import ResourceContent, ResourceResult, ResourceTemplate

    from rubricator.mcp.resolve import read_comparanda_schema
    from rubricator.surface.resources import frozen_resources

    row = frozen_resources()["comparanda-schema"]

    def comparanda_schema(version: str) -> ResourceResult:
        return ResourceResult([ResourceContent(read_comparanda_schema(version), mime_type=row.mime_type)])

    comparanda_schema.__annotations__ = {"version": str, "return": ResourceResult}
    return ResourceTemplate.from_function(
        comparanda_schema, uri_template=row.uri_template, name=row.name,
        description=row.description, mime_type=row.mime_type,
    )


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

    def analysis_document(id: str) -> ResourceResult:
        # The mime type is stated on the content, because a template's own
        # mime_type does not reach a function's plain-string result.
        # A file that cannot be merged is left out of the body and named in the
        # content's metadata (#151): the body is a closed comparanda document
        # with no slot for it, and leaving it out silently is not an option.
        document, skipped = runtime.store.read_skipping(id)
        body = json.dumps(document, ensure_ascii=False, sort_keys=True)
        meta = {"skipped": skipped} if skipped else None
        return ResourceResult([ResourceContent(body, mime_type=_JSON, meta=meta)])

    # Concrete, not the postponed strings: the host resolves annotations in this
    # module's globals, where the locally imported names do not exist.
    analysis_document.__annotations__ = {"id": str, "return": ResourceResult}

    return ResourceTemplate.from_function(
        analysis_document,
        uri_template=analysis_uri("{id}"),
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


#: Where the HTTP transport listens unless told otherwise. Loopback, and never
#: anything else by default: the server has no authentication of its own (see
#: ``docs/connector-http.md``), so reachable-by-anyone must be a decision.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PATH = "/mcp"
_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}


def _is_loopback(host: str) -> bool:
    import ipaddress

    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _allowed_hosts(host: str, extra: Sequence[str]) -> list[str] | None:
    """The Host values to accept, or ``None`` to leave the framework's loopback rule.

    On a loopback bind the framework's own rule suffices unless the user adds
    names (a proxy). On any other bind it must be explicit: in ``"auto"`` mode
    the framework checks only connections that arrive on a loopback address, so
    a remote client would otherwise be checked against nothing. The framework
    adds its loopback names to any list it is given.
    """
    if _is_loopback(host):
        return [host, *extra] if extra else None
    return [host, *extra]


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(prog="rubricator-mcp")
    parser.add_argument(
        "--root", default=None,
        help="directory to store analyses in (default: the user-data working store, "
        "moved by RUBRICATOR_DATA_DIR)",
    )
    parser.add_argument(
        "--transport", choices=("stdio", "http"), default="stdio",
        help="stdio (default) is how a desktop client attaches; http serves Streamable HTTP",
    )
    http = parser.add_argument_group(
        "http transport",
        "Only with --transport http. The server has NO authentication: it binds to "
        "loopback unless --allow-remote is given, and a remote bind must sit behind "
        "something that authenticates.",
    )
    http.add_argument("--host", default=DEFAULT_HOST, help=f"address to bind (default {DEFAULT_HOST})")
    http.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    http.add_argument("--path", default=DEFAULT_PATH, help=f"endpoint path (default {DEFAULT_PATH})")
    http.add_argument(
        "--allow-remote", action="store_true",
        help="permit binding a non-loopback address (all analyses become readable and "
        "writable by anyone who can reach the port)",
    )
    http.add_argument(
        "--allow-host", action="append", default=[], metavar="HOSTNAME",
        help="extra Host header value to accept, for a reverse proxy (repeatable)",
    )
    return parser


def _check_args(parser, args) -> None:
    """Refuse, at start-up and in words, what would otherwise fail late or silently."""
    if args.root is not None:
        # An empty value is an unset variable in a client config, which would
        # otherwise fall through to the default store without a word.
        if not args.root.strip():
            parser.error("--root is empty (an unset variable in the client config?)")
        if os.path.exists(args.root) and not os.path.isdir(args.root):
            parser.error(f"--root {args.root!r} exists and is not a directory")
    if args.transport == "stdio":
        return
    if not 0 <= args.port <= 65535:
        parser.error(f"--port {args.port} is not a port")
    if not args.path.startswith("/"):
        parser.error(f"--path {args.path!r} must start with '/'")
    for name in args.allow_host:
        # The framework matches these as globs, so `*` would switch the
        # DNS-rebinding check off without a word.
        if not name.strip() or any(c in name for c in "*?[]"):
            parser.error(f"--allow-host {name!r} must be a plain host name, without wildcards")
    if not _is_loopback(args.host) and not args.allow_remote:
        parser.error(
            f"--host {args.host!r} is not a loopback address and the server has no "
            "authentication. Bind 127.0.0.1 and put an authenticating proxy in front, "
            "or pass --allow-remote to say you have."
        )


def main(argv: Sequence[str] | None = None) -> None:  # pragma: no cover - process entry point
    """Serve over stdio (a desktop client) or Streamable HTTP (a connector).

    Both transports run the one server :func:`make_server` builds, so the
    surface cannot differ between them. stdout is the protocol channel under
    stdio, so nothing else may write to it: the framework's start-up banner is
    switched off, and diagnostics go to stderr.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    _check_args(parser, args)
    server = make_server(root=args.root)
    if args.transport == "stdio":
        server.run(transport="stdio", show_banner=False)
        return
    if not _is_loopback(args.host):
        print(
            f"rubricator-mcp: serving on {args.host}:{args.port} with NO authentication",
            file=sys.stderr,
        )
    server.run(
        transport="http", show_banner=False, host=args.host, port=args.port, path=args.path,
        # "auto" validates Host and Origin on a loopback bind (the DNS-rebinding
        # defence: a web page the user visits cannot drive a local server) and
        # on an explicit allowlist; the framework default is off.
        host_origin_protection="auto",
        allowed_hosts=_allowed_hosts(args.host, args.allow_host),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
