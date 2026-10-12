"""Tool 14, ``aggregate_assertions`` (#97): order statistics, and no point value for a polarised cell.

The acceptance lines of #97, each checked:

- ``reduction="mean"`` raises, naming the level of measurement;
- a polarised fixture returns no point value and a ``contested`` marker;
- the mode is reported alongside the reduction;
- it is a no-op at k = 1 rather than an error.
"""

from __future__ import annotations

import pytest

from rubricator.compose import build_runtime
from rubricator.contributors import human
from rubricator.surface import bind
from rubricator.tools.aggregate import (
    _measurement_for,
    _order_statistic,
    _reduce_cell,
    _steps,
    aggregate_assertions,
    cell_shape,
)
from rubricator.tools.analysis import (
    alternatives_set,
    analysis_open,
    criteria_set,
    measures_mark_missing,
    measures_write,
)

AT = "2026-10-12T12:00:00Z"

#: alternative -> the values four raters give it on "support". alpha is the
#: issue's polarised cell (split between 2 and 4); beta has one dominant mode;
#: gamma is scored once; delta only ever gets a blank.
SCORES = {
    "alpha": [2, 4, 2, 4],
    "beta": [3, 4, 4, None],
    "gamma": [5, None, None, None],
}


@pytest.fixture()
def runtime():
    rt = build_runtime(blobs={})
    s = rt.store
    analysis_open(s, analysis_id="a", question="Which kettle?",
        allow_skip_confirmation=True, at="2026-08-22T12:00:00Z")
    alternatives_set(s, analysis_id="a", alternatives=[
        {"id": a, "label": a.title()} for a in ("alpha", "beta", "gamma", "delta")
    ])
    criteria_set(s, analysis_id="a", criteria=[{
        "id": "support", "label": "Vendor support",
        "anchors": {"1": "none", "3": "undated", "5": "dated"},
    }])
    for i, rater in enumerate(("r1", "r2", "r3", "r4")):
        cells = [
            {"alternativeId": alt, "criterionId": "support", "value": values[i],
             "justification": f"{rater} read the support page", "independence": "independent"}
            for alt, values in SCORES.items() if values[i] is not None
        ]
        measures_write(s, analysis_id="a", contributor_id=rater, author=human(rater, rater),
                       at=AT, cells=cells)
    measures_mark_missing(s, analysis_id="a", contributor_id="r1", author=human("r1", "r1"),
                          at=AT, code="deferred", note="next session",
                          criterion_ids=["support"], alternative_ids=["delta"])
    return rt


def _cells(result):
    return {c["alternativeId"]: c for c in result["cells"]}


def test_a_polarised_cell_gets_no_point_value_and_a_contested_marker(runtime) -> None:
    alpha = _cells(aggregate_assertions(runtime.store, analysis_id="a"))["alpha"]
    assert alpha["polarised"] and alpha["contested"]
    assert alpha["reduced"] is None, "the median would land on 3, a level nobody chose"
    assert alpha["modes"] == [2, 4]
    assert [(m["level"], m["count"]) for m in alpha["levels"]] == [
        (1, 0), (2, 2), (3, 0), (4, 2), (5, 0),
    ]
    assert (alpha["min"], alpha["max"], alpha["span"], alpha["n"]) == (2, 4, 2, 4)


def test_a_contested_reduction_on_request_is_still_marked(runtime) -> None:
    alpha = _cells(aggregate_assertions(
        runtime.store, analysis_id="a", allow_contested_reduction=True
    ))["alpha"]
    assert alpha["reduced"] == 2 and alpha["contested"], "lower median of 2,2,4,4"


def test_lower_median_is_a_level_a_rater_chose_and_the_mode_comes_with_it(runtime) -> None:
    beta = _cells(aggregate_assertions(runtime.store, analysis_id="a"))["beta"]
    assert beta["reduced"] == 4 and beta["modes"] == [4] and not beta["polarised"]


def test_k_equal_one_is_a_no_op(runtime) -> None:
    gamma = _cells(aggregate_assertions(runtime.store, analysis_id="a"))["gamma"]
    assert (gamma["n"], gamma["reduced"], gamma["modes"], gamma["span"]) == (1, 5, [5], 0)


def test_a_cell_with_only_a_blank_reduces_to_null(runtime) -> None:
    delta = _cells(aggregate_assertions(runtime.store, analysis_id="a"))["delta"]
    assert delta["n"] == 0 and delta["reduced"] is None and delta["modes"] == []


@pytest.mark.parametrize("reduction, expected", [("min", 3), ("max", 4), ("median", 4)])
def test_the_other_order_statistics(runtime, reduction, expected) -> None:
    beta = _cells(aggregate_assertions(runtime.store, analysis_id="a", reduction=reduction))
    assert beta["beta"]["reduced"] == expected


@pytest.mark.parametrize("mean", ["mean", "trimmed-mean"])
def test_a_mean_is_refused_naming_the_level_of_measurement(runtime, mean) -> None:
    with pytest.raises(ValueError, match="measured at the ordinal level"):
        aggregate_assertions(runtime.store, analysis_id="a", reduction=mean)


@pytest.mark.parametrize("mean", ["mean", "Mean", "geometric-mean", "average"])
def test_the_surface_refuses_a_mean_naming_the_level_of_measurement(runtime, mean) -> None:
    with pytest.raises(ValueError, match="measured at the ordinal level"):
        bind(runtime)["aggregate_assertions"](analysis_id="a", reduction=mean)


def test_a_wider_gap_unpolarises_a_one_level_split(runtime) -> None:
    alpha = _cells(aggregate_assertions(runtime.store, analysis_id="a", polarised_gap=2))["alpha"]
    assert not alpha["polarised"] and alpha["reduced"] == 2


@pytest.mark.parametrize("gap", [-1, 1.5, True])
def test_a_nonsense_gap_is_refused(runtime, gap) -> None:
    with pytest.raises(ValueError, match="polarised_gap"):
        aggregate_assertions(runtime.store, analysis_id="a", polarised_gap=gap)


def test_a_tombstoned_row_is_left_out(runtime) -> None:
    alternatives_set(runtime.store, analysis_id="a", alternatives=[
        {"id": "alpha", "label": "Alpha", "tombstoned": True},
        *({"id": a, "label": a.title()} for a in ("beta", "gamma", "delta")),
    ])
    assert "alpha" not in _cells(aggregate_assertions(runtime.store, analysis_id="a"))


def test_the_bound_verb_keeps_its_envelope(runtime) -> None:
    result = bind(runtime)["aggregate_assertions"](analysis_id="a")
    assert "1 polarised, left without a value and marked contested" in result["summary"]


# --- the shape and the statistic, below the store ---------------------------


def test_the_polarised_rule_is_comparandas() -> None:
    levels = [1, 2, 3, 4, 5]
    assert cell_shape([1, 5], levels)["polarised"]
    assert not cell_shape([1, 5, 5], levels)["polarised"], "one dominant mode"
    assert not cell_shape([2, 3], levels)["polarised"], "no empty level between"
    assert cell_shape([2, 3], levels, gap=0)["polarised"], "gap 0: any tied split"
    assert cell_shape([1, 3, 5], levels)["polarised"], "three-way tie with gaps"
    assert cell_shape([2, 2, 7], levels)["n"] == 2, "values off the levels are ignored"
    assert not cell_shape([True, 1], levels)["n"] == 2, "a bool is not a level"


def test_string_levels_keep_their_declared_order() -> None:
    shape = cell_shape(["high", "low", "high"], ["low", "medium", "high"])
    assert (shape["min"], shape["max"], shape["span"], shape["modes"]) == ("low", "high", 2, ["high"])
    assert _order_statistic(shape["ordered"], "lower-median", "ordinal") == "high"


def test_a_numeric_range_is_never_polarised_and_spans_its_distance() -> None:
    shape = cell_shape([10.0, 30.0, 10.0, 30.0], None)
    assert not shape["polarised"] and shape["span"] == 20.0


@pytest.mark.parametrize("level, expected", [
    ("ordinal", 2), ("interval", 3.0), ("ratio", 3.0), ("nominal", None),
])
def test_median_by_level_of_measurement(level, expected) -> None:
    assert _order_statistic([2, 4], "median", level) == expected


# --- found by the adversarial review of #149 --------------------------------


def _cell(values):
    return {"alternativeId": "x", "criterionId": "c", "measure": "score",
            "assertions": [{"id": f"s{i}", "value": v} for i, v in enumerate(values)]}


def test_a_nominal_cell_has_modes_and_counts_but_no_order() -> None:
    nominal = {"level": "nominal", "levels": ["red", "green", "blue"]}
    row = _reduce_cell(_cell(["red", "blue"]), nominal, reduction="lower-median",
                       allow_contested=False, gap=1)
    assert (row["reduced"], row["min"], row["max"], row["span"]) == (None, None, None, None)
    assert not row["polarised"] and not row["contested"]
    assert row["modes"] == ["red", "blue"] and row["n"] == 2


def test_each_measure_reads_its_own_measurement() -> None:
    criterion = {
        "defaultMeasurement": {"level": "ordinal", "levels": [1, 2, 3, 4, 5]},
        "measurements": {"confidence": {"level": "ratio", "range": {"min": 0, "max": 5}}},
    }
    measurement = _measurement_for(criterion, "confidence")
    row = _reduce_cell(_cell([1, 5]), measurement, reduction="median", allow_contested=False,
                       gap=1)
    assert row["reduced"] == 3.0 and not row["polarised"]
    assert _measurement_for({"defaultMeasurement": None}, "score") == {}


def test_an_ordinal_range_without_levels_still_catches_a_bimodal_cell() -> None:
    measurement = {"level": "ordinal", "range": {"min": 0, "max": 10}}
    assert _steps(measurement) == list(range(11))
    row = _reduce_cell(_cell([0, 0, 10, 10]), measurement, reduction="lower-median",
                       allow_contested=False, gap=1)
    assert row["polarised"] and row["reduced"] is None


@pytest.mark.parametrize("pair, expected", [(["a", "b"], "a"), ([False, True], False)])
def test_an_interval_median_never_averages_what_is_not_a_number(pair, expected) -> None:
    assert _order_statistic(pair, "median", "interval") == expected


def test_values_off_the_scale_are_counted_not_silently_dropped() -> None:
    shape = cell_shape([2, 7, 7], [1, 2, 3, 4, 5])
    assert shape["n"] == 1 and shape["offScale"] == 2
    assert cell_shape([2, 3], [])["n"] == 0, "declared empty levels admit nothing"
