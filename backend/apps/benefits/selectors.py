"""Read queries for enrollments and entitlements."""

from django.db.models import Count, Q, Sum

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.registry.selectors import households_for

from .models import Enrollment, Entitlement

S = Entitlement.Status
# Who sees benefits of every household (architecture 5.2). Volunteers see their households' benefits.
VIEW_ALL_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY)


def entitlements_for(user, qs=None):
    qs = Entitlement.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *VIEW_ALL_ROLES):
        return qs
    return qs.filter(enrollment__household__in=households_for(user))


def enrollments_for(user, qs=None):
    qs = Enrollment.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *VIEW_ALL_ROLES):
        return qs
    return qs.filter(household__in=households_for(user))


def cycle_summary(cycle) -> dict:
    """Planned vs confirmed vs delivered vs missed, with amounts (architecture 10.3)."""
    rows = cycle.entitlements.aggregate(
        total=Count("id"),
        **{status.value: Count("id", filter=Q(status=status)) for status in S},
        committed_amount=Sum("amount", filter=Q(status__in=(S.CONFIRMED, S.READY, S.DELIVERED))),
        delivered_amount=Sum("amount", filter=Q(status=S.DELIVERED)),
    )
    rows["budget"] = cycle.budget
    return rows
