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
tool reports when the set has moved since (#152 records the choice). Rows,
columns and the frame's wording move without a version, so each record also
keeps what each part held when it was given (:func:`covered`), and anything new
since is put to the user again the same way (#195): retiring every confirmed criterion and alternative
and declaring new ones is not something an earlier "confirm" answered.

The records live beside the document, not in it: comparanda v1 has no slot
for one (#152).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from rubricator.store import AnalysisStore

__all__ = [
    "frame_confirm", "record_decision", "gate", "ordered", "refuse_unconfirmed", "skip_record",
    "PARTS", "SCOPES", "DECISIONS", "OUT_OF_BAND_INSTRUCTIONS", "covered",
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


#: The subject fields the user is shown when asked (:data:`OUT_OF_BAND_INSTRUCTIONS`),
#: and so the ones a confirmation answered: every field ``frame_set`` writes.
_SHOWN_SUBJECT: tuple[str, ...] = ("question", "decision", "decider", "context", "ambiguities")


def covered(frame: Mapping[str, Any]) -> dict[str, Any]:
    """What each part shows the user, kept on a confirmation so a later read can tell it moved.

    The frame is a digest of its question, decision, decider, context and open
    ambiguities; the alternatives are the live rows as ``[id, digest of the
    row]``, so a changed label or description is a changed row; the criteria
    are the live column ids -- their meaning is ``criteriaVersion``'s to track.
    Read tolerantly: a damaged list is kept as what it holds.

    >>> covered({"subject": {"question": "which?"}, "criteria": [{"id": "c"}, {"id": "d", "tombstoned": True}],
    ...          "alternatives": [{"id": "k0", "label": "K"}]})["criteria"]
    ['c']
    """
    def live(key: str) -> list[Mapping[str, Any]]:
        rows = frame.get(key)
        return [r for r in rows if isinstance(r, Mapping) and not r.get("tombstoned")] \
            if isinstance(rows, list) else []

    def digest(value: Any) -> str:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                               default=str)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    subject = frame.get("subject") if isinstance(frame.get("subject"), Mapping) else {}
    return {
        "frame": digest({k: subject.get(k) for k in _SHOWN_SUBJECT}),
        "alternatives": sorted([str(a.get("id")), digest(a)] for a in live("alternatives")),
        "criteria": sorted(str(c.get("id")) for c in live("criteria")),
    }


def _moved(state: Mapping[str, Any], frame: Mapping[str, Any]) -> list[str]:
    """How each part moved past the confirmation that decides it, in words; empty when none did.

    The frame moved when its wording did. A row or column moved in when it is
    live now and was not then; one retired since was confirmed, and narrowing
    asks nothing new. A skip confirmed nothing, so it has nothing to move from.
    A record that kept nothing (written before records did) cannot say, so its
    part is put to the user again: asking is the cheap side of not knowing.
    """
    now = covered(frame)
    out = []
    for part in PARTS:
        record = state["deciding"][part]
        if record is None or record.get("mechanism") == "skip-at-open":
            continue
        kept = record.get("covered")
        then = kept.get(part) if isinstance(kept, Mapping) else None
        if part == "frame":
            if then != now[part]:
                out.append("the frame's question, decision, decider, context or ambiguities changed")
            continue
        seen = {json.dumps(x, default=str) for x in then} if isinstance(then, list) else None
        new = [x for x in now[part] if seen is None or json.dumps(x) not in seen]
        if new:
            names = ", ".join(x[0] if isinstance(x, list) else x for x in new)
            out.append(f"alternatives added or changed: {names}" if part == "alternatives"
                       else f"criteria added: {names}")
    return out


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
    if not isinstance(decision, str) or not isinstance(scope, str):
        return "invalid"
    if decision == _REQUESTED and scope in SCOPES:
        return "request"
    if decision == _SKIP and scope == "all" and record.get("mechanism") == "skip-at-open" and said("at"):
        return "open"
    if decision in DECISIONS and scope in SCOPES and said("authorId") and said("text") and said("at"):
        return "open" if DECISIONS[decision] else "close"
    return "invalid"


def ordered(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Records in write order, a tie resolved toward caution.

    Two branches can write the same sequence (each counted from what it had).
    Between those, a record that closes the gate -- or cannot be read -- sorts
    last, so a merged ``confirm`` and ``revise`` leave it closed rather than
    letting a content digest, which a caller can steer, decide.
    """
    def caution(r: Mapping[str, Any]) -> int:
        return 0 if _kind(r) in ("request", "open") else 1

    return sorted(records, key=lambda r: (r.get("_sequence", 0), caution(r)))


def _covers(record: Mapping[str, Any], part: str) -> bool:
    return _kind(record) == "invalid" or record.get("scope") in ("all", part)


def gate(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Whether scoring may start, and which record decides each part.

    ``open`` is true when every part's latest decision opens the gate. A
    request (an out-of-band question asked and not yet answered) decides
    nothing; an invalid record decides every part, closed.
    """
    records = ordered(records)
    deciding: dict[str, Mapping[str, Any] | None] = {}
    for part in PARTS:
        decided = [r for r in records if _kind(r) != "request" and _covers(r, part)]
        deciding[part] = decided[-1] if decided else None
    closed = [part for part, r in deciding.items() if r is None or _kind(r) != "open"]
    invalid = [r for r in records if _kind(r) == "invalid"]
    return {"open": not closed, "closed": closed, "deciding": deciding, "invalid": invalid}


def _standing(state: Mapping[str, Any]) -> tuple[str, bool]:
    """What stands behind an open gate, in words, and whether any part rests on the skip.

    Each part is decided by its own latest record, so a skip at open followed by a
    confirm of the criteria alone leaves the frame and alternatives resting on the
    skip: the account says which, because nobody confirmed those (#187).
    """
    groups: list[tuple[list[str], Mapping[str, Any]]] = []
    for part in PARTS:
        record = state["deciding"][part]
        for parts, other in groups:
            if other is record:
                parts.append(part)
                break
        else:
            groups.append(([part], record))

    def one(parts: Sequence[str], record: Mapping[str, Any]) -> str:
        if record.get("mechanism") == "skip-at-open":
            return (f"skipped at open, at the caller's request, at {record['at']}: nobody "
                    f"confirmed the {', '.join(parts)}")
        return f"confirmed by {record.get('authorId', 'agent')} at {record['at']}"

    skipped = any(r.get("mechanism") == "skip-at-open" for _, r in groups)
    if len(groups) == 1:
        return one(*groups[0]), skipped
    return "; ".join(f"{', '.join(parts)}: {one(parts, r)}" for parts, r in groups), skipped


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
        "covered": covered(frame),
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
    records = ordered(store.confirmations(analysis_id))
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
            moved = _moved(state, frame)
            if version in (None, current) and not moved:
                standing, skipped = _standing(state)
                return result(
                    True, "recorded", deciding, None,
                    f"{standing}; scoring is open" if skipped else f"already {standing}; nothing to ask",
                )
            # Something moved since: scoring stays open (ADR-0005's gate opens
            # both ways, #152), but the question is put again so a fresh confirm
            # of what is there now can be recorded.
            ask()
            by = deciding.get("authorId", "agent")
            return result(
                True, "recorded", deciding, OUT_OF_BAND_INSTRUCTIONS,
                f'confirmed by {by} at version "{version}"; the criteria are now at "{current}", so '
                "put them to the user again and record their answer."
                if version not in (None, current) else
                f"confirmed by {by}; since then, {'; '.join(moved)}. Put the frame and criteria "
                "to the user again and record their answer.",
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
        standing, skipped = _standing(state)
        return result(True, "out-of-band", record, None,
                      f"{standing}: scoring may start" if skipped
                      else f"confirmed by {record['authorId']}: scoring may start")
    follow = (
        "Make the changes the user asked for, then call frame_confirm with no decision to ask again."
        if decision != "confirm" else
        f"Still to confirm: {', '.join(state['closed'])}. Call frame_confirm with that scope."
    )
    return result(False, "out-of-band", record, follow,
                  f'"{decision}" recorded from {record["authorId"]}; the gate stays closed for the '
                  f"{', '.join(state['closed'])}")
