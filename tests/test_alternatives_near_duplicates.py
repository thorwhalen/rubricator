"""Tool 6 (#55): ``alternatives_set`` flags near-duplicate alternatives and never merges them.

Deduplicating two alternatives is a decision about the frame, and the tool is
not entitled to make it: the rows are written exactly as given, and a pair whose
labels nearly coincide is reported beside them for the model to put to the user.
The threshold is a named constant (:data:`NEAR_DUPLICATE_THRESHOLD`), not a magic
number in the body. Fixtures are invented (comparanda ADR-0033).
"""

from __future__ import annotations

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind
from rubricator.tools.analysis import (
    NEAR_DUPLICATE_THRESHOLD,
    label_similarity,
    near_duplicates,
)

MOMENT = "2026-08-22T12:00:00Z"


def _verbs():
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    return runtime, verbs


def test_the_threshold_is_a_named_constant() -> None:
    assert 0 < NEAR_DUPLICATE_THRESHOLD <= 1
    assert NEAR_DUPLICATE_THRESHOLD == 0.75


@pytest.mark.parametrize("a, b, expected", [
    ("Brightwater K2", "Brightwater K2", 1.0),
    ("Brightwater K2", "brightwater-k2", 1.0),          # case and punctuation fold away
    ("K2", "K2 kettle", 1.0),                           # one label inside the other
    ("Option A", "Option B", 0.5),                      # stopwords count: these are distinct
    ("Brightwater K2", "Brightwater K3", 0.5),
    ("Lumen L5", "Brightwater K2", 0.0),
    ("", "K2", 0.0),                                    # nothing to compare is not a match
    (5, "K2", 0.0),                                     # a hand-edited label is not a match
])
def test_label_similarity_is_the_overlap_of_label_tokens(a, b, expected) -> None:
    assert label_similarity(a, b) == expected
    assert label_similarity(b, a) == expected


def test_a_near_duplicate_pair_is_flagged_and_both_rows_are_written() -> None:
    runtime, verbs = _verbs()
    got = verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k2", "label": "Brightwater K2"},
        {"id": "l5", "label": "Lumen L5"},
        {"id": "k2-kettle", "label": "The Brightwater K2 kettle"},
    ])
    assert got["nearDuplicates"] == [{"a": "k2", "b": "k2-kettle", "similarity": 1.0}]
    assert [a["id"] for a in runtime.store.frame("a1")["alternatives"]] == ["k2", "l5", "k2-kettle"]
    assert "never merged" in got["summary"] and "k2 / k2-kettle" in got["summary"]


def test_distinct_alternatives_flag_nothing() -> None:
    _, verbs = _verbs()
    got = verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "a", "label": "Option A"}, {"id": "b", "label": "Option B"},
        {"id": "k2", "label": "Brightwater K2"}, {"id": "k3", "label": "Brightwater K3"},
    ])
    assert got["nearDuplicates"] == []
    assert "near-duplicate" not in got["summary"]


def test_a_tombstoned_row_is_not_compared() -> None:
    """A retired row has left every comparison; flagging it against its successor is noise."""
    _, verbs = _verbs()
    got = verbs["alternatives_set"](analysis_id="a1", alternatives=[
        {"id": "k2-old", "label": "Brightwater K2", "tombstoned": True, "supersededBy": ["k2"]},
        {"id": "k2", "label": "Brightwater K2"},
    ])
    assert got["nearDuplicates"] == []


def test_pairs_are_ordered_by_id_whatever_the_input_order() -> None:
    rows = [{"id": "z", "label": "Kettle"}, {"id": "m", "label": "kettle"}, {"id": "a", "label": "KETTLE"}]
    assert [(p["a"], p["b"]) for p in near_duplicates(rows)] == [("a", "m"), ("a", "z"), ("m", "z")]
    assert near_duplicates(rows) == near_duplicates(list(reversed(rows)))
