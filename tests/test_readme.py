"""The README's examples run as written.

Coding agents read the README first, so an example that has drifted from the
API teaches the wrong call to every one of them. Each ``python`` block is run
in a fresh namespace; the claims made about the surface in prose are checked
here too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCKS = re.findall(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), flags=re.S)


def test_the_readme_has_a_runnable_example() -> None:
    assert BLOCKS


@pytest.mark.parametrize("block", BLOCKS, ids=lambda b: b.splitlines()[0][:40])
def test_each_python_block_runs(block: str) -> None:
    exec(compile(block, str(README), "exec"), {})


def test_the_refusal_the_readme_describes_is_what_happens() -> None:
    from rubricator.compose import build_runtime
    from rubricator.surface import bind

    verbs = bind(build_runtime(blobs={}))
    verbs["analysis_open"](analysis_id="kettles", question="Which kettle for a small office?")
    with pytest.raises(ValueError, match="Allowed here: ambiguities, analysis_id"):
        verbs["frame_set"](analysis_id="kettles", ambiguities=[], colour="blue")


def test_the_files_and_skills_the_readme_names_exist() -> None:
    root = README.parent
    for name in ("rubricator-dev-tool-contract", "rubricator-dev-prompt-change"):
        assert (root / "skills" / name / "SKILL.md").is_file()
        assert (root / ".claude" / "skills" / name / "SKILL.md").is_file()
    for path in ("CLAUDE.md", "rubricator/surface/frozen.py", "docs/install.md",
                 "docs/connector-http.md", "docs/adr/README.md", "docs/research/README.md"):
        assert (root / path).exists(), path
    from rubricator.tools.prompts import prompts_list

    assert {p["id"] for p in prompts_list()["prompts"]} >= {
        "propose-criteria", "confirm-frame", "score-cell", "resume"}
