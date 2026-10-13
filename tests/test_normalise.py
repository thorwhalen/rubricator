"""The versioned normaliser (#62, ADR-0014): what it does, and that a change is detectable."""

from __future__ import annotations

import pytest

from rubricator.normalise import (
    CURRENT,
    NORMALISERS,
    PINS,
    PROBE,
    drifted,
    excerpt_hash,
    excerpt_matches,
    normalise,
)


@pytest.mark.parametrize("raw, normalised", [
    ("Cafe\u0301", "Caf\u00e9"),                                  # NFC
    ("co\u200bop\u00ader\u2060ate\ufeff", "cooperate"),       # zero-width strip
    ("\u201cit\u2019s\u201d \u2014 \u2026", '"it\'s" - ...'),  # typographic variants
    ("\ufb01nal \ufb02ow \ufb03x", "final flow ffix"),        # ligatures
    ("infor-\nmation", "information"),                         # line-break hyphenation
    ("infor- \r\n  mation", "information"),
    ("well-\nKnown", "well- Known"),                           # a real hyphen: capital follows
    ("1990-\n2000", "1990- 2000"),                             # a real hyphen: digit follows
    ("a \t\n\u00a0 b  ", "a b"),                               # whitespace collapse
    ("infor\u00ad\nmation", "information"),                   # soft hyphen at a line break
    ("Infor\u00ad\nMation", "InforMation"),                   # ... joined even before a capital
    ("mod-\rern syl-\u2028lable para-\u2029graph", "modern syllable paragraph"),  # every break
    ("e\u200b\u0301 \ufb01\u0301", "\u00e9 f\u00ed"),         # NFC after strip and fold
    ("\uff21\u00b2\u01c6", "\uff21\u00b2\u01c6"),               # NFC, never NFKC
    ("\u02bc\uff0d", "\u02bc\uff0d"),                           # look-alikes are not folded
])
def test_each_step_of_nfc_v1(raw, normalised) -> None:
    assert normalise(raw, normaliser_id="nfc-v1") == normalised


def test_every_registered_normaliser_matches_its_pin() -> None:
    """The table is append-only: an edit in place shows up here, not in a reader's citation."""
    assert drifted() == []
    assert set(PINS) == set(NORMALISERS) and CURRENT in NORMALISERS


def test_an_edit_in_place_is_detected() -> None:
    edited = {**NORMALISERS, "nfc-v1": lambda text: NORMALISERS["nfc-v1"](text).lower()}
    assert drifted(normalisers=edited) == ["nfc-v1"]


def test_a_new_version_without_a_pin_is_detected() -> None:
    added = {**NORMALISERS, "nfc-v2": lambda text: NORMALISERS["nfc-v1"](text).casefold()}
    assert drifted(normalisers=added) == ["nfc-v2"]


def test_changing_the_version_is_detectable_on_a_stored_hash() -> None:
    """A hash recorded under one version does not verify under another that differs on it.

    The round trip: record (excerpt, hash, normaliserId); a later normaliser that
    treats the excerpt differently fails the check, and the recorded one still
    passes -- so a reader can tell "the quote changed" from "the normaliser did".
    """
    stricter = {**NORMALISERS, "nfc-v2": lambda text: NORMALISERS["nfc-v1"](text).casefold()}
    excerpt = "The Team plan is supported until 2030."
    recorded = excerpt_hash(excerpt, normaliser_id="nfc-v1")
    assert excerpt_matches(excerpt, recorded, normaliser_id="nfc-v1", normalisers=stricter)
    assert not excerpt_matches(excerpt, recorded, normaliser_id="nfc-v2", normalisers=stricter)


def test_the_hash_is_over_normalised_text() -> None:
    assert excerpt_hash("infor-\nmation  \u201cok\u201d") == excerpt_hash('information "ok"')
    assert excerpt_hash("x").startswith("sha256:")


def test_an_unknown_normaliser_is_refused_never_degraded() -> None:
    with pytest.raises(KeyError, match='"plain" is not one this package can reproduce .*nfc-v1'):
        excerpt_matches("x", excerpt_hash("x"), normaliser_id="plain")


def test_checking_names_the_normaliser_explicitly() -> None:
    """No default: checking under the current normaliser instead of the recorded one is the bug."""
    with pytest.raises(TypeError):
        excerpt_matches("x", excerpt_hash("x"))  # type: ignore[call-arg]


def test_a_lowercase_compound_broken_at_its_own_hyphen_is_joined_a_known_limit() -> None:
    """Nothing in the text says whether "well-\\nknown" was one word or two; nfc-v1 joins it.

    Pinned so that changing the heuristic is a new normaliser, not an edit, and
    so that the limit is on record rather than discovered.
    """
    assert normalise("well-\nknown e-\nmail") == "wellknown email"


@pytest.mark.parametrize("text", [
    PROBE,
    "e\u200b\u0301",
    "\ufb01\u0301\u200d\u0327",
    "a\u00ad\u0301 b",
    "x-\n\u0301y",
    " \u2028 lead",
    "Cafe\u0301-\ninfor\u00ad\r\nmation",
])
def test_normalising_twice_changes_nothing(text) -> None:
    """A quote copied out of a stored rendition must normalise to itself, or it cannot be found."""
    once = normalise(text)
    assert normalise(once) == once
