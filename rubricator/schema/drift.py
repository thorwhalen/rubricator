"""Comparing the vendored schema set with what the companion repository has published (#127).

Warn-only by design (comparanda ``cross-repo-coordination`` §3.3): a red build
because someone else released is a coordination tax with no safety benefit. So
this module only *describes* drift, as sentences, and never raises on it.

It does no I/O of its own. :func:`drift` takes the companion's published
``{version: sha256}`` as an argument, so the runtime never fetches (ADR-0010's
tool layer has no network) and a test needs no network; the fetching lives in
``scripts/check_schema_drift.py``, run on a schedule by CI.

>>> drift({1: PINS["comparanda.v1.json"].sha256})
[]
>>> drift({1: "0" * 64, 2: "1" * 64})
['version 1: the companion publishes a different file than the vendored pin; re-vendor it from its tag, or find out why a published version changed.', 'version 2 is published by the companion and is not vendored; vendoring it and adding it to EMITS is a coordinated release.']
"""

from __future__ import annotations

from typing import Mapping

from rubricator.schema.pins import PINS
from rubricator.schema.source import EMITS

__all__ = ["drift"]


def drift(published: Mapping[int, str]) -> list[str]:
    """Every way the vendored set is behind or different from ``published`` (version to sha256)."""
    lines: list[str] = []
    for version in sorted(published):
        pin = PINS.get(f"comparanda.v{version}.json")
        if version not in EMITS or pin is None:
            lines.append(
                f"version {version} is published by the companion and is not vendored; "
                "vendoring it and adding it to EMITS is a coordinated release."
            )
        elif pin.sha256 != published[version]:
            lines.append(
                f"version {version}: the companion publishes a different file than the vendored pin; "
                "re-vendor it from its tag, or find out why a published version changed."
            )
    for version in sorted(EMITS - set(published)):
        lines.append(f"version {version} is vendored but the companion no longer publishes it.")
    return lines
