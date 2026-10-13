"""The nits #195 filed beside its should-fix findings, each held by a test."""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.schema.pins import PINS, read_pinned
from rubricator.store import AnalysisStore
from rubricator.tools.analysis import alternatives_set, analysis_open

AT = "2026-10-12T12:00:00Z"
FRAME = {"id": "a1", "schemaVersion": 1, "subject": {"question": "which kettle?"},
         "alternatives": [], "criteria": [], "authors": [], "cells": []}


def test_an_id_with_files_but_no_frame_is_not_listed() -> None:
    """#145: ``analyses()`` listed what ``exists()`` and ``frame()`` call not found."""
    store = AnalysisStore({}, now=fixed_clock(AT))
    store.put_frame("a1", dict(FRAME))
    store.blobs["analyses/orphan/contributions/ana.json"] = b"{}"
    assert store.analyses() == ["a1"]


class _CountingBlobs(dict):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reads: dict[str, int] = {}

    def __getitem__(self, key):
        self.reads[key] = self.reads.get(key, 0) + 1
        return super().__getitem__(key)


def test_a_file_s_contract_verdict_is_taken_from_the_one_read_it_parsed() -> None:
    """#157/#164/#165: a second read could hash bytes other than those validated."""
    store = AnalysisStore(_CountingBlobs(), now=fixed_clock(AT))
    store.put_frame("a1", dict(FRAME))
    store.put_contribution("a1", "ana", {"authors": [], "cells": []})
    key = store.contribution_key("a1", "ana")
    store.blobs.reads.clear()
    store.read_skipping("a1")
    assert store.blobs.reads[key] == 1


def test_a_verdict_is_filed_under_the_contract_that_gave_it() -> None:
    """#157: keyed by ``id(contract)`` alone, a collected contract's id could be reused."""
    store = AnalysisStore({}, now=fixed_clock(AT))
    store.put_frame("a1", dict(FRAME))
    store.put_contribution("a1", "ana", {"authors": [], "cells": []})
    store.read_skipping("a1")
    assert all(id(contract) == key for key, (contract, _) in store._verdicts.items())


def test_a_second_copy_of_a_stored_problem_is_a_new_one() -> None:
    """#155: introduced problems were compared as a set."""
    store = build_runtime(blobs={}).store
    analysis_open(store, analysis_id="a", question="q?", allow_skip_confirmation=True, at=AT)
    alternatives_set(store, analysis_id="a", alternatives=[{"id": "k1", "label": "K"}])
    key = store.frame_key("a")
    frame = json.loads(store.blobs[key])
    frame["alternatives"][0]["label"] = 5  # a hand edit the contract refuses
    store.blobs[key] = json.dumps(frame).encode()
    with pytest.raises(ValueError, match=r"alternatives\[1\]\.label"):
        alternatives_set(store, analysis_id="a", alternatives=[{"id": "k1", "label": 5},
                                                              {"id": "k2", "label": 5}])
    # The stored one alone still does not lock the analysis.
    alternatives_set(store, analysis_id="a", alternatives=[{"id": "k1", "label": 5},
                                                          {"id": "k2", "label": "K2"}])


def test_a_vendored_file_is_read_only_if_it_matches_its_pin(tmp_path) -> None:
    """#135: the pin was checked by a test, never when the package read the file."""
    for name in PINS:
        (tmp_path / name).write_bytes(b"{}")
    with pytest.raises(ValueError, match="not the contract it claims to be"):
        read_pinned("comparanda.v1.json", directory=tmp_path)
    (tmp_path / "stray.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="has no pin"):
        read_pinned("stray.json", directory=tmp_path)
