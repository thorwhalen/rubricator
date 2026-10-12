"""Content-hash pins for the companion repository's vendored artifacts.

The vendored files under ``rubricator/schema/comparanda/`` are copies of what the
companion repository published at an **immutable tag**, not of whatever its
``main`` holds today. The tag alone does not stop drift on this side: a
hand-edit, or a re-copy from a moving branch, would leave a file that still says
"v1" and is a different contract. That has already happened once -- the
pre-freeze artifact and the frozen one both called themselves v1.

So each file is pinned by the sha256 of its bytes, together with the URL it was
copied from. :func:`pin_problems` compares the two, and a test runs it.

Re-vendoring is therefore three steps, and none is optional: download from the
tag URL, replace the file, update its pin here. A changed hash without a changed
source URL is a re-copy from somewhere else, and a reviewer should ask why.

This is the content-hash half of the version-handshake mechanism (#127). Serving
each version as a resource, lowest-version emission and the scheduled drift
check against the companion's published ``latest`` remain there.

>>> pin_problems()
[]
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

__all__ = ["Pin", "PINS", "SCHEMA_TAG", "pin_problems"]

#: The companion repository's tag the vendored artifacts were copied from.
SCHEMA_TAG = "schema-v1"

_RAW = f"https://raw.githubusercontent.com/thorwhalen/comparanda/{SCHEMA_TAG}/schema"

_VENDORED_DIR = Path(__file__).parent / "comparanda"


@dataclass(frozen=True)
class Pin:
    """Where a vendored file came from, and what its bytes hash to."""

    source: str
    sha256: str


#: One pin per vendored file, keyed by its file name under ``comparanda/``.
PINS: Mapping[str, Pin] = {
    "comparanda.v1.json": Pin(
        source=f"{_RAW}/comparanda.v1.json",
        sha256="c609bae104aa321583a387ef37b652c598846ca16bd913edd5e2cf6d4d7ac805",
    ),
    "vocabularies.v1.json": Pin(
        source=f"{_RAW}/vocabularies.v1.json",
        sha256="e42cd002779d0bda30d713c42bced3123aeee98ed008fa57e0ba84b30d7c4138",
    ),
}


def pin_problems(
    pins: Mapping[str, Pin] = PINS, *, directory: Path = _VENDORED_DIR
) -> list[str]:
    """Every way the vendored directory disagrees with its pins, as sentences.

    Checks both directions: a pinned file that is missing or whose bytes moved,
    and a ``.json`` file that is vendored but pinned by nobody.
    """

    def sha256_of(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    problems: list[str] = []
    for name, pin in pins.items():
        path = directory / name
        if not path.exists():
            problems.append(f"{name} is pinned but not vendored")
        elif (actual := sha256_of(path)) != pin.sha256:
            problems.append(
                f"{name} hashes to {actual}, not its pin {pin.sha256}. Re-copy it from "
                f"{pin.source}, or update the pin if the source moved on purpose."
            )
    for path in sorted(directory.glob("*.json")):
        if path.name not in pins:
            problems.append(f"{path.name} is vendored but has no pin")
    return problems
