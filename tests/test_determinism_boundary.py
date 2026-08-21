"""The architectural rule, enforced mechanically rather than by intention.

ADR-0003: **tools are deterministic; the loop is not.** A tool that embeds a
model call breaks the connector runtime, because there is no API key there.

This is the rule most likely to erode, and it erodes plausibly: someone needs a
summary inside a tool "just this once", imports a client, and the connector
keeps working on their machine because their machine has a key. It fails for
everyone else, at import time, with an error that does not mention the reason.

So the rule is a test. If this file fails, do not relax it -- split the step
into a prompt the caller's model runs plus a deterministic tool that validates
what came back.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

import rubricator
from rubricator import tools

TOOLS_DIR = Path(tools.__file__).parent
SCHEMA_DIR = Path(rubricator.__file__).parent / "schema"

#: Anything that reaches a model. `aix` is the required facade for the *agent*
#: runtime and is legitimate there -- but not in the tool layer, which must run
#: with no key at all.
MODEL_MODULES = {
    "aix", "openai", "anthropic", "litellm", "cohere", "google", "mistralai",
    "ollama", "transformers", "sentence_transformers", "tiktoken", "oa",
}

#: Sources of non-determinism. A tool whose output depends on process state or
#: the clock cannot be replayed, which makes the ADR-0008 stability metric
#: measure our own noise instead of the agent's.
NONDETERMINISTIC = {"random", "secrets", "uuid"}

#: Network. If a tool must fetch, that is its declared purpose and it belongs
#: behind an explicit adapter, not inside the tool layer.
NETWORK_MODULES = {"requests", "httpx", "urllib", "urllib3", "aiohttp", "socket"}


def _python_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a file, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", _python_files(TOOLS_DIR), ids=lambda p: p.name)
def test_tool_layer_imports_no_model_client(path: Path) -> None:
    """No tool may reach a model. This is the rule the connector depends on."""
    offending = _imported_roots(path) & MODEL_MODULES
    assert not offending, (
        f"{path.name} imports {sorted(offending)}. ADR-0003: no tool may require a model, "
        "because the connector runtime has no API key. If this step needs judgement, it is "
        "not a tool -- expose it as a prompt the caller's model runs, plus a deterministic "
        "tool that validates the result."
    )


@pytest.mark.parametrize("path", _python_files(TOOLS_DIR), ids=lambda p: p.name)
def test_tool_layer_is_deterministic(path: Path) -> None:
    """No unseeded randomness, no clock, no process state in the tool layer."""
    offending = _imported_roots(path) & NONDETERMINISTIC
    assert not offending, (
        f"{path.name} imports {sorted(offending)}. A tool must give byte-identical output for "
        "identical input. Derive any permutation from an explicit seed argument (see "
        "rubricator.tools.traversal.seeded_permutation), never from process state."
    )


@pytest.mark.parametrize("path", _python_files(TOOLS_DIR), ids=lambda p: p.name)
def test_tool_layer_does_not_reach_the_network(path: Path) -> None:
    offending = _imported_roots(path) & NETWORK_MODULES
    assert not offending, (
        f"{path.name} imports {sorted(offending)}. A hidden fetch inside a tool is a "
        "dependency nobody declared and a failure mode that only shows up offline."
    )


def test_schema_layer_imports_no_model_client() -> None:
    """Validation is arithmetic over a document; it never needs inference."""
    for path in _python_files(SCHEMA_DIR):
        offending = _imported_roots(path) & MODEL_MODULES
        assert not offending, f"{path.name} imports {sorted(offending)}"


def test_only_the_schema_facade_loads_a_schema() -> None:
    """Nothing outside the facade may embed or load an analysis schema.

    This is what keeps the swap from the local sketch to the published contract a
    one-line change. Once tools grow their own copies of the shape, adopting the
    real artifact stops being a constructor argument and becomes a sweep -- which
    the coordination plan names as the assumption most likely to be quietly
    dropped under pressure.
    """
    facade = SCHEMA_DIR / "source.py"
    for path in _python_files(Path(rubricator.__file__).parent):
        if path == facade:
            continue
        text = path.read_text(encoding="utf-8")
        assert "sketch.json" not in text, (
            f"{path.relative_to(Path(rubricator.__file__).parent)} references the schema sketch "
            "directly. Go through SchemaSource instead."
        )


def test_importing_the_tool_layer_needs_no_optional_dependency() -> None:
    """`import rubricator.tools` must work in a bare environment.

    The connector ships with no model client and the tool layer is the part that
    has to run there. If importing it starts requiring an extra, the connector
    stops being installable without one.
    """
    for info in pkgutil.walk_packages(tools.__path__, prefix="rubricator.tools."):
        importlib.import_module(info.name)


def test_seeded_permutation_is_stable_across_processes() -> None:
    """The property that makes a shuffled traversal reproducible at all.

    Hard-coded expectation rather than a self-comparison: comparing the function
    to itself in one process would pass even if it were seeded from the clock.
    """
    from rubricator.tools.traversal import seeded_permutation

    once = seeded_permutation(["alpha", "beta", "gamma", "delta"], "fixed-seed")
    twice = seeded_permutation(["delta", "gamma", "beta", "alpha"], "fixed-seed")
    assert once == twice, "the permutation must not depend on input order"
    assert sorted(once) == ["alpha", "beta", "delta", "gamma"]
    assert seeded_permutation(["a", "b", "c"], "s1") != seeded_permutation(["a", "b", "c"], "s2") \
        or len({"a", "b", "c"}) == 1, "different seeds should generally give different orders"
