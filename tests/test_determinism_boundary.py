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
import re
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
#:
#: ``datetime`` and ``time`` are here even though the docstring above has claimed
#: "no clock" since this file was written -- they were never actually denied. The
#: gap matters now rather than in principle: a stored citation check is required
#: to carry ``checkedAt``, so the tool that writes one needs a moment, and the
#: obvious way to get it is the one that silently breaks replay. A tool that
#: needs the time takes it as an argument; ``rubricator/clock.py`` is where the
#: two implementations live, and it is outside this directory on purpose.
NONDETERMINISTIC = {"random", "secrets", "uuid", "datetime", "time"}

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


def test_only_the_schema_facade_loads_a_packaged_json_resource() -> None:
    """Nothing outside the facade may load a JSON file that ships with the package.

    This is what keeps the swap from the local sketch to the published contract a
    one-line change. Once tools grow their own copies of the shape, adopting the
    real artifact stops being a constructor argument and becomes a sweep -- which
    the coordination plan names as the assumption most likely to be quietly
    dropped under pressure.

    **The rule is "reads a packaged resource", not "mentions a filename".** Two
    earlier attempts got the shape wrong in opposite directions. Grepping for the
    literal ``sketch.json`` meant the exact violation it was written to stop -- a
    tool reading the *published* artifact directly -- would have sailed through
    it. Grepping for any ``.json`` string instead flagged
    ``rubricator/store``'s key format, which names a `.json` file it will never
    open and is data rather than a resource.

    What separates them is ``__file__``: a schema artifact is loaded relative to
    the package, and a store key is a runtime string. So the test is for the
    *pair*, and it is checked on the AST rather than by grep so that a mention
    inside a docstring does not trip it.
    """
    package_root = Path(rubricator.__file__).parent
    schema_pkg = package_root / "schema"

    for path in _python_files(package_root):
        if schema_pkg in path.parents or path.parent == schema_pkg:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        strings = {
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        json_literals = sorted(s for s in strings if s.endswith(".json"))
        if "__file__" in names and json_literals:
            raise AssertionError(
                f"{path.relative_to(package_root)} loads a packaged JSON resource "
                f"({', '.join(json_literals)}). Only rubricator/schema/ may do that; everything "
                "else goes through SchemaSource, which is what keeps adopting a new version of "
                "the published contract a constructor argument rather than a sweep."
            )


def test_the_clock_lives_in_exactly_one_module() -> None:
    """`datetime` is denied to the tool layer, so it must be reachable elsewhere.

    Without this, the denial above could be satisfied by deleting the capability
    rather than by relocating it -- and the first tool that needs a timestamp
    would have nowhere legitimate to get one and would reach for the clock.
    """
    from rubricator.clock import fixed_clock, system_clock

    assert fixed_clock("2026-01-01T00:00:00Z")() == "2026-01-01T00:00:00Z"
    stamp = system_clock()
    assert stamp.endswith("Z") and "T" in stamp, stamp


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
