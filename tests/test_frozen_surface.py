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

#: A span every scored cell here cites: since #171 a value with no evidence is refused.
CITED = [{"id": "e1", "target": "doc:spec", "sourceType": "primary",
          "selectors": [{"type": "TextQuoteSelector", "exact": "as stated"}]}]

ADR = Path(__file__).resolve().parents[1] / "docs" / "adr" / "0026-the-frozen-tool-surface.md"
MOMENT = "2026-08-22T12:00:00Z"

AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "a"}, {"level": "3", "text": "b"}, {"level": "5", "text": "c"}]


@pytest.fixture()
def verbs():
    return bind(build_runtime(blobs={}, now=fixed_clock(MOMENT), new_id=sequential_ids("a")))


def _open_scored(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="which?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=["which region?"], decision="adopt one")
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "x", "criterionId": "c", "value": 3, "justification": "says so",
                "evidence": CITED}],
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
    from rubricator.surface.frozen import definitions_digest

    hint = "run scripts/measure_tool_tokens.py and record its output in frozen.MEASURED"
    assert MEASURED["advertised"]["tools"] == len(advertised()), hint
    assert MEASURED["wholeSurface"]["tools"] == len(FROZEN_TOOLS), hint
    assert MEASURED["advertised"]["sha256"] == definitions_digest(advertised()), (
        f"advertised definitions changed; {hint}")
    assert MEASURED["wholeSurface"]["sha256"] == definitions_digest(FROZEN_TOOLS), (
        f"frozen definitions changed; {hint}")
    assert MEASURED["advertised"]["bytes"] == definitions_bytes(advertised())
    assert MEASURED["wholeSurface"]["bytes"] == definitions_bytes(FROZEN_TOOLS)
    assert MEASURED["advertised"]["tokens"] > 0 and MEASURED["measuredAt"] != "unmeasured", hint


def test_the_adr_records_the_measurement() -> None:
    text = ADR.read_text(encoding="utf-8")
    assert f"{MEASURED['advertised']['tokens']:,}" in text
    assert f"{MEASURED['wholeSurface']['tokens']:,}" in text


# --- the review's findings, kept failing-able ---------------------------------


def _write(verbs, cell_extra=None, **cell):
    verbs["analysis_open"](analysis_id="a1", question="which?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    return verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "x", "criterionId": "c",
               **({"evidence": CITED} if "value" in cell else {}), **cell}],
    )


def test_every_write_leaves_a_document_the_published_schema_accepts() -> None:
    """ADR-0017: the stored record is itself a schema-valid comparanda analysis."""
    from rubricator.merge import merge_contributions

    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    _write(verbs, value=5, justification="dated", evidence=[{
        "id": "e1", "target": "rendition:r", "sourceType": "primary", "stance": "supports",
        "selectors": [{"type": "TextQuoteSelector", "exact": "until 2029"},
                      {"type": "TextPositionSelector", "start": 10, "end": 20}],
        "check": {"status": "exact", "checkedAt": MOMENT, "checkerVersion": "rubricator/0.0.1"},
    }])
    verbs["measures_mark_missing"](
        analysis_id="a1", contributor_id="ben", author={**AUTHOR, "id": "ben"},
        code="not-evidenced", note="silent", independence="independent",
    )
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "x", "label": "X", "tombstoned": True, "supersededBy": ["y"]}, {"id": "y", "label": "Y"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "c", "label": "C", "anchors": ANCHORS, "tombstoned": True}])
    store = runtime.store
    merged = merge_contributions(store.frame("a1"), store.contributions("a1"))
    assert merged["alternatives"][0]["tombstoned"] is True
    assert merged["criteria"][0]["tombstoned"] is True
    result = runtime.schema.validate(merged)
    assert result.ok, result.report()


def test_a_selector_comparanda_would_refuse_is_refused_at_the_boundary(verbs) -> None:
    with pytest.raises(ValueError, match=r"refused: measures_write: at \$\.cells\[0\]\.evidence\[0\]\.selectors\[0\]"):
        _write(verbs, value=5, justification="j", evidence=[{
            "id": "e1", "target": "t", "sourceType": "primary",
            "selectors": [{"type": "Bogus", "exact": "x"}]}])


def test_a_value_the_scale_cannot_take_is_refused(verbs) -> None:
    """#49: scores are bounded -- by the validator, since the scale is data."""
    with pytest.raises(ValueError, match="not one of the levels its scale declares"):
        _write(verbs, value=9.5, justification="j")
    with pytest.raises(ValueError, match="not one of the levels"):
        _write(verbs, value="5", justification="j")


def test_a_scored_row_can_be_retired_but_not_dropped(verbs) -> None:
    _write(verbs, value=3, justification="j")
    with pytest.raises(ValueError, match="tombstone"):
        verbs["alternatives_set"](analysis_id="a1", alternatives=[])
    out = verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "x", "label": "X", "tombstoned": True}])
    assert out["alternatives"] == ["x"]


def test_a_frame_field_can_be_cleared_and_is_kept_when_unmentioned(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="q")
    verbs["frame_set"](analysis_id="a1", ambiguities=[], decision="adopt", decider="the CTO")
    kept = verbs["frame_set"](analysis_id="a1", ambiguities=[], decision="adopt one")
    assert kept["decider"] == "the CTO"
    cleared = verbs["frame_set"](analysis_id="a1", ambiguities=[], decider="")
    assert cleared["decider"] is None and cleared["decision"] == "adopt one"


def test_an_empty_selection_cannot_mean_every_cell(verbs) -> None:
    _write(verbs, value=3, justification="j")
    with pytest.raises(ValueError, match=r"at \$\.criterion_ids"):
        verbs["measures_mark_missing"](
            analysis_id="a1", contributor_id="ana", author=AUTHOR, code="deferred", note="n",
            criterion_ids=[])


def test_a_stated_moment_must_be_a_moment(verbs) -> None:
    _write(verbs, value=3, justification="j")
    with pytest.raises(ValueError, match=r"at \$\.at"):
        verbs["measures_write"](analysis_id="a1", contributor_id="ana", author=AUTHOR, at="next tuesday",
                                cells=[{"alternativeId": "x", "criterionId": "c", "value": 4}])


def test_an_id_that_could_leave_its_directory_is_refused(verbs) -> None:
    for bad in ("../escape", "", "a/b", "x" * 65):
        with pytest.raises(ValueError, match="not a usable id"):
            verbs["analysis_open"](analysis_id=bad, question="q")


def test_a_plan_over_duplicate_ids_is_refused(verbs) -> None:
    with pytest.raises(ValueError, match="more than once"):
        verbs["plan_traversal"](alternatives=["x", "x"], criteria=["c"])


def test_forbidden_parameters_are_absent_at_every_depth() -> None:
    def names(node):
        if isinstance(node, dict):
            for k, v in node.get("properties", {}).items():
                yield k
                yield from names(v)
            for k in ("items", "additionalProperties"):
                if isinstance(node.get(k), dict):
                    yield from names(node[k])
            for alt in node.get("anyOf", []) + node.get("allOf", []):
                yield from names(alt)
    for spec in FROZEN_TOOLS:
        assert not set(names(spec.input_schema)) & FORBIDDEN_PARAMETERS, spec.name


@pytest.mark.parametrize(
    "violation, schema",
    [
        ("additionalProperties", {"required": ["a"], "additionalProperties": {"type": "integer", "minimum": 3}}),
        ("minimum", {"required": ["a"], "additionalProperties": {"type": "integer", "minimum": 3}}),
        ("const", {"const": {"a": 1}}),
        ("format", {"type": "string", "format": "regex"}),
        ("minItems", {"type": "array", "items": {"type": "string"}, "minItems": True}),
        ("seven JSON types", {"type": ["string", "null"]}),
        ("properties must be", {"type": "object", "additionalProperties": False, "properties": []}),
    ],
)
def test_the_checker_catches_what_the_review_slipped_past_it(violation, schema) -> None:
    found = subset_violations(schema)
    assert any(violation in line for line in found), (violation, found)


def test_the_checker_decodes_json_pointer_escapes() -> None:
    schema = {"$defs": {"a/b": {"type": "string"}}, "$ref": "#/$defs/a~1b"}
    assert subset_violations(schema) == []


def test_the_digest_pin_catches_a_same_length_edit() -> None:
    from rubricator.surface.frozen import ToolSpec, definitions_digest

    spec = frozen()["frame_set"]
    edited = ToolSpec(**{**spec.__dict__, "input_schema": {
        **spec.input_schema,
        "properties": {**spec.input_schema["properties"], "context": {"type": "number"}}}})
    rows = tuple(edited if s.name == "frame_set" else s for s in advertised())
    assert definitions_digest(rows) != MEASURED["advertised"]["sha256"]


# --- the second review's findings -------------------------------------------


SELECTORS = [
    {"type": "TextQuoteSelector", "exact": "until 2029", "prefix": "supported ", "suffix": "."},
    {"type": "TextPositionSelector", "start": 10, "end": 20},
    {"type": "PageRegionSelector", "page": 3, "rect": {"x": 0, "y": 0, "w": 100, "h": 20}},
    {"type": "LineRangeSelector", "startLine": 1, "endLine": 2, "contentHash": "abc"},
    {"type": "TimeRangeSelector", "startSeconds": 1.5, "endSeconds": 2.5},
    {"type": "PathSelector", "syntax": "xpath", "value": "//p"},
]
#: Selectors the schema accepts and the ADR-0014 locator profile does not store (#62).
OUTSIDE_THE_PROFILE = {"PathSelector"}


@pytest.mark.parametrize("selector", [s for s in SELECTORS if s["type"] not in OUTSIDE_THE_PROFILE],
                         ids=lambda s: s["type"])
def test_every_selector_the_surface_accepts_is_one_the_published_schema_accepts(selector) -> None:
    from rubricator.merge import merge_contributions

    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    # A position is a hint and never the sole locator (ADR-0014): the quote rides beside it.
    selectors = [selector] if selector is SELECTORS[0] else [SELECTORS[0], selector]
    _write(verbs, value=5, justification="j", evidence=[{
        "id": "e1", "target": "rendition:r", "sourceType": "primary", "selectors": selectors}])
    merged = merge_contributions(runtime.store.frame("a1"), runtime.store.contributions("a1"))
    result = runtime.schema.validate(merged)
    assert result.ok, result.report()


@pytest.mark.parametrize("selector", [s for s in SELECTORS if s["type"] in OUTSIDE_THE_PROFILE],
                         ids=lambda s: s["type"])
def test_a_selector_the_schema_accepts_and_the_profile_rejects_is_refused(verbs, selector) -> None:
    with pytest.raises(ValueError, match=rf"{selector['type']} is not in the locator profile"):
        _write(verbs, value=5, justification="j", evidence=[{
            "id": "e1", "target": "rendition:r", "sourceType": "primary",
            "selectors": [SELECTORS[0], selector]}])


def test_a_boolean_is_never_a_level(verbs) -> None:
    with pytest.raises(ValueError, match="value True is not one of the levels"):
        _write(verbs, value=True, justification="j")


def test_an_unknown_alternative_is_refused_like_an_unknown_criterion(verbs) -> None:
    verbs["analysis_open"](analysis_id="a1", question="q", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": ANCHORS}])
    with pytest.raises(KeyError, match="alternatives ghost are not in this analysis"):
        verbs["measures_write"](analysis_id="a1", contributor_id="ana", author=AUTHOR,
                                cells=[{"alternativeId": "ghost", "criterionId": "c", "value": 3}])


def test_an_undeclared_measure_or_missing_code_is_refused_on_write(verbs) -> None:
    with pytest.raises(ValueError, match='measure "confidence" is not one this analysis declares'):
        _write(verbs, measure="confidence", value=0.8)
    with pytest.raises(ValueError, match=r'the code "paywalled" is neither a core code nor declared'):
        _write(verbs, missing={"code": "paywalled", "note": "n"})


def test_a_tombstoned_row_takes_no_new_assertions(verbs) -> None:
    _write(verbs, value=3, justification="j")
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X", "tombstoned": True}])
    with pytest.raises(ValueError, match="tombstoned and takes no new assertions"):
        verbs["measures_write"](analysis_id="a1", contributor_id="ben", author={**AUTHOR, "id": "ben"},
                                cells=[{"alternativeId": "x", "criterionId": "c", "value": 4,
                                        "independence": "independent"}])


def test_reasoning_is_declared_before_value_in_the_cell_shape() -> None:
    """ADR-0013: property order is generation order, and this argument is the judgement."""
    from rubricator.surface.frozen import CELL, definitions_digest

    order = list(CELL["properties"])
    assert order.index("justification") < order.index("value")
    assert order.index("evidence") < order.index("value")
    assert order.index("evidence") < order.index("missing")
    # And the pin sees a reorder: insertion order is part of the digest.
    from rubricator.surface.frozen import ToolSpec
    spec = frozen()["measures_write"]
    cells = spec.input_schema["properties"]["cells"]
    reordered = {**cells, "items": {**cells["items"], "properties": dict(reversed(list(cells["items"]["properties"].items())))}}
    edited = ToolSpec(**{**spec.__dict__, "input_schema": {
        **spec.input_schema, "properties": {**spec.input_schema["properties"], "cells": reordered}}})
    rows = tuple(edited if s.name == "measures_write" else s for s in advertised())
    assert definitions_digest(rows) != MEASURED["advertised"]["sha256"]


def test_the_citation_threshold_is_not_a_model_knob(verbs) -> None:
    assert "partial_threshold" not in frozen()["check_citations"].input_schema["properties"]
    with pytest.raises(ValueError, match="partial_threshold"):
        verbs["check_citations"](citations=[{"quote": "a", "source": "b"}], partial_threshold=0)


@pytest.mark.parametrize("moment", ["2026-08-22", "2026-08-22T12", "2026-08-22T12:00:00",
                                    "20260822T120000Z", "2026-W34-6T12:00Z", "next tuesday"])
def test_a_moment_that_is_not_rfc3339_is_refused(verbs, moment) -> None:
    _write(verbs, value=3, justification="j")
    with pytest.raises(ValueError, match=r"at \$\.at"):
        verbs["measures_write"](analysis_id="a1", contributor_id="ana", author=AUTHOR, at=moment,
                                cells=[{"alternativeId": "x", "criterionId": "c", "value": 4}])


@pytest.mark.parametrize("moment", ["2026-08-22T12:00:00Z", "2026-08-22T12:00:00z",
                                    "2026-08-22T12:00:00.5Z", "2026-08-22T12:00:00.123456789+02:00",
                                    "2026-08-22t12:00:00-05:30"])
def test_an_rfc3339_moment_is_accepted_on_every_supported_python(verbs, moment) -> None:
    _write(verbs, value=3, justification="j")
    verbs["measures_write"](analysis_id="a1", contributor_id="ana", author=AUTHOR, at=moment,
                            cells=[{"alternativeId": "x", "criterionId": "c", "value": 4, "evidence": CITED, "justification": "j",
                                    "independence": "resampled"}])


@pytest.mark.parametrize(
    "violation, schema",
    [
        ("what it admits", {}),
        ("what it admits", {"description": "anything"}),
        ("declare items", {"type": "array"}),
        ("required must be", {"type": "object", "additionalProperties": False, "properties": {"a": {"type": "string"}}, "required": "a"}),
        ("$defs must be", {"type": "string", "$defs": []}),
    ],
)
def test_the_checker_catches_the_latent_holes(violation, schema) -> None:
    found = subset_violations(schema)
    assert any(violation in line for line in found), (violation, found)


def test_a_minted_id_never_starts_with_an_option_dash() -> None:
    from rubricator.ids import random_id
    from rubricator.store import check_id

    ids = {random_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(not i.startswith("-") and check_id(i) for i in ids)


def test_a_bulk_blank_skips_tombstoned_cells_but_refuses_one_named(verbs) -> None:
    _write(verbs, value=3, justification="j")
    verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "x", "label": "X", "tombstoned": True}, {"id": "y", "label": "Y"}])
    out = verbs["measures_mark_missing"](
        analysis_id="a1", contributor_id="ben", author={**AUTHOR, "id": "ben"},
        code="not-evidenced", note="n")
    assert out["marked"] == 1
    with pytest.raises(ValueError, match="tombstoned"):
        verbs["measures_mark_missing"](
            analysis_id="a1", contributor_id="cy", author={**AUTHOR, "id": "cy"},
            code="not-evidenced", note="n", alternative_ids=["x"], independence="independent")


@pytest.mark.parametrize("moment", ["2026-08-22T12:00:00.12Z", "2026-08-22T12:00:00.1234Z"])
def test_short_fractions_are_padded_for_every_supported_python(verbs, moment) -> None:
    _write(verbs, value=3, justification="j")
    verbs["measures_write"](analysis_id="a1", contributor_id="ana", author=AUTHOR, at=moment,
                            cells=[{"alternativeId": "x", "criterionId": "c", "value": 4, "evidence": CITED, "justification": "j",
                                    "independence": "resampled"}])
