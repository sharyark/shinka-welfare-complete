"""Read queries for deliveries, including the after-cycle reconciliation (architecture 10.3)."""

from django.db.models import Count, Q, Sum

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.benefits.models import Entitlement

from .models import Distribution

S = Entitlement.Status
VIEW_ALL_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY)


def distributions_for(user, qs=None):
    """Office bearers see all deliveries; volunteers see the ones they made."""
    qs = Distribution.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *VIEW_ALL_ROLES):
        return qs
    if has_any_role(user, Role.VOLUNTEER):
        return qs.filter(delivered_by=user)
    return qs.none()


def cycle_reconciliation(cycle) -> dict:
    """Planned vs delivered vs missed, per mohalla and per volunteer, plus delivered amounts."""
    by_mohalla = (
        Entitlement.all_objects.filter(cycle=cycle)
        .exclude(status=S.CANCELLED)
        .values("enrollment__household__mohalla__name")
        .annotate(
            planned=Count("id"),
            delivered=Count("id", filter=Q(status=S.DELIVERED)),
            missed=Count("id", filter=Q(status=S.MISSED)),
            waiting=Count("id", filter=Q(status__in=(S.PLANNED, S.CONFIRMED, S.READY))),
        )
        .order_by("enrollment__household__mohalla__name")
    )
    by_volunteer = (
        Distribution.all_objects.filter(entitlement__cycle=cycle)
        .values("delivered_by__name")
        .annotate(delivered=Count("id"), amount=Sum("amount"))
        .order_by("-delivered")
    )
    return {
        "cycle": str(cycle),
        "by_mohalla": [
            {
                "mohalla": row["enrollment__household__mohalla__name"],
                "planned": row["planned"],
                "delivered": row["delivered"],
                "missed": row["missed"],
                "waiting": row["waiting"],
            }
            for row in by_mohalla
        ],
        "by_volunteer": [
            {"volunteer": row["delivered_by__name"], "delivered": row["delivered"], "amount": row["amount"]}
            for row in by_volunteer
        ],
    }
