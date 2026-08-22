"""The connector: the same verbs, over MCP.

Built with ``py2mcp`` from the one registry in :mod:`rubricator.surface`, so the
CLI and the connector cannot expose different sets. That is not tidiness: an
in-house post-mortem in this ecosystem found twelve handlers across eight
capability families out of step between two surfaces that claimed to "stay
aligned by construction", and the verdict was that by construction was not a
mechanism -- no test, no shared registry, no codegen. This is the shared
registry.

**No model access anywhere in this path.** The connector's intelligence is the
caller's model, reading prompts and calling these verbs; the verbs themselves
are deterministic and would run with no API key at all (ADR-0003). That is the
whole reason the tool layer is denied a model client by a test.
"""

from __future__ import annotations

from typing import Any

from rubricator.compose import Runtime, build_runtime
from rubricator.surface import bind

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


def make_server(runtime: Runtime | None = None, **kwargs: Any):
    """Build the MCP server over the bound verbs.

    ``runtime`` is the seam: pass one built against a GitHub-backed store and the
    connector serves a shared team repository instead of a local directory, with
    no handler changing.
    """
    from py2mcp import mk_mcp_server

    runtime = runtime or build_runtime(**kwargs)
    return mk_mcp_server(
        list(bind(runtime).values()),
        name="rubricator",
        instructions=_INSTRUCTIONS,
    )


def main() -> None:  # pragma: no cover - process entry point
    """Serve over stdio, which is how a desktop client attaches."""
    import argparse

    parser = argparse.ArgumentParser(prog="rubricator-mcp")
    parser.add_argument("--root", default=None, help="directory to store analyses in")
    args = parser.parse_args()
    make_server(root=args.root).run()
