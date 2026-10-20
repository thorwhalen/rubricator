"""The frozen resource surface (ADR-0026, #66): eight rows, held against what is served."""

from __future__ import annotations

import pytest

from rubricator.surface import FROZEN_RESOURCES, match_resource
from rubricator.surface.resources import RESOURCE_URIS, parse_span_id, span_id
from rubricator.tools.views import analysis_uri


def test_there_are_eight_resources_with_unique_names_and_templates():
    assert len(FROZEN_RESOURCES) == 8
    assert len({r.name for r in FROZEN_RESOURCES}) == 8
    assert len(set(RESOURCE_URIS)) == 8


def test_every_row_states_what_the_issue_requires():
    for r in FROZEN_RESOURCES:
        assert r.uri_template.startswith("rubricator://")
        assert r.mime_type
        assert r.audience and set(r.audience) <= {"assistant", "user"}
        assert 0 <= r.priority <= 1
        assert r.why_resource and r.failure


def test_the_three_method_resources_are_assistant_audience_and_high_priority():
    rows = {r.name: r for r in FROZEN_RESOURCES}
    for name in ("method", "confidence-rubric", "missingness-codes"):
        assert rows[name].audience == ("assistant",)
        assert rows[name].priority >= 0.9


def test_templates_are_level_one_only():
    for uri in RESOURCE_URIS:
        assert "{+" not in uri and "{#" not in uri


def test_the_analysis_row_is_what_the_server_already_serves():
    row = next(r for r in FROZEN_RESOURCES if r.name == "analysis")
    assert row.status == "implemented"
    assert row.uri_template.replace("{id}", "{analysis_id}") == analysis_uri("{analysis_id}")


def test_no_analysis_list_tool_exists_because_the_list_is_a_resource():
    from rubricator.surface.frozen import DELIBERATELY_ABSENT

    assert "analysis_list" in DELIBERATELY_ABSENT
    assert any(r.name == "analyses" and r.audience == ("user",) for r in FROZEN_RESOURCES)


@pytest.mark.parametrize(
    "uri,name,variables",
    [
        ("rubricator://method", "method", {}),
        ("rubricator://schema/comparanda/1", "comparanda-schema", {"version": "1"}),
        ("rubricator://analyses", "analyses", {}),
        ("rubricator://analysis/a-1", "analysis", {"id": "a-1"}),
        ("rubricator://analysis/a-1/document/doc-x", "document", {"id": "a-1", "document_id": "doc-x"}),
        ("rubricator://analysis/a-1/span/3-9", "span", {"id": "a-1", "span_id": "3-9"}),
    ],
)
def test_a_concrete_uri_resolves_to_exactly_one_row(uri, name, variables):
    row, found = match_resource(uri)
    assert (row.name, found) == (name, variables)


def test_span_ids_round_trip_and_malformed_ones_are_refused():
    assert parse_span_id(span_id(10, 42)) == (10, 42)
    for bad in ("10:42", "42-10", "10-10", "-3", "a-b", ""):
        with pytest.raises(ValueError, match="span id"):
            parse_span_id(bad)
