"""The command line: the cheapest audit of the core, and the v1 proof.

Written first among the surfaces even though the product's surfaces are an MCP
connector and a web application, because it is the one that costs nothing and
catches the most per minute. It applies a pressure the others do not: every
argument has to be flat, ordered and serialisable; no live object may cross the
boundary; and nothing in the core may print or exit.

``demo`` is the **one-command test** -- the definition of v1 for this package.
It runs the whole deterministic chain end to end on a real store with every seam
on its default, and prints something a person can read. If it stops passing, a
seam swap broke the core rather than the seam.

The verbs are the same functions the MCP connector exposes, referenced from one
registry (:mod:`rubricator.surface`). Authoring two lists separately is how two
surfaces come to disagree while a comment claims they cannot.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.contributors import human, persona
from rubricator.tools.analysis import (
    analysis_open,
    criteria_set,
    frame_set,
    measures_mark_missing,
    measures_write,
    report_completeness,
)

__all__ = ["main", "demo"]

#: A moment, so `demo` is byte-reproducible. A fixture whose timestamps move is
#: a fixture nobody can diff, and this command is also a test.
_DEMO_MOMENT = "2026-08-22T12:00:00Z"


def demo(root: str | None = None) -> int:
    """Run the whole chain on one analysis, and print it.

    Deliberately small and deliberately complete: one contributor signing under a
    persona, one scored cell with a rationale, one honest blank that moves
    ``silenceRate``, and a completeness report. Every seam is on its default.
    """
    runtime = build_runtime(root=root, now=fixed_clock(_DEMO_MOMENT))
    store = runtime.store
    at = runtime.now()
    analysis_id = "demo"

    analysis_open(store, analysis_id=analysis_id, question="Which runtime should we adopt?")
    frame_set(
        store,
        analysis_id=analysis_id,
        alternatives=[
            {"id": "alpha", "label": "Alpha"},
            {"id": "beta", "label": "Beta"},
        ],
        ambiguities=['"adopt" — for the new service only, or everywhere?'],
    )
    criteria_set(
        store,
        analysis_id=analysis_id,
        criteria=[
            {
                "id": "support",
                "label": "Vendor support",
                "anchors": {
                    "1": "no published support commitment",
                    "3": "a support commitment is stated but not dated",
                    "5": "a dated, published support commitment exists",
                },
            }
        ],
    )

    ana = human("ana", "Ana Ruiz")
    cfo = persona(ana, "the sceptical CFO", acting_as="scored on cost exposure alone")

    measures_write(
        store,
        analysis_id=analysis_id,
        contributor_id="ana",
        author=cfo,
        at=at,
        cells=[
            {
                "alternativeId": "alpha",
                "criterionId": "support",
                "value": 5,
                "justification": "the vendor publishes a dated support window",
                "independence": "independent",
                "evidence": [
                    {
                        "id": "e1",
                        "target": "rendition:alpha-support",
                        "sourceType": "primary",
                        "stance": "supports",
                        "derivedFrom": [],
                        "selectors": [
                            {
                                "type": "TextQuoteSelector",
                                "exact": "supported until 30 June 2029",
                            }
                        ],
                        "check": {
                            "status": "exact",
                            "checkedAt": at,
                            "checkerVersion": "rubricator/0.0.1",
                        },
                    }
                ],
            }
        ],
    )
    measures_mark_missing(
        store,
        analysis_id=analysis_id,
        contributor_id="ana",
        author=cfo,
        at=at,
        code="not-evidenced",
        note="searched the vendor site and two industry reports; none states a support window",
        criterion_ids=["support"],
        alternative_ids=["beta"],
    )

    report = report_completeness(store, analysis_id=analysis_id)

    print(f"analysis: {analysis_id}  ({len(store.contributors(analysis_id))} contributor)")
    print(f"  signed by: {cfo['displayName']}  (principal: {cfo['principalId']}, {cfo['kind']})")
    print(f"  cells: {report['total']}  valued: {report['present']}  blank: {report['settledAbsent']}")
    print(f"  silenceRate: {report['silenceRate']:.2f}"
          f"   (informative blanks: {report['informativeAbsent']})")
    print(f"  outstanding: {report['outstanding']}")
    if report["degradations"]:
        print(f"  could not interpret: {len(report['degradations'])}")
    caveat = runtime.caveat()
    if caveat:
        print(f"  note: {caveat}")
    return 0


def _show(store, analysis_id: str) -> int:
    from rubricator.merge import merge_contributions

    merged = merge_contributions(
        store.frame(analysis_id),
        store.contributions(analysis_id),
        renditions=store.renditions(analysis_id),
    )
    json.dump(merged, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a status rather than exiting, so it is testable."""
    parser = argparse.ArgumentParser(prog="rubricator", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the whole chain end to end and print it")
    p_demo.add_argument("--root", default=None, help="directory to store in (default: in memory)")

    p_show = sub.add_parser("show", help="print one merged analysis as JSON")
    p_show.add_argument("analysis_id")
    p_show.add_argument("--root", required=True)

    p_report = sub.add_parser("report", help="completeness counts for one analysis")
    p_report.add_argument("analysis_id")
    p_report.add_argument("--root", required=True)

    args = parser.parse_args(argv)

    if args.command == "demo":
        return demo(args.root)
    runtime = build_runtime(root=args.root)
    if args.command == "show":
        return _show(runtime.store, args.analysis_id)
    report = report_completeness(runtime.store, analysis_id=args.analysis_id)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0
