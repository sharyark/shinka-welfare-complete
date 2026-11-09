from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.assessment import selectors, services
from apps.assessment.models import Assessment, NeedFactor
from apps.core.exceptions import BusinessRuleError
from apps.registry import services as registry
from apps.registry.models import Household

from .conftest import COMFORTABLE, POOR

pytestmark = pytest.mark.django_db


def test_volunteer_submits_and_score_uses_members_and_answers(verified, submit):
    assessment = submit(verified)
    assert assessment.status == Assessment.Status.PENDING
    # Head doesn't earn (25) + kacha house (10) + no land (10)
    assert assessment.score == 45
    assert [row["code"] for row in assessment.breakdown] == ["no_earning_member", "poor_housing", "no_land"]


def test_pending_household_can_be_surveyed_but_not_approved(register, submit, president):
    assessment = submit(register())
    with pytest.raises(BusinessRuleError, match="Verify the household"):
        services.approve_assessment(assessment, president)


def test_only_one_pending_survey_per_household(verified, submit):
    submit(verified)
    with pytest.raises(BusinessRuleError) as exc:
        submit(verified)
    assert exc.value.code == "assessment_pending"


def test_invalid_answers_are_refused(verified, submit):
    with pytest.raises(ValidationError):
        submit(verified, answers={"housing": "castle"})
    assert not Assessment.all_objects.exists()


def test_volunteer_can_only_survey_households_they_can_see(verified, submit, volunteer2):
    with pytest.raises(BusinessRuleError, match="households you can see"):
        submit(verified, user=volunteer2)


def test_finance_secretary_cannot_submit(verified, submit, finance_sec):
    with pytest.raises(PermissionDenied):
        submit(verified, user=finance_sec)


def test_archived_household_cannot_be_surveyed(verified, submit, coordinator):
    registry.archive_household(verified, coordinator, "Moved away")
    with pytest.raises(BusinessRuleError, match="archived"):
        submit(Household.all_objects.get(pk=verified.pk))


def test_committee_weights_change_new_scores_only(verified, submit, society, president):
    first = submit(verified)
    services.ensure_factors(society)
    NeedFactor.all_objects.filter(society=society, code="no_earning_member").update(points=40)
    services.reject_assessment(first, president, "Redo with new weights")
    second = submit(verified)
    first.refresh_from_db()
    assert (first.score, second.score) == (45, 60)  # the old score is frozen


def test_weight_changes_are_recorded_with_who_changed_them(society, president):
    services.ensure_factors(society)
    factor = NeedFactor.all_objects.get(society=society, code="orphan")
    factor.points = 8
    factor._history_user = president
    factor.save()
    history = factor.history.order_by("history_date")
    assert [h.points for h in history] == [5, 8]
    assert history.last().history_user == president


def test_ensure_factors_is_safe_to_run_twice(society):
    services.ensure_factors(society)
    services.ensure_factors(society)
    assert NeedFactor.all_objects.filter(society=society).count() == 9


# --- Approval -----------------------------------------------------------------------


def test_president_approves_and_score_becomes_current(verified, submit, president):
    assessment = services.approve_assessment(submit(verified), president)
    assert assessment.status == Assessment.Status.APPROVED
    assert assessment.valid_until == services.add_months(timezone.localdate(), 12)
    household = selectors.with_need_score(Household.all_objects.filter(pk=verified.pk)).get()
    assert household.need_score == 45


def test_only_president_approves(verified, submit, coordinator):
    with pytest.raises(PermissionDenied):
        services.approve_assessment(submit(verified), coordinator)


def test_president_cannot_approve_own_survey(verified, submit, president):
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_assessment(submit(verified, user=president), president)
    assert exc.value.code == "maker_checker"


def test_president_cannot_approve_own_family(verified, submit, president):
    verified.users.add(president)
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_assessment(submit(verified), president)
    assert exc.value.code == "conflict_of_interest"


def test_new_approval_supersedes_the_old_one(verified, submit, president):
    old = services.approve_assessment(submit(verified), president)
    new = services.approve_assessment(submit(verified, answers=COMFORTABLE), president)
    old.refresh_from_db()
    assert old.status == Assessment.Status.SUPERSEDED
    household = selectors.with_need_score(Household.all_objects.filter(pk=verified.pk)).get()
    assert household.need_score == new.score == 25  # only "no earning member" now


def test_expired_score_no_longer_counts(verified, submit, president):
    services.approve_assessment(submit(verified), president)
    qs = Household.all_objects.filter(pk=verified.pk)
    in_a_year = timezone.localdate() + timedelta(days=370)
    assert selectors.with_need_score(qs, on=in_a_year).get().need_score is None


def test_validity_comes_from_society_settings(verified, submit, president, society):
    society.settings["assessment_valid_months"] = 6
    society.save()
    assessment = services.approve_assessment(submit(verified), president)
    assert assessment.valid_until == services.add_months(timezone.localdate(), 6)


def test_reject_needs_a_reason(verified, submit, president):
    assessment = submit(verified)
    with pytest.raises(BusinessRuleError, match="reason"):
        services.reject_assessment(assessment, president, "")
    assert services.reject_assessment(assessment, president, "Wrong house").status == "rejected"


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 11, 10), 12, date(2027, 11, 10)),
        (date(2026, 12, 15), 2, date(2027, 2, 15)),
    ],
)
def test_add_months(start, months, expected):
    assert services.add_months(start, months) == expected


# --- Who sees scores ---------------------------------------------------------------------


def test_visibility(verified, submit, volunteer, volunteer2, coordinator, finance_sec):
    submit(verified)
    assert selectors.assessments_for(volunteer).count() == 1
    assert selectors.assessments_for(volunteer2).count() == 0
    assert selectors.assessments_for(coordinator).count() == 1
    assert selectors.assessments_for(finance_sec).count() == 0
    assert selectors.can_see_scores(coordinator) and not selectors.can_see_scores(volunteer)


def test_poor_answers_fixture_is_valid():
    from apps.assessment.survey import clean_answers

    assert clean_answers(POOR) == POOR
