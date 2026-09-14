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

#: The pair this whole file exists to keep apart.
THE_PAIR = ("not-evidenced", "indeterminate")

ALL = prompts()

#: Prompts that tell an agent which blank to emit.
#:
#: Derived from what a prompt *declares* rather than from ``stage == 5``. Keying
#: on the stage made one deleted line disable the check silently: with no prompt
#: at stage 5 the parametrize list is empty, pytest reports a skip, and the suite
#: is green while nothing is teaching the distinction at all. A prompt that names
#: either half of the pair is in scope by construction.
SCORING = {pid: p for pid, p in ALL.items() if set(p.missing_codes) & set(THE_PAIR)}


def _backticked(body: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9-]*)`", body))


def _sentences(body: str) -> list[str]:
    """Rough sentence-ish units: a table row, a list item, or a line.

    Deliberately crude. It exists so a check can ask whether a code and its gloss
    appear *together* rather than merely both somewhere in several thousand
    words, which is a check that passes on a prompt teaching the two backwards.
    """
    return [part for line in body.splitlines() for part in re.split(r"(?<=[.!?]) ", line)]


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
    """`pending` and `unknown` are no longer codes, in either repository.

    **The whole word, anywhere in the body** -- not only inside single backticks.
    An earlier version of this test matched `` `unknown` `` and nothing else, so
    a retired code survived it inside a fenced JSON example, in a table cell, in
    plain prose, and capitalised. A JSON output example is the single most likely
    place a stale code outlives a sweep, and it was the blind spot.

    The cost is that a prompt may not use "unknown" or "pending" as ordinary
    English either. That is the right trade at this size: the cost of the ban is
    one synonym, and the cost of a miss is an agent instructed to emit a value
    ``measures_mark_missing`` refuses.
    """
    body = ALL[prompt_id].body.lower()
    offending = {word for word in RETIRED_SPELLINGS if re.search(rf"\b{word}\b", body)}
    assert not offending, (
        f"{prompt_id} uses retired missingness spellings: "
        + ", ".join(f"`{c}` (now `{RETIRED_SPELLINGS[c]}`)" for c in sorted(offending))
        + ". If you meant the English word, pick another -- this check cannot tell them apart, "
        "and a stale code in a JSON example is how one survives a rename."
    )


def test_at_least_one_prompt_is_in_scope_for_the_distinction() -> None:
    """Guards the guard: an empty parametrize list is a green suite that checks nothing.

    :data:`SCORING` is derived, so it can become empty without anyone deleting a
    test. pytest reports that as a skip, which reads like a dependency being
    absent rather than like the product claim going unchecked.
    """
    assert SCORING, (
        "no prompt declares `not-evidenced` or `indeterminate`, so the checks below run "
        "over nothing. Either a prompt lost its `missing-codes`, or the codes were renamed "
        "upstream again and nothing here followed."
    )


@pytest.mark.parametrize("prompt_id", sorted(SCORING))
def test_every_scoring_prompt_teaches_silence_apart_from_conflict(prompt_id: str) -> None:
    """The reason `not-evidenced` was adopted at all.

    Both codes are terminal and both are informative, so nothing downstream can
    recover the distinction if the prompt does not make it. A prompt that offers
    only "emit a blank" gets whichever code the model reaches for first.

    **Each code must be glossed in the same breath as its own meaning.** Checking
    that "silent" and "conflict" each appear *somewhere* passed a prompt that
    taught the pair exactly backwards, which is worse than a prompt that does not
    mention them: it is confidently wrong in the direction the product's whole
    claim rests on.

    This is a smoke test and is not sufficient. Whether the distinction is
    actually followable is settled by running the prompt blind against cells
    built to confuse it -- see the changelog entry in the prompt file.
    """
    prompt = ALL[prompt_id]
    for code in THE_PAIR:
        assert code in prompt.missing_codes, (
            f"{prompt_id} declares one half of the pair and not the other: teaching "
            f"`{code}`'s counterpart without `{code}` leaves the model to guess which it means"
        )
    units = _sentences(prompt.body)
    for code, gloss in (("not-evidenced", ("silent",)), ("indeterminate", ("conflict", "settle"))):
        together = [
            u for u in units if code in u and any(word in u.lower() for word in gloss)
        ]
        assert together, (
            f"{prompt_id} never glosses `{code}` next to {' or '.join(gloss)}. Both words may "
            "be elsewhere in the file and still teach the pair backwards."
        )


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


@pytest.mark.parametrize(
    "label, text",
    [
        ("a colon in a value", "---\nid: a\ntitle: Score: one cell\nversion: 1\n---\n# B\n"),
        ("a BOM", "﻿---\nid: a\ntitle: A\nversion: 1\n---\n# B\n"),
        ("CRLF line endings", "---\r\nid: a\r\ntitle: A\r\nversion: 1\r\n---\r\n# B\r\n"),
        ("a fence inside the body", "---\nid: a\ntitle: A\nversion: 1\n---\n# B\n\n---\n\nmore\n"),
    ],
)
def test_the_header_survives_ordinary_editor_output(label: str, text: str) -> None:
    """Shapes a text editor produces on its own, which must not eat the header.

    Each of these once made the whole file read as a body with no front matter,
    which serves a model its own metadata and then fails a guard test somewhere
    else entirely -- sending the author to look for a bug in their prose.
    """
    from rubricator.prompts import _parse

    prompt = _parse(text, default_id="filename")
    assert prompt.id == "a", label
    assert prompt.version == 1, label
    assert prompt.body.startswith("# B"), label


def test_an_unindented_list_item_is_still_a_list_item() -> None:
    """YAML allows both indentations; read as a key, the item would vanish."""
    from rubricator.prompts import _parse

    flush = _parse(
        "---\nid: a\nversion: 1\nmissing-codes:\n- withheld\n- deferred\n---\n# B\n",
        default_id="x",
    )
    assert flush.missing_codes == ("withheld", "deferred")


@pytest.mark.parametrize(
    "label, text",
    [
        ("an unterminated fence", "---\nid: a\nversion: 1\n# B\n"),
        ("no front matter at all", "# B\n"),
        ("a version that is not a number", "---\nid: a\nversion: v2\n---\n# B\n"),
    ],
)
def test_a_malformed_header_cannot_reach_a_model_unnoticed(label: str, text: str) -> None:
    """The loader is permissive; the suite is strict. This is where that is checked.

    Parsing leniently means a half-written prompt is still loadable, which is what
    makes drafting one cost nothing. It is only safe because a file that failed to
    parse lands at version 0 and is then refused by
    :func:`test_every_prompt_is_versioned_and_says_why_it_changed`.
    """
    from rubricator.prompts import _parse

    assert _parse(text, default_id="x").version == 0, label


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
    # Named explicitly rather than compared against `ALL`, which IS the shipped
    # mapping: `set(prompts()) == set(ALL)` compared an object with itself and
    # could not have failed however badly the override leaked.
    assert "score-cell" in prompts() and "local" not in prompts()


def test_an_override_root_is_re_read_rather_than_cached(tmp_path) -> None:
    """Someone iterating on wording must not be served the previous version.

    The shipped bundle is a frozen build artifact and is cached; a caller-supplied
    root is the override seam and is not. Caching both made an edit invisible
    until the process restarted, which is the worst possible feedback loop for
    content whose whole point is that it can be edited without touching code.
    """
    path = tmp_path / "local.md"
    path.write_text("---\nid: local\nversion: 1\n---\n# First\n", encoding="utf-8")
    assert prompts(tmp_path)["local"].body == "# First"
    path.write_text("---\nid: local\nversion: 2\n---\n# Second\n", encoding="utf-8")
    assert prompts(tmp_path)["local"].body == "# Second"


def test_an_empty_or_missing_root_says_so_rather_than_serving_nothing(tmp_path) -> None:
    """A typo in an override path must not quietly produce a runtime with no prompts."""
    with pytest.raises(FileNotFoundError, match="no prompt files"):
        prompts(tmp_path / "does-not-exist")
    with pytest.raises(FileNotFoundError, match="no prompt files"):
        prompts(tmp_path)


def test_two_files_claiming_one_id_is_an_error(tmp_path) -> None:
    """Last-one-wins would make a recorded prompt version name two different texts."""
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("---\nid: same\nversion: 1\n---\n# X\n", encoding="utf-8")
    with pytest.raises(ValueError, match="claim id"):
        prompts(tmp_path)


def test_the_shipped_bundle_cannot_be_edited_by_a_caller() -> None:
    """It is handed out by reference, so a writable mapping is process-wide state.

    One `del` in any caller and the connector stops serving a prompt, with nothing
    in the tree to explain why.
    """
    with pytest.raises(TypeError):
        prompts()["injected"] = None  # type: ignore[index]
