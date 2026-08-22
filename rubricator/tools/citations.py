"""Deterministic citation checking.

The product's whole claim is that its citations can be checked. This module is
where that claim becomes mechanical rather than aspirational -- and it is
deliberately *not* a judge.

**What this does.** Given a claimed quote and the source text it points at, it
decides whether the quote is actually there, under progressively more forgiving
notions of "there": exact, whitespace-normalised, punctuation-and-case
normalised, and finally a token-overlap score that catches a quote reassembled
from adjacent sentences.

**What this deliberately does not do.** It does not decide whether the quote
*supports the claim*. That is a judgement, it needs a model, and ADR-0003
forbids a tool from calling one. Semantic faithfulness belongs in the evaluation
suite (ADR-0008) as an explicit LLM-judge, run at test time where a key exists.
Conflating the two would put a model call in the tool layer and break the
connector runtime, where there is no key at all.

The distinction matters for a second reason: a deterministic check that a quote
exists is *evidence a reader can re-run*. A model's opinion that a quote supports
a claim is another assertion needing its own justification.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

__all__ = [
    "CitationCheck",
    "CitationVerdict",
    "VERDICTS_FOUND",
    "normalise_for_match",
    "check_citation",
    "check_citations",
]

#: The one verdict vocabulary, ADR-0014's, matching the companion repository's
#: `CitationVerdict` exactly.
#:
#: Three spellings were live at once: this module's, ADR-0014's, and comparanda's.
#: ADR-0014 is the accepted decision, so the other two came to it. What this
#: module used to publish -- ``verified`` / ``partial`` / ``not-found`` /
#: ``empty`` -- was pinned green by doctests under ``--doctest-modules``, so CI
#: was actively enforcing the wrong contract across the boundary.
#:
#: ``exact``         verbatim, after whitespace normalisation only.
#: ``normalised``    found once punctuation and case are folded.
#: ``fuzzy``         enough tokens appear in order to clear the threshold.
#: ``moved``         found, and the source has changed since it was ingested --
#:                   the anchor needs re-recording, but the quote is real.
#: ``stale``         the citation no longer resolves. **Read as "this citation
#:                   does not work any more", not strictly as "the document
#:                   changed and the quote is gone"**: this function compares a
#:                   quote against the text it is given and cannot always know
#:                   why the quote is absent. The actionable fact for a reader is
#:                   the same either way, and inventing a seventh verdict for
#:                   "absent, cause unknown" would split a distinction nobody can
#:                   act on differently.
#: ``unresolvable``  nothing could be checked -- no target, or an empty quote,
#:                   which is not a citation at all.
#: ``unchecked``     no check has run. Never returned by this function; it is the
#:                   value a stored reference carries before one does.
CitationVerdict = Literal[
    "exact", "normalised", "fuzzy", "moved", "stale", "unresolvable", "unchecked"
]

#: Verdicts under which the quoted text was actually located.
VERDICTS_FOUND: frozenset[str] = frozenset({"exact", "normalised", "fuzzy", "moved"})

#: Verdicts that count toward ADR-0008's ``quote_verbatim_rate`` release gate.
#: Both mean the quote is *there*; they differ only in how much punctuation had
#: to be forgiven, which is not a difference a reader acts on.
VERDICTS_VERBATIM: frozenset[str] = frozenset({"exact", "normalised"})

#: Fraction of the quote's tokens that must appear, in order, in the source for
#: a `fuzzy` verdict. Chosen to be forgiving enough to catch a quote whose
#: whitespace or ellipsis was mangled, and strict enough that an unrelated
#: sentence does not clear it. It is a threshold, not a finding -- the
#: evaluation suite is what calibrates it against a real corpus.
DEFAULT_PARTIAL_THRESHOLD = 0.85

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalise_for_match(text: str, *, fold_punctuation: bool = False) -> str:
    """Normalise text for comparison, reproducibly.

    Unicode NFKC first, so that a typographic quote in the source and a straight
    quote in the citation are the same character; then whitespace collapsed,
    because a quote lifted from a PDF carries line breaks the original does not.

    ``fold_punctuation`` additionally strips punctuation and case. That is the
    most forgiving comparison offered, and it is still deterministic.

    >>> normalise_for_match("The  quick\\n brown fox")
    'The quick brown fox'
    >>> normalise_for_match('He said "hello".', fold_punctuation=True)
    'he said hello'
    """
    out = unicodedata.normalize("NFKC", text)
    out = _WHITESPACE.sub(" ", out).strip()
    if fold_punctuation:
        out = _PUNCT.sub("", out).lower()
        out = _WHITESPACE.sub(" ", out).strip()
    return out


def _tokens(text: str) -> list[str]:
    return normalise_for_match(text, fold_punctuation=True).split()


def _ordered_overlap(quote_tokens: Sequence[str], source_tokens: Sequence[str]) -> float:
    """Fraction of the quote's tokens found in the source, in order.

    A greedy forward scan: each quote token is matched against the source from
    where the previous match ended. Order matters, so a bag of the right words in
    the wrong order does not score well -- which is the point, since a
    citation is a claim about a contiguous span.
    """
    if not quote_tokens:
        return 0.0
    matched = 0
    cursor = 0
    for token in quote_tokens:
        try:
            cursor = source_tokens.index(token, cursor) + 1
            matched += 1
        except ValueError:
            continue
    return matched / len(quote_tokens)


@dataclass(frozen=True)
class CitationCheck:
    """The result of checking one claimed quote against its source.

    ``status`` is the verdict; ``detail`` says which comparison produced it, so a
    reader can tell "found verbatim" from "found only after folding punctuation",
    which are different degrees of trustworthy.
    """

    status: CitationVerdict
    detail: str
    #: Character offsets of the match in the *normalised* source, when exact.
    span: tuple[int, int] | None = None
    #: Ordered-token overlap, always computed, so a caller can rank near misses.
    overlap: float = 0.0
    evidence_id: str | None = None

    @property
    def found(self) -> bool:
        """Whether the quote was located at all, at any strictness."""
        return self.status in VERDICTS_FOUND

    @property
    def verbatim(self) -> bool:
        """Whether it counts toward ADR-0008's verbatim gate."""
        return self.status in VERDICTS_VERBATIM


def check_citation(
    quote: str,
    source: str,
    *,
    evidence_id: str | None = None,
    partial_threshold: float = DEFAULT_PARTIAL_THRESHOLD,
    source_changed: bool | None = None,
) -> CitationCheck:
    """Check whether ``quote`` occurs in ``source``.

    The ladder runs strictest first and stops at the first rung that succeeds, so
    the verdict always names the *strongest* sense in which the quote was found.
    See :data:`CitationVerdict` for what each one means.

    ``source_changed`` says whether the source has changed since it was ingested
    -- normally the answer to "does the original still hash to what the rendition
    recorded". It is a **separate axis from the ladder** and is passed in rather
    than guessed, because this function is given text and cannot know its
    history. When it is true, a located quote is ``moved`` rather than a ladder
    rung: the quote is real and its anchor needs re-recording, which is a
    different instruction to a reader than "found verbatim".

    An empty quote is ``unresolvable`` rather than silently passing, because
    "cited a span containing nothing" is exactly the failure this module exists
    to catch.

    >>> check_citation("brown fox", "The quick brown fox jumps").status
    'exact'
    >>> check_citation("Brown, fox!", "The quick brown fox jumps").status
    'normalised'
    >>> check_citation("nothing like this", "The quick brown fox").status
    'stale'
    >>> check_citation("", "anything").status
    'unresolvable'
    >>> check_citation("brown fox", "The quick brown fox", source_changed=True).status
    'moved'
    """
    if not quote.strip():
        return CitationCheck(
            "unresolvable", "the quote is empty, which is not a citation", evidence_id=evidence_id
        )

    n_quote = normalise_for_match(quote)
    n_source = normalise_for_match(source)

    index = n_source.find(n_quote)
    if index != -1:
        return CitationCheck(
            "moved" if source_changed else "exact",
            "found verbatim after whitespace normalisation"
            + (", but the source has changed since it was ingested" if source_changed else ""),
            span=(index, index + len(n_quote)),
            overlap=1.0,
            evidence_id=evidence_id,
        )

    f_quote = normalise_for_match(quote, fold_punctuation=True)
    f_source = normalise_for_match(source, fold_punctuation=True)
    f_index = f_source.find(f_quote)
    if f_index != -1:
        return CitationCheck(
            "moved" if source_changed else "normalised",
            "found after folding punctuation and case"
            + (", but the source has changed since it was ingested" if source_changed else ""),
            span=(f_index, f_index + len(f_quote)),
            overlap=1.0,
            evidence_id=evidence_id,
        )

    overlap = _ordered_overlap(_tokens(quote), _tokens(source))
    if overlap >= partial_threshold:
        return CitationCheck(
            "moved" if source_changed else "fuzzy",
            f"{overlap:.0%} of the quote's tokens appear in order, but not contiguously; "
            "the span may have been reassembled from separate passages",
            overlap=overlap,
            evidence_id=evidence_id,
        )

    return CitationCheck(
        "stale",
        f"the quote is not in this text; best ordered-token overlap was {overlap:.0%}"
        + (
            ". The source has changed since it was ingested"
            if source_changed
            else ". Whether the source changed since it was ingested is not known here"
        ),
        overlap=overlap,
        evidence_id=evidence_id,
    )


@dataclass(frozen=True)
class CitationReport:
    """Aggregate over a set of checks, with the counts a reviewer actually wants."""

    checks: tuple[CitationCheck, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def exact(self) -> int:
        """Found verbatim, the strictest rung."""
        return sum(1 for c in self.checks if c.status == "exact")

    @property
    def verbatim(self) -> int:
        """Found verbatim *or* after folding punctuation and case."""
        return sum(1 for c in self.checks if c.verbatim)

    @property
    def failed(self) -> tuple[CitationCheck, ...]:
        """Checks that located nothing. These are the ones to look at."""
        return tuple(c for c in self.checks if not c.found)

    @property
    def verbatim_rate(self) -> float:
        """ADR-0008's ``quote_verbatim_rate``: the share found verbatim.

        Counts ``exact`` **and** ``normalised``, which is what ADR-0008 defines.
        It counted only the strictest rung until this was checked, so the gate
        was reading a narrower quantity than the one it is specified over --
        every quote whose punctuation had been folded scored as a miss.
        """
        return self.verbatim / self.total if self.total else 0.0

    @property
    def exact_rate(self) -> float:
        """The strictest rung alone. Reported beside the gate, never as it."""
        return self.exact / self.total if self.total else 0.0

    def summary(self) -> str:
        if not self.total:
            return "no citations to check"
        parts = [f"{self.total} citation(s)", f"{self.verbatim} verbatim"]
        weaker = self.total - self.verbatim - len(self.failed)
        if weaker:
            parts.append(f"{weaker} found only after normalisation")
        if self.failed:
            parts.append(f"{len(self.failed)} NOT FOUND")
        return ", ".join(parts)


def check_citations(
    pairs: Iterable[tuple[str, str]] | Iterable[tuple[str, str, str]],
    *,
    partial_threshold: float = DEFAULT_PARTIAL_THRESHOLD,
) -> CitationReport:
    """Check many citations.

    Accepts ``(quote, source)`` or ``(evidence_id, quote, source)`` triples. The
    result preserves input order, because a report whose order depends on a set
    or a dict would not be byte-identical across runs -- and reproducibility is
    the property this whole module is for.

    >>> r = check_citations([("brown fox", "the quick brown fox"), ("zebra", "no")])
    >>> r.total, r.verbatim, len(r.failed)
    (2, 1, 1)
    >>> r.summary()
    '2 citation(s), 1 verbatim, 1 NOT FOUND'
    """
    checks: list[CitationCheck] = []
    for item in pairs:
        if len(item) == 3:
            evidence_id, quote, source = item
        else:
            evidence_id, (quote, source) = None, item  # type: ignore[misc]
        checks.append(
            check_citation(
                quote, source, evidence_id=evidence_id, partial_threshold=partial_threshold
            )
        )
    return CitationReport(tuple(checks))
