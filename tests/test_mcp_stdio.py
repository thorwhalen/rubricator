"""The connector as a process: stdio, the listed surface, and what installing it pulls in (#78).

``test_frozen_surface`` checks the server object in-process. These tests start
the real entry point as a child process and talk to it as a desktop client does,
because the failures that matter here -- a banner on stdout corrupting the
protocol, an entry point that imports and then exits, a console script that
points nowhere -- are invisible in-process.
"""

from __future__ import annotations

import asyncio
import importlib.metadata as md
import re
import sys

import pytest

pytest.importorskip("py2mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from packaging.requirements import Requirement  # noqa: E402

from rubricator.surface import advertised, describe  # noqa: E402


def _params(root) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "rubricator.mcp", "--root", str(root)],
    )


async def _session_roundtrip(root):
    async with stdio_client(_params(root)) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            templates = (await session.list_resource_templates()).resourceTemplates
            opened = await session.call_tool(
                "analysis_open", {"analysis_id": "a1", "question": "which tool?"}
            )
            return init, tools, templates, opened


@pytest.fixture(scope="module")
def roundtrip(tmp_path_factory):
    return asyncio.run(asyncio.wait_for(_session_roundtrip(tmp_path_factory.mktemp("store")), 60))


def test_the_server_starts_over_stdio_and_names_itself(roundtrip) -> None:
    init, *_ = roundtrip
    assert init.serverInfo.name == "rubricator"
    assert init.instructions and "qualified blank" in init.instructions


def test_the_listed_surface_is_the_frozen_rows_over_the_wire(roundtrip) -> None:
    _, tools, *_ = roundtrip
    rows = {spec.name: spec for spec in advertised()}
    assert {t.name for t in tools} == set(rows)
    for tool in tools:
        spec = rows[tool.name]
        assert tool.inputSchema == spec.input_schema, tool.name
        assert tool.outputSchema == spec.output_schema, tool.name
        assert tool.description == describe(spec), tool.name


def test_the_analysis_resource_is_listed(roundtrip) -> None:
    _, _, templates, _ = roundtrip
    assert [t.name for t in templates] == ["analysis"]


def test_a_call_round_trips_summary_beside_structured_content(roundtrip) -> None:
    *_, opened = roundtrip
    assert not opened.isError
    assert opened.structuredContent["analysisId"] == "a1"
    assert opened.content[0].text == opened.structuredContent["summary"]


# --- installing the connector pulls no model client (ADR-0003, ADR-0019) ------

#: Distribution names, not module names: what `pip install rubricator[mcp]`
#: would bring, whether or not it is imported. `test_determinism_boundary`
#: covers what the connector imports; this covers what it installs.
MODEL_DISTRIBUTIONS = {
    "aix", "oa", "openai", "anthropic", "litellm", "cohere", "mistralai", "ollama",
    "google-genai", "google-generativeai", "google-ai-generativelanguage",
    "transformers", "sentence-transformers", "tiktoken", "langchain", "langchain-core",
}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _closure(name: str, extras: frozenset[str] = frozenset()) -> set[str]:
    """Every distribution reachable from ``name`` under ``extras``, markers evaluated."""
    seen: set[str] = set()
    todo = [(_norm(name), extras)]
    while todo:
        dist_name, wanted = todo.pop()
        try:
            dist = md.distribution(dist_name)
        except md.PackageNotFoundError:
            continue
        seen.add(dist_name)
        for line in dist.requires or []:
            req = Requirement(line)
            env_extras = wanted or {""}
            if req.marker is not None and not any(
                req.marker.evaluate({"extra": e}) for e in env_extras
            ):
                continue
            key = _norm(req.name)
            if key not in seen or req.extras:
                todo.append((key, frozenset(req.extras)))
                seen.add(key)
    return seen


def test_the_connector_extra_installs_no_model_client() -> None:
    assert md.distribution("rubricator").requires, "rubricator metadata not installed"
    pulled = _closure("rubricator", frozenset({"mcp"}))
    assert {"fastmcp", "py2mcp", "mcp"} <= pulled, "the closure walk missed the connector"
    assert not pulled & MODEL_DISTRIBUTIONS, (
        f"`rubricator[mcp]` would install {sorted(pulled & MODEL_DISTRIBUTIONS)}. ADR-0003: the "
        "connector has no API key; ADR-0019: model access lives in the `agent` extra only."
    )


def test_the_base_install_installs_no_model_client() -> None:
    assert not _closure("rubricator") & MODEL_DISTRIBUTIONS


def test_the_console_script_points_at_the_entry_point() -> None:
    tomllib = pytest.importorskip("tomllib")  # 3.11+; the script table is plain data
    from pathlib import Path

    import rubricator
    from rubricator.mcp import server

    pyproject = Path(rubricator.__file__).parent.parent / "pyproject.toml"
    if not pyproject.exists():  # an installed wheel has no pyproject beside it
        pytest.skip("source tree only")
    scripts = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts["rubricator-mcp"] == "rubricator.mcp.server:main"
    assert callable(server.main)
