"""The analysis verbs: plain functions, JSON in, JSON-able dict out.

**This module is the single source of truth for the tool surface.** It knows
nothing about MCP, about HTTP, or about any agent host: a wrapper references
``rubricator.tools.analysis:frame_set`` by string and gets a dict back. That is
what lets one registry feed the CLI and the MCP connector without two lists to
keep aligned -- and a parity test between two surfaces is proof that you have two
implementations.

Every function here is **deterministic** (ADR-0003). Nothing calls a model,
nothing reads a clock, nothing reaches the network. Where a step needs judgement
it is a *prompt* the caller's model runs, plus a verb here that validates what
came back. That is not a stylistic preference: the connector runtime has no API
key, so a model call inside a tool works on the author's machine and fails for
everyone else, at import time, with an error that does not mention the reason.

The moment is always an argument (``at``), never a clock -- see
:mod:`rubricator.clock`.

**Nothing is stored that the closed contract refuses (#136).** comparanda v1
closes every object, so every frame and every assertion is checked against the
vendored schema before its bytes land, and a key a verb reads past -- on a
criterion or a cell -- is refused rather than dropped. Either way the caller is
told the path and the keys that are allowed there, and nothing is written.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping, Sequence

from rubricator.contributors import sign
from rubricator.interpret.resolution import Degradation, degradation_of
from rubricator.locators import profile_problems
from rubricator.procedure import (
    check_facts,
    contradiction,
    derived_rung,
    is_rfc3339,
    resolved_procedure_id,
    refresh_procedures,
    stored_prior_applied,
    round_id,
)
from rubricator.rules import declaration_entries, declarations_for
from rubricator.schema.source import EMITS
from rubricator.schema.vocabulary import vocabulary
from rubricator.store import AnalysisNotFound, AnalysisStore
from rubricator.tools.corpus import agent_produced_names, cited_document

__all__ = [
    "analysis_open",
    "frame_set",
    "alternatives_set",
    "NEAR_DUPLICATE_THRESHOLD",
    "label_similarity",
    "near_duplicates",
    "criteria_set",
    "measures_write",
    "measures_mark_missing",
    "report_completeness",
]

#: The default level of measurement a criterion gets when it declares none.
#: A row, not a constant embedded in a function: adding a scale is appending one
#: of these, and no call site changes (ADR-0021).
SCALE_PRESETS: Mapping[str, Mapping[str, Any]] = {
    "ordinal-1-5-anchored": {
        "means": "Five ordinal levels with written evidence conditions at 1, 3 and 5.",
        "measurement": {
            "level": "ordinal",
            "preference": "increasing",
            "range": {"min": 1, "max": 5},
            "levels": [1, 2, 3, 4, 5],
        },
        "anchorsRequiredAt": ["1", "3", "5"],
    },
}

DEFAULT_SCALE = "ordinal-1-5-anchored"

#: The fields of a criterion's structured definition, in the companion's
#: spelling (comparanda #61). The shape is closed: any other key is refused.
DEFINITION_FIELDS: tuple[str, ...] = (
    "objective", "question", "evidenceRule", "missingRules", "exclusions",
)

#: The definition fields a criterion should carry to be scoreable (ADR-0016's
#: 2026-08-21 amendment). Reported as gaps by ``criteria_set``, never refused:
#: an under-defined criterion is unfinished, not dishonest (ADR-0024). Level,
#: preference and the ordinal anchors are not listed because the scale preset
#: always supplies the first two and the anchors are refused when missing.
DEFINITION_EXPECTED: tuple[str, ...] = DEFINITION_FIELDS


def _live_document(
    store: AnalysisStore, analysis_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """The merged document, or ``None`` when no live analysis has this id.

    One read rather than ``exists()`` then ``read()``: the retention window can
    end between two calls, and a reopen that raced it must start afresh rather
    than fail.

    **A contribution that cannot be merged does not lock the analysis** (#151):
    it is left out, and named beside the document.
    """
    try:
        return store.read_skipping(analysis_id)
    except AnalysisNotFound:
        return None, []


_NEEDS_A_QUESTION = (
    "a new analysis needs a question. Pass the question being decided, or the id of an "
    "existing analysis to reopen it."
)


def refuse_an_empty_open(store: AnalysisStore, arguments: Mapping[str, Any]) -> None:
    """Refuse an ``analysis_open`` that names neither an analysis nor a question.

    Run by the surface before an id is minted, so the caller hears what is
    missing rather than that a handle it never chose is unknown.
    """
    no_id = not str(arguments.get("analysis_id") or "").strip()
    if no_id and not str(arguments.get("question") or "").strip():
        raise ValueError(f"refused: {_NEEDS_A_QUESTION}")


def analysis_open(
    store: AnalysisStore,
    *,
    analysis_id: str,
    question: str | None = None,
    allow_skip_confirmation: bool = False,
    at: str | None = None,
) -> dict[str, Any]:
    """Start an analysis, or reopen one. Writes the frame and nothing else.

    An analysis exists before it has any alternatives or criteria, because the
    thing being decided is the first thing that is known and the criteria
    discussion is the valuable part (ADR-0005).

    **Reopening never overwrites.** An id the store already holds returns
    ``created: false`` with what is there, and the stage the work has reached,
    so that a resumed session -- or a model retrying a call -- cannot reset a
    matrix by opening it twice, and knows where to pick up. A new analysis needs
    a ``question``; a reopened one ignores the argument, because the question is
    the one thing a frame may not quietly change. An unknown or expired id with
    no question is refused naming the retention window, because the caller
    almost certainly expected it to be there.

    ``allow_skip_confirmation`` is ADR-0005's "skippable by explicit
    instruction, never by default": set when the analysis is created, it leaves
    a skip record (attributed to the agent, never to a human) that opens the
    step-4 gate. It cannot be added to an existing analysis -- that is what
    ``frame_confirm`` is for. ``at`` dates the skip and the document's
    ``createdAt``.

    The ``analysis_id`` is an opaque handle (ADR-0017). The surface mints one
    when the caller gives none (:mod:`rubricator.ids`); the connector's default
    store keeps an analysis for 30 days from its last write
    (:data:`rubricator.store.RETENTION_DAYS`), and export defeats that window.
    """
    from rubricator.tools.confirm import gate, skip_record
    from rubricator.tools.views import STAGES, skipped_note, stage_of

    document, skipped_files = _live_document(store, analysis_id)
    if document is not None:
        records = store.confirmations(analysis_id)
        skipped = any(r.get("decision") == "skip" for r in records)
        if allow_skip_confirmation and not (skipped and gate(records)["open"]):
            # A retry of the create that skipped is fine. Anything else would
            # be a skip added after the fact, or one that a later revise has
            # already overruled -- both silently ignored if not refused.
            raise ValueError(
                f'refused, nothing was written: "{analysis_id}" already exists, and skipping the '
                "confirmation can only be chosen when an analysis is created"
                + (", and a later decision has closed the gate since" if skipped else "")
                + ". Put the frame and criteria to the user with frame_confirm instead."
            )
        n_alt = sum(1 for a in document.get("alternatives", []) if not a.get("tombstoned"))
        n_crit = sum(1 for c in document.get("criteria", []) if not c.get("tombstoned"))
        stage = stage_of(document, confirmed=gate(records)["open"])
        summary = (
            f'reopened "{analysis_id}" at stage {stage} ({STAGES[stage][0]}): {n_alt} '
            f"alternative(s), {n_crit} criteria{skipped_note(skipped_files)}; "
            f"next: {STAGES[stage][1]}"
        )
        return {
            "analysisId": analysis_id,
            "created": False,
            "question": str(document["subject"]["question"]),
            "alternatives": n_alt,
            "criteria": n_crit,
            "stage": stage,
            "skipped": skipped_files,
            "summary": summary,
        }
    if not (question or "").strip():
        # A rule (a reopen needs something to reopen), so a ValueError -- but it
        # names the window, because an id the caller expected to find is the
        # likelier story than a new analysis with no question.
        raise ValueError(
            f'refused: no analysis "{analysis_id}" in this store. Analyses are kept for '
            f"{store.retention_days} days from their last write, so it has expired or never "
            f"existed here. To start one under this id, {_NEEDS_A_QUESTION}"
        )
    if allow_skip_confirmation and not at:
        raise ValueError("refused: a skipped confirmation is dated; pass at.")
    frame = {
        "id": analysis_id,
        "schemaVersion": min(EMITS),
        "subject": {"question": question},
        "measures": [{"name": "score"}],
        "defaultReduction": "single",
        "alternatives": [],
        "criteria": [],
        "groups": [],
        "inapplicable": [],
        "rejectedCriteria": [],
        "cells": [],
        "authors": [],
        "procedures": [],
        "rounds": [],
        "threads": [],
        "suggestions": [],
        "missingCodes": [],
        "scales": [],
        "reductions": [],
        "renditions": [],
    }
    if at:
        frame["createdAt"] = at
    _put_frame(store, analysis_id, frame)
    # A new analysis inherits no gate: a records directory left behind when a
    # frame was removed outside the surface must not confirm this one.
    store.clear_confirmations(analysis_id)
    if allow_skip_confirmation:
        store.add_confirmation(analysis_id, skip_record(at=at))
    return {
        "analysisId": analysis_id,
        "created": True,
        "question": question,
        "alternatives": 0,
        "criteria": 0,
        "stage": 1,
        "skipped": [],
        "summary": f'opened "{analysis_id}" with no alternatives and no criteria yet; next: '
        + STAGES[1][1],
    }


def frame_set(
    store: AnalysisStore,
    *,
    analysis_id: str,
    ambiguities: Sequence[str],
    decision: str | None = None,
    decider: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Record the frame: the decision, who decides, and what is still ambiguous.

    Stage 1 of ADR-0005. The rows are **not** written here: they are stage 2's
    output and :func:`alternatives_set` writes them, so that a frame can be
    settled and confirmed before anyone has enumerated anything.

    ``ambiguities`` is required to be *considered*, not required to be non-empty:
    the ADR-0005 rule is that ambiguity is surfaced rather than resolved
    silently, and a caller that has genuinely found none says so by passing an
    empty list. What is not available is not passing the argument at all and
    having the question of whether anyone looked go unrecorded.
    """
    frame = store.frame(analysis_id)
    subject = frame["subject"]
    # None leaves a field as it was; an empty string clears it. Both are
    # needed: a model re-stating the frame must not erase what it did not
    # mention, and a user must be able to withdraw a decider.
    for key, value in (("decision", decision), ("decider", decider), ("context", context)):
        if value is None:
            continue
        if value.strip():
            subject[key] = value
        else:
            subject.pop(key, None)
    subject["ambiguities"] = list(ambiguities)
    _put_frame(store, analysis_id, frame)
    n = len(subject["ambiguities"])
    return {
        "analysisId": analysis_id,
        "decision": subject.get("decision"),
        "decider": subject.get("decider"),
        "ambiguities": subject["ambiguities"],
        "summary": f"frame recorded; {n} ambiguit{'y' if n == 1 else 'ies'} left open for the user",
    }


#: How much two alternatives' labels must share before the pair is flagged as a
#: possible duplicate (#55): the overlap coefficient of their label tokens, see
#: :func:`label_similarity`. Provisional and named, so it can be settled against
#: the ADR-0008 fixtures; set for recall, because a flag costs one question to
#: the user and a missed duplicate splits one alternative's evidence in two.
NEAR_DUPLICATE_THRESHOLD = 0.75


def label_similarity(a: str, b: str) -> float:
    """The overlap coefficient of two labels' ``lex-v1`` token sets, ``|A & B| / min(|A|, |B|)``.

    Tokens, not terms: a stopword is kept, because in a label it is often the
    whole difference ("Option A" and "Option B"). Overlap rather than Jaccard, so
    a label inside a longer one ("K2", "The K2 kettle") scores 1. A label with no
    tokens matches nothing.

    >>> label_similarity("Brightwater K2", "the brightwater-k2 kettle")
    1.0
    >>> label_similarity("Option A", "Option B")
    0.5
    """
    from rubricator.lexical import tokens

    if not (isinstance(a, str) and isinstance(b, str)):
        return 0.0  # a hand-edited label of another type: the contract's to report, not a match
    left, right = set(tokens(a)), set(tokens(b))
    if not left or not right:
        return 0.0
    return round(len(left & right) / min(len(left), len(right)), 4)


def near_duplicates(alternatives: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Pairs of live alternatives whose labels reach :data:`NEAR_DUPLICATE_THRESHOLD`, by id.

    Flagged, never merged: whether two rows are one alternative is a decision
    about the frame, which is the user's (ADR-0005). Tombstoned rows are left
    out, as they are of every comparison.
    """
    live = sorted(
        (a for a in alternatives if not a.get("tombstoned")), key=lambda a: a["id"]
    )
    pairs = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            similarity = label_similarity(a.get("label", ""), b.get("label", ""))
            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                pairs.append({"a": a["id"], "b": b["id"], "similarity": similarity})
    return pairs


def alternatives_set(
    store: AnalysisStore, *, analysis_id: str, alternatives: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Declare the alternatives -- the rows -- replacing the current set.

    Stage 2 of ADR-0005. Dropping an alternative that any cell refers to is
    refused, for the same reason :func:`criteria_set` refuses to drop a scored
    criterion: a row with history is never deleted, it is tombstoned, and that
    is a separate, visible act.

    Near-duplicate alternatives are *flagged*, never merged (#55): every row is
    written as given, and :func:`near_duplicates` names the pairs whose labels
    nearly coincide, for the user to decide. Flagging an alternative with no
    source needs a slot for its source, which the input does not have yet.
    """
    frame = store.frame(analysis_id)
    ids = [a["id"] for a in alternatives]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(
            f"refused, nothing was written: alternative ids {', '.join(dupes)} appear more than "
            "once. Two rows with one id would be one row with two labels."
        )
    # Only a real drop is guarded -- a row in the stored set and not in this one
    # -- as criteria_set guards columns. Read tolerantly, so a damaged stored
    # list can still be replaced by the verb that replaces it.
    stored, intact = _stored_rows(frame.get("alternatives", []))
    dropping = set(stored) - set(ids)
    referenced, unread = _references(store, analysis_id, "alternativeId")
    # A row carries no versioned meaning, so re-declaring a scored one loses nothing.
    _refuse_a_blind_repair("alternatives", stored, intact, referenced, unread, kept=set(ids))
    dropped = sorted(dropping & referenced)
    if dropped:
        raise ValueError(
            f"refused, nothing was written: alternatives {', '.join(dropped)} would be dropped, "
            "but cells refer to them. Keep them in the set, or tombstone them."
        )
    _refuse_a_blind_drop("alternatives", dropping, unread)
    frame["alternatives"] = [dict(a) for a in alternatives]
    _put_frame(store, analysis_id, frame)
    flagged = near_duplicates(alternatives)
    summary = f"{len(ids)} alternative(s) declared"
    if flagged:
        summary += (
            f"; {len(flagged)} near-duplicate pair(s) flagged and never merged ("
            + ", ".join(f"{p['a']} / {p['b']}" for p in flagged)
            + "): ask the user whether each pair is one alternative before scoring"
        )
    return {
        "analysisId": analysis_id,
        "alternatives": ids,
        "nearDuplicates": flagged,
        "summary": summary,
    }


def criteria_set(
    store: AnalysisStore,
    *,
    analysis_id: str,
    criteria: Sequence[Mapping[str, Any]],
    editorial: Sequence[str] = (),
) -> dict[str, Any]:
    """Declare the criteria, expanding each one's named scale.

    A criterion names a scale (defaulting to the anchored 1-5 ordinal) and the
    preset expands into a complete measurement. **Authoring raises on an unknown
    name**, listing every known one, because at authoring time you are choosing
    and a silent default is a typo becoming a scale nobody meant. Reading is the
    opposite and never raises -- see :mod:`rubricator.interpret.resolution`.

    The expansion also writes a ``ScaleDeclaration`` row into the document, so a
    reader that has never heard of the scale still knows what it was.

    A criterion may carry a structured ``definition`` (``objective``,
    ``question``, ``evidenceRule``, ``missingRules: [{when, code}]``,
    ``exclusions``), emitted as given. Authoring raises on an unknown definition
    key, on a missing rule whose code neither the core vocabulary nor the
    analysis nor the criterion defines (the companion's honesty rule
    ``missing-rule-code-defined``), on an anchor keyed to a level the scale
    cannot take, and on a criterion's missing-code declaration the companion
    refuses (#140): one that redeclares a core code, one that claims
    ``structural: true`` while refining anything but the structural core code,
    or an id declared twice -- mirrored over documents in :mod:`rubricator.rules`. Fields a criterion should have and does not are *reported* in
    ``definitionGaps`` -- ADR-0024: incompleteness informs, it does not reject.

    **Direction of preference.** ``preference`` (``increasing``, ``decreasing``,
    ``target`` with a numeric ``target``, ``ordered``, ``none``) is required on
    every emitted measurement. A criterion that does not state one gets the
    preset's, and is listed in ``defaultedPreference`` so the default is seen.

    **Versioning (ADR-0016).** The first call sets ``criteriaVersion`` to
    ``"1"``. A later call that changes any existing criterion's meaning (see
    :data:`rubricator.criteria_versions.MEANING_FIELDS`) moves it forward, and
    each changed criterion's ``definedInVersion`` moves with it, so scores given
    under the old meaning are reported as superseded. ``editorial`` names the
    changed criteria whose edit moves no boundary -- the set version still
    moves, so the edit is on record, but nothing is superseded. Material is the
    default because the author is the only one who can say otherwise, and the
    cautious mistake is re-scoring a cell, not trusting a stale one. Every
    assertion written afterwards records the version it was scored against.
    Dropping a criterion that any cell refers to is refused: removing it and
    adding it back with a new meaning would otherwise slip past the version.
    """
    frame = store.frame(analysis_id)
    declared: dict[str, dict[str, Any]] = {d["id"]: d for d in frame.get("scales", [])}
    problems: list[str] = []
    out: list[dict[str, Any]] = []
    gaps: dict[str, list[str]] = {}
    defaulted: list[str] = []

    _refuse_unknown_keys(criteria, "CRITERION", root="$.criteria")
    for c in criteria:
        scale_id = c.get("scale", DEFAULT_SCALE)
        preset = SCALE_PRESETS.get(scale_id)
        if preset is None:
            known = ", ".join(sorted(SCALE_PRESETS))
            raise KeyError(
                f'unknown scale "{scale_id}" on criterion "{c.get("id")}". Known scales: {known}. '
                "To use a new one, add a preset row, or declare it in the analysis with a "
                '"broader" parent so a reader which does not implement it can still classify it.'
            )

        measurement = dict(preset["measurement"])
        measurement["scale"] = scale_id
        if "preference" in c:
            problems.extend(_apply_preference(c.get("id"), measurement, c))
        elif "target" in c:
            problems.append(
                f'criterion "{c.get("id")}" declares a "target" but no preference; a target '
                'is read only with preference "target".'
            )
        else:
            defaulted.append(c["id"])
        anchors = _anchor_levels(c.get("anchors"))
        required = list(preset["anchorsRequiredAt"])
        if required:
            if not anchors:
                problems.append(
                    f'criterion "{c.get("id")}" uses scale "{scale_id}", which requires anchors '
                    f"at levels {', '.join(required)}, and declares none. An unanchored level is "
                    "scored against taste rather than against a document."
                )
            else:
                missing_levels = [lvl for lvl in required if not str(anchors.get(lvl, "")).strip()]
                if missing_levels:
                    problems.append(
                        f'criterion "{c.get("id")}" is missing an anchor at '
                        f"{', '.join(missing_levels)}."
                    )
                measurement["anchors"] = {
                    "levels": {k: v for k, v in anchors.items()},
                    "contentHash": _anchor_hash(anchors),
                    "requires": required,
                }

        if anchors:
            problems.extend(_anchor_level_problems(c.get("id"), measurement, anchors))
        criterion_codes = [dict(d) for d in c.get("missingCodes", [])]
        definition = c.get("definition")
        if definition is not None:
            # The stored analysis-level list may be a hand edit of any shape (#169):
            # walked as declarations only, so it never locks a criteria write (#160).
            problems.extend(
                _definition_problems(
                    c.get("id"), definition,
                    [*criterion_codes, *declaration_entries(frame.get("missingCodes"))],
                )
            )
        if definition is None or isinstance(definition, Mapping):
            gap = [f for f in DEFINITION_EXPECTED if _is_blank((definition or {}).get(f))]
            if gap:
                gaps[c["id"]] = gap

        emitted = {
            "id": c["id"],
            "label": c["label"],
            "defaultMeasurement": measurement,
            "missingCodes": criterion_codes,
        }
        if isinstance(definition, Mapping):
            emitted["definition"] = _copy_definition(definition)
        # Retired, never deleted (ADR-0016): the two comparanda fields for a
        # column that stays in the set because cells refer to it.
        if c.get("tombstoned"):
            emitted["tombstoned"] = True
        if c.get("supersededBy"):
            emitted["supersededBy"] = list(c["supersededBy"])
        out.append(emitted)
        declared.setdefault(
            scale_id, {"id": scale_id, "broader": "stevens", "means": preset["means"], "params": {}}
        )

    # The companion refuses a declaration that redeclares a core code or claims
    # structural absence under another parent (#140). Only the criteria's own
    # declarations are this verb's to refuse; the analysis-level list has no
    # write path here, and a problem there is not this caller's to fix.
    from rubricator.rules import schema_problems

    problems.extend(
        f"{p.path}: {p.message} Fix: {p.fix} [{p.rule_id}]"
        for p in schema_problems({"criteria": out})
    )
    if problems:
        raise ValueError("; ".join(problems))

    if isinstance(editorial, str):
        raise TypeError("editorial is a list of criterion ids, not one string.")
    revised = _revise_versions(store, analysis_id, frame, out, editorial=editorial)

    from rubricator.criteria_versions import superseded_cells
    from rubricator.merge import merge_contributions

    frame["criteria"] = out
    frame["scales"] = [declared[k] for k in sorted(declared)]
    # Merged before the write, so anything that can raise does so with nothing
    # stored: a retry then sees the same before-state and the same revision.
    # Merged from the files that merge (#156): the superseded-cells report is a
    # report, not a guard, so a colleague's broken file leaves its cells out of
    # it -- named in ``skipped`` -- rather than refusing this write.
    contributions, skipped = store.mergeable_contributions(analysis_id, frame=frame)
    merged = merge_contributions(
        frame, contributions, contributors=store.contributors(analysis_id)
    )
    _put_frame(store, analysis_id, frame)
    superseded = superseded_cells(merged)
    summary = f'{len(out)} criteria at version "{frame["criteriaVersion"]}"'
    if revised:
        summary += f"; {len(revised)} revised"
    if superseded["count"]:
        summary += f"; {superseded['count']} cell(s) now answer an older definition"
    if gaps:
        summary += f"; {len(gaps)} under-defined"
    if skipped:
        summary += (
            f"; {len(skipped)} stored file(s) could not be merged, so their cells are not in "
            "supersededCells (see skipped)"
        )
    return {
        "analysisId": analysis_id,
        "criteria": [c["id"] for c in out],
        "criteriaVersion": frame["criteriaVersion"],
        # Lists rather than id-keyed objects, because the frozen surface closes
        # every object (ADR-0013 rule 3) and an id-keyed object cannot be closed.
        "revised": [
            {"criterionId": cid, "fields": r["fields"], "material": r["material"]}
            for cid, r in revised.items()
        ],
        "supersededCells": superseded,
        # Completeness, not a refusal: which definition fields each criterion
        # still lacks. Empty when every criterion is fully defined.
        "definitionGaps": [{"criterionId": cid, "fields": f} for cid, f in gaps.items()],
        # Criteria whose direction of preference came from the scale preset
        # rather than from the caller. Misaligned direction is a documented
        # failure of generated rubrics; a cost scored "increasing" because
        # nobody said otherwise is exactly it, so the default is made visible.
        "defaultedPreference": defaulted,
        "skipped": skipped,
        "summary": summary,
    }


def measures_write(
    store: AnalysisStore,
    *,
    analysis_id: str,
    contributor_id: str,
    author: Mapping[str, Any],
    at: str,
    cells: Sequence[Mapping[str, Any]],
    expected_criteria_version: str | None = None,
    procedure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one contributor's scored cells.

    ``procedure``, when given, states a few closed facts about the pass these
    cells belong to (:mod:`rubricator.procedure`); the tools write the procedure
    record from them and from the draws, stamp each assertion with its
    ``procedureId`` and ``roundId``, and derive the independence rung where the
    cell names none. A rung that contradicts them is refused. Agents only.

    ``expected_criteria_version``, when given, is the criteria-set version the
    caller read before scoring; a mismatch is refused, because the stamp would
    otherwise claim a version the scorer never saw.

    Writes **only that contributor's file**. Two people scoring the same matrix
    never touch the same key, which is what makes a shared git repository a
    viable backend with no locking protocol, and the merge into one document
    happens on read.
    """
    from rubricator.criteria_versions import effective_version
    from rubricator.tools.confirm import refuse_unconfirmed

    frame = store.frame(analysis_id)
    refuse_unconfirmed(store, analysis_id)
    criteria_version = effective_version(frame.get("criteriaVersion"))
    if expected_criteria_version is not None and expected_criteria_version != criteria_version:
        raise ValueError(
            f"refused, nothing was written: these scores were made against criteria version "
            f'"{expected_criteria_version}", and the set is now at "{criteria_version}". Re-read '
            "the criteria and re-score, so no score is stamped with a version it never saw."
        )
    _refuse_malformed_cells(cells)
    _refuse_malformed_author(author)
    facts = _checked_procedure(procedure, author, at)
    known = {c["id"]: c for c in frame.get("criteria", [])}
    # A blank that says nobody looked is a placeholder, not a draw of the pass: it is not
    # stamped with the procedure, derives no rung and is not counted among the repeats.
    placeholder = [_is_placeholder(c, frame) for c in cells]
    if all(placeholder):
        facts = None
    rows = {a["id"]: a for a in frame.get("alternatives", [])}
    for axis, index, verb in (
        ("criteria", known, "criteria_set"), ("alternatives", rows, "alternatives_set")
    ):
        key = "criterionId" if axis == "criteria" else "alternativeId"
        unknown = sorted({c[key] for c in cells} - set(index))
        if unknown:
            raise KeyError(
                f"refused, nothing was written: {axis} {', '.join(unknown)} are not in this "
                f"analysis. Declare them with {verb} first."
            )
    measures = {m["name"] for m in frame.get("measures", [])} or {"score"}
    problems = [
        p
        for cell in cells
        for p in _cell_problems(cell, rows, known, measures, frame)
    ]
    problems += _primary_into_agent_produced(cells, agent_produced_names(store, analysis_id))
    if problems:
        raise ValueError("refused, nothing was written: " + "; ".join(problems))
    # Judged once, before the writer's own file is read: a colleague's broken
    # file is left out as every read leaves it out, and the writer's own --
    # however it is broken -- refuses here, cleanly, instead of failing inside.
    mergeable, skipped = store.mergeable_contributions(analysis_id)
    _refuse_an_unread_own_file(store, analysis_id, contributor_id, skipped)
    contribution, introduced = _existing(store, analysis_id, contributor_id, author)
    # The record the store holds for this author, not the argument: a later call cannot
    # restate the model a stored assertion was signed under (#99).
    signer = next(a for a in contribution["authors"] if a["id"] == author["id"])
    facts = stored_prior_applied(facts, contribution, signer["id"], contributor_id)
    index = {
        (c["alternativeId"], c["criterionId"], c["measure"]): c
        for c in contribution["cells"]
    }

    added: list[tuple[tuple[str, str, str], str]] = []
    off_contract = _contract().refusals(
        _as_stored(dict(author)), pointer="/properties/authors/items", root="$.author"
    )
    for i, cell in enumerate(cells):
        key = (cell["alternativeId"], cell["criterionId"], cell.get("measure", "score"))
        target = index.setdefault(
            key,
            {"alternativeId": key[0], "criterionId": key[1], "measure": key[2], "assertions": []},
        )
        assertion_id = cell.get("assertionId") or _fresh_id(target, key)
        if any(a["id"] == assertion_id for a in target["assertions"]):
            raise ValueError(
                f'refused, nothing was written: assertion id "{assertion_id}" is already used in '
                f"cell {'/'.join(key)}. Omit assertionId to get a fresh one, or choose another."
            )
        added.append((key, assertion_id))
        cell_facts = None if placeholder[i] else facts
        independence, perturbation = _rung_for(cell, cell_facts)
        assertion = sign(
            author,
            at=at,
            assertion_id=assertion_id,
            value=cell.get("value"),
            missing=cell.get("missing"),
            justification=cell.get("justification"),
            evidence=list(cell.get("evidence", [])),
            independence=independence,
            perturbation=perturbation,
            criteria_version=criteria_version,
        )
        if cell_facts is not None:
            assertion["procedureId"] = resolved_procedure_id(facts, signer, contribution)
            rid = round_id(facts, signer["id"], contributor_id)
            if rid is not None:
                if any(a.get("roundId") == rid for a in target["assertions"]):
                    raise ValueError(
                        f"refused, nothing was written: cell {'/'.join(key)} already holds a "
                        f"draw from pass {facts['round']}. A cell's next pass is a new round "
                        "number: give this one the next unused number."
                    )
                assertion["roundId"] = rid
        off_contract += [
            _ARGUMENT_FIELD.sub(lambda m: _ARGUMENT_PATHS[m.group(1)], line)
            for line in _contract().refusals(
                _as_stored(assertion), pointer="/properties/cells/items/properties/assertions/items",
                root=f"$.cells[{i}]",
            )
        ]
        target["assertions"].append(assertion)
    if off_contract:
        raise ValueError(_OFF_CONTRACT + "; ".join(dict.fromkeys(off_contract)))

    contribution["cells"] = [index[k] for k in sorted(index)]
    if facts is not None:
        refresh_procedures(contribution, facts=facts, author=signer, contributor_id=contributor_id)
        off_contract += [
            line for field in ("procedures", "rounds")
            for line in _contract().refusals(
                _as_stored(contribution[field]), pointer=f"/properties/{field}", root=f"$.{field}"
            )
        ]
        if off_contract:
            raise ValueError(_OFF_CONTRACT + "; ".join(dict.fromkeys(off_contract)))
    _refuse_dishonest(
        store, analysis_id, contributor_id, contribution, added=added, mergeable=mergeable,
        introduced=author["id"] if introduced else None,
    )
    store.put_contribution(analysis_id, contributor_id, contribution)
    valued = sum(1 for c in cells if c.get("value") is not None)
    return {
        "analysisId": analysis_id,
        "contributorId": contributor_id,
        "written": len(cells),
        "criteriaVersion": criteria_version,
        "skipped": skipped,
        "summary": f"{len(cells)} assertion(s) written for {contributor_id}: "
        f"{valued} valued, {len(cells) - valued} qualified blank(s)" + _skipped_clause(skipped),
    }


def _is_placeholder(cell: Mapping[str, Any], frame: Mapping[str, Any]) -> bool:
    """Whether ``cell`` is a blank whose code says nobody looked (``not-assessed``, ``deferred``, a kind of them)."""
    code = (cell.get("missing") or {}).get("code") if isinstance(cell.get("missing"), Mapping) else None
    if not isinstance(code, str):
        return False
    facts = vocabulary().resolve(code, declarations_for(frame, cell.get("criterionId"))).facts
    return facts is not None and not facts.terminal


def _checked_procedure(
    procedure: Mapping[str, Any] | None, author: Mapping[str, Any], at: Any
) -> Mapping[str, Any] | None:
    """The pass facts, refused when malformed or when a human is the signer."""
    if procedure is None:
        return None
    try:
        check_facts(procedure)
    except ValueError as problem:
        raise ValueError(f"refused, nothing was written: {problem}") from None
    if author.get("kind") != "agent":
        raise ValueError(
            "refused, nothing was written: a procedure record describes an agent's pass; a human "
            "states the independence of each assertion on the cell."
        )
    if not is_rfc3339(at):
        raise ValueError(
            f"refused, nothing was written: at={at!r} is not an RFC 3339 date-time, and a "
            "procedure record orders its passes by time."
        )
    return procedure


def _rung_for(
    cell: Mapping[str, Any], facts: Mapping[str, Any] | None
) -> tuple[str | None, Mapping[str, Any] | None]:
    """The rung and perturbation a cell is signed with: the caller's, else derived from the pass."""
    independence, perturbation = cell.get("independence"), cell.get("perturbation")
    if facts is None:
        return independence, perturbation
    clash = contradiction(facts, independence)
    if clash:
        raise ValueError(f"refused, nothing was written: cell {cell['alternativeId']}/"
                         f"{cell['criterionId']}: {clash}")
    if independence is None:
        independence = derived_rung(facts, has_perturbation=perturbation is not None)
    if independence == "perturbed" and perturbation is None and facts.get("seed") is not None:
        perturbation = {"kind": "traversal-order", "seed": facts["seed"],
                        **({"detail": f"{facts['traversal']} traversal"} if facts.get("traversal") else {})}
    return independence, perturbation


def measures_mark_missing(
    store: AnalysisStore,
    *,
    analysis_id: str,
    contributor_id: str,
    author: Mapping[str, Any],
    at: str,
    code: str,
    note: str,
    criterion_ids: Sequence[str] = (),
    alternative_ids: Sequence[str] = (),
    independence: str | None = None,
    procedure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark a selection of cells as a qualified blank.

    ``code`` is validated against **the analysis's own vocabulary** -- the core
    six plus whatever it declares -- and never against a literal list here. The
    companion repository's set is open, so a list embedded in this signature
    would go stale on the first deployment that extends it.

    This is what makes "fill these two criteria and mark the rest deferred" a
    first-class instruction rather than a prompt hope, and it is what makes a
    partial analysis a valid, resumable document rather than a broken one.

    ``independence`` is needed when a marked cell already holds another live
    assertion (``independence-recorded``); a blank beside a score is two claims.

    ``procedure`` is :func:`measures_write`'s: a blank from a repeated pass is a draw
    like any other, so it is stamped with the same procedure and round, and counted
    in the repeats (#218). It is for one named cell, so ``procedure`` requires exactly one
    ``alternative_ids`` and one ``criterion_ids`` and a terminal code (someone looked): the
    default selection is the whole matrix, which "mark the rest" wants and a repeat never
    does, and ``not-assessed`` / ``deferred`` are placeholders, not draws.
    """
    if procedure is not None and not (len(criterion_ids) == 1 and len(alternative_ids) == 1):
        raise ValueError(
            "refused, nothing was written: a blank from a repeated pass is for one cell: name "
            "exactly one of alternative_ids and one of criterion_ids. A procedure on a wider "
            "selection would put a second draw beside every score in it (and a first draw "
            "where nothing was scored)."
        )
    frame = store.frame(analysis_id)
    # The default selection is every *live* row and column: a tombstoned one
    # takes no new assertions, and "mark the rest" must not fail because a row
    # was retired. One named explicitly is still refused, by measures_write.
    criteria = list(criterion_ids) or [
        c["id"] for c in frame["criteria"] if not c.get("tombstoned")
    ]
    for crit in criteria:
        declarations = declarations_for(frame, crit)
        if vocabulary().resolve(code, declarations).source == "undeclared":
            known = ", ".join(sorted(vocabulary().missing_codes))
            raise KeyError(
                f'unknown missingness code "{code}" for criterion "{crit}". Known here: {known}'
                + (f", plus {', '.join(d['id'] for d in declarations)}" if declarations else "")
                + ". Declare it on the analysis (or on that criterion) with a broader parent and "
                "what it means, so that a reader which does not implement it can still classify "
                "the blank."
            )

    if procedure is not None:
        for crit in criteria:
            facts = vocabulary().resolve(code, declarations_for(frame, crit)).facts
            if facts is not None and not facts.terminal:
                raise ValueError(
                    f'refused, nothing was written: "{code}" says nobody has looked at the cell '
                    "(or that it was set aside), so it is not a draw of a pass and carries no "
                    "procedure. Mark it without one."
                )

    alternatives = list(alternative_ids) or [
        a["id"] for a in frame["alternatives"] if not a.get("tombstoned")
    ]
    cells = [
        {
            "alternativeId": alt,
            "criterionId": crit,
            "measure": "score",
            "missing": {"code": code, "note": note},
            "justification": note,
            **({"independence": independence} if independence else {}),
        }
        for alt in alternatives
        for crit in criteria
    ]
    # `justification` is dropped for a blank: the note is where the reason lives,
    # and carrying both invites them to disagree.
    for c in cells:
        c.pop("justification")

    result = measures_write(
        store,
        analysis_id=analysis_id,
        contributor_id=contributor_id,
        author=author,
        at=at,
        cells=cells,
        procedure=procedure,
    )
    return {
        **result,
        "code": code,
        "marked": len(cells),
        "summary": f'{len(cells)} cell(s) marked "{code}" for {contributor_id}'
        + _skipped_clause(result["skipped"]),
    }


def report_completeness(store: AnalysisStore, *, analysis_id: str) -> dict[str, Any]:
    """Counts and rates over the merged document, plus what could not be read.

    ``silenceRate`` counts only **informative** absence -- "we looked and the
    sources are silent" -- and not every terminal one. Counting `withheld` here
    too would lump "we know and are not saying" in with "nobody says", and only
    the second tells a reader anything about the subject.

    Degradations are returned **beside** the counts and are never written into
    the document: they are facts about this build, and storing one would make one
    reader's gap look like a property of the data.
    """
    from rubricator.criteria_versions import superseded_cells
    from rubricator.rules import honesty_problems, schema_problems
    from rubricator.tools.views import skipped_note

    merged, skipped = store.read_skipping(analysis_id)
    declarations = schema_problems(merged)
    vocab = vocabulary()

    total = present = structural = settled = informative = outstanding = 0
    degradations: list[Degradation] = []

    # A retired row or column leaves every comparison, so its claims leave the counts
    # (#186): three scores on a removed alternative are not three valued cells.
    retired = {
        (axis, row["id"])
        for axis, key in (("alt", "alternatives"), ("crit", "criteria"))
        for row in merged.get(key, []) if row.get("tombstoned")
    }
    for cell in merged["cells"]:
        if ("alt", cell["alternativeId"]) in retired or ("crit", cell["criterionId"]) in retired:
            continue
        for assertion in cell["assertions"]:
            total += 1
            if "value" in assertion:
                present += 1
                continue
            code = assertion.get("missing", {}).get("code", "")
            resolution = vocab.resolve(code, declarations_for(merged, cell["criterionId"]))
            d = degradation_of(
                resolution,
                "missing-code",
                f"cells[{cell['alternativeId']}/{cell['criterionId']}].missing.code",
            )
            if d:
                degradations.append(d)
            facts = resolution.facts
            if facts is None:
                # Unresolvable: counted as outstanding. Over-reporting work
                # remaining is the safe direction; under-reporting it makes an
                # analysis look finished when nobody knows what the code meant.
                outstanding += 1
            elif facts.structural:
                structural += 1
            elif facts.terminal:
                settled += 1
                if facts.informative:
                    informative += 1
            else:
                outstanding += 1

    applicable = total - structural
    rate = (lambda n: n / applicable if applicable else 0.0)
    return {
        "analysisId": analysis_id,
        "total": total,
        "structural": structural,
        "applicable": applicable,
        "present": present,
        "settledAbsent": settled,
        "informativeAbsent": informative,
        "outstanding": outstanding,
        "examinedRate": rate(present + settled),
        "valuedRate": rate(present),
        "silenceRate": rate(informative),
        "degradations": [
            {"axis": d.axis, "id": d.id, "at": d.at, "because": d.because, "broader": d.broader}
            for d in degradations
        ],
        # Cells whose live scores answer an older definition of their criterion
        # (ADR-0016). Reported beside the rates rather than folded into them, so
        # the rates keep the companion's meaning.
        "supersededCells": superseded_cells(merged),
        # Not completeness: the honesty problems the write-time hook could not
        # refuse (they sit on assertions already stored). Reported here so they
        # are seen; #61's analysis_validate is where they reject.
        "honestyProblems": [
            {"path": p.path, "message": p.message, "fix": p.fix, "ruleId": p.rule_id}
            for p in honesty_problems(merged)
        ],
        # The schema family's declaration rules (#161): a missing-code declaration
        # the companion refuses -- redeclaring a core code, claiming structural
        # absence under another parent, one id declared twice. criteria_set
        # refuses them at authoring; this is where they are seen when they reach
        # the document another way -- an analysis-level list, a hand edit, an
        # import, or a frame stored before #140.
        "schemaProblems": [
            {"path": p.path, "message": p.message, "fix": p.fix, "ruleId": p.rule_id}
            for p in declarations
        ],
        "skipped": skipped,
        "summary": (
            f"{present} valued, {settled} settled blank(s), {outstanding} outstanding of "
            f"{applicable} applicable cell(s); silenceRate {rate(informative):.2f}"
            + (f"; {len(degradations)} code(s) this build could not interpret" if degradations else "")
            + (f"; {len({p.path for p in declarations})} declaration(s) the companion would "
               "refuse (see schemaProblems), which the counts above honour as written"
               if declarations else "")
            + skipped_note(skipped)
        ),
    }


def _revise_versions(
    store: AnalysisStore,
    analysis_id: str,
    frame: dict[str, Any],
    out: list[dict[str, Any]],
    *,
    editorial: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Set ``criteriaVersion`` and each ``definedInVersion`` on ``frame``/``out``.

    Raises, writing nothing, on a referenced criterion being dropped and on an
    ``editorial`` id that names no changed criterion. Returns what changed.
    """
    from rubricator.criteria_versions import meaning_changed, next_version

    # Read tolerantly, so the verb that replaces a hand-edited list can repair it
    # (#169), but never blindly: see _stored_rows (second review of #226).
    before, intact = _stored_rows(frame.get("criteria", []))
    after_ids = {c["id"] for c in out}
    referenced, unread = _references(store, analysis_id, "criterionId")
    _refuse_a_blind_repair("criteria", before, intact, referenced, unread)
    dropped = sorted((set(before) - after_ids) & referenced)
    if dropped:
        raise ValueError(
            f"criteria {', '.join(dropped)} would be dropped, but cells refer to them. Keep them "
            "in the set (change their meaning, and the scores are reported as superseded), or "
            "leave them be; a criterion with history is never deleted."
        )
    _refuse_a_blind_drop("criteria", set(before) - after_ids, unread)
    changed = {
        c["id"]: fields
        for c in out
        if c["id"] in before and (fields := meaning_changed(before[c["id"]], c))
    }
    stray = sorted(set(editorial) - set(changed))
    if stray:
        raise ValueError(
            f"editorial names {', '.join(stray)}, which did not change meaning in this call. "
            "editorial lists only the changed criteria whose edit moves no boundary."
        )

    version = frame.get("criteriaVersion")
    if changed:
        version = next_version(version)
    elif version is None:
        version = "1"
    frame["criteriaVersion"] = version
    for c in out:
        if c["id"] in changed and c["id"] not in editorial:
            c["definedInVersion"] = version
        elif before.get(c["id"], {}).get("definedInVersion") is not None:
            c["definedInVersion"] = before[c["id"]]["definedInVersion"]
        elif c["id"] not in before and before:
            # Introduced (or re-introduced) into an existing set: any score on
            # this id from before now -- a peer's file not yet pulled, a
            # dropped-then-re-added column -- answered some other question.
            c["definedInVersion"] = version
    return {
        cid: {"fields": fields, "material": cid not in editorial}
        for cid, fields in sorted(changed.items())
    }


#: Directions of preference (the companion's closed enum, ADR-0018 there).
PREFERENCES: tuple[str, ...] = ("increasing", "decreasing", "target", "ordered", "none")


def _apply_preference(
    criterion_id: Any, measurement: dict[str, Any], criterion: Mapping[str, Any]
) -> list[str]:
    """Set a stated direction of preference on ``measurement``, or say why not.

    Mirrors the companion's measurement rules: ordered levels carry a range
    (the presets always do), ``target`` needs ``range.target`` inside the range,
    and a nominal level admits only ``none``.
    """
    where = f'criterion "{criterion_id}"'
    pref = criterion["preference"]
    if pref not in PREFERENCES:
        return [f'{where} has preference "{pref}"; the directions are {", ".join(PREFERENCES)}.']
    if measurement.get("level") == "nominal" and pref != "none":
        return [f'{where} is nominal, so its only preference is "none".']
    rng = dict(measurement.get("range") or {})
    target = criterion.get("target")
    if pref == "target":
        if not isinstance(target, (int, float)) or isinstance(target, bool):
            return [f'{where} prefers a target but declares no numeric "target".']
        if not rng:
            return [f"{where} prefers a target, but its scale declares no range to hold it."]
        if not rng["min"] <= target <= rng["max"]:
            return [f"{where} has target {target} outside its range [{rng['min']}, {rng['max']}]."]
        rng["target"] = target
        measurement["range"] = rng
    elif target is not None:
        return [f'{where} declares a "target" but its preference is "{pref}", not "target".']
    measurement["preference"] = pref
    return []


def _anchor_level_problems(
    criterion_id: Any, measurement: Mapping[str, Any], anchors: Mapping[str, Any]
) -> list[str]:
    """Anchors on levels the scale cannot take (the companion's #61 check).

    Compared as strings, as the companion does: anchor keys are strings and
    levels may be numbers.
    """
    declared = [str(lvl) for lvl in measurement.get("levels", [])]
    rng = measurement.get("range")
    keys = {str(k) for k in [*anchors, *measurement.get("anchors", {}).get("requires", [])]}

    def fits(key: str) -> bool:
        if declared:
            return key in declared
        if not rng:
            return True
        try:
            n = float(key)
        except ValueError:
            return False
        return n == n and rng["min"] <= n <= rng["max"]

    bad = sorted(k for k in keys if not fits(k))
    if not bad:
        return []
    scale = f"levels: {', '.join(declared)}" if declared else f"range [{rng['min']}, {rng['max']}]"
    return [
        f'criterion "{criterion_id}" has an anchor at level(s) {", ".join(bad)}, which the scale '
        f"cannot take ({scale}). An anchor on such a level is a condition no score can ever meet."
    ]


def _definition_problems(
    criterion_id: Any, definition: Any, declarations: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Authoring checks on a structured definition: closed shape, resolvable codes."""
    where = f'criterion "{criterion_id}" definition'
    if not isinstance(definition, Mapping):
        return [f"{where} must be an object with fields {', '.join(DEFINITION_FIELDS)}."]
    problems: list[str] = []
    extra = sorted(map(str, set(definition) - set(DEFINITION_FIELDS)))
    if extra:
        problems.append(
            f"{where} has unknown field(s) {', '.join(extra)}; the fields are "
            f"{', '.join(DEFINITION_FIELDS)}. Anchors live on the scale (\"anchors\"), not here."
        )
    for f in ("objective", "question", "evidenceRule"):
        if f in definition and not isinstance(definition[f], str):
            problems.append(f"{where}.{f} must be a string.")
    exclusions = definition.get("exclusions", [])
    if not (isinstance(exclusions, list) and all(isinstance(e, str) for e in exclusions)):
        problems.append(f"{where}.exclusions must be a list of strings (empty if none).")
    rules = definition.get("missingRules", [])
    if not isinstance(rules, list):
        return [*problems, f"{where}.missingRules must be a list of {{when, code}}."]
    for k, rule in enumerate(rules):
        if not (
            isinstance(rule, Mapping)
            and set(rule) == {"when", "code"}
            and all(isinstance(rule[x], str) for x in ("when", "code"))
        ):
            problems.append(f"{where}.missingRules[{k}] must be exactly {{when: str, code: str}}.")
            continue
        if vocabulary().resolve(rule["code"], declarations).source == "undeclared":
            problems.append(
                f'{where}.missingRules[{k}] tells raters to record "{rule["code"]}", which is '
                "neither a core code nor declared on the analysis or this criterion. Name a core "
                "code, or declare it in missingCodes with a broader parent and what it means."
            )
    return problems


def _is_blank(value: Any) -> bool:
    """Absent, or a whitespace-only string. An empty *list* is an answer ("none")."""
    return value is None or (isinstance(value, str) and not value.strip())


def _cell_problems(
    cell: Mapping[str, Any],
    rows: Mapping[str, Mapping[str, Any]],
    criteria: Mapping[str, Mapping[str, Any]],
    measures: set[str],
    frame: Mapping[str, Any],
) -> list[str]:
    """Every reason ``cell`` cannot be written, each naming the cell.

    Three checks the schema cannot make because the answer is data in the frame:
    the measure is one the analysis declares; the row and the column are not
    tombstoned; and a ``score`` value is one its criterion's scale can take
    (:func:`_off_scale`). (A missingness code the document never defines is the
    ``blank-is-defined`` rule's, at the honesty stage.) And one the schema
    allows and this repository's profile does not: every evidence reference
    stays inside the ADR-0014 locator profile (:func:`profile_problems`) --
    comparanda v1 accepts ``PathSelector``, and a quote-less position.
    """
    where = f"cell {cell['alternativeId']}/{cell['criterionId']}"
    out: list[str] = []
    measure = cell.get("measure", "score")
    if measure not in measures:
        out.append(
            f'{where}: measure "{measure}" is not one this analysis declares '
            f"({', '.join(sorted(measures))})"
        )
    for label, item in (("alternative", rows[cell["alternativeId"]]),
                        ("criterion", criteria[cell["criterionId"]])):
        if item.get("tombstoned"):
            out.append(f'{where}: {label} "{item["id"]}" is tombstoned and takes no new assertions')
    # An undeclared missingness code is the ``blank-is-defined`` rule's, at the
    # honesty stage, so it is refused with the rule and its source like the others (#184).
    if measure == "score":
        problem = _off_scale(cell, criteria[cell["criterionId"]])
        if problem:
            out.append(problem)
    out += [f"{where}: {p}" for p in profile_problems(cell.get("evidence") or [])]
    return out


def _primary_into_agent_produced(
    cells: Sequence[Mapping[str, Any]], names: Mapping[str, str]
) -> list[str]:
    """Every ``primary`` reference naming a document a model wrote: secondary at best.

    ADR-0015 constraint 3. A summary, an extracted table or a prior analysis
    that re-entered the corpus is someone's reading of a source, never the
    source, however faithfully it quotes one. The marker is set at ingestion
    only, so this reads it from there (:func:`agent_produced_names`).
    """
    out = []
    for cell in cells:
        for ref in cell.get("evidence") or []:
            hit = cited_document(ref, names)
            if hit and ref.get("sourceType") == "primary":
                out.append(
                    f'cell {cell["alternativeId"]}/{cell["criterionId"]}: evidence "{ref.get("id")}" '
                    f'is "primary" but cites {hit}, which corpus_add marked agent-produced -- a '
                    "model wrote it (ADR-0015). Record it as secondary at best, or cite the "
                    "original it was made from"
                )
    return out


def _off_scale(cell: Mapping[str, Any], criterion: Mapping[str, Any]) -> str | None:
    """Why ``cell``'s score is one its criterion's scale cannot take, or ``None``.

    The frozen surface cannot bound ``value`` in the schema -- the scale is data
    (ADR-0021) and is not known when the schema is written -- so ADR-0013's
    range check lives here, against the measurement the criterion declares: the
    ``levels`` where it lists them, the ``range`` otherwise. A blank has no
    value and is never off scale. A boolean is never a number here: ``True``
    equals ``1`` in Python and would otherwise pass as a level.

    >>> crit = {"id": "c", "defaultMeasurement": {"levels": [1, 2, 3], "range": {"min": 1, "max": 3}}}
    >>> _off_scale({"alternativeId": "x", "criterionId": "c", "value": 2}, crit) is None
    True
    >>> _off_scale({"alternativeId": "x", "criterionId": "c", "value": 2.5}, crit)
    'cell x/c: value 2.5 is not one of the levels its scale declares (1, 2, 3)'
    >>> _off_scale({"alternativeId": "x", "criterionId": "c", "value": True}, crit)
    'cell x/c: value True is not one of the levels its scale declares (1, 2, 3)'
    """
    if "value" not in cell or cell["value"] is None:
        return None
    value = cell["value"]
    measurement = criterion.get("defaultMeasurement", {})
    where = f"cell {cell['alternativeId']}/{cell['criterionId']}"

    def same(a: Any, b: Any) -> bool:
        return type(a) is type(b) and a == b or (
            isinstance(a, (int, float)) and isinstance(b, (int, float))
            and not isinstance(a, bool) and not isinstance(b, bool) and a == b
        )

    levels = measurement.get("levels")
    if levels:
        if not any(same(value, lvl) for lvl in levels):
            shown = ", ".join(str(lvl) for lvl in levels)
            return f"{where}: value {value!r} is not one of the levels its scale declares ({shown})"
        return None
    rng = measurement.get("range")
    if rng:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{where}: value {value!r} is not a number, and the scale is a numeric range"
        if value < rng["min"] or value > rng["max"]:
            return f"{where}: value {value!r} is outside the scale's range {rng['min']}..{rng['max']}"
    return None


def _anchor_levels(anchors: Any) -> dict[str, str] | None:
    """Anchors as the stored ``{level: text}`` mapping, from either input shape.

    The frozen surface takes anchors as a **list** of ``{level, text}`` rows,
    because an object keyed by level cannot be closed and ADR-0013 closes every
    object a tool accepts. Python callers may still pass the mapping. Both land
    here as one shape, so nothing downstream knows there were two.

    >>> _anchor_levels([{"level": "1", "text": "a"}, {"level": 3, "text": "b"}])
    {'1': 'a', '3': 'b'}
    >>> _anchor_levels({"1": "a"})
    {'1': 'a'}
    >>> _anchor_levels(None) is None
    True
    """
    if anchors is None:
        return None
    if isinstance(anchors, Mapping):
        return {str(k): v for k, v in anchors.items()}
    rows = list(anchors)
    levels = [str(r["level"]) for r in rows]
    if len(set(levels)) != len(levels):
        raise ValueError(
            "anchors name the same level twice; one evidence condition per level."
        )
    return {str(r["level"]): r["text"] for r in rows}


def _copy_definition(definition: Mapping[str, Any]) -> dict[str, Any]:
    out = {k: definition[k] for k in DEFINITION_FIELDS if k in definition}
    if "missingRules" in out:
        out["missingRules"] = [dict(r) for r in out["missingRules"]]
    if "exclusions" in out:
        out["exclusions"] = list(out["exclusions"])
    return out


def _fresh_id(cell: Mapping[str, Any], key: tuple[str, str, str]) -> str:
    """A default assertion id not yet used in this cell.

    The first assertion gets ``alt-crit-measure``; a second one -- a re-score, a
    replication draw -- gets a ``-2`` suffix and so on, so two claims about one
    cell never share an identity.
    """
    base = "-".join(key)
    taken = {a["id"] for a in cell["assertions"]}
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _refuse_dishonest(
    store: AnalysisStore,
    analysis_id: str,
    contributor_id: str,
    contribution: Mapping[str, Any],
    *,
    added: Sequence[tuple[tuple[str, str, str], str]],
    mergeable: Sequence[tuple[str, Mapping[str, Any]]],
    introduced: str | None = None,
) -> None:
    """The write-time honesty hook (ADR-0024): refuse before the bytes land.

    Checks the document as it **would be merged** with this contribution in
    place, because the rules are cross-contributor: two people each scoring a
    cell once is fine on its own and dishonest together if neither recorded
    independence.

    **Refuses only for the assertions this call adds**, the ones the caller can
    still change -- and for the author this call introduces (``introduced``), whose
    record is the caller's own argument: an author already stored is not amended by
    a later call, so a problem on one is stored, not this call's. A problem on an assertion already stored -- this contributor's
    or anyone's -- does not block: nothing can amend a stored assertion in place,
    so refusing would lock that contributor (or everyone) out of the whole
    analysis over one cell. `comparanda` counts by difference for the same
    reason. Those problems stay visible: :func:`report_completeness` returns
    them as ``honestyProblems`` over the merged document.

    **Checked against the document readers see** (#156): ``mergeable`` is the
    contributions every read merges, so a colleague's file that cannot be
    merged is left out here too, and the write's result names it. The cost is
    deliberate and stated: a claim in that file is not seen by this check, so a
    second score on a cell it also scores can land with no independence
    recorded, and once the file is repaired the pair surfaces as a stored
    ``honestyProblems`` entry in :func:`report_completeness` that neither author
    can amend in place. Refusing instead would let one truncated file -- a bad
    git conflict, say -- stop every colleague from writing at all.
    """
    from rubricator.merge import MergeProblem, merge_contributions
    from rubricator.rules import honesty_problems

    others = [(cid, c) for cid, c in mergeable if cid != contributor_id]
    try:
        merged = merge_contributions(
            store.frame(analysis_id),
            sorted([*others, (contributor_id, contribution)]),
            contributors=sorted({*store.contributors(analysis_id), contributor_id}),
        )
    except MergeProblem as problem:
        raise ValueError(f"refused, nothing was written: {problem}") from problem
    # Matched by cell *and* id: a caller's ids need only be unique per cell, so
    # an id alone would pull in another cell's stored problem.
    own = {f"cells[{'/'.join(key)}].assertions[{contributor_id}:{a}]" for key, a in added}
    # The author this call introduces, and any persona of it: a persona stored
    # earlier is judged against its principal's kind only once that principal exists.
    own_authors = set() if introduced is None else {f"authors[{introduced}]", *(
        f"authors[{a['id']}]" for a in merged.get("authors", []) if a.get("principalId") == introduced
    )}
    problems = [
        p
        for p in honesty_problems(merged)
        if any(p.path == o or p.path.startswith(f"{o}.") for o in own)
        or p.path in own_authors
    ]
    problems += _persona_kinds_that_cannot_both_hold(merged, introduced)
    if problems:
        raise ValueError(
            "refused, nothing was written: "
            + "; ".join(str(p) for p in problems)
        )


def _refuse_an_unread_own_file(
    store: AnalysisStore, analysis_id: str, contributor_id: str, skipped: Sequence[Mapping[str, str]]
) -> None:
    """Refuse a write into the writer's own file when every read leaves that file out.

    An unreadable file would be overwritten, losing what it held; a skipped one
    would receive a write nobody merges. Either way it is the writer's to repair.
    """
    own_file = store.contribution_key(analysis_id, contributor_id)
    for s in skipped:
        if s["file"] == own_file:
            raise ValueError(
                f"refused, nothing was written: {own_file}, this contributor's own file, is left "
                f"out of every read, so this write would land where nobody merges it, or replace "
                f"what it holds. Why: {s['because']}"
            )


def _skipped_clause(skipped: Sequence[Mapping[str, str]]) -> str:
    """The clause a write's summary carries when its honesty check left files out (#156)."""
    if not skipped:
        return ""
    return (
        f"; {len(skipped)} other stored file(s) could not be merged and were left out of the "
        "honesty check (see skipped)"
    )


def _references(
    store: AnalysisStore, analysis_id: str, key: str
) -> tuple[set[str], list[str]]:
    """Every id the stored cells refer to under ``key``, and the files that could not be read.

    Read from **every** file that parses, mergeable or not (#156): a row or a
    column with history is never deleted, and a file a reader skips -- a forged
    author, say -- still holds that history for when it is repaired. A file that
    does not parse, or names a row or column with something other than a string,
    cannot be consulted; the caller decides whether that matters
    (:func:`_refuse_a_blind_drop`).
    """
    referenced: set[str] = set()
    unread: list[str] = []
    for contributor_id in store.contributors(analysis_id):
        file = store.contribution_key(analysis_id, contributor_id)
        try:
            refs = [cell[key] for cell in store._read(file).get("cells", [])]
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
            unread.append(file)
            continue
        # A reference that is not a string names nothing yet, and may name a
        # dropped row once repaired: the file is as good as unread.
        if all(isinstance(r, str) for r in refs):
            referenced.update(refs)
        else:
            unread.append(file)
    return referenced, unread


def _stored_rows(stored: Any) -> tuple[dict[str, Mapping[str, Any]], bool | set[str]]:
    """The stored rows by id as far as they can be read, and whether all of them could.

    A hand edit can leave the frame's alternatives or criteria as an object, a
    scalar, or a list with entries that are not rows (#169). The verb that
    replaces the list is its repair, so it reads what it can: a list's object
    entries, an object's values. ``intact`` is false when anything was skipped,
    which :func:`_refuse_a_blind_repair` uses to refuse a write whose effect on a
    scored row cannot be told. A missing key is an empty list, not a broken one
    (callers pass ``frame.get(axis, [])``); an explicit ``null`` is broken. An id
    stored twice is not intact either, and is returned as the set of duplicated
    ids, because the last copy cannot be told apart from the record its scores
    were made against.

    >>> _stored_rows([{"id": "a"}, 3])
    ({'a': {'id': 'a'}}, False)
    >>> _stored_rows({"a": {"id": "a"}})
    ({'a': {'id': 'a'}}, False)
    >>> _stored_rows(None)
    ({}, False)
    >>> _stored_rows([{"id": "a"}, {"id": "a", "label": "x"}])[1]
    {'a'}
    """
    if stored is None:
        rows: Any = []
    elif isinstance(stored, Mapping):
        rows = list(stored.values())
    elif isinstance(stored, list):
        rows = stored
    else:
        rows = []
    good = [r for r in rows if isinstance(r, Mapping) and isinstance(r.get("id"), str)]
    readable = {r["id"]: r for r in good}
    ids = [r["id"] for r in good]
    duplicated = {i for i in ids if ids.count(i) > 1}
    if duplicated:
        return readable, duplicated
    return readable, isinstance(stored, list) and len(readable) == len(stored)


def _refuse_a_blind_repair(
    axis: str,
    stored: Mapping[str, Any],
    intact: bool | set[str],
    referenced: set[str],
    unread: Sequence[str],
    *,
    kept: set[str] = frozenset(),
) -> None:
    """Refuse replacing a stored list that could not be read whole, where that could hide history.

    With rows skipped, a cell may refer to a row whose stored record is gone:
    the drop guard and the change of meaning are both computed against the
    stored rows, so a replacement would delete that row, or redefine it with
    its scores still attached, without a word (second review of #226). Refused
    then, as is any repair while a contribution cannot be read to tell. A list
    nobody scored against is repaired as before. ``kept`` are ids the call
    re-declares where that is safe without the old record: alternatives, whose
    rows carry no versioned meaning. Criteria pass none, since a criterion
    re-declared over a lost record may have changed meaning undetected.
    """
    if intact is True:
        return
    duplicated = intact if isinstance(intact, set) else set()
    lost = sorted(((referenced - set(stored)) | (referenced & duplicated)) - kept)
    if lost:
        raise ValueError(
            f"refused, nothing was written: the stored {axis} are not a list of objects each with "
            f"a distinct string id, and cells refer to {', '.join(lost)}, whose stored record cannot be "
            "read; whether this call drops or redefines them cannot be told. Repair the frame "
            "file by hand."
        )
    if unread:
        raise ValueError(
            f"refused, nothing was written: the stored {axis} are not a list of objects each with "
            f"a distinct string id, and {', '.join(unread)} cannot be read to tell whether its cells refer "
            f"to {axis} whose stored record is lost. Its owner repairs or removes it, or repair "
            "the frame file by hand."
        )


def _refuse_a_blind_drop(axis: str, dropping: set[str], unread: Sequence[str]) -> None:
    """Refuse dropping ``axis`` ids while a file that might refer to them cannot be read.

    Skipping the file would let the drop through on a guess, and deleting a row
    or column with history is the one thing these verbs never do. A write that
    drops nothing is unaffected, so a colleague's broken file blocks only the
    writes it could be a reason to block (#156).
    """
    if not (dropping and unread):
        return
    raise ValueError(
        f"refused, nothing was written: this drops {axis} {', '.join(sorted(dropping))}, and "
        f"{', '.join(unread)} cannot be read to tell whether its cells refer to them (not "
        "JSON, or not shaped like a contribution). Its owner "
        f"repairs or removes it; or keep the {axis} in the set, or tombstone them."
    )


#: Assertion fields filled from an argument rather than from the cell, named at
#: that argument -- once, not once per cell.
_ARGUMENT_PATHS = {"at": "at $.at", "authorId": "at $.author.id"}
_ARGUMENT_FIELD = re.compile(r"^at \$\.cells\[\d+\]\.(at|authorId)(?=:)")

_OFF_CONTRACT = (
    "refused, nothing was written: the stored analysis would be one the companion's closed "
    "schema (comparanda v1) refuses: "
)


def _contract():
    from rubricator.schema.source import SchemaSource

    return SchemaSource.vendored()


def _put_frame(store: AnalysisStore, analysis_id: str, frame: dict[str, Any]) -> None:
    """Store the frame, **unless this write makes it one comparanda v1 refuses** (#136).

    v1 closes every object, so a key a caller added -- a ``url`` on an
    alternative, ``notes`` on a missing-code declaration -- would otherwise be
    copied in verbatim and the analysis stored in a shape its own renderer
    refuses. The whole frame is checked rather than the fragment a verb touched,
    because a frame is itself a valid v1 document and one check covers every
    verb that writes one, including the next.

    **Only problems this write introduces are refused.** A frame stored before
    the check existed, or edited by hand, may already carry one; refusing every
    later write over it would lock the analysis, since each verb repairs only
    its own part and none could go first. Those stay visible where they are
    read: ``analysis_get`` leaves them out of its views and names them. A
    problem is recognised by its content, not its index, so a stored one that a
    list reordering moved is still the stored one, and a new value breaking the
    same rule in the same place is still new -- as is a second copy of a stored one.
    """
    try:
        stored = _contract().identified_refusals(_as_stored(store.frame(analysis_id)))
    except (AnalysisNotFound, KeyError, ValueError):
        stored = []
    # Counted, not collected: a second copy of a stored problem is a new one (#195).
    before = Counter(identity for _, identity in stored)
    introduced = []
    for line, identity in _contract().identified_refusals(_as_stored(frame)):
        if before[identity]:
            before[identity] -= 1
        else:
            introduced.append(line)
    if introduced:
        raise ValueError(_OFF_CONTRACT + "; ".join(introduced))
    store.put_frame(analysis_id, frame)


def _as_stored(value: Any) -> Any:
    """``value`` as the store will write it: a tuple is a JSON array once stored.

    NaN and the infinities are refused here: Python's JSON would write them, and
    every strict parser -- the companion's renderer among them -- refuses the file.
    """
    import json

    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except ValueError:
        raise ValueError(
            "refused, nothing was written: a number is NaN or infinite, which JSON cannot "
            "carry and the companion's renderer refuses. Record a qualified blank instead."
        ) from None


def _unknown_keys(
    value: Any, shape: Mapping[str, Any], path: str, *, read_past: Sequence[str] = ()
) -> list[str]:
    """Keys in ``value`` that ``shape`` has no property for, with their path.

    ``read_past`` names the nested lists of objects the verb also reads field by
    field (a criterion's anchor rows), and so would drop a key from without a
    word. Everything else nested is copied whole, where the stored-document
    check sees it, or has its own refusal (a criterion's definition).
    """
    if not isinstance(value, Mapping):
        return []
    allowed = shape["properties"]
    extra = sorted(set(value) - set(allowed), key=repr)
    found = (
        [f"at {path}: {', '.join(repr(k) for k in extra)} "
         f"{'is' if len(extra) == 1 else 'are'} not recorded anywhere. "
         f"Allowed here: {', '.join(sorted(allowed))}"]
        if extra else []
    )
    for key in read_past:
        child = value.get(key)
        if child is not None and not isinstance(child, (list, tuple, Mapping)):
            found.append(f"at {path}.{key}: pass a list (or a mapping), so it can be checked "
                         "before it is read")
        if isinstance(child, (list, tuple)):
            found += [
                p for i, item in enumerate(child)
                for p in _unknown_keys(item, allowed[key]["items"], f"{path}.{key}[{i}]")
            ]
    return found


def _refuse_unknown_keys(items: Sequence[Any], shape: str, *, root: str) -> None:
    """Refuse a key the verb would otherwise drop without a word (#136).

    A criterion and a cell are read field by field, so an extra key is not
    copied into the document -- it is lost, and the caller believes it was
    kept. The allowed keys are the frozen surface's (ADR-0026), so a Python
    caller and an MCP caller are refused for the same keys. Keys only: a value's
    shape is the stored-document check's job, and the verbs accept a few
    convenience spellings (anchors as a mapping) the wire does not.
    """
    from rubricator.surface.frozen import CELL, CRITERION

    row, read_past = {"CELL": (CELL, ()), "CRITERION": (CRITERION, ("anchors",))}[shape]
    problems = [
        p for i, item in enumerate(items)
        for p in _unknown_keys(item, row, f"{root}[{i}]", read_past=read_past)
    ]
    if problems:
        raise ValueError("refused, nothing was written: " + "; ".join(problems))


def _plain(value: Any) -> Any:
    """``value`` as JSON would carry it: tuples are lists, read-only mappings are dicts."""
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _as_checked(cell: Any) -> Any:
    """A cell for the schema: plain, except that an evidence entry stays what the caller passed.

    The reference is stored as JSON, so a read-only mapping as an entry would pass
    every rule and fail in the store (#179): it must still read as "not an object".
    """
    if not isinstance(cell, Mapping):
        return cell
    plain = {k: _plain(v) for k, v in cell.items() if k != "evidence"}
    if "evidence" in cell:
        evidence = cell["evidence"]
        plain["evidence"] = list(evidence) if isinstance(evidence, (list, tuple)) else evidence
    return plain


def _refuse_malformed_author(author: Any) -> None:
    """Refuse an author the frozen AUTHOR shape does not admit, with its path (#195, from #178).

    As :func:`_refuse_malformed_cells` does for cells: ``bind`` refuses these at
    its input schema, and a direct caller reached ``author["id"]`` and crashed
    with a bare ``KeyError`` instead. Unknown keys are left to the contract
    check, which names the keys that are allowed.
    """
    from rubricator.schema.source import explain
    from rubricator.surface.frozen import AUTHOR
    from rubricator.surface import _validator

    problems = [
        explain(e, root="$.author")
        for e in sorted(_validator(AUTHOR).iter_errors(author), key=lambda e: list(e.path))
        if e.validator != "additionalProperties"
    ]
    if problems:
        raise ValueError(
            "refused, nothing was written: " + "; ".join(problems) + ". Fix: pass author as an "
            "object with id and displayName (strings) and kind, as contributors.human() builds it."
        )


def _refuse_malformed_cells(cells: Any) -> None:
    """Refuse a cell the frozen surface's CELL shape does not admit, all of them in one pass (#182).

    ``bind`` refuses these at its input schema, but a direct caller reaches the
    verb without it, and everything after this -- the id lookups, the locator
    profile, the honesty rules, :func:`sign` -- indexes a cell as an object of
    typed fields: a string cell, a ``missing`` with no code, a list where an id
    belongs crashed there (``TypeError``, ``KeyError``) instead of refusing. The
    check is the surface's own CELL row (ADR-0026), so a Python caller and an MCP
    caller are refused for the same shapes, each with its path. A tuple is a
    Python caller's list and was always written as one (#179).

    Two things are left to the later stages, which report them beside the other
    problems of that stage: unknown keys (they name the keys that *are*
    allowed), and what is wrong *inside* an evidence reference -- only the
    evidence container and its entries being objects is checked here, because
    the verb's locator and honesty checks walk them as such.
    """
    from rubricator.schema.source import explain
    from rubricator.surface.frozen import CELL, arr
    from rubricator.surface import _validator

    shape = {
        **CELL,
        "properties": {
            **CELL["properties"], "evidence": arr({"type": "object"}),
        },
    }
    errors = _validator(arr(shape)).iter_errors(
        [_as_checked(c) for c in cells] if isinstance(cells, (list, tuple)) else cells
    )
    problems = [
        explain(e, root="$.cells") for e in sorted(errors, key=lambda e: list(e.path))
        if e.validator != "additionalProperties"
    ]
    problems += [
        p for i, cell in enumerate(cells) if isinstance(cell, Mapping)
        for p in _unknown_keys(cell, CELL, f"$.cells[{i}]")
    ] if isinstance(cells, (list, tuple)) else []
    if problems:
        raise ValueError(
            "refused, nothing was written: " + "; ".join(problems) + ". Fix: pass each cell as an "
            "object with alternativeId and criterionId (strings), and value or missing "
            "({code, note}), justification, and evidence as a list of reference objects (leave "
            "evidence out, not null, for a blank that cites nothing)."
        )


def _persona_kinds_that_cannot_both_hold(
    merged: Mapping[str, Any], introduced: str | None
) -> list[Any]:
    """Refuse a persona whose kind no principal could match beside a stored sibling (#184).

    ``persona-keeps-kind`` compares a persona with its principal, and a principal
    that is not stored yet gives it nothing to compare with. Two personas of one
    principal in different kinds would then both be accepted, and whichever kind
    the principal later took, one of them would break the rule: the contributor
    would be locked out of their own id. So the second is refused now.
    """
    from rubricator.rules import Problem

    authors = [a for a in merged.get("authors", []) if isinstance(a, Mapping)]
    persona = next((a for a in authors if a.get("id") == introduced), None)
    principal = persona.get("principalId") if persona else None
    if principal is None or any(a.get("id") == principal for a in authors):
        return []
    return [
        Problem(
            path=f"authors[{introduced}]",
            message=(
                f'persona "{introduced}" is of kind "{persona.get("kind")}" but another persona of '
                f'"{principal}", "{other["id"]}", is "{other.get("kind")}"; whichever kind "{principal}" '
                "takes, one of them would change who made the assertion."
            ),
            fix=f'give both personas the one kind their principal "{principal}" has or will have.',
            rule_id="persona-keeps-kind",
        )
        for other in authors
        if other.get("principalId") == principal and other.get("id") != introduced
        and other.get("kind") != persona.get("kind")
    ]


def _existing(
    store: AnalysisStore,
    analysis_id: str,
    contributor_id: str,
    author: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    # The caller has already refused a file every read leaves out
    # (:func:`_refuse_an_unread_own_file`), so this one merges.
    try:
        contribution = store._read(store.contribution_key(analysis_id, contributor_id))
    except KeyError:
        contribution = {"contributorId": contributor_id, "authors": [], "cells": []}
    authors = {a["id"]: a for a in contribution.get("authors", [])}
    introduced = author["id"] not in authors
    authors.setdefault(author["id"], dict(author))
    contribution["authors"] = [authors[k] for k in sorted(authors)]
    contribution.setdefault("cells", [])
    return contribution, introduced


def _anchor_hash(levels: Mapping[str, str]) -> str:
    """The change detector for an anchor set.

    Hashes the same canonical bytes the companion repository does -- sorted keys,
    no whitespace -- because two producers disagreeing about whether the anchor
    text moved is the failure the hash exists to prevent.

    A **change detector, not a comparability key**: a hash cannot tell a
    boundary-moving edit from a typo fix, so comparability keys on the
    criterion's declared material version instead (ADR-0012's amendment).
    """
    import hashlib
    import json

    canonical = json.dumps(
        [[k, levels[k]] for k in sorted(levels)], ensure_ascii=False, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
