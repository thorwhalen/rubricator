"""The frozen tool surface (ADR-0026): names, signatures, envelopes, and the cut order.

**This module is data.** Every tool the surface will ever advertise is a row
here -- implemented or not -- with its name, its ``inputSchema`` and
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
    "MEASURED", "RETENTION_DAYS",
]

Status = Literal["implemented", "planned", "transitional"]


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
    #: The issue that tracks implementation, for a planned or transitional tool.
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
CRITERION = obj(
    {
        "id": S, "label": S, "scale": S, "preference": PREFERENCE, "target": N,
        "anchors": arr(obj({"level": S, "text": S}, ("level", "text"))),
        "missingCodes": arr(MISSING_DECLARATION),
        "definition": DEFINITION,
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
        "justification": S,
        "evidence": arr(EVIDENCE),
        "value": SCALAR,
        "missing": obj({"code": S, "note": S}, ("code",)),
        "independence": INDEPENDENCE,
        "perturbation": obj({"kind": S, "seed": {"anyOf": [S, N]}, "detail": S}, ("kind",)),
    },
    ("alternativeId", "criterionId"),
)
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
    "analysisId": S, "contributorId": S, "written": I, "criteriaVersion": S, "summary": S,
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
            "minted. " + _RETENTION
        ),
        determinism="A store read and, for a new id, one write of a fixed empty frame.",
        failure=(
            "An unknown or expired id with no question is refused, naming the retention "
            "window; with a question it starts afresh under that id. Nothing is deleted."
        ),
        input_schema=obj({"analysis_id": S, "question": S}),
        output_schema=obj(
            {"analysisId": S, "created": B, "question": S, "alternatives": I, "criteria": I,
             "stage": I, "summary": S},
            ("analysisId", "created", "question", "alternatives", "criteria", "stage", "summary"),
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
                     "byCode": arr(obj({"code": S, "count": I}, ("code", "count")))},
                    ("alternatives", "criteria", "cells", "outstanding", "superseded", "byCode"),
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
                "summary": S,
            },
            ("analysisId", "view", "question", "stage", "counts", "omitted", "summary"),
        ),
    ),
    ToolSpec(
        name="corpus_add", family="corpus", stage="2, 5", status="planned",
        minimum_viable=True, cut_rank=None, research_row=3, issue=53,
        contract=(
            "Add source documents to an analysis's corpus. Each is normalised with the "
            "versioned normaliser, given a stable id from its content hash (so adding the same "
            "text twice is idempotent), and recorded with character offsets into the normalised "
            "full document. Says which sources were cleaned and keeps the offset map."
        ),
        determinism="A fixed chunker and a versioned normaliser over text the caller supplies; no fetch.",
        failure="A source with no text is refused, naming which one; nothing is partially added.",
        input_schema=obj(
            {
                "analysis_id": S,
                "sources": arr(obj({"id": S, "title": S, "text": S, "uri": S, "mediaType": S}, ("text",))),
                "chunking": obj({"windowChars": I, "overlapChars": I}),
            },
            ("analysis_id", "sources"),
        ),
        output_schema=obj(
            {"analysisId": S, "documentIds": arr(S), "spanCount": I, "tokenEstimate": I,
             "warnings": arr(S), "summary": S},
            ("analysisId", "documentIds", "spanCount", "tokenEstimate", "warnings", "summary"),
        ),
    ),
    ToolSpec(
        name="corpus_search", family="corpus", stage="2, 3, 5", status="planned",
        minimum_viable=True, cut_rank=None, research_row=4, issue=54,
        contract=(
            "Find spans in the corpus by lexical match: BM25 plus normalised substring, never "
            "embeddings (ADR-0010). Returns the top k spans with their document, offsets and "
            "text. An empty query returns the whole corpus when it is under the inline "
            "threshold. Retrieve small, present wide."
        ),
        determinism="A fixed tokenizer, a fixed stopword list, and the tie-break (score, documentId, start).",
        failure="An empty query over a corpus above the inline threshold is refused with the threshold and the size.",
        input_schema=obj(
            {"analysis_id": S, "query": S, "k": I, "document_ids": arr(S),
             "must_include": arr(S), "window_chars": I},
            ("analysis_id", "query"),
        ),
        output_schema=obj(
            {
                "analysisId": S, "query": S,
                "hits": arr(obj(
                    {"spanId": S, "documentId": S, "start": I, "end": I, "text": S, "score": N},
                    ("spanId", "documentId", "start", "end", "text", "score"))),
                "inlined": B, "summary": S,
            },
            ("analysisId", "query", "hits", "inlined", "summary"),
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
            "tombstoned, never deleted. Near-duplicates and alternatives with no source are "
            "flagged, never merged (#55)."
        ),
        determinism="A validated write; the near-duplicate check is normalisation and a named threshold.",
        failure="Duplicate ids, or dropping a scored row, is refused with nothing written.",
        input_schema=obj({"analysis_id": S, "alternatives": arr(ALTERNATIVE)}, ("analysis_id", "alternatives")),
        output_schema=obj(
            {"analysisId": S, "alternatives": arr(S), "summary": S},
            ("analysisId", "alternatives", "summary"),
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
            "changed criteria whose edit moves no boundary in editorial. Under-defined "
            "criteria are reported in definitionGaps, not refused."
        ),
        determinism="Schema checks, a versioned diff of definitions, and a lexical anchor check.",
        failure=(
            "Refused with nothing written: an unknown scale, a missing required anchor, an "
            "anchor on a level the scale cannot take, an undeclared missing-rule code, a "
            "target with no target preference, or dropping a criterion that cells refer to."
        ),
        input_schema=obj(
            {"analysis_id": S, "criteria": arr(CRITERION), "editorial": arr(S)},
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
                "summary": S,
            },
            ("analysisId", "criteria", "criteriaVersion", "revised", "supersededCells",
             "definitionGaps", "defaultedPreference", "summary"),
        ),
    ),
    ToolSpec(
        name="frame_confirm", family="frame", stage="4", status="planned",
        minimum_viable=True, cut_rank=None, research_row=8, issue=57,
        contract=(
            "The ADR-0005 step-4 gate. Where the client supports elicitation, asks the user "
            "to confirm the frame and criteria with a flat form (decision, notes, criteria to "
            "drop); where it does not, returns mechanism=out-of-band with instructions to ask "
            "in chat and call again with the user's decision. The tool never confirms on its "
            "own behalf. A confirmation is stored as authored, timestamped provenance."
        ),
        determinism="It records a decision; it does not make one.",
        failure="A call that carries no human decision and cannot elicit one returns confirmed=false with instructions, never an error.",
        input_schema=obj(
            {"analysis_id": S, "scope": enum("all", "frame", "alternatives", "criteria"),
             "decision": enum("confirm", "revise", "reject"), "confirmed_by": S,
             "confirmation_text": S},
            ("analysis_id",),
        ),
        output_schema=obj(
            {
                "analysisId": S, "confirmed": B,
                "mechanism": enum("elicitation", "out-of-band", "recorded"),
                "record": opt(obj(
                    {"authorId": S, "at": S, "text": S, "criteriaVersion": S, "decision": S},
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
            "refused if the set moved since you read it. Honesty rules run before the bytes "
            "land (ADR-0024)."
        ),
        determinism="Schema validation and the honesty rules over the merged document; the moment is supplied, never read from a clock.",
        failure=(
            "Refused with nothing written: a cell on an unknown criterion, a reused assertion "
            "id, a criteria-version mismatch, or an honesty violation such as a second claim on "
            "a cell with no independence recorded."
        ),
        input_schema=obj(
            {"analysis_id": S, "contributor_id": S, "author": AUTHOR,
             "at": {"type": "string", "format": "date-time"}, "cells": arr(CELL),
             "expected_criteria_version": S},
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
            "criteria and mark the rest deferred' a first-class instruction."
        ),
        determinism="Set arithmetic over the frame, then measures_write.",
        failure="An undeclared code is refused, listing what is known and how to declare a new one.",
        input_schema=obj(
            {"analysis_id": S, "contributor_id": S, "author": AUTHOR,
             "at": {"type": "string", "format": "date-time"}, "code": S, "note": S,
             "criterion_ids": at_least_one(S), "alternative_ids": at_least_one(S),
             "independence": INDEPENDENCE},
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
            "refused, naming the level of measurement; a nominal criterion gets modes only."
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
                     "offScale": I, "polarised": B, "contested": B},
                    ("alternativeId", "criterionId", "measure", "n", "reduced", "polarised",
                     "contested"))),
                "summary": S,
            },
            ("analysisId", "reduction", "cells", "summary"),
        ),
    ),
    ToolSpec(
        name="stability_report", family="report", stage="6", status="planned",
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
                "dominanceSurvival": arr(obj({"alternativeId": S, "rate": N}, ("alternativeId", "rate"))),
                "paretoChurn": N,
                "perCriterion": arr(obj(
                    {"criterionId": S, "agreement": opt(N), "lowestRung": opt(INDEPENDENCE),
                     "histogram": arr(obj({"level": S, "count": I}, ("level", "count"))),
                     "compression": N},
                    ("criterionId", "agreement", "lowestRung", "histogram", "compression"))),
                "weighted": opt(obj(
                    {"tauDistribution": arr(N), "top1Churn": N, "top3Churn": N,
                     "band": enum("stable", "borderline", "unstable")},
                    ("tauDistribution", "top1Churn", "top3Churn", "band"))),
                "summary": S,
            },
            ("analysisId", "dominanceSurvival", "paretoChurn", "perCriterion", "weighted", "summary"),
        ),
    ),
    ToolSpec(
        name="report_weaknesses", family="report", stage="6", status="planned",
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
        name="disclose_variance", family="report", stage="6", status="planned",
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
        name="compute_coupling_matrix", family="criteria", stage="3", status="planned",
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
        name="fit_bradley_terry", family="measures", stage="5", status="planned",
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
                "summary": S,
            },
            ("analysisId", "total", "structural", "applicable", "present", "settledAbsent",
             "informativeAbsent", "outstanding", "examinedRate", "valuedRate", "silenceRate",
             "degradations", "supersededCells", "honestyProblems", "summary"),
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
    return tuple(spec for spec in FROZEN_TOOLS if spec.status != "planned")


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
        "tools": 13, "tokens": 7325, "bytes": 17308,
        "sha256": "6a723227816afff55957c679775bde637465ddb8059d414274407c251f5d4423",
    },
    "wholeSurface": {
        "tools": 22, "tokens": 10582, "bytes": 25601,
        "sha256": "ab6d0e7cf0bcf9e7783d452c545f2c55c796a0ec3e561837689d1211f74433de",
    },
}
