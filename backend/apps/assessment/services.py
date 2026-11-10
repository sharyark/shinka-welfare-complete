"""
Business rules for household assessments (surveys and need scores).

- Volunteers, the Program Coordinator and the President submit surveys; volunteers
  only for households they can see (the ones they registered).
- One open (pending) survey per household at a time.
- Only the President approves (architecture 5.2), never their own submission
  (maker-checker) and never for their own family (conflict of interest).
- Only verified households get an approved score. Approved scores expire after
  `assessment_valid_months` (Society.settings, default 12); then a new survey is needed.
"""

import calendar
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import require_role
from apps.core.exceptions import BusinessRuleError
from apps.registry.models import Household, Member
from apps.registry.selectors import households_for
from apps.registry.services import is_linked

from .models import Assessment, NeedFactor
from .survey import FACTORS, MemberFacts, clean_answers, compute_score

SUBMIT_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)
APPROVE_ROLES = (Role.PRESIDENT,)
DEFAULT_VALID_MONTHS = 12


# --- Weights -------------------------------------------------------------------------


def ensure_factors(society) -> None:
    """Create the committee's editable weights with the default points. Safe to run again."""
    for factor in FACTORS:
        NeedFactor.all_objects.get_or_create(
            society=society, code=factor.code, defaults={"points": factor.default_points}
        )


def factor_points(society) -> dict[str, int]:
    """The society's weights; defaults for any factor not yet in the database."""
    points = {f.code: f.default_points for f in FACTORS}
    points.update(NeedFactor.all_objects.filter(society=society).values_list("code", "points"))
    return points


# --- Submitting --------------------------------------------------------------------------


def member_facts(household: Household) -> list[MemberFacts]:
    return [
        MemberFacts(
            is_head=m.relation == Member.Relation.HEAD,
            is_female=m.gender == Member.Gender.FEMALE,
            is_earning=m.is_earning,
            is_disabled=m.is_disabled,
            is_orphan=m.is_orphan,
            is_widow=m.is_widow,
        )
        for m in Member.all_objects.filter(household=household)
    ]


def check_can_submit(*, society, user, household: Household) -> None:
    """All checks for a new survey. Also used by the admin form to show errors before saving."""
    if society is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    require_role(user, *SUBMIT_ROLES, action="submit household surveys")
    if household.society_id != society.id or not households_for(user).filter(pk=household.pk).exists():
        raise BusinessRuleError("You can only survey households you can see.")
    if household.status not in (Household.Status.PENDING, Household.Status.VERIFIED):
        raise BusinessRuleError(f"This household is {household.status}; it can't be surveyed.")
    if Assessment.all_objects.filter(household=household, status=Assessment.Status.PENDING).exists():
        raise BusinessRuleError(
            "This household already has a survey awaiting approval.", code="assessment_pending"
        )


@transaction.atomic
def submit_assessment(
    *, society, user, household: Household, answers: dict, notes: str = "", into: Assessment | None = None
) -> Assessment:
    """Score and save a new survey. `into`: an unsaved Assessment to fill (the admin passes its own)."""
    household = Household.all_objects.select_for_update().get(pk=household.pk)  # one submit at a time
    check_can_submit(society=society, user=user, household=household)
    answers = clean_answers(answers)
    score = compute_score(member_facts(household), answers, factor_points(society))
    assessment = into or Assessment()
    assessment.society = society
    assessment.created_by = user
    assessment.submitted_by = user
    assessment.household = household
    assessment.answers = answers
    assessment.score = score.total
    assessment.breakdown = score.breakdown
    assessment.notes = notes
    assessment.save()
    return assessment


# --- Deciding ------------------------------------------------------------------------------


def add_months(day: date, months: int) -> date:
    """31 Jan + 1 month = 28 (or 29) Feb, not an error."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def _locked(assessment: Assessment) -> Assessment:
    return (
        Assessment.all_objects.select_for_update(of=("self",))
        .select_related("household")
        .get(pk=assessment.pk)
    )


@transaction.atomic
def approve_assessment(assessment: Assessment, user) -> Assessment:
    require_role(user, *APPROVE_ROLES, action="approve need scores")
    assessment = _locked(assessment)
    household = assessment.household
    if assessment.status != Assessment.Status.PENDING:
        raise BusinessRuleError(f"This survey is already {assessment.status}.")
    if assessment.submitted_by_id == user.pk:
        raise BusinessRuleError(
            "You submitted this survey, so someone else must approve it.", code="maker_checker"
        )
    if is_linked(user, household):
        raise BusinessRuleError("You can't approve your own family's survey.", code="conflict_of_interest")
    if household.status != Household.Status.VERIFIED:
        raise BusinessRuleError("Verify the household before approving its need score.")

    # The newest approved survey is the one that counts; older ones are kept as history.
    Assessment.all_objects.filter(household=household, status=Assessment.Status.APPROVED).update(
        status=Assessment.Status.SUPERSEDED, updated_at=timezone.now()
    )
    months = (household.society.settings or {}).get("assessment_valid_months", DEFAULT_VALID_MONTHS)
    assessment.status = Assessment.Status.APPROVED
    assessment.approved_by = user
    assessment.approved_at = timezone.now()
    assessment.valid_until = add_months(timezone.localdate(), months)
    assessment.save()
    return assessment


@transaction.atomic
def reject_assessment(assessment: Assessment, user, reason: str) -> Assessment:
    require_role(user, *APPROVE_ROLES, action="reject surveys")
    assessment = _locked(assessment)
    if assessment.status != Assessment.Status.PENDING:
        raise BusinessRuleError("Only surveys awaiting approval can be rejected.")
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    assessment.status = Assessment.Status.REJECTED
    assessment.decision_note = reason.strip()
    assessment.save(update_fields=["status", "decision_note", "updated_at"])
    return assessment
