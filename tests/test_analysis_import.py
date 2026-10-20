"""``analysis_import`` (#246): a comparanda document made elsewhere, stored as an analysis, or refused whole."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rubricator.cli import main
from rubricator.compose import build_runtime
from rubricator.merge import merge_contributions
from rubricator.tools.importing import analysis_import
from rubricator.tools.weaknesses import report_weaknesses

FOREIGN = Path(__file__).resolve().parents[1] / "docs/evaluation/audit-existing/foreign"


def _parts():
    return (json.loads((FOREIGN / "frame.json").read_text()),
            json.loads((FOREIGN / "consultant.json").read_text()))


def _plain() -> dict:
    """One merged document, as a colleague's tool would hand it over: ids not namespaced."""
    frame, contribution = _parts()
    return {**frame, "authors": contribution["authors"], "cells": contribution["cells"]}


def _store():
    return build_runtime(blobs={}).store


def test_a_plain_document_imports_and_reads_like_the_hand_placed_one() -> None:
    frame, contribution = _parts()
    by_hand = _store()
    by_hand.put_frame("seed-library", frame)
    by_hand.put_contribution("seed-library", "pat", contribution)

    store = _store()
    out = analysis_import(store, document=_plain())
    assert out["analysisId"] == "seed-library"
    assert out["contributors"] == [{"contributorId": "pat", "assertions": 24}]
    assert "not confirmed" in out["summary"]
    assert report_weaknesses(store, analysis_id="seed-library", budget=5) == report_weaknesses(
        by_hand, analysis_id="seed-library", budget=5)


def test_an_exported_analysis_round_trips_without_double_namespacing() -> None:
    frame, contribution = _parts()
    merged = merge_contributions(frame, [("pat", contribution)])
    store = _store()
    analysis_import(store, document=merged, analysis_id="again")
    assert store.read("again") == {**merged, "id": "again"}


def test_contributors_are_split_by_principal_and_personas_ride_along() -> None:
    doc = _plain()
    doc["authors"] = doc["authors"] + [
        {"id": "ben", "displayName": "Ben", "kind": "human"},
        {"id": "ben:sceptic", "displayName": "Ben as the sceptic", "kind": "human", "principalId": "ben"},
    ]
    cell = copy.deepcopy(doc["cells"][0])
    cell["assertions"] = [{**cell["assertions"][0], "id": f"b{i}", "authorId": who}
                          for i, who in enumerate(("ben", "ben:sceptic"))]
    doc["cells"].append(cell)
    store = _store()
    out = analysis_import(store, document=doc)
    assert [c["contributorId"] for c in out["contributors"]] == ["ben", "pat"]
    assert store.frame("seed-library")["authors"] == []
    ids = {a["id"] for c in store.read("seed-library")["cells"] for a in c["assertions"]}
    assert {"ben:b0", "ben:b1"} <= ids


def test_what_the_merge_refuses_is_refused_with_its_reason() -> None:
    doc = _plain()
    doc["authors"].append({"id": "cfo", "displayName": "The CFO", "kind": "human", "principalId": "pat"})
    store = _store()
    with pytest.raises(ValueError, match='would not merge: .*"cfo".*<principalId>:<name>'):
        analysis_import(store, document=doc)
    assert not store.exists("seed-library")


def test_a_document_comparanda_refuses_is_not_stored() -> None:
    doc = _plain()
    doc["alternatives"][0]["colour"] = "green"
    store = _store()
    with pytest.raises(ValueError, match="not one comparanda accepts"):
        analysis_import(store, document=doc)
    assert not store.exists("seed-library")


def test_an_existing_analysis_is_never_replaced() -> None:
    store = _store()
    analysis_import(store, document=_plain())
    with pytest.raises(ValueError, match="already here"):
        analysis_import(store, document=_plain())


def test_superseding_across_contributors_is_refused_naming_why() -> None:
    doc = _plain()
    doc["authors"].append({"id": "ben", "displayName": "Ben", "kind": "human"})
    cell = doc["cells"][0]
    cell["assertions"].append({**cell["assertions"][0], "id": "b1", "authorId": "ben"})
    cell["assertions"][0]["supersededBy"] = "b1"
    store = _store()
    with pytest.raises(ValueError, match="supersedes only their own"):
        analysis_import(store, document=doc)
    assert not store.exists("seed-library")


def test_an_author_that_cannot_name_a_file_is_refused() -> None:
    doc = _plain()
    doc["authors"] = [{**doc["authors"][0], "id": "pat smith"}]
    for cell in doc["cells"]:
        for a in cell["assertions"]:
            a["authorId"] = "pat smith"
    with pytest.raises(ValueError, match="cannot name a contributor's file"):
        analysis_import(_store(), document=doc)


def test_the_cli_imports_and_refuses_without_a_traceback(tmp_path, capsys) -> None:
    path = tmp_path / "pat.json"
    path.write_text(json.dumps(_plain()))
    root = str(tmp_path / "store")
    assert main(["import", str(path), "--analysis-id", "pats", "--root", root]) == 0
    assert 'Imported "pats"' in capsys.readouterr().out
    assert main(["import", str(path), "--analysis-id", "pats", "--root", root]) == 1
    assert "already here" in capsys.readouterr().err
    (tmp_path / "bad.json").write_text("{not json")
    assert main(["import", str(tmp_path / "bad.json"), "--root", root]) == 1
    assert "could not be read as JSON" in capsys.readouterr().err


def test_a_cell_field_the_merge_would_drop_is_refused() -> None:
    doc = _plain()
    doc["cells"][0]["readOnly"] = True
    with pytest.raises(ValueError, match="readOnly, which a contributor's cell cannot hold"):
        analysis_import(_store(), document=doc)


def test_a_cell_with_no_assertions_is_kept_in_the_frame() -> None:
    doc = _plain()
    doc["cells"].append({"alternativeId": "sprigg", "criterionId": "ease-of-use", "measure": "score",
                         "reduction": "latest", "assertions": []})
    store = _store()
    analysis_import(store, document=doc)
    kept = [c for c in store.read("seed-library")["cells"]
            if (c["alternativeId"], c["criterionId"], c["measure"]) == ("sprigg", "ease-of-use", "score")]
    assert kept and kept[0]["reduction"] == "latest"


def test_an_undeclared_author_is_refused() -> None:
    doc = _plain()
    doc["cells"][0]["assertions"][0]["authorId"] = "zed"
    with pytest.raises(ValueError, match='"zed", who is not in the document'):
        analysis_import(_store(), document=doc)


def test_records_that_collide_once_unprefixed_are_refused() -> None:
    doc = _plain()
    doc["procedures"] = [{"id": "p1", "describedAs": "x"}, {"id": "pat:p1", "describedAs": "y"}]
    first, second = doc["cells"][0]["assertions"][0], doc["cells"][1]["assertions"][0]
    first["procedureId"], second["procedureId"] = "p1", "pat:p1"
    store = _store()
    with pytest.raises(ValueError, match="two procedures records with id p1"):
        analysis_import(store, document=doc)
    assert not store.exists("seed-library")
