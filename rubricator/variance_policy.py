"""The two variance policies of ADR-0018, as named configurations rather than branches (#103).

A deployed agent can spend calls and wait; a connector has one shared transcript
and a human watching. One policy would bankrupt the one or waste the other, so
each runtime gets a :class:`VariancePolicy` -- :data:`DEPLOYED` and
:data:`CONNECTOR` -- and every consumer reads the policy it was handed. Nothing
asks "which runtime is this"; that is how the difference stays visible and
testable. A policy is data: a different one is a keyword argument, not an edit.

The prohibitions of ADR-0018 hold in both and are checked when a policy is built,
so a configuration that breaks one cannot exist: never a mean (a reduction is an
order statistic, :data:`rubricator.tools.aggregate.REDUCTIONS`), never a point
reduction over a polarised cell (``allow_contested_reduction`` is not a policy
field and stays the caller's explicit, per-call choice), and never an agreement
label that calls in-session draws inter-rater (the wording is
:func:`rubricator.independence.agreement`'s, not the policy's).

The adaptive stopping rule is **provisional**: ``adaptive_stop_confirmed`` is
``False`` until the harness arm of #41 has measured whether stopping at
agreement under-samples the tail that decides ``contested``. It is a field, so
confirming or amending it is one edit here.

>>> DEPLOYED.repeats, DEPLOYED.early_stop_at, DEPLOYED.escalate_to
(5, 3, 9)
>>> CONNECTOR.repeats, CONNECTOR.adaptive
(1, False)
>>> repeats_wanted(DEPLOYED, [3, 3, 3])
0
>>> repeats_wanted(DEPLOYED, [3, 3, 4])
2
>>> repeats_wanted(DEPLOYED, [1, 3, 3, 4, 5], review_flagged=True)
4
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from rubricator.tools.aggregate import DEFAULT_REDUCTION, REDUCTIONS, _is_a_mean
from rubricator.tools.traversal import TraversalOrder

__all__ = [
    "CONNECTOR",
    "DEPLOYED",
    "POLICIES",
    "VariancePolicy",
    "policy_for",
    "repeats_wanted",
]

#: Steps the connector takes after its single pass, in order (ADR-0018).
CONNECTOR_STEPS: tuple[str, ...] = ("review", "budget", "re-score", "disclose")


@dataclass(frozen=True)
class VariancePolicy:
    """How many times, in what order, and how a cell is reduced; see the module docstring."""

    name: str
    traversal: TraversalOrder = "cell-wise"
    #: A seeded permutation per repeat; turning it off repeats one order bias.
    shuffle: bool = True
    #: ``k``: the repeats a cell gets before any adaptive rule acts.
    repeats: int = 1
    #: Halt at this many draws when they agree; ``None`` means no early stop.
    early_stop_at: int | None = None
    #: Repeats for a cell the review step flags; ``None`` means never escalate.
    escalate_to: int | None = None
    reduction: str = DEFAULT_REDUCTION
    #: Whether the report is the full stability report (all three views).
    full_stability_report: bool = False
    #: What follows the pass, for a policy that is a procedure rather than a budget.
    steps: tuple[str, ...] = ()
    #: Whether a re-scoring pass is shown the prior scores.
    rescore_shows_prior: bool = False
    #: ``False`` until #41 has measured what stopping on agreement does to the tail.
    adaptive_stop_confirmed: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.repeats, bool) or not isinstance(self.repeats, int) or self.repeats < 1:
            raise ValueError(f"policy {self.name!r}: repeats must be 1 or more, got {self.repeats!r}")
        if _is_a_mean(self.reduction) or self.reduction not in REDUCTIONS:
            raise ValueError(
                f"policy {self.name!r}: reduction {self.reduction!r} is not an order statistic "
                f"({', '.join(REDUCTIONS)}); a mean is never a policy"
            )
        if self.early_stop_at is not None and not 2 <= self.early_stop_at <= self.repeats:
            raise ValueError(
                f"policy {self.name!r}: early_stop_at={self.early_stop_at!r} must lie in "
                f"2..repeats ({self.repeats})"
            )
        if self.escalate_to is not None and self.escalate_to <= self.repeats:
            raise ValueError(
                f"policy {self.name!r}: escalate_to={self.escalate_to!r} must exceed repeats "
                f"({self.repeats})"
            )

    @property
    def adaptive(self) -> bool:
        """Whether the number of draws depends on what the draws said."""
        return self.early_stop_at is not None or self.escalate_to is not None

    def with_(self, **changes: Any) -> "VariancePolicy":
        """A copy with ``changes``; validated like any other policy."""
        return replace(self, **changes)


DEPLOYED = VariancePolicy(
    name="deployed",
    repeats=5,
    early_stop_at=3,
    escalate_to=9,
    full_stability_report=True,
)

CONNECTOR = VariancePolicy(
    name="connector",
    repeats=1,
    steps=CONNECTOR_STEPS,
    rescore_shows_prior=False,
)

#: The policies by runtime name; a new runtime adds a row.
POLICIES: Mapping[str, VariancePolicy] = {p.name: p for p in (DEPLOYED, CONNECTOR)}


def policy_for(runtime: str) -> VariancePolicy:
    """The policy for ``runtime`` (``deployed`` or ``connector``)."""
    try:
        return POLICIES[runtime]
    except KeyError:
        raise ValueError(
            f"no variance policy for runtime {runtime!r}; known: {', '.join(POLICIES)}"
        ) from None


def repeats_wanted(
    policy: VariancePolicy, draws: Sequence[Any], *, review_flagged: bool = False
) -> int:
    """How many more draws of one cell ``policy`` wants, given the values drawn so far.

    ``0`` means stop. Agreement is every draw equal. Without an adaptive rule the
    answer is simply ``repeats`` minus what is held; with one, a cell whose first
    ``early_stop_at`` draws agree stops there, and a cell the review flagged goes on
    to ``escalate_to``. Pure: a function of the values and the policy.
    """
    held = len(draws)
    target = policy.repeats
    if policy.early_stop_at is not None and held >= policy.early_stop_at:
        if len(set(draws[: policy.early_stop_at])) == 1:
            return 0
    if review_flagged and policy.escalate_to is not None:
        target = policy.escalate_to
    return max(0, target - held)
