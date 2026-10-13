"""The versioned ingest-time normaliser: the text every stored quote resolves against.

ADR-0014 (and its 2026-08-22 amendment) makes normalisation a **stored
artifact**, not a comparison tolerance. A rendition is normalised once, at
ingest, and every quote's ``excerptHash`` is taken over normalised text -- so
changing what normalisation does silently invalidates every hash anyone has ever
stored, and nothing would raise. Hence three rules, each mechanical here:

- **Every normaliser has an id, and the id is stored on the reference**
  (``normaliserId``). :func:`excerpt_hash` and :func:`excerpt_matches` take it
  explicitly; there is no "whatever the current one is" at check time.
- **The table is append-only.** A version is never edited and never removed. A
  better de-hyphenator ships as ``nfc-v2`` beside ``nfc-v1``, and re-checking old
  references under it is a migration someone chooses.
- **Each version's behaviour is pinned.** :data:`PINS` holds the sha256 of each
  normaliser's output over :data:`PROBE`, a string that exercises every step.
  :func:`drifted` names any normaliser whose output no longer matches its pin --
  which is what an edit in place looks like -- and a test keeps it empty.

An unknown id is refused, never degraded to the nearest known one (ADR-0021):
claiming a quote was checked against text we cannot reproduce is the confident
guess in a different costume.

This is **not** :func:`rubricator.tools.citations.normalise_for_match`. That one
is a match-time tolerance and may change freely; this one produces what is
stored. Neither may stand in for the other.

>>> normalise("The \\ufb01rst  infor-\\nmation \\u201cpage\\u201d\\u200b")
'The first information "page"'
>>> excerpt_matches("infor-\\nmation", excerpt_hash("information"), normaliser_id="nfc-v1")
True
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Callable, Mapping

__all__ = [
    "CURRENT",
    "NORMALISERS",
    "PINS",
    "PROBE",
    "normalise",
    "excerpt_hash",
    "excerpt_matches",
    "drifted",
]

Normaliser = Callable[[str], str]

#: Characters that render as nothing and survive copy-paste: zero-width space,
#: non-joiner, joiner, word joiner, the BOM. The soft hyphen is invisible too, but
#: it is removed only after de-hyphenation has read it as a line-break hyphen.
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))
_SOFT_HYPHEN = "\u00ad"

#: Typographic variants a quote may carry in either direction, and the
#: ligatures a PDF text layer emits. Folded to one spelling each.
_FOLD = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u2026": "...",
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
    "\ufb05": "st", "\ufb06": "st",
})

#: Any line break a text layer emits: CRLF, LF, a bare CR, and the Unicode line
#: and paragraph separators.
_BREAK = r"[ \t]*(?:\r\n|[\n\r\u2028\u2029])[ \t]*"
#: A soft hyphen at a line break is always a word broken by layout: joined.
_SOFT_BREAK = re.compile(_SOFT_HYPHEN + _BREAK)
#: A hard hyphen at a line break between a letter and a lowercase letter: joined,
#: as a word the layout broke. "well-\nKnown" and "1990-\n2000" are left alone --
#: a capital or a digit after the break means the hyphen was real. **Known limit,
#: pinned by a test rather than hidden:** a lowercase compound broken at its own
#: hyphen ("well-\nknown") is joined too ("wellknown"); nothing in the text says
#: which it was. Match-time tolerance (``normalise_for_match``) is where a quote
#: written "well-known" is still found.
_HARD_BREAK = re.compile(r"(?<=[^\W\d_])-" + _BREAK + r"(?=[^\W\d_])")
_WHITESPACE = re.compile(r"\s+")


def _nfc_v1(text: str) -> str:
    """Zero-width strip, folding, de-hyphenation, then NFC, then whitespace collapse.

    NFC comes after the strip and the folds, not before: removing a zero-width
    character or unfolding a ligature can leave a base letter beside a combining
    mark that NFC has not yet composed, and the result would not be idempotent --
    a quote copied out of a rendition would normalise to something else.
    """
    out = text.translate(_ZERO_WIDTH).translate(_FOLD)
    out = _SOFT_BREAK.sub("", out)
    out = _HARD_BREAK.sub(lambda m: "" if _text_after(m).islower() else m.group(0), out)
    out = unicodedata.normalize("NFC", out.replace(_SOFT_HYPHEN, ""))
    return _WHITESPACE.sub(" ", out).strip()


def _text_after(match: re.Match[str]) -> str:
    """The character right after ``match`` -- the first letter of the line that continues."""
    return match.string[match.end(): match.end() + 1]


#: Append-only. A new behaviour is a new id; an existing entry is never edited.
NORMALISERS: Mapping[str, Normaliser] = {"nfc-v1": _nfc_v1}

#: The normaliser new renditions are made with.
CURRENT = "nfc-v1"

#: Exercises every step, and the characters a plausible edit would treat
#: differently: decomposed accents (one behind a zero-width character, one on a
#: ligature), compatibility characters NFKC would change and NFC must not
#: (fullwidth, superscript, a digraph), curly quotes, primes, look-alikes that
#: are deliberately not folded (U+02BC, U+FF0D), an ellipsis, soft and hard
#: hyphens at every kind of line break, real hyphens before a capital and a
#: digit, and whitespace of every kind -- NBSP, ideographic space, vertical tab,
#: line and paragraph separators.
PROBE = (
    "Cafe\u0301 e\u200b\u0301 \ufb01\u0301 \u200bco\u00adop\u2060era\ufefftive: "
    "\uff21\u00b2\u01c6 \u201cthe \ufb01nal \ufb02ow\u201d \u2014 it\u2019s \u2032\u2033 "
    "\u02bc\uff0d 1990\u20132000\u2026 infor-\nmation, trans-\r\nport, mod-\rern, "
    "syl-\u2028lable, para\u00ad\ngraph, soft\u00adly, well-\nKnown, 1990-\n2000,"
    "\u00a0\u3000 \t\x0b\u2029\n end"
)

#: sha256 of each normaliser's output over :data:`PROBE`. Moves only by adding a row.
PINS: Mapping[str, str] = {
    "nfc-v1": "dce3e284690a08727575daa95d659af20913e2b1301533312600197f90ff89e8",
}


def _normaliser(normaliser_id: str, normalisers: Mapping[str, Normaliser]) -> Normaliser:
    try:
        return normalisers[normaliser_id]
    except KeyError:
        raise KeyError(
            f'normaliser "{normaliser_id}" is not one this package can reproduce '
            f"(known: {', '.join(sorted(normalisers))}). A quote recorded under it cannot be "
            "re-checked here; it is never checked under a different one instead."
        ) from None


def normalise(
    text: str, *, normaliser_id: str = CURRENT, normalisers: Mapping[str, Normaliser] = NORMALISERS
) -> str:
    """``text`` as normaliser ``normaliser_id`` renders it."""
    return _normaliser(normaliser_id, normalisers)(text)


def excerpt_hash(
    text: str, *, normaliser_id: str = CURRENT, normalisers: Mapping[str, Normaliser] = NORMALISERS
) -> str:
    """The ``excerptHash`` of an excerpt: ``sha256:`` over its normalised UTF-8 bytes.

    Store it with the ``normaliserId`` it was made under; the hash alone does not
    say which normaliser produced the text it covers.
    """
    normalised = normalise(text, normaliser_id=normaliser_id, normalisers=normalisers)
    return "sha256:" + hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def excerpt_matches(
    text: str, recorded_hash: str, *, normaliser_id: str,
    normalisers: Mapping[str, Normaliser] = NORMALISERS,
) -> bool:
    """Does ``text`` hash to ``recorded_hash`` under the normaliser it was recorded with?

    ``normaliser_id`` has no default on purpose: checking under the current
    normaliser rather than the recorded one is the silent invalidation this
    module exists to prevent.
    """
    return excerpt_hash(text, normaliser_id=normaliser_id, normalisers=normalisers) == recorded_hash


def drifted(
    *, normalisers: Mapping[str, Normaliser] = NORMALISERS, pins: Mapping[str, str] = PINS
) -> list[str]:
    """The ids whose behaviour no longer matches their pin, or that have no pin at all.

    Empty is the only acceptable answer. An id listed here was edited in place
    (every hash stored under it may now be wrong) or added without a pin.
    """
    return sorted(
        nid for nid, fn in normalisers.items()
        if pins.get(nid) != hashlib.sha256(fn(PROBE).encode("utf-8")).hexdigest()
    )
