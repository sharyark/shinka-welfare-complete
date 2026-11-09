"""The scoring rules on their own: no database needed."""

import pytest
from django.core.exceptions import ValidationError

from apps.assessment.survey import FACTORS, MemberFacts, clean_answers, compute_score

from .conftest import COMFORTABLE, POOR

DEFAULTS = {f.code: f.default_points for f in FACTORS}
EARNER = MemberFacts(is_head=True, is_earning=True)


def score(members, answers, points=DEFAULTS):
    return compute_score(members, answers, points)


def test_comfortable_family_scores_zero():
    assert score([EARNER], COMFORTABLE).total == 0


def test_example_widow_with_disabled_and_orphan_children():
    members = [
        MemberFacts(is_head=True, is_female=True, is_widow=True),
        MemberFacts(is_orphan=True),
        MemberFacts(is_orphan=True, is_disabled=True),
    ]
    result = score(members, POOR)
    # no earner 25 + widow 15 + 1 disabled 10 + 2 orphans 10 + kacha 10 + no land 10 = 80
    assert result.total == 80
    assert {row["code"]: row["points"] for row in result.breakdown} == {
        "no_earning_member": 25,
        "female_headed": 15,
        "disabled_member": 10,
        "orphan": 10,
        "poor_housing": 10,
        "no_land": 10,
    }


def test_support_lowers_the_score_but_never_below_zero():
    answers = {**COMFORTABLE, "receives_remittances": True, "government_job_or_business": True}
    result = score([EARNER], answers)
    assert result.total == 0
    assert sum(row["points"] for row in result.breakdown) == -40


def test_score_is_capped_at_100():
    members = [MemberFacts(is_head=True, is_female=True)] + [MemberFacts(is_disabled=True)] * 6
    assert score(members, POOR).total == 100


def test_rented_house_counts_as_poor_housing():
    codes = [row["code"] for row in score([EARNER], {**COMFORTABLE, "housing": "rented"}).breakdown]
    assert codes == ["poor_housing"]


def test_committee_weights_are_used_and_zero_turns_a_factor_off():
    members = [MemberFacts(is_head=True)]  # no earner
    assert score(members, COMFORTABLE, {**DEFAULTS, "no_earning_member": 40}).total == 40
    assert score(members, COMFORTABLE, {**DEFAULTS, "no_earning_member": 0}).breakdown == []


def test_answers_are_validated():
    assert clean_answers({**POOR, "monthly_income_pkr": 15000, "unknown": "dropped"}) == {
        **POOR,
        "monthly_income_pkr": 15000,
    }
    with pytest.raises(ValidationError) as exc:
        clean_answers({"housing": "palace", "owns_agricultural_land": "yes", "monthly_income_pkr": -5})
    errors = exc.value.message_dict
    assert set(errors) == {
        "housing",
        "owns_agricultural_land",
        "monthly_income_pkr",
        "receives_remittances",
        "government_job_or_business",
        "owns_vehicle_or_livestock",
    }
