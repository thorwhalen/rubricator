"""A reusable check that a computation is byte-identical in-process and across processes (#48).

The determinism boundary (``test_determinism_boundary.py``) proves what a tool
module *imports*: no model, no clock, no randomness, no network. It cannot see
the subtler leak a reviewer misses -- a set or dict iterated into output, whose
order follows ``PYTHONHASHSEED`` -- because nothing is imported to do it. This
helper catches that by running the computation:

1. twice in this process, which catches state carried between calls;
2. once in each of several fresh processes, each under a different hash seed,
   which catches iteration-order and hash-seed leakage.

Each run's result is serialised as canonical JSON in **insertion order** (never
``sort_keys``, which would hide a dict-order leak), and every serialisation must
be equal byte for byte.

The computation is named as ``"module:function"``: a function taking no
arguments and returning a JSON-able value, importable from this directory, so a
fresh interpreter can run it with nothing passed but the name.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

__all__ = ["HASH_SEEDS", "NotReproducible", "canonical", "reproducible"]

#: The hash seeds the fresh processes run under. Fixed, so the check itself is
#: reproducible: a leak either shows under these seeds on every run or never.
HASH_SEEDS: tuple[str, ...] = ("0", "1", "2026")

_HERE = Path(__file__).resolve().parent

_RUNNER = (
    "import importlib, json, sys\n"
    "module, _, name = sys.argv[1].partition(':')\n"
    "value = getattr(importlib.import_module(module), name)()\n"
    "sys.stdout.write(json.dumps(value, sort_keys=False, ensure_ascii=True, "
    "separators=(',', ':')))\n"
)


class NotReproducible(AssertionError):
    """Two runs of one computation serialised differently."""


def canonical(value: Any) -> bytes:
    """Canonical JSON in insertion order: what "byte-identical" is measured on."""
    return json.dumps(value, sort_keys=False, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _call(ref: str) -> Any:
    module, _, name = ref.partition(":")
    return getattr(importlib.import_module(module), name)()


def _in_a_fresh_process(ref: str, seed: str) -> bytes:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(_HERE), env.get("PYTHONPATH", "")) if p)
    done = subprocess.run(
        [sys.executable, "-c", _RUNNER, ref], capture_output=True, env=env, timeout=120,
    )
    if done.returncode != 0:
        raise NotReproducible(
            f"{ref} failed in a fresh process (PYTHONHASHSEED={seed}):\n"
            f"{done.stderr.decode(errors='replace')}"
        )
    return done.stdout


def _first_difference(a: bytes, b: bytes) -> str:
    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f"first difference at byte {at}: ...{a[max(0, at - 60):at + 60]!r}... vs ...{b[max(0, at - 60):at + 60]!r}..."


def reproducible(ref: str, *, seeds: Sequence[str] = HASH_SEEDS) -> Any:
    """Run ``ref`` twice here and once per hash seed in a fresh process; return its value.

    Raises :class:`NotReproducible` naming the run that differed and where.
    Returns the parsed value of the first run, so a caller can go on to assert
    what it contains.
    """
    first = canonical(_call(ref))
    runs = {"a second call in this process": canonical(_call(ref))}
    runs.update({f"a fresh process, PYTHONHASHSEED={s}": _in_a_fresh_process(ref, s) for s in seeds})
    for where, got in runs.items():
        if got != first:
            raise NotReproducible(
                f"{ref} is not byte-identical in {where}; {_first_difference(first, got)}"
            )
    return json.loads(first)
