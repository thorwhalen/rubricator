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


def _analysis(*, criteria=None, confirm=True):
    clock = {"now": MONDAY}
    runtime = build_runtime(blobs={}, now=lambda: clock["now"])
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="kettles", question="which kettle should the office buy?")
    verbs["frame_set"](analysis_id="kettles", ambiguities=[])
    verbs["alternatives_set"](analysis_id="kettles",
                              alternatives=[{"id": i, "label": label} for i, label in KETTLES])
    verbs["criteria_set"](analysis_id="kettles", criteria=criteria or [
        {"id": c, "label": c.replace("-", " "), "anchors": ANCHORS} for c in CRITERIA])
    verbs["frame_confirm"](analysis_id="kettles")
    if confirm:
        verbs["frame_confirm"](analysis_id="kettles", decision="confirm", confirmed_by="Ana",
                               confirmation_text="Yes, those three criteria, go ahead.")
    return verbs, clock


def _write(verbs, cells):
    verbs["measures_write"](analysis_id="kettles", contributor_id="ana", author=ANA, cells=cells)


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
                                      rescore=0, next="score")


def s2_never_confirmed():
    verbs, clock = _analysis(confirm=False)
    return _reads(verbs, clock), dict(confirmation="not-confirmed", nobody=9, aside=0, blank=0,
                                      scored=0, rescore=0, next="confirm")


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
                                      rescore=2, next="confirm")


def s4_only_deferred_left():
    verbs, clock = _analysis()
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in ("repair-policy",)),
                   _score("brindle", "spare-parts"),
                   _blank("copperleaf", "spare-parts", "not-evidenced", SILENT),
                   _blank("tamsin", "spare-parts", "withheld", "the vendor shared it under NDA"),
                   *(_blank(a, "noise", "deferred", LEFT) for a, _ in KETTLES)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=0, aside=3, blank=2, scored=4,
                                      rescore=0, next="ask-deferred")


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
        confirmation="confirmed", nobody=1, aside=2, blank=1, scored=5, rescore=0, next="score")


def s6_settled():
    verbs, clock = _analysis()
    _write(verbs, [*(_score(a, c) for a, _ in KETTLES for c in CRITERIA if c != "noise"),
                   _blank("brindle", "noise", "not-evidenced", SILENT),
                   _blank("copperleaf", "noise", "indeterminate", CONFLICT),
                   _blank("tamsin", "noise", "not-evidenced", SILENT)])
    return _reads(verbs, clock), dict(confirmation="confirmed", nobody=0, aside=0, blank=3, scored=6,
                                      rescore=0, next="review")


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
                                      rescore=3, next="rescore")


SCENARIOS = {f.__name__.split("_", 1)[0]: f for f in (
    s1_mixed, s2_never_confirmed, s3_criteria_changed, s4_only_deferred_left, s5_declared_code,
    s6_settled, s7_reconfirmed_rescore)}


def _check(sid: str, reads: dict, want: dict) -> None:
    """The expectations agree with the fields the prompt tells the subject to read."""
    summary, done, confirm = reads["analysis_get"], reads["report_completeness"], reads["frame_confirm"]
    by = {r["code"]: r["count"] for r in summary["counts"]["byCode"]}
    got = dict(
        confirmation=("not-confirmed" if not confirm["confirmed"]
                      else "changed" if confirm["instructions"] else "confirmed"),
        nobody=by.get("not-assessed", 0), aside=sum(n for c, n in by.items() if c != "not-assessed"),
        blank=done["settledAbsent"], scored=done["present"], rescore=summary["counts"]["superseded"],
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
