"""Where an analysis lives: one mapping of bytes, and one file per contributor.

**Exactly one interface is invented for the whole persistence layer, and it is
not invented at all**: ``MutableMapping[str, bytes]``. It is standard, ``dol``
already supplies implementations of it over the filesystem, over zip archives and
over object stores, and every ``dol`` decorator -- caching, key transformation,
filtering -- applies to all of them without knowing which one it wrapped.

A five-port store abstraction was the alternative and buys nothing here: every
port would be a method on something that is already a Mapping.

## The key layout, and the one invariant that makes GitHub cheap

::

    analyses/{analysis_id}/frame.json
    analyses/{analysis_id}/contributions/{contributor_id}.json
    analyses/{analysis_id}/renditions/{rendition_id}.json

**One file per contributor.** That is not a filing convention; it is what makes
a shared git repository a viable backend without a locking protocol. Two people
scoring the same matrix never write the same key, so a pull-rebase-push cannot
conflict on content -- and the merge that produces one document happens on read,
in :mod:`rubricator.merge`, deterministically, in this package rather than in a
backend. Two backends that merged differently would be two products.

The frame -- subject, alternatives, criteria, declared vocabularies -- is shared
and is written by whoever is framing. It is the one file two people can collide
on, which is correct: changing the criteria mid-analysis is a thing that *should*
be coordinated rather than merged silently (ADR-0016).

## What is deliberately not here

No cache. ``read()`` merges every contribution on every call, which is free at
fixture scale and O(contributors x cells) at fifty by five hundred. The fix when
it hurts is one ``dol.cache_this`` at the composition root, keyed on the content
hash of the contribution set -- no interface changes. Naming the deferral is the
point: an uncached merge nobody wrote down becomes a mysterious slowness later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator, MutableMapping

__all__ = ["AnalysisStore", "BytesStore", "memory_store", "file_store"]

#: The whole persistence interface. See the module docstring.
BytesStore = MutableMapping[str, bytes]

_ENCODING = "utf-8"


def memory_store() -> BytesStore:
    """An in-process store.

    A real implementation, not a stub: it is the right answer for tests, for a
    single-session connector run, and for anything that never needs to outlive
    the process. Nothing downstream can tell it apart from a filesystem.
    """
    return {}


def file_store(root: str) -> BytesStore:
    """A filesystem store rooted at ``root``.

    ``dol.Files`` is exactly a ``MutableMapping[str, bytes]`` over a directory
    tree, so swapping in a GitHub-backed or object-store implementation later is
    a different argument at the composition root and no call-site change.

    Wrapped in ``mk_dirs_if_missing`` because the key layout is nested -- one
    directory per analysis, another for its contributions -- and a store that
    demanded its directories be created first would push a filesystem detail up
    into every caller, including the ones that will not be filesystems.
    """
    import os

    from dol import Files
    from dol.filesys import mk_dirs_if_missing

    # The wrapper only creates paths *below* the root, so the root itself is
    # ours to ensure. Stated rather than assumed: this is exactly the kind of
    # split responsibility that produces a confusing FileNotFoundError.
    os.makedirs(root, exist_ok=True)
    return mk_dirs_if_missing(Files(root))


@dataclass(frozen=True)
class AnalysisStore:
    """The document-shaped view over a bytes store.

    Everything above this reads and writes analyses; everything below it reads
    and writes bytes. That is the whole seam, and it is why ``blobs`` is a plain
    constructor argument rather than an interface with five methods.
    """

    blobs: BytesStore

    # -- keys ---------------------------------------------------------------
    #
    # Built here and nowhere else. A key format computed in two places is a
    # format that diverges in one of them.

    @staticmethod
    def frame_key(analysis_id: str) -> str:
        return f"analyses/{analysis_id}/frame.json"

    @staticmethod
    def contribution_key(analysis_id: str, contributor_id: str) -> str:
        return f"analyses/{analysis_id}/contributions/{contributor_id}.json"

    @staticmethod
    def rendition_key(analysis_id: str, rendition_id: str) -> str:
        return f"analyses/{analysis_id}/renditions/{rendition_id}.json"

    # -- reading ------------------------------------------------------------

    def analyses(self) -> list[str]:
        """Every analysis id in the store, sorted.

        Enumerable from v1 deliberately: migrating between backends is
        ``for k, v in old.items(): new[k] = v``, and that is only free if the
        store can be walked.
        """
        ids = {
            k.split("/")[1]
            for k in self.blobs
            if k.startswith("analyses/") and k.count("/") >= 2
        }
        return sorted(ids)

    def frame(self, analysis_id: str) -> dict[str, Any]:
        return self._read(self.frame_key(analysis_id))

    def contributors(self, analysis_id: str) -> list[str]:
        """Contributor ids with a file, sorted -- so a merge is reproducible."""
        prefix = f"analyses/{analysis_id}/contributions/"
        return sorted(
            k[len(prefix):].removesuffix(".json") for k in self.blobs if k.startswith(prefix)
        )

    def contributions(self, analysis_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        """Every contribution, in contributor-id order.

        Ordered, not because order should matter to the merge -- it must not --
        but because a merge whose *output* depends on dict iteration order would
        not be byte-identical across runs, and reproducibility is what makes a
        stored analysis diffable.
        """
        for contributor_id in self.contributors(analysis_id):
            yield contributor_id, self._read(self.contribution_key(analysis_id, contributor_id))

    def renditions(self, analysis_id: str) -> list[dict[str, Any]]:
        prefix = f"analyses/{analysis_id}/renditions/"
        return [self._read(k) for k in sorted(k for k in self.blobs if k.startswith(prefix))]

    # -- writing ------------------------------------------------------------

    def put_frame(self, analysis_id: str, frame: dict[str, Any]) -> None:
        self._write(self.frame_key(analysis_id), frame)

    def put_contribution(
        self, analysis_id: str, contributor_id: str, contribution: dict[str, Any]
    ) -> None:
        self._write(self.contribution_key(analysis_id, contributor_id), contribution)

    def put_rendition(self, analysis_id: str, rendition: dict[str, Any]) -> None:
        self._write(self.rendition_key(analysis_id, rendition["id"]), rendition)

    def exists(self, analysis_id: str) -> bool:
        return self.frame_key(analysis_id) in self.blobs

    # -- bytes --------------------------------------------------------------

    def _read(self, key: str) -> dict[str, Any]:
        try:
            raw = self.blobs[key]
        except KeyError:
            raise KeyError(
                f"nothing stored at {key!r}. Either the analysis does not exist, or this store "
                "is rooted somewhere else than the one that wrote it."
            ) from None
        return json.loads(raw.decode(_ENCODING))

    def _write(self, key: str, document: dict[str, Any]) -> None:
        # Sorted keys and a trailing newline, because these files are diffed by
        # people and merged by git: a re-serialisation that reorders keys shows
        # up as a whole-file change and buries the one line that moved.
        payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self.blobs[key] = payload.encode(_ENCODING)
