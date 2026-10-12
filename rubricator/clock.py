"""The clock, in one place, because a tool that reads one is not a tool.

ADR-0003 says tools are deterministic: identical input, byte-identical output.
A tool that calls ``datetime.now()`` breaks that quietly rather than loudly --
it works, its tests pass, and then the ADR-0008 stability harness measures our
own timestamps as if they were the agent's variance.

The failure is specific and it is *coming*, not hypothetical: a stored citation
check is required to carry ``checkedAt`` (ADR-0014), so the tool that writes one
needs a moment. The tempting fix is to reach for the clock where the field is
filled. The rule instead is:

    **A tool that needs the time takes it as an argument.**

That is why this module is one function and why the determinism test denies
``datetime`` and ``time`` to everything under ``rubricator/tools/``. This module
lives outside that directory on purpose: it is the composition root's business
to hand a clock down, not a tool's business to find one.

Two implementations, and neither is a stub:

- :func:`system_clock` is the real one, and the default the composition root
  wires. UTC, always -- a local-time stamp in a document shared across
  timezones is a fact nobody can compare.
- :func:`fixed_clock` returns the same moment forever. It is what a test uses,
  and it is also what makes a golden fixture reproducible, so it is a shipped
  component rather than test scaffolding.

>>> clock = fixed_clock("2026-08-22T12:00:00Z")
>>> clock(), clock()
('2026-08-22T12:00:00Z', '2026-08-22T12:00:00Z')
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

__all__ = ["Clock", "system_clock", "fixed_clock", "instant", "RFC3339"]

#: A clock is a callable returning an RFC 3339 timestamp in UTC.
#:
#: Deliberately a plain callable rather than a protocol or a class: a seam is one
#: keyword argument, and anything more here would be a registry for a thing with
#: exactly two implementations.
Clock = Callable[[], str]


def system_clock() -> str:
    """The current moment, UTC, RFC 3339 with a ``Z`` suffix.

    The ``+00:00`` that :meth:`datetime.isoformat` produces is correct and is not
    what the rest of the ecosystem writes, so it is normalised here rather than
    at each of the places that would otherwise have to remember.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fixed_clock(moment: str) -> Clock:
    """A clock that always returns ``moment``.

    Not test scaffolding: it is what makes a golden fixture byte-reproducible,
    and a fixture whose timestamps move is a fixture that cannot be diffed.
    """
    return lambda: moment


#: RFC 3339 `date-time`: date, "T", time, optional fraction, Z or an offset.
RFC3339 = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[Tt](?P<time>\d{2}:\d{2}:\d{2})(?P<frac>\.\d+)?"
    r"(?P<zone>[Zz]|[+-]\d{2}:\d{2})\Z"
)


def _fromisoformat_friendly(m: "re.Match[str]") -> str:
    """The matched moment in the one spelling every supported Python parses."""
    # Exactly six digits: 3.10's parser accepts only 3 or 6, 3.12 accepts 1-6.
    digits = (m.group("frac") or ".")[1:7]
    frac = f".{digits.ljust(6, '0')}" if digits else ""
    zone = m.group("zone")
    return f"{m.group('date')}T{m.group('time')}{frac}{'+00:00' if zone in 'Zz' else zone}"


def instant(moment: str) -> datetime:
    """An RFC 3339 moment as an aware datetime, parsed the same on every supported Python.

    Moments are compared as instants, never as strings: ``10:00:00+02:00`` is
    earlier than ``09:00:00Z``, and ``09:00:00.5Z`` is later than ``09:00:00Z``,
    and string order gets both wrong.

    >>> instant('2026-08-22T10:00:00+02:00') < instant('2026-08-22T09:00:00Z')
    True
    >>> instant('2026-08-22T09:00:00.5Z') > instant('2026-08-22T09:00:00Z')
    True
    >>> instant('2026-08-22')
    Traceback (most recent call last):
    ...
    ValueError: '2026-08-22' is not an RFC 3339 date-time such as 2026-08-22T12:00:00Z
    """
    if not isinstance(moment, str) or not RFC3339.match(moment):
        raise ValueError(f"{moment!r} is not an RFC 3339 date-time such as 2026-08-22T12:00:00Z")
    return datetime.fromisoformat(RFC3339.sub(_fromisoformat_friendly, moment))
