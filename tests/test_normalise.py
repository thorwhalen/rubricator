"""The versioned normaliser (#62, ADR-0014): what it does, and that a change is detectable."""

from __future__ import annotations

import pytest

from rubricator.normalise import (
    CURRENT,
    NORMALISERS,
    PINS,
    drifted,
    excerpt_hash,
    excerpt_matches,
    normalise,
)


@pytest.mark.parametrize("raw, normalised", [
    ("Café", "Café"),                                  # NFC
    ("co​op­er⁠ate﻿", "cooperate"),       # zero-width strip
    ("“it’s” — …", '"it\'s" - ...'),  # typographic variants
    ("ﬁnal ﬂow ﬃx", "final flow ffix"),        # ligatures
    ("infor-\nmation", "information"),                         # line-break hyphenation
    ("infor- \r\n  mation", "information"),
    ("well-\nKnown", "well- Known"),                           # a real hyphen: capital follows
    ("1990-\n2000", "1990- 2000"),                             # a real hyphen: digit follows
    ("a \t\n  b  ", "a b"),                               # whitespace collapse
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
    assert excerpt_hash("infor-\nmation  “ok”") == excerpt_hash('information "ok"')
    assert excerpt_hash("x").startswith("sha256:")


def test_an_unknown_normaliser_is_refused_never_degraded() -> None:
    with pytest.raises(KeyError, match='"plain" is not one this package can reproduce .*nfc-v1'):
        excerpt_matches("x", excerpt_hash("x"), normaliser_id="plain")


def test_checking_names_the_normaliser_explicitly() -> None:
    """No default: checking under the current normaliser instead of the recorded one is the bug."""
    with pytest.raises(TypeError):
        excerpt_matches("x", excerpt_hash("x"))  # type: ignore[call-arg]
