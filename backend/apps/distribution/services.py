"""
Recording deliveries (architecture section 10.3).

- Volunteers and office bearers record deliveries. On distribution day any
  volunteer can serve any family (they scan the QR card), but never their own.
- Only a benefit that is "ready" can be delivered, and only once: the
  entitlement row is locked, and the database allows one distribution per
  entitlement.
- Safe to retry: if the phone sends the same delivery again (same client_uuid),
  the existing record is returned instead of an error or a duplicate.
"""

import uuid

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import require_role
from apps.benefits.models import Entitlement
from apps.benefits.services import move
from apps.core.exceptions import BusinessRuleError
from apps.registry.models import Household, Member
from apps.registry.qr import household_from_qr
from apps.registry.services import is_linked

from .models import Distribution

DELIVER_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.VOLUNTEER)


def find_household(society, text: str) -> Household | None:
    """From a scanned QR token, or a household code typed by hand."""
    text = (text or "").strip()
    if not text:
        return None
    by_code = Household.all_objects.filter(society=society, code__iexact=text).first()
    return by_code or household_from_qr(text, society.pk)


@transaction.atomic
def deliver(
    *,
    entitlement: Entitlement,
    user,
    client_uuid: uuid.UUID | None = None,
    received_by: Member | None = None,
    method: str = Distribution.Method.MANUAL,
    delivered_at=None,
    into: Distribution | None = None,
    **extra,
) -> tuple[Distribution, bool]:
    """Record a delivery. Returns (distribution, created); created is False for a retried request."""
    require_role(user, *DELIVER_ROLES, action="record deliveries")
    client_uuid = client_uuid or uuid.uuid4()

    # Lock the row: two volunteers scanning the same card at the same second can't both deliver.
    entitlement = (
        Entitlement.all_objects.select_for_update(of=("self",))
        .select_related("enrollment__household", "enrollment__program")
        .get(pk=entitlement.pk)
    )
    # Checked after locking, so two copies of the same retried request can't both get through.
    earlier = Distribution.all_objects.filter(client_uuid=client_uuid).first()
    if earlier is not None:
        if earlier.entitlement_id != entitlement.pk:
            raise BusinessRuleError(
                "This delivery ID was already used for another benefit.", code="uuid_reused"
            )
        return earlier, False  # the phone retried; nothing new to save

    household = entitlement.enrollment.household
    if household.society_id != user.society_id:
        raise BusinessRuleError("This benefit belongs to another society.")
    if entitlement.status == Entitlement.Status.DELIVERED:
        raise BusinessRuleError("Already collected.", code="already_delivered")
    if entitlement.status != Entitlement.Status.READY:
        raise BusinessRuleError(
            f"Not ready to collect yet ({entitlement.get_status_display().lower()}).", code="not_ready"
        )
    if is_linked(user, household):
        raise BusinessRuleError(
            "You can't hand out benefits to your own family. Ask another volunteer.",
            code="conflict_of_interest",
        )
    if received_by is not None and received_by.household_id != household.pk:
        raise BusinessRuleError("That person is not in this household.")

    distribution = into or Distribution()  # the admin passes its own unsaved object
    values = {
        "society_id": household.society_id,
        "created_by": user,
        "entitlement": entitlement,
        "household": household,
        "delivered_at": delivered_at or timezone.now(),
        "quantity": entitlement.quantity,
        "unit": entitlement.unit,
        "amount": entitlement.amount,
        "delivered_by": user,
        "received_by": received_by,
        "method": method,
        "client_uuid": client_uuid,
        **extra,
    }
    for name, value in values.items():
        setattr(distribution, name, value)
    distribution.save()
    move(entitlement, Entitlement.Status.DELIVERED)
    return distribution, True
