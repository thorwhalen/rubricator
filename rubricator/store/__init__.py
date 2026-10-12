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
    analyses/{analysis_id}/confirmations/{sequence}-{digest}.json

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

The step-4 confirmation records (ADR-0005) sit beside the document rather than
in it, because comparanda v1 has no slot for them (#152), and they are **one
file per record**, never appended to a shared file: two people answering the
gate on two branches leave two files, and a revise can never be lost to a
conflict resolution. A record's name is its sequence on the branch that wrote
it plus a digest of its content, so order is write order -- never a
caller-supplied moment, which a model could set in the future to outrank a
later human ``revise`` -- and two branches that wrote the same sequence keep
both, in a fixed order.

## Where it lives

In the platform user-data directory, never inside the package (ADR-0017):
``~/.local/share/rubricator/working/`` by default, the whole data root moved by
one environment variable, ``RUBRICATOR_DATA_DIR``. ``working`` is the *kind*:
this is rubricator's working store, the one the retention window governs, and
the root stays open for other kinds. :func:`file_store` refuses a root inside the
installed package, because a code directory is a build output and a deploy that
syncs it eventually deletes everything the user was working on.

## Retention

An analysis is kept for :data:`RETENTION_DAYS` from its **last write** -- to its
frame, any contribution or any rendition -- and then deleted the next time
anything looks at it, or by :meth:`AnalysisStore.sweep`. Asking for an expired
analysis raises :class:`AnalysisNotFound`, the same error an id that never
existed raises: the id is opaque and unguessable, so there is nothing to learn
from the difference and nothing to leak by refusing to tell.

The last write is recorded, not inferred from the backend. Writing a key adds a
stamp whose *name* is the moment --
``analyses/{analysis_id}/touched/<the rest of that key>/20260822T120000Z`` -- and
removes that key's older stamps. Named rather than filled, so that two people
editing the frame on two branches each delete the old stamp and add a *different*
file, which git merges cleanly; a stamp with the moment as content would conflict
on every such merge, including ones where the frame itself merged without one.
The latest parseable stamp wins, and a file under ``touched/`` that does not
parse -- a merge's ``.orig``, a stray -- is ignored rather than allowed to make
the analysis unreadable. A file modification time would have been free and wrong:
a fresh clone dates everything to the clone. An analysis written before stamps
existed has no date, and is kept: the window errs toward losing nothing.

The retention clock is the wall clock, and is not the clock the verbs record in
the document. A fixture written with :func:`rubricator.clock.fixed_clock` so its
assertions are reproducible is still dated by when it was written, and is not
deleted the first time it is read.

## What is deliberately not here

No cache. ``read()`` merges every contribution on every call, which is free at
fixture scale and O(contributors x cells) at fifty by five hundred. The fix when
it hurts is one ``dol.cache_this`` at the composition root, keyed on the content
hash of the contribution set -- no interface changes. Naming the deferral is the
point: an uncached merge nobody wrote down becomes a mysterious slowness later.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, MutableMapping

from rubricator.clock import Clock, system_clock

__all__ = [
    "AnalysisStore", "AnalysisNotFound", "BytesStore", "memory_store", "file_store",
    "working_store", "data_dir", "working_dir", "check_id", "RETENTION_DAYS", "DATA_DIR_ENV",
]

#: The whole persistence interface. See the module docstring.
BytesStore = MutableMapping[str, bytes]

#: The retention window, in days from **last write**, that ADR-0017 makes a
#: stated contract: it is quoted verbatim in ``analysis_open``'s description,
#: where the model reads it, and a test keeps the two in step. Export defeats it
#: -- the window governs only this working store, never a file the user owns.
#:
#: The default of :attr:`AnalysisStore.retention_days`, which is what enforces it
#: (see "Retention" above). A store configured with another window states its own
#: value: the connector renders ``analysis_open``'s description from the store it
#: serves, so the model is never told a window the store does not keep.
RETENTION_DAYS = 30

#: The one environment variable that moves the whole data root. One knob, not one
#: per kind of data.
DATA_DIR_ENV = "RUBRICATOR_DATA_DIR"

#: The kind of data the working store holds, as the folder under the data root.
_WORKING_KIND = "working"

_ENCODING = "utf-8"

#: What an id that becomes part of a key may look like. Keys are paths on the
#: filesystem target (ADR-0023), so an id is confined to what cannot leave its
#: directory: no separators, no dots, no empty string.
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def check_id(value: str) -> str:
    """``value`` if it may be part of a store key; ``ValueError`` otherwise.

    >>> check_id("demo-1")
    'demo-1'
    >>> check_id("../escape")
    Traceback (most recent call last):
        ...
    ValueError: refused: "../escape" is not a usable id. An id is 1 to 64 letters, digits, "-" or "_", because it becomes part of a path.
    """
    if not isinstance(value, str) or not _ID.match(value):
        raise ValueError(
            f'refused: "{value}" is not a usable id. An id is 1 to 64 letters, digits, "-" or '
            '"_", because it becomes part of a path.'
        )
    return value


def memory_store() -> BytesStore:
    """An in-process store.

    A real implementation, not a stub: it is the right answer for tests, for a
    single-session connector run, and for anything that never needs to outlive
    the process. Nothing downstream can tell it apart from a filesystem.
    """
    return {}


def data_dir() -> Path:
    """rubricator's data root: ``$RUBRICATOR_DATA_DIR``, else the platform user-data directory.

    ``$XDG_DATA_HOME/rubricator`` (``~/.local/share/rubricator``) on Linux and
    macOS, ``%LOCALAPPDATA%\\rubricator`` on Windows. Resolved when called, never
    at import, so a bad variable fails the call that needs the directory rather
    than every import of the package.

    >>> working_dir() == data_dir() / "working"
    True
    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "rubricator"
    base = os.environ.get("XDG_DATA_HOME") or os.path.join("~", ".local", "share")
    return Path(base).expanduser() / "rubricator"


def working_dir() -> Path:
    """Where the working store keeps analyses: ``data_dir() / "working"``."""
    return data_dir() / _WORKING_KIND


def _package_dir() -> Path:
    from importlib.resources import files

    return Path(str(files("rubricator"))).resolve()


def _refuse_inside_package(root: str | os.PathLike[str]) -> Path:
    resolved = Path(root).expanduser().resolve()
    package = _package_dir()

    # samefile, not path equality: on a case-insensitive filesystem (a Mac's)
    # ".../RUBRICATOR/data" is inside the package and does not compare equal to it.
    def _is_package(candidate: Path) -> bool:
        return candidate == package or (
            candidate.exists() and package.exists() and os.path.samefile(candidate, package)
        )

    if any(_is_package(c) for c in (resolved, *resolved.parents)):
        raise ValueError(
            f"refused: {str(resolved)!r} is inside the rubricator package directory. Data in a "
            "code directory is deleted by the next install or deploy. Use the default "
            f"working store, or set {DATA_DIR_ENV} to a directory outside the package."
        )
    return resolved


def working_store() -> BytesStore:
    """The default persistent store: files under :func:`working_dir`."""
    return file_store(working_dir())


def file_store(root: str | os.PathLike[str]) -> BytesStore:
    """A filesystem store rooted at ``root``.

    ``dol.Files`` is exactly a ``MutableMapping[str, bytes]`` over a directory
    tree, so swapping in a GitHub-backed or object-store implementation later is
    a different argument at the composition root and no call-site change.

    Wrapped in ``mk_dirs_if_missing`` because the key layout is nested -- one
    directory per analysis, another for its contributions -- and a store that
    demanded its directories be created first would push a filesystem detail up
    into every caller, including the ones that will not be filesystems.

    Refuses a root inside the installed package directory (ADR-0017).
    """
    from dol import Files
    from dol.filesys import mk_dirs_if_missing

    resolved = _refuse_inside_package(root)
    # The wrapper only creates paths *below* the root, so the root itself is
    # ours to ensure. Stated rather than assumed: this is exactly the kind of
    # split responsibility that produces a confusing FileNotFoundError.
    os.makedirs(resolved, exist_ok=True)
    return mk_dirs_if_missing(Files(str(resolved)))


class AnalysisNotFound(KeyError):
    """No live analysis under this id: it never existed, or its retention window ran out.

    A ``KeyError``, so every surface already reports it as a recoverable tool
    error (ADR-0026), and typed, so a caller that wants to offer "open a fresh
    one" can catch exactly this. The two cases are deliberately one error
    (ADR-0017): the message names the window and the ways out, never which case
    it was.

    >>> str(AnalysisNotFound("a1", retention_days=30))  # doctest: +ELLIPSIS
    'no analysis "a1" in this store. Analyses are kept for 30 days from their last write...'
    """

    def __init__(self, analysis_id: str, *, retention_days: int) -> None:
        super().__init__(analysis_id)
        self.analysis_id = analysis_id
        self.retention_days = retention_days

    def __reduce__(self) -> tuple[Any, ...]:
        return (_not_found, (self.analysis_id, self.retention_days))

    def __str__(self) -> str:
        return (
            f'no analysis "{self.analysis_id}" in this store. Analyses are kept for '
            f"{self.retention_days} days from their last write, so this id has either expired "
            "or never existed here (the two are not distinguished). Open a fresh analysis with "
            "analysis_open, or list the analyses this store holds. If you expected it to be "
            "here, the store may be rooted somewhere else than the one that wrote it."
        )


def _not_found(analysis_id: str, retention_days: int) -> AnalysisNotFound:
    return AnalysisNotFound(analysis_id, retention_days=retention_days)


#: How a stamp's moment is spelled in its key: compact, sortable, and free of
#: ":" so it is a legal file name on every platform.
_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def _stamp_name(moment: str) -> str:
    return _instant(moment).astimezone(timezone.utc).strftime(_STAMP_FORMAT)


def _stamp_moment(name: str) -> datetime | None:
    """The moment a stamp's name spells, or ``None`` for anything else."""
    try:
        return datetime.strptime(name, _STAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _instant(stamp: str) -> datetime:
    """An RFC 3339 timestamp as an aware datetime; a naive one is read as UTC."""
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class AnalysisStore:
    """The document-shaped view over a bytes store.

    Everything above this reads and writes analyses; everything below it reads
    and writes bytes. That is the whole seam, and it is why ``blobs`` is a plain
    constructor argument rather than an interface with five methods.

    ``now`` and ``retention_days`` are the retention contract (ADR-0017): the
    clock dates every write and decides what has expired, so a test can move
    time without waiting for it. It is the wall clock by default and is
    deliberately not the clock the verbs stamp assertions with (see "Retention").

    >>> from rubricator.clock import fixed_clock
    >>> blobs = {}
    >>> AnalysisStore(blobs, now=fixed_clock("2026-01-01T00:00:00Z")).put_frame("a1", {})
    >>> later = AnalysisStore(blobs, now=fixed_clock("2026-03-01T00:00:00Z"))
    >>> later.exists("a1"), blobs
    (False, {})
    """

    blobs: BytesStore
    now: Clock = system_clock
    retention_days: int = RETENTION_DAYS

    def __post_init__(self) -> None:
        if (
            isinstance(self.retention_days, bool)
            or not isinstance(self.retention_days, int)
            or self.retention_days < 1
        ):
            raise ValueError(
                f"refused: retention_days={self.retention_days!r}. The retention window is a "
                "whole number of days, at least 1."
            )
        try:
            timedelta(days=self.retention_days)
        except OverflowError:
            raise ValueError(
                f"refused: retention_days={self.retention_days!r} is longer than a date can "
                "express. To keep analyses indefinitely, export them."
            ) from None

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

    @staticmethod
    def confirmation_key(analysis_id: str, name: str) -> str:
        return f"analyses/{analysis_id}/confirmations/{name}.json"

    @staticmethod
    def stamp_prefix(key: str) -> str:
        """The directory holding the stamps that date ``key``'s last write."""
        _, analysis_id, rest = key.split("/", 2)
        return f"analyses/{analysis_id}/touched/{rest}/"

    # -- retention ----------------------------------------------------------

    def _last_writes(self, prefix: str = "analyses/") -> dict[str, datetime | None]:
        """Every analysis id under ``prefix`` with its last write, in **one** walk.

        One pass over the keys however many analyses there are: listing or
        sweeping by asking each analysis in turn walks the store once per
        analysis, which is quadratic in a store that holds a month of work.

        A stamp dated after ``now`` is ignored: that write has not happened yet,
        so it is a fast clock or a stray, and counting it would keep the analysis
        alive for as long as the error lasts. An analysis with no usable stamp is
        undated (``None``) and kept.
        """
        now = _instant(self.now())
        latest: dict[str, datetime | None] = {}
        for key in self.blobs:
            if not key.startswith(prefix) or key.count("/") < 2:
                continue
            _, analysis_id, rest = key.split("/", 2)
            latest.setdefault(analysis_id, None)
            if not rest.startswith("touched/"):
                continue
            moment = _stamp_moment(rest.rsplit("/", 1)[-1])
            if moment is not None and moment <= now:
                current = latest[analysis_id]
                latest[analysis_id] = moment if current is None else max(current, moment)
        return latest

    def last_write(self, analysis_id: str) -> str | None:
        """The latest write to any part of the analysis, or ``None`` if undated."""
        moment = self._last_writes(f"analyses/{analysis_id}/").get(analysis_id)
        return None if moment is None else moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _is_expired(self, last: datetime | None) -> bool:
        if last is None:
            return False
        return _instant(self.now()) - last >= timedelta(days=self.retention_days)

    def expired(self, analysis_id: str) -> bool:
        """Whether the window has run out since the last write. Undated is never expired."""
        return self._is_expired(self._last_writes(f"analyses/{analysis_id}/").get(analysis_id))

    def sweep(self) -> list[str]:
        """Delete every expired analysis; the ids deleted, sorted.

        Expired analyses are also deleted whenever one is asked for, so the sweep
        is for reclaiming space, never for correctness.
        """
        gone = sorted(a for a, last in self._last_writes().items() if self._is_expired(last))
        for analysis_id in gone:
            self._purge(analysis_id)
        return gone

    def _purge(self, analysis_id: str) -> None:
        prefix = f"analyses/{analysis_id}/"
        for key in [k for k in self.blobs if k.startswith(prefix)]:
            del self.blobs[key]

    def _live(self, analysis_id: str) -> bool:
        """Whether the analysis is here and in its window; an expired one is deleted."""
        if self.frame_key(analysis_id) not in self.blobs:
            return False
        if self.expired(analysis_id):
            self._purge(analysis_id)
            return False
        return True

    def _require(self, analysis_id: str) -> None:
        if not self._live(analysis_id):
            raise AnalysisNotFound(analysis_id, retention_days=self.retention_days)

    # -- reading ------------------------------------------------------------

    def analyses(self) -> list[str]:
        """Every live analysis id in the store, sorted.

        Enumerable from v1 deliberately: migrating between backends is
        ``for k, v in old.items(): new[k] = v``, and that is only free if the
        store can be walked. Expired analyses are not listed, and are left for
        :meth:`sweep` or the next request for them to delete.
        """
        return sorted(a for a, last in self._last_writes().items() if not self._is_expired(last))

    def frame(self, analysis_id: str) -> dict[str, Any]:
        self._require(analysis_id)
        return self._read(self.frame_key(analysis_id))

    def contributors(self, analysis_id: str) -> list[str]:
        """Contributor ids with a file, sorted -- so a merge is reproducible."""
        self._require(analysis_id)
        return self._contributor_ids(analysis_id)

    def _contributor_ids(self, analysis_id: str) -> list[str]:
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
        self._require(analysis_id)
        for contributor_id in self._contributor_ids(analysis_id):
            yield contributor_id, self._read(self.contribution_key(analysis_id, contributor_id))

    def renditions(self, analysis_id: str) -> list[dict[str, Any]]:
        self._require(analysis_id)
        prefix = f"analyses/{analysis_id}/renditions/"
        return [self._read(k) for k in sorted(k for k in self.blobs if k.startswith(prefix))]

    def read(self, analysis_id: str) -> dict[str, Any]:
        """The whole analysis: the frame and every contribution, merged.

        The record is the document (ADR-0017): what comes back is one comparanda
        analysis at whatever stage the work has reached, never a checkpoint
        format. Merged on read and never written back (its 2026-08-22 amendment).
        """
        from rubricator.merge import merge_contributions

        return merge_contributions(
            self.frame(analysis_id),
            self.contributions(analysis_id),
            renditions=self.renditions(analysis_id),
        )

    # -- writing ------------------------------------------------------------

    # Ids are checked on the write path only. A read lists the keys that exist
    # and must be able to read them all back -- a stray file in a shared
    # repository must not make the whole analysis unreadable.
    #
    # A contribution or a rendition needs a live analysis: writing one to an
    # expired analysis would re-date it and bring back a record the window had
    # already ended. A frame written over an expired analysis starts afresh,
    # which is what reopening an expired id means.

    def put_frame(self, analysis_id: str, frame: dict[str, Any]) -> None:
        check_id(analysis_id)
        if self.expired(analysis_id):
            self._purge(analysis_id)
        self._write(self.frame_key(analysis_id), frame)

    def put_contribution(
        self, analysis_id: str, contributor_id: str, contribution: dict[str, Any]
    ) -> None:
        check_id(analysis_id)
        check_id(contributor_id)
        self._require(analysis_id)
        self._write(self.contribution_key(analysis_id, contributor_id), contribution)

    def put_rendition(self, analysis_id: str, rendition: dict[str, Any]) -> None:
        check_id(analysis_id)
        check_id(rendition["id"])
        self._require(analysis_id)
        self._write(self.rendition_key(analysis_id, rendition["id"]), rendition)

    def _confirmation_keys(self, analysis_id: str) -> list[str]:
        prefix = f"analyses/{analysis_id}/confirmations/"
        return sorted(k for k in self.blobs if k.startswith(prefix) and k.endswith(".json"))

    def confirmations(self, analysis_id: str) -> list[dict[str, Any]]:
        """The step-4 records (ADR-0005), in write order; empty when none was given.

        A record file that cannot be read comes back as
        ``{"decision": "unreadable", "key": ...}`` rather than raising or being
        skipped: skipping one could drop a ``revise`` and reopen the gate, and
        raising would lock the analysis on one bad file. The gate reads an
        unreadable record as closing everything until it is repaired.
        """
        self._require(analysis_id)
        records: list[dict[str, Any]] = []
        for key in self._confirmation_keys(analysis_id):
            try:
                record = self._read(key)
            except (KeyError, UnicodeDecodeError, ValueError):
                record = None
            records.append(
                record if isinstance(record, dict) else {"decision": "unreadable", "key": key}
            )
        return records

    def add_confirmation(self, analysis_id: str, record: dict[str, Any]) -> None:
        """Write one record as its own file: never a shared file two branches append to."""
        check_id(analysis_id)
        self._require(analysis_id)
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode(_ENCODING)
        sequence = len(self._confirmation_keys(analysis_id)) + 1
        name = f"{sequence:06d}-{hashlib.sha256(payload).hexdigest()[:12]}"
        self._write(self.confirmation_key(analysis_id, name), record)

    def clear_confirmations(self, analysis_id: str) -> None:
        """Remove every record: a new analysis inherits no gate from a leftover file."""
        for key in self._confirmation_keys(analysis_id):
            del self.blobs[key]
            for stamp in [k for k in self.blobs if k.startswith(self.stamp_prefix(key))]:
                del self.blobs[stamp]

    def exists(self, analysis_id: str) -> bool:
        """Whether a live analysis is here. An expired one is deleted and is not."""
        return self._live(analysis_id)

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
        prefix = self.stamp_prefix(key)
        stamp = prefix + _stamp_name(self.now())
        self.blobs[stamp] = b""
        for old in [k for k in self.blobs if k.startswith(prefix) and k != stamp]:
            del self.blobs[old]
