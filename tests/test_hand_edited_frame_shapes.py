"""A hand-edited frame of the wrong shape never crashes a reading tool (#169).

#151 and #159 made the store tolerate a broken *contribution*. A hand edit to the
*frame* could still crash every reader with a bare ``TypeError`` or
``AttributeError``:

- ``missingCodes`` of ``null`` or a number, on the analysis or on a criterion,
  crashed the declaration walk in :mod:`rubricator.rules`;
- ``criteria`` or ``alternatives`` as an object rather than a list (or a list of
  non-objects) crashed every reader that indexes the rows.

Declarations are walked as lists only, as ``_declaration_lists`` already did
since #160, so an analysis-level declaration problem still never locks a
criteria write. A row list the merge cannot index is the frame's own
``MergeProblem``, reported once, as #159 does for the other frame shapes.
"""

from __future__ import annotations

import json

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.merge import MergeProblem
from rubricator.rules import declarations_for, honesty_problems, missing_rule_code_defined
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"}, {"level": "5", "text": "fast"}]
RULES = {"missingRules": [{"when": "the maker says nothing", "code": "not-evidenced"}]}

#: Every tool that reads a stored analysis through the merge.
READERS = [
    ("analysis_open", {}),
    ("analysis_get", {}),
    ("analysis_get", {"view": "summary"}),
    ("analysis_get", {"view": "outstanding"}),
    ("report_completeness", {}),
    ("aggregate_assertions", {}),
]


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k1", "label": "Kettle one"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS, "definition": RULES}])
    return rt


def _hand_edit(runtime, change) -> None:
    key = runtime.store.frame_key("a1")
    frame = json.loads(runtime.store.blobs[key])
    change(frame)
    runtime.store.blobs[key] = json.dumps(frame).encode()


DECLARATION_SHAPES = {
    "analysis missingCodes null": lambda f: f.__setitem__("missingCodes", None),
    "analysis missingCodes a number": lambda f: f.__setitem__("missingCodes", 5),
    "analysis missingCodes an object": lambda f: f.__setitem__("missingCodes", {"a": 1}),
    "criterion missingCodes null": lambda f: f["criteria"][0].__setitem__("missingCodes", None),
    "criterion missingCodes a number": lambda f: f["criteria"][0].__setitem__("missingCodes", 5),
    "declarations that are not objects": lambda f: f.__setitem__("missingCodes", [None, 3, "x"]),
}

ROW_SHAPES = {
    "criteria as an object": lambda f: f.__setitem__("criteria", {"speed": f["criteria"][0]}),
    "alternatives as an object": lambda f: f.__setitem__(
        "alternatives", {"k1": f["alternatives"][0]}),
    "criteria null": lambda f: f.__setitem__("criteria", None),
    "a criterion that is a number": lambda f: f.__setitem__("criteria", [1]),
    "an alternative with no id": lambda f: f["alternatives"].append({"label": "?"}),
    "a criterion whose id is a number": lambda f: f["criteria"].append({"id": 7, "label": "?"}),
}


@pytest.mark.parametrize("name, arguments", READERS)
@pytest.mark.parametrize("shape", sorted(DECLARATION_SHAPES))
def test_a_declaration_list_that_is_not_a_list_is_read_past(runtime, shape, name, arguments) -> None:
    """Not a list is no declarations: the read goes on, as the schema-rule walk already did."""
    _hand_edit(runtime, DECLARATION_SHAPES[shape])
    got = bind(runtime)[name](analysis_id="a1", **arguments)
    assert isinstance(got["summary"], str)


@pytest.mark.parametrize("name, arguments", READERS)
@pytest.mark.parametrize("shape", sorted(ROW_SHAPES))
def test_rows_the_merge_cannot_index_are_the_frame_s_problem(runtime, shape, name, arguments) -> None:
    _hand_edit(runtime, ROW_SHAPES[shape])
    with pytest.raises(MergeProblem, match="the frame.*repair the frame file"):
        bind(runtime)[name](analysis_id="a1", **arguments)


@pytest.mark.parametrize("shape", sorted(DECLARATION_SHAPES))
def test_criteria_set_still_repairs_a_criterion_s_declarations(runtime, shape) -> None:
    """The write path that owns criteria is never locked over a declaration problem (#160)."""
    _hand_edit(runtime, DECLARATION_SHAPES[shape])
    bind(runtime)["criteria_set"](analysis_id="a1", criteria=[
        {"id": "speed", "label": "Boil speed", "anchors": ANCHORS, "definition": RULES}])
    assert runtime.store.frame("a1")["criteria"][0].get("missingCodes") in (None, [])


def test_a_rule_naming_a_code_only_a_broken_list_declared_is_still_reported() -> None:
    """Skipping the broken list leaves the rule's code undeclared, which is reported, not hidden."""
    document = {"missingCodes": {"id": "vendor-silent"}, "criteria": [{
        "id": "c", "missingCodes": None,
        "definition": {"missingRules": [{"when": "w", "code": "vendor-silent"}]}}]}
    assert [p.rule_id for p in missing_rule_code_defined(document)] == ["missing-rule-code-defined"]


@pytest.mark.parametrize("document", [
    {"missingCodes": None, "criteria": [{"id": "c", "missingCodes": 5}]},
    {"criteria": {"c": {}}},
    {"criteria": [1, {"id": "c", "definition": "loose"}]},
    {"criteria": [{"id": "c", "definition": {"missingRules": {"code": "x"}}}]},
    {"criteria": [{"id": "c", "definition": {"missingRules": [None, {"code": ["x"]}]}}]},
])
def test_the_declaration_walk_never_raises_on_a_document_from_disk(document) -> None:
    declarations_for(document, "c")
    list(missing_rule_code_defined(document))
    honesty_problems(document)


def test_a_valid_declaration_beside_junk_still_resolves() -> None:
    declared = {"id": "vendor-silent", "broader": "not-evidenced", "means": "the maker is silent"}
    document = {"missingCodes": [None, declared], "criteria": [{"id": "c", "missingCodes": 5}]}
    assert declarations_for(document, "c") == [declared]
