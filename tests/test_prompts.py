"""The prompt bundle, checked against the vocabulary it is written against.

Issue #109 is a rename forced on this repository by the companion repo: `pending`
became `deferred`, `unknown` became `indeterminate`, and `not-evidenced` was added
because "we searched and the sources are silent" and "the sources conflict and I
cannot discriminate" are different findings that were being collapsed into one.

The sweep of the *documents* was the easy half and is done. The half that decides
whether the distinction is real is the prompt: an agent that cannot tell silence
from conflict emits a code that means nothing, and a vocabulary the suite cannot
police is decoration.

These tests are the policing. The load-bearing one is
:func:`test_every_code_a_prompt_declares_resolves_in_the_live_vocabulary` -- the
next time a code is renamed upstream, it fails here rather than shipping a prompt
that teaches a spelling the tool layer rejects.
"""

from __future__ import annotations

import re

import pytest

from rubricator.prompts import PROMPTS_DIR, prompts
from rubricator.schema.vocabulary import vocabulary
from rubricator.tools.prompts import prompts_get, prompts_list

#: Spellings the companion repository retired in its 2026-08-21 ADR-0009
#: amendment. A prompt naming one of these as a *code* is teaching a value that
#: `measures_mark_missing` will refuse.
#:
#: Matched in backticks only, which is the per-site rule made mechanical: the
#: English words "pending" and "unknown" are fine in prose, and a blind
#: search-and-replace over this repository would have rewritten an error message
#: about "unknown traversal order".
RETIRED_SPELLINGS = {"pending": "deferred", "unknown": "indeterminate"}

ALL = prompts()
SCORING = {pid: p for pid, p in ALL.items() if p.stage == 5}


def _backticked(body: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9-]*)`", body))


def test_the_bundle_is_not_empty() -> None:
    """The directory ships in the wheel; an empty one means nothing is served.

    `pyproject.toml` has listed `rubricator/data/**` as a build artifact since
    before there was anything in it, so the packaging said "prompts ship" while
    the connector had none to hand anybody.
    """
    assert ALL, f"no prompts found in {PROMPTS_DIR}"


@pytest.mark.parametrize("prompt_id", sorted(ALL))
def test_every_code_a_prompt_declares_resolves_in_the_live_vocabulary(prompt_id: str) -> None:
    """The rename tripwire.

    Codes are *declared* in front matter rather than scraped out of the prose, so
    this check is exact rather than heuristic -- and so that a prompt author has
    to state which vocabulary they think they are writing against.
    """
    core = vocabulary().missing_codes
    for code in ALL[prompt_id].missing_codes:
        assert code in core, (
            f"{prompt_id} declares missingness code {code!r}, which is not in the "
            f"vendored vocabulary manifest (v{vocabulary().version}). Either the companion "
            "repository renamed it and this prompt was not swept, or the prompt invented one."
        )


@pytest.mark.parametrize("prompt_id", sorted(ALL))
def test_a_prompt_declares_exactly_the_core_codes_it_names(prompt_id: str) -> None:
    """Declaration and prose cannot drift apart without this failing.

    Without it the front matter becomes a thing nobody updates, and the tripwire
    above starts checking a list that no longer describes the prompt.
    """
    prompt = ALL[prompt_id]
    named = _backticked(prompt.body) & set(vocabulary().missing_codes)
    declared = set(prompt.missing_codes)
    assert named <= declared, (
        f"{prompt_id} names {sorted(named - declared)} in its body but does not declare them"
    )
    assert declared <= named, (
        f"{prompt_id} declares {sorted(declared - named)} but never mentions them"
    )


@pytest.mark.parametrize("prompt_id", sorted(ALL))
def test_no_prompt_teaches_a_retired_spelling(prompt_id: str) -> None:
    """`pending` and `unknown` are no longer codes, in either repository."""
    offending = _backticked(ALL[prompt_id].body) & set(RETIRED_SPELLINGS)
    assert not offending, (
        f"{prompt_id} names retired missingness spellings as codes: "
        + ", ".join(f"`{c}` (now `{RETIRED_SPELLINGS[c]}`)" for c in sorted(offending))
    )


@pytest.mark.parametrize("prompt_id", sorted(SCORING))
def test_every_scoring_prompt_teaches_silence_apart_from_conflict(prompt_id: str) -> None:
    """The reason `not-evidenced` was adopted at all.

    Both codes are terminal and both are informative, so nothing downstream can
    recover the distinction if the prompt does not make it. A scoring prompt that
    offers only "emit a blank" gets whichever code the model reaches for first.
    """
    prompt = ALL[prompt_id]
    for code in ("not-evidenced", "indeterminate"):
        assert code in prompt.missing_codes, f"{prompt_id} does not teach `{code}`"
    assert "silent" in prompt.body, f"{prompt_id} never says what `not-evidenced` looks like"
    assert "conflict" in prompt.body, f"{prompt_id} never says what `indeterminate` looks like"


@pytest.mark.parametrize("prompt_id", sorted(ALL))
def test_every_prompt_states_the_honesty_rule_in_its_own_words(prompt_id: str) -> None:
    """ADR-0006's three obligations, restated in every prompt rather than linked.

    A prompt cannot follow a reference. This is checked because it is the clause
    most likely to be lost to a tidy-up: a diff that "removed the boilerplate" is
    a regression here whatever else it improved.
    """
    body = ALL[prompt_id].body.lower()
    for phrase, obligation in (
        ("qualified blank", "prefer a qualified blank to a plausible guess"),
        ("span", "cite spans, not documents"),
        ("inference", "never present the agent's own inference as source material"),
    ):
        assert phrase in body, f"{prompt_id} does not state: {obligation}"


@pytest.mark.parametrize("prompt_id", sorted(ALL))
def test_every_prompt_is_versioned_and_says_why_it_changed(prompt_id: str) -> None:
    """Without a version, an evaluation number is attached to nothing (ADR-0008)."""
    prompt = ALL[prompt_id]
    assert prompt.version >= 1, f"{prompt_id} has no version"
    assert prompt.changelog, f"{prompt_id} has no changelog"
    assert any(entry.strip().startswith(str(prompt.version)) for entry in prompt.changelog), (
        f"{prompt_id} is at version {prompt.version} with no changelog entry for it"
    )


def test_the_bundle_is_servable_over_the_surface_registry() -> None:
    """Both runtimes serve the same files, which is only true if one list feeds both."""
    from rubricator.compose import build_runtime
    from rubricator.surface import bind

    verbs = bind(build_runtime(blobs={}))
    listed = {p["id"] for p in verbs["prompts_list"]()["prompts"]}
    assert listed == set(ALL)
    assert verbs["prompts_get"](prompt_id="score-cell")["body"] == ALL["score-cell"].body


def test_asking_for_a_prompt_that_is_not_there_says_what_is() -> None:
    """An error naming the alternatives is the difference between a typo and a hunt."""
    with pytest.raises(KeyError, match="score-cell"):
        prompts_get(prompt_id="score-sell")


def test_listing_omits_the_bodies() -> None:
    """A listing that costs several thousand words per call is a listing nobody makes."""
    assert all("body" not in entry for entry in prompts_list()["prompts"])


def test_a_prompts_header_is_not_served_to_the_model() -> None:
    """The changelog is provenance for maintainers, not an instruction to follow."""
    body = prompts_get(prompt_id="score-cell")["body"]
    assert "changelog:" not in body
    assert body.startswith("# ")


def test_the_root_seam_reads_a_different_directory(tmp_path) -> None:
    """The one seam this module has, exercised rather than asserted.

    A deployment overriding the wording points `root` at its own directory; if
    that does not work, "prompts are content" is a claim about the file layout
    and not about the runtime.
    """
    (tmp_path / "local.md").write_text(
        "---\nid: local\ntitle: Local\nversion: 2\n---\n# Local\n", encoding="utf-8"
    )
    override = prompts(tmp_path)
    assert set(override) == {"local"}
    assert override["local"].version == 2
    assert set(prompts()) == set(ALL), "the default bundle must be unaffected"
