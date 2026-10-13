"""Build the resume evaluation's scenarios from the real verbs: tool results in, expectations beside them.

Each scenario drives a fresh in-memory analysis through the frozen surface to a
partial state, then records exactly what a resuming session's reads return
(``analysis_get`` summary, ``frame_confirm`` with no decision,
``report_completeness``, and the criteria view where a declared code needs it).
The expectations are stated by hand and checked against those results here, so
a tool whose output drifts fails the build of the fixture rather than silently
changing what the subject is graded against. Nothing here calls a model.

    python scripts/resume_scenarios.py docs/evaluation/resume/scenarios.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import bind

MONDAY, WEDNESDAY = "2026-10-12T09:30:00Z", "2026-10-14T16:00:00Z"
ANA = {"id": "ana", "displayName": "Ana", "kind": "human"}
KETTLES = [("brindle", "Brindle"), ("copperleaf", "Copperleaf"), ("tamsin", "Tamsin")]
ANCHORS = [{"level": "1", "text": "no published policy"}, {"level": "3", "text": "a policy with gaps"},
           {"level": "5", "text": "a dated, complete policy"}]
CRITERIA = ["repair-policy", "spare-parts", "noise"]
SPAN = {"id": "e1", "target": "doc:brochure", "sourceType": "primary", "stance": "supports",
        "excerpt": "parts stocked for ten years"}


def _score(alt, crit):
    return {"alternativeId": alt, "criterionId": crit, "value": 4,
            "justification": "the brochure states it", "evidence": [SPAN]}


def _blank(alt, crit, code, note):
    return {"alternativeId": alt, "criterionId": crit, "missing": {"code": code, "note": note}}


SILENT = "the maker's pages were read and say nothing on it"
CONFLICT = "the manual and the support page give different terms"
LEFT = "the user asked to leave noise until the lab results arrive"


def _analysis(*, criteria=None, confirm=True, skip=False):
    clock = {"now": MONDAY}
    runtime = build_runtime(blobs={}, now=lambda: clock["now"])
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="kettles", question="which kettle should the office buy?",
                           allow_skip_confirmation=skip)
    verbs["frame_set"](analysis_id="kettles", ambiguities=[])
    verbs["alternatives_set"](analysis_id="kettles",
                              alternatives=[{"id": i, "label": label} for i, label in KETTLES])
    verbs["criteria_set"](analysis_id="kettles", criteria=criteria or [
        {"id": c, "label": c.replace("-", " "), "anchors": ANCHORS} for c in CRITERIA])
    if skip:
        return verbs, clock
    verbs["frame_confirm"](analysis_id="kettles")
    if confirm:
        verbs["frame_confirm"](analysis_id="kettles", decision="confirm", confirmed_by="Ana",
                               confirmation_text="Yes, those three criteria, go ahead.")
    return verbs, clock


def _write(verbs, cells, author=ANA):
    verbs["measures_write"](analysis_id="kettles", contributor_id=author["id"], author=author, cells=cells)


def _reads(verbs, clock, *, criteria_view=False) -> dict[str, Any]:
    clock["now"] = WEDNESDAY
    out = {
        "analysis_get": verbs["analysis_get"](analysis_id="kettles", view="summary"),
        "frame_confirm": verbs["frame_confirm"](analysis_id="kettles"),
        "report_completeness": verbs["report_completeness"](analysis_id="kettles"),
    }
    if criteria_view:
        out["analysis_get (criteria)"] = verbs["analysis_get"](analysis_id="kettles", view="criteria")
    return out


def s1_mixed():
    verbs, clock = _analysis()
    _write(verbs, [_score("brindle", "repair-policy"),
                   _blank("brindle", "spare-parts", "not-evidenced", SILENT),
                   _blank("copperleaf", "repair-policy", "indeterminate", CONFLICT),
                   _blank("copperleaf", "noise", "deferred", LEFT),
                   _blank("tamsin", "noise", "deferred", LEFT)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=4, aside=2, blank=2, scored=1,
                                      rescore=0, na=0, next="score")


def s2_never_confirmed():
    verbs, clock = _analysis(confirm=False)
    return _reads(verbs, clock), dict(confirmation="not-confirmed", nobody=9, aside=0, blank=0,
                                      scored=0, rescore=0, na=0, next="confirm")


def s3_criteria_changed():
    verbs, clock = _analysis()
    _write(verbs, [_score("brindle", "repair-policy"),
                   _blank("copperleaf", "repair-policy", "indeterminate", CONFLICT),
                   _score("tamsin", "spare-parts")])
    revised = [{"id": "repair-policy", "label": "repair policy", "anchors": [
        {**ANCHORS[0], "text": "no policy, or one that excludes the heating element"}, *ANCHORS[1:]]}]
    verbs["criteria_set"](analysis_id="kettles", criteria=revised + [
        {"id": c, "label": c.replace("-", " "), "anchors": ANCHORS} for c in CRITERIA[1:]])
    return _reads(verbs, clock), dict(confirmation="changed", nobody=6, aside=0, blank=1, scored=2,
                                      rescore=2, na=0, next="confirm")


def s4_only_deferred_left():
    verbs, clock = _analysis()
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in ("repair-policy",)),
                   _score("brindle", "spare-parts"),
                   _blank("copperleaf", "spare-parts", "not-evidenced", SILENT),
                   _blank("tamsin", "spare-parts", "withheld", "the vendor shared it under NDA"),
                   *(_blank(a, "noise", "deferred", LEFT) for a, _ in KETTLES)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=0, aside=3, blank=2, scored=4,
                                      rescore=0, na=0, next="ask-deferred")


def s5_declared_code():
    criteria = [{"id": c, "label": c.replace("-", " "), "anchors": ANCHORS} for c in CRITERIA[:2]] + [
        {"id": "noise", "label": "noise", "anchors": ANCHORS, "missingCodes": [
            {"id": "queued", "broader": "deferred", "means": "waiting on the lab's decibel report"}]}]
    verbs, clock = _analysis(criteria=criteria)
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in CRITERIA[:2] if (a, c) != ("tamsin", "spare-parts")),
                   _blank("brindle", "noise", "queued", "lab report due Friday"),
                   _blank("copperleaf", "noise", "queued", "lab report due Friday"),
                   _blank("tamsin", "noise", "not-evidenced", SILENT)])
    return _reads(verbs, clock, criteria_view=True), dict(
        confirmation="confirmed", nobody=1, aside=2, blank=1, scored=5, rescore=0, na=0, next="score")


def s6_settled():
    verbs, clock = _analysis()
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in CRITERIA if c != "noise"),
                   _blank("brindle", "noise", "not-evidenced", SILENT),
                   _blank("copperleaf", "noise", "indeterminate", CONFLICT),
                   _blank("tamsin", "noise", "not-evidenced", SILENT)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=0, aside=0, blank=3, scored=6,
                                      rescore=0, na=0, next="review")


def s7_reconfirmed_rescore():
    verbs, clock = _analysis()
    _write(verbs, [_score(a, c) for a, _ in KETTLES for c in CRITERIA])
    revised = [{"id": "noise", "label": "noise", "anchors": [
        {**ANCHORS[0], "text": "over 60 dB at one metre"}, *ANCHORS[1:]]}]
    verbs["criteria_set"](analysis_id="kettles", criteria=[
        {"id": c, "label": c.replace("-", " "), "anchors": ANCHORS} for c in CRITERIA[:2]] + revised)
    verbs["frame_confirm"](analysis_id="kettles")
    verbs["frame_confirm"](analysis_id="kettles", decision="confirm", confirmed_by="Ana",
                           confirmation_text="Yes, the new noise anchors are right.")
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=0, aside=0, blank=0, scored=9,
                                      rescore=3, na=0, next="rescore")


def s8_skipped():
    verbs, clock = _analysis(skip=True)
    _write(verbs, [_score("brindle", "repair-policy")])
    return _reads(verbs, clock), dict(confirmation="skipped", nobody=8, aside=0, blank=0, scored=1,
                                      rescore=0, na=0, next="score")


def s9_revise_asked():
    verbs, clock = _analysis(confirm=False)
    verbs["frame_confirm"](analysis_id="kettles", decision="revise", confirmed_by="Ana",
                           confirmation_text="Drop noise and add the kettle's weight instead.")
    return _reads(verbs, clock), dict(confirmation="not-confirmed", nobody=9, aside=0, blank=0,
                                      scored=0, rescore=0, na=0, next="confirm")


def s10_two_raters_and_a_removed_row():
    verbs, clock = _analysis()
    _write(verbs, [{**_score(a, c), "independence": "independent"}
                   for a, _ in KETTLES for c in CRITERIA if c != "noise"])
    ben = {"id": "ben", "displayName": "Ben", "kind": "human"}
    _write(verbs, [{**_score("brindle", "repair-policy"), "value": 2, "independence": "independent"}], ben)
    verbs["alternatives_set"](analysis_id="kettles", alternatives=[
        {"id": i, "label": label, **({"tombstoned": True} if i == "tamsin" else {})}
        for i, label in KETTLES])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=2, aside=0, blank=0, scored=7,
                                      rescore=0, na=0, next="score")


def s11_not_applicable_and_partial_scope():
    verbs, clock = _analysis(confirm=False)
    verbs["frame_confirm"](analysis_id="kettles", decision="confirm", scope="criteria",
                           confirmed_by="Ana", confirmation_text="The criteria are right; I have not looked at the kettles yet.")
    return _reads(verbs, clock), dict(confirmation="not-confirmed", nobody=9, aside=0, blank=0,
                                      scored=0, rescore=0, na=0, next="confirm")


def s12_not_applicable():
    verbs, clock = _analysis()
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in CRITERIA[:2]),
                   _blank("brindle", "noise", "not-applicable", "Brindle is a stovetop kettle with no motor"),
                   _blank("copperleaf", "noise", "not-evidenced", SILENT)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=1, aside=0, blank=1, scored=6,
                                      rescore=0, na=1, next="score")


SCENARIOS = {f.__name__.split("_", 1)[0]: f for f in (
    s1_mixed, s2_never_confirmed, s3_criteria_changed, s4_only_deferred_left, s5_declared_code,
    s6_settled, s7_reconfirmed_rescore, s8_skipped, s9_revise_asked,
    s10_two_raters_and_a_removed_row, s11_not_applicable_and_partial_scope, s12_not_applicable)}


def _check(sid: str, reads: dict, want: dict) -> None:
    """The expectations agree with the fields the prompt tells the subject to read, read as it says."""
    summary, done, confirm = reads["analysis_get"], reads["report_completeness"], reads["frame_confirm"]
    declared = {d["id"]: d["broader"] for c in reads.get("analysis_get (criteria)", {}).get("criteria", [])
                for d in c.get("missingCodes", [])}
    by: dict[str, int] = {}
    for row in summary["counts"]["byCode"]:
        meaning = declared.get(row["code"], row["code"])
        by[meaning if meaning == "deferred" else "not-assessed"] = by.get(
            meaning if meaning == "deferred" else "not-assessed", 0) + row["count"]
    record = confirm["record"] or {}
    got = dict(
        confirmation=("changed" if confirm["instructions"] and record.get("decision") == "confirm"
                      and record.get("scope") == "all"
                      else "not-confirmed" if confirm["instructions"]
                      else "skipped" if record.get("decision") == "skip" else "confirmed"),
        nobody=by.get("not-assessed", 0), aside=by.get("deferred", 0), blank=done["settledAbsent"],
        scored=done["present"], rescore=summary["counts"]["superseded"], na=done["structural"],
    )
    mismatch = {k: (v, want[k]) for k, v in got.items() if v != want[k]}
    assert not mismatch, f"{sid}: tool output and expectation disagree: {mismatch}"


def main(out: str) -> None:
    scenarios = []
    for sid, build in SCENARIOS.items():
        reads, want = build()
        _check(sid, reads, want)
        scenarios.append({"id": sid, "toolResults": reads, "expected": want})
    with open(out, "w") as f:
        json.dump(scenarios, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
