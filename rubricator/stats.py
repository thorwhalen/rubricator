"""Vendored rank and resampling statistics: pure Python, so the package never needs ``scipy``.

ADR-0008's 2026-08-21 amendment: ``scipy`` is a **test-only** extra. The
coefficients here are small enough to vendor and are cross-checked against
``scipy`` in the test suite, never imported from it at runtime, so the MCP server
installs fast and light and the evaluation suite's weight stays out of it.

Everything is deterministic given its inputs -- the bootstrap takes a seed, never
a global random state -- because a report keyed by seed (#86) is only worth its
key if the same seed reproduces the same interval.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Sequence

__all__ = ["kendall_tau_b", "bootstrap_interval", "wilson_interval"]


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float:
    """Kendall's tau-b between two paired sequences, ties corrected.

    The O(n^2) pair count: this project's sequences are criteria or analyses,
    tens long, never millions. ``nan`` when either side is constant, which is
    what ``scipy.stats.kendalltau`` returns and what a correlation of a constant
    honestly is.

    >>> kendall_tau_b([1, 2, 3, 4], [1, 2, 3, 4])
    1.0
    >>> kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1])
    -1.0
    >>> round(kendall_tau_b([1, 2, 2, 3], [1, 3, 2, 3]), 6)
    0.8
    >>> kendall_tau_b([1, float("nan"), 3], [1, 2, 3])
    nan
    """
    if len(x) != len(y):
        raise ValueError(f"kendall_tau_b needs paired sequences; got lengths {len(x)} and {len(y)}")
    if any(v != v for v in (*x, *y)):  # NaN compares unequal to itself
        return math.nan
    n = len(x)
    concordant = discordant = ties_x = ties_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = x[i] - x[j], y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
    return (concordant - discordant) / denominator if denominator else math.nan


def bootstrap_interval(
    values: Sequence[float],
    *,
    seed: int,
    resamples: int = 2000,
    level: float = 0.95,
) -> tuple[float, float]:
    """A percentile bootstrap interval for the mean of ``values``.

    **One value per analysis.** The unit resampled is whatever ``values`` holds,
    and the evaluation runner only ever hands this one number per analysis: cells
    within an analysis share a subject, a corpus and a traversal, so resampling
    cells treats correlated measurements as independent and returns an interval
    far narrower than the evidence supports (ADR-0008).

    >>> bootstrap_interval([1.0, 1.0, 1.0], seed=0)
    (1.0, 1.0)
    >>> lo, hi = bootstrap_interval([0.0, 1.0, 0.5, 0.25], seed=7)
    >>> 0.0 <= lo <= hi <= 1.0
    True
    """
    if not values:
        raise ValueError("bootstrap_interval needs at least one value")
    if not 0 < level < 1:
        raise ValueError(f"level must be strictly between 0 and 1; got {level!r}")
    if resamples < 1:
        raise ValueError(f"resamples must be at least 1; got {resamples!r}")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    tail = (1 - level) / 2
    return _quantile(means, tail), _quantile(means, 1 - tail)


def _quantile(ordered: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile of an already sorted sequence."""
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def wilson_interval(successes: int, n: int, *, level: float = 0.95) -> tuple[float, float]:
    """The Wilson score interval for a proportion.

    Per-level counts here are small (three confidence levels share a few dozen cells), and a bare
    proportion reads as precision it does not have; Wilson stays inside [0, 1] and is not
    degenerate at 0 or ``n`` successes. ``(0.0, 1.0)`` for ``n == 0``: nothing was observed.

    >>> wilson_interval(0, 0)
    (0.0, 1.0)
    >>> lo, hi = wilson_interval(8, 10)
    >>> round(lo, 3), round(hi, 3)
    (0.49, 0.943)
    >>> wilson_interval(10, 10)[1]
    1.0
    >>> wilson_interval(0, 10)[0]
    0.0
    """
    if not 0 <= successes <= n:
        raise ValueError(f"wilson_interval needs 0 <= successes <= n; got {successes} of {n}")
    if n == 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(0.5 + level / 2)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (0.0 if successes == 0 else max(0.0, centre - half),
            1.0 if successes == n else min(1.0, centre + half))
