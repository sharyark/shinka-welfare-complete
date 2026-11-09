"""
Business rules for households and members. The API, the admin panel and tests
all call these functions.

Rules:
- Only office bearers and volunteers register households, and only with the family's consent.
- A household has exactly one head; a CNIC can be registered only once per society.
- Volunteers may edit only pending households they registered themselves.
- Verification is maker-checker: the person who registered a household can't verify it,
  and nobody can verify a household they are linked to (conflict of interest).
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.phone import normalize_phone
from apps.accounts.roles import has_any_role, require_role
from apps.core.exceptions import BusinessRuleError

from .cnic import protect_cnic
from .models import Household, HouseholdCounter, Member

REGISTER_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)
MANAGE_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR)  # edit anything, verify, reject, archive


# --- Checks (also used by admin forms to show errors before saving) -------------


def check_can_register(*, society, user, mohalla, consent: bool) -> None:
    if society is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    require_role(user, *REGISTER_ROLES, action="register households")
    if mohalla.society_id != society.id or not mohalla.is_active:
        raise BusinessRuleError("Choose an active mohalla of this society.")
    if not consent:
        raise BusinessRuleError(
            "The family must agree to their information being recorded before registering.", code="consent"
        )


def check_can_edit(household: Household, user) -> None:
    if has_any_role(user, *MANAGE_ROLES):
        if household.status == Household.Status.ARCHIVED:
            raise BusinessRuleError("Archived households can't be changed.")
        return
    require_role(user, *REGISTER_ROLES, action="edit households")
    if household.status != Household.Status.PENDING or household.registered_by_id != user.pk:
        raise BusinessRuleError(
            "Volunteers can only change households they registered, until they are verified."
        )


def check_member(member: Member, *, user, cnic: str | None = None, check_head: bool = True) -> dict:
    """
    Checks a new or changed member. `cnic` is what the user typed (None = unchanged,
    "" = remove). Returns the CNIC fields to store.
    """
    household = member.household
    if not household._state.adding:  # a household being created is checked by check_can_register
        check_can_edit(household, user)
        if check_head and member.relation == Member.Relation.HEAD:
            other_head = Member.all_objects.filter(household=household, relation=Member.Relation.HEAD)
            if other_head.exclude(pk=member.pk).exists():
                raise BusinessRuleError("This household already has a head. Change that member first.")

    fields = {} if cnic is None else protect_cnic(cnic)
    if fields.get("cnic_hash"):
        same = (
            Member.all_objects.filter(
                society_id=household.society_id or member.society_id, cnic_hash=fields["cnic_hash"]
            )
            .exclude(pk=member.pk)
            .select_related("household")
            .first()
        )
        if same:
            raise BusinessRuleError(
                f"This CNIC is already registered ({same.full_name}, household {same.household.code}).",
                code="duplicate_cnic",
            )
    return fields


# --- Households ------------------------------------------------------------------


def next_household_code(society) -> str:
    """SHK-0001, SHK-0002… without gaps or duplicates. Must be called inside a transaction."""
    counter, _ = HouseholdCounter.all_objects.select_for_update().get_or_create(society=society)
    counter.last_number += 1
    counter.save(update_fields=["last_number", "updated_at"])
    prefix = (society.settings or {}).get("household_code_prefix") or society.slug[:3].upper()
    return f"{prefix}-{counter.last_number:04d}"


@transaction.atomic
def create_household(household: Household, *, society, user, consent: bool) -> Household:
    """Saves a new (unsaved) household: gives it a code and marks it pending verification."""
    check_can_register(society=society, user=user, mohalla=household.mohalla, consent=consent)
    household.society = society
    household.created_by = user
    household.registered_by = user
    household.consent_given_at = timezone.now()
    household.status = Household.Status.PENDING
    if household.phone:
        household.phone = normalize_phone(household.phone)
    household.code = next_household_code(society)
    household.save()
    return household


@transaction.atomic
def register_household(*, society, user, consent: bool, members: list[dict], **fields) -> Household:
    """A household and all its members in one step (used by the API / mobile app)."""
    heads = [m for m in members if m.get("relation") == Member.Relation.HEAD]
    if len(heads) != 1:
        raise BusinessRuleError("Add exactly one head of household.", code="one_head")
    household = create_household(Household(**fields), society=society, user=user, consent=consent)
    for data in members:
        data = dict(data)
        cnic = data.pop("cnic", None)
        save_member(Member(household=household, **data), user=user, cnic=cnic)
    return household


@transaction.atomic
def update_household(household: Household, *, user, **fields) -> Household:
    household = _locked(household)  # decide on the current status, not a stale copy
    check_can_edit(household, user)
    if "mohalla" in fields:
        mohalla = fields["mohalla"]
        if mohalla.society_id != household.society_id or not mohalla.is_active:
            raise BusinessRuleError("Choose an active mohalla of this society.")
    if fields.get("phone"):
        fields["phone"] = normalize_phone(fields["phone"])
    users = fields.pop("users", None)
    for name, value in fields.items():
        setattr(household, name, value)
    household.save()
    if users is not None:
        household.users.set(users)
    return household


def _locked(household: Household) -> Household:
    return Household.all_objects.select_for_update().get(pk=household.pk)


def is_linked(user, household: Household) -> bool:
    """The user's own family: their app account is linked, or it's their phone number."""
    return household.users.filter(pk=user.pk).exists() or (
        bool(household.phone) and household.phone == user.phone
    )


@transaction.atomic
def verify_household(household: Household, user) -> Household:
    require_role(user, *MANAGE_ROLES, action="verify households")
    household = _locked(household)
    if household.status != Household.Status.PENDING:
        raise BusinessRuleError(f"Household is already {household.get_status_display().lower()}.")
    if household.registered_by_id == user.pk:
        raise BusinessRuleError(
            "You registered this household, so someone else must verify it.", code="maker_checker"
        )
    if is_linked(user, household):
        raise BusinessRuleError("You can't verify your own family's household.", code="conflict_of_interest")
    if not household.members.filter(relation=Member.Relation.HEAD).exists():
        raise BusinessRuleError("Add the head of household before verifying.", code="one_head")
    household.status = Household.Status.VERIFIED
    household.verified_by = user
    household.verified_at = timezone.now()
    household.decision_note = ""
    household.save(update_fields=["status", "verified_by", "verified_at", "decision_note", "updated_at"])
    return household


def _decide(household: Household, user, reason: str, *, allowed_from, new_status, action: str, done: str):
    require_role(user, *MANAGE_ROLES, action=f"{action} households")
    household = _locked(household)
    if household.status != allowed_from:
        raise BusinessRuleError(f"Only {allowed_from.value} households can be {done}.")
    if not (reason or "").strip():
        raise BusinessRuleError("Give a reason.")
    household.status = new_status
    household.decision_note = reason.strip()
    household.save(update_fields=["status", "decision_note", "updated_at"])
    return household


@transaction.atomic
def reject_household(household: Household, user, reason: str) -> Household:
    return _decide(
        household,
        user,
        reason,
        allowed_from=Household.Status.PENDING,
        new_status=Household.Status.REJECTED,
        action="reject",
        done="rejected",
    )


@transaction.atomic
def reopen_household(household: Household, user, reason: str) -> Household:
    """A rejected household gets another chance (e.g. missing documents were brought)."""
    return _decide(
        household,
        user,
        reason,
        allowed_from=Household.Status.REJECTED,
        new_status=Household.Status.PENDING,
        action="reopen",
        done="reopened",
    )


@transaction.atomic
def archive_household(household: Household, user, reason: str) -> Household:
    """No longer helped (moved away, circumstances improved). History is kept."""
    return _decide(
        household,
        user,
        reason,
        allowed_from=Household.Status.VERIFIED,
        new_status=Household.Status.ARCHIVED,
        action="archive",
        done="archived",
    )


# --- Members ---------------------------------------------------------------------


@transaction.atomic
def save_member(member: Member, *, user, cnic: str | None = None) -> Member:
    """Create or update a member. `cnic`: None = unchanged, "" = remove."""
    if not member.household._state.adding:
        member.household = _locked(member.household)  # decide on the current status, not a stale copy
    for name, value in check_member(member, user=user, cnic=cnic).items():
        setattr(member, name, value)
    if member._state.adding:
        member.society_id = member.household.society_id
        member.created_by = user
    member.save()
    return member


@transaction.atomic
def remove_member(member: Member, *, user) -> None:
    """Only for fixing data-entry mistakes on households not yet verified."""
    household = _locked(member.household)  # decide on the current status, not a stale copy
    check_can_edit(household, user)
    if household.status != Household.Status.PENDING:
        raise BusinessRuleError("Members of a verified household can't be removed.")
    member.delete()
