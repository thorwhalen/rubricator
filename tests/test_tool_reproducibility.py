"""Every exposed verb is byte-identical in-process and across hash seeds (#48).

The determinism boundary proves what each tool module imports; this proves what
each verb *returns and writes*, by replaying one end-to-end analysis through the
reusable helper in :mod:`determinism_helper`: twice in this process and once
under each of several hash seeds in a fresh one. A test per verb, so a failure
names the verb, and a test per tool module, so a new module cannot ship without
a scenario. The helper is shown to catch a planted set-iteration-order leak.
"""

from __future__ import annotations

import importlib

import pytest

from determinism_helper import NotReproducible, reproducible
from rubricator.surface import TOOL_REFS

VERBS = [ref.partition(":")[2] for ref in TOOL_REFS]
MODULES = sorted({ref.partition(":")[0] for ref in TOOL_REFS})


@pytest.fixture(scope="module")
def replayed():
    """The chain, already proven byte-identical across every run as a whole."""
    return reproducible("determinism_scenarios:every_verb")


@pytest.mark.parametrize("verb", VERBS)
def test_every_verb_is_replayed_and_returns_something(replayed, verb) -> None:
    assert verb in replayed, f"{verb} has no step in determinism_scenarios.every_verb; add one"
    assert replayed[verb]


@pytest.mark.parametrize("module", MODULES)
def test_every_tool_module_has_a_verb_in_the_replay(replayed, module) -> None:
    verbs = [ref.partition(":")[2] for ref in TOOL_REFS if ref.startswith(module + ":")]
    assert verbs and all(v in replayed for v in verbs)
    importlib.import_module(module)


def test_the_replay_writes_reproducible_bytes_too(replayed) -> None:
    assert any(k.endswith("/frame.json") for k in replayed["store"])


def test_the_helper_catches_a_set_iteration_order_leak() -> None:
    with pytest.raises(NotReproducible, match="PYTHONHASHSEED"):
        reproducible("determinism_scenarios:a_set_order_leak")
