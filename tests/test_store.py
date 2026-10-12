"""The store of ADR-0017: the record is the document, it lives outside the package, and it expires.

Four claims, each the acceptance line of #51 and each checked here rather than
asserted in a docstring:

1. **Every stage reads back as a valid analysis** -- including the moment after
   ``analysis_open``, with zero alternatives and zero criteria, which is the
   structural requirement ADR-0017 placed on comparanda. Valid means both halves
   of what ``analysis_validate`` (#61) will compose: the published schema, and
   the honesty rules of :mod:`rubricator.rules`.
2. **Data never lands inside the package directory.**
3. **Expiry is a typed, recoverable error naming the window** -- never an empty
   result -- and an expired id is indistinguishable from one that never existed.
4. **Swapping the mapping changes no tool module**: the same chain runs on a
   hand-written ``MutableMapping`` that is not a dict and not a ``dol`` store.
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

import rubricator
from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.rules import honesty_problems
from rubricator.store import (
    DATA_DIR_ENV,
    RETENTION_DAYS,
    AnalysisNotFound,
    AnalysisStore,
    file_store,
    working_dir,
)
from rubricator.surface import bind, describe, frozen
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    frame_set,
    measures_mark_missing,
    measures_write,
    report_completeness,
)

PACKAGE_DIR = Path(rubricator.__file__).resolve().parent
TOOLS_DIR = PACKAGE_DIR / "tools"
T0 = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


class MovableClock:
    """A clock a test can move forward, so a 30-day window takes no time to test."""

    def __init__(self, moment: datetime = T0) -> None:
        self.moment = moment

    def __call__(self) -> str:
        return self.moment.isoformat().replace("+00:00", "Z")

    def advance(self, **delta: float) -> None:
        self.moment += timedelta(**delta)


class DictBackedStore(MutableMapping):
    """A ``MutableMapping[str, bytes]`` that is neither a dict nor a ``dol`` store.

    The swap the store seam promises, demonstrated: if a tool reached past
    ``AnalysisStore`` to anything dict- or filesystem-specific, it would break here.
    """

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def __getitem__(self, key: str) -> bytes:
        return self._data[key]

    def __setitem__(self, key: str, value: bytes) -> None:
        if not isinstance(value, bytes):
            raise TypeError(f"a bytes store holds bytes, not {type(value).__name__}")
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._data))

    def __len__(self) -> int:
        return len(self._data)


@pytest.fixture()
def clock() -> MovableClock:
    return MovableClock()


@pytest.fixture()
def data_root(tmp_path, monkeypatch) -> Path:
    """The data root moved to a temporary directory, by the one variable that moves it."""
    root = tmp_path / "data"
    monkeypatch.setenv(DATA_DIR_ENV, str(root))
    return root


# --- 1. every stage reads back as a valid analysis ---------------------------

ANA = human("ana", "Ana Ruiz")
AT = "2026-08-22T12:00:00Z"


def _stages() -> list[tuple[str, Callable[[AnalysisStore], Any]]]:
    """The deterministic chain, one step per ADR-0005 stage the tools reach."""
    return [
        ("open", lambda s: analysis_open(s, analysis_id="a1", question="Which runtime?")),
        ("frame", lambda s: frame_set(s, analysis_id="a1", ambiguities=["for the new service?"])),
        ("alternatives", lambda s: alternatives_set(
            s, analysis_id="a1",
            alternatives=[{"id": "alpha", "label": "Alpha"}, {"id": "beta", "label": "Beta"}],
        )),
        ("criteria", lambda s: criteria_set(s, analysis_id="a1", criteria=[{
            "id": "support", "label": "Vendor support",
            "anchors": {"1": "no commitment", "3": "undated commitment", "5": "dated commitment"},
        }])),
        ("score", lambda s: measures_write(
            s, analysis_id="a1", contributor_id="ana", author=ANA, at=AT,
            cells=[{
                "alternativeId": "alpha", "criterionId": "support", "value": 5,
                "justification": "a dated support window is published",
                "independence": "independent",
                "evidence": [{
                    "id": "e1", "target": "rendition:alpha", "sourceType": "primary",
                    "stance": "supports", "derivedFrom": [],
                    "selectors": [{"type": "TextQuoteSelector", "exact": "until 30 June 2029"}],
                }],
            }],
        )),
        ("blank", lambda s: measures_mark_missing(
            s, analysis_id="a1", contributor_id="ana", author=ANA, at=AT,
            code="deferred", note="scored next session",
            criterion_ids=["support"], alternative_ids=["beta"],
        )),
    ]


@pytest.mark.parametrize("backend", ["files", "mapping"])
def test_every_stage_reads_back_as_a_valid_analysis(backend, tmp_path, clock) -> None:
    blobs = file_store(tmp_path / "store") if backend == "files" else DictBackedStore()
    runtime = build_runtime(blobs=blobs, now=clock)
    assert runtime.schema.origin == "published", "a sketch would prove nothing about the contract"
    for stage, step in _stages():
        step(runtime.store)
        document = runtime.store.read("a1")
        result = runtime.schema.validate(document)
        assert result.ok, f"after {stage}: {result.report()}"
        assert honesty_problems(document) == [], f"after {stage}"
        if stage == "open":
            assert document["alternatives"] == [] and document["criteria"] == []


# --- 2. never inside the package directory -----------------------------------


def test_the_default_store_is_the_user_data_working_store(data_root) -> None:
    runtime = build_runtime()
    analysis_open(runtime.store, analysis_id="a1", question="Which runtime?")
    assert working_dir() == data_root / "working"
    assert (data_root / "working" / "analyses" / "a1" / "frame.json").is_file()


def test_the_default_location_is_outside_the_package(monkeypatch) -> None:
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    where = working_dir().expanduser().resolve()
    assert PACKAGE_DIR not in where.parents and where != PACKAGE_DIR


@pytest.mark.parametrize("inside", [".", "data", "store/analyses"])
def test_a_root_inside_the_package_is_refused(inside) -> None:
    root = PACKAGE_DIR / inside
    with pytest.raises(ValueError, match="inside the rubricator package directory"):
        file_store(root)
    with pytest.raises(ValueError, match=DATA_DIR_ENV):
        build_runtime(root=str(root))
    assert not (PACKAGE_DIR / "store" / "analyses").exists()


def test_a_data_dir_pointed_into_the_package_is_refused(monkeypatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(PACKAGE_DIR))
    with pytest.raises(ValueError, match="inside the rubricator package directory"):
        build_runtime()


def test_a_whole_run_on_the_default_store_writes_nothing_in_the_package(data_root, clock) -> None:
    before = sorted(p for p in PACKAGE_DIR.rglob("*") if "__pycache__" not in p.parts)
    runtime = build_runtime(now=clock)
    for _, step in _stages():
        step(runtime.store)
    after = sorted(p for p in PACKAGE_DIR.rglob("*") if "__pycache__" not in p.parts)
    assert after == before
    assert any((data_root / "working").rglob("*.json"))


# --- 3. expiry ---------------------------------------------------------------


def _opened(clock: MovableClock, *, blobs=None, **kwargs) -> AnalysisStore:
    store = AnalysisStore({} if blobs is None else blobs, now=clock, **kwargs)
    analysis_open(store, analysis_id="a1", question="Which runtime?")
    return store


def test_an_analysis_is_kept_until_the_window_from_last_write(clock) -> None:
    store = _opened(clock)
    clock.advance(days=RETENTION_DAYS, seconds=-1)
    assert store.exists("a1") and store.frame("a1")["id"] == "a1"


def test_expiry_is_a_typed_recoverable_error_naming_the_window(clock) -> None:
    store = _opened(clock)
    clock.advance(days=RETENTION_DAYS)
    with pytest.raises(AnalysisNotFound) as caught:
        report_completeness(store, analysis_id="a1")
    assert isinstance(caught.value, KeyError), "a KeyError is a tool error, not a protocol error"
    message = str(caught.value)
    assert f"{RETENTION_DAYS} days from their last write" in message
    assert "analysis_open" in message


def test_expiry_deletes_the_record(clock) -> None:
    blobs: dict[str, bytes] = {}
    store = _opened(clock, blobs=blobs)
    alternatives_set(store, analysis_id="a1", alternatives=[{"id": "alpha", "label": "Alpha"}])
    clock.advance(days=RETENTION_DAYS)
    assert not store.exists("a1")
    assert blobs == {}


def test_expired_and_never_existed_are_the_same_error(clock) -> None:
    store = _opened(clock)
    clock.advance(days=RETENTION_DAYS + 1)
    with pytest.raises(AnalysisNotFound) as expired:
        store.frame("a1")
    with pytest.raises(AnalysisNotFound) as never:
        store.frame("a2")
    assert str(expired.value).replace('"a1"', '"x"') == str(never.value).replace('"a2"', '"x"')


def test_the_window_runs_from_the_last_write_to_any_part(clock) -> None:
    store = _opened(clock)
    clock.advance(days=20)
    criteria_set(store, analysis_id="a1", criteria=[{
        "id": "support", "label": "Vendor support",
        "anchors": {"1": "none", "3": "undated", "5": "dated"},
    }])
    clock.advance(days=20)  # 40 days after creation, 20 after the last write
    assert store.exists("a1")
    assert store.last_write("a1") == "2026-09-11T12:00:00Z"


def test_a_contribution_dates_the_analysis_without_sharing_a_key(clock) -> None:
    blobs: dict[str, bytes] = {}
    store = _opened(clock, blobs=blobs)
    alternatives_set(
        store, analysis_id="a1",
        alternatives=[{"id": "alpha", "label": "Alpha"}, {"id": "beta", "label": "Beta"}],
    )
    criteria_set(store, analysis_id="a1", criteria=[{
        "id": "support", "label": "Vendor support",
        "anchors": {"1": "none", "3": "undated", "5": "dated"},
    }])
    keys_before = set(blobs)
    clock.advance(days=25)
    for who, row in (("ana", "alpha"), ("ben", "beta")):
        measures_mark_missing(
            store, analysis_id="a1", contributor_id=who, author=human(who, who.title()), at=AT,
            code="deferred", note="later", criterion_ids=["support"], alternative_ids=[row],
        )
    written = set(blobs) - keys_before
    stamps = {k for k in written if "/touched/" in k}
    assert stamps == {
        "analyses/a1/touched/contributions/ana.json/20260916T120000Z",
        "analyses/a1/touched/contributions/ben.json/20260916T120000Z",
    }, "two contributors must never write the same key -- stamps included"
    clock.advance(days=25)
    assert store.exists("a1")


def test_reopening_an_expired_id_starts_afresh(clock) -> None:
    store = _opened(clock)
    alternatives_set(store, analysis_id="a1", alternatives=[{"id": "alpha", "label": "Alpha"}])
    clock.advance(days=RETENTION_DAYS)
    result = analysis_open(store, analysis_id="a1", question="A different question")
    assert result["created"] is True
    assert store.read("a1")["alternatives"] == []


def test_a_contribution_cannot_revive_an_expired_analysis(clock) -> None:
    blobs: dict[str, bytes] = {}
    store = _opened(clock, blobs=blobs)
    clock.advance(days=RETENTION_DAYS)
    with pytest.raises(AnalysisNotFound):
        store.put_contribution("a1", "ana", {"authors": [], "cells": []})
    assert blobs == {}


def test_listing_omits_expired_and_sweep_deletes_them(clock) -> None:
    blobs: dict[str, bytes] = {}
    store = AnalysisStore(blobs, now=clock)
    analysis_open(store, analysis_id="old", question="q")
    clock.advance(days=RETENTION_DAYS - 1)
    analysis_open(store, analysis_id="new", question="q")
    clock.advance(days=1)
    assert store.analyses() == ["new"]
    assert any(k.startswith("analyses/old/") for k in blobs), "listing does not delete"
    assert store.sweep() == ["old"]
    assert not any(k.startswith("analyses/old/") for k in blobs)
    assert store.analyses() == ["new"]


def test_an_undated_analysis_is_kept(clock) -> None:
    """Written before stamps existed: no date, so the window cannot have run out."""
    blobs: dict[str, bytes] = {}
    store = _opened(clock, blobs=blobs)
    for key in [k for k in blobs if "/touched/" in k]:
        del blobs[key]
    clock.advance(days=10 * RETENTION_DAYS)
    assert store.last_write("a1") is None and store.exists("a1")


def test_the_window_is_configurable_and_the_surface_states_it(clock) -> None:
    store = _opened(clock, retention_days=7)
    clock.advance(days=7)
    with pytest.raises(AnalysisNotFound, match="kept for 7 days"):
        store.frame("a1")
    row = frozen()["analysis_open"]
    assert "for 7 days from its last write" in describe(row, retention_days=7)
    assert describe(row) == describe(row, retention_days=RETENTION_DAYS)


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "30"])
def test_a_nonsense_window_is_refused(bad) -> None:
    with pytest.raises(ValueError, match="retention_days"):
        AnalysisStore({}, retention_days=bad)


def test_the_surface_reports_expiry_as_the_typed_error(clock) -> None:
    runtime = build_runtime(blobs={}, retention_clock=clock)
    verbs = bind(runtime)
    opened = verbs["analysis_open"](question="Which runtime?")
    clock.advance(days=RETENTION_DAYS)
    with pytest.raises(AnalysisNotFound, match=f"{RETENTION_DAYS} days"):
        verbs["report_completeness"](analysis_id=opened["analysisId"])


# --- 4. the mapping swaps without touching a tool ----------------------------


def test_no_tool_module_reaches_below_the_store_facade() -> None:
    """Tools see ``AnalysisStore`` and nothing under it: no bytes store, no ``dol``, no paths."""
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "rubricator.store":
                names = {a.name for a in node.names}
                assert names <= {"AnalysisStore", "AnalysisNotFound"}, f"{path.name}: {names}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [
                    node.module or ""
                ]
                assert not any(m.split(".")[0] == "dol" for m in modules), path.name
            if isinstance(node, ast.Attribute):
                assert node.attr != "blobs", f"{path.name} reaches into the bytes store"


# --- found by the adversarial review of #145 ---------------------------------


def test_a_fixture_written_with_a_fixed_clock_is_not_deleted_on_read(tmp_path, capsys) -> None:
    """The assertion clock is not the retention clock."""
    from rubricator.cli import main
    from rubricator.clock import fixed_clock

    root = str(tmp_path / "store")
    runtime = build_runtime(root=root, now=fixed_clock("2020-01-01T00:00:00Z"))
    analysis_open(runtime.store, analysis_id="fixture", question="Which?")
    assert main(["show", "fixture", "--root", root]) == 0
    assert '"question": "Which?"' in capsys.readouterr().out


def test_two_branches_editing_the_frame_leave_two_stamps_not_a_conflict(clock) -> None:
    """What a clean git merge of two frame edits leaves behind: both stamps, old one gone."""
    base: dict[str, bytes] = {}
    store = _opened(clock, blobs=base)
    ana, ben = dict(base), dict(base)
    clock.advance(days=1)
    alternatives_set(AnalysisStore(ana, now=clock), analysis_id="a1",
                     alternatives=[{"id": "alpha", "label": "Alpha"}])
    clock.advance(days=1)
    criteria_set(AnalysisStore(ben, now=clock), analysis_id="a1", criteria=[{
        "id": "support", "label": "Vendor support",
        "anchors": {"1": "none", "3": "undated", "5": "dated"},
    }])
    old = {k for k in base if "/touched/" in k}
    assert not old & set(ana) and not old & set(ben), "each branch deleted the old stamp"
    added_ana = {k for k in ana if "/touched/" in k}
    added_ben = {k for k in ben if "/touched/" in k}
    assert added_ana.isdisjoint(added_ben), "different moments are different files"
    merged = {**ana, **ben, "analyses/a1/frame.json": ben["analyses/a1/frame.json"]}
    assert AnalysisStore(merged, now=clock).last_write("a1") == "2026-08-24T12:00:00Z"


@pytest.mark.parametrize("stray", ["frame.json/20260822T120000Z.orig", "frame.json.orig", "x"])
def test_a_stray_file_under_touched_is_ignored(clock, stray) -> None:
    blobs: dict[str, bytes] = {}
    store = _opened(clock, blobs=blobs)
    blobs[f"analyses/a1/touched/{stray}"] = b"<<<<<<< HEAD\n"
    assert store.analyses() == ["a1"] and store.sweep() == []
    assert report_completeness(store, analysis_id="a1")["analysisId"] == "a1"


def test_the_typed_error_survives_pickling() -> None:
    import pickle

    error = pickle.loads(pickle.dumps(AnalysisNotFound("a1", retention_days=7)))
    assert isinstance(error, AnalysisNotFound) and "kept for 7 days" in str(error)


def test_a_window_too_long_to_express_is_refused() -> None:
    with pytest.raises(ValueError, match="export"):
        AnalysisStore({}, retention_days=10**9)


def test_contributors_of_an_expired_analysis_is_the_typed_error(clock) -> None:
    store = _opened(clock)
    clock.advance(days=RETENTION_DAYS)
    with pytest.raises(AnalysisNotFound):
        store.contributors("a1")


def test_a_reopen_reads_once_so_it_cannot_race_the_window(monkeypatch, clock) -> None:
    """analysis_open asks for the frame once: no exists()-then-frame() window to fall into."""
    store = _opened(clock)
    monkeypatch.setattr(AnalysisStore, "exists", lambda self, a: pytest.fail("exists() called"))
    clock.advance(days=RETENTION_DAYS)
    assert analysis_open(store, analysis_id="a1", question="again")["created"] is True


def test_the_cli_reports_a_missing_analysis_as_a_message(data_root, capsys) -> None:
    from rubricator.cli import main

    assert main(["show", "nope"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("rubricator: no analysis \"nope\"") and "Traceback" not in err


def test_a_symlink_into_the_package_is_refused(tmp_path) -> None:
    link = tmp_path / "innocent"
    link.symlink_to(PACKAGE_DIR, target_is_directory=True)
    with pytest.raises(ValueError, match="inside the rubricator package directory"):
        file_store(link / "data")
