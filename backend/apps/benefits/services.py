"""
Business rules for enrollments and entitlements.

- Only verified households of the same society can be enrolled, and only if
  they meet the program's rules (need score, age, gender).
- Generating a cycle plans one entitlement per eligible household (or person).
  Running it again only adds the newly eligible: nobody gets two.
- Entitlements move only along the allowed paths (see models.py). Confirming
  (promising the money) is the President's decision and can't exceed the
  cycle's budget. "Delivered" is set only by the distribution step.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import require_role
from apps.assessment.selectors import with_need_score
from apps.core.exceptions import BusinessRuleError
from apps.programs.models import Cycle, Program
from apps.programs.services import MANAGE_ROLES, locked_cycle
from apps.registry.models import Household, Member

from .models import Enrollment, Entitlement

CONFIRM_ROLES = (Role.PRESIDENT,)
S = Entitlement.Status
ALLOWED = {
    S.PLANNED: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.READY, S.CANCELLED},
    S.READY: {S.DELIVERED, S.MISSED},
    S.MISSED: {S.READY},
}
OPEN_STATUSES = (S.PLANNED, S.CONFIRMED, S.READY)  # not yet given, not cancelled
COMMITTED_STATUSES = (S.CONFIRMED, S.READY, S.DELIVERED)  # money promised or spent


# --- Eligibility --------------------------------------------------------------------


def years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February in a non-leap year
        return day.replace(year=day.year - years, day=28)


def eligible_households(program: Program, on: date | None = None):
    """Verified households of the program's society that meet its need-score cutoff."""
    qs = Household.all_objects.filter(society_id=program.society_id, status=Household.Status.VERIFIED)
    if program.min_need_score is not None:
        qs = with_need_score(qs, on).filter(need_score__gte=program.min_need_score)
    return qs


def eligible_members(program: Program, households, on: date):
    """People in those households who meet the program's age and gender limits on `on`."""
    qs = Member.all_objects.filter(household__in=households)
    if program.member_gender:
        qs = qs.filter(gender=program.member_gender)
    if program.member_min_age is not None:
        qs = qs.filter(date_of_birth__lte=years_before(on, program.member_min_age))
    if program.member_max_age is not None:
        qs = qs.filter(date_of_birth__gt=years_before(on, program.member_max_age + 1))
    return qs


def check_eligible(program: Program, household: Household, member: Member | None, *, check_need_score=True):
    if household.society_id != program.society_id:
        raise BusinessRuleError("Household belongs to another society.")
    if household.status != Household.Status.VERIFIED:
        raise BusinessRuleError("Only verified households can be enrolled.")
    if program.target == Program.Target.MEMBER and member is None:
        raise BusinessRuleError("This program is per person: choose the member.")
    if program.target == Program.Target.HOUSEHOLD and member is not None:
        raise BusinessRuleError("This program is per household: don't choose a member.")
    if member is not None and member.household_id != household.pk:
        raise BusinessRuleError("That person is not in this household.")
    today = timezone.localdate()
    if check_need_score and program.min_need_score is not None:
        if not eligible_households(program, today).filter(pk=household.pk).exists():
            raise BusinessRuleError(
                f"Needs an approved need score of at least {program.min_need_score}.", code="not_eligible"
            )
    if member is not None and not eligible_members(program, [household], today).filter(pk=member.pk).exists():
        raise BusinessRuleError(f"{member.full_name} doesn't meet this program's age or gender limits.")


# --- Enrollments -------------------------------------------------------------------------


def check_can_enroll(*, program, household, member=None, user, check_need_score=True) -> None:
    """All checks for a manual enrollment. Also used by the admin form."""
    require_role(user, *MANAGE_ROLES, action="enroll households")
    if not program.is_active:
        raise BusinessRuleError("The program is switched off.")
    check_eligible(program, household, member, check_need_score=check_need_score)
    already = Enrollment.all_objects.filter(program=program, status=Enrollment.Status.ACTIVE)
    already = already.filter(member=member) if member else already.filter(household=household, member=None)
    if already.exists():
        raise BusinessRuleError("Already enrolled in this program.", code="already_enrolled")


@transaction.atomic
def enroll(
    *,
    program: Program,
    household: Household,
    user,
    member: Member | None = None,
    source=Enrollment.Source.MANUAL,
    check_need_score=True,
    notes="",
    into: Enrollment | None = None,
) -> Enrollment:
    household = Household.all_objects.select_for_update().get(pk=household.pk)
    check_can_enroll(
        program=program, household=household, member=member, user=user, check_need_score=check_need_score
    )
    enrollment = into or Enrollment()
    enrollment.society_id = program.society_id
    enrollment.created_by = user
    enrollment.program = program
    enrollment.household = household
    enrollment.member = member
    enrollment.source = source
    enrollment.start_date = enrollment.start_date or timezone.localdate()
    enrollment.notes = notes or enrollment.notes
    enrollment.save()
    return enrollment


@transaction.atomic
def end_enrollment(enrollment: Enrollment, user, reason: str) -> Enrollment:
    """E.g. the student finished school. Benefits not yet given are cancelled."""
    require_role(user, *MANAGE_ROLES, action="end enrollments")
    enrollment = Enrollment.all_objects.select_for_update().get(pk=enrollment.pk)
    if enrollment.status != Enrollment.Status.ACTIVE:
        raise BusinessRuleError("This enrollment has already ended.")
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    enrollment.status = Enrollment.Status.ENDED
    enrollment.end_date = timezone.localdate()
    enrollment.end_reason = reason.strip()
    enrollment.save(update_fields=["status", "end_date", "end_reason", "updated_at"])
    enrollment.entitlements.filter(status__in=OPEN_STATUSES).update(
        status=S.CANCELLED, status_note=f"Enrollment ended: {reason.strip()}"[:255], updated_at=timezone.now()
    )
    return enrollment


# --- Planning entitlements ------------------------------------------------------------------


def plan_entitlement(enrollment: Enrollment, *, user, due_date: date, cycle: Cycle | None = None, **values):
    """One planned benefit, with the program's defaults unless values are given."""
    program = enrollment.program
    return Entitlement.objects.create(
        society_id=enrollment.society_id,
        created_by=user,
        enrollment=enrollment,
        cycle=cycle,
        due_date=due_date,
        quantity=values.get("quantity") or program.default_quantity,
        unit=program.unit,
        amount=values.get("amount", program.default_amount),
        collection_point=values.get("collection_point") or (cycle.collection_point if cycle else ""),
    )


@transaction.atomic
def generate_cycle(cycle: Cycle, user) -> dict:
    """
    Plan an entitlement for everyone eligible in this cycle. Safe to run again:
    existing enrollments are reused, and nobody gets a second entitlement.
    """
    require_role(user, *MANAGE_ROLES, action="generate cycles")
    cycle = locked_cycle(cycle)
    program = cycle.program
    if cycle.status != Cycle.Status.ACTIVE:
        raise BusinessRuleError("Activate the cycle first.")
    if program.requires_application:
        raise BusinessRuleError(
            "People apply for this program; entitlements come from approved applications."
        )

    households = eligible_households(program)  # need score valid today; ages are counted on the due date
    if program.target == Program.Target.MEMBER:
        targets = [
            (m.household, m)
            for m in eligible_members(program, households, cycle.due_date).select_related("household")
        ]
    else:
        targets = [(h, None) for h in households]

    counts = {"enrolled": 0, "planned": 0, "already_planned": 0}
    for household, member in targets:
        lookup = {"member": member} if member else {"household": household, "member": None}
        enrollment = Enrollment.all_objects.filter(
            program=program, status=Enrollment.Status.ACTIVE, **lookup
        ).first()
        if enrollment is None:
            enrollment = Enrollment.objects.create(
                society_id=program.society_id,
                created_by=user,
                program=program,
                household=household,
                member=member,
                source=Enrollment.Source.CYCLE,
                start_date=timezone.localdate(),
            )
            counts["enrolled"] += 1
        if Entitlement.all_objects.filter(enrollment=enrollment, cycle=cycle).exists():
            counts["already_planned"] += 1
            continue
        plan_entitlement(enrollment, user=user, due_date=cycle.due_date, cycle=cycle)
        counts["planned"] += 1
    return counts


@transaction.atomic
def close_cycle(cycle: Cycle, user) -> Cycle:
    """Finish a cycle: what was never confirmed is cancelled, what was ready but not collected is missed."""
    require_role(user, *MANAGE_ROLES, action="close cycles")
    cycle = locked_cycle(cycle)
    if cycle.status != Cycle.Status.ACTIVE:
        raise BusinessRuleError("Only active cycles can be closed.")
    now = timezone.now()
    cycle.entitlements.filter(status__in=(S.PLANNED, S.CONFIRMED)).update(
        status=S.CANCELLED, status_note="Cycle closed", updated_at=now
    )
    cycle.entitlements.filter(status=S.READY).update(
        status=S.MISSED, status_note="Cycle closed", updated_at=now
    )
    cycle.status = Cycle.Status.CLOSED
    cycle.save(update_fields=["status", "updated_at"])
    return cycle


# --- Moving an entitlement along its path ---------------------------------------------------


def _locked(entitlement: Entitlement) -> Entitlement:
    return (
        # of=("self",): lock only the entitlement row. PostgreSQL can't lock the optional cycle
        # joined in, and confirm_entitlement locks the cycle separately anyway.
        Entitlement.all_objects.select_for_update(of=("self",))
        .select_related("cycle", "enrollment__program")
        .get(pk=entitlement.pk)
    )


def move(entitlement: Entitlement, new_status: str, *, note: str = "", **fields) -> Entitlement:
    """Change status if the path allows it. Call inside a transaction with a locked row."""
    if new_status not in ALLOWED.get(entitlement.status, set()):
        raise BusinessRuleError(
            f"Can't go from {entitlement.get_status_display().lower()} to {S(new_status).label.lower()}.",
            code="invalid_status_change",
        )
    entitlement.status = new_status
    entitlement.status_note = note[:255]
    for name, value in fields.items():
        setattr(entitlement, name, value)
    entitlement.save()
    return entitlement


def committed_amount(cycle: Cycle) -> Decimal:
    total = cycle.entitlements.filter(status__in=COMMITTED_STATUSES).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


@transaction.atomic
def confirm_entitlement(entitlement: Entitlement, user) -> Entitlement:
    """The committee promises this benefit; it must fit the cycle's budget."""
    require_role(user, *CONFIRM_ROLES, action="confirm benefits")
    entitlement = _locked(entitlement)
    cycle = entitlement.cycle
    if cycle is not None:
        cycle = locked_cycle(cycle)  # one confirmation at a time per cycle, so the budget can't be overrun
        if cycle.status != Cycle.Status.ACTIVE:
            raise BusinessRuleError("The cycle isn't active.")
        if cycle.budget is not None and committed_amount(cycle) + (entitlement.amount or 0) > cycle.budget:
            raise BusinessRuleError(
                f"Over budget: {cycle.name} has Rs {cycle.budget - committed_amount(cycle):,.0f} left.",
                code="over_budget",
            )
    return move(entitlement, S.CONFIRMED, confirmed_by=user)


@transaction.atomic
def mark_ready(entitlement: Entitlement, user, collection_point: str = "") -> Entitlement:
    require_role(user, *MANAGE_ROLES, action="mark benefits ready")
    entitlement = _locked(entitlement)
    fields = {"collection_point": collection_point} if collection_point else {}
    return move(entitlement, S.READY, **fields)


@transaction.atomic
def cancel_entitlement(entitlement: Entitlement, user, reason: str) -> Entitlement:
    require_role(user, *MANAGE_ROLES, action="cancel benefits")
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    return move(_locked(entitlement), S.CANCELLED, note=reason.strip())


@transaction.atomic
def mark_missed(entitlement: Entitlement, user, reason: str = "Not collected") -> Entitlement:
    require_role(user, *MANAGE_ROLES, action="mark benefits missed")
    return move(_locked(entitlement), S.MISSED, note=reason or "Not collected")


@transaction.atomic
def reschedule(entitlement: Entitlement, user, due_date: date) -> Entitlement:
    """A missed benefit gets a new collection date."""
    require_role(user, *MANAGE_ROLES, action="reschedule benefits")
    entitlement = _locked(entitlement)
    if entitlement.cycle and entitlement.cycle.status == Cycle.Status.CLOSED:
        raise BusinessRuleError("The cycle is closed.")
    return move(entitlement, S.READY, note=f"Rescheduled to {due_date:%d %b %Y}", due_date=due_date)
