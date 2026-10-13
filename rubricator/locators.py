"""The evidence-reference locator profile: typed selectors, their fragments, and what is refused.

ADR-0014 narrows the W3C Web Annotation selector model to what a producer
holding text, a PDF or a media file can honestly produce. **Positions are hints;
quotes are truth.** A reference is a flat array of selectors that all select the
same span, and a ``TextQuoteSelector`` is mandatory wherever a text layer exists.

The profile, and nothing else, can be constructed here:

======================  =====================================================
``TextQuoteSelector``   the truth: ``prefix`` / ``exact`` / ``suffix``
``TextPositionSelector`` a hint, allowed to go stale, never the sole locator
``LineRangeSelector``   lines, 1-based and inclusive, as a person counts them
``PageSelector``        **both** ``index`` (0-based) and ``label``
``MediaTimeSelector``   seconds into a media file
``FragmentSelector``    the extension point: a fragment and its ``conformsTo``
======================  =====================================================

**Rejected:** ``CssSelector``, ``XPathSelector``, ``DataPositionSelector``,
``RangeSelector`` -- and comparanda's ``PathSelector``, which carries the same
two syntaxes. Every one binds a reference to a DOM the producer never had. There
is no class for them, :func:`selector_from_dict` refuses them, and
:func:`profile_problems` is what the write path runs so that one is never stored.

**Every typed selector serialises losslessly to a** ``FragmentSelector``
(:func:`to_fragment`, :func:`from_fragment`), so a reference round-trips to a
standard annotation and back. Two off-by-one traps, documented rather than
discovered:

- A page has an **index** and a **label**, and they are different numbers: a
  journal PDF shows "iv" at index 3. RFC 8118's ``page=`` is 1-based, so index 3
  is ``page=4``. RFC 8118 has no parameter for a label; it rides as
  ``pagelabel=``, this profile's extension, which an RFC 8118 reader ignores.
- RFC 5147 line positions are the **boundaries between** lines: ``line=40,58``
  is lines 41 to 58. So :class:`LineRangeSelector` (41, 58) is ``line=40,58``.

**A stored hash names its normaliser, and matches** (#195, from #174). An
``excerptHash`` is taken over the excerpt as a normaliser renders it
(:mod:`rubricator.normalise`), so one is refused without its excerpt, without
the ``normaliserId`` it was made under, or when it does not match; an unknown
``normaliserId`` is refused outright, never checked under another (ADR-0021).

**A text-fragment link is derived, never stored.** ``#:~:text=prefix-,exact,-suffix``
is isomorphic to a ``TextQuoteSelector``; :func:`text_fragment_link` renders it
from the stored quote, and :func:`profile_problems` refuses a stored fragment
that conforms to Text Fragments, because it would be a second, competing copy of
the same locator.

>>> quote = TextQuoteSelector(exact="supported until 2029", prefix="is ", suffix=".")
>>> text_fragment_link(quote, url="https://example.org/support")
'https://example.org/support#:~:text=is%20-,supported%20until%202029,-.'
>>> from_fragment(to_fragment(LineRangeSelector(41, 58))) == LineRangeSelector(41, 58)
True
>>> to_fragment(LineRangeSelector(41, 58)).value
'line=40,58'
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping, Union
from urllib.parse import quote as _percent, unquote

__all__ = [
    "TextQuoteSelector",
    "TextPositionSelector",
    "LineRangeSelector",
    "PageSelector",
    "MediaTimeSelector",
    "FragmentSelector",
    "Selector",
    "REJECTED",
    "RFC_5147",
    "RFC_8118",
    "MEDIA_FRAGMENTS",
    "TEXT_FRAGMENTS",
    "selector_from_dict",
    "selector_to_dict",
    "to_stored",
    "to_fragment",
    "from_fragment",
    "text_fragment_link",
    "profile_problems",
    "is_blank_text",
]

#: The ``conformsTo`` value of each fragment standard this profile reaches.
RFC_5147 = "http://tools.ietf.org/rfc/rfc5147"
RFC_8118 = "http://tools.ietf.org/rfc/rfc8118"
MEDIA_FRAGMENTS = "http://www.w3.org/TR/media-frags/"
TEXT_FRAGMENTS = "https://wicg.github.io/scroll-to-text-fragment/"

#: Each rejected selector type, and why. Shown verbatim in every refusal.
REJECTED: Mapping[str, str] = {
    name: "it binds the reference to a DOM the producer never had; a corpus document is text, "
          "a PDF or a media file, not a live page (ADR-0014). Locate the span with a "
          "TextQuoteSelector instead"
    for name in ("CssSelector", "XPathSelector", "DataPositionSelector", "RangeSelector",
                 "PathSelector")
}

#: Selectors that address a text layer: where one is present, a quote must be too.
_TEXT_ADDRESSED = ("TextPositionSelector", "LineRangeSelector")


def is_blank_text(value: str) -> bool:
    """Whether ``value`` has nothing visible in it.

    ``str.strip`` keeps a zero-width space (a format character), so a quote or
    a note of one would read as written and say nothing.

    >>> is_blank_text(" \\u200b\\n"), is_blank_text("2029")
    (True, False)
    """
    import unicodedata

    return all(ch.isspace() or unicodedata.category(ch) == "Cf" for ch in value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _count(value: Any, name: str) -> None:
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
             f"{name} must be a non-negative integer, got {value!r}")


def _text(value: Any, name: str, *, required: bool = False) -> None:
    """A string that can travel: UTF-8 encodable (no lone surrogate), non-blank when required."""
    _require(isinstance(value, str), f"{name} must be a string, got {value!r}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"{name} holds a lone surrogate, which no document can contain") from None
    _require(not required or not is_blank_text(value), f"{name} must not be blank")


def _seconds(value: Any, name: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{name} must be a number of seconds, got {value!r}")
    try:
        seconds = float(value)
    except OverflowError:
        raise ValueError(f"{name} is too large to be a time: {value!r}") from None
    _require(math.isfinite(seconds) and seconds >= 0,
             f"{name} must be a finite, non-negative number of seconds, got {value!r}")
    return seconds


@dataclass(frozen=True)
class TextQuoteSelector:
    """The span's own words, with context to disambiguate it. The truth of a reference."""

    exact: str
    prefix: str = ""
    suffix: str = ""

    def __post_init__(self) -> None:
        _text(self.exact, "exact", required=True)
        _text(self.prefix, "prefix")
        _text(self.suffix, "suffix")


@dataclass(frozen=True)
class TextPositionSelector:
    """Character offsets ``[start, end)`` into the normalised rendition. A hint that may go stale."""

    start: int
    end: int

    def __post_init__(self) -> None:
        _count(self.start, "start")
        _count(self.end, "end")
        _require(self.start < self.end,
                 f"[{self.start}, {self.end}) selects no characters; end must be after start")


@dataclass(frozen=True)
class LineRangeSelector:
    """Lines ``start_line`` to ``end_line``, 1-based and inclusive -- not RFC 5147's boundaries."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _count(self.start_line, "start_line")
        _count(self.end_line, "end_line")
        _require(1 <= self.start_line <= self.end_line,
                 f"lines run from 1, start before end: got {self.start_line}..{self.end_line}")


@dataclass(frozen=True)
class PageSelector:
    """A page, by its 0-based ``index`` in the file **and** the ``label`` printed on it."""

    index: int
    label: str

    def __post_init__(self) -> None:
        _count(self.index, "index")
        _require(isinstance(self.label, str) and bool(self.label),
                 "a page needs its label as well as its index: they are different numbers")
        _text(self.label, "label", required=True)


@dataclass(frozen=True)
class MediaTimeSelector:
    """Seconds ``[start, end]`` into a media file."""

    start: float
    end: float

    def __post_init__(self) -> None:
        start, end = _seconds(self.start, "start"), _seconds(self.end, "end")
        _require(start < end, f"{start}s to {end}s selects no time; end must be after start")


@dataclass(frozen=True)
class FragmentSelector:
    """A fragment identifier, and the standard it conforms to. The profile's extension point."""

    value: str
    conforms_to: str

    def __post_init__(self) -> None:
        _text(self.value, "value", required=True)
        _text(self.conforms_to, "conformsTo", required=True)


Selector = Union[TextQuoteSelector, TextPositionSelector, LineRangeSelector, PageSelector,
                 MediaTimeSelector, FragmentSelector]

_TYPES = {cls.__name__: cls for cls in (TextQuoteSelector, TextPositionSelector,
                                        LineRangeSelector, PageSelector, MediaTimeSelector,
                                        FragmentSelector)}
#: The wire spelling of each field, where it differs from the Python one (W3C / Hypothesis).
_WIRE = {"start_line": "startLine", "end_line": "endLine", "conforms_to": "conformsTo"}


def selector_from_dict(data: Mapping[str, Any]) -> Selector:
    """A typed selector from its JSON shape; a rejected or unknown type is refused with the reason.

    >>> selector_from_dict({"type": "PageSelector", "index": 3, "label": "iv"})
    PageSelector(index=3, label='iv')
    >>> selector_from_dict({"type": "XPathSelector", "value": "//p"})
    Traceback (most recent call last):
    ...
    ValueError: XPathSelector is not in the locator profile: it binds the reference to a DOM ...
    """
    kind = data.get("type")
    _require(isinstance(kind, str), f"a selector's type must be a string, got {kind!r}")
    if kind in REJECTED:
        raise ValueError(f"{kind} is not in the locator profile: {REJECTED[kind]}")
    if kind not in _TYPES:
        raise ValueError(f"{kind!r} is not a selector type in the locator profile "
                         f"(known: {', '.join(_TYPES)})")
    wire = {_WIRE.get(k, k): k for k in _TYPES[kind].__dataclass_fields__}
    extra = sorted(set(data) - set(wire) - {"type"})
    _require(not extra, f"{kind} has no field {', '.join(extra)}")
    return _TYPES[kind](**{wire[k]: v for k, v in data.items() if k != "type"})


def selector_to_dict(selector: Selector) -> dict[str, Any]:
    """The JSON shape of a typed selector -- the inverse of :func:`selector_from_dict`."""
    return {"type": type(selector).__name__,
            **{_WIRE.get(k, k): v for k, v in asdict(selector).items()}}


def to_stored(selector: Selector) -> dict[str, Any]:
    """The selector in the shape comparanda v1 stores, or a refusal when v1 has no lossless slot.

    v1 names two of the profile's selectors differently and has no slot at all
    for a page label or a fragment. Mapping a :class:`PageSelector` onto
    ``PageRegionSelector`` would drop the label -- the trap the profile exists to
    prevent -- so both are refused until the contract carries them (#173).

    >>> to_stored(MediaTimeSelector(1.5, 2))
    {'type': 'TimeRangeSelector', 'startSeconds': 1.5, 'endSeconds': 2}
    """
    if isinstance(selector, (TextQuoteSelector, TextPositionSelector, LineRangeSelector)):
        return selector_to_dict(selector)
    if isinstance(selector, MediaTimeSelector):
        return {"type": "TimeRangeSelector", "startSeconds": selector.start,
                "endSeconds": selector.end}
    raise ValueError(
        f"{type(selector).__name__} has no lossless slot in comparanda v1's stored selectors "
        "(#173); keep the TextQuoteSelector, which every text-layer reference carries anyway"
    )


# -- fragments ---------------------------------------------------------------------------------

def _number(value: float) -> str:
    """The shortest plain-decimal spelling that reads back as the same float.

    Media Fragments' ``npt`` seconds are digits with an optional fraction and no
    exponent, so ``repr`` (``1e-05``) is not allowed: the shortest round-tripping
    digits are written out in positional form instead (``0.00001``).
    """
    if float(value).is_integer():
        return str(int(value))
    return format(Decimal(repr(float(value))), "f")


def _directive(text: str) -> str:
    """Percent-encode for a text directive, where ``-``, ``,`` and ``&`` are syntax."""
    return _percent(text, safe="").replace("-", "%2D")


def to_fragment(selector: Selector) -> FragmentSelector:
    """The selector as a standard fragment identifier, losslessly."""
    if isinstance(selector, FragmentSelector):
        return selector
    if isinstance(selector, TextPositionSelector):
        return FragmentSelector(f"char={selector.start},{selector.end}", RFC_5147)
    if isinstance(selector, LineRangeSelector):
        # RFC 5147 counts boundaries: line 41 starts at boundary 40.
        return FragmentSelector(f"line={selector.start_line - 1},{selector.end_line}", RFC_5147)
    if isinstance(selector, PageSelector):
        return FragmentSelector(
            f"page={selector.index + 1}&pagelabel={_percent(selector.label, safe='')}", RFC_8118)
    if isinstance(selector, MediaTimeSelector):
        return FragmentSelector(f"t={_number(selector.start)},{_number(selector.end)}",
                                MEDIA_FRAGMENTS)
    if isinstance(selector, TextQuoteSelector):
        parts = ([f"{_directive(selector.prefix)}-"] if selector.prefix else []) + \
                [_directive(selector.exact)] + \
                ([f"-{_directive(selector.suffix)}"] if selector.suffix else [])
        return FragmentSelector(":~:text=" + ",".join(parts), TEXT_FRAGMENTS)
    raise TypeError(f"{type(selector).__name__} is not a selector in the locator profile")


_CHAR = re.compile(r"char=(\d+),(\d+)")
_LINE = re.compile(r"line=(\d+),(\d+)")
_PAGE = re.compile(r"page=(\d+)&pagelabel=([^&]+)")
_TIME = re.compile(r"t=(?:npt:)?(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)")


def from_fragment(fragment: FragmentSelector) -> Selector:
    """The typed selector a fragment serialises; the fragment itself when it is none of them."""
    standard, value = fragment.conforms_to, fragment.value
    if standard == RFC_5147 and (m := _CHAR.fullmatch(value)):
        return TextPositionSelector(int(m[1]), int(m[2]))
    if standard == RFC_5147 and (m := _LINE.fullmatch(value)):
        return LineRangeSelector(int(m[1]) + 1, int(m[2]))
    if standard == RFC_8118 and (m := _PAGE.fullmatch(value)):
        return PageSelector(int(m[1]) - 1, unquote(m[2]))
    if standard == MEDIA_FRAGMENTS and (m := _TIME.fullmatch(value)):
        return MediaTimeSelector(float(m[1]), float(m[2]))
    if standard == TEXT_FRAGMENTS and value.startswith(":~:text="):
        parts = value[len(":~:text="):].split(",")
        prefix = unquote(parts.pop(0)[:-1]) if parts[0].endswith("-") and len(parts) > 1 else ""
        suffix = unquote(parts.pop()[1:]) if len(parts) > 1 and parts[-1].startswith("-") else ""
        _require(len(parts) == 1, f"a text fragment with a range is not a quote: {value!r}")
        return TextQuoteSelector(unquote(parts[0]), prefix, suffix)
    return fragment


def text_fragment_link(quote: TextQuoteSelector, *, url: str = "") -> str:
    """A deep link that scrolls to the quote, rendered from it -- never stored beside it."""
    return f"{url}#{to_fragment(quote).value}"


# -- the write path ----------------------------------------------------------------------------

#: How each stored comparanda v1 selector reads as a profile type, for validation.
#: ``contentHash`` on a line range is v1's own integrity field and is not checked here.
_AS_PROFILE = {
    "TextQuoteSelector": lambda s: selector_from_dict(s),
    "TextPositionSelector": lambda s: selector_from_dict(s),
    "LineRangeSelector": lambda s: LineRangeSelector(s.get("startLine"), s.get("endLine")),
    "TimeRangeSelector": lambda s: MediaTimeSelector(s.get("startSeconds"), s.get("endSeconds")),
    "PageRegionSelector": lambda s: _page_region(s),
}


def _page_region(stored: Mapping[str, Any]) -> None:
    """comparanda v1's ``PageRegionSelector``: a whole page number and, optionally, a box on it.

    The box must select an area at a non-negative position. Its unit is not
    held here: the companion documents fractions of the page, and producers
    have written pixels, so bounding it at 1 is an open contract question
    rather than a rule. The profile has no type of its own for it, so it is
    checked here and stored as given.
    """
    def number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    page = stored.get("page")
    finite = {"page": page, **(stored["rect"] if isinstance(stored.get("rect"), Mapping) else {})}
    _require(all(math.isfinite(v) for v in finite.values() if number(v)),
             f"a page region holds a NaN or infinite number, which no document can carry: {finite!r}")
    _require(number(page) and page >= 0 and float(page).is_integer(),
             f"page must be a whole, non-negative page number, got {page!r}")
    rect = stored.get("rect")
    if rect is None:
        return
    _require(isinstance(rect, Mapping), f"rect must be an object, got {rect!r}")
    sides = {k: rect.get(k) for k in ("x", "y", "w", "h")}
    _require(all(number(v) and v >= 0 for v in sides.values()),
             f"rect's x, y, w and h are non-negative numbers, got {sides!r}")
    _require(sides["w"] > 0 and sides["h"] > 0, "rect selects no area: w and h must be above 0")


def _hash_problems(ref: Mapping[str, Any]) -> list[str]:
    """What is wrong with a reference's ``normaliserId`` and ``excerptHash``, as sentences."""
    from rubricator.normalise import NORMALISERS, excerpt_matches

    normaliser, recorded, excerpt = ref.get("normaliserId"), ref.get("excerptHash"), ref.get("excerpt")
    if normaliser is not None and normaliser not in NORMALISERS:
        return [f"normaliserId {normaliser!r} is not one this package can reproduce (known: "
                f"{', '.join(sorted(NORMALISERS))}); a quote recorded under it cannot be checked, "
                "and is never checked under another (ADR-0021)"]
    if recorded is None:
        return []
    if not isinstance(excerpt, str) or is_blank_text(excerpt):
        return ["an excerptHash with no excerpt hashes nothing a reader can see; add the excerpt "
                "it was taken over, or drop excerptHash"]
    if normaliser is None:
        return ["an excerptHash without the normaliserId it was made under cannot be re-checked; "
                "add normaliserId (normalise.CURRENT for a hash made now)"]
    if not excerpt_matches(excerpt, recorded, normaliser_id=normaliser):
        return [f"excerptHash does not match its excerpt under {normaliser}; recompute it with "
                "normalise.excerpt_hash, or correct the excerpt"]
    return []


def _same_standard(a: Any, b: str) -> bool:
    return isinstance(a, str) and a.rstrip("/") == b.rstrip("/")


def profile_problems(evidence: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every way a set of evidence references leaves the locator profile, each naming the reference.

    Run before anything is stored. Refuses a rejected selector type, a stored
    text fragment (derive it instead), a selector the profile's own rules refuse
    (a blank quote, an empty or reversed range), and a position with no usable
    quote beside it.

    >>> profile_problems([{"id": "e1", "selectors": [{"type": "TextPositionSelector", "start": 1, "end": 4}]}])
    ['evidence e1: a TextPositionSelector is a hint that may go stale and is never the sole locator; add the TextQuoteSelector for the same span (ADR-0014)']
    """
    out: list[str] = []
    # A reference that is not an object is a shape problem, the schema's to
    # report; skipped here so this check never raises on one (#179).
    for ref in (r for r in evidence if isinstance(r, Mapping)):
        where = f"evidence {ref.get('id', '?')}"
        raw = ref.get("selectors")
        selectors = [s for s in raw if isinstance(s, Mapping)] if isinstance(raw, (list, tuple)) else []
        kinds = [k if isinstance(k, str) else repr(k) for k in (s.get("type") for s in selectors)]
        out += [f"{where}: {kind} is not in the locator profile: {REJECTED[kind]}"
                for kind in kinds if kind in REJECTED]
        out += [f"{where}: a text-fragment link is rendered from the TextQuoteSelector, never "
                "stored beside it as a second locator; drop the FragmentSelector (ADR-0014)"
                for s in selectors
                if s.get("type") == "FragmentSelector"
                and _same_standard(s.get("conformsTo"), TEXT_FRAGMENTS)]
        out += [f"{where}: {p}" for p in _hash_problems(ref)]
        valid: list[str] = []
        for selector, kind in zip(selectors, kinds):
            if kind not in _AS_PROFILE:
                continue
            try:
                _AS_PROFILE[kind](selector)
                valid.append(kind)
            except (ValueError, TypeError) as refused:
                out.append(f"{where}: {kind} is outside the locator profile: {refused}")
        out += [f"{where}: a {kind} is a hint that may go stale and is never the sole locator; "
                "add the TextQuoteSelector for the same span (ADR-0014)"
                for kind in dict.fromkeys(kinds)
                if kind in _TEXT_ADDRESSED and "TextQuoteSelector" not in valid]
    return out
