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
import json
import re
import subprocess
import sys
import threading

import pytest
from packaging.requirements import Requirement

from rubricator.surface import advertised, describe

# The process tests need the connector extra; the dependency tests at the bottom
# do not, and run in the bare job too.


def _argv(root) -> list[str]:
    return [sys.executable, "-m", "rubricator.mcp", "--root", str(root)]


async def _session_roundtrip(root, errlog):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=_argv(root)[1:])
    # A file, not sys.stderr: under `pytest --capture=sys` sys.stderr has no
    # fileno, and the child's stderr is the only clue when it dies at start-up.
    async with stdio_client(params, errlog=errlog) as (read, write):
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
    pytest.importorskip("py2mcp")
    work = tmp_path_factory.mktemp("store")
    with open(work / "stderr.log", "w+") as errlog:
        try:
            return asyncio.run(asyncio.wait_for(_session_roundtrip(work, errlog), 60))
        except BaseException as exc:
            errlog.seek(0)
            raise AssertionError(f"the server did not answer: {exc!r}\n{errlog.read()}") from exc


def test_stdout_carries_only_protocol_messages(tmp_path) -> None:
    """The MCP client logs and drops a stray stdout line, so the client tests above
    cannot see a banner or a print: read the raw bytes instead."""
    pytest.importorskip("py2mcp")
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "analysis_open", "arguments": {"analysis_id": "a1", "question": "q"}}},
    ]
    # Close stdin only after the last reply: EOF ends the session, and a call
    # still in flight at that moment is dropped.
    proc = subprocess.Popen(
        _argv(tmp_path), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    )
    watchdog = threading.Timer(60, proc.kill)  # a hung server must not hang the suite
    watchdog.start()
    try:
        proc.stdin.write("".join(json.dumps(m) + "\n" for m in messages))
        proc.stdin.flush()
        lines = []
        while not any(json.loads(line).get("id") == 3 for line in lines):
            line = proc.stdout.readline()
            assert line, "the server closed stdout before answering the call"
            lines.append(line)
    finally:
        watchdog.cancel()
        proc.kill()
        proc.communicate()
    for line in lines:
        reply = json.loads(line)  # a banner or a print is not JSON
        assert reply.get("jsonrpc") == "2.0", line


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
    assert {t.name for t in templates} == {"analysis", "document", "span", "comparanda-schema"}


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
    """Every distribution reachable from ``name`` under ``extras``, markers evaluated.

    A requirement that applies but is not installed would cut the walk short
    silently, so it is an error: a closure that stops early proves nothing.
    """
    seen: set[str] = set()
    missing: list[str] = []
    todo = [(_norm(name), extras)]
    while todo:
        dist_name, wanted = todo.pop()
        try:
            dist = md.distribution(dist_name)
        except md.PackageNotFoundError:
            missing.append(dist_name)
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
    seen -= set(missing)
    assert not missing, f"cannot walk the install closure: {sorted(set(missing))} not installed"
    return seen


def test_the_connector_extra_installs_no_model_client() -> None:
    pytest.importorskip("py2mcp")
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
    installed = md.entry_points(group="console_scripts", name="rubricator-mcp")
    if not installed:
        pytest.skip("installed metadata predates the script: reinstall to check it")
    assert {e.value for e in installed} == {"rubricator.mcp.server:main"}
