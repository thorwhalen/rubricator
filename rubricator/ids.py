"""Minting an analysis id, in one place, because a tool that mints one is not a tool.

ADR-0017 says an ``analysis_id`` is an opaque, unguessable handle. Unguessable
means random, and ``random``/``secrets`` are denied to everything under
``rubricator/tools/`` by the determinism boundary (ADR-0010): a verb that minted
its own id would give a different result for the same input, and the ADR-0008
harness would measure that as the agent's variance.

So, exactly as with the clock (:mod:`rubricator.clock`):

    **A verb that needs a fresh id takes it as an argument.**

The composition root hands an ``IdMinter`` down, and the surface supplies the
id when the caller did not -- so a model calling ``analysis_open`` with no id
gets a handle, a replay can state the id it is reconstructing, and nothing in
the tool layer ever reaches for randomness.

Two implementations, and neither is a stub:

- :func:`random_id` is the real one and the default the composition root wires.
- :func:`sequential_ids` returns ``prefix-1``, ``prefix-2``, ... -- what a test or
  a golden fixture uses, so the ids in a fixture are stable and diffable.

>>> mint = sequential_ids("demo")
>>> mint(), mint()
('demo-1', 'demo-2')
"""

from __future__ import annotations

import secrets
from itertools import count
from typing import Callable

__all__ = ["IdMinter", "random_id", "sequential_ids"]

#: An id minter is a callable returning a fresh identifier each time it is called.
IdMinter = Callable[[], str]

#: Bytes of entropy behind a minted id. 12 bytes is 96 bits -- unguessable in the
#: ADR-0017 sense, and 16 URL-safe characters, short enough to read back.
_ENTROPY_BYTES = 12


def random_id() -> str:
    """A fresh, unguessable, URL-safe handle."""
    return secrets.token_urlsafe(_ENTROPY_BYTES)


def sequential_ids(prefix: str = "analysis") -> IdMinter:
    """``prefix-1``, ``prefix-2``, ... Stable, so a fixture can be diffed."""
    counter = count(1)
    return lambda: f"{prefix}-{next(counter)}"
