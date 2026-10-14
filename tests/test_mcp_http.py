"""The connector over Streamable HTTP (#79): same surface, loopback by default.

Like ``test_mcp_stdio``, these start the real entry point as a child process,
because what matters is what a client reaches: the listed surface, the address
actually bound, and whether the Host check refuses what it should.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from rubricator.surface import advertised

pytest.importorskip("py2mcp")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _argv(root, *extra: str) -> list[str]:
    return [sys.executable, "-m", "rubricator.mcp", "--root", str(root), *extra]


@contextlib.contextmanager
def _serving(root, *extra: str):
    port = _free_port()
    errlog = open(root / "stderr.log", "w+")
    proc = subprocess.Popen(
        _argv(root, "--transport", "http", "--port", str(port), *extra),
        stdout=subprocess.DEVNULL, stderr=errlog,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                errlog.seek(0)
                raise AssertionError(f"the server exited: {errlog.read()}")
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), 0.2):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("the server never listened")
        yield port
    finally:
        proc.kill()
        proc.wait()
        errlog.close()


async def _roundtrip(url: str):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            templates = (await session.list_resource_templates()).resourceTemplates
            opened = await session.call_tool(
                "analysis_open", {"analysis_id": "a1", "question": "which tool?"}
            )
            return init, tools, templates, opened


@pytest.fixture(scope="module")
def over_http(tmp_path_factory):
    root = tmp_path_factory.mktemp("store")
    with _serving(root) as port:
        return asyncio.run(asyncio.wait_for(_roundtrip(f"http://127.0.0.1:{port}/mcp"), 60))


def test_http_serves_the_same_surface_as_stdio(over_http) -> None:
    init, tools, templates, opened = over_http
    assert init.serverInfo.name == "rubricator"
    rows = {spec.name: spec for spec in advertised()}
    assert {t.name for t in tools} == set(rows)
    for tool in tools:
        assert tool.inputSchema == rows[tool.name].input_schema, tool.name
        assert tool.outputSchema == rows[tool.name].output_schema, tool.name
    assert [t.name for t in templates] == ["analysis"]
    assert not opened.isError and opened.structuredContent["analysisId"] == "a1"


def _post(port: int, host: str | None) -> int:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp", data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    if host is not None:
        request.add_header("Host", host)
    try:
        return urllib.request.urlopen(request, timeout=10).status
    except urllib.error.HTTPError as err:
        return err.code


def test_a_foreign_host_header_is_refused_and_a_local_one_is_not(tmp_path) -> None:
    """The DNS-rebinding guard: a web page the user visits must not drive the server."""
    with _serving(tmp_path) as port:
        assert _post(port, f"evil.example:{port}") == 421
        # The empty body is not a JSON-RPC message, so a request that gets past
        # the guard is answered 400 by the protocol layer, not 421 by the guard.
        assert _post(port, f"127.0.0.1:{port}") == 400
        assert _post(port, f"localhost:{port}") == 400


def test_allow_host_adds_to_the_local_names_for_a_proxy(tmp_path) -> None:
    with _serving(tmp_path, "--allow-host", "proxy.example") as port:
        assert _post(port, f"proxy.example:{port}") == 400
        assert _post(port, f"localhost:{port}") == 400
        assert _post(port, f"evil.example:{port}") == 421


def test_a_remote_bind_always_gets_an_explicit_host_list() -> None:
    """In the framework's "auto" mode a connection arriving on a non-loopback address
    is checked only against an explicit list; None would mean checked against nothing.
    Unit-level, because a test must not itself expose an unauthenticated server."""
    from rubricator.mcp.server import _allowed_hosts

    assert _allowed_hosts("0.0.0.0", []) == ["0.0.0.0"]
    assert _allowed_hosts("::", ["proxy.example"]) == ["::", "proxy.example"]
    assert _allowed_hosts("10.1.2.3", []) == ["10.1.2.3"]
    assert _allowed_hosts("127.0.0.1", []) is None
    assert _allowed_hosts("127.0.0.1", ["p.example"]) == ["127.0.0.1", "p.example"]


@pytest.mark.parametrize("name", ["*", "*.example", "a?b", "[x]", " "])
def test_a_wildcard_allow_host_is_refused(tmp_path, name) -> None:
    done = subprocess.run(
        _argv(tmp_path, "--transport", "http", "--allow-host", name),
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 2 and "plain host name" in done.stderr


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_a_non_loopback_bind_is_refused_without_allow_remote(tmp_path, host) -> None:
    done = subprocess.run(
        _argv(tmp_path, "--transport", "http", "--host", host),
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 2
    assert "no authentication" in done.stderr and "--allow-remote" in done.stderr


def test_a_foreign_origin_is_refused(tmp_path) -> None:
    with _serving(tmp_path) as port:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp", data=b"{}", method="POST",
            headers={"Content-Type": "application/json", "Origin": "https://evil.example",
                     "Accept": "application/json, text/event-stream"},
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(request, timeout=10)
        assert err.value.code == 403


def test_only_loopback_is_bound_by_default(tmp_path) -> None:
    others = _non_loopback_addresses()
    if not others:
        pytest.skip("this host has no non-loopback address to probe")
    with _serving(tmp_path) as port:
        for other in others:
            with pytest.raises(OSError), socket.create_connection((other, port), 0.5):
                pass


def _non_loopback_addresses() -> list[str]:
    found = []
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))  # no packet is sent; this picks the outgoing interface
        found.append(s.getsockname()[0])
    return [a for a in found if not a.startswith("127.")]


@pytest.mark.parametrize("flags, message", [
    (["--port", "70000"], "not a port"),
    (["--path", "mcp"], "must start with"),
])
def test_bad_http_flags_fail_at_start_up(tmp_path, flags, message) -> None:
    done = subprocess.run(
        _argv(tmp_path, "--transport", "http", *flags), capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 2 and message in done.stderr
