"""The cross-language parity test, which ADR-0004 puts in the dependent.

`comparanda` must never need to know this package exists, so its own test asserts
only that its emitted manifest matches its TypeScript constants. The
*cross-language* comparison is this file: the vendored artifact against the
sibling checkout, when one is present.

**What a green check here does and does not mean.** It means the two builds agree
on the *members* of every vocabulary and on the facts each core member carries.
It does **not** mean they agree on semantics: both can register a `lower-median`
and disagree about ties, and nothing here would notice. That needs golden
fixtures run through both implementations with byte-compared output, which is
deliberately not in v1 -- so this file is weaker protection than its passing
suggests, and says so rather than letting a green tick be over-read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rubricator.schema.vocabulary import VOCABULARY_VERSION, vocabulary

#: Where a developer checkout of the companion repository sits relative to this
#: one. Absent on CI and on anyone else's machine, which is why the test that
#: uses it skips rather than fails -- and why it is not the only test here.
_SIBLING = Path(__file__).resolve().parents[2] / "comparanda" / "schema"


def test_the_vendored_manifest_is_readable_and_complete() -> None:
    """The artifact this build actually reads, checked without any sibling.

    This is the half that runs everywhere. If the vendored file is truncated,
    stale in shape, or missing a vocabulary, the failure shows up here rather
    than as a mysterious `KeyError` inside a tool.
    """
    v = vocabulary()
    assert v.version == VOCABULARY_VERSION
    assert set(v.missing_codes) == {
        "not-applicable", "not-assessed", "deferred",
        "not-evidenced", "indeterminate", "withheld",
    }
    assert set(v.reductions) == {
        "single", "latest", "lower-median", "mode", "mean", "consensus"
    }
    assert v.scales == ("stevens",)
    for name in ("citationVerdict", "independence", "authorKind", "sourceType"):
        assert v.closed_enums[name], name


def test_the_two_terminal_codes_that_mean_opposite_things() -> None:
    """The distinction `silenceRate` keys on, asserted rather than assumed.

    `not-evidenced` and `withheld` are both terminal. A consumer computing the
    honesty metric from `terminal` alone gets a different, weaker number -- it
    counts "we know and are not saying" as though it were "nobody says".
    """
    v = vocabulary()
    assert v.facts("not-evidenced").terminal is v.facts("withheld").terminal is True
    assert v.is_informative("not-evidenced") is True
    assert v.is_informative("withheld") is False


def test_an_undeclared_code_is_never_informative() -> None:
    """The cautious direction, and the one that matters.

    An unknown blank must not inflate `silenceRate`: it is the number a careless
    agent would otherwise move for free, by emitting a code nobody defined.
    """
    v = vocabulary()
    assert v.resolve("paywalled").source == "undeclared"
    assert v.is_informative("paywalled") is False


def test_a_declared_code_carries_its_own_facts_and_never_degrades() -> None:
    """The return on facts travelling in the document rather than in a reader."""
    v = vocabulary()
    declarations = [
        {
            "id": "paywalled",
            "broader": "not-evidenced",
            "means": "The source exists but is behind a paywall we did not pass.",
            "informative": False,
        }
    ]
    r = v.resolve("paywalled", declarations)
    assert r.source == "declared"
    assert r.facts.terminal is True          # inherited from not-evidenced
    assert r.facts.informative is False      # overridden, and this is the point
    assert v.is_informative("paywalled", declarations) is False


def test_the_verdict_vocabulary_matches_what_this_package_publishes() -> None:
    """This repo's citation ladder and the companion's enum are one vocabulary.

    Three spellings were live at once, and this module's was pinned green by its
    own doctests -- so CI enforced the wrong contract across the boundary until
    someone compared them. This is that comparison, mechanised.
    """
    from rubricator.tools.citations import VERDICTS_FOUND, VERDICTS_VERBATIM

    published = set(vocabulary().closed_enums["citationVerdict"])
    assert VERDICTS_FOUND <= published
    assert VERDICTS_VERBATIM <= published
    for retired in ("verified", "partial", "not-found", "empty", "drifted"):
        assert retired not in published


@pytest.mark.skipif(not _SIBLING.exists(), reason="no sibling comparanda checkout")
def test_the_vendored_copy_matches_the_companion_repository() -> None:
    """Byte-for-byte, against the checkout that produced it.

    Skipped where there is no sibling -- CI, and anyone else's machine -- which
    is a real limitation and not a hidden one: the test above is what runs
    everywhere, and this one is what catches a vendored copy that has fallen
    behind on the machine where both repos are being changed together. That is
    exactly where the drift starts.
    """
    for name in (f"comparanda.v{VOCABULARY_VERSION}.json", f"vocabularies.v{VOCABULARY_VERSION}.json"):
        vendored = Path(__file__).resolve().parents[1] / "rubricator" / "schema" / "comparanda" / name
        upstream = _SIBLING / name
        assert json.loads(vendored.read_text()) == json.loads(upstream.read_text()), (
            f"{name} is stale. Re-copy it from the companion repository's schema/ directory; "
            "it is a build artifact there and must not be hand-edited here."
        )
