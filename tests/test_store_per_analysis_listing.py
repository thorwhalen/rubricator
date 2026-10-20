"""A read or write of one analysis lists that analysis's keys, not the whole store (#146).

The working store holds a month of every analysis, so a cost that grows with the
store rather than with the analysis being touched grows with use. The filesystem
store offers ``keys_under(prefix)``, which lists one directory; these tests count
what the store is asked for and assert that nothing outside the analysis is.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Iterator

import pytest

from rubricator.contributors import human
from rubricator.store import AnalysisStore, file_store
from rubricator.tools.analysis import analysis_open

ANA = human("ana", "Ana Ruiz")
AT = "2026-08-22T12:00:00Z"


class CountingStore(MutableMapping):
    """Forwards to a filesystem store and records every key it hands out."""

    def __init__(self, inner: MutableMapping[str, bytes]) -> None:
        self.inner = inner
        self.whole_walks = 0
        self.listed: list[str] = []

    def keys_under(self, prefix: str) -> Iterator[str]:
        for key in self.inner.keys_under(prefix):
            self.listed.append(key)
            yield key

    def __iter__(self) -> Iterator[str]:
        self.whole_walks += 1
        for key in self.inner:
            self.listed.append(key)
            yield key

    def __getitem__(self, key: str) -> bytes:
        return self.inner[key]

    def __setitem__(self, key: str, value: bytes) -> None:
        self.inner[key] = value

    def __delitem__(self, key: str) -> None:
        del self.inner[key]

    def __len__(self) -> int:
        return len(self.inner)


@pytest.fixture()
def counted(tmp_path) -> tuple[AnalysisStore, CountingStore]:
    blobs = CountingStore(file_store(tmp_path / "working"))
    store = AnalysisStore(blobs, now=lambda: AT)
    for analysis_id in ("other1", "other2", "a1"):
        analysis_open(store, analysis_id=analysis_id, question="Which runtime?")
        store.put_contribution(analysis_id, "bob", {"assertions": []})
    blobs.whole_walks, blobs.listed = 0, []
    return store, blobs


def _only_a1(blobs: CountingStore) -> None:
    assert blobs.whole_walks == 0
    assert blobs.listed, "nothing was listed at all: the test is not measuring the read"
    assert all(k.startswith("analyses/a1/") for k in blobs.listed), sorted(
        {k.split("/")[1] for k in blobs.listed}
    )


def test_a_read_lists_only_that_analysis(counted) -> None:
    store, blobs = counted
    store.read("a1")
    _only_a1(blobs)


def test_a_write_lists_only_that_analysis(counted) -> None:
    store, blobs = counted
    store.put_contribution("a1", "ana", {"assertions": []})
    _only_a1(blobs)


def test_a_store_without_the_listing_is_walked_and_still_right(tmp_path) -> None:
    store = AnalysisStore({}, now=lambda: AT)
    analysis_open(store, analysis_id="a1", question="Which runtime?")
    analysis_open(store, analysis_id="a2", question="Which runtime?")
    store.put_contribution("a1", "bob", {"assertions": []})
    assert store.contributors("a1") == ["bob"] and store.contributors("a2") == []


def test_the_listing_agrees_with_the_walk(tmp_path) -> None:
    blobs = file_store(tmp_path / "working")
    store = AnalysisStore(blobs, now=lambda: AT)
    for analysis_id in ("a1", "a10", "b"):
        analysis_open(store, analysis_id=analysis_id, question="Which runtime?")
    for prefix in ("analyses/", "analyses/a1/", "analyses/a1/touched/", "analyses/none/"):
        assert sorted(blobs.keys_under(prefix)) == sorted(k for k in blobs if k.startswith(prefix))


@pytest.mark.parametrize("prefix", ["analyses/../", "/etc/", "analyses//", "analyses/./"])
def test_a_prefix_that_names_no_key_lists_nothing_outside_the_root(tmp_path, prefix) -> None:
    (tmp_path / "outside.json").write_bytes(b"{}")
    blobs = file_store(tmp_path / "working")
    assert list(blobs.keys_under(prefix)) == []
