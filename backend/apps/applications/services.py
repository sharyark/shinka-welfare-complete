"""
Business rules for applications (architecture 10.2 and 5.2).

- Who submits: the family itself (a Beneficiary account linked to the household),
  a volunteer for a household they can see, or the office (Coordinator, President).
  Only verified households, only programs that take applications, one open
  application per family/person per program.
- Home visit: a volunteer or the Coordinator, not the person who submitted it, and
  not for their own family. Urgent cases (e.g. burial) may skip the visit.
- Decision: only the President, never on an application they submitted or for
  their own family. Approving enrolls the household (need-score cutoff applies)
  and creates a CONFIRMED entitlement for the approved amount and date.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role, require_role
from apps.benefits import services as benefits
from apps.benefits.models import Enrollment
from apps.core.exceptions import BusinessRuleError
from apps.programs.models import Program
from apps.registry.models import Household, Member
from apps.registry.selectors import households_for
from apps.registry.services import is_linked

from .models import Application

S = Application.Status
OPEN = (S.SUBMITTED, S.UNDER_REVIEW)
OFFICE_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR)
VISIT_ROLES = (Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)
DECIDE_ROLES = (Role.PRESIDENT,)


def _channel(user, household) -> str:
    if has_any_role(user, *OFFICE_ROLES):
        return Application.Channel.OFFICE
    if has_any_role(user, Role.VOLUNTEER):
        return Application.Channel.VOLUNTEER
    return Application.Channel.APP


def check_can_submit(*, user, household: Household, program: Program, member: Member | None = None) -> None:
    """All checks for a new application. Also used by the admin form."""
    if user.society_id is None or household.society_id != user.society_id:
        raise BusinessRuleError("You can only apply for households of your society.")
    own_family = household.users.filter(pk=user.pk).exists()
    allowed = (
        has_any_role(user, *OFFICE_ROLES)
        or (has_any_role(user, Role.VOLUNTEER) and households_for(user).filter(pk=household.pk).exists())
        or (has_any_role(user, Role.BENEFICIARY) and own_family)
    )
    if not allowed:
        raise BusinessRuleError("You can't apply for this household.", code="not_allowed")
    if household.status != Household.Status.VERIFIED:
        raise BusinessRuleError("The household must be verified before applying.")
    if program.society_id != household.society_id or not program.is_active:
        raise BusinessRuleError("Choose an active program of this society.")
    if not program.requires_application:
        raise BusinessRuleError("This program doesn't take applications; benefits are planned per cycle.")
    if program.target == Program.Target.MEMBER and member is None:
        raise BusinessRuleError("Choose who the help is for.")
    if member is not None and member.household_id != household.pk:
        raise BusinessRuleError("That person is not in this household.")
    open_ones = Application.all_objects.filter(program=program, status__in=OPEN)
    open_ones = (
        open_ones.filter(member=member) if member else open_ones.filter(household=household, member=None)
    )
    if open_ones.exists():
        raise BusinessRuleError("There is already an open application for this.", code="already_open")


@transaction.atomic
def submit_application(
    *,
    user,
    household: Household,
    program: Program,
    description: str,
    into: Application | None = None,
    **fields,
) -> Application:
    household = Household.all_objects.select_for_update().get(pk=household.pk)
    check_can_submit(user=user, household=household, program=program, member=fields.get("member"))
    if not (description or "").strip():
        raise BusinessRuleError("Describe what is needed.")
    application = into or Application()
    values = {
        "society_id": household.society_id,
        "created_by": user,
        "submitted_by": user,
        "household": household,
        "program": program,
        "description": description.strip(),
        "channel": _channel(user, household),
        "status": S.SUBMITTED,
        **fields,
    }
    for name, value in values.items():
        setattr(application, name, value)
    application.save()
    return application


def _locked(application: Application) -> Application:
    return (
        Application.all_objects.select_for_update(of=("self",))
        .select_related("household", "program")
        .get(pk=application.pk)
    )


@transaction.atomic
def record_visit(application: Application, user, report: str) -> Application:
    require_role(user, *VISIT_ROLES, action="record home visits")
    application = _locked(application)
    if application.status != S.SUBMITTED:
        raise BusinessRuleError("Only newly submitted applications need a visit.")
    if application.submitted_by_id == user.pk:
        raise BusinessRuleError(
            "Someone other than the person who submitted it must visit.", code="maker_checker"
        )
    if is_linked(user, application.household):
        raise BusinessRuleError(
            "You can't verify your own family's application.", code="conflict_of_interest"
        )
    if not (report or "").strip():
        raise BusinessRuleError("Write what you saw on the visit.")
    application.status = S.UNDER_REVIEW
    application.visited_by = user
    application.visited_at = timezone.now()
    application.visit_report = report.strip()
    application.save()
    return application


def _check_decider(application: Application, user) -> None:
    require_role(user, *DECIDE_ROLES, action="decide applications")
    if application.status not in OPEN:
        raise BusinessRuleError(f"This application is already {application.get_status_display().lower()}.")
    if application.status == S.SUBMITTED and application.urgency != Application.Urgency.URGENT:
        raise BusinessRuleError("A volunteer must visit the family first.", code="visit_needed")
    if application.submitted_by_id == user.pk:
        raise BusinessRuleError(
            "You submitted this application, so you can't decide it.", code="maker_checker"
        )
    if is_linked(user, application.household):
        raise BusinessRuleError(
            "You can't decide your own family's application.", code="conflict_of_interest"
        )


@transaction.atomic
def approve_application(
    application: Application,
    user,
    *,
    amount: Decimal | None = None,
    due_date: date | None = None,
    note: str = "",
) -> Application:
    """Approve, enroll the household and promise the help (a confirmed entitlement)."""
    application = _locked(application)
    _check_decider(application, user)
    program = application.program
    amount = amount if amount is not None else (application.approved_amount or application.amount_requested)
    if amount is None:
        amount = program.default_amount
    if program.unit == Program.Unit.CASH and amount is None:
        raise BusinessRuleError("Set the approved amount.")
    due = due_date or application.due_date or application.needed_by or timezone.localdate()

    lookup = (
        {"member": application.member}
        if application.member
        else {"household": application.household, "member": None}
    )
    enrollment = Enrollment.all_objects.filter(
        program=program, status=Enrollment.Status.ACTIVE, **lookup
    ).first()
    if enrollment is None:
        enrollment = benefits.enroll(
            program=program,
            household=application.household,
            member=application.member,
            user=user,
            source=Enrollment.Source.APPLICATION,
        )
    entitlement = benefits.plan_entitlement(enrollment, user=user, due_date=due, amount=amount)
    entitlement = benefits.confirm_entitlement(entitlement, user)  # use the fresh copy it returns

    application.status = S.APPROVED
    application.approved_amount = amount
    application.due_date = due
    application.decided_by = user
    application.decided_at = timezone.now()
    application.decision_note = (note or "").strip()[:255]
    application.entitlement = entitlement
    application.save()
    return application


@transaction.atomic
def reject_application(application: Application, user, reason: str) -> Application:
    application = _locked(application)
    _check_decider(application, user)
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    application.status = S.REJECTED
    application.decided_by = user
    application.decided_at = timezone.now()
    application.decision_note = reason.strip()[:255]
    application.save()
    return application


@transaction.atomic
def withdraw_application(application: Application, user) -> Application:
    """The family (or whoever submitted it) no longer needs the help."""
    application = _locked(application)
    if application.status not in OPEN:
        raise BusinessRuleError("Only open applications can be withdrawn.")
    may = (
        application.submitted_by_id == user.pk
        or application.household.users.filter(pk=user.pk).exists()
        or has_any_role(user, *OFFICE_ROLES)
    )
    if not may:
        raise BusinessRuleError("You can't withdraw this application.", code="not_allowed")
    application.status = S.WITHDRAWN
    application.save()
    return application
