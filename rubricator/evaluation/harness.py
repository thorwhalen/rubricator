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

What "the package" means is its **source**, not its version string: the version
in ``pyproject.toml`` does not move between commits, so the record carries the
SHA-256 of every file shipped in the package, and the versions of the
dependencies a check could lean on. A subject and a metric each carry a declared
``version`` *and* a fingerprint of their code where it can be read, because a
declared version is the one input a person forgets to bump.

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

import copy
import hashlib
import inspect
import json
import math
import platform
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Mapping, MutableMapping, Sequence

from rubricator.clock import Clock, system_clock
from rubricator.stats import bootstrap_interval

__all__ = [
    "HARNESS_VERSION", "MIN_ANALYSES_FOR_INTERVAL", "Fixture", "Metric", "Subject", "expected_subject", "load_fixtures",
    "version_inputs", "run_key", "run_suite", "report_store", "save_report",
]

#: Bumped when the runner changes how a number is computed or reported.
HARNESS_VERSION = 1

#: The fewest analyses an interval is reported over. Below it the report gives
#: the mean and no interval: one analysis resampled is a zero-width interval,
#: which reads as certainty and is the opposite (ADR-0006). A keyword on
#: :func:`run_suite`, recorded in the run key.
MIN_ANALYSES_FOR_INTERVAL = 2

#: The dependencies whose version could move a number -- the validator a schema
#: check runs through, the store a fixture is read from.
_RECORDED_DEPENDENCIES = ("jsonschema", "dol")

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
    trend line that lies. The source of ``measure`` is fingerprinted into the key
    as well, where Python can read it, for the time the bump is forgotten.

    Each call gets its own copy of the fixture and of the produced analysis, so a
    metric that mutates what it is given cannot change what the next one sees.
    """

    name: str
    version: int
    tier: Tier
    measure: Callable[[Fixture, Mapping[str, Any]], float | None]
    description: str = ""


@dataclass(frozen=True)
class Subject:
    """What produces an analysis from a fixture.

    ``version`` is declared, like a metric's, and the source of ``run`` is
    fingerprinted beside it. ``model_id`` is ``None`` when no model is involved --
    recorded as such, never guessed. ``config`` holds whatever else could change
    the output (the traversal arm, a temperature where the runtime has one) and
    enters the run key whole, so it must be plain JSON: string keys, lists rather
    than tuples, no sets -- anything else would either fail to serialise or
    serialise ambiguously. ``prompts`` is the prompt set the subject is served,
    when it is not the shipped one.
    """

    name: str
    run: Callable[[Fixture, int], Mapping[str, Any]]
    version: str
    model_id: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    prompts: Mapping[str, Any] | None = None


def expected_subject() -> Subject:
    """Replay each fixture's expected analysis: no model, no seed dependence.

    The baseline every metric should score perfectly on, which makes it the
    harness's self-test as well as the CI tier's subject.
    """
    return Subject(name="expected", run=_replay, version="1")


def _replay(fixture: Fixture, seed: int) -> Mapping[str, Any]:
    return fixture.expected


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
    expected = json.loads(files[_EXPECTED])
    for name, value in ((_FIXTURE, meta), (_EXPECTED, expected)):
        if not isinstance(value, dict):
            raise ValueError(
                f"refused: {fixture_id}/{name} holds a {type(value).__name__}; it must be a "
                "JSON object."
            )
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
        expected=expected,
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
    min_analyses: int,
) -> dict[str, Any]:
    """Every input that could change a number in the report, as one JSON record."""
    from rubricator.prompts import prompts as shipped_prompts
    from rubricator.schema.pins import PINS, SCHEMA_TAG
    from rubricator.surface.frozen import definitions_digest

    served = shipped_prompts() if subject.prompts is None else subject.prompts
    return {
        "harness": HARNESS_VERSION,
        "package": {
            "name": "rubricator",
            "version": _distribution_version("rubricator"),
            "sourceSha256": _package_digest(),
        },
        "dependencies": {name: _distribution_version(name) for name in _RECORDED_DEPENDENCIES},
        "python": platform.python_version(),
        "toolSurface": {"definitionsSha256": definitions_digest()},
        "schema": {"tag": SCHEMA_TAG, "sha256": {k: p.sha256 for k, p in sorted(PINS.items())}},
        "prompts": {
            pid: {"version": p.version, "sha256": hashlib.sha256(p.body.encode()).hexdigest()}
            for pid, p in sorted(served.items())
        },
        "subject": {
            "name": subject.name,
            "version": subject.version,
            "sourceSha256": _source_digest(subject.run),
            "config": _plain_json(subject.config, "subject.config"),
        },
        "model": subject.model_id,
        "seed": seed,
        "fixtures": {f.id: f.digest for f in fixtures},
        "suite": {
            m.name: {"version": m.version, "tier": m.tier, "sourceSha256": _source_digest(m.measure)}
            for m in suite
        },
        "bootstrap": {
            "unit": "analysis", "resamples": resamples, "level": level,
            "minAnalyses": min_analyses,
        },
    }


def run_key(versions: Mapping[str, Any]) -> str:
    """The sha256 of the version record as canonical JSON: the report's identity."""
    canonical = json.dumps(versions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _distribution_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
        return None


def _package_digest() -> str:
    """SHA-256 over every file shipped in the package, by relative path and bytes.

    The version string does not move between commits; this does, with any change
    to code, prompts or vendored schema. Caches excluded, because they are a
    by-product of running, not an input to it.
    """
    from importlib.resources import files
    from pathlib import Path

    root = Path(str(files("rubricator")))
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _source_digest(fn: Callable[..., Any]) -> str | None:
    """SHA-256 of a function's source, or ``None`` where Python cannot read it.

    A fingerprint, not a proof: it sees the function's own text and not what it
    closes over or calls. It catches the common case -- an edited metric whose
    version nobody bumped -- and the declared version carries the rest.
    """
    try:
        return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
    except (OSError, TypeError):
        return None


def _plain_json(value: Any, where: str) -> Any:
    """``value`` if it is plain JSON that serialises one way only; ``TypeError`` otherwise."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{where} is {value!r}; a run key needs finite numbers")
        return value
    if isinstance(value, list):
        return [_plain_json(v, f"{where}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, Mapping):
        bad = [k for k in value if not isinstance(k, str)]
        if bad:
            raise TypeError(f"{where} has non-string keys {bad!r}; JSON keys are strings")
        return {k: _plain_json(v, f"{where}.{k}") for k, v in value.items()}
    raise TypeError(
        f"{where} is a {type(value).__name__}; a run key holds plain JSON only (use a list for a "
        "tuple or a set, so it cannot collide with one)"
    )


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
    min_analyses: int = MIN_ANALYSES_FOR_INTERVAL,
    now: Clock = system_clock,
) -> dict[str, Any]:
    """Run ``suite`` over ``fixtures`` and return the report.

    A subject or metric that raises on one fixture is recorded against that
    fixture and counted in the metric's ``errors``; the run goes on, because a
    crash on fixture 17 should not hide what fixtures 1-16 measured. A metric
    whose every value errored or did not apply reports ``n = 0`` and no mean --
    never a zero that looks like a score.

    Fixtures run in id order whatever order they arrive in, because the bootstrap
    draws by position and the run key records the set, not the order.
    """
    fixtures = sorted(fixtures, key=lambda f: f.id)
    ids = [f.id for f in fixtures]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise ValueError(f"refused: fixture ids must be unique; repeated: {repeated}")
    subject = subject or expected_subject()
    _check_suite(suite)
    versions = version_inputs(
        subject=subject, seed=seed, fixtures=fixtures, suite=suite,
        resamples=resamples, level=level, min_analyses=min_analyses,
    )
    per_analysis: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for fixture in fixtures:
        row: dict[str, Any] = {}
        try:
            produced = subject.run(copy.deepcopy(fixture), seed)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append({"fixture": fixture.id, "stage": "subject", "error": _describe(exc)})
            per_analysis[fixture.id] = {m.name: {"error": "subject failed"} for m in suite}
            continue
        for metric in suite:
            try:
                value = metric.measure(copy.deepcopy(fixture), copy.deepcopy(produced))
                row[metric.name] = _value(metric, value)
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                errors.append({"fixture": fixture.id, "stage": metric.name, "error": _describe(exc)})
                row[metric.name] = {"error": _describe(exc)}
        per_analysis[fixture.id] = row
    return {
        "runKey": run_key(versions),
        "at": now(),
        "versions": versions,
        "metrics": {
            m.name: _summarise(
                m, per_analysis, seed=seed, resamples=resamples, level=level,
                min_analyses=min_analyses,
            )
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
    level: float, min_analyses: int,
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
    if len(values) >= min_analyses:
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

    ``{runKey}/{at}-{content hash}.json``: every report produced by the same
    inputs sits under one prefix, and none overwrites another -- a model run at
    nonzero temperature is a replicate worth keeping, not a duplicate to discard.
    The content hash is what separates two replicates finished in the same
    second; two reports that collide on it are the same bytes.
    """
    store = report_store() if store is None else store
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    stamp = str(report["at"]).replace(":", "")
    content = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    key = f"{report['runKey']}/{stamp}-{content}.json"
    store[key] = payload.encode("utf-8")
    return key
