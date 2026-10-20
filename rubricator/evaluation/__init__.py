"""The evaluation suite of ADR-0008: the harness here, the checks as they land (#88-#94).

See :mod:`rubricator.evaluation.harness` for the runner and what a report records.
"""

from rubricator.evaluation.adherence import ADHERENCE_SUITE, DEFERRAL_ADHERENCE, INVENTED_CRITERIA
from rubricator.evaluation.discrimination import DISCRIMINATION_SUITE, confidence_report, gate_failures
from rubricator.evaluation.proper_scoring import ALLOWED_CERTAINTY, certainty_report, graded_certainty
from rubricator.evaluation.harness import (
    HARNESS_VERSION,
    MIN_ANALYSES_FOR_INTERVAL,
    Fixture,
    Metric,
    Subject,
    expected_subject,
    load_fixtures,
    report_store,
    run_key,
    run_suite,
    save_report,
    version_inputs,
)

__all__ = [
    "DISCRIMINATION_SUITE", "confidence_report", "gate_failures",
    "ALLOWED_CERTAINTY", "certainty_report", "graded_certainty",
    "ADHERENCE_SUITE", "DEFERRAL_ADHERENCE", "INVENTED_CRITERIA",
    "HARNESS_VERSION", "MIN_ANALYSES_FOR_INTERVAL", "Fixture", "Metric", "Subject", "expected_subject", "load_fixtures",
    "report_store", "run_key", "run_suite", "save_report", "version_inputs",
]
