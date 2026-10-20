"""The version handshake (#127): EMITS is a vendored, pinned set; emission is lowest-first; drift only warns."""

from __future__ import annotations

import pytest

from rubricator.schema.drift import drift
from rubricator.schema.pins import PINS
from rubricator.schema.source import EMITS, SUPPORTED_SCHEMA_VERSIONS, emit_version, published_schema_text


def test_emits_is_a_set_and_every_member_is_vendored_pinned_and_servable():
    assert isinstance(EMITS, frozenset) and EMITS
    assert SUPPORTED_SCHEMA_VERSIONS == tuple(sorted(EMITS))
    for version in EMITS:
        assert f"comparanda.v{version}.json" in PINS
        assert published_schema_text(version)


def test_a_version_outside_emits_is_refused_even_if_a_file_were_present():
    with pytest.raises(ValueError, match="supports"):
        published_schema_text(max(EMITS) + 1)


def test_emission_picks_the_lowest_version_that_expresses_the_document():
    assert emit_version({"id": "x", "subject": {"question": "q"}}) == min(EMITS)


def test_a_document_no_version_expresses_is_refused_naming_each_attempt():
    with pytest.raises(ValueError, match="no emittable schema version"):
        emit_version({"id": "x", "subject": {"question": "q"}, "bogus": 1})


def test_drift_reports_a_newer_published_version_and_a_changed_file_and_is_silent_when_equal():
    pin = PINS["comparanda.v1.json"].sha256
    assert drift({1: pin}) == []
    assert any("not vendored" in line for line in drift({1: pin, 2: "a" * 64}))
    assert any("different file" in line for line in drift({1: "b" * 64}))
