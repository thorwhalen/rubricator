"""#103: the two ADR-0018 policies are configurations, and the prohibitions hold in both."""

from __future__ import annotations

import pytest

from rubricator.independence import agreement
from rubricator.tools.aggregate import REDUCTIONS
from rubricator.variance_policy import (
    CONNECTOR,
    DEPLOYED,
    POLICIES,
    VariancePolicy,
    policy_for,
    repeats_wanted,
)


def test_the_deployed_default_is_the_adr_numbers() -> None:
    assert (DEPLOYED.traversal, DEPLOYED.shuffle) == ("cell-wise", True)
    assert (DEPLOYED.repeats, DEPLOYED.early_stop_at, DEPLOYED.escalate_to) == (5, 3, 9)
    assert DEPLOYED.reduction == "lower-median" and DEPLOYED.full_stability_report


def test_the_connector_default_is_one_pass_then_the_steps() -> None:
    assert (CONNECTOR.traversal, CONNECTOR.shuffle, CONNECTOR.repeats) == ("cell-wise", True, 1)
    assert CONNECTOR.steps == ("review", "budget", "re-score", "disclose")
    assert not CONNECTOR.adaptive and not CONNECTOR.rescore_shows_prior


def test_adaptive_stopping_is_provisional_until_41() -> None:
    assert DEPLOYED.adaptive and not DEPLOYED.adaptive_stop_confirmed
    assert DEPLOYED.with_(adaptive_stop_confirmed=True).adaptive_stop_confirmed


@pytest.mark.parametrize("policy", POLICIES.values(), ids=list(POLICIES))
def test_never_a_mean_in_either_policy(policy) -> None:
    assert policy.reduction in REDUCTIONS
    for bad in ("mean", "trimmed-mean", "average"):
        with pytest.raises(ValueError, match="never a policy|not an order statistic"):
            policy.with_(reduction=bad)


@pytest.mark.parametrize("policy", POLICIES.values(), ids=list(POLICIES))
def test_no_policy_can_waive_the_polarised_refusal(policy) -> None:
    assert not hasattr(policy, "allow_contested_reduction")


def test_in_session_draws_are_never_called_inter_rater() -> None:
    authors = {"bot": {"id": "bot", "kind": "agent", "agent": {"name": "r", "model": "m"}}}
    draws = [{"authorId": "bot", "independence": "perturbed", "value": 3},
             {"authorId": "bot", "independence": "perturbed", "value": 3}]
    assert "not inter-rater agreement" in agreement(draws, authors)["label"]


def test_policy_lookup_and_bad_shapes() -> None:
    assert policy_for("deployed") is DEPLOYED and policy_for("connector") is CONNECTOR
    with pytest.raises(ValueError, match="no variance policy"):
        policy_for("laptop")
    with pytest.raises(ValueError):
        VariancePolicy(name="x", repeats=0)
    with pytest.raises(ValueError):
        VariancePolicy(name="x", repeats=3, early_stop_at=4)
    with pytest.raises(ValueError):
        VariancePolicy(name="x", repeats=5, escalate_to=5)


def test_repeats_wanted_stops_early_on_agreement_and_escalates_on_flag() -> None:
    assert repeats_wanted(DEPLOYED, []) == 5
    assert repeats_wanted(DEPLOYED, [3, 3]) == 3
    assert repeats_wanted(DEPLOYED, [3, 3, 3]) == 0
    assert repeats_wanted(DEPLOYED, [3, 3, 4]) == 2
    assert repeats_wanted(DEPLOYED, [3, 3, 4, 3, 3]) == 0
    assert repeats_wanted(DEPLOYED, [3, 3, 4, 3, 3], review_flagged=True) == 4
    assert repeats_wanted(CONNECTOR, []) == 1 and repeats_wanted(CONNECTOR, [2]) == 0
    assert repeats_wanted(CONNECTOR, [2], review_flagged=True) == 0
