"""The fixed tokenizer and stopword list behind lexical retrieval and near-duplicate flags.

ADR-0010 names four places where a change would reorder retrieved spans without
announcing itself: the tokenizer, the stopword list, the chunker and the
tie-break. This module owns the first two, and treats them as the normaliser
treats normalisation (:mod:`rubricator.normalise`):

- **Each has an id.** :data:`TOKENIZER_ID` and :data:`STOPWORDS_ID` name what a
  score or a flag was computed under, so a changed tokenizer is a new id beside
  the old one, never an edit in place.
- **Each is pinned.** :data:`PINS` holds the sha256 of the tokenizer's output
  over :data:`PROBE` and of the sorted stopword list; :func:`drifted` names
  whichever no longer matches, and a test keeps it empty. Python's own Unicode
  tables move between releases, so the probe is what says whether the running
  interpreter still tokenizes as the pin did.

The tokenizer is deliberately plain. NFKC folds compatibility forms (``ﬁ`` to
``fi``, full-width digits to ASCII), ``casefold`` folds case more thoroughly than
``lower`` (``ß`` to ``ss``), and a token is a maximal run of letters, combining
marks and numbers, by Unicode category (``L*``, ``M*``, ``N*``). Marks are kept
inside a token because a decomposed accent NFKC cannot compose would otherwise
split a word in two; Python's regex word class excludes them. Punctuation, symbols,
underscores and whitespace separate tokens and are dropped, so
``boil-dry``, ``Boil Dry`` and ``boil_dry`` are the same two tokens. No stemming:
a stemmer is a language model in miniature, its rules are a release away from
moving, and the model calling ``corpus_search`` can issue a second query with
the other inflection.

>>> tokens("The Brightwater K2 boils 1.7 litres -- in under four minutes!")
['the', 'brightwater', 'k2', 'boils', '1', '7', 'litres', 'in', 'under', 'four', 'minutes']
>>> terms("The Brightwater K2 boils 1.7 litres -- in under four minutes!")
['brightwater', 'k2', 'boils', '1', '7', 'litres', 'under', 'four', 'minutes']
>>> folded("Auto shut-off,  BOIL-DRY protection")
'auto shut off boil dry protection'
>>> contains_phrase("Auto shut-off, boil-dry protection", "boil dry")
True
>>> contains_phrase("Auto shut-off, boil-dry protection", "oil dry")
False
"""

from __future__ import annotations

import hashlib
import unicodedata
from functools import lru_cache
from typing import Mapping

__all__ = [
    "TOKENIZER_ID",
    "STOPWORDS_ID",
    "STOPWORDS",
    "PROBE",
    "PINS",
    "tokens",
    "terms",
    "folded",
    "contains_phrase",
    "drifted",
]

#: The tokenizer's id. A change to :func:`tokens` ships as a new id.
TOKENIZER_ID = "lex-v1"

#: The stopword list's id. Adding or removing a word is a new id: it changes
#: which spans score at all, which ADR-0010 calls a release-note event.
STOPWORDS_ID = "stop-en-v1"

#: Function words that carry no retrieval signal in English. Short on purpose:
#: a long list starts dropping words that *do* discriminate in a comparison
#: ("not", "no", "only", "without", "more", "less", "most", "least" are kept,
#: because a criterion often turns on exactly those).
STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he", "her",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "may", "might", "of",
    "on", "or", "our", "she", "should", "so", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "you", "your",
})

#: A string that exercises every step: compatibility forms, case folding beyond
#: ASCII, punctuation and underscores as separators, digits, accented letters.
PROBE = (
    "The ﬁrst König's STRASSE — Straße; boil_dry/boil-dry "
    "１２V café CAFÉ 3.5kW ‘quoted’ İstanbul"
)

#: The Unicode general-category initials a token is made of: letters, marks, numbers.
_TOKEN_CATEGORIES = frozenset("LMN")


def tokens(text: str) -> list[str]:
    """``lex-v1``: NFKC, then ``casefold``, then every maximal run of letters, marks and numbers.

    Returns a fresh list each call; the work is cached per text, because a
    search tokenizes every span of the corpus and a session searches it often.
    """
    return list(_tokens(text))


@lru_cache(maxsize=8192)
def _tokens(text: str) -> tuple[str, ...]:
    out: list[str] = []
    current: list[str] = []
    for ch in unicodedata.normalize("NFKC", text).casefold():
        if unicodedata.category(ch)[0] in _TOKEN_CATEGORIES:
            current.append(ch)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return tuple(out)


def terms(text: str) -> list[str]:
    """:func:`tokens` without the :data:`STOPWORDS`: what BM25 scores and similarity compares."""
    return [t for t in tokens(text) if t not in STOPWORDS]


def folded(text: str) -> str:
    """The tokens joined by single spaces: the form a phrase is matched in.

    Stopwords are kept, since a phrase is matched as written ("the lid is
    hinged"), and only case, compatibility forms and punctuation are folded away.
    """
    return " ".join(tokens(text))


def contains_phrase(text: str, phrase: str) -> bool:
    """Whether ``phrase``'s tokens occur in ``text``'s, consecutively and on token boundaries.

    The "normalised substring" match of ADR-0010. On token boundaries, so ``"oil"``
    does not match inside ``"boil"``; a phrase with no tokens matches nothing.
    """
    needle = folded(phrase)
    return bool(needle) and f" {needle} " in f" {folded(text)} "


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprints() -> dict[str, str]:
    return {
        TOKENIZER_ID: _digest("\n".join(tokens(PROBE))),
        STOPWORDS_ID: _digest("\n".join(sorted(STOPWORDS))),
    }


#: The sha256 of :func:`tokens` over :data:`PROBE`, and of the sorted stopword
#: list. Recorded, never recomputed at import: a pin computed from the code it
#: pins would hold whatever the code does.
PINS: Mapping[str, str] = {
    "lex-v1": "d848492a57b2f5e7b3fbe130042b9c430cde11f69ff2c5d0b6322e597d15efa9",
    "stop-en-v1": "6030c6c6e54fbf5dfe5a552aa55cb04b635868f9b8c26a658bfd1d3209c97d20",
}


def drifted() -> list[str]:
    """The ids whose behaviour no longer matches :data:`PINS`; empty when nothing moved.

    >>> drifted()
    []
    """
    live = _fingerprints()
    return sorted(k for k, pin in PINS.items() if live.get(k) != pin)
