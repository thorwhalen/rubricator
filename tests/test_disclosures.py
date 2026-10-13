"""The variance disclosure is content that says what #101 requires, and nothing it may not.

The text is read by a person deciding how far to trust a comparison, so what
it must say is tested as text: the procedure as recorded, what each step does
and does not remove, the in-session limit, the test-retest label, and the
human parallel with a checkable source for each effect. And what it must not
say: no size for any mitigation, because #96 has measured none.
"""

from __future__ import annotations

import re

import pytest

from rubricator.disclosures import DISCLOSURES_DIR, disclosures
from rubricator.schema.vocabulary import vocabulary

VARIANCE = disclosures()["variance"]
BODY = VARIANCE.body
PROSE, _, SOURCES = BODY.partition("### Sources")


def _sources() -> dict[str, str]:
    """``{number: url}`` for every entry of the Sources list."""
    return dict(re.findall(r"^(\d+)\. .*?\]\((https://[^)]+)\)", SOURCES, re.MULTILINE))


def test_it_is_versioned_with_a_changelog_entry_for_this_version() -> None:
    assert VARIANCE.version >= 1
    assert any(entry.startswith(f"{VARIANCE.version} (") for entry in VARIANCE.changelog)


def test_every_placeholder_is_declared_and_every_declared_one_is_used() -> None:
    """A renderer fills what the header names; a stray ``{x}`` would reach a reader raw."""
    used = set(re.findall(r"\{([a-z_]+)\}", BODY))
    assert used == set(VARIANCE.extra["placeholders"])


def test_it_states_the_procedure_as_recorded() -> None:
    for field in ("{scorings}", "{traversal}", "{order}", "{independence}"):
        assert field in PROSE


#: What a renderer would fill, for the procedures ADR-0018 prescribes and for none.
RENDERINGS = {
    "connector, one pass": {
        "scorings": "1", "traversal": "cell-wise", "order": "shuffled (seed 7)",
        "independence": "not applicable: one scoring per cell"},
    "deployed, adaptive": {
        "scorings": "3 to 9, varying by cell", "traversal": "cell-wise",
        "order": "shuffled, one seed per repeat", "independence": "resampled"},
    "nothing recorded": dict.fromkeys(("scorings", "traversal", "order", "independence"),
                                      "not recorded"),
}


@pytest.mark.parametrize("values", list(RENDERINGS.values()), ids=list(RENDERINGS))
def test_every_recorded_procedure_renders_as_a_true_record(values) -> None:
    """Each field is a "label: value" line, so no procedure can make a sentence false."""
    rendered = BODY.format_map(values)
    for name, value in values.items():
        assert f": {value}\n" in rendered, name
    assert "{" not in rendered


def test_it_says_what_each_step_does_not_remove() -> None:
    assert PROSE.count("It does not") >= 3


def test_in_session_isolation_is_attenuation_not_elimination() -> None:
    assert "in-session isolation" in PROSE
    assert "attenuates" in PROSE and "does not eliminate" in PROSE
    assert "transcript" in PROSE


def test_repeats_of_one_model_are_test_retest_not_agreement() -> None:
    assert "test–retest reliability" in PROSE
    assert "not agreement between independent raters" in PROSE
    assert "weakest independence rung" in PROSE


def test_every_rung_named_is_one_the_stored_ladder_spells() -> None:
    """ADR-0018's older spellings map to comparanda's; the reader sees the stored one."""
    ladder = set(vocabulary().closed_enums["independence"])
    named = set(re.findall(r"rung `([a-z-]+)`", PROSE))
    assert named and named <= ladder


@pytest.mark.parametrize("effect, marker, source", [
    ("halo", "the halo effect", "pubmed.ncbi.nlm.nih.gov/15641893"),
    ("joint versus separate evaluation", "side by side or one at a time", "Hsee1996"),
    ("sequential contrast", "a contrast effect", "sequential-contrast-effects"),
])
def test_the_human_parallel_names_each_effect_with_its_own_source(effect, marker, source) -> None:
    """Required by #101: without it the notice reads as "machines are uniquely bad"."""
    assert "Human panels show the same effects" in PROSE
    sentence = next(s for s in re.split(r"(?<=\.) ", PROSE) if marker in s)
    cited = re.findall(r"\[(\d+)\]", sentence)
    assert cited, f"the {effect} sentence cites nothing"
    assert any(source in _sources()[n] for n in cited), f"the {effect} sentence cites the wrong source"


def test_it_says_the_machine_is_not_uniquely_unreliable() -> None:
    """The sentence the human parallel exists for, held verbatim."""
    assert "This is not a claim that a machine evaluator is uniquely unreliable." in PROSE


def test_contrast_is_not_described_as_assimilation() -> None:
    """A contrast effect pushes a judgement away from the last one; #101's wording had it pulled toward."""
    sentence = next(s for s in re.split(r"(?<=\.) ", PROSE) if "contrast effect" in s)
    assert "moves away" in sentence and "toward" not in sentence


def test_every_citation_resolves_to_a_linked_source() -> None:
    cited = set(re.findall(r"\[(\d+)\]", PROSE))
    assert cited == set(_sources())


#: Words that state a size or a completeness no measurement backs (#96 has measured none).
SIZE_WORDS = r"\b(half|third|quarter|most|mostly|entirely|fully|completely|largely|substantially|" \
    r"significantly|greatly|removes|eliminates|prevents|guarantees)\b"


def test_the_mitigation_bullets_claim_no_size() -> None:
    section = PROSE.split("**What that removes, and what it does not.**")[1].split("**Why it matters.**")[0]
    assert not re.search(SIZE_WORDS, section, re.I), re.search(SIZE_WORDS, section, re.I)


def test_it_claims_no_measured_size_for_any_mitigation() -> None:
    """#96 has measured none. A guard, not a proof: a size needs a number or a percent."""
    stripped = re.sub(r"\[\d+\]|\{[a-z_]+\}", "", PROSE)
    assert not re.search(r"\d|%|per ?cent", stripped)
    assert "not yet been measured" in PROSE


def test_the_shipped_directory_holds_only_disclosures_the_loader_serves() -> None:
    assert {p.stem for p in DISCLOSURES_DIR.glob("*.md")} == set(disclosures())


def test_an_override_root_is_served_and_not_cached(tmp_path) -> None:
    (tmp_path / "variance.md").write_text("---\nid: variance\nversion: 2\n---\nours\n")
    assert disclosures(tmp_path)["variance"].body == "ours"
    (tmp_path / "variance.md").write_text("---\nid: variance\nversion: 3\n---\nedited\n")
    assert disclosures(tmp_path)["variance"].body == "edited"
