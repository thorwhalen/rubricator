"""Traversal planning: deciding the order cells are scored in, deterministically.

Scoring order changes the answer. That is established, not speculated: when a
model scores several attributes in one generation, later attributes are pulled
toward earlier ones strongly enough to collapse distinct dimensions into one, and
a judgement's position in the generation degrades its accuracy. Humans show the
same family of effects -- halo, sequential contrast, joint-versus-separate
reversals -- so this is not a machine defect to apologise for; it is a property
of sequential evaluation that a careful procedure has to design around.

See ``docs/research/scoring-order-effects.md`` for the evidence and
``docs/research/findings-method.md`` for what this project does about it.

**Why a tool, and not a prompt.** Two reasons, and the second is the interesting
one:

1. A permutation from a seed is pure computation. It needs no judgement, so under
   ADR-0003 it is a tool, and being a tool means it works identically in the
   connector runtime where there is no API key.
2. **If the model chooses the order, the order is not random.** A model asked to
   "consider these in a random order" produces something correlated with its own
   priors -- which is precisely the confound being controlled for. Handing the
   model a permutation it did not choose is what converts a *systematic* order
   effect into a *random* one, and a random one averages out while a systematic
   one accumulates.

The connector gets this mitigation for free: it costs no extra model calls, only
structure. That matters, because the connector has no sampling budget to spend.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, Sequence

__all__ = ["TraversalOrder", "TraversalPlan", "plan_traversal", "seeded_permutation"]

TraversalOrder = Literal["cell-wise", "column-wise", "row-wise", "single-pass"]

#: Traversals ranked by how much cross-cell contamination they permit, least
#: first. `cell-wise` isolates every judgement by construction and is the
#: default; `single-pass` puts the whole matrix in one generation and is the
#: cheapest and the worst.
ISOLATION_RANK: dict[TraversalOrder, int] = {
    "cell-wise": 0,
    "column-wise": 1,
    "row-wise": 2,
    "single-pass": 3,
}


def seeded_permutation(items: Sequence[str], seed: str) -> list[str]:
    """Permute ``items`` reproducibly from a string seed.

    Deliberately not :mod:`random`. A global PRNG is process state, and a tool
    whose output depends on process state is not a deterministic tool -- two
    calls with the same arguments could differ, which would make the ADR-0008
    stability metric measure our own noise. Sorting by a hash of ``(seed, item)``
    depends on nothing but the arguments.

    The sort is by ``(digest, item)`` so that two items hashing identically --
    astronomically unlikely, but free to handle -- still order deterministically
    rather than by input position.

    >>> seeded_permutation(["a", "b", "c"], "s1") == seeded_permutation(["a", "b", "c"], "s1")
    True
    >>> sorted(seeded_permutation(["a", "b", "c"], "s1"))
    ['a', 'b', 'c']
    """

    def key(item: str) -> tuple[str, str]:
        digest = hashlib.sha256(f"{seed}\x00{item}".encode("utf-8")).hexdigest()
        return (digest, item)

    return sorted(items, key=key)


@dataclass(frozen=True)
class TraversalPlan:
    """An ordered list of scoring steps, plus the record of how it was made.

    ``provenance`` is not decoration. An analysis whose assertions were perturbed
    is only interpretable if a reader can tell *what* was varied and reproduce
    it, and the companion schema has a ``perturbation`` field expecting exactly
    this. A perturbation nobody recorded is indistinguishable from noise.
    """

    order: TraversalOrder
    #: Steps to execute in order. For `cell-wise`, one (alternative, criterion)
    #: pair each; for `column-wise`, one criterion with its alternatives; and so
    #: on. Always a tuple, so a plan cannot be mutated between planning and use.
    steps: tuple[tuple[str, ...], ...]
    seed: str
    provenance: dict[str, str]

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def isolation(self) -> int:
        """How much cross-cell contamination this traversal permits. Lower is better."""
        return ISOLATION_RANK[self.order]

    @property
    def model_calls(self) -> int:
        """How many generations this plan costs. The whole trade-off, in one number."""
        return len(self.steps)


def plan_traversal(
    alternatives: Sequence[str],
    criteria: Sequence[str],
    *,
    order: TraversalOrder = "cell-wise",
    seed: str = "rubricator",
    shuffle: bool = True,
) -> TraversalPlan:
    """Produce the plan for scoring a matrix.

    ``cell-wise`` is the default because it removes cross-cell anchoring *by
    construction* rather than by asking the model not to anchor. It costs
    ``len(alternatives) * len(criteria)`` generations, which is the expensive
    option, and that cost is the honest price of the isolation.

    ``shuffle`` seeds the within-plan ordering. Leave it on. Turning it off makes
    the traversal reproducible in a different and worse sense: every run carries
    the *same* order bias, so repeats agree with each other for a reason that has
    nothing to do with the evidence.

    >>> plan = plan_traversal(["a1", "a2"], ["c1", "c2"], seed="x")
    >>> len(plan), plan.order
    (4, 'cell-wise')
    >>> plan_traversal(["a1", "a2"], ["c1", "c2"], seed="x").steps == plan.steps
    True
    >>> plan_traversal(["a1", "a2"], ["c1"], order="column-wise").model_calls
    1
    """
    if not alternatives:
        raise ValueError("no alternatives to score")
    if not criteria:
        raise ValueError("no criteria to score against")

    alts = list(seeded_permutation(alternatives, f"{seed}\x01alt") if shuffle else alternatives)
    crits = list(seeded_permutation(criteria, f"{seed}\x01crit") if shuffle else criteria)

    steps: list[tuple[str, ...]]
    if order == "cell-wise":
        pairs = [(a, c) for c in crits for a in alts]
        # Re-permute the pairs too, so the plan does not silently become
        # column-wise-with-extra-calls -- adjacent cells sharing a criterion is
        # itself an ordering the model can pick up on across a session.
        keyed = seeded_permutation([f"{a}\x00{c}" for a, c in pairs], f"{seed}\x01pair") if shuffle else [
            f"{a}\x00{c}" for a, c in pairs
        ]
        steps = [tuple(k.split("\x00")) for k in keyed]
    elif order == "column-wise":
        steps = [(c, *alts) for c in crits]
    elif order == "row-wise":
        steps = [(a, *crits) for a in alts]
    elif order == "single-pass":
        steps = [tuple(alts) + tuple(crits)]
    else:  # pragma: no cover - guarded by the Literal, kept for runtime callers
        raise ValueError(f"unknown traversal order: {order!r}")

    return TraversalPlan(
        order=order,
        steps=tuple(steps),
        seed=seed,
        provenance={
            "kind": "traversal-order",
            "order": order,
            "seed": seed,
            "shuffled": str(shuffle).lower(),
            "alternatives": str(len(alternatives)),
            "criteria": str(len(criteria)),
        },
    )


def describe_tradeoff(alternatives: int, criteria: int) -> str:
    """A plain-language cost comparison, for a caller deciding what to afford.

    Written for the connector case, where there is no per-call budget to reason
    about and the real currency is the orchestrating session's patience.

    >>> print(describe_tradeoff(6, 6))
    cell-wise: 36 generations, no cross-cell contamination
    column-wise: 6 generations, alternatives contaminate each other within a criterion
    row-wise: 6 generations, criteria contaminate each other within an alternative
    single-pass: 1 generation, everything contaminates everything
    """
    return "\n".join(
        [
            f"cell-wise: {alternatives * criteria} generations, no cross-cell contamination",
            f"column-wise: {criteria} generations, alternatives contaminate each other "
            "within a criterion",
            f"row-wise: {alternatives} generations, criteria contaminate each other "
            "within an alternative",
            "single-pass: 1 generation, everything contaminates everything",
        ]
    )
