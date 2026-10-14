"""Tool 4 (#54): ``corpus_search`` -- lexical retrieval, fixed tokenizer, fixed tie-break.

One test per "Done when" line of the issue, then the edges: identical queries
over identical corpora give byte-identical results across processes; exact score
ties are broken by ``(score, documentId, start)``; the inline-corpus behaviour is
one documented behaviour of the tool; and every way of finding nothing says why.
Fixtures are invented (comparanda ADR-0033).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from rubricator import lexical
from rubricator.clock import fixed_clock
from rubricator.compose import build_runtime
from rubricator.surface import TOOL_REFS, bind
from rubricator.surface.frozen import frozen
from rubricator.tools.search import (
    BM25_B,
    BM25_K1,
    DEFAULT_K,
    DEFAULT_WINDOW_CHARS,
    INLINE_THRESHOLD_TOKENS,
)

MOMENT = "2026-08-22T12:00:00Z"
K2 = (
    "The Brightwater K2 kettle boils one litre in under four minutes. "
    "Its element is rated at 2.2 kW and the lid is hinged. "
    "Boil-dry protection cuts the power when the kettle runs empty."
)
LUMEN = (
    "The Lumen L5 kettle has a 1.5 litre capacity and a keep-warm mode. "
    "It has no boil-dry protection; the manual says to never run it empty. "
    "The base swivels through 360 degrees."
)
SOURCES = [
    {"id": "k2", "title": "K2 spec sheet", "text": K2, "agentProduced": False},
    {"id": "l5", "title": "L5 manual", "text": LUMEN, "agentProduced": False},
]
SMALL = {"windowChars": 70, "overlapChars": 0}


def _verbs(sources=SOURCES, chunking=SMALL):
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    ids = []
    if sources:
        ids = verbs["corpus_add"](analysis_id="a1", sources=sources, chunking=chunking)["documentIds"]
    return runtime, verbs, ids


def _content(runtime, document_id: str) -> str:
    document, _ = runtime.store.read_skipping("a1")
    return next(r["content"] for r in document["renditions"] if r["id"] == document_id)


# --- the row ------------------------------------------------------------------


def test_the_row_is_implemented_and_exposed() -> None:
    assert frozen()["corpus_search"].status == "implemented"
    assert "rubricator.tools.search:corpus_search" in TOOL_REFS


def test_the_named_constants_are_the_research_s() -> None:
    """k=8 and a 600-character presentation window (findings-method row 4); BM25's usual k1 and b."""
    assert (DEFAULT_K, DEFAULT_WINDOW_CHARS) == (8, 600)
    assert (BM25_K1, BM25_B) == (1.2, 0.75)
    assert INLINE_THRESHOLD_TOKENS == 25_000


# --- what a hit is ------------------------------------------------------------


def test_a_hit_is_a_stored_span_widened_for_reading() -> None:
    runtime, verbs, (k2, _) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="element rated kW", k=1)
    (hit,) = got["hits"]
    content = _content(runtime, k2)
    assert hit["documentId"] == k2
    assert hit["text"] == content[hit["start"]:hit["end"]]
    span_start, span_end = map(int, hit["spanId"].rsplit(":", 1)[1].split("-"))
    stored = runtime.store.corpus_records("a1")[k2]["ingest"]["spans"]
    assert {"start": span_start, "end": span_end} in stored
    assert hit["start"] <= span_start and span_end <= hit["end"]
    assert "2.2 kW" in hit["text"]
    assert got["inlined"] is False


def test_the_window_is_the_presentation_and_never_cuts_the_span() -> None:
    runtime, verbs, (k2, _) = _verbs()
    narrow = verbs["corpus_search"](analysis_id="a1", query="element rated", k=1, window_chars=1)
    wide = verbs["corpus_search"](analysis_id="a1", query="element rated", k=1, window_chars=120)
    span = narrow["hits"][0]
    start, end = map(int, span["spanId"].rsplit(":", 1)[1].split("-"))
    assert (span["start"], span["end"]) == (start, end)
    assert wide["hits"][0]["end"] - wide["hits"][0]["start"] == 120
    assert wide["hits"][0]["spanId"] == span["spanId"]


def test_the_best_match_comes_first_and_k_caps_the_hits() -> None:
    _, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="swivels base 360 degrees")
    assert got["hits"][0]["documentId"] == l5
    assert "swivels" in got["hits"][0]["text"]
    assert len(verbs["corpus_search"](analysis_id="a1", query="kettle", k=1)["hits"]) == 1
    scores = [h["score"] for h in verbs["corpus_search"](analysis_id="a1", query="kettle")["hits"]]
    assert scores == sorted(scores, reverse=True)


def test_the_whole_phrase_outranks_its_words_scattered() -> None:
    """BM25 *plus* normalised substring: a span holding the query as written ranks first."""
    scattered = {"id": "x", "text": "Power cuts are rare. Protection is dry humour. Boil water.",
                 "agentProduced": False}
    _, verbs, ids = _verbs(sources=[*SOURCES, scattered], chunking={"windowChars": 400, "overlapChars": 0})
    got = verbs["corpus_search"](analysis_id="a1", query="Boil-dry protection cuts the power")
    assert "Boil-dry protection cuts the power" in got["hits"][0]["text"]


def test_case_punctuation_and_compatibility_forms_do_not_matter() -> None:
    _, verbs, _ = _verbs()
    a = verbs["corpus_search"](analysis_id="a1", query="BOIL DRY")
    b = verbs["corpus_search"](analysis_id="a1", query="boil-dry")
    assert [h["spanId"] for h in a["hits"]] == [h["spanId"] for h in b["hits"]] != []


def test_must_include_keeps_only_spans_holding_every_phrase() -> None:
    _, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="boil-dry protection",
                                 must_include=["no boil-dry"])
    assert [h["documentId"] for h in got["hits"]] == [l5]
    assert all(lexical.contains_phrase(h["text"], "no boil-dry") for h in got["hits"])


def test_document_ids_restricts_the_search() -> None:
    _, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="kettle", document_ids=[k2])
    assert {h["documentId"] for h in got["hits"]} == {k2}


def test_a_hit_in_an_agent_produced_document_says_so() -> None:
    summary = {"id": "s", "text": "A summary: the K2 kettle is the fastest to boil.", "agentProduced": True}
    _, verbs, ids = _verbs(sources=[*SOURCES, summary])
    got = verbs["corpus_search"](analysis_id="a1", query="fastest to boil")
    assert got["hits"][0]["documentId"] == ids[2]
    assert got["hits"][0]["agentProduced"] is True
    assert all(h["agentProduced"] is False for h in got["hits"] if h["documentId"] != ids[2])
    assert "agent-produced" in got["summary"]


# --- done when: byte-identical across processes -------------------------------


_IN_A_PROCESS = textwrap.dedent("""
    import json, sys
    from rubricator.clock import fixed_clock
    from rubricator.compose import build_runtime
    from rubricator.surface import bind
    sources, query = json.loads(sys.argv[1])
    verbs = bind(build_runtime(blobs={}, now=fixed_clock("2026-08-22T12:00:00Z")))
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    verbs["corpus_add"](analysis_id="a1", sources=sources,
                        chunking={"windowChars": 70, "overlapChars": 0})
    got = verbs["corpus_search"](analysis_id="a1", query=query)
    sys.stdout.write(json.dumps(got, sort_keys=False, ensure_ascii=True))
""")


def test_identical_queries_return_byte_identical_results_across_processes() -> None:
    argument = json.dumps([SOURCES, "kettle boil-dry protection empty"])
    runs = [
        subprocess.run([sys.executable, "-c", _IN_A_PROCESS, argument], capture_output=True,
                       check=True, env={"PYTHONHASHSEED": seed, "PATH": ""}).stdout
        for seed in ("0", "1", "random")
    ]
    assert runs[0] == runs[1] == runs[2]
    assert json.loads(runs[0])["hits"]


# --- done when: ties are broken by the stated key -----------------------------


def test_exact_score_ties_are_broken_by_document_id_then_start() -> None:
    """Three spans with the same text score exactly alike; the order is (documentId, start)."""
    line = "Boil-dry protection is standard. "
    twins = [
        {"id": "one", "text": line * 2, "agentProduced": False},
        # A trailing space makes a second original, so a second document, of
        # text that chunks into the same spans.
        {"id": "two", "text": line * 2 + " ", "agentProduced": False},
    ]
    _, verbs, ids = _verbs(sources=twins, chunking={"windowChars": len(line), "overlapChars": 0})
    got = verbs["corpus_search"](analysis_id="a1", query="boil-dry protection", window_chars=1)
    scores = {h["score"] for h in got["hits"]}
    assert len(scores) == 1, "the fixture must hold exact ties"
    keys = [(h["documentId"], h["start"]) for h in got["hits"]]
    assert keys == sorted(keys) and len(keys) == 4
    assert sorted(set(ids)) == sorted({d for d, _ in keys})


# --- done when: the inline-corpus behaviour is one documented behaviour --------


def test_an_empty_query_returns_the_whole_corpus_under_the_threshold() -> None:
    runtime, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="   ")
    assert got["inlined"] is True
    assert [(h["documentId"], h["start"], h["text"]) for h in got["hits"]] == [
        (d, 0, _content(runtime, d)) for d in sorted([k2, l5])]
    assert str(INLINE_THRESHOLD_TOKENS) in got["summary"].replace(",", "")


def test_an_empty_query_over_a_large_corpus_is_refused_with_the_threshold_and_the_size() -> None:
    big = {"id": "big", "text": "kettle " * (INLINE_THRESHOLD_TOKENS * 4 // 7 + 10),
           "agentProduced": False}
    runtime, verbs, _ = _verbs(sources=[big], chunking=None)
    before = dict(runtime.store.blobs)
    with pytest.raises(ValueError, match=r"25,000 tokens.*about [\d,]+ tokens.*non-empty query"):
        verbs["corpus_search"](analysis_id="a1", query="")
    assert dict(runtime.store.blobs) == before


# --- finding nothing is never silent ------------------------------------------


def test_no_match_is_an_empty_list_that_says_what_was_searched() -> None:
    _, verbs, _ = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="espresso grinder")
    assert got["hits"] == []
    assert "no span matched" in got["summary"] and "2 document(s)" in got["summary"]


def test_an_empty_corpus_is_refused_not_reported_as_no_match() -> None:
    _, verbs, _ = _verbs(sources=[])
    with pytest.raises(ValueError, match="holds no documents.*corpus_add"):
        verbs["corpus_search"](analysis_id="a1", query="kettle")


def test_an_unknown_document_id_is_refused_naming_it() -> None:
    _, verbs, (k2, _) = _verbs()
    with pytest.raises(KeyError, match="doc-nope.*" + k2):
        verbs["corpus_search"](analysis_id="a1", query="kettle", document_ids=["doc-nope"])


@pytest.mark.parametrize("query", ["?!", "--", "​"])
def test_a_query_with_nothing_to_match_is_refused(query) -> None:
    _, verbs, _ = _verbs()
    with pytest.raises(ValueError, match="no letters or digits"):
        verbs["corpus_search"](analysis_id="a1", query=query)


def test_a_must_include_phrase_with_nothing_to_match_is_refused() -> None:
    _, verbs, _ = _verbs()
    with pytest.raises(ValueError, match="must_include"):
        verbs["corpus_search"](analysis_id="a1", query="kettle", must_include=["..."])


@pytest.mark.parametrize("argument", [{"k": 0}, {"window_chars": 0}, {"k": -3}])
def test_a_non_positive_size_is_refused(argument) -> None:
    _, verbs, _ = _verbs()
    with pytest.raises(ValueError, match="at least 1"):
        verbs["corpus_search"](analysis_id="a1", query="kettle", **argument)


def test_a_document_with_no_readable_spans_is_left_out_and_named() -> None:
    runtime, verbs, (k2, l5) = _verbs()
    runtime.store.blobs[runtime.store.corpus_key("a1", k2, "ingest")] = b"{half-written"
    got = verbs["corpus_search"](analysis_id="a1", query="kettle")
    assert {h["documentId"] for h in got["hits"]} == {l5}
    assert any(k2 in w and "corpus_add" in w for w in got["warnings"])


def test_searching_writes_nothing() -> None:
    runtime, verbs, _ = _verbs()
    before = dict(runtime.store.blobs)
    verbs["corpus_search"](analysis_id="a1", query="kettle")
    verbs["corpus_search"](analysis_id="a1", query="")
    assert dict(runtime.store.blobs) == before


# --- review of #226: a search of nothing, or of part, never reads as complete ---


def _break_spans(runtime, *document_ids) -> None:
    for rid in document_ids:
        runtime.store.blobs[runtime.store.corpus_key("a1", rid, "ingest")] = b"{half-written"


def test_no_readable_spans_anywhere_is_refused_not_reported_as_no_match() -> None:
    runtime, verbs, (k2, l5) = _verbs()
    _break_spans(runtime, k2, l5)
    with pytest.raises(ValueError, match="no chosen document has readable spans"):
        verbs["corpus_search"](analysis_id="a1", query="kettle")


def test_a_frame_held_rendition_with_no_spans_is_refused_alone_and_inlined_on_request() -> None:
    runtime = build_runtime(blobs={}, now=fixed_clock(MOMENT))
    verbs = bind(runtime)
    verbs["analysis_open"](analysis_id="a1", question="which kettle?")
    frame = runtime.store.frame("a1")
    frame["renditions"] = [{"id": "r1", "originalLocator": "inline", "normaliserId": "nfc-v1",
                            "originalSha256": "sha256:" + "0" * 64, "content": K2}]
    runtime.store.put_frame("a1", frame)
    with pytest.raises(ValueError, match="r1"):
        verbs["corpus_search"](analysis_id="a1", query="kettle")
    assert verbs["corpus_search"](analysis_id="a1", query="")["hits"][0]["documentId"] == "r1"


def test_an_empty_document_ids_is_refused() -> None:
    _, verbs, _ = _verbs()
    for query in ("", "kettle"):
        with pytest.raises(ValueError, match="document_ids is empty"):
            verbs["corpus_search"](analysis_id="a1", query=query, document_ids=[])


def test_a_narrowed_inline_says_what_it_left_out() -> None:
    _, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="", must_include=["swivels"])
    assert [h["documentId"] for h in got["hits"]] == [l5]
    assert "1 of the corpus's 2 document(s) inlined" in got["summary"]
    assert "without every must_include phrase" in got["summary"]
    assert "whole corpus" not in got["summary"]
    none = verbs["corpus_search"](analysis_id="a1", query="", must_include=["espresso"])
    assert none["hits"] == [] and "0 of the corpus's 2" in none["summary"]
    by_id = verbs["corpus_search"](analysis_id="a1", query="", document_ids=[k2])
    assert "1 not in document_ids" in by_id["summary"]


def test_a_narrowed_search_and_its_warnings_are_in_the_summary() -> None:
    runtime, verbs, (k2, l5) = _verbs()
    got = verbs["corpus_search"](analysis_id="a1", query="kettle", document_ids=[l5])
    assert "in 1 document(s) of the 2 in the corpus" in got["summary"]
    _break_spans(runtime, k2)
    got = verbs["corpus_search"](analysis_id="a1", query="kettle")
    assert "1 document(s) could not be searched (see warnings)" in got["summary"]


def test_whole_number_floats_for_the_sizes_are_taken_as_integers() -> None:
    _, verbs, _ = _verbs()
    a = verbs["corpus_search"](analysis_id="a1", query="kettle", k=2.0, window_chars=100.0)
    b = verbs["corpus_search"](analysis_id="a1", query="kettle", k=2, window_chars=100)
    assert a == b


def test_the_tie_break_orders_ties_whatever_order_the_spans_arrive_in() -> None:
    """Review of #226: spans built in key order let a missing tie-break pass unnoticed."""
    from rubricator.tools.search import _ranked

    text = "Boil-dry protection is standard."
    spans = [(rid, start, start + len(text), lexical.terms(text), text)
             for rid in ("doc-b", "doc-a") for start in (40, 0)]
    ranked = _ranked("boil-dry protection", spans, chosen={"doc-a", "doc-b"}, required=[])
    assert len({r[0] for r in ranked}) == 1
    assert [(r[1], r[2]) for r in ranked] == [("doc-a", 0), ("doc-a", 40), ("doc-b", 0), ("doc-b", 40)]
