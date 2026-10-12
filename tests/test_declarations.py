"""Missing-code declarations the companion refuses are refused at authoring (#140).

`comparanda` refuses a declaration that redeclares a core code
(``no-redeclaring-core``), one that claims ``structural: true`` while refining
anything but the structural core code (``structural-refines-not-applicable``),
and an id declared twice in one list (``unique-declarations``). The
``missing-rule-code-defined`` mirror trusts these declarations, so they are
checked where they are written and mirrored over documents in
:mod:`rubricator.rules`.
"""

from __future__ import annotations

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.rules import HONESTY_RULES, SCHEMA_RULES, schema_problems
from rubricator.surface import bind

MOMENT = "2026-08-22T12:00:00Z"
ANCHORS = [{"level": "1", "text": "a"}, {"level": "3", "text": "b"}, {"level": "5", "text": "c"}]
GOOD = {"id": "vendor-silent", "broader": "not-evidenced", "means": "the vendor says nothing"}
REDECLARED = {"id": "not-evidenced", "broader": "withheld", "means": "mine now"}
STRUCTURAL_ELSEWHERE = {"id": "hidden", "broader": "withheld", "means": "left out",
                        "structural": True}
STRUCTURAL_REFINED = {"id": "no-such-model", "broader": "not-applicable",
                      "means": "the vendor has no such model", "structural": True}


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(rt)
    verbs["analysis_open"](analysis_id="a1", question="which?", allow_skip_confirmation=True)
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    return rt


def _criteria(*declarations):
    return [{"id": "c", "label": "C", "anchors": ANCHORS, "missingCodes": list(declarations)}]


@pytest.mark.parametrize("declarations, rule", [
    ((REDECLARED,), "no-redeclaring-core"),
    ((STRUCTURAL_ELSEWHERE,), "structural-refines-not-applicable"),
    ((GOOD, GOOD), "unique-declarations"),
])
def test_criteria_set_refuses_a_declaration_the_companion_refuses(runtime, declarations, rule) -> None:
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=rf"criteria\[0\]\.missingCodes\[\d\]: .* Fix: .*\[{rule}\]"):
        bind(runtime)["criteria_set"](analysis_id="a1", criteria=_criteria(*declarations))
    assert dict(runtime.store.blobs) == before


def test_well_formed_declarations_are_kept(runtime) -> None:
    bind(runtime)["criteria_set"](analysis_id="a1", criteria=_criteria(GOOD, STRUCTURAL_REFINED))
    stored = runtime.store.frame("a1")["criteria"][0]["missingCodes"]
    assert [d["id"] for d in stored] == ["vendor-silent", "no-such-model"]
    assert runtime.schema.validate(runtime.store.read("a1")).ok


def test_an_analysis_level_problem_is_not_this_verb_s_to_refuse(runtime) -> None:
    """It has no write path here; a criteria write must not be locked over it."""
    frame = runtime.store.frame("a1")
    frame["missingCodes"] = [REDECLARED]
    runtime.store.put_frame("a1", frame)
    bind(runtime)["criteria_set"](analysis_id="a1", criteria=_criteria(GOOD))


@pytest.mark.parametrize("document, path, rule", [
    ({"missingCodes": [REDECLARED]}, "missingCodes[0]", "no-redeclaring-core"),
    ({"missingCodes": [STRUCTURAL_ELSEWHERE]}, "missingCodes[0]", "structural-refines-not-applicable"),
    ({"criteria": [{"id": "c", "missingCodes": [REDECLARED]}]},
     "criteria[0].missingCodes[0]", "no-redeclaring-core"),
    ({"criteria": [{"id": "c", "missingCodes": [STRUCTURAL_ELSEWHERE]}]},
     "criteria[0].missingCodes[0]", "structural-refines-not-applicable"),
    ({"reductions": [{"id": "lower-median"}]}, "reductions[0]", "no-redeclaring-core"),
    ({"missingCodes": [GOOD, GOOD]}, "missingCodes[1]", "unique-declarations"),
])
def test_each_rule_is_mirrored_over_documents(document, path, rule) -> None:
    problems = schema_problems(document)
    assert [(p.path, p.rule_id, p.family, p.severity) for p in problems] == [
        (path, rule, "schema", "error")]


def test_a_well_formed_document_has_no_schema_problems() -> None:
    assert schema_problems({"missingCodes": [GOOD],
                            "criteria": [{"id": "c", "missingCodes": [STRUCTURAL_REFINED]}]}) == []


def test_schema_rules_are_not_honesty_rules() -> None:
    """Malformed, not dishonest: the families stay apart, as the companion keeps them."""
    assert not set(SCHEMA_RULES) & set(HONESTY_RULES)
