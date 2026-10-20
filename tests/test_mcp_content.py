"""Prompts as native MCP prompts and the document and span resources, end to end (#80)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("py2mcp")

from rubricator.compose import build_runtime
from rubricator.mcp.server import make_server
from rubricator.prompts import prompts

TEXT = "Alpha is fast. Beta is cheap. Gamma is neither."




def _run(coro):
    return asyncio.run(coro)


def _runtime_with_corpus():
    from rubricator.surface import bind

    runtime = build_runtime(blobs={})
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which?")
    added = verbs["corpus_add"](analysis_id="a1", sources=[{"text": TEXT, "title": "t", "agentProduced": False}])
    return runtime, added


def test_every_prompt_file_is_served_with_its_body_unchanged():
    runtime, _ = _runtime_with_corpus()
    server = make_server(runtime)
    listed = {p.name for p in _run(server.list_prompts())}
    assert listed == set(prompts())
    for pid, prompt in prompts().items():
        rendered = _run(server.render_prompt(pid))
        assert rendered.messages[0].content.text == prompt.body


def test_the_span_resource_resolves_a_stored_span_to_its_exact_text():
    runtime, added = _runtime_with_corpus()
    server = make_server(runtime)
    doc = added["documents"][0]["documentId"] if "documents" in added else None
    assert doc
    records = runtime.store.corpus_records("a1")[doc]["ingest"]["spans"]
    s = records[0]
    uri = f"rubricator://analysis/a1/span/{doc}:{s['start']}-{s['end']}"
    got = _run(server.read_resource(uri))
    assert got.contents[0].content == TEXT[s["start"] : s["end"]]
    assert got.contents[0].meta["documentId"] == doc
    full = _run(server.read_resource(f"rubricator://analysis/a1/document/{doc}"))
    assert full.contents[0].content == TEXT


def test_a_span_that_was_not_stored_is_refused_not_rounded():
    runtime, added = _runtime_with_corpus()
    server = make_server(runtime)
    doc = added["documents"][0]["documentId"]
    with pytest.raises(Exception, match="not a stored span"):
        _run(server.read_resource(f"rubricator://analysis/a1/span/{doc}:1-5"))
    with pytest.raises(Exception, match="no document"):
        _run(server.read_resource("rubricator://analysis/a1/span/doc-nope:0-5"))
    with pytest.raises(Exception, match="no analysis"):
        _run(server.read_resource("rubricator://analysis/zzz/span/doc-x:0-5"))


def _read(server, uri):
    return _run(server.read_resource(uri)).contents[0]


def test_every_frozen_resource_is_implemented_and_listed_over_the_server():
    from rubricator.surface import FROZEN_RESOURCES

    runtime, _ = _runtime_with_corpus()
    server = make_server(runtime)
    listed = {r.name for r in _run(server.list_resources())} | {t.name for t in _run(server.list_resource_templates())}
    assert all(r.status == "implemented" for r in FROZEN_RESOURCES)
    assert listed == {r.name for r in FROZEN_RESOURCES}


def test_method_and_rubric_are_the_shipped_files():
    from rubricator.mcp.resolve import read_shipped

    server = make_server(_runtime_with_corpus()[0])
    assert _read(server, "rubricator://method").content == read_shipped("method")
    assert "`high`" in _read(server, "rubricator://confidence-rubric").content


def test_missingness_codes_are_the_manifest_core_with_their_flags():
    import json

    server = make_server(_runtime_with_corpus()[0])
    body = json.loads(_read(server, "rubricator://missingness-codes").content)
    by = {c["code"]: c for c in body["codes"]}
    assert set(by) == {"not-applicable", "not-assessed", "deferred", "not-evidenced", "indeterminate", "withheld"}
    assert by["withheld"]["terminal"] and not by["withheld"]["informative"]


def test_the_schema_is_served_by_version_and_an_unsupported_one_is_refused():
    import json

    from rubricator.schema.source import published_schema_text

    server = make_server(_runtime_with_corpus()[0])
    assert _read(server, "rubricator://schema/comparanda/1").content == published_schema_text(1)
    json.loads(published_schema_text(1))
    for bad in ("2", "x"):
        with pytest.raises(Exception, match="supports 1|whole number"):
            _read(server, f"rubricator://schema/comparanda/{bad}")


def test_the_analyses_list_names_each_analysis_and_an_empty_store_is_an_empty_list():
    import json

    runtime, _ = _runtime_with_corpus()
    server = make_server(runtime)
    rows = json.loads(_read(server, "rubricator://analyses").content)["analyses"]
    assert [(r["id"], r["question"], r["stage"]) for r in rows] == [("a1", "which?", 1)]
    empty = make_server(build_runtime(blobs={}))
    assert json.loads(_read(empty, "rubricator://analyses").content) == {"analyses": []}
