"""The evaluation harness: run a suite over a fixture set, and key the report by what could have moved it.

ADR-0008 makes the suite mandatory; this is the runner the checks plug into
(#86). Its one job beyond running is **attribution**: a metric that moved is only
useful if you know what moved it, so every report carries every version input
that could have changed a number -- the package, the frozen tool surface, each
prompt's version *and* content hash, the vendored schema's pins, the subject and
its model id, the seed, each fixture's content hash, each metric's version, and
the bootstrap settings -- and is stored under the hash of exactly that record.
Two reports with the same key were produced by the same inputs; two with
different keys say, field by field, which input differs.

## The three things a run is made of

- **Fixtures** (:func:`load_fixtures`): source documents plus an expected
  analysis, read from any ``Mapping[str, bytes]`` -- a directory today, the
  corpus shared with the companion repository later (#87).
- **A subject** (:class:`Subject`): what produces an analysis from a fixture. A
  model-driven arm declares its ``model_id``; :func:`expected_subject` replays
  each fixture's expected analysis and declares none, which is the no-model run
  the CI tier needs and the harness's own self-test.
- **A suite**: :class:`Metric` rows, each returning **one number per analysis**.

## Bootstrap by analysis, never by cell

A metric returns one value per analysis, and the interval resamples analyses.
That is a constraint of the interface rather than a convention: cells within an
analysis share a subject, a corpus and a traversal, so resampling cells treats
correlated measurements as independent and reports an interval far narrower than
the evidence supports (ADR-0008, as amended). A per-cell quantity is reduced to
its per-analysis value inside the metric, where the reduction is visible.

No model is called here and nothing reaches the network: a subject that needs a
model brings its own access (ADR-0019), and the harness only records its id.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Mapping, MutableMapping, Sequence

from rubricator.clock import Clock, system_clock
from rubricator.stats import bootstrap_interval

__all__ = [
    "HARNESS_VERSION", "Fixture", "Metric", "Subject", "expected_subject", "load_fixtures",
    "version_inputs", "run_key", "run_suite", "report_store", "save_report",
]

#: Bumped when the runner changes how a number is computed or reported.
HARNESS_VERSION = 1

#: ADR-0008's three tiers: every commit, nightly on fixtures, release on the full corpus.
Tier = Literal["ci", "nightly", "release"]

_FIXTURE = "fixture.json"
_EXPECTED = "expected.json"
_SOURCES = "sources/"


@dataclass(frozen=True)
class Fixture:
    """One fixture: what it is, the analysis it should produce, and its sources.

    ``digest`` is the sha256 over every key and byte the fixture was read from,
    so a report can tell a changed fixture from a changed agent.
    """

    id: str
    family: str
    expected: Mapping[str, Any]
    sources: Mapping[str, bytes]
    meta: Mapping[str, Any]
    digest: str


@dataclass(frozen=True)
class Metric:
    """One check: a name, a version, a tier, and a per-analysis measurement.

    ``measure(fixture, produced)`` returns one number for that analysis, or
    ``None`` when the check does not apply to this fixture (a citation check on a
    fixture with no citations). Bump ``version`` whenever the definition
    changes: it is part of the run key, and a silently redefined metric is a
    trend line that lies.
    """

    name: str
    version: int
    tier: Tier
    measure: Callable[[Fixture, Mapping[str, Any]], float | None]
    description: str = ""


@dataclass(frozen=True)
class Subject:
    """What produces an analysis from a fixture.

    ``model_id`` is ``None`` when no model is involved -- recorded as such, never
    guessed. ``config`` holds whatever else could change the output (the
    traversal arm, a temperature where the runtime has one) and enters the run key
    whole.
    """

    name: str
    run: Callable[[Fixture, int], Mapping[str, Any]]
    model_id: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)


def expected_subject() -> Subject:
    """Replay each fixture's expected analysis: no model, no seed dependence.

    The baseline every metric should score perfectly on, which makes it the
    harness's self-test as well as the CI tier's subject.
    """
    return Subject(name="expected", run=lambda fixture, seed: fixture.expected)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def load_fixtures(source: Mapping[str, bytes]) -> list[Fixture]:
    """Every fixture in ``source``, sorted by id.

    The layout, one directory per fixture::

        {fixture_id}/fixture.json      {"id", "family", "description", ...}
        {fixture_id}/expected.json     the expected comparanda analysis
        {fixture_id}/sources/{name}    the source documents, any bytes

    A fixture directory missing either JSON file, or whose ``fixture.json``
    names another id or no family, is refused with the key at fault -- a fixture
    that loads half-way is a metric computed over the wrong set.
    """
    grouped: dict[str, dict[str, bytes]] = {}
    for key in source:
        fixture_id, sep, rest = key.partition("/")
        if not sep or not rest:
            raise ValueError(
                f"refused: {key!r} is not inside a fixture directory. Every key is "
                f"{{fixture_id}}/{_FIXTURE}, {{fixture_id}}/{_EXPECTED} or "
                f"{{fixture_id}}/{_SOURCES}{{name}}."
            )
        grouped.setdefault(fixture_id, {})[rest] = source[key]
    return [_fixture(fixture_id, files) for fixture_id, files in sorted(grouped.items())]


def _fixture(fixture_id: str, files: Mapping[str, bytes]) -> Fixture:
    for required in (_FIXTURE, _EXPECTED):
        if required not in files:
            raise ValueError(f"refused: fixture {fixture_id!r} has no {required}.")
    unknown = sorted(k for k in files if k not in (_FIXTURE, _EXPECTED) and not k.startswith(_SOURCES))
    if unknown:
        raise ValueError(
            f"refused: fixture {fixture_id!r} holds {unknown}, which is neither {_FIXTURE}, "
            f"{_EXPECTED} nor under {_SOURCES}."
        )
    meta = json.loads(files[_FIXTURE])
    if meta.get("id") != fixture_id:
        raise ValueError(
            f"refused: {fixture_id}/{_FIXTURE} says id {meta.get('id')!r}; the directory says "
            f"{fixture_id!r}. One of them is a copy that was not renamed."
        )
    if not isinstance(meta.get("family"), str) or not meta["family"].strip():
        raise ValueError(f"refused: {fixture_id}/{_FIXTURE} names no family.")
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode() + b"\0" + hashlib.sha256(files[name]).digest())
    return Fixture(
        id=fixture_id,
        family=meta["family"],
        expected=json.loads(files[_EXPECTED]),
        sources={k[len(_SOURCES):]: v for k, v in files.items() if k.startswith(_SOURCES)},
        meta=meta,
        digest=digest.hexdigest(),
    )


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def version_inputs(
    *,
    subject: Subject,
    seed: int,
    fixtures: Sequence[Fixture],
    suite: Sequence[Metric],
    resamples: int,
    level: float,
    prompts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Every input that could change a number in the report, as one JSON record.

    ``prompts`` defaults to the shipped prompts; pass the set a subject was
    actually served when it was not the shipped one.
    """
    from rubricator.prompts import prompts as shipped_prompts
    from rubricator.schema.pins import PINS, SCHEMA_TAG
    from rubricator.surface.frozen import definitions_digest

    served = shipped_prompts() if prompts is None else prompts
    return {
        "harness": HARNESS_VERSION,
        "package": {"name": "rubricator", "version": _package_version()},
        "python": platform.python_version(),
        "toolSurface": {"definitionsSha256": definitions_digest()},
        "schema": {"tag": SCHEMA_TAG, "sha256": {k: p.sha256 for k, p in sorted(PINS.items())}},
        "prompts": {
            pid: {"version": p.version, "sha256": hashlib.sha256(p.body.encode()).hexdigest()}
            for pid, p in sorted(served.items())
        },
        "subject": {"name": subject.name, "config": dict(subject.config)},
        "model": subject.model_id,
        "seed": seed,
        "fixtures": {f.id: f.digest for f in fixtures},
        "suite": {m.name: {"version": m.version, "tier": m.tier} for m in suite},
        "bootstrap": {"unit": "analysis", "resamples": resamples, "level": level},
    }


def run_key(versions: Mapping[str, Any]) -> str:
    """The sha256 of the version record as canonical JSON: the report's identity."""
    canonical = json.dumps(versions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _package_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("rubricator")
    except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
        return "unknown"


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def run_suite(
    fixtures: Iterable[Fixture],
    suite: Sequence[Metric],
    *,
    subject: Subject | None = None,
    seed: int = 0,
    resamples: int = 2000,
    level: float = 0.95,
    now: Clock = system_clock,
    prompts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ``suite`` over ``fixtures`` and return the report.

    A subject or metric that raises on one fixture is recorded against that
    fixture and counted in the metric's ``errors``; the run goes on, because a
    crash on fixture 17 should not hide what fixtures 1-16 measured. A metric
    whose every value errored or did not apply reports ``n = 0`` and no mean --
    never a zero that looks like a score.
    """
    fixtures = list(fixtures)
    subject = subject or expected_subject()
    _check_suite(suite)
    versions = version_inputs(
        subject=subject, seed=seed, fixtures=fixtures, suite=suite,
        resamples=resamples, level=level, prompts=prompts,
    )
    per_analysis: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for fixture in fixtures:
        row: dict[str, Any] = {}
        try:
            produced = subject.run(fixture, seed)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append({"fixture": fixture.id, "stage": "subject", "error": _describe(exc)})
            per_analysis[fixture.id] = {m.name: {"error": "subject failed"} for m in suite}
            continue
        for metric in suite:
            try:
                row[metric.name] = _value(metric, metric.measure(fixture, produced))
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                errors.append({"fixture": fixture.id, "stage": metric.name, "error": _describe(exc)})
                row[metric.name] = {"error": _describe(exc)}
        per_analysis[fixture.id] = row
    return {
        "runKey": run_key(versions),
        "at": now(),
        "versions": versions,
        "metrics": {
            m.name: _summarise(m, per_analysis, seed=seed, resamples=resamples, level=level)
            for m in suite
        },
        "perAnalysis": per_analysis,
        "errors": errors,
    }


def _check_suite(suite: Sequence[Metric]) -> None:
    if not suite:
        raise ValueError("refused: an empty suite measures nothing. Pass at least one Metric.")
    names = [m.name for m in suite]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"refused: metric names must be unique; repeated: {duplicates}")


def _value(metric: Metric, value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TypeError(
            f"{metric.name} returned {value!r}; a metric returns one finite number per analysis, "
            "or None when it does not apply"
        )
    return float(value)


def _summarise(
    metric: Metric, per_analysis: Mapping[str, Mapping[str, Any]], *, seed: int, resamples: int,
    level: float,
) -> dict[str, Any]:
    cells = [row.get(metric.name) for row in per_analysis.values()]
    values = [v for v in cells if isinstance(v, float)]
    summary: dict[str, Any] = {
        "version": metric.version,
        "tier": metric.tier,
        "unit": "analysis",
        "n": len(values),
        "notApplicable": sum(v is None for v in cells),
        "errors": sum(isinstance(v, Mapping) for v in cells),
        "mean": None,
        "interval": None,
    }
    if values:
        summary["mean"] = sum(values) / len(values)
        summary["interval"] = list(
            bootstrap_interval(values, seed=seed, resamples=resamples, level=level)
        )
    return summary


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Storing reports
# ---------------------------------------------------------------------------


def report_store(root: str | None = None) -> MutableMapping[str, bytes]:
    """Where reports are kept: ``data_dir() / "evaluations"`` unless told otherwise.

    A report is derived data, so it never defaults into the repository; commit
    one deliberately, and only from public fixtures.
    """
    from rubricator.store import data_dir, file_store

    return file_store(root or data_dir() / "evaluations")


def save_report(
    report: Mapping[str, Any], store: MutableMapping[str, bytes] | None = None
) -> str:
    """Write ``report`` under its run key and time; the key written.

    ``{runKey}/{at}.json``: every report produced by the same inputs sits under
    one prefix, and none overwrites another -- a model run at nonzero temperature
    is a replicate worth keeping, not a duplicate to discard.
    """
    store = report_store() if store is None else store
    stamp = str(report["at"]).replace(":", "")
    key = f"{report['runKey']}/{stamp}.json"
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    store[key] = payload.encode("utf-8")
    return key
