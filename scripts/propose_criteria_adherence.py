"""Score a propose-criteria adherence run: invented frames in, one row of numbers per arm.

The subject writes a JSON array of ``{"frameId", "output"}``; this grades each
proposal against ``docs/evaluation/propose-criteria/frames.json`` with no model
call. The checks are #68's done-when, made mechanical:

- the criteria go to ``criteria_set`` as they stand, with no definition gaps and
  no defaulted preference;
- the proposal keeps its own ladder (:func:`rubricator.ladder.proposal_problems`:
  leaves are exactly the criteria, closed reject codes, every sibling pair
  flagged, group sizes, provenance);
- the means objective the user stated as a requirement is rejected as one;
- no criterion is taken from the alternatives' brochures (the trap word);
- every user-stated quote is the user's words, verbatim;
- no anchor is worded as an absence, which a scorer could never meet.

    python scripts/propose_criteria_adherence.py docs/evaluation/propose-criteria/frames.json out-*.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ladder import proposal_problems
from rubricator.surface import bind

_ABSENCE = re.compile(r"\bno source\b|\bdoes not (?:mention|state)\b|\bnothing (?:is )?stated\b", re.I)


def _accepted(frame: Mapping[str, Any], proposal: Mapping[str, Any]) -> bool:
    verbs = bind(build_runtime(blobs={}, now=fixed_clock("2026-10-13T12:00:00Z")))
    verbs["analysis_open"](analysis_id="a", question=frame["subject"]["question"],
                           allow_skip_confirmation=True)
    try:
        result = verbs["criteria_set"](analysis_id="a", criteria=proposal.get("criteria", []))
    except (KeyError, ValueError, TypeError):
        return False
    return not result["definitionGaps"] and not result["defaultedPreference"]


def _criterion_text(proposal: Mapping[str, Any]) -> str:
    return " ".join(f"{c.get('id')} {c.get('label')} {(c.get('definition') or {}).get('question')}"
                    for c in proposal.get("criteria", [])).lower()


def grade(spec: Mapping[str, Any], outputs: list[Mapping[str, Any]]) -> dict[str, str]:
    """One row of numbers for one arm, each ``hits/applicable``."""
    by_id = {o["frameId"]: o["output"] for o in outputs}
    frames = [f for f in spec["frames"] if f["id"] in by_id]

    def rate(selected, ok):
        hits = [ok(f, by_id[f["id"]]) for f in selected]
        return f"{sum(hits)}/{len(hits)}"

    def rejected_as(f, o, reason, word):
        return any(r.get("reason") == reason and word in str(r.get("label", "")).lower()
                   for r in o.get("rejected", []))

    return {
        "criteria_set_no_repair": rate(frames, _accepted),
        "ladder_kept": rate(frames, lambda f, o: proposal_problems(o) == []),
        "means_rejected": rate(frames, lambda f, o: rejected_as(f, o, "means-objective", f["expected"]["means"])),
        "brochure_trap_avoided": rate(frames, lambda f, o: f["expected"]["trap"] not in _criterion_text(o)),
        "user_rejected_honoured": rate([f for f in frames if "userRejected" in f["expected"]],
                                       lambda f, o: rejected_as(f, o, "user-rejected", f["expected"]["userRejected"])),
        "quotes_verbatim": rate(frames, lambda f, o: all(
            p.get("quote", "") in f["user"] for p in o.get("provenance", []) if p.get("source") == "user-stated")),
        "no_absence_anchor": rate(frames, lambda f, o: not any(
            _ABSENCE.search(a.get("text", "")) for c in o.get("criteria", []) for a in c.get("anchors", []))),
    }


def problems(spec: Mapping[str, Any], outputs: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    """The ladder problems per frame, for reading a row that is not clean."""
    return {o["frameId"]: proposal_problems(o["output"]) for o in outputs}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    for path in sys.argv[2:]:
        outputs = json.loads(Path(path).read_text())
        print(Path(path).stem, json.dumps(grade(spec, outputs)))
        for frame, found in problems(spec, outputs).items():
            for p in found:
                print(f"  {frame}: {p}")
