"""
Business rules for programs and cycles.

Only the President and the Program Coordinator manage programs. Generating and
closing a cycle change entitlements, so those live in apps/benefits/services.py
(benefits depends on programs, never the other way round).
"""

from django.db import transaction

from apps.accounts.models import Role
from apps.accounts.roles import require_role
from apps.core.exceptions import BusinessRuleError

from .models import Cycle

MANAGE_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR)


def locked_cycle(cycle: Cycle) -> Cycle:
    return (
        Cycle.all_objects.select_for_update(of=("self",))
        .select_related("program", "society")
        .get(pk=cycle.pk)
    )


@transaction.atomic
def activate_cycle(cycle: Cycle, user) -> Cycle:
    require_role(user, *MANAGE_ROLES, action="activate cycles")
    cycle = locked_cycle(cycle)
    if cycle.status != Cycle.Status.DRAFT:
        raise BusinessRuleError(f"This cycle is already {cycle.status}.")
    if not cycle.program.is_active:
        raise BusinessRuleError("The program is switched off; turn it on first.")
    cycle.status = Cycle.Status.ACTIVE
    cycle.save(update_fields=["status", "updated_at"])
    return cycle
