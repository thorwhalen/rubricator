"""score-cell's emitted object is a cell ``measures_write`` stores with no repair (#72, #154).

The prompt's worked examples are the shape a model copies, so they are what is
tested: each ``json`` block in the body is parsed and its ``cell`` written
through the frozen surface exactly as it stands. A prompt whose own example the
verb refuses would teach every caller to repair the model's output by hand,
which is how keys get dropped and confidence gets folded into prose.

``confidence`` and ``dependsOn`` ride beside the cell, not inside it, because the
closed comparanda v1 cell has no slot for either (#126 asks for confidence's).
The plan is written first and never emitted (#154's recommendation).
"""

from __future__ import annotations

import json
import re

import pytest

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.prompts import prompts
from rubricator.surface import bind
from rubricator.surface.frozen import CELL

MOMENT = "2026-10-13T12:00:00Z"
AUTHOR = {"id": "scorer", "displayName": "Scorer", "kind": "agent",
          "agent": {"name": "rubricator", "promptVersion": "score-cell@2"}}
ANCHORS = [{"level": "1", "text": "a source states there is no commitment"},
           {"level": "3", "text": "a source states an undated commitment"},
           {"level": "5", "text": "a source states a dated commitment"}]
BESIDE_THE_CELL = {"confidence", "dependsOn"}
REASONING, VALUE = ("justification", "evidence"), ("value", "missing")

BODY = prompts()["score-cell"].body
EXAMPLES = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", BODY, re.S)]


def _verbs():
    verbs = bind(build_runtime(blobs={}, now=fixed_clock(MOMENT)))
    verbs["analysis_open"](analysis_id="a1", question="which vendor?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "vendor-a", "label": "Vendor A"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[
        {"id": "support-window", "label": "Support window", "anchors": ANCHORS}])
    return verbs


def test_the_prompt_shows_a_score_and_both_terminal_blanks() -> None:
    """The examples are the contract a model copies; all three shapes must be there."""
    shapes = {e["cell"].get("missing", {}).get("code", "score") for e in EXAMPLES}
    assert shapes == {"score", "not-evidenced", "indeterminate"}


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e["cell"].get("missing", {}).get("code", "score"))
def test_each_example_cell_is_written_with_no_repair(example) -> None:
    written = _verbs()["measures_write"](analysis_id="a1", contributor_id="scorer", author=AUTHOR,
                                         at=MOMENT, cells=[example["cell"]])
    assert written["written"] == 1


@pytest.mark.parametrize("example", EXAMPLES)
def test_only_confidence_and_depends_on_ride_beside_the_cell(example) -> None:
    assert set(example) - {"cell"} <= BESIDE_THE_CELL
    assert "plan" not in example and "plan" not in example["cell"]
    assert isinstance(example["dependsOn"], list), "dependsOn is elicited every time, [] when none"
    is_score = "value" in example["cell"]
    assert ("confidence" in example) == is_score, "confidence grades a score; a blank's is its code"


@pytest.mark.parametrize("example", EXAMPLES)
def test_reasoning_is_emitted_before_the_value(example) -> None:
    """ADR-0013: under constrained decoding, key order is generation order."""
    keys = list(example["cell"])
    last_reasoning = max((keys.index(k) for k in REASONING if k in keys), default=-1)
    first_value = min(keys.index(k) for k in VALUE if k in keys)
    assert last_reasoning < first_value
    assert list(example) == [k for k in ("cell", "confidence", "dependsOn") if k in example]


def test_the_examples_use_only_keys_the_frozen_cell_declares() -> None:
    """The prompt's prose names the cell's fields; a renamed field upstream fails here first."""
    declared = set(CELL["properties"])
    for example in EXAMPLES:
        assert set(example["cell"]) <= declared


def _section(heading: str) -> str:
    """The body of one ``## `` section, so a check cannot pass on a sentence elsewhere."""
    match = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", BODY, re.S | re.M)
    assert match, f"score-cell has no section {heading!r}"
    return match.group(1)


@pytest.mark.parametrize("example", EXAMPLES)
def test_each_example_obeys_the_scorers_own_rules(example) -> None:
    """The honesty rules ``measures_write`` enforces (#171), plus score-cell's stricter own.

    The verb refuses an uncited value, a blank with no note and evidence on an
    unsearched blank; score-cell further cites only spans it was handed.
    """
    cell = example["cell"]
    evidence = cell.get("evidence", [])
    assert all(span["sourceType"] in {"primary", "secondary"} for span in evidence), \
        "score-cell evidence is only spans the scorer was handed"
    assert len({span["id"] for span in evidence}) == len(evidence)
    if "value" in cell:
        assert evidence and isinstance(cell["value"], (int, float))
    else:
        assert cell["missing"].get("note")
        if cell["missing"]["code"] in {"not-assessed", "deferred"}:
            assert "evidence" not in cell


def test_the_plan_is_written_first_and_not_emitted() -> None:
    procedure = _section("Procedure")
    assert "**not emitted**" in procedure
    assert not re.search(r"`plan`", _section("What to emit"))


def test_depends_on_is_elicited_every_time_in_the_prose() -> None:
    """The examples could show ``dependsOn`` while the instruction to give it is gone."""
    asked = _section("Which other criteria did this cell turn on?")
    assert "Every cell answers this" in asked and "`dependsOn`" in asked
    assert "Always present" in _section("What to emit")


def test_the_score_is_never_hedged_toward_the_middle() -> None:
    assert "never hedged toward the middle" in _section("The rule that outranks the rest")


def test_a_downgrade_reason_has_a_countable_form() -> None:
    confidence = _section("Confidence")
    assert "`downgraded (<kind>): <span id> vs <span id>.`" in confidence
    for kind in ("superseded", "different-quantity", "different-date", "unexplained"):
        assert f"`{kind}`" in confidence
