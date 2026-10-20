"""The server instructions send a connector-only model to the prompts, and name only real ones (#216)."""

from __future__ import annotations

import re

from rubricator.mcp.server import _INSTRUCTIONS
from rubricator.prompts import prompts


def test_the_instructions_send_the_model_to_run_analysis_and_the_frame_first() -> None:
    assert "`run-analysis`" in _INSTRUCTIONS and "prompts_get" in _INSTRUCTIONS
    assert "frame_set" in _INSTRUCTIONS and "ask" in _INSTRUCTIONS


def test_every_prompt_the_instructions_name_is_served() -> None:
    stages = _INSTRUCTIONS[_INSTRUCTIONS.index("own prompt"):_INSTRUCTIONS.index("read with")]
    named = set(re.findall(r"`([a-z-]+)`", stages)) | {"run-analysis"}
    assert len(named) >= 6 and named <= set(prompts()), named - set(prompts())
