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
    assert any("1 source(s) have no uri" in w for w in result["warnings"])
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
