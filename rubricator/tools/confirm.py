"""The ADR-0005 step-4 gate: ``frame_confirm``, and the check every scoring write makes.

**The tool records a decision; it never makes one.** A confirmation is stored
as authored, timestamped provenance -- who, when, their words, which parts of
the analysis it covers, and the criteria-set version it was given against --
never as a boolean a model could set. Two paths carry a human decision in:

- **elicitation**, where the client declares the capability: the connector
  asks the user with a flat form and records the answer through
  :func:`record_decision`. That wiring is the connector's (#81);
- **out-of-band**, everywhere else: the first call returns instructions to ask
  the user in chat, and a second call carries the user's decision, their name
  and their verbatim reply. A decision that arrives before the question was
  asked, or without a name and the user's words, records nothing.

**The gate.** Scoring is refused until, for each of the frame, the
alternatives and the criteria, the latest decision covering it is ``confirm``
-- or the analysis was opened with ``allow_skip_confirmation``, which ADR-0005
allows by explicit instruction and never by default. A later ``revise`` or
``reject`` closes the gate again until a new ``confirm``. A criteria revision
does not: ADR-0005 says the gate opens both ways and ADR-0016 owns what a
revision costs, so the record keeps the version it was given against and the
tool reports when the set has moved since (#152 records the choice).

The records live beside the document, not in it: comparanda v1 has no slot
for one (#152).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.store import AnalysisStore

__all__ = [
    "frame_confirm", "record_decision", "gate", "refuse_unconfirmed", "skip_record",
    "PARTS", "SCOPES", "DECISIONS", "OUT_OF_BAND_INSTRUCTIONS",
]

#: The parts of an analysis a confirmation can cover; ``all`` covers every one.
PARTS: tuple[str, ...] = ("frame", "alternatives", "criteria")
SCOPES: tuple[str, ...] = ("all", *PARTS)

#: The decisions a human can give, and whether each opens the gate. ``skip`` is
#: not a human decision: it is the record ``allow_skip_confirmation`` leaves.
DECISIONS: Mapping[str, bool] = {"confirm": True, "revise": False, "reject": False}
_SKIP = "skip"
_REQUESTED = "requested"

#: What the caller's model is told to do when no human decision has arrived.
#: Specific enough to follow without further design (#57): what to show, what
#: to ask, what not to infer, and exactly how to call back.
OUT_OF_BAND_INSTRUCTIONS = (
    "Ask the user in chat before anything is scored. Show them: the question, the decision "
    "and who decides, the ambiguities still open, every alternative, and every criterion with "
    "its definition, scale and direction of preference, naming any two criteria that overlap. "
    "Ask them to answer confirm, revise (saying what to change) or reject. Do not answer for "
    "them, and do not read silence, thanks or a change of topic as consent. When they answer, "
    "call frame_confirm again with decision set to their answer, confirmed_by set to the name "
    "they go by, and confirmation_text set to their reply word for word. On revise, make the "
    "changes they asked for, then call frame_confirm with no decision to ask again."
)


def _kind(record: Mapping[str, Any]) -> str:
    """What a stored record is: ``request``, ``open``, ``close`` or ``invalid``.

    Read strictly, because the store is a shared repository a person can edit:
    a ``confirm`` opens only with an author and words, a skip only with the
    mechanism ``analysis_open`` writes, and anything else -- an unreadable file,
    an unknown decision, a missing field -- closes every part until it is
    repaired. A malformed record must never be what opens the gate.
    """
    def said(key: str) -> bool:
        return isinstance(record.get(key), str) and bool(record[key].strip())

    decision, scope = record.get("decision"), record.get("scope")
    if decision == _REQUESTED and scope in SCOPES:
        return "request"
    if decision == _SKIP and scope == "all" and record.get("mechanism") == "skip-at-open" and said("at"):
        return "open"
    if decision in DECISIONS and scope in SCOPES and said("authorId") and said("text") and said("at"):
        return "open" if DECISIONS[decision] else "close"
    return "invalid"


def _covers(record: Mapping[str, Any], part: str) -> bool:
    return _kind(record) == "invalid" or record.get("scope") in ("all", part)


def gate(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Whether scoring may start, and which record decides each part.

    ``open`` is true when every part's latest decision opens the gate. A
    request (an out-of-band question asked and not yet answered) decides
    nothing; an invalid record decides every part, closed.
    """
    deciding: dict[str, Mapping[str, Any] | None] = {}
    for part in PARTS:
        decided = [r for r in records if _kind(r) != "request" and _covers(r, part)]
        deciding[part] = decided[-1] if decided else None
    closed = [part for part, r in deciding.items() if r is None or _kind(r) != "open"]
    invalid = [r for r in records if _kind(r) == "invalid"]
    return {"open": not closed, "closed": closed, "deciding": deciding, "invalid": invalid}


def _closed_message(state: Mapping[str, Any]) -> str:
    parts = ", ".join(state["closed"])
    if state["invalid"]:
        return (
            f"{len(state['invalid'])} stored confirmation record(s) cannot be read as a decision "
            f"({', '.join(sorted(str(r.get('key', r.get('decision'))) for r in state['invalid']))}), "
            "so the gate is closed until whoever edited them repairs or removes them. "
        )
    return (
        f"the user has not confirmed the {parts} (ADR-0005 step 4), and no measure is written "
        "before they do. Call frame_confirm to put the frame and criteria to them; open the "
        "analysis with allow_skip_confirmation only if they explicitly said to skip this."
    )


def refuse_unconfirmed(store: AnalysisStore, analysis_id: str) -> None:
    """Raise unless the gate is open. Called by every scoring write, before anything."""
    state = gate(store.confirmations(analysis_id))
    if not state["open"]:
        raise ValueError("refused, nothing was written: " + _closed_message(state))


def skip_record(*, at: str) -> dict[str, Any]:
    """The record ``allow_skip_confirmation`` leaves: attributed to the agent, never a human."""
    return {
        "decision": _SKIP, "scope": "all", "authorId": "agent", "at": at,
        "text": "confirmation skipped by explicit instruction when the analysis was opened",
        "mechanism": "skip-at-open",
    }


def record_decision(
    store: AnalysisStore,
    *,
    analysis_id: str,
    at: str,
    scope: str,
    decision: str,
    author_id: str,
    text: str,
    mechanism: str,
) -> dict[str, Any]:
    """Append one authored human decision. The one writer both paths share.

    Not on the surface: the out-of-band path reaches it through
    :func:`frame_confirm`'s checks, and the elicitation path through the
    connector, which alone can know that a form was put to a person (#81).
    """
    from rubricator.criteria_versions import effective_version

    if decision not in DECISIONS or scope not in SCOPES:
        raise ValueError(f"unknown decision {decision!r} or scope {scope!r}")
    frame = store.frame(analysis_id)
    record = {
        "decision": decision, "scope": scope, "authorId": author_id, "at": at, "text": text,
        "criteriaVersion": effective_version(frame.get("criteriaVersion")),
        "mechanism": mechanism,
    }
    store.add_confirmation(analysis_id, record)
    return record


def _shown(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    # Only a record that is a decision is shown; an invalid one is named in the
    # summary instead, because its fields are whatever someone typed.
    if record is None or _kind(record) not in ("open", "close"):
        return None
    keys = ("authorId", "at", "text", "criteriaVersion", "decision", "scope", "mechanism")
    return {k: record[k] for k in keys if k in record}


def frame_confirm(
    store: AnalysisStore,
    *,
    analysis_id: str,
    at: str,
    scope: str = "all",
    decision: str | None = None,
    confirmed_by: str | None = None,
    confirmation_text: str | None = None,
) -> dict[str, Any]:
    """The step-4 gate's out-of-band path, and the resume read of what was decided.

    With no ``decision``: an open gate is reported with the record that opened
    it (``mechanism: recorded``), so a resuming session does not re-ask; a
    closed one returns instructions to ask the user in chat, and notes that
    the question was asked. With a ``decision``: it is recorded only when the
    question was asked first and ``confirmed_by`` and ``confirmation_text``
    are both given -- otherwise ``confirmed: false`` with instructions, never
    an error, and nothing is written.
    """
    from rubricator.criteria_versions import effective_version

    if scope not in SCOPES:
        raise ValueError(f'unknown scope "{scope}"; the scopes are {", ".join(SCOPES)}.')
    if decision is not None and decision not in DECISIONS:
        raise ValueError(f'unknown decision "{decision}"; the decisions are {", ".join(DECISIONS)}.')
    frame = store.frame(analysis_id)
    current = effective_version(frame.get("criteriaVersion"))
    records = store.confirmations(analysis_id)
    state = gate(records)

    def result(confirmed: bool, mechanism: str, record: Any, instructions: str | None,
               summary: str) -> dict[str, Any]:
        return {
            "analysisId": analysis_id, "confirmed": confirmed, "mechanism": mechanism,
            "record": _shown(record), "instructions": instructions, "summary": summary,
        }

    def ask() -> None:
        """Note that the question is being put to the user, once per pending question."""
        last = records[-1] if records else None
        if not (last and _kind(last) == "request" and last.get("scope") == scope):
            store.add_confirmation(analysis_id, {
                "decision": _REQUESTED, "scope": scope, "at": at, "mechanism": "out-of-band",
            })

    if decision is None:
        if state["open"]:
            deciding = state["deciding"]["criteria"]
            version = deciding.get("criteriaVersion")
            if version in (None, current):
                return result(
                    True, "recorded", deciding, None,
                    f"already confirmed by {deciding.get('authorId', 'agent')} at {deciding['at']}; "
                    "nothing to ask",
                )
            # The set has moved since: scoring stays open (ADR-0005's gate opens
            # both ways), but the question is put again so a fresh confirm of
            # the new version can be recorded.
            ask()
            return result(
                True, "recorded", deciding, OUT_OF_BAND_INSTRUCTIONS,
                f'confirmed by {deciding.get("authorId", "agent")} at version "{version}"; the criteria are '
                f'now at "{current}", so put them to the user again and record their answer.',
            )
        ask()
        last = next((r for r in reversed(records) if _kind(r) != "request"), None)
        return result(
            False, "out-of-band", last, OUT_OF_BAND_INSTRUCTIONS,
            f"not confirmed: {_closed_message(state)} Ask the user now.",
        )

    missing = [n for n, v in (("confirmed_by", confirmed_by), ("confirmation_text", confirmation_text))
               if not str(v or "").strip()]
    if missing:
        return result(
            False, "out-of-band", None, OUT_OF_BAND_INSTRUCTIONS,
            f"nothing recorded: a decision is the user's, so it needs {' and '.join(missing)} -- "
            "who gave it, and their words.",
        )
    # A decision that would open the gate must answer a question asked since
    # the last decision: one request is not a standing licence to record
    # answers. One that closes it (revise, reject) needs no fresh question --
    # the only thing a model could fabricate with it is more caution.
    last_request = max(
        (i for i, r in enumerate(records)
         if _kind(r) == "request" and r.get("scope") in ("all", scope)),
        default=-1,
    )
    unasked = last_request < 0 or any(
        _kind(r) != "request" for r in records[last_request + 1:]
    )
    if DECISIONS[decision] and unasked:
        return result(
            False, "out-of-band", None, OUT_OF_BAND_INSTRUCTIONS,
            "nothing recorded: the question has not been put to the user yet. Call frame_confirm "
            "with no decision first, follow its instructions, then call again with their answer.",
        )
    record = record_decision(
        store, analysis_id=analysis_id, at=at, scope=scope, decision=decision,
        author_id=str(confirmed_by).strip(), text=str(confirmation_text), mechanism="out-of-band",
    )
    state = gate(store.confirmations(analysis_id))
    if state["open"]:
        return result(True, "out-of-band", record, None,
                      f"confirmed by {record['authorId']}: scoring may start")
    follow = (
        "Make the changes the user asked for, then call frame_confirm with no decision to ask again."
        if decision != "confirm" else
        f"Still to confirm: {', '.join(state['closed'])}. Call frame_confirm with that scope."
    )
    return result(False, "out-of-band", record, follow,
                  f'"{decision}" recorded from {record["authorId"]}; the gate stays closed for the '
                  f"{', '.join(state['closed'])}")
