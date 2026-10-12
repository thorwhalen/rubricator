"""The frozen surface (ADR-0026), held against the implementation.

Every row in ``rubricator/surface/frozen.py`` is a promise: a name, an input
signature, an output envelope, a contract. These tests are what makes the
promise cost something to break. A verb whose signature drifts from its row, a
schema that leaves the ADR-0013 subset, a result that misses its envelope, a
name the surface decided against, or a definition whose token cost was never
re-measured all fail here.

ADR-0020's rule applies: a guard is not believed until it has been shown
failing against a deliberate violation, so the subset checker is fed one of
each before it is trusted on the real rows.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ids import sequential_ids
from rubricator.surface import (
    FROZEN_TOOLS,
    NEEDS_CLOCK,
    NEEDS_ID,
    TOOL_REFS,
    ContractViolation,
    advertised,
    bind,
    describe,
    frozen,
    subset_violations,
)
from rubricator.surface.frozen import (
    DELIBERATELY_ABSENT,
    FORBIDDEN_PARAMETERS,
    MEASURED,
    RETENTION_DAYS,
    definitions_bytes,
)

ADR = Path(__file__).resolve().parents[1] / "docs" / "adr" / "0026-the-frozen-tool-surface.md"
MOMENT = "2026-08-22T12:00:00Z"

AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "a"}, {"level": "3", "text": "b"}, {"level": "5", "text": "c"}]


@pytest.fixture()
def verbs():
    return bind(build_runtime(blobs={}, now=fixed_clock(MOMENT), new_id=sequential_ids("a")))


def _open_scored(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which?")
    verbs["frame_set"](analysis_id="a1", ambiguities=["which region?"], decision="adopt one")
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": 3, "justification": "says so"}],
    )


# --- the rows themselves ------------------------------------------------------


@pytest.mark.parametrize("spec", FROZEN_TOOLS, ids=lambda s: s.name)
def test_every_input_and_output_schema_is_in_the_adr_0013_subset(spec) -> None:
    assert subset_violations(spec.input_schema) == [], spec.name
    assert subset_violations(spec.output_schema) == [], spec.name


@pytest.mark.parametrize(
    "violation, schema",
    [
        ("minimum", {"type": "integer", "minimum": 1}),
        ("maxLength", {"type": "string", "maxLength": 3}),
        ("additionalProperties", {"type": "object", "properties": {}}),
        ("not internal", {"$ref": "https://example.invalid/x.json"}),
        ("recursive", {"$defs": {"n": {"type": "object", "additionalProperties": False,
                                        "properties": {"k": {"$ref": "#/$defs/n"}}}},
                       "$ref": "#/$defs/n"}),
        ("minItems", {"type": "array", "items": {"type": "string"}, "minItems": 2}),
        ("scalars", {"enum": [{"a": 1}]}),
        ("prefixItems", {"type": "array", "prefixItems": [{"type": "string"}]}),
        ("oneOf", {"oneOf": [{"type": "string"}]}),
    ],
)
def test_the_subset_checker_catches_each_violation(violation, schema) -> None:
    """ADR-0020: a guard is demonstrated failing before it is believed."""
    found = subset_violations(schema)
    assert found, f"the checker let a {violation} violation through"
    assert any(violation in line for line in found), (violation, found)


#: Pure functions over caller-supplied data keep the research's names, which the
#: ADRs cite verbatim (ADR-0011 `plan_traversal`, ADR-0014 `check_citations`).
#: Everything that acts on a stored analysis is noun-first: family, then verb.
RESEARCH_NAMED = {
    "check_citations", "plan_traversal", "stability_report", "disclose_variance",
    "aggregate_assertions", "compute_coupling_matrix", "fit_bradley_terry",
}


@pytest.mark.parametrize("spec", FROZEN_TOOLS, ids=lambda s: s.name)
def test_every_row_states_its_contract(spec) -> None:
    assert spec.contract and spec.determinism and spec.failure and spec.stage
    if spec.name not in RESEARCH_NAMED:
        assert spec.name.startswith(spec.family + "_"), (
            f"{spec.name} is not noun-first for family {spec.family}"
        )
    assert "summary" in spec.output_schema["required"], f"{spec.name} must return a summary"
    if spec.minimum_viable:
        assert spec.cut_rank is None, f"{spec.name} is minimum viable and cannot have a cut rank"
    else:
        assert isinstance(spec.cut_rank, int), f"{spec.name} is cuttable and needs a cut rank"
    if spec.status != "implemented":
        assert spec.issue, f"{spec.name} is {spec.status} and must name the issue tracking it"


def test_the_surface_is_twenty_tools_plus_two_transitional() -> None:
    by_status = {}
    for spec in FROZEN_TOOLS:
        by_status.setdefault(spec.status, []).append(spec.name)
    assert len(FROZEN_TOOLS) == 22
    assert sorted(by_status["transitional"]) == ["prompts_get", "prompts_list"]
    assert sum(1 for s in FROZEN_TOOLS if s.minimum_viable) == 15
    rows = {s.research_row for s in FROZEN_TOOLS if s.research_row}
    assert rows == set(range(1, 20)), "every one of the research's 19 has a row"


def test_deliberately_absent_names_and_parameters_are_absent() -> None:
    names = {s.name for s in FROZEN_TOOLS} | {ref.partition(":")[2] for ref in TOOL_REFS}
    assert not names & set(DELIBERATELY_ABSENT)
    for spec in FROZEN_TOOLS:
        params = set(spec.input_schema["properties"])
        assert not params & FORBIDDEN_PARAMETERS, spec.name
        if "seed" in params:
            # The traversal seed and the bootstrap seed: deterministic inputs
            # to a pure function, not a model's sampling seed.
            assert spec.name in {"plan_traversal", "fit_bradley_terry"}, spec.name


def test_the_adr_names_every_frozen_tool_and_every_absence() -> None:
    text = ADR.read_text(encoding="utf-8")
    for spec in FROZEN_TOOLS:
        assert f"`{spec.name}`" in text, f"ADR-0026 does not name {spec.name}"
    for absent in DELIBERATELY_ABSENT:
        assert absent in text, f"ADR-0026 does not carry the absence of {absent}"


# --- the implementation against the rows -------------------------------------


def test_every_exposed_verb_has_a_row_and_no_planned_row_is_exposed() -> None:
    exposed = {ref.partition(":")[2] for ref in TOOL_REFS}
    assert exposed == {s.name for s in advertised()}
    assert len(set(TOOL_REFS)) == len(TOOL_REFS)


@pytest.mark.parametrize("name", [ref.partition(":")[2] for ref in TOOL_REFS])
def test_the_python_signature_agrees_with_the_frozen_input(name, verbs) -> None:
    """Names and required-ness are frozen; the closed shapes live in the row."""
    spec = frozen()[name]
    params = inspect.signature(verbs[name]).parameters
    assert set(params) == set(spec.input_schema["properties"]), name
    required = {p for p, v in params.items() if v.default is inspect.Parameter.empty}
    assert required == set(spec.input_schema["required"]), name
    for p in NEEDS_CLOCK & {name}:
        assert "at" not in spec.input_schema["required"]
    for p in NEEDS_ID & {name}:
        assert "analysis_id" not in spec.input_schema["required"]


def test_every_result_matches_its_envelope(verbs) -> None:
    """bind validates outputs, so running the chain is the assertion."""
    _open_scored(verbs)
    verbs["measures_mark_missing"](
        analysis_id="a1", contributor_id="ben", author={**AUTHOR, "id": "ben"},
        code="not-evidenced", note="nothing says", criterion_ids=["c"], independence="independent",
    )
    report = verbs["report_completeness"](analysis_id="a1")
    assert report["present"] == 1 and "summary" in report
    verbs["check_citations"](citations=[{"quote": "says so", "source": "it says so here"}])
    verbs["plan_traversal"](alternatives=["x"], criteria=["c"], seed="s")
    verbs["prompts_get"](prompt_id=verbs["prompts_list"]()["prompts"][0]["id"])


def test_an_envelope_violation_is_a_server_error_not_a_silent_pass() -> None:
    """The output half of the contract is shown failing, per ADR-0020."""
    from rubricator import surface
    from rubricator.surface.frozen import ToolSpec

    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    spec = frozen()["report_completeness"]
    narrower = ToolSpec(**{**spec.__dict__, "output_schema": {
        "type": "object", "properties": {"summary": {"type": "string"}},
        "required": ["summary"], "additionalProperties": False}})
    original = surface.frozen
    surface.frozen = lambda: {**original(), "report_completeness": narrower}
    try:
        verbs = bind(runtime)
        verbs["analysis_open"](analysis_id="a1", question="q")
        with pytest.raises(ContractViolation, match="outputSchema does not admit"):
            verbs["report_completeness"](analysis_id="a1")
    finally:
        surface.frozen = original


@pytest.mark.parametrize(
    "name, arguments, where",
    [
        ("frame_set", {"analysis_id": "a1", "ambiguities": [], "colour": "blue"}, "$"),
        ("alternatives_set", {"analysis_id": "a1", "alternatives": [{"id": "x", "label": "X", "url": "u"}]},
         "$.alternatives[0]"),
        ("criteria_set", {"analysis_id": "a1", "criteria": [
            {"id": "c", "label": "C", "anchors": ANCHORS,
             "missingCodes": [{"id": "p", "broader": "withheld", "means": "m", "notes": "n"}]}]},
         "$.criteria[0].missingCodes[0]"),
        ("measures_write", {"analysis_id": "a1", "contributor_id": "ana", "author": AUTHOR,
                            "cells": [{"alternativeId": "x", "criterionId": "c", "value": 3,
                                       "plan": "first I"}]},
         "$.cells[0]"),
        ("measures_write", {"analysis_id": "a1", "contributor_id": "ana",
                            "author": {**AUTHOR, "email": "x"}, "cells": []}, "$.author"),
    ],
)
def test_an_extra_key_is_refused_at_the_boundary_with_its_path(verbs, name, arguments, where) -> None:
    """The closed schema refuses an extra key *before* it is stored (#136)."""
    verbs["analysis_open"](analysis_id="a1", question="q")
    with pytest.raises(ValueError, match=f"refused: {name}: at " + where.replace("$", r"\$")
                       .replace("[", r"\[").replace("]", r"\]").replace(".", r"\.")) as e:
        verbs[name](**arguments)
    assert "Allowed here:" in str(e.value)


def test_a_wrong_type_is_refused_with_its_path(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="q")
    with pytest.raises(ValueError, match=r"refused: frame_set: at \$\.ambiguities"):
        verbs["frame_set"](analysis_id="a1", ambiguities="none")


# --- analysis_open: minting, reopening, retention ----------------------------


def test_an_id_is_minted_when_the_caller_gives_none(verbs) -> None:
    opened = verbs["analysis_open"](question="which?")
    assert opened["analysisId"] == "a-1" and opened["created"] is True
    assert verbs["analysis_open"](question="which?")["analysisId"] == "a-2"


def test_reopening_never_overwrites(verbs) -> None:
    _open_scored(verbs)
    again = verbs["analysis_open"](analysis_id="a1", question="something else")
    assert again["created"] is False
    assert again["question"] == "which?"
    assert again["alternatives"] == 1 and again["criteria"] == 1
    assert verbs["report_completeness"](analysis_id="a1")["present"] == 1


def test_a_new_analysis_needs_a_question(verbs) -> None:
    with pytest.raises(ValueError, match="needs a question"):
        verbs["analysis_open"](analysis_id="fresh")


def test_analysis_open_states_the_retention_window() -> None:
    assert f"{RETENTION_DAYS} days" in describe(frozen()["analysis_open"])


# --- the connector advertises the rows ---------------------------------------


def test_the_connector_advertises_the_frozen_rows_verbatim() -> None:
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    tools = {t.name: t for t in asyncio.run(server._list_tools())}
    assert set(tools) == {s.name for s in advertised()}
    for spec in advertised():
        wire = tools[spec.name].to_mcp_tool()
        assert wire.inputSchema == spec.input_schema, spec.name
        assert wire.outputSchema == spec.output_schema, spec.name
        assert wire.description == describe(spec), spec.name


def test_a_result_over_mcp_is_the_summary_beside_the_structured_content() -> None:
    pytest.importorskip("py2mcp")
    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    result = asyncio.run(server.call_tool("analysis_open", {"analysis_id": "a1", "question": "q"}))
    assert result.structured_content["analysisId"] == "a1"
    assert result.content[0].text == result.structured_content["summary"]


def test_a_refusal_over_mcp_is_a_tool_error_carrying_the_fact() -> None:
    """Validation and business-rule failures are tool errors, not protocol errors."""
    pytest.importorskip("py2mcp")
    from fastmcp.exceptions import ToolError

    from rubricator.mcp.server import make_server

    server = make_server(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    asyncio.run(server.call_tool("analysis_open", {"analysis_id": "a1", "question": "q"}))
    # A top-level extra key is caught by the host's own argument check (an
    # error result over the wire, a validation error in-process); a nested one
    # reaches the frozen row, which names the path and what is allowed.
    with pytest.raises(Exception, match="x"):
        asyncio.run(server.call_tool("frame_set", {"analysis_id": "a1", "ambiguities": [], "x": 1}))
    with pytest.raises(ToolError, match=r"at \$\.alternatives\[0\].*Allowed here"):
        asyncio.run(server.call_tool(
            "alternatives_set",
            {"analysis_id": "a1", "alternatives": [{"id": "x", "label": "X", "url": "u"}]}))
    with pytest.raises(ToolError, match="needs a question"):
        asyncio.run(server.call_tool("analysis_open", {"analysis_id": "nope"}))


# --- the measurement ----------------------------------------------------------


def test_the_token_measurement_is_current() -> None:
    """Measured, not estimated -- and re-measured whenever the definitions change.

    The byte size of the exact definitions a client sends is pinned to the size
    recorded beside the token count. Change a description or a schema and this
    fails until ``scripts/measure_tool_tokens.py`` has been run again and its
    output pasted into ``MEASURED``.
    """
    live, whole = definitions_bytes(advertised()), definitions_bytes(FROZEN_TOOLS)
    hint = "run scripts/measure_tool_tokens.py and record its output in frozen.MEASURED"
    assert MEASURED["advertised"]["tools"] == len(advertised()), hint
    assert MEASURED["wholeSurface"]["tools"] == len(FROZEN_TOOLS), hint
    assert MEASURED["advertised"]["bytes"] == live, f"advertised definitions changed; {hint}"
    assert MEASURED["wholeSurface"]["bytes"] == whole, f"frozen definitions changed; {hint}"
    assert MEASURED["advertised"]["tokens"] > 0 and MEASURED["measuredAt"] != "unmeasured", hint


def test_the_adr_records_the_measurement() -> None:
    text = ADR.read_text(encoding="utf-8")
    assert f"{MEASURED['advertised']['tokens']:,}" in text
    assert f"{MEASURED['wholeSurface']['tokens']:,}" in text
