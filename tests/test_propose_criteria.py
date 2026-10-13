"""propose-criteria (#68): its own worked example is a proposal the tools accept as it stands.

The example is what a model copies, so it is what is held to the done-when of
#68: its criteria go to ``criteria_set`` with no repair and come back with no
definition gaps; its ladder's leaves are exactly its criteria; every reject has
a reason from the closed set; every pair of criteria refining one objective is
flagged. Prose checks pin the instructions the example cannot show.
"""

from __future__ import annotations

import json
import re

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ladder import REJECT_REASONS, leaves, proposal_problems, sibling_pairs
from rubricator.prompts import prompts
from rubricator.surface import bind

BODY = prompts()["propose-criteria"].body
EXAMPLES = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", BODY, re.S)]
KEYS = ["ladder", "rejected", "criteria", "overlaps", "groups", "provenance", "questions"]


def _section(heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", BODY, re.S | re.M)
    assert match, f"propose-criteria has no section {heading!r}"
    return match.group(1)


def _criteria_set(criteria):
    verbs = bind(build_runtime(blobs={}, now=fixed_clock("2026-10-13T12:00:00Z")))
    verbs["analysis_open"](analysis_id="a1", question="which booking system?",
                           allow_skip_confirmation=True)
    return verbs["criteria_set"](analysis_id="a1", criteria=criteria)


def test_there_is_a_worked_example() -> None:
    assert len(EXAMPLES) == 1


@pytest.mark.parametrize("example", EXAMPLES)
def test_the_criteria_go_to_criteria_set_with_no_repair_and_no_gaps(example) -> None:
    result = _criteria_set(example["criteria"])
    assert result["definitionGaps"] == [] and result["defaultedPreference"] == []
    assert result["criteria"] == [c["id"] for c in example["criteria"]]


@pytest.mark.parametrize("example", EXAMPLES)
def test_the_proposal_keeps_its_own_ladder(example) -> None:
    assert list(example) == KEYS
    assert proposal_problems(example) == []
    assert leaves(example["ladder"]) == {c["id"] for c in example["criteria"]}


@pytest.mark.parametrize("example", EXAMPLES)
def test_the_example_rejects_a_means_objective_and_flags_its_siblings(example) -> None:
    """The two behaviours a model most needs to see done, not only described."""
    reasons = {r["reason"] for r in example["rejected"]}
    assert "means-objective" in reasons and reasons <= set(REJECT_REASONS)
    assert sibling_pairs(example["ladder"], [c["id"] for c in example["criteria"]])


def test_the_reason_codes_taught_are_exactly_the_closed_set() -> None:
    taught = set(re.findall(r"^\| `([a-z-]+)` \|", _section("Reject out loud"), re.M)) - {"reason"}
    assert taught == set(REJECT_REASONS)


def test_the_ladder_is_taught_in_both_directions() -> None:
    ladder = _section("The ladder")
    assert "why is that important?" in ladder.lower() and "what do you mean by that" in ladder.lower()
    assert "**The leaves are the criteria.**" in ladder
    assert "never promoted to a criterion" in ladder and "`exclusions`" in ladder


def test_criteria_never_come_from_the_alternatives_or_from_correlation() -> None:
    where = _section("Where criteria come from")
    assert "do\nnot come from the alternatives" in where or "do not come from the alternatives" in where
    assert "correlation" in where


def test_too_many_criteria_are_grouped_never_cut() -> None:
    size = _section("Too many")
    assert "Do not drop a criterion" in size and "**count**" in size


def test_every_definition_field_is_asked_for() -> None:
    carries = _section("What every criterion carries")
    for field in ("objective", "question", "evidenceRule", "missingRules", "exclusions"):
        assert f"`{field}`" in carries
    assert "evidence condition" in carries and "never as an absence" in carries
    assert "`preference`" in carries and "never leave it to a default" in carries


def _mutated(change):
    import copy

    proposal = copy.deepcopy(EXAMPLES[0])
    change(proposal)
    return proposal_problems(proposal)


@pytest.mark.parametrize("change, says", [
    (lambda p: p["ladder"]["edges"].append({"from": "boat-colour", "to": "member-access"}),
     "leaf boat-colour is not a proposed criterion"),
    (lambda p: p["ladder"]["edges"].pop(), "criterion admin-time is not a leaf"),
    (lambda p: p["ladder"]["edges"].append({"from": "member-access", "to": "nowhere"}),
     "which is not a declared objective"),
    (lambda p: p["ladder"]["edges"].append({"from": "member-access", "to": "member-access"}),
     "loops back on itself"),
    (lambda p: p["overlaps"].clear(), "mobile-booking and short-notice-booking both refine member-access"),
    (lambda p: p["overlaps"][0].update(probe=""), "carries no indifference question"),
    (lambda p: p["rejected"].append({"label": "x", "reason": "too-many"}), "'too-many' is not one of"),
    (lambda p: p["rejected"].append({"label": "x", "reason": "merged-into", "mergedInto": "ghost"}),
     "names no proposed criterion"),
    (lambda p: p["criteria"][2]["definition"].update(exclusions=["The price."]),
     "no exclusion of admin-time begins with the means objective's label"),
    (lambda p: p["rejected"][0].update(label="the"), "no exclusion of admin-time begins"),
    (lambda p: p["rejected"][0].update(label=" "), "rejected[0]: has no label"),
    (lambda p: p["ladder"]["objectives"].append({"id": "safety", "text": "s"}) or
     p["ladder"]["edges"].append({"from": "mobile-booking", "to": "safety"}),
     "mobile-booking refines member-access, safety"),
    (lambda p: p["ladder"]["objectives"].append({"id": "admin-time", "text": "t"}),
     "admin-time is declared both as an objective and as a criterion"),
    (lambda p: p["criteria"][0]["definition"].update(exclusions=[]), "mobile-booking has no exclusions"),
    (lambda p: p["criteria"][0]["definition"].update(missingRules=[]), "mobile-booking has no missingRules"),
    (lambda p: p["criteria"].append(dict(p["criteria"][0])), "mobile-booking is proposed twice"),
    (lambda p: p["groups"][0].update(size=3), "member-access has 2 criteria under it"),
    (lambda p: p["groups"].pop(), "committee-workload is not reported with its size"),
    (lambda p: p["provenance"][0].pop("quote"), "quotes nothing the user said"),
    (lambda p: p["provenance"].pop(), "criterion admin-time has no provenance"),
])
def test_each_broken_proposal_is_named(change, says) -> None:
    problems = _mutated(change)
    assert any(says in p for p in problems), problems


@pytest.mark.parametrize("change", [
    lambda p: p["ladder"]["objectives"].append({"text": "no id"}),
    lambda p: p["ladder"].update(edges=None),
    lambda p: p.update(criteria=None, rejected=None, groups=None),
    lambda p: p["criteria"][0]["definition"].update(exclusions=None),
    lambda p: p["overlaps"].append("not an object"),
    lambda p: p["overlaps"].append({"criteria": ["mobile-booking", None], "via": "member-access"}),
    lambda p: p["ladder"]["edges"].append({"to": "member-access"}),
    lambda p: p.update(ladder="not a ladder"),
])
def test_a_malformed_proposal_is_reported_never_raised(change) -> None:
    """A model's output is read here; one bad answer must not stop a whole grading run."""
    assert isinstance(_mutated(change), list)


def test_the_recorded_evaluation_still_grades_as_recorded() -> None:
    """A change to the checker that moved the published numbers would otherwise go unnoticed."""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("grader", root / "scripts/propose_criteria_adherence.py")
    grader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grader)
    frames = json.loads((root / "docs/evaluation/propose-criteria/frames.json").read_text())
    for arm in ("sonnet", "haiku"):
        path = root / f"docs/evaluation/propose-criteria/2026-10-13/out-v1-{arm}.json"
        row = grader.grade(frames, json.loads(path.read_text()))
        assert all(hits == total for hits, total in (v.split("/") for v in row.values())), (arm, row)
