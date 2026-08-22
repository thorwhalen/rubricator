"""Who is asserting, and under what name.

Humans and agents are **peers** here. Each contributes an assertion with a
rationale, each is retained with an author and a timestamp, each is subject to
the same missingness vocabulary and the same evidence requirements. What
separates them is ``kind``, which a reader can see at a glance, and the
independence rung the assertion records -- not a second, parallel representation
(ADR-0011's 2026-08-22 amendment).

## Personas

A contributor may sign under a declared alternate name, because scoring a matrix
once as the operator and once as the buyer surfaces disagreements a single pass
hides. A persona is a **materialised author of its own** -- its own id, display
name and kind -- distinguished only by ``principalId`` naming whoever is behind
it.

Four rules, each because the obvious misreading is worse than the feature:

1. **A persona is not anonymity.** The principal stays in the document and is not
   hidden from readers. Someone wanting to contribute unattributed uses an
   anonymous identity and gets what that honestly offers. A persona a contributor
   *believed* was concealing them is the worst outcome available here.
2. **A persona is not an independence rung.** One person under three personas is
   one person. The collapse happens in the companion repo's
   ``effectiveIndependence``; this module's job is to make it *possible* by
   always recording the principal.
3. **A persona never changes ``kind``.** An agent asked to reason as the buyer is
   still ``agent``, with its model and prompt version unchanged. A role-played
   agent presenting as human would defeat the primary requirement -- that human
   and machine assertions be distinguishable at a glance -- in the one case where
   the confusion is deliberate.
4. **A persona is declared, never inferred** from what was written.

>>> ana = human('ana', 'Ana Ruiz')
>>> ana['kind'], ana.get('principalId')
('human', None)
>>> cfo = persona(ana, 'the sceptical CFO', acting_as='scored on cost alone')
>>> cfo['id'], cfo['principalId'], cfo['kind']
('ana:the-sceptical-cfo', 'ana', 'human')
"""

from __future__ import annotations

import re
from typing import Any, Mapping

__all__ = ["human", "agent", "persona", "sign", "AttestationMethod"]

#: How well the host knows an identity. A disclosure, never a control: nothing
#: refuses an assertion for being unverified, because the alternative is a
#: permission model this package has no business having.
AttestationMethod = str

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG.sub("-", text.strip().lower()).strip("-")


def human(
    id: str,
    display_name: str,
    *,
    attestation: AttestationMethod = "unverified",
    issuer: str | None = None,
) -> dict[str, Any]:
    """A person.

    ``unverified`` is the default because it is the truthful one: this package
    authenticates nobody, and a host that asserts nothing should leave it in
    place rather than have a better-sounding value chosen for it.
    """
    return _author(id, display_name, "human", attestation, issuer)


def agent(
    id: str,
    display_name: str,
    *,
    name: str,
    model: str | None = None,
    prompt_version: str | None = None,
    run_id: str | None = None,
    attestation: AttestationMethod = "unverified",
) -> dict[str, Any]:
    """An agent run.

    ``model``, ``prompt_version`` and ``run_id`` are what make a machine
    assertion re-runnable, and their absence is what makes one unfalsifiable.
    They are optional here because the connector genuinely may not know its own
    model id -- but a runtime that *does* know and omits them is discarding the
    only handle anyone has on why a number came out the way it did.
    """
    author = _author(id, display_name, "agent", attestation, None)
    author["agent"] = {
        k: v
        for k, v in {
            "name": name,
            "model": model,
            "promptVersion": prompt_version,
            "runId": run_id,
        }.items()
        if v is not None
    }
    return author


def persona(
    principal: Mapping[str, Any],
    display_name: str,
    *,
    acting_as: str | None = None,
) -> dict[str, Any]:
    """An alternate signing identity for an existing author.

    Takes the principal rather than an id so that ``kind`` and the agent block
    are carried over rather than re-supplied -- rule 3 becomes impossible to
    violate by forgetting, instead of being a thing to remember.
    """
    if principal.get("principalId"):
        raise ValueError(
            f'"{principal["id"]}" is itself a persona of "{principal["principalId"]}". '
            "Personas do not nest: a persona of a persona is still one person, and a chain "
            "would make the collapse that keeps agreement statistics honest depend on how "
            "deep it went. Create the new persona from the principal instead."
        )
    author: dict[str, Any] = {
        "id": f"{principal['id']}:{_slug(display_name)}",
        "displayName": display_name,
        # Rule 3: never changes kind. An agent reasoning as the buyer is an agent.
        "kind": principal["kind"],
        # Rule 1: the principal is retained and is not hidden.
        "principalId": principal["id"],
    }
    if acting_as:
        author["actingAs"] = acting_as
    if "agent" in principal:
        author["agent"] = dict(principal["agent"])
    if "attestation" in principal:
        author["attestation"] = dict(principal["attestation"])
    return author


def sign(
    author: Mapping[str, Any],
    *,
    at: str,
    assertion_id: str,
    value: Any = None,
    missing: Mapping[str, Any] | None = None,
    justification: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    independence: str | None = None,
) -> dict[str, Any]:
    """Build one assertion, signed by ``author``.

    ``at`` is passed in rather than read from a clock, because this is called
    from the tool layer and a tool that reads a clock cannot be replayed. See
    :mod:`rubricator.clock`.

    Exactly one of ``value`` and ``missing`` is required: an assertion that says
    nothing is not an assertion, which is the no-bare-nulls rule at the level
    where it actually bites.

    ``independence`` is deliberately optional **with no default**. Defaulting it
    to the most independent rung is how five draws of one model come to be stored
    as five raters, and once that is written down nothing in the document says
    otherwise. Absent means unknown, and everything downstream treats unknown as
    not-independent.
    """
    if (value is None) == (missing is None):
        raise ValueError(
            "an assertion carries exactly one of a value and a qualified absence. "
            + (
                "Both were given."
                if value is not None
                else "Neither was given -- if the answer is not known, say which kind of blank "
                'it is: "not-evidenced" when the sources are silent, "indeterminate" when they '
                'conflict, "not-assessed" when nobody has looked yet.'
            )
        )
    assertion: dict[str, Any] = {
        "id": assertion_id,
        "authorId": author["id"],
        "at": at,
        "evidence": list(evidence or []),
        "version": 1,
    }
    if value is not None:
        assertion["value"] = value
    if missing is not None:
        assertion["missing"] = dict(missing)
    if justification:
        assertion["justification"] = justification
    if independence is not None:
        assertion["independence"] = independence
    return assertion


def _author(
    id: str,
    display_name: str,
    kind: str,
    attestation: AttestationMethod,
    issuer: str | None,
) -> dict[str, Any]:
    author: dict[str, Any] = {"id": id, "displayName": display_name, "kind": kind}
    stamp: dict[str, Any] = {"method": attestation}
    if issuer:
        stamp["issuer"] = issuer
    author["attestation"] = stamp
    return author
