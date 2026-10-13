"""The ADR-0014 locator profile (#62): what can be built, what round-trips, what is never stored."""

from __future__ import annotations

import pytest

from rubricator.locators import (
    MEDIA_FRAGMENTS,
    REJECTED,
    RFC_5147,
    RFC_8118,
    TEXT_FRAGMENTS,
    FragmentSelector,
    LineRangeSelector,
    MediaTimeSelector,
    PageSelector,
    TextPositionSelector,
    TextQuoteSelector,
    from_fragment,
    profile_problems,
    selector_from_dict,
    selector_to_dict,
    text_fragment_link,
    to_fragment,
    to_stored,
)

#: Every typed selector, including the shapes that break a naive serialisation:
#: the characters that are syntax in a text directive, non-ASCII, an empty
#: prefix or suffix, a zero-length range, a label with an ampersand.
TYPED = [
    TextQuoteSelector("supported until 2029"),
    TextQuoteSelector("a-b, c & d", prefix="x-,", suffix=",-y"),
    TextQuoteSelector("100% \u00abguaranteed\u00bb", prefix="", suffix="\u2014end"),
    TextQuoteSelector("ends with a dash -", prefix="- starts with one"),
    TextPositionSelector(0, 1),
    TextPositionSelector(120, 345),
    LineRangeSelector(1, 1),
    LineRangeSelector(41, 58),
    PageSelector(0, "i"),
    PageSelector(3, "iv"),
    PageSelector(11, "A&B=3 %"),
    MediaTimeSelector(0, 0.5),
    MediaTimeSelector(1e-05, 2),
    MediaTimeSelector(5e-324, 1),
    MediaTimeSelector(12.5, 20),
    MediaTimeSelector(0.1, 1e-7 + 3),
    FragmentSelector("xywh=10,10,50,50", MEDIA_FRAGMENTS),
]


@pytest.mark.parametrize("selector", TYPED, ids=repr)
def test_every_typed_selector_round_trips_through_its_fragment(selector) -> None:
    fragment = to_fragment(selector)
    assert isinstance(fragment, FragmentSelector)
    assert from_fragment(fragment) == selector


@pytest.mark.parametrize("selector", TYPED, ids=repr)
def test_every_typed_selector_round_trips_through_its_json_shape(selector) -> None:
    assert selector_from_dict(selector_to_dict(selector)) == selector


def test_the_two_off_by_one_traps_are_where_the_standards_put_them() -> None:
    """RFC 5147 counts boundaries between lines; RFC 8118 counts pages from 1."""
    assert to_fragment(LineRangeSelector(41, 58)) == FragmentSelector("line=40,58", RFC_5147)
    assert to_fragment(PageSelector(3, "iv")) == FragmentSelector("page=4&pagelabel=iv", RFC_8118)


def test_a_page_needs_both_its_index_and_its_label() -> None:
    with pytest.raises(ValueError, match="label as well as its index"):
        PageSelector(3, "")
    with pytest.raises(TypeError):
        PageSelector(3)  # type: ignore[call-arg]


@pytest.mark.parametrize("kind", sorted(REJECTED))
def test_a_rejected_selector_type_cannot_be_constructed(kind) -> None:
    with pytest.raises(ValueError, match=f"{kind} is not in the locator profile: .*DOM"):
        selector_from_dict({"type": kind, "value": "//p"})
    import rubricator.locators as module
    assert not hasattr(module, kind), "there is no class to construct one with"


@pytest.mark.parametrize("kind", sorted(REJECTED))
def test_a_rejected_selector_type_is_refused_by_the_profile(kind) -> None:
    problems = profile_problems([{"id": "e1", "selectors": [
        {"type": "TextQuoteSelector", "exact": "q"}, {"type": kind, "value": "//p"}]}])
    assert problems and all(kind in p for p in problems)


def test_a_text_fragment_link_is_derived_from_the_stored_quote() -> None:
    quote = TextQuoteSelector("supported until 2029", prefix="is ", suffix=".")
    link = text_fragment_link(quote, url="https://example.org/s")
    assert link == "https://example.org/s#:~:text=is%20-,supported%20until%202029,-."
    assert from_fragment(FragmentSelector(link.split("#", 1)[1], TEXT_FRAGMENTS)) == quote


def test_a_text_fragment_is_never_stored_beside_the_quote() -> None:
    quote = TextQuoteSelector("supported until 2029")
    fragment = to_fragment(quote)
    problems = profile_problems([{"id": "e1", "selectors": [
        selector_to_dict(quote), selector_to_dict(fragment)]}])
    assert len(problems) == 1 and "never stored beside it" in problems[0]


@pytest.mark.parametrize("kind", ["TextPositionSelector", "LineRangeSelector"])
def test_a_position_is_never_the_sole_locator(kind) -> None:
    selector = selector_to_dict(TYPED[5] if kind == "TextPositionSelector" else TYPED[7])
    assert "never the sole locator" in profile_problems([{"id": "e1", "selectors": [selector]}])[0]
    with_quote = [selector_to_dict(TYPED[0]), selector]
    assert profile_problems([{"id": "e1", "selectors": with_quote}]) == []


def test_media_and_page_need_no_quote() -> None:
    """No text layer, nothing to quote: the profile asks for a quote only where text exists."""
    selectors = [{"type": "TimeRangeSelector", "startSeconds": 1, "endSeconds": 2},
                 {"type": "PageRegionSelector", "page": 3}]
    assert profile_problems([{"id": "e1", "selectors": selectors}]) == []


@pytest.mark.parametrize("bad", [
    lambda: TextQuoteSelector(""),
    lambda: TextQuoteSelector("   "),
    lambda: TextQuoteSelector("x", prefix=5),
    lambda: TextQuoteSelector("\ud800"),
    lambda: PageSelector(1, "\udfff"),
    lambda: TextPositionSelector(5, 4),
    lambda: TextPositionSelector(4, 4),
    lambda: MediaTimeSelector(3, 3),
    lambda: MediaTimeSelector(10 ** 400, 10 ** 401),
    lambda: FragmentSelector(1, 2),
    lambda: selector_from_dict({"type": ["TextQuoteSelector"], "exact": "x"}),
    lambda: TextPositionSelector(-1, 4),
    lambda: LineRangeSelector(0, 3),
    lambda: MediaTimeSelector(float("nan"), 1),
    lambda: MediaTimeSelector(2, 1),
    lambda: FragmentSelector("char=1,2", ""),
])
def test_a_selector_that_selects_nothing_cannot_be_built(bad) -> None:
    with pytest.raises(ValueError):
        bad()


def test_an_unknown_field_is_refused_not_dropped() -> None:
    with pytest.raises(ValueError, match="has no field rect"):
        selector_from_dict({"type": "PageSelector", "index": 1, "label": "2", "rect": {}})


@pytest.mark.parametrize("selector", [s for s in TYPED if not isinstance(s, (PageSelector, FragmentSelector))],
                         ids=repr)
def test_what_v1_can_store_is_stored_in_a_shape_the_write_path_accepts(selector) -> None:
    from rubricator.clock import fixed_clock
    from rubricator.compose import build_runtime
    from rubricator.surface import bind

    verbs = bind(build_runtime(blobs={}, now=fixed_clock("2026-10-13T12:00:00Z")))
    verbs["analysis_open"](analysis_id="a1", question="q", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "x", "label": "X"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "c", "label": "C", "anchors": [
        {"level": "1", "text": "a"}, {"level": "3", "text": "b"}, {"level": "5", "text": "c"}]}])
    selectors = [to_stored(TYPED[0]), to_stored(selector)]
    written = verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author={"id": "ana", "displayName": "A", "kind": "human"},
        cells=[{"alternativeId": "x", "criterionId": "c", "justification": "j", "value": 5,
                "evidence": [{"id": "e1", "target": "r", "sourceType": "primary", "selectors": selectors}]}])
    assert written["written"] == 1


@pytest.mark.parametrize("selector", [PageSelector(3, "iv"), FragmentSelector("xywh=1,1,2,2", MEDIA_FRAGMENTS)])
def test_what_v1_cannot_store_losslessly_is_refused_not_degraded(selector) -> None:
    with pytest.raises(ValueError, match="no lossless slot in comparanda v1"):
        to_stored(selector)


def test_a_time_fragment_is_plain_decimal_never_an_exponent() -> None:
    """Media Fragments' npt seconds have no exponent form; repr() would write one."""
    assert to_fragment(MediaTimeSelector(1e-05, 2)).value == "t=0.00001,2"
    assert "e" not in to_fragment(MediaTimeSelector(5e-324, 1)).value


@pytest.mark.parametrize("bad, says", [
    ({"type": "TextQuoteSelector", "exact": "   "}, "must not be blank"),
    ({"type": "TextPositionSelector", "start": 5, "end": 2}, "selects no characters"),
    ({"type": "TextPositionSelector", "start": 1.5, "end": 2}, "non-negative integer"),
    ({"type": "LineRangeSelector", "startLine": 0, "endLine": -3}, "non-negative integer"),
    ({"type": "TimeRangeSelector", "startSeconds": 4, "endSeconds": 1}, "selects no time"),
])
def test_the_write_path_applies_the_profile_rules_not_only_the_type_names(bad, says) -> None:
    quote = {"type": "TextQuoteSelector", "exact": "q"}
    problems = profile_problems([{"id": "e1", "selectors": [quote, bad]}])
    assert any(says in p for p in problems), problems


def test_a_blank_quote_does_not_count_as_the_quote_beside_a_position() -> None:
    problems = profile_problems([{"id": "e1", "selectors": [
        {"type": "TextQuoteSelector", "exact": ""}, {"type": "TextPositionSelector", "start": 1, "end": 4}]}])
    assert any("never the sole locator" in p for p in problems)


def test_a_line_range_keeps_its_stored_content_hash_and_passes() -> None:
    selectors = [{"type": "TextQuoteSelector", "exact": "q"},
                 {"type": "LineRangeSelector", "startLine": 2, "endLine": 3, "contentHash": "sha256:ab"}]
    assert profile_problems([{"id": "e1", "selectors": selectors}]) == []


def test_a_stored_text_fragment_is_refused_however_its_standard_is_spelt() -> None:
    fragment = {"type": "FragmentSelector", "value": ":~:text=q", "conformsTo": TEXT_FRAGMENTS.rstrip("/")}
    assert profile_problems([{"id": "e1", "selectors": [
        {"type": "TextQuoteSelector", "exact": "q"}, fragment]}])


def test_a_selector_type_that_is_not_a_string_is_not_a_crash() -> None:
    """The frozen input schema refuses it first; the profile check must not raise on it either."""
    problems = profile_problems([{"id": "e1", "selectors": [{"type": ["x"]}]}])
    assert problems == []
