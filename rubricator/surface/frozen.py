"""The frozen tool surface (ADR-0026): names, signatures, envelopes, and the cut order.

**This module is data.** Every tool the surface will ever advertise is a row
here -- implemented or not, and a cut one keeps its row -- with its name, its ``inputSchema`` and
``outputSchema`` in the ADR-0013 subset, the contract the model reads, the
ADR-0005 stage it serves, why it needs no inference, how it fails, whether it
is in the minimum viable set, and when it is cut. The tests in
``tests/test_frozen_surface.py`` hold the implementation against these rows:
a verb whose Python signature disagrees with its row, a schema that leaves the
subset, a name that was decided against, or a result that does not match its
envelope all fail there.

Two things are frozen and one is not. **Names** and **input signatures** are
frozen: changing either is an amendment to ADR-0026 with its reason recorded.
**Output envelopes may grow** additively -- a new optional field is a row
edit, not an amendment -- because an output field constrains what the server
returns, never what a model may say.

Readers are the connector (which advertises these schemas verbatim and
validates every call against them), the CLI (which validates the same way),
the conformance tests, and a human deciding what to cut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from rubricator.store import RETENTION_DAYS

__all__ = [
    "ToolSpec", "FROZEN_TOOLS", "frozen", "advertised", "describe", "definitions",
    "definitions_bytes", "definitions_digest", "definitions_json", "DELIBERATELY_ABSENT", "FORBIDDEN_PARAMETERS", "ERROR_CONVENTION",
    "MEASURED", "AWAITING_MEASUREMENT", "RETENTION_DAYS",
]

Status = Literal["implemented", "planned", "transitional", "cut"]


@dataclass(frozen=True)
class ToolSpec:
    """One row of the frozen surface."""

    name: str
    family: str
    #: ADR-0005 stages served, as the research wrote them ("5, resume").
    stage: str
    status: Status
    minimum_viable: bool
    #: 1 is cut first. ``None`` is never cut. ADR-0026 records the order.
    cut_rank: int | None
    contract: str
    determinism: str
    failure: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    #: The issue that tracks implementation, for a planned or transitional tool, or that
    #: records the cut, for a cut one.
    issue: int | None = None
    #: The research table's row number, for the mapping in ADR-0026.
    research_row: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Schema fragments. Inlined rather than $ref'd: each tool's schema is then
# self-contained, which is what a client that copies one schema at a time needs.
# ---------------------------------------------------------------------------

S: dict[str, Any] = {"type": "string"}
I: dict[str, Any] = {"type": "integer"}
N: dict[str, Any] = {"type": "number"}
B: dict[str, Any] = {"type": "boolean"}


def obj(properties: Mapping[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def arr(items: Mapping[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": dict(items)}


def opt(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {"anyOf": [dict(schema), {"type": "null"}]}


def enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def const(value: str) -> dict[str, Any]:
    return {"type": "string", "const": value}


def at_least_one(items: Mapping[str, Any]) -> dict[str, Any]:
    """An array that, when given, names something: ``[]`` is refused.

    Used where an omitted argument means "all" -- so that a model saying "none"
    cannot be read as "every one", which is the one misreading that writes
    the whole matrix.
    """
    return {"type": "array", "items": dict(items), "minItems": 1}


SCALAR = {"anyOf": [N, S, B]}
DATE_TIME: dict[str, Any] = {"type": "string", "format": "date-time"}
MISSING_BROADER = enum(
    "not-applicable", "not-assessed", "deferred", "not-evidenced", "indeterminate", "withheld"
)
PREFERENCE = enum("increasing", "decreasing", "target", "ordered", "none")
INDEPENDENCE = enum("shared-context", "resampled", "perturbed", "independent", "consensus")
SOURCE_TYPE = enum("primary", "secondary", "agent-summary", "agent-inference")
STANCE = enum("supports", "contradicts", "qualifies", "context")
VERDICT = enum("exact", "normalised", "fuzzy", "moved", "stale", "unresolvable", "unchecked")
TRAVERSAL_ORDER = enum("cell-wise", "column-wise", "row-wise", "single-pass")
RULESET = enum("draft", "default", "strict-publication", "conformance")

#: Rows and columns may be retired but never deleted once scored: ``tombstoned``
#: and ``supersededBy`` are the comparanda fields for that, and they are on the
#: input shape because a refusal that says "tombstone it" must be followable.
ALTERNATIVE = obj(
    {"id": S, "label": S, "description": S, "groupIds": arr(S),
     "tombstoned": B, "supersededBy": arr(S)},
    ("id", "label"),
)
MISSING_DECLARATION = obj(
    {"id": S, "broader": MISSING_BROADER, "means": S,
     "structural": B, "terminal": B, "informative": B},
    ("id", "broader", "means"),
)
DEFINITION = obj({
    "objective": S, "question": S, "evidenceRule": S,
    "missingRules": arr(obj({"when": S, "code": S}, ("when", "code"))),
    "exclusions": arr(S),
})
#: Where a criterion came from (comparanda ``Criterion.provenance``, ADR-0016 / ADR-0006 one level up).
PROVENANCE = obj(
    {
        "origin": enum("user-stated", "derived-from-source", "agent-proposed", "imported"),
        "authorId": S, "at": S, "derivedFrom": arr(S), "rationale": S,
    },
    ("origin",),
)
#: A criterion proposed and then removed, with ADR-0016's closed reason (#259).
REJECTED_CRITERION = obj(
    {
        "label": S, "code": enum(
            "merged-into", "means-objective", "not-controllable", "no-discrimination-expected",
            "user-rejected"),
        "reason": S, "mergedIntoId": S, "proposedBy": S,
    },
    ("label", "code", "reason"),
)
CRITERION = obj(
    {
        "id": S, "label": S, "provenance": PROVENANCE, "scale": S, "preference": PREFERENCE, "target": N,
        "anchors": arr(obj({"level": S, "text": S}, ("level", "text"))),
        "missingCodes": arr(MISSING_DECLARATION),
        "definition": DEFINITION,
        "acceptability": obj({"threshold": N, "rationale": S}, ("threshold", "rationale")),
        "tombstoned": B, "supersededBy": arr(S),
    },
    ("id", "label"),
)
SUBJECT = obj(
    {"question": S, "decision": S, "decider": S, "context": S, "ambiguities": arr(S)},
    ("question",),
)
AUTHOR = obj(
    {
        "id": S, "displayName": S, "kind": enum("human", "agent", "imported", "derived"),
        "principalId": S, "actingAs": S,
        "attestation": obj(
            {"method": enum("unverified", "host-session", "oauth", "signature"),
             "issuer": S, "at": S}, ("method",)),
        "agent": obj({"name": S, "model": S, "promptVersion": S, "runId": S}, ("name",)),
        "role": S,
    },
    ("id", "displayName", "kind"),
)
#: The six comparanda selectors, each discriminated by a ``const`` type exactly
#: as the companion schema discriminates them, so a selector the surface
#: accepts is a selector the stored document validates with.
SELECTOR = {"anyOf": [
    obj({"type": const("TextQuoteSelector"), "exact": S, "prefix": S, "suffix": S},
        ("type", "exact")),
    obj({"type": const("TextPositionSelector"), "start": N, "end": N}, ("type", "start", "end")),
    obj({"type": const("PageRegionSelector"), "page": N,
         "rect": obj({"x": N, "y": N, "w": N, "h": N}, ("x", "y", "w", "h"))},
        ("type", "page")),
    obj({"type": const("LineRangeSelector"), "startLine": N, "endLine": N, "contentHash": S},
        ("type", "startLine", "endLine")),
    obj({"type": const("TimeRangeSelector"), "startSeconds": N, "endSeconds": N},
        ("type", "startSeconds", "endSeconds")),
    obj({"type": const("PathSelector"), "syntax": enum("css", "xpath"), "value": S},
        ("type", "syntax", "value")),
]}
CHECK = obj(
    {"status": VERDICT, "checkedAt": S, "checkerVersion": S, "resolvedBy": S,
     "originalDrifted": B, "detail": S},
    ("status",),
)
EVIDENCE = obj(
    {
        "id": S, "target": S, "sourceType": SOURCE_TYPE, "stance": STANCE,
        "selectors": arr(SELECTOR), "excerpt": S, "excerptHash": S, "renditionId": S,
        "normaliserId": S, "derivedFrom": arr(S), "check": CHECK, "label": S, "retrievedAt": S,
    },
    ("id", "target", "sourceType"),
)
#: Reasoning before value (ADR-0013): property order is generation order under
#: constrained decoding, and in the connector this argument *is* the judgement.
#: ``justification`` and ``evidence`` come before ``value`` and ``missing``, and
#: a test holds that order, because nothing else in the schema would notice.
CELL = obj(
    {
        "alternativeId": S, "criterionId": S, "measure": S, "assertionId": S,
        "supersedes": S,
        "justification": S,
        "evidence": arr(EVIDENCE),
        "value": SCALAR,
        "missing": obj({"code": S, "note": S}, ("code",)),
        "independence": INDEPENDENCE,
        "perturbation": obj({"kind": S, "seed": {"anyOf": [S, N]}, "detail": S}, ("kind",)),
    },
    ("alternativeId", "criterionId"),
)
#: The facts a caller states about a scoring pass (ADR-0018, #99). Everything else
#: in the procedure record -- the repeats, the times, the model, the prompt version,
#: the seeds -- the tools count or read, so none of it is a field here.
PROCEDURE = obj(
    {
        "traversal": TRAVERSAL_ORDER,
        "reduction": enum("lower-median", "median", "min", "max"),
        "seed": {"anyOf": [S, N]},
        "round": I,
        "session": enum("same", "fresh"),
        "prior": enum("withheld", "shown"),
    },
)
#: How a cell's agreement may be described: its lowest independence rung and the
#: wording that goes with it (ADR-0018). Null for a cell with fewer than two draws.
AGREEMENT = obj(
    {"rung": enum("unrecorded", "in-session", "fresh-session", "distinct-model", "distinct-human"),
     "label": S, "counts": arr(obj({"rung": S, "count": I}, ("rung", "count")))},
    ("rung", "label", "counts"),
)
#: A stored file a read left out because it cannot be merged (#151): never
#: dropped silently, so every reading tool returns the list, empty when whole.
SKIPPED = obj({"file": S, "because": S}, ("file", "because"))
SUPERSEDED_CELL = obj(
    {"alternativeId": S, "criterionId": S, "measure": S, "definedInVersion": S,
     "assertions": arr(obj({"id": S, "criteriaVersion": S}, ("id", "criteriaVersion")))},
    ("alternativeId", "criterionId", "measure", "definedInVersion", "assertions"),
)
SUPERSEDED = obj(
    {"count": I, "cells": arr(SUPERSEDED_CELL), "undetermined": arr(SUPERSEDED_CELL),
     "unversioned": I},
    ("count", "cells", "undetermined", "unversioned"),
)
PROBLEM = obj(
    {"path": S, "message": S, "fix": S, "ruleId": S,
     "family": enum("schema", "honesty", "completeness"), "severity": enum("error", "warning")},
    ("path", "message", "fix", "ruleId", "family", "severity"),
)
CELL_REF = obj({"alternativeId": S, "criterionId": S, "reason": S}, ("alternativeId", "criterionId"))
WEIGHT = obj({"criterionId": S, "weight": N}, ("criterionId", "weight"))
PROMPT_HEAD = {
    "id": S, "title": S, "version": I, "stage": opt(I), "updated": opt(S), "missingCodes": arr(S),
}
WRITE_RESULT = {
    "analysisId": S, "contributorId": S, "written": I, "criteriaVersion": S,
    "skipped": arr(SKIPPED), "summary": S,
}

def _retention(days: int) -> str:
    return (
        f"An analysis_id is an opaque handle. The connector's default store keeps an analysis "
        f"for {days} days from its last write; export defeats that window."
    )


_RETENTION = _retention(RETENTION_DAYS)

# ---------------------------------------------------------------------------
# The rows.
# ---------------------------------------------------------------------------

FROZEN_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="analysis_open", family="analysis", stage="1, resume", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=1,
        contract=(
            "Start a new analysis from the question being decided, or reopen an existing one "
            "by id. A new analysis is a valid, empty comparanda document: no alternatives, no "
            "criteria. Reopening never overwrites: an existing id returns created=false and "
            "what is there, so a retry cannot reset a matrix. Omit analysis_id to have one "
            "minted. Set allow_skip_confirmation only when the user explicitly said to skip "
            "the step-4 confirmation; it can be set only at creation. " + _RETENTION
        ),
        determinism="A store read and, for a new id, one write of a fixed empty frame.",
        failure=(
            "An unknown or expired id with no question is refused, naming the retention "
            "window; with a question it starts afresh under that id. Nothing is deleted."
        ),
        input_schema=obj({"analysis_id": S, "question": S, "allow_skip_confirmation": B,
                          "at": DATE_TIME}),
        output_schema=obj(
            {"analysisId": S, "created": B, "question": S, "alternatives": I, "criteria": I,
             "stage": I, "skipped": arr(SKIPPED), "summary": S},
            ("analysisId", "created", "question", "alternatives", "criteria", "stage", "skipped",
             "summary"),
        ),
    ),
    ToolSpec(
        name="analysis_get", family="analysis", stage="all", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=2,
        contract=(
            "Read the durable state of an analysis as one projection: summary (counts and "
            "stage), frame (subject and alternatives), criteria (with definitions and the set "
            "version), outstanding (only cells not yet settled, with counts by missingness "
            "code -- the resume affordance), or full (a resource link, never the document body)."
        ),
        determinism="A pure projection of stored state.",
        failure="An unknown id is refused, naming the two ways out: open a fresh analysis, or list the analyses resource.",
        input_schema=obj(
            {"analysis_id": S, "view": enum("summary", "frame", "criteria", "outstanding", "full")},
            ("analysis_id",),
        ),
        output_schema=obj(
            {
                "analysisId": S, "view": S, "question": S, "stage": I,
                "counts": obj(
                    {"alternatives": I, "criteria": I, "cells": I, "outstanding": I,
                     "superseded": I,
                     "byKind": obj({"scored": I, "settledBlank": I, "notApplicable": I},
                                   ("scored", "settledBlank", "notApplicable")),
                     "byCode": arr(obj({"code": S, "count": I}, ("code", "count")))},
                    ("alternatives", "criteria", "cells", "outstanding", "superseded", "byKind",
                     "byCode"),
                ),
                "subject": SUBJECT,
                "alternatives": arr(ALTERNATIVE),
                "criteria": arr(CRITERION),
                "criteriaVersion": opt(S),
                "outstanding": arr(obj(
                    {"alternativeId": S, "criterionId": S, "measure": S, "code": S, "recorded": B},
                    ("alternativeId", "criterionId", "measure", "code", "recorded"))),
                "resourceLink": opt(S),
                "omitted": arr(S),
                "skipped": arr(SKIPPED),
                "summary": S,
            },
            ("analysisId", "view", "question", "stage", "counts", "omitted", "skipped", "summary"),
        ),
    ),
    ToolSpec(
        name="corpus_add", family="corpus", stage="2, 5", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=3, issue=53,
        contract=(
            "Add source documents to an analysis's corpus. Each is normalised with the "
            "versioned normaliser, given a stable id from its content hash (so adding the same "
            "text twice is idempotent), and chunked into character offsets into the normalised "
            "full document, which is what quotes resolve against. Set agentProduced to true for "
            "text a model wrote (a prior analysis, a summary, an extracted table), and when "
            "unsure: references into it are then secondary at best. Says which were cleaned."
        ),
        determinism="A fixed chunker and a versioned normaliser over text the caller supplies; no fetch.",
        failure="A source with no text is refused, naming which one; nothing is partially added.",
        input_schema=obj(
            {
                "analysis_id": S,
                "sources": arr(obj({"id": S, "title": S, "text": S, "uri": S, "mediaType": S,
                                    "agentProduced": B}, ("text", "agentProduced"))),
                "chunking": obj({"windowChars": I, "overlapChars": I}),
            },
            ("analysis_id", "sources"),
        ),
        output_schema=obj(
            {"analysisId": S, "documentIds": arr(S),
             "documents": arr(obj(
                 {"documentId": S, "sourceId": S, "added": B, "cleaned": B, "agentProduced": B,
                  "spanCount": I, "tokenEstimate": I},
                 ("documentId", "added", "cleaned", "agentProduced", "spanCount",
                  "tokenEstimate"))),
             "spanCount": I, "tokenEstimate": I, "corpusTokenEstimate": I,
             "warnings": arr(S), "summary": S},
            ("analysisId", "documentIds", "documents", "spanCount", "tokenEstimate",
             "corpusTokenEstimate", "warnings", "summary"),
        ),
    ),
    ToolSpec(
        name="corpus_search", family="corpus", stage="2, 3, 5", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=4, issue=54,
        contract=(
            "Find spans in the corpus by lexical match: BM25 plus the whole query as a phrase, "
            "never embeddings (ADR-0010). No stemming: try other inflections. Returns the top k "
            "(default 8) spans, each widened to window_chars (default 600) for reading; start "
            "and end are the returned text's offsets into the document quotes resolve against. "
            "must_include keeps spans holding every phrase. A hit in an agent-produced document "
            "says so. An empty query returns the whole corpus when it is under 25,000 tokens."
        ),
        determinism="A pinned tokenizer and stopword list, stored spans, and the tie-break (score, documentId, start).",
        failure=(
            "An empty query over a corpus above the threshold is refused with the threshold and "
            "the size; so are an empty corpus, an unknown document id, and a query with no "
            "letters or digits. No match is an empty list saying what was searched."
        ),
        input_schema=obj(
            {"analysis_id": S, "query": S, "k": I, "document_ids": arr(S),
             "must_include": arr(S), "window_chars": I},
            ("analysis_id", "query"),
        ),
        output_schema=obj(
            {
                "analysisId": S, "query": S,
                "hits": arr(obj(
                    {"spanId": S, "documentId": S, "start": I, "end": I, "text": S, "score": N,
                     "agentProduced": B},
                    ("spanId", "documentId", "start", "end", "text", "score", "agentProduced"))),
                "inlined": B, "warnings": arr(S), "skipped": arr(SKIPPED), "summary": S,
            },
            ("analysisId", "query", "hits", "inlined", "warnings", "skipped", "summary"),
        ),
    ),
    ToolSpec(
        name="frame_set", family="frame", stage="1", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=5,
        contract=(
            "Record the frame: the decision being made, who decides, any context, and the "
            "ambiguities found. ambiguities is required so that whether anyone looked is on "
            "record; pass an empty list to say none were found. Alternatives are not written "
            "here -- they are stage 2's output and alternatives_set writes them."
        ),
        determinism="A validated write of the subject fields.",
        failure="An unknown analysis id is refused.",
        input_schema=obj(
            {"analysis_id": S, "ambiguities": arr(S), "decision": S, "decider": S, "context": S},
            ("analysis_id", "ambiguities"),
        ),
        output_schema=obj(
            {"analysisId": S, "decision": opt(S), "decider": opt(S), "ambiguities": arr(S),
             "summary": S},
            ("analysisId", "decision", "decider", "ambiguities", "summary"),
        ),
    ),
    ToolSpec(
        name="alternatives_set", family="alternatives", stage="2", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=6, issue=55,
        contract=(
            "Declare the alternatives -- the rows -- replacing the current set. Dropping an "
            "alternative that any cell refers to is refused: a row with history is "
            "tombstoned, never deleted. Pairs whose labels nearly coincide are returned in "
            "nearDuplicates, never merged: ask the user whether each pair is one alternative."
        ),
        determinism="A validated write; the near-duplicate check is token overlap and a named threshold.",
        failure="Duplicate ids, or dropping a scored row, is refused with nothing written.",
        input_schema=obj({"analysis_id": S, "alternatives": arr(ALTERNATIVE)}, ("analysis_id", "alternatives")),
        output_schema=obj(
            {"analysisId": S, "alternatives": arr(S),
             "nearDuplicates": arr(obj({"a": S, "b": S, "similarity": N}, ("a", "b", "similarity"))),
             "summary": S},
            ("analysisId", "alternatives", "nearDuplicates", "summary"),
        ),
    ),
    ToolSpec(
        name="criteria_set", family="criteria", stage="3", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=7,
        contract=(
            "Declare the criteria -- the columns -- replacing the current set and versioning "
            "it (ADR-0016). Each names a scale (default: the anchored 1-5 ordinal, which "
            "requires anchors at levels 1, 3 and 5), a direction of preference, and may carry "
            "a structured definition and its own missingness codes. A change of meaning moves "
            "the set version and reports which cells now answer an older definition; name the "
            "changed criteria whose edit moves no boundary in editorial. acceptability is a "
            "floor {threshold, rationale} whose failure is a veto; confidence_scale "
            "(confidence-1-3) declares a confidence measure on every criterion, kept when "
            "omitted; another preset changes it and none removes it, superseding no cell. "
            "Under-defined criteria are reported in definitionGaps, not refused."
        ),
        determinism="Schema checks, a versioned diff of definitions, and a lexical anchor check.",
        failure=(
            "Refused with nothing written: an unknown scale, a missing required anchor, an "
            "anchor on a level the scale cannot take, an undeclared missing-rule code, a "
            "target with no target preference, a floor off the scale or with no rationale, an "
            "anchored confidence_scale, changing or removing one that cells were recorded on, "
            "or dropping a criterion that cells refer to."
        ),
        input_schema=obj(
            {"analysis_id": S, "criteria": arr(CRITERION), "editorial": arr(S),
             "confidence_scale": S},
            ("analysis_id", "criteria"),
        ),
        output_schema=obj(
            {
                "analysisId": S, "criteria": arr(S), "criteriaVersion": S,
                "revised": arr(obj({"criterionId": S, "fields": arr(S), "material": B},
                                   ("criterionId", "fields", "material"))),
                "supersededCells": SUPERSEDED,
                "definitionGaps": arr(obj({"criterionId": S, "fields": arr(S)}, ("criterionId", "fields"))),
                "defaultedPreference": arr(S),
                "skipped": arr(SKIPPED),
                "summary": S,
            },
            ("analysisId", "criteria", "criteriaVersion", "revised", "supersededCells",
             "definitionGaps", "defaultedPreference", "skipped", "summary"),
        ),
    ),
    ToolSpec(
        name="criteria_reject", family="criteria", stage="3", status="implemented",
        minimum_viable=False, cut_rank=3, research_row=None,
        contract=(
            "Record criteria that were proposed and then removed, each with ADR-0016's closed "
            "reason (merged-into with the id of the criterion it was merged into, means-objective, "
            "not-controllable, no-discrimination-expected, user-rejected) and a sentence saying "
            "why. They ship with the analysis as its rejected criteria, so a criteria set with no "
            "visible rejects can be told from one nobody interrogated. Adds to the record, never "
            "replaces it; criteria_set does not touch it."
        ),
        determinism="Schema validation and a lookup of the merged-into id among the criteria; the moment is supplied, never read from a clock.",
        failure=(
            "Refused with nothing written: an unknown reason, a blank label or reason, a "
            "merged-into with no live criterion to name (or any other reason naming one), or a "
            "label that is a live criterion's."
        ),
        input_schema=obj(
            {"analysis_id": S, "rejected": arr(REJECTED_CRITERION), "at": DATE_TIME},
            ("analysis_id", "rejected"),
        ),
        output_schema=obj(
            {
                "analysisId": S, "written": I, "total": I,
                "byCode": arr(obj({"code": S, "count": I}, ("code", "count"))),
                "summary": S,
            },
            ("analysisId", "written", "total", "byCode", "summary"),
        ),
    ),
    ToolSpec(
        name="frame_confirm", family="frame", stage="4", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=8,
        contract=(
            "The ADR-0005 step-4 gate: nothing is scored until the user confirms the frame and "
            "criteria. Call with no decision: an earlier confirmation is returned "
            "(mechanism=recorded) so a resumed session does not re-ask; otherwise you get "
            "instructions to ask the user in chat. Then call again with their decision, "
            "confirmed_by and their reply verbatim as confirmation_text; scope names what they "
            "answered for, one part or two joined with +. A confirm is recorded "
            "only in answer to a question asked since the last decision; if the criteria moved "
            "after a confirmation you get instructions to ask again. The tool never confirms "
            "on its own behalf; the record is authored and timestamped."
        ),
        determinism=(
            "It records a decision; it does not make one. A call with no decision writes at most "
            "one record, noting that the question was asked (on a gate resting on the skip, that "
            "a confirmation is invited); a read of a settled gate writes nothing."
        ),
        failure="A call that carries no human decision and cannot elicit one returns confirmed=false with instructions, never an error.",
        input_schema=obj(
            {"analysis_id": S,
             "scope": enum("all", "frame", "alternatives", "criteria", "frame+alternatives",
                           "frame+criteria", "alternatives+criteria"),
             "decision": enum("confirm", "revise", "reject"), "confirmed_by": S,
             "confirmation_text": S, "at": DATE_TIME},
            ("analysis_id",),
        ),
        output_schema=obj(
            {
                "analysisId": S, "confirmed": B,
                "mechanism": enum("elicitation", "out-of-band", "recorded"),
                "record": opt(obj(
                    {"authorId": S, "at": S, "text": S, "criteriaVersion": S, "decision": S,
                     "scope": S, "mechanism": S},
                    ("authorId", "at", "decision"))),
                "instructions": opt(S), "summary": S,
            },
            ("analysisId", "confirmed", "mechanism", "record", "instructions", "summary"),
        ),
    ),
    ToolSpec(
        name="plan_traversal", family="plan", stage="5", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=9,
        contract=(
            "The order in which to score the cells, from a seed. The model follows the plan "
            "and never chooses the order; the seed enters provenance so a run replays "
            "exactly (ADR-0011). cell-wise is the default and the isolating choice; "
            "column-wise, row-wise and single-pass exist for the evaluation harness."
        ),
        determinism="A pure function of (seed, alternatives, criteria).",
        failure="An empty axis is refused: a plan over nothing is not a plan.",
        input_schema=obj(
            {"alternatives": arr(S), "criteria": arr(S), "order": TRAVERSAL_ORDER, "seed": S,
             "shuffle": B},
            ("alternatives", "criteria"),
        ),
        output_schema=obj(
            {
                "order": TRAVERSAL_ORDER, "seed": S, "steps": arr(arr(S)), "modelCalls": I,
                "isolation": I,
                "provenance": obj(
                    {"kind": S, "order": S, "seed": S, "shuffled": S, "alternatives": S,
                     "criteria": S},
                    ("kind", "order", "seed", "shuffled", "alternatives", "criteria")),
                "summary": S,
            },
            ("order", "seed", "steps", "modelCalls", "isolation", "provenance", "summary"),
        ),
    ),
    ToolSpec(
        name="measures_write", family="measures", stage="5", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=10,
        contract=(
            "Write one contributor's assertions: a value with its justification and cited "
            "evidence, or a qualified blank naming its missingness code. Writes only that "
            "contributor's file and never echoes a previously written score. Each assertion "
            "is stamped with the criteria-set version; pass expected_criteria_version to be "
            "refused if the set moved since you read it. An agent passes procedure on every "
            "pass, the first included (round number, same or fresh session, whether the prior "
            "was withheld or shown, and the plan's traversal, reduction and seed when it has "
            "one); a cell takes one draw per round: the tools record the "
            "procedure, count its repeats and derive each draw's independence rung, and refuse "
            "a rung the pass contradicts. A re-score replaces the writer's own earlier claim "
            "by naming it in supersedes: that assertion stays, marked superseded. "
            "Honesty rules run before the bytes land (ADR-0024)."
        ),
        determinism="Schema validation and the honesty rules over the merged document; the moment is supplied, never read from a clock.",
        failure=(
            "Refused with nothing written: an analysis the user has not confirmed "
            "(frame_confirm), a cell on an unknown criterion, a reused assertion id, a "
            "criteria-version mismatch, a supersedes naming no assertion of the writer's own in "
            "that cell, or an honesty violation such as a second claim on a "
            "cell with no independence recorded."
        ),
        input_schema=obj(
            {"analysis_id": S, "contributor_id": S, "author": AUTHOR,
             "at": DATE_TIME, "cells": arr(CELL),
             "expected_criteria_version": S, "procedure": PROCEDURE},
            ("analysis_id", "contributor_id", "author", "cells"),
        ),
        output_schema=obj(WRITE_RESULT, tuple(WRITE_RESULT)),
    ),
    ToolSpec(
        name="measures_mark_missing", family="measures", stage="5, resume", status="implemented",
        minimum_viable=False, cut_rank=4, research_row=11,
        contract=(
            "Mark a selection of cells as one qualified blank -- every alternative, or those "
            "named, against every criterion, or those named -- with a note saying why. The "
            "code must be one the analysis's own vocabulary resolves: the core six, or a code "
            "declared on the analysis or the criterion. This is what makes 'fill these two "
            "criteria and mark the rest deferred' a first-class instruction. A blank from a "
            "pass takes the same procedure as measures_write, so it is counted and stamped "
            "like any other draw; with a procedure it is for one cell (exactly one of "
            "alternative_ids and one of criterion_ids) and its code is one that says someone "
            "looked, not not-assessed or deferred. measure defaults to score; name confidence "
            "to blank confidence cells."
        ),
        determinism="Set arithmetic over the frame, then measures_write.",
        failure="An undeclared code is refused, listing what is known and how to declare a new one.",
        input_schema=obj(
            {"analysis_id": S, "contributor_id": S, "author": AUTHOR,
             "at": DATE_TIME, "code": S, "note": S,
             "criterion_ids": at_least_one(S), "alternative_ids": at_least_one(S),
             "independence": INDEPENDENCE, "procedure": PROCEDURE, "measure": S},
            ("analysis_id", "contributor_id", "author", "code", "note"),
        ),
        output_schema=obj(
            {**WRITE_RESULT, "code": S, "marked": I},
            (*WRITE_RESULT, "code", "marked"),
        ),
    ),
    ToolSpec(
        name="analysis_validate", family="analysis", stage="5, 6", status="planned",
        minimum_viable=True, cut_rank=None, research_row=12, issue=61,
        contract=(
            "Validate the merged analysis against the published comparanda JSON Schema at the "
            "ADR-0002 boundary, and run the rule families of ADR-0024 over it: honesty "
            "problems are errors and are never suppressed; completeness problems inform. "
            "ruleset chooses the composition: draft (honesty only), default, "
            "strict-publication, conformance."
        ),
        determinism="JSON Schema validation plus a passed-in rule set.",
        failure="Never raises on an invalid document: it returns valid=false and every problem with its path and fix.",
        input_schema=obj({"analysis_id": S, "ruleset": RULESET, "schema_version": S}, ("analysis_id",)),
        output_schema=obj(
            {"analysisId": S, "valid": B, "schemaVersion": S, "ruleset": RULESET,
             "problems": arr(PROBLEM), "summary": S},
            ("analysisId", "valid", "schemaVersion", "ruleset", "problems", "summary"),
        ),
    ),
    ToolSpec(
        name="check_citations", family="citations", stage="5, 6", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=13,
        contract=(
            "Check claimed quotes against their source text, deterministically, and grade "
            "each: exact, normalised, fuzzy, moved, stale, or unresolvable (ADR-0014). Cell-level "
            "so a bad citation can be repaired inside the scoring loop. Give the source text; "
            "nothing is fetched."
        ),
        determinism="String containment and ordered-token overlap at a fixed threshold; the normaliser is versioned.",
        failure="An empty quote is graded unresolvable rather than passing; a missing source is refused.",
        input_schema=obj(
            {"citations": arr(obj({"quote": S, "source": S, "evidenceId": S}, ("quote", "source")))},
            ("citations",),
        ),
        output_schema=obj(
            {
                "total": I, "exact": I, "verbatim": I, "failed": I, "verbatimRate": N,
                "exactRate": N,
                "checks": arr(obj(
                    {"evidenceId": opt(S), "status": VERDICT, "detail": S,
                     "span": opt(obj({"start": I, "end": I}, ("start", "end"))), "overlap": N},
                    ("evidenceId", "status", "detail", "span", "overlap"))),
                "summary": S,
            },
            ("total", "exact", "verbatim", "failed", "verbatimRate", "exactRate", "checks",
             "summary"),
        ),
    ),
    ToolSpec(
        name="aggregate_assertions", family="measures", stage="5", status="implemented",
        minimum_viable=False, cut_rank=3, research_row=14, issue=97,
        contract=(
            "Reduce the assertions of each cell to one value by an order statistic -- lower "
            "median by default. A polarised cell (two or more occupied levels separated by at "
            "least polarised_gap empty levels, with no single dominant mode) yields no value "
            "unless allow_contested_reduction is set, and is flagged contested. A mean is "
            "refused, naming the level of measurement; a nominal criterion gets modes only. "
            "Each cell carries agreement: its lowest independence rung and what that lets you "
            "call it (self-consistency, test-retest; inter-rater only across distinct humans)."
        ),
        determinism="Order statistics over stored values.",
        failure="reduction=mean is refused naming the level of measurement; a polarised cell reduces to null, flagged.",
        input_schema=obj(
            {"analysis_id": S, "reduction": enum("lower-median", "median", "min", "max"),
             "allow_contested_reduction": B, "polarised_gap": I},
            ("analysis_id",),
        ),
        output_schema=obj(
            {
                "analysisId": S, "reduction": S,
                "cells": arr(obj(
                    {"alternativeId": S, "criterionId": S, "measure": S, "n": I,
                     "reduced": opt(SCALAR), "min": opt(SCALAR), "max": opt(SCALAR),
                     "span": opt(N), "modes": arr(SCALAR),
                     "levels": arr(obj({"level": SCALAR, "count": I}, ("level", "count"))),
                     "offScale": I, "polarised": B, "contested": B,
                     "agreement": opt(AGREEMENT)},
                    ("alternativeId", "criterionId", "measure", "n", "reduced", "polarised",
                     "contested"))),
                "skipped": arr(SKIPPED),
                "summary": S,
            },
            ("analysisId", "reduction", "cells", "skipped", "summary"),
        ),
    ),
    ToolSpec(
        name="stability_report", family="report", stage="6", status="implemented",
        minimum_viable=False, cut_rank=3, research_row=15, issue=98,
        contract=(
            "How stable the picture is. Weight-free first: dominance survival per alternative "
            "and Pareto-set churn under perturbation. Weighted only when weights are declared: "
            "tau-b, top-1 and top-3 churn, a band verdict. Per criterion: test-retest "
            "agreement labelled by the lowest independence rung present, plus the histogram "
            "and compression that drive the escalation trigger."
        ),
        determinism="Vendored rank statistics, Pareto computation and histograms; no scipy.",
        failure="With fewer than two assertions per cell the per-criterion agreement is null and says why, never a number.",
        input_schema=obj(
            {"analysis_id": S, "weights": arr(WEIGHT), "tau_bands": obj({"low": N, "high": N}, ("low", "high"))},
            ("analysis_id",),
        ),
        output_schema=obj(
            {
                "analysisId": S,
                "repeatedMatrices": I,
                "basis": arr(S),
                "dominanceSurvival": arr(obj({"alternativeId": S, "rate": N}, ("alternativeId", "rate"))),
                "paretoChurn": N,
                "blankDensity": N,
                "perCell": arr(obj(
                    {"alternativeId": S, "criterionId": S, "n": I, "span": opt(N), "polarised": B},
                    ("alternativeId", "criterionId", "n", "span", "polarised"))),
                "perCriterion": arr(obj(
                    {"criterionId": S, "agreement": opt(N), "lowestRung": opt(INDEPENDENCE),
                     "agreementLabel": opt(S), "repeatedCells": I,
                     "histogram": arr(obj({"level": S, "count": I}, ("level", "count"))),
                     "compression": N},
                    ("criterionId", "agreement", "lowestRung", "agreementLabel", "repeatedCells",
                     "histogram", "compression"))),
                "weighted": opt(obj(
                    {"tauDistribution": arr(N), "top1Churn": N, "top3Churn": N,
                     "band": enum("stable", "borderline", "unstable")},
                    ("tauDistribution", "top1Churn", "top3Churn", "band"))),
                "summary": S,
            },
            ("analysisId", "repeatedMatrices", "basis", "dominanceSurvival", "paretoChurn",
             "blankDensity", "perCell", "perCriterion", "weighted", "summary"),
        ),
    ),
    ToolSpec(
        name="report_weaknesses", family="report", stage="6", status="implemented",
        minimum_viable=False, cut_rank=5, research_row=16, issue=64,
        contract=(
            "The deterministic half of the review stage: which cells are uncited, thinly "
            "evidenced, low in confidence, stale in their citations, or rest on the agent's "
            "own inference; which alternatives are dominated; which veto flags fired. With a "
            "budget, a value-of-information plan: pivotal cells first, then thin evidence, "
            "with under-defined criteria routed to redefine rather than rescore."
        ),
        determinism="Rank statistics and exact perturbation over stored values.",
        failure="An empty matrix returns empty lists with a summary saying nothing has been scored, never silence.",
        input_schema=obj(
            {"analysis_id": S, "top_k": I, "budget": I, "weights": arr(WEIGHT)}, ("analysis_id",)
        ),
        output_schema=obj(
            {
                "analysisId": S, "uncited": arr(CELL_REF), "thinEvidence": arr(CELL_REF),
                "lowConfidence": arr(CELL_REF), "staleCitations": arr(CELL_REF),
                "agentInferenceOnly": arr(CELL_REF), "dominatedAlternatives": arr(S),
                "vetoFlags": arr(obj({"alternativeId": S, "criterionId": S, "reason": S},
                                     ("alternativeId", "criterionId", "reason"))),
                "traversalLeakageDiagnostic": arr(obj(
                    {"criterionA": S, "criterionB": S, "correlation": N, "note": S},
                    ("criterionA", "criterionB", "correlation", "note"))),
                "rescoringPlan": opt(obj(
                    {"rescore": arr(CELL_REF), "redefine": arr(S), "budget": I},
                    ("rescore", "redefine", "budget"))),
                "summary": S,
            },
            ("analysisId", "uncited", "thinEvidence", "lowConfidence", "staleCitations",
             "agentInferenceOnly", "dominatedAlternatives", "vetoFlags",
             "traversalLeakageDiagnostic", "rescoringPlan", "summary"),
        ),
    ),
    ToolSpec(
        name="disclose_variance", family="report", stage="6", status="implemented",
        minimum_viable=False, cut_rank=2, research_row=17, issue=100,
        contract=(
            "Render the variance disclosure from what the procedure record says actually "
            "happened: what was measured, what was not, how many draws at which independence "
            "rung. The wording is content, not code, so a reviewer edits it without a release."
        ),
        determinism="Template substitution over a provenance record.",
        failure="An analysis with no procedure record discloses that nothing was measured; it never invents a number.",
        input_schema=obj({"analysis_id": S}, ("analysis_id",)),
        output_schema=obj(
            {"analysisId": S, "text": S, "measured": arr(S), "notMeasured": arr(S),
             "procedureIds": arr(S), "summary": S},
            ("analysisId", "text", "measured", "notMeasured", "procedureIds", "summary"),
        ),
    ),
    ToolSpec(
        name="compute_coupling_matrix", family="criteria", stage="3", status="cut",
        minimum_viable=False, cut_rank=1, research_row=18, issue=65,
        contract=(
            "Arithmetic over probe scores the model supplied (probe generation and scoring are "
            "prompts): how much a change aimed at one criterion moves the others. Flags "
            "off-diagonal mass above a named threshold. Opt-in: it costs 3n^2 judgements."
        ),
        determinism="Arithmetic.",
        failure="A probe naming an unknown criterion is refused.",
        input_schema=obj(
            {"criteria": arr(S),
             "probe_scores": arr(obj(
                 {"probeId": S, "targetCriterionId": S, "criterionId": S, "score": N},
                 ("probeId", "targetCriterionId", "criterionId", "score")))},
            ("criteria", "probe_scores"),
        ),
        output_schema=obj(
            {"offDiagonalMass": N,
             "flagged": arr(obj({"criterionA": S, "criterionB": S, "mass": N},
                                ("criterionA", "criterionB", "mass"))),
             "matrix": arr(obj({"criterionId": S, "row": arr(N)}, ("criterionId", "row"))),
             "summary": S},
            ("offDiagonalMass", "flagged", "matrix", "summary"),
        ),
    ),
    ToolSpec(
        name="fit_bradley_terry", family="measures", stage="5", status="cut",
        minimum_viable=False, cut_rank=1, research_row=19, issue=65,
        contract=(
            "Latent strengths from pairwise comparisons, with bootstrap intervals. Reached "
            "only through the four-condition escalation of ADR-0011; the caller maps strengths "
            "back to rubric levels by a monotone anchor map and marks the derivation, because "
            "a fitted score is not the same kind of object as a judged one."
        ),
        determinism="Numeric optimisation from a fixed start, bootstrap from a stated seed.",
        failure="A comparison graph that is not connected is refused, naming the components.",
        input_schema=obj(
            {"comparisons": arr(obj({"winner": S, "loser": S, "tie": B}, ("winner", "loser"))),
             "tie_model": enum("davidson", "none"), "bootstrap": I, "seed": S},
            ("comparisons",),
        ),
        output_schema=obj(
            {"strengths": arr(obj({"alternativeId": S, "strength": N, "low": N, "high": N},
                                  ("alternativeId", "strength", "low", "high"))),
             "tieParameter": opt(N), "summary": S},
            ("strengths", "tieParameter", "summary"),
        ),
    ),
    ToolSpec(
        name="report_completeness", family="report", stage="5, 6, resume", status="implemented",
        minimum_viable=True, cut_rank=None, research_row=None,
        contract=(
            "Counts and rates over the merged analysis: valued cells, settled blanks, "
            "informative blanks, and what is outstanding; silenceRate counts only 'we looked "
            "and the sources are silent'. Reports beside the counts the codes this build could "
            "not interpret, the cells scored against an older criterion definition, and the "
            "honesty problems already stored."
        ),
        determinism="Arithmetic over the merged document.",
        failure="An unknown analysis id is refused; an unresolvable code counts as outstanding, the safe direction.",
        input_schema=obj({"analysis_id": S}, ("analysis_id",)),
        output_schema=obj(
            {
                "analysisId": S, "total": I, "structural": I, "applicable": I, "present": I,
                "settledAbsent": I, "informativeAbsent": I, "outstanding": I,
                "examinedRate": N, "valuedRate": N, "silenceRate": N,
                "degradations": arr(obj(
                    {"axis": S, "id": S, "at": S, "because": S, "broader": opt(S)},
                    ("axis", "id", "at", "because", "broader"))),
                "supersededCells": SUPERSEDED,
                "honestyProblems": arr(obj({"path": S, "message": S, "fix": S, "ruleId": S},
                                           ("path", "message", "fix", "ruleId"))),
                "schemaProblems": arr(obj({"path": S, "message": S, "fix": S, "ruleId": S},
                                          ("path", "message", "fix", "ruleId"))),
                "skipped": arr(SKIPPED),
                "summary": S,
            },
            ("analysisId", "total", "structural", "applicable", "present", "settledAbsent",
             "informativeAbsent", "outstanding", "examinedRate", "valuedRate", "silenceRate",
             "degradations", "supersededCells", "honestyProblems", "schemaProblems", "skipped",
             "summary"),
        ),
        notes=("Not in the research's 19: added when the completeness report was built, "
               "and kept because analysis_get's outstanding view returns cells where this "
               "returns rates.",),
    ),
    ToolSpec(
        name="prompts_list", family="prompts", stage="all", status="transitional",
        minimum_viable=True, cut_rank=None, issue=80,
        contract=(
            "Every prompt this runtime serves -- id, title, version, stage -- without the "
            "bodies. Transitional: retired when the prompts are served as native MCP prompts."
        ),
        determinism="Reads versioned content files.",
        failure="Cannot fail on input; a runtime with no prompts returns an empty list.",
        input_schema=obj({}),
        output_schema=obj(
            {"prompts": arr(obj(PROMPT_HEAD, tuple(PROMPT_HEAD))), "summary": S},
            ("prompts", "summary"),
        ),
    ),
    ToolSpec(
        name="prompts_get", family="prompts", stage="all", status="transitional",
        minimum_viable=True, cut_rank=None, issue=80,
        contract=(
            "One prompt with the text a model should be given, and the version that text "
            "carries, so a run's provenance can name the wording that produced it. "
            "Transitional: retired when the prompts are served as native MCP prompts."
        ),
        determinism="Reads one versioned content file.",
        failure="An unknown id is refused, listing the ids this runtime serves.",
        input_schema=obj({"prompt_id": S}, ("prompt_id",)),
        output_schema=obj(
            {**PROMPT_HEAD, "body": S, "summary": S}, (*PROMPT_HEAD, "body", "summary")
        ),
    ),
)


def frozen() -> Mapping[str, ToolSpec]:
    """The rows by name."""
    return {spec.name: spec for spec in FROZEN_TOOLS}


def advertised() -> tuple[ToolSpec, ...]:
    """The rows a surface exposes today: implemented and transitional."""
    return tuple(spec for spec in FROZEN_TOOLS if spec.status in ("implemented", "transitional"))


def describe(spec: ToolSpec, *, retention_days: int = RETENTION_DAYS) -> str:
    """The description a model reads: contract, stage, determinism, failure.

    Rendered from the row rather than taken from the Python docstring, because
    a docstring written for the developer maintaining a verb and a description
    written for the model choosing one have different readers, and the token
    cost of the second is measured (:data:`MEASURED`).

    ``retention_days`` is the window of the store being served, stated in place
    of the default where a row states it, so a store configured with another
    window never advertises the default. At the default the text is the row's,
    byte for byte, which is what the measurement pins.
    """
    contract = spec.contract.replace(_RETENTION, _retention(retention_days))
    return (
        f"{contract}\n\nStage: {spec.stage}. Deterministic: {spec.determinism} "
        f"Fails: {spec.failure}"
    )


def definitions(specs: tuple[ToolSpec, ...] = FROZEN_TOOLS) -> list[dict[str, Any]]:
    """The tool definitions as a client sends them to a model: name, description, input schema.

    This is the exact list the token measurement is taken over, so what is
    measured is what costs context on every turn -- not an estimate of it.
    """
    return [
        {"name": spec.name, "description": describe(spec), "input_schema": dict(spec.input_schema)}
        for spec in specs
    ]


def definitions_json(specs: tuple[ToolSpec, ...] = FROZEN_TOOLS) -> bytes:
    """:func:`definitions` as canonical compact JSON: insertion order, no whitespace, ASCII.

    Insertion order, **not** sorted keys: property order is generation order
    under constrained decoding (ADR-0013), so reordering a schema's properties
    changes what the model does and must change the digest.
    """
    import json

    return json.dumps(
        definitions(specs), separators=(",", ":"), sort_keys=False, ensure_ascii=True
    ).encode("ascii")


def definitions_bytes(specs: tuple[ToolSpec, ...] = FROZEN_TOOLS) -> int:
    """Size of :func:`definitions_json`; recorded beside the count for a reader."""
    return len(definitions_json(specs))


def definitions_digest(specs: tuple[ToolSpec, ...] = FROZEN_TOOLS) -> str:
    """SHA-256 of :func:`definitions_json`; the pin for :data:`MEASURED`.

    A digest rather than a length: a same-length edit -- ``string`` to
    ``number``, one word for another -- changes what the model reads and what
    it costs, and a length pin let both through.
    """
    import hashlib

    return hashlib.sha256(definitions_json(specs)).hexdigest()


#: What the surface deliberately does not have, and why. A test asserts none of
#: these names is ever advertised.
DELIBERATELY_ABSENT: Mapping[str, str] = {
    "propose_criteria": "judgement: a prompt the caller's model runs (ADR-0003)",
    "score_cell": "judgement: a prompt the caller's model runs (ADR-0003)",
    "review": "judgement: a prompt the caller's model runs (ADR-0003)",
    "detect_overlap": "judgement: a prompt the caller's model runs (ADR-0003)",
    "corpus_embed": "no embedding-backed search inside a tool (ADR-0010)",
    "semantic_search": "no embedding-backed search inside a tool (ADR-0010)",
    "aggregate_total": "no aggregate or total: comparanda computes none by default",
    "compute_total": "no aggregate or total: comparanda computes none by default",
    "analysis_list": "a resource -- the host lists, the model does not browse",
    "conformal_interval": "not in v1; when it lands it reads a stored calibration table",
}

#: Parameters no scoring tool may carry. Neither exists in the connector, and a
#: parameter that silently no-ops in one of two first-class runtimes is a bug in
#: the specification. Seed the traversal, not the model.
FORBIDDEN_PARAMETERS: frozenset[str] = frozenset({"temperature", "seed_model", "model_seed"})

#: How a tool says no.
ERROR_CONVENTION: Mapping[str, str] = {
    "validation": (
        "Arguments are validated against the frozen inputSchema before the verb runs; a "
        "failure raises ValueError naming the JSON path, what was found, and what is allowed."
    ),
    "business": (
        "A verb refuses with ValueError (a rule), KeyError (an unknown id or code) or "
        "TypeError (a shape), whose message carries the fact needed to fix it, and states "
        "that nothing was written when that is so."
    ),
    "wire": (
        "Over MCP, every such exception is a tool result with isError: true whose text is "
        "the message. An unknown tool or a malformed request is a protocol-level error, "
        "raised by the host, never by a verb."
    ),
    "envelope": (
        "Every success returns structuredContent matching the tool's outputSchema, whose "
        "required summary string is also the human-readable content."
    ),
}

#: The measured token cost of the advertised definitions. Measured, not
#: estimated: scripts/measure_tool_tokens.py sends the exact tool list a client
#: sends to the provider's token counter and records what came back. ``sha256``
#: is the digest of that list as canonical JSON, and a test pins the live
#: digest to it, so any change to the definitions fails until the measurement
#: is redone. ``bytes`` is recorded for the reader, not as the pin.
MEASURED: Mapping[str, Any] = {
    "measuredAt": "2026-10-12",
    "model": "claude-sonnet-5-5",
    "advertised": {
        "tools": 14, "tokens": 7917, "bytes": 18897,
        "sha256": "ca76e767cdb31c6f97e621701ff9afb5248f19a79d3d75ce4d7f8516286d4d41",
    },
    "wholeSurface": {
        "tools": 22, "tokens": 10792, "bytes": 26207,
        "sha256": "4f0f6e6e5422fea75a253bedd2050f09e89a23820750bebcdeef7ffc204c4b48",
    },
}

#: Definitions changed where no provider key was at hand, so they could not be
#: counted. :data:`MEASURED` stays the last real measurement; this pins the
#: digest and size of what is served *now* and names the open issue that owes
#: the count, so a further change still fails the test. It holds no token
#: count, because an estimate is what ADR-0009 forbids recording as one.
#: ``None`` once the issue's measurement is pasted into :data:`MEASURED`.
AWAITING_MEASUREMENT: Mapping[str, Any] | None = {
    "issue": 199,
    "advertised": {
        "tools": 20, "bytes": 28818,
        "sha256": "edb26233b717cf6fc289f84c20fd85d06491e069775b4be2152d37d639e1df8a",
    },
    "wholeSurface": {
        "tools": 23, "bytes": 31439,
        "sha256": "dbdf1be63f0d66da33f9541a03fd7aaacf46da21ab1594d303e0040aab57156f",
    },
}
