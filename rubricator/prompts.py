"""The prompt bundle: content on disk, read through one accessor.

Prompts are **content, not code** (ADR-0003), and both runtimes serve the same
files -- the connector hands them to the caller's model, the deployed agent loads
them into its own loop. That is only true if there is exactly one thing that
knows where they are, which is this module.

**Why a directory of Markdown rather than strings in a module.** A prompt that
lives in a Python string is edited by whoever is editing Python, reviewed as a
diff of escaped text, and impossible to serve to an MCP client as a resource. A
prompt that lives in a file can be read by a person, versioned on its own, and
handed to either runtime unchanged. ADR-0007 was settled on exactly this: serving
the prompts *is* the prompt bundle, so there is no second artifact to build.

**The seam is ``root``.** It defaults to the shipped directory, which is the
strongest implementation that needs no new dependency: the files ship in the
wheel (``pyproject.toml`` ``[tool.hatch.build] artifacts``). Point it at a
directory of overrides and a deployment serves its own wording with no call site
changing. Nothing here caches across roots, so a test can point at a fixture
directory and get exactly what is in it.

**Front matter is a deliberately small dialect** -- flat ``key: value`` scalars
plus ``key:`` followed by ``  - item`` lists. Not YAML, because a full YAML
parser is a dependency this package does not otherwise need, and the connector
runtime is the one that must install in a bare environment. If a prompt ever
needs nested structure, that is the signal that the structure belongs in the
tool layer rather than in a prompt's header.

>>> p = prompts()['score-cell']
>>> p.version >= 1
True
>>> 'not-evidenced' in p.missing_codes and 'indeterminate' in p.missing_codes
True
>>> p.body.startswith('# Score one cell')
True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

__all__ = ["Prompt", "prompts", "PROMPTS_DIR"]

#: Where the shipped prompts live. One constant, so that "where are the prompts"
#: has one answer for the wheel, the tests and both runtimes.
PROMPTS_DIR = Path(__file__).parent / "data" / "prompts"

_FENCE = "---"


@dataclass(frozen=True)
class Prompt:
    """One prompt, as served.

    ``body`` is what a model sees. The header is *not* part of it: a changelog
    entry is provenance for the humans maintaining the prompt, and pasting it in
    front of the instructions is both noise and a small invitation to follow it.
    """

    id: str
    title: str
    version: int
    body: str
    stage: int | None = None
    updated: str | None = None
    #: The missingness codes this prompt teaches, declared rather than inferred.
    #: Declared because a test checks them against the live vocabulary manifest:
    #: when the companion repository renames a code, the prompt that still names
    #: the old spelling fails loudly instead of quietly teaching a code the tool
    #: layer will reject.
    missing_codes: tuple[str, ...] = ()
    changelog: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)


def prompts(root: str | Path | None = None) -> Mapping[str, Prompt]:
    """Every prompt in ``root``, keyed by id.

    A read-only mapping rather than a class with lookup methods: the bundle is
    data, and a caller wanting to list, filter or serve it should not have to
    learn an interface. Read-only because the shipped bundle is handed out by
    reference -- a caller that could write to it would be editing what every
    later caller in the process serves, which is the opposite of "one thing knows
    where the prompts are".

    **Only the shipped directory is cached.** It is a frozen build artifact read
    many times per analysis. A caller-supplied root is not frozen -- it is the
    override seam, and somebody iterating on wording would otherwise edit a file
    and be served the previous version until the process restarted.

    A root with no ``.md`` files at all raises rather than returning nothing: a
    typo in an override path would otherwise serve an empty bundle in silence,
    and "the connector has no prompts" is not a failure anyone notices quickly.
    """
    if root is None:
        return _shipped()
    return _load(Path(root))


@lru_cache(maxsize=1)
def _shipped() -> Mapping[str, Prompt]:
    """The bundle inside the wheel, read once."""
    return _load(PROMPTS_DIR)


def _load(root: Path) -> Mapping[str, Prompt]:
    found: dict[str, Prompt] = {}
    for path in sorted(root.glob("*.md")):
        prompt = _parse(path.read_text(encoding="utf-8"), default_id=path.stem)
        if prompt.id in found:
            raise ValueError(
                f'two prompts in {root} claim id "{prompt.id}" -- the later one would win '
                "silently, and every run recorded against that id would name two different "
                "sets of instructions."
            )
        found[prompt.id] = prompt
    if not found:
        raise FileNotFoundError(
            f"no prompt files in {root}. A runtime with an empty bundle serves nothing and "
            "says nothing about it; check the path before assuming the prompts were dropped."
        )
    return MappingProxyType(found)


def _parse(text: str, *, default_id: str) -> Prompt:
    """Split front matter from body and build a :class:`Prompt`.

    A file with no front matter is still a prompt -- it takes its id from its
    filename and version 0, which reads as "unversioned" in any report. Refusing
    it outright would make the loader the thing that has to be fixed first when
    someone drafts a prompt, and the point of content files is that drafting one
    costs nothing.
    """
    header, body = _split(text)
    meta = _front_matter(header)
    known = {"id", "title", "version", "stage", "updated", "missing-codes", "changelog"}
    return Prompt(
        id=_scalar(meta, "id") or default_id,
        title=_scalar(meta, "title") or default_id,
        version=_as_int(_scalar(meta, "version")),
        stage=_as_int(_scalar(meta, "stage")) if "stage" in meta else None,
        updated=_scalar(meta, "updated"),
        missing_codes=tuple(_as_list(meta.get("missing-codes", ()))),
        changelog=tuple(_as_list(meta.get("changelog", ()))),
        body=body.strip(),
        extra={k: v for k, v in meta.items() if k not in known},
    )


def _scalar(meta: Mapping[str, Any], key: str) -> str | None:
    """A scalar value, or ``None`` where the key is absent or is a list.

    ``title:`` with nothing after it parses as an empty list, and ``str([])`` is
    the string ``"[]"`` -- a title that looks deliberate and is a bug.
    """
    value = meta.get(key)
    return value if isinstance(value, str) else None


def _split(text: str) -> tuple[str, str]:
    """Header and body, around the first pair of ``---`` fences.

    A leading BOM is stripped first. An editor that adds one would otherwise make
    the first line not equal ``---``, the whole file would read as a body with no
    header, and the prompt would be served to a model with its own front matter
    at the top -- a failure whose cause is invisible in every diff.
    """
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != _FENCE:
        return "", text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FENCE:
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", text  # an unterminated fence is a malformed header, not a body


def _front_matter(header: str) -> dict[str, Any]:
    """The small dialect: ``key: value`` scalars, and ``key:`` + ``- item`` lists.

    A list item is recognised at **any** indentation, including none. YAML
    permits both, and the unindented form read as a key would silently drop the
    item and invent a garbage key beside it -- the guard tests in
    ``tests/test_prompts.py`` would catch the result, but only after the author
    had gone looking for a bug in their prose.
    """
    meta: dict[str, Any] = {}
    current: list[str] | None = None
    for raw in header.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current is not None:
                current.append(stripped[2:].strip())
            continue
        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            meta[key], current = value, None
        else:
            current = meta[key] = []
    return meta


def _as_int(value: Any) -> int:
    """An integer, or ``0`` for anything that is not one.

    ``0`` rather than an exception, because the loader stays permissive and the
    suite is what is strict: a prompt at version 0 is refused by
    ``tests/test_prompts.py``, and so is a prompt whose ``stage`` failed to parse.
    """
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _as_list(value: Any) -> Sequence[str]:
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]
