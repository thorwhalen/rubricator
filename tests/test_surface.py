"""One registry, two surfaces, and the store never crosses the JSON boundary.

The failure this file exists to prevent has an in-house post-mortem: two
surfaces claimed to "stay aligned by construction", and the verdict when they
drifted was that by construction was not a mechanism -- no test, no shared
registry, no codegen. There is one registry here, and these are the mechanisms.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from rubricator.compose import build_runtime
from rubricator.surface import NEEDS_CLOCK, TOOL_REFS, bind


@pytest.fixture()
def verbs():
    return bind(build_runtime(blobs={}, now=lambda: "2026-08-22T12:00:00Z"))


def test_every_ref_resolves_and_is_exposed_once(verbs) -> None:
    assert len(verbs) == len(TOOL_REFS)
    assert len(set(TOOL_REFS)) == len(TOOL_REFS)


def test_no_bound_verb_advertises_the_store(verbs) -> None:
    """The seam must not reach the wire.

    A `functools.partial` still reports the parameter it bound, so a surface
    built from partials advertises `store` as something a caller supplies -- and
    a caller that obliged would be handing a Mapping across a JSON boundary.
    This assertion fails against that implementation.
    """
    for name, fn in verbs.items():
        params = set(inspect.signature(fn).parameters)
        assert "store" not in params, f"{name} advertises the store"


def test_the_clock_is_optional_where_it_is_bound(verbs) -> None:
    """Bound, but not removed: a replay may state the moment it reconstructs."""
    for name in NEEDS_CLOCK:
        at = inspect.signature(verbs[name]).parameters["at"]
        assert at.default is None, f"{name}.at should default to the runtime clock"


def test_a_bound_verb_runs_without_a_moment(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which?")
    verbs["frame_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](
        analysis_id="a1",
        criteria=[{"id": "c", "label": "C", "anchors": {"1": "a", "3": "b", "5": "c"}}],
    )
    result = verbs["measures_write"](
        analysis_id="a1", contributor_id="ana",
        author={"id": "ana", "displayName": "Ana", "kind": "human"},
        cells=[{"alternativeId": "x", "criterionId": "c", "value": 3,
                "justification": "the filing says so"}],
    )
    assert result["written"] == 1


def test_annotations_are_resolved_so_a_host_can_read_them(verbs) -> None:
    """These modules use postponed annotations, so a wrapper must resolve them.

    A closure defined in the surface module carries *its* globals, not the
    defining module's, so a host calling `get_type_hints` fails on the first name
    it cannot evaluate. That failure is at server-construction time and its
    message names a parameter rather than the cause.
    """
    import typing

    for name, fn in verbs.items():
        hints = typing.get_type_hints(fn)
        assert hints, f"{name} exposes no resolvable type hints"


def test_the_mcp_server_builds_over_the_same_registry(verbs) -> None:
    """The connector is the registry plus py2mcp, and nothing else."""
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}))
    tools = asyncio.run(server._list_tools())
    assert {t.name for t in tools} == set(verbs)
    for tool in tools:
        properties = set((tool.parameters or {}).get("properties", {}))
        assert "store" not in properties, f"{tool.name} advertises the store over MCP"
