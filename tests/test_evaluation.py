"""The evaluation harness skeleton (#86): fixtures in, a report keyed by every version input out.

The two acceptance lines, checked:

- **A report records every version input that could have changed the result** --
  and changing any one of them changes the run key, while the run's time does not.
- **``scipy`` is a test-only extra; the vendored rank statistics are used at
  runtime** -- the package never imports it, and the vendored coefficient matches
  it here, where it is allowed.
"""

from __future__ import annotations

import ast
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

import rubricator
from rubricator.compose import build_runtime
from rubricator.evaluation import (
    Fixture,
    Metric,
    Subject,
    expected_subject,
    load_fixtures,
    run_key,
    run_suite,
    save_report,
)
from rubricator.prompts import prompts
from rubricator.stats import bootstrap_interval, kendall_tau_b
from rubricator.tools.analysis import alternatives_set, analysis_open, criteria_set

PACKAGE_DIR = Path(rubricator.__file__).resolve().parent


def _expected(question: str, alternatives: list[str]) -> dict:
    """An invented, schema-valid expected analysis, built by the tools themselves."""
    runtime = build_runtime(blobs={})
    store = runtime.store
    analysis_open(store, analysis_id="x", question=question)
    alternatives_set(
        store, analysis_id="x", alternatives=[{"id": a, "label": a.title()} for a in alternatives]
    )
    criteria_set(store, analysis_id="x", criteria=[{
        "id": "fit", "label": "Fit", "anchors": {"1": "poor", "3": "fair", "5": "good"},
    }])
    return store.read("x")


def _fixture_bytes() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for fid, family, alts in (
        ("kettles", "known-answer", ["copper", "steel"]),
        ("ferries", "absent-evidence", ["day", "night", "fast"]),
    ):
        files[f"{fid}/fixture.json"] = json.dumps({"id": fid, "family": family}).encode()
        files[f"{fid}/expected.json"] = json.dumps(_expected(f"Which {fid}?", alts)).encode()
        files[f"{fid}/sources/notes.txt"] = f"invented notes about {fid}".encode()
    return files


def _alternatives(fixture: Fixture, produced) -> float:
    return float(len(produced["alternatives"]))


def _valid(fixture: Fixture, produced) -> float:
    return 1.0 if build_runtime(blobs={}).schema.validate(produced).ok else 0.0


SUITE = [
    Metric("alternatives", version=1, tier="ci", measure=_alternatives),
    Metric("schema_valid", version=1, tier="ci", measure=_valid),
]


@pytest.fixture()
def fixtures() -> list[Fixture]:
    return load_fixtures(_fixture_bytes())


def _report(fixtures, **kwargs):
    kwargs.setdefault("now", lambda: "2026-10-12T12:00:00Z")
    kwargs.setdefault("resamples", 200)
    return run_suite(fixtures, kwargs.pop("suite", SUITE), **kwargs)


# --- loading ---------------------------------------------------------------


def test_fixtures_load_sorted_with_sources_and_a_content_digest(fixtures) -> None:
    assert [f.id for f in fixtures] == ["ferries", "kettles"]
    assert fixtures[1].sources == {"notes.txt": b"invented notes about kettles"}
    edited = _fixture_bytes()
    edited["kettles/sources/notes.txt"] = b"edited"
    assert load_fixtures(edited)[1].digest != fixtures[1].digest


@pytest.mark.parametrize("mutate, match", [
    (lambda f: f.pop("kettles/expected.json"), "no expected.json"),
    (lambda f: f.__setitem__("kettles/fixture.json", b'{"id": "other", "family": "x"}'),
     "says id 'other'"),
    (lambda f: f.__setitem__("kettles/fixture.json", b'{"id": "kettles"}'), "names no family"),
    (lambda f: f.__setitem__("stray.json", b"{}"), "not inside a fixture directory"),
    (lambda f: f.__setitem__("kettles/notes.md", b""), "neither"),
])
def test_a_malformed_fixture_is_refused_with_the_key_at_fault(mutate, match) -> None:
    files = _fixture_bytes()
    mutate(files)
    with pytest.raises(ValueError, match=match):
        load_fixtures(files)


# --- running ---------------------------------------------------------------


def test_the_expected_subject_scores_its_own_fixtures(fixtures) -> None:
    report = _report(fixtures)
    assert report["metrics"]["schema_valid"]["mean"] == 1.0
    assert report["perAnalysis"]["ferries"]["alternatives"] == 3.0
    summary = report["metrics"]["alternatives"]
    assert summary["unit"] == "analysis" and summary["n"] == 2 and summary["mean"] == 2.5
    lo, hi = summary["interval"]
    assert 2.0 <= lo <= hi <= 3.0


def test_the_bootstrap_resamples_analyses_not_cells(fixtures) -> None:
    """Two analyses give an interval over two values, however many rows or cells each holds."""
    report = _report(fixtures)
    summary = report["metrics"]["alternatives"]
    assert summary["n"] == 2 and set(report["perAnalysis"]) == {"ferries", "kettles"}
    lo, hi = summary["interval"]
    assert 2.0 <= lo <= hi <= 3.0, "an interval over analyses stays inside their range"


def test_a_failing_subject_or_metric_is_recorded_not_fatal(fixtures) -> None:
    def flaky(fixture, seed):
        if fixture.id == "ferries":
            raise RuntimeError("model timed out")
        return fixture.expected

    def picky(fixture, produced):
        if fixture.id == "kettles":
            raise KeyError("cells")
        return 1.0

    report = _report(
        fixtures,
        subject=Subject("flaky", flaky, version="1", model_id="m-1"),
        suite=[*SUITE, Metric("picky", version=1, tier="ci", measure=picky)],
    )
    assert {(e["fixture"], e["stage"]) for e in report["errors"]} == {
        ("ferries", "subject"), ("kettles", "picky"),
    }
    picky_summary = report["metrics"]["picky"]
    assert picky_summary["n"] == 0 and picky_summary["mean"] is None
    assert picky_summary["errors"] == 2


def test_a_metric_that_does_not_apply_is_not_a_zero(fixtures) -> None:
    only_kettles = Metric("only", 1, "ci", lambda f, p: 1.0 if f.id == "kettles" else None)
    summary = _report(fixtures, suite=[only_kettles])["metrics"]["only"]
    assert summary["n"] == 1 and summary["notApplicable"] == 1 and summary["mean"] == 1.0


@pytest.mark.parametrize("bad", [float("nan"), True, "1", [1.0]])
def test_a_metric_must_return_one_finite_number(fixtures, bad) -> None:
    report = _report(fixtures, suite=[Metric("bad", 1, "ci", lambda f, p: bad)])
    assert report["metrics"]["bad"]["errors"] == 2
    assert "one finite number per analysis" in report["errors"][0]["error"]


def test_an_empty_or_ambiguous_suite_is_refused(fixtures) -> None:
    with pytest.raises(ValueError, match="empty suite"):
        run_suite(fixtures, [])
    with pytest.raises(ValueError, match="unique"):
        run_suite(fixtures, [SUITE[0], SUITE[0]])


# --- attribution -----------------------------------------------------------


def test_the_report_records_every_version_input(fixtures) -> None:
    subject = Subject("arm", lambda f, s: f.expected, version="1", model_id="m-1")
    versions = _report(fixtures, subject=subject, seed=7)["versions"]
    assert set(versions) == {
        "harness", "package", "dependencies", "python", "toolSurface", "schema", "prompts",
        "subject", "model", "seed", "fixtures", "suite", "bootstrap",
    }
    assert len(versions["package"]["sourceSha256"]) == 64
    assert set(versions["dependencies"]) == {"jsonschema", "dol"}
    assert versions["model"] == "m-1" and versions["seed"] == 7
    assert versions["prompts"]["score-cell"]["version"] == prompts()["score-cell"].version
    assert set(versions["fixtures"]) == {"ferries", "kettles"}
    assert versions["schema"]["tag"] == "schema-v1"
    assert versions["bootstrap"]["unit"] == "analysis"


def test_every_version_input_moves_the_run_key_and_the_clock_does_not(fixtures) -> None:
    base = _report(fixtures)
    key = base["runKey"]
    assert _report(fixtures, now=lambda: "2027-01-01T00:00:00Z")["runKey"] == key
    edited_prompts = dict(prompts())
    edited_prompts["score-cell"] = replace(edited_prompts["score-cell"], body="edited, same version")
    changed = {
        "seed": _report(fixtures, seed=1),
        "model": _report(fixtures, subject=replace(expected_subject(), model_id="m-2")),
        "subject config": _report(
            fixtures, subject=replace(expected_subject(), config={"arm": "column-wise"})
        ),
        "prompt body": _report(
            fixtures, subject=replace(expected_subject(), prompts=edited_prompts)
        ),
        "subject version": _report(fixtures, subject=replace(expected_subject(), version="2")),
        "subject code": _report(
            fixtures, subject=replace(expected_subject(), run=lambda f, s: f.expected)
        ),
        "metric code": _report(
            fixtures, suite=[replace(SUITE[0], measure=lambda f, p: 0.0), SUITE[1]]
        ),
        "minimum n": _report(fixtures, min_analyses=3),
        "fixture": _report(fixtures[:1]),
        "metric version": _report(fixtures, suite=[replace(SUITE[0], version=2), SUITE[1]]),
        "bootstrap": _report(fixtures, resamples=201),
    }
    for what, report in changed.items():
        assert report["runKey"] != key, f"changing the {what} did not change the run key"
    tampered = json.loads(json.dumps(base["versions"]))
    for field in ("harness", "package", "dependencies", "toolSurface", "schema", "python"):
        before = tampered[field]
        tampered[field] = "something else"
        assert run_key(tampered) != key, field
        tampered[field] = before


def test_the_same_inputs_reproduce_the_same_report(fixtures) -> None:
    assert _report(fixtures, seed=3) == _report(fixtures, seed=3)


def test_reports_are_stored_by_run_key_and_never_overwrite(fixtures) -> None:
    store: dict[str, bytes] = {}
    first = save_report(_report(fixtures), store)
    second = save_report(_report(fixtures, now=lambda: "2026-10-13T12:00:00Z"), store)
    assert first != second and first.split("/")[0] == second.split("/")[0]
    assert json.loads(store[first])["metrics"]["schema_valid"]["mean"] == 1.0


# --- statistics, and scipy staying out of the package ----------------------


def test_the_package_never_imports_scipy() -> None:
    for path in PACKAGE_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )
            assert not any(n.split(".")[0] == "scipy" for n in names), path


def test_kendall_tau_b_matches_scipy() -> None:
    scipy_stats = pytest.importorskip("scipy.stats")
    rng = random.Random(20261012)
    for _ in range(300):
        n = rng.randint(2, 30)
        x = [rng.randint(1, 5) for _ in range(n)]
        y = [rng.randint(1, 5) for _ in range(n)]
        ours, theirs = kendall_tau_b(x, y), scipy_stats.kendalltau(x, y).statistic
        assert (ours != ours and theirs != theirs) or abs(ours - theirs) < 1e-12, (x, y)


def test_the_bootstrap_is_seeded_and_refuses_nonsense() -> None:
    values = [0.1, 0.9, 0.4, 0.7]
    assert bootstrap_interval(values, seed=1) == bootstrap_interval(values, seed=1)
    for kwargs, match in (({"level": 1.0}, "level"), ({"resamples": 0}, "resamples")):
        with pytest.raises(ValueError, match=match):
            bootstrap_interval(values, seed=1, **kwargs)
    with pytest.raises(ValueError, match="at least one"):
        bootstrap_interval([], seed=1)


# --- found by the adversarial review of #147 --------------------------------


def test_fixture_order_changes_neither_the_key_nor_the_numbers(fixtures) -> None:
    assert _report(fixtures) == _report(list(reversed(fixtures)))


def test_a_mutating_metric_cannot_corrupt_the_fixture_or_the_next_metric(fixtures) -> None:
    def vandal(fixture, produced):
        produced["alternatives"].clear()
        fixture.expected["alternatives"].clear()
        return 0.0

    report = _report(fixtures, suite=[Metric("vandal", 1, "ci", vandal), SUITE[0]])
    assert report["perAnalysis"]["ferries"]["alternatives"] == 3.0
    assert len(fixtures[0].expected["alternatives"]) == 3


def test_replicates_in_the_same_second_do_not_overwrite(fixtures) -> None:
    store: dict[str, bytes] = {}
    first = _report(fixtures)
    second = json.loads(json.dumps(first))
    second["perAnalysis"]["ferries"]["alternatives"] = 4.0  # a nonzero-temperature replicate
    keys = {save_report(first, store), save_report(second, store)}
    assert len(keys) == 2 == len(store)


@pytest.mark.parametrize("config", [{1: "x"}, {"arm": ("a", "b")}, {"arm": {"a"}},
                                    {"t": float("nan")}])
def test_a_config_that_would_serialise_ambiguously_is_refused(fixtures, config) -> None:
    with pytest.raises(TypeError, match="subject.config"):
        _report(fixtures, subject=replace(expected_subject(), config=config))


def test_one_analysis_gets_a_mean_and_no_interval(fixtures) -> None:
    summary = _report(fixtures[:1])["metrics"]["alternatives"]
    assert summary["n"] == 1 and summary["mean"] == 3.0 and summary["interval"] is None


def test_duplicate_fixture_ids_are_refused(fixtures) -> None:
    with pytest.raises(ValueError, match="unique"):
        _report([*fixtures, fixtures[0]])


@pytest.mark.parametrize("name", ["fixture.json", "expected.json"])
def test_a_fixture_file_that_is_not_an_object_is_refused(name) -> None:
    files = _fixture_bytes()
    files[f"kettles/{name}"] = b"[1]"
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_fixtures(files)


def test_kendall_tau_b_is_nan_on_nan_like_scipy() -> None:
    import math

    assert math.isnan(kendall_tau_b([1.0, float("nan"), 3.0], [1, 2, 3]))
