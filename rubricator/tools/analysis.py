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
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rubricator.contributors import sign
from rubricator.interpret.resolution import Degradation, degradation_of
from rubricator.schema.vocabulary import vocabulary
from rubricator.store import AnalysisStore

__all__ = [
    "analysis_open",
    "frame_set",
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


def analysis_open(store: AnalysisStore, *, analysis_id: str, question: str) -> dict[str, Any]:
    """Start an analysis. Writes the frame and nothing else.

    An analysis exists before it has any alternatives or criteria, because the
    thing being decided is the first thing that is known and the criteria
    discussion is the valuable part (ADR-0005).
    """
    frame = {
        "id": analysis_id,
        "schemaVersion": 1,
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
    store.put_frame(analysis_id, frame)
    return {"analysisId": analysis_id, "created": True}


def frame_set(
    store: AnalysisStore,
    *,
    analysis_id: str,
    alternatives: Sequence[Mapping[str, Any]],
    ambiguities: Sequence[str] = (),
    decision: str | None = None,
) -> dict[str, Any]:
    """Record what is being compared, and what is still ambiguous about it.

    ``ambiguities`` is required to be *considered*, not required to be non-empty:
    the ADR-0005 rule is that surface ambiguity is surfaced rather than resolved
    silently, and a caller that has genuinely found none says so by passing an
    empty list. What is not available is not passing the argument at all and
    having the question of whether anyone looked go unrecorded.
    """
    frame = store.frame(analysis_id)
    frame["alternatives"] = [dict(a) for a in alternatives]
    if decision:
        frame["subject"]["decision"] = decision
    frame["subject"]["ambiguities"] = list(ambiguities)
    store.put_frame(analysis_id, frame)
    return {
        "analysisId": analysis_id,
        "alternatives": len(frame["alternatives"]),
        "ambiguities": list(ambiguities),
    }


def criteria_set(
    store: AnalysisStore,
    *,
    analysis_id: str,
    criteria: Sequence[Mapping[str, Any]],
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
    ``missing-rule-code-defined``), and on an anchor keyed to a level the scale
    cannot take. Fields a criterion should have and does not are *reported* in
    ``definitionGaps`` -- ADR-0024: incompleteness informs, it does not reject.
    """
    frame = store.frame(analysis_id)
    declared: dict[str, dict[str, Any]] = {d["id"]: d for d in frame.get("scales", [])}
    problems: list[str] = []
    out: list[dict[str, Any]] = []
    gaps: dict[str, list[str]] = {}

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
        anchors = c.get("anchors")
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
            problems.extend(
                _definition_problems(
                    c.get("id"), definition, [*criterion_codes, *frame.get("missingCodes", [])]
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
        out.append(emitted)
        declared.setdefault(
            scale_id, {"id": scale_id, "broader": "stevens", "means": preset["means"], "params": {}}
        )

    if problems:
        raise ValueError("; ".join(problems))

    frame["criteria"] = out
    frame["scales"] = [declared[k] for k in sorted(declared)]
    store.put_frame(analysis_id, frame)
    return {
        "analysisId": analysis_id,
        "criteria": [c["id"] for c in out],
        # Completeness, not a refusal: which definition fields each criterion
        # still lacks. Empty when every criterion is fully defined.
        "definitionGaps": gaps,
    }


def measures_write(
    store: AnalysisStore,
    *,
    analysis_id: str,
    contributor_id: str,
    author: Mapping[str, Any],
    at: str,
    cells: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Write one contributor's scored cells.

    Writes **only that contributor's file**. Two people scoring the same matrix
    never touch the same key, which is what makes a shared git repository a
    viable backend with no locking protocol, and the merge into one document
    happens on read.
    """
    contribution = _existing(store, analysis_id, contributor_id, author)
    index = {
        (c["alternativeId"], c["criterionId"], c["measure"]): c
        for c in contribution["cells"]
    }

    added: list[tuple[tuple[str, str, str], str]] = []
    for cell in cells:
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
        target["assertions"].append(
            sign(
                author,
                at=at,
                assertion_id=assertion_id,
                value=cell.get("value"),
                missing=cell.get("missing"),
                justification=cell.get("justification"),
                evidence=list(cell.get("evidence", [])),
                independence=cell.get("independence"),
                perturbation=cell.get("perturbation"),
            )
        )

    contribution["cells"] = [index[k] for k in sorted(index)]
    _refuse_dishonest(store, analysis_id, contributor_id, contribution, added=added)
    store.put_contribution(analysis_id, contributor_id, contribution)
    return {"analysisId": analysis_id, "contributorId": contributor_id, "written": len(cells)}


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
    """
    frame = store.frame(analysis_id)
    criteria = list(criterion_ids) or [c["id"] for c in frame["criteria"]]
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

    alternatives = list(alternative_ids) or [a["id"] for a in frame["alternatives"]]
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
    )
    return {**result, "code": code, "marked": len(cells)}


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
    from rubricator.merge import merge_contributions
    from rubricator.rules import honesty_problems

    frame = store.frame(analysis_id)
    merged = merge_contributions(
        frame, store.contributions(analysis_id), renditions=store.renditions(analysis_id)
    )
    vocab = vocabulary()

    total = present = structural = settled = informative = outstanding = 0
    degradations: list[Degradation] = []

    for cell in merged["cells"]:
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
        # Not completeness: the honesty problems the write-time hook could not
        # refuse (they sit on assertions already stored). Reported here so they
        # are seen; #61's analysis_validate is where they reject.
        "honestyProblems": [
            {"path": p.path, "message": p.message, "fix": p.fix, "ruleId": p.rule_id}
            for p in honesty_problems(merged)
        ],
    }


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


def declarations_for(document: Mapping[str, Any], criterion_id: str) -> list[Mapping[str, Any]]:
    """The missingness declarations in scope for one criterion, nearest first.

    The criterion's own codes come before the analysis's, as in the companion's
    ``makeVocabulary``: the resolver takes the first match, so a criterion-scoped
    redefinition wins inside that criterion and nowhere else.
    """
    criterion = next((c for c in document.get("criteria", []) if c.get("id") == criterion_id), {})
    return [*criterion.get("missingCodes", []), *document.get("missingCodes", [])]


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
) -> None:
    """The write-time honesty hook (ADR-0024): refuse before the bytes land.

    Checks the document as it **would be merged** with this contribution in
    place, because the rules are cross-contributor: two people each scoring a
    cell once is fine on its own and dishonest together if neither recorded
    independence.

    **Refuses only for the assertions this call adds**, the ones the caller can
    still change. A problem on an assertion already stored -- this contributor's
    or anyone's -- does not block: nothing can amend a stored assertion in place,
    so refusing would lock that contributor (or everyone) out of the whole
    analysis over one cell. `comparanda` counts by difference for the same
    reason. Those problems stay visible: :func:`report_completeness` returns
    them as ``honestyProblems`` over the merged document.
    """
    from rubricator.merge import merge_contributions
    from rubricator.rules import honesty_problems

    others = [(cid, c) for cid, c in store.contributions(analysis_id) if cid != contributor_id]
    merged = merge_contributions(
        store.frame(analysis_id), sorted([*others, (contributor_id, contribution)])
    )
    # Matched by cell *and* id: a caller's ids need only be unique per cell, so
    # an id alone would pull in another cell's stored problem.
    own = {f"cells[{'/'.join(key)}].assertions[{contributor_id}:{a}]" for key, a in added}
    problems = [
        p
        for p in honesty_problems(merged)
        if any(p.path == o or p.path.startswith(f"{o}.") for o in own)
    ]
    if problems:
        raise ValueError(
            "refused, nothing was written: "
            + "; ".join(f"{p.path}: {p.message} Fix: {p.fix}" for p in problems)
        )


def _existing(
    store: AnalysisStore,
    analysis_id: str,
    contributor_id: str,
    author: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        contribution = store._read(store.contribution_key(analysis_id, contributor_id))
    except KeyError:
        contribution = {"contributorId": contributor_id, "authors": [], "cells": []}
    authors = {a["id"]: a for a in contribution["authors"]}
    authors.setdefault(author["id"], dict(author))
    contribution["authors"] = [authors[k] for k in sorted(authors)]
    contribution.setdefault("cells", [])
    return contribution


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
