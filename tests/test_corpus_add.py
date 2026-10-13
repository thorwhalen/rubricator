"""Tool 3 (#53): ``corpus_add`` -- versioned normalisation, stable ids, offsets into the full document.

What these hold, one per "Done when" line of the issue and then the edges:
the same source twice is one document with one id; every document carries the
normaliser that made it, and a normaliser changed in place is refused rather
than silently re-hashing; nothing is prepended to the text quotes resolve
against; an agent-produced document is marked, the marker survives a later
undeclared add, and rubricator's own output is marked whatever the caller says;
and a refusal adds nothing.
"""

from __future__ import annotations

import json

import pytest

from rubricator import normalise as normaliser
from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.ids import sequential_ids
from rubricator.surface import bind
from rubricator.tools.corpus import (
    CHUNKER_ID,
    DEFAULT_OVERLAP_CHARS,
    DEFAULT_WINDOW_CHARS,
    INGEST_RECORD,
    MARKER_RECORD,
    chunk_spans,
    original_sha256,
    rendition_id,
)

MOMENT = "2026-08-22T12:00:00Z"
#: Invented, like every fixture here (comparanda ADR-0033).
KETTLE = (
    "The Brightwater K2 kettle boils one litre in “under four minutes”.\n"
    "Its element is rated at 2.2 kW, and the lid is hinged.  "
)
SPEC = {"id": "k2-spec", "title": "K2 spec sheet", "text": KETTLE,
        "uri": "https://example.org/k2", "mediaType": "text/plain", "agentProduced": False}


def _verbs():
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT), new_id=sequential_ids("a"))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    return runtime, verbs


def _snapshot(runtime) -> dict[str, bytes]:
    return {k: v for k, v in runtime.store.blobs.items() if "/touched/" not in k}


# --- done when: the same source twice is one document --------------------------


def test_the_same_source_twice_has_one_id_and_one_document() -> None:
    runtime, verbs = _verbs()
    first = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    before = _snapshot(runtime)
    second = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "id": "again"}])
    assert first["documentIds"] == second["documentIds"]
    assert second["documents"][0]["added"] is False
    assert any("already in the corpus" in w for w in second["warnings"])
    assert _snapshot(runtime) == before, "a repeat add writes nothing"
    assert len(runtime.store.read("a1")["renditions"]) == 1


def test_a_repeat_inside_one_call_is_added_once() -> None:
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[SPEC, SPEC])
    assert result["documentIds"][0] == result["documentIds"][1]
    assert [d["added"] for d in result["documents"]] == [True, False]
    assert len(runtime.store.read("a1")["renditions"]) == 1
    assert result["spanCount"] == result["documents"][0]["spanCount"], "counted once"


def test_the_id_is_derived_from_the_content_and_the_normaliser() -> None:
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    expected = rendition_id(original_sha256(KETTLE), normaliser_id="nfc-v1")
    assert result["documentIds"] == [expected]
    assert rendition_id(original_sha256(KETTLE), normaliser_id="nfc-v2") != expected, (
        "the same original under a new normaliser is a new document, not a rewrite of the old"
    )
    _, other = _verbs()
    assert other["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"] == [expected], (
        "stable across analyses and processes: nothing random goes into an id"
    )


# --- done when: the normaliser is stored, and a change to it is detectable ----


def test_every_document_carries_its_normaliser_and_the_originals_hash() -> None:
    runtime, verbs = _verbs()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    (rendition,) = runtime.store.read("a1")["renditions"]
    assert rendition == {
        "id": doc_id,
        "originalLocator": "https://example.org/k2",
        "originalSha256": original_sha256(KETTLE),
        "normaliserId": "nfc-v1",
        "content": normaliser.normalise(KETTLE, normaliser_id="nfc-v1"),
        "label": "K2 spec sheet",
    }
    ingest = runtime.store.corpus_records("a1")[doc_id][INGEST_RECORD]
    assert ingest["normaliserId"] == "nfc-v1" and ingest["chunkerId"] == CHUNKER_ID
    result = runtime.schema.validate(runtime.store.read("a1"))
    assert result.ok, result.report()


def test_a_normaliser_edited_in_place_is_refused(monkeypatch) -> None:
    runtime, verbs = _verbs()
    monkeypatch.setitem(normaliser.NORMALISERS, "nfc-v1", lambda text: text.lower())
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match="nfc-v1 no longer produce"):
        verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    assert _snapshot(runtime) == before


# --- done when: nothing is prepended to the text quotes resolve against -------


def test_the_rendition_is_the_normalised_text_and_nothing_else() -> None:
    runtime, verbs = _verbs()
    verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    (rendition,) = runtime.store.read("a1")["renditions"]
    content = rendition["content"]
    assert content.startswith("The Brightwater K2 kettle"), "no title, no preamble"
    assert "K2 spec sheet" not in content
    assert normaliser.normalise(content) == content, "a quote copied out of it resolves back into it"


def test_spans_are_offsets_into_the_full_document() -> None:
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[SPEC],
                                 chunking={"windowChars": 30, "overlapChars": 0})
    doc_id = result["documentIds"][0]
    content = runtime.store.read("a1")["renditions"][0]["content"]
    spans = runtime.store.corpus_records("a1")[doc_id][INGEST_RECORD]["spans"]
    assert [(s["start"], s["end"]) for s in spans] == chunk_spans(content, window_chars=30,
                                                                   overlap_chars=0)
    assert result["spanCount"] == len(spans) > 1
    covered = set().union(*(range(s["start"], s["end"]) for s in spans))
    assert all(i in covered for i, c in enumerate(content) if c != " ")


def test_default_chunking_is_stated_and_used() -> None:
    runtime, verbs = _verbs()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    ingest = runtime.store.corpus_records("a1")[doc_id][INGEST_RECORD]
    assert ingest["chunking"] == {"windowChars": DEFAULT_WINDOW_CHARS,
                                  "overlapChars": DEFAULT_OVERLAP_CHARS}


def test_a_document_is_never_rechunked() -> None:
    runtime, verbs = _verbs()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    spans = runtime.store.corpus_records("a1")[doc_id][INGEST_RECORD]["spans"]
    again = verbs["corpus_add"](analysis_id="a1", sources=[SPEC],
                                chunking={"windowChars": 10, "overlapChars": 2})
    assert runtime.store.corpus_records("a1")[doc_id][INGEST_RECORD]["spans"] == spans
    assert any("spans were kept" in w for w in again["warnings"])


# --- done when: re-ingesting an agent-produced document sets the marker -------


def test_a_declared_agent_produced_document_is_marked() -> None:
    runtime, verbs = _verbs()
    summary = {"text": "A summary a model wrote of the K2 spec.", "agentProduced": True}
    result = verbs["corpus_add"](analysis_id="a1", sources=[summary])
    doc_id = result["documentIds"][0]
    assert result["documents"][0]["agentProduced"] is True
    marker = runtime.store.corpus_records("a1")[doc_id][MARKER_RECORD]
    assert marker["reasons"] == ["the caller declared it agent-produced"]


def test_the_marker_survives_an_undeclared_re_add() -> None:
    runtime, verbs = _verbs()
    verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])
    again = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    assert again["documents"][0]["agentProduced"] is True
    assert any("never cleared" in w for w in again["warnings"])


def test_a_later_declaration_marks_a_document_already_present() -> None:
    runtime, verbs = _verbs()
    first = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])
    assert first["documents"][0]["agentProduced"] is False
    later = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])
    assert later["documents"][0]["agentProduced"] is True
    assert MARKER_RECORD in runtime.store.corpus_records("a1")[first["documentIds"][0]]


def test_either_occurrence_in_one_call_marks() -> None:
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1",
                                 sources=[SPEC, {**SPEC, "agentProduced": True}])
    assert MARKER_RECORD in runtime.store.corpus_records("a1")[result["documentIds"][0]]


def test_a_prior_analysis_is_marked_whatever_the_caller_says() -> None:
    runtime, verbs = _verbs()
    exported = json.dumps(runtime.store.read("a1"))
    result = verbs["corpus_add"](analysis_id="a1",
                                 sources=[{"text": exported, "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is True
    assert any("although not declared" in w for w in result["warnings"])


def test_agent_produced_is_required_on_every_source() -> None:
    _, verbs = _verbs()
    with pytest.raises(ValueError, match="agentProduced"):
        verbs["corpus_add"](analysis_id="a1", sources=[{"text": KETTLE}])


# --- refusals add nothing -----------------------------------------------------


@pytest.mark.parametrize("bad, named", [
    ({"id": "blank", "text": "   \n", "agentProduced": False}, '"blank"'),
    ({"title": "Invisible", "text": "​‍", "agentProduced": False}, '"Invisible"'),
])
def test_a_source_with_no_text_is_refused_by_name_and_nothing_is_added(bad, named) -> None:
    runtime, verbs = _verbs()
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match=r"nothing was added.*sources\[1\] \(" + named):
        verbs["corpus_add"](analysis_id="a1", sources=[SPEC, bad])
    assert _snapshot(runtime) == before


@pytest.mark.parametrize("chunking", [
    {"windowChars": 0}, {"windowChars": 10, "overlapChars": 10}, {"overlapChars": -1},
])
def test_an_impossible_chunking_is_refused(chunking) -> None:
    runtime, verbs = _verbs()
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match="nothing was added"):
        verbs["corpus_add"](analysis_id="a1", sources=[SPEC], chunking=chunking)
    assert _snapshot(runtime) == before


def test_no_sources_is_refused() -> None:
    _, verbs = _verbs()
    with pytest.raises(ValueError, match="no sources"):
        verbs["corpus_add"](analysis_id="a1", sources=[])


# --- what the caller is told ----------------------------------------------------


def test_cleaning_an_inline_source_and_a_pdf_are_all_said() -> None:
    _, verbs = _verbs()
    pdf = {"text": "Extracted text from a PDF.", "mediaType": "application/pdf",
           "uri": "https://example.org/k2.pdf", "agentProduced": False}
    plain = {"text": "Already clean.", "agentProduced": False}
    result = verbs["corpus_add"](analysis_id="a1", sources=[SPEC, pdf, plain])
    assert [d["cleaned"] for d in result["documents"]] == [True, False, False]
    assert any("application/pdf" in w and "not the file" in w for w in result["warnings"])
    assert any("1 document(s) were added with no uri" in w for w in result["warnings"])
    assert "1 cleaned by nfc-v1" in result["summary"]


def test_different_originals_that_normalise_alike_are_both_kept_and_said() -> None:
    runtime, verbs = _verbs()
    curly = {"text": "It’s fast.", "agentProduced": False}
    straight = {"text": "It's fast.", "agentProduced": False}
    result = verbs["corpus_add"](analysis_id="a1", sources=[curly, straight])
    assert len(set(result["documentIds"])) == 2
    assert any("same normalised text" in w for w in result["warnings"])
    assert len(runtime.store.read("a1")["renditions"]) == 2


def test_same_calls_give_byte_identical_results_and_stores() -> None:
    def run():
        runtime, verbs = _verbs()
        out = verbs["corpus_add"](analysis_id="a1", sources=[SPEC, {**SPEC, "text": "Other."}])
        return json.dumps(out, sort_keys=True), _snapshot(runtime)

    assert run() == run()


# --- the #201 review's findings, kept failing-able ------------------------------


def test_a_variant_of_a_marked_text_is_marked_too() -> None:
    """Finding 1: a trailing newline made a second, unmarked copy of a marked summary."""
    runtime, verbs = _verbs()
    summary = "A summary a model wrote of the K2 spec."
    verbs["corpus_add"](analysis_id="a1", sources=[{"text": summary, "agentProduced": True}])
    variant = verbs["corpus_add"](analysis_id="a1",
                                  sources=[{"text": summary + "\n", "agentProduced": False}])
    assert variant["documents"][0]["added"] is True
    assert variant["documents"][0]["agentProduced"] is True
    marker = runtime.store.corpus_records("a1")[variant["documentIds"][0]][MARKER_RECORD]
    assert "which is marked" in marker["reasons"][0]


def test_a_later_declaration_in_the_same_call_marks_before_anything_is_visible() -> None:
    """Finding 2: rows for one id agreed with each other and with the summary."""
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[
        {"text": "hello world", "agentProduced": False},
        {"text": "hello world", "agentProduced": True},
    ])
    assert [d["agentProduced"] for d in result["documents"]] == [True, True]
    assert "1 marked agent-produced" in result["summary"]


@pytest.mark.parametrize("damage", [b"[]", b"null", b"not json"])
def test_a_damaged_record_neither_crashes_nor_half_adds(damage) -> None:
    """Finding 3: a record that parses to a non-object crashed after earlier writes."""
    runtime, verbs = _verbs()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    runtime.store.blobs[runtime.store.corpus_key("a1", doc_id, INGEST_RECORD)] = damage
    result = verbs["corpus_add"](analysis_id="a1", sources=[
        {"text": "Something new.", "agentProduced": False}, SPEC,
    ])
    assert result["documents"][1]["spanCount"] > 0, "the damaged spans are rebuilt"


@pytest.mark.parametrize("wrap", [
    lambda t: "﻿" + t,
    lambda t: "```json\n" + t + "\n```",
])
def test_rubricator_output_is_recognised_through_a_bom_or_a_fence(wrap) -> None:
    """Finding 6."""
    runtime, verbs = _verbs()
    exported = wrap(json.dumps(runtime.store.read("a1")))
    result = verbs["corpus_add"](analysis_id="a1", sources=[{"text": exported, "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is True


def test_a_tool_result_pasted_back_is_marked() -> None:
    """Finding 6: analysis_get's own JSON is the likeliest thing an agent re-ingests."""
    _, verbs = _verbs()
    pasted = json.dumps(verbs["analysis_get"](analysis_id="a1", view="frame"))
    result = verbs["corpus_add"](analysis_id="a1", sources=[{"text": pasted, "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is True


def test_a_uri_offered_on_a_re_add_is_said_not_to_be_recorded() -> None:
    """Finding 7."""
    _, verbs = _verbs()
    inline = {"text": KETTLE, "agentProduced": False}
    verbs["corpus_add"](analysis_id="a1", sources=[inline])
    again = verbs["corpus_add"](analysis_id="a1", sources=[{**inline, "uri": "https://example.org/k"}])
    assert any("were not recorded" in w and "example.org/k" in w for w in again["warnings"])


def test_the_no_uri_warning_counts_documents_not_sources() -> None:
    """Finding 8."""
    _, verbs = _verbs()
    inline = {"text": KETTLE, "agentProduced": False}
    result = verbs["corpus_add"](analysis_id="a1", sources=[inline, inline, inline])
    assert any(w.startswith("1 document(s) were added with no uri") for w in result["warnings"])


# --- ADR-0015 constraint 3 at the write path: secondary at best ------------------

AUTHOR = {"id": "ana", "displayName": "Ana", "kind": "human"}
ANCHORS = [{"level": "1", "text": "slow"}, {"level": "3", "text": "fair"},
           {"level": "5", "text": "fast"}]


def _scorable():
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT), new_id=sequential_ids("a"))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?", allow_skip_confirmation=True)
    verbs["frame_set"](analysis_id="a1", ambiguities=[])
    verbs["alternatives_set"](analysis_id="a1", alternatives=[{"id": "k2", "label": "K2"}])
    verbs["criteria_set"](analysis_id="a1", criteria=[{"id": "speed", "label": "Speed",
                                                       "anchors": ANCHORS}])
    return runtime, verbs


def _score(verbs, doc_id, source_type, *, by="renditionId"):
    ref = {"id": "e1", "target": doc_id if by == "target" else "doc:k2", "sourceType": source_type,
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    if by == "renditionId":
        ref["renditionId"] = doc_id
    return verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                "justification": "the sheet says under four minutes", "evidence": [ref]}],
    )


@pytest.mark.parametrize("by", ["renditionId", "target"])
def test_a_primary_reference_into_an_agent_produced_document_is_refused(by) -> None:
    runtime, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match=rf"nothing was written.*{doc_id}.*agent-produced"):
        _score(verbs, doc_id, "primary", by=by)
    assert _snapshot(runtime) == before
    assert _score(verbs, doc_id, "secondary", by=by)["summary"]


def test_a_primary_reference_into_a_fetched_document_is_written() -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    assert _score(verbs, doc_id, "primary")["summary"]


def test_marking_a_document_already_cited_as_primary_says_which_assertions() -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    _score(verbs, doc_id, "primary")
    later = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])
    assert any(w.startswith(f"{doc_id} is now marked") and "k2/speed" in w
               for w in later["warnings"])


# --- the second #201 review's findings ------------------------------------------


@pytest.mark.parametrize("target", ["rendition:{id}", "https://example.org/k2"])
def test_every_name_for_a_marked_document_is_refused_as_primary(target) -> None:
    """Finding 1: ``target`` is opaque; ``rendition:<id>`` and the uri name the document too."""
    runtime, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    ref = {"id": "e1", "target": target.format(id=doc_id), "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    with pytest.raises(ValueError, match=rf"cites {doc_id}"):
        verbs["measures_write"](
            analysis_id="a1", contributor_id="ana", author=AUTHOR,
            cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                    "justification": "the sheet says so", "evidence": [ref]}])


def test_a_uri_shared_with_an_unmarked_document_stays_citable() -> None:
    """A summary given its source's uri must not make the source uncitable."""
    _, verbs = _scorable()
    verbs["corpus_add"](analysis_id="a1", sources=[SPEC, {
        "text": "A model's summary of the K2 sheet.", "uri": SPEC["uri"], "agentProduced": True}])
    ref = {"id": "e1", "target": SPEC["uri"], "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    assert verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                "justification": "the sheet says so", "evidence": [ref]}])["summary"]


def test_content_marking_runs_both_ways_and_inside_one_call() -> None:
    """Finding 2: a variant stored before its twin was marked, and one in the same call."""
    runtime, verbs = _verbs()
    text = "A summary a model wrote of the K2 spec."
    early = verbs["corpus_add"](analysis_id="a1", sources=[{"text": text + "\n", "agentProduced": False}])
    early_id = early["documentIds"][0]
    result = verbs["corpus_add"](analysis_id="a1", sources=[
        {"text": text, "agentProduced": True}, {"text": text + "  ", "agentProduced": False}])
    assert [d["agentProduced"] for d in result["documents"]] == [True, True]
    assert MARKER_RECORD in runtime.store.corpus_records("a1")[early_id]
    assert any(w.startswith(f"{early_id}, already in the corpus, is now marked") for w in result["warnings"])


@pytest.mark.parametrize("text", [
    json.dumps({"analysisId": "VT-123", "summary": "Lab test of the K2: 3m50s to boil."}),
    json.dumps({"schemaVersion": "2", "alternatives": [], "criteria": [], "weights": {}}),
])
def test_a_source_that_merely_resembles_rubricator_output_is_not_marked(text) -> None:
    """Finding 3: a marker cannot be cleared, so a false positive is permanent."""
    _, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[{"text": text, "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is False


def test_a_tilde_fence_is_seen_through() -> None:
    """Finding 4."""
    runtime, verbs = _verbs()
    fenced = "~~~\n" + json.dumps(runtime.store.read("a1")) + "~~~"
    result = verbs["corpus_add"](analysis_id="a1", sources=[{"text": fenced, "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is True


def test_an_ingest_record_with_unusable_spans_is_rebuilt() -> None:
    """Finding 5."""
    runtime, verbs = _verbs()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[SPEC])["documentIds"][0]
    runtime.store.blobs[runtime.store.corpus_key("a1", doc_id, INGEST_RECORD)] = b'{"spans": 5}'
    result = verbs["corpus_add"](analysis_id="a1", sources=[
        {"text": "Something new.", "agentProduced": False}, SPEC])
    assert result["documents"][1]["spanCount"] > 0


def test_a_later_occurrence_contributes_its_declaration_and_its_uri() -> None:
    """Finding 6."""
    runtime, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1", sources=[
        {"text": KETTLE, "agentProduced": False},
        {"text": KETTLE, "uri": "https://example.org/k2", "agentProduced": True}])
    assert not any("although not declared" in w for w in result["warnings"])
    (rendition,) = runtime.store.read("a1")["renditions"]
    assert rendition["originalLocator"] == "https://example.org/k2"


# --- the third #201 review's findings -------------------------------------------


@pytest.mark.parametrize("field, value", [
    ("target", "rendition:{id}#120-140"), ("target", "{id}#span-0"), ("target", "doc:{id}"),
    ("target", " {id} "), ("target", "RENDITION:{ID}"), ("renditionId", "{id} "),
    ("target", "https://example.org/k2#p1"), ("target", "https://example.org/k2/"),
    ("target", "http://EXAMPLE.org/k2"),
])
def test_any_spelling_of_a_marked_documents_name_is_refused_as_primary(field, value) -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    ref = {"id": "e1", "target": "doc:k2", "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    ref[field] = value.format(id=doc_id, ID=doc_id.upper())
    with pytest.raises(ValueError, match=rf"cites {doc_id}"):
        verbs["measures_write"](
            analysis_id="a1", contributor_id="ana", author=AUTHOR,
            cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                    "justification": "the sheet says so", "evidence": [ref]}])


@pytest.mark.parametrize("record", [
    {"id": "TKT-88", "subject": "Kettle K2 recall"},
    {"id": "TKT-88", "subject": {"question": "Is the K2 recalled?"}},
])
def test_a_ticket_export_with_id_and_subject_is_not_marked(record) -> None:
    _, verbs = _verbs()
    result = verbs["corpus_add"](analysis_id="a1",
                                 sources=[{"text": json.dumps(record), "agentProduced": False}])
    assert result["documents"][0]["agentProduced"] is False


# --- the fourth #201 review's findings ------------------------------------------


def test_a_reference_into_the_unmarked_original_is_decided_by_its_rendition_id() -> None:
    """Finding 1: the original went in inline; the summary was filed under its uri."""
    _, verbs = _scorable()
    original = {"text": KETTLE, "agentProduced": False}
    summary = {"text": "A model's summary.", "uri": SPEC["uri"], "agentProduced": True}
    original_id = verbs["corpus_add"](analysis_id="a1", sources=[original, summary])["documentIds"][0]
    ref = {"id": "e1", "target": SPEC["uri"], "renditionId": original_id, "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    assert verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                "justification": "the sheet says so", "evidence": [ref]}])["summary"]


@pytest.mark.parametrize("target", [
    "https://www.example.org/k2", "https://example.org:443/k2", "https://example.org/k2?",
    "{hex}",
])
def test_more_spellings_of_a_marked_documents_name_are_refused(target) -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    ref = {"id": "e1", "target": target.format(hex=doc_id.removeprefix("doc-")),
           "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    with pytest.raises(ValueError, match=rf"cites {doc_id}"):
        verbs["measures_write"](
            analysis_id="a1", contributor_id="ana", author=AUTHOR,
            cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                    "justification": "the sheet says so", "evidence": [ref]}])


# --- the rarer spellings of #203 -------------------------------------------------


@pytest.mark.parametrize("target", [
    "example.org/k2", "www.example.org/k2/",
    "doc-{short}", "{short}", "RENDITION:DOC-{short}#span-1",
    "https://example.org/%6B2", "https://example.org/k%32", "https://example.org/K2",
    "https://user@example.org/k2", "https://user:pw@EXAMPLE.org:443/k2",
    "user:pw@example.org/k2", "//example.org/k2", "https://example.org.:443/k2",
])
def test_rarer_spellings_of_a_marked_documents_name_are_refused(target) -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    ref = {"id": "e1", "target": target.format(short=doc_id.removeprefix("doc-")[:8]),
           "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    with pytest.raises(ValueError, match=rf"cites {doc_id}"):
        verbs["measures_write"](
            analysis_id="a1", contributor_id="ana", author=AUTHOR,
            cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                    "justification": "the sheet says so", "evidence": [ref]}])


@pytest.mark.parametrize("target", [
    "doc:k2", "docs/k2.md", "https://example.org/k3", "https://other.org/k2",
    "https://example.org/k2/specs", "{seven}", "k2",
])
def test_names_that_are_not_the_marked_document_are_written(target) -> None:
    _, verbs = _scorable()
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[{**SPEC, "agentProduced": True}])[
        "documentIds"][0]
    ref = {"id": "e1", "target": target.format(seven=doc_id.removeprefix("doc-")[:7]),
           "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    assert verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                "justification": "the sheet says so", "evidence": [ref]}])["summary"]


def _primary_ref_refused_or_written(verbs, target):
    ref = {"id": "e1", "target": target, "sourceType": "primary",
           "selectors": [{"type": "TextQuoteSelector", "exact": "under four minutes"}]}
    return verbs["measures_write"](
        analysis_id="a1", contributor_id="ana", author=AUTHOR,
        cells=[{"alternativeId": "k2", "criterionId": "speed", "value": 4,
                "justification": "the sheet says so", "evidence": [ref]}])


def test_a_marked_uri_differing_only_in_case_from_an_unmarked_one_is_still_decided() -> None:
    """Review of #203: folding case must not merge two documents into one ambiguous uri."""
    _, verbs = _scorable()
    marked = {"text": "A model's summary.", "uri": "https://example.org/K2", "agentProduced": True}
    unmarked = {"text": KETTLE, "uri": "https://example.org/k2", "agentProduced": False}
    ids = verbs["corpus_add"](analysis_id="a1", sources=[marked, unmarked])["documentIds"]
    with pytest.raises(ValueError, match=rf"cites {ids[0]}"):
        _primary_ref_refused_or_written(verbs, "https://example.org/K2")
    assert _primary_ref_refused_or_written(verbs, "https://example.org/k2")["summary"]


def test_a_case_variant_of_a_lone_marked_uri_is_refused() -> None:
    _, verbs = _scorable()
    marked = {"text": "A model's summary.", "uri": "https://example.org/K2", "agentProduced": True}
    doc_id = verbs["corpus_add"](analysis_id="a1", sources=[marked])["documentIds"][0]
    with pytest.raises(ValueError, match=rf"cites {doc_id}"):
        _primary_ref_refused_or_written(verbs, "https://example.org/k2")


def test_a_hostile_target_of_hex_words_is_checked_in_linear_time() -> None:
    import time

    from rubricator.tools.corpus import cited_document

    names = {f"doc-{i:032x}": f"doc-{i:032x}" for i in range(200)}
    target = " ".join(f"{i:08x}" for i in range(10**6 // 9))
    started = time.perf_counter()
    cited_document({"target": target}, names)
    assert time.perf_counter() - started < 3


def test_a_fence_full_of_whitespace_is_linear() -> None:
    """Finding 3: the fence regex backtracked quadratically on a long whitespace run."""
    import time

    from rubricator.tools.corpus import _as_json

    text = "```" + " " * 200_000 + "x"
    started = time.perf_counter()
    assert _as_json(text) is None
    assert time.perf_counter() - started < 1.0
