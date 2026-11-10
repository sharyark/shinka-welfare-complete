"""Read queries for trips, including the monthly cost report (architecture 10.6, 17)."""

from django.db.models import Count, F, Q, Sum

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role

from .models import Trip

STAFF_VIEW = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY, Role.VOLUNTEER)


def trips_for(user, qs=None):
    """Staff see all trips; a family sees its own (and ones it requested)."""
    qs = Trip.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *STAFF_VIEW):
        return qs
    return qs.filter(Q(household__users=user) | Q(requested_by=user)).distinct()


def monthly_costs(year: int, month: int, qs=None):
    """Completed trips per vehicle in one month: count, kilometres, fuel and cost per trip."""
    qs = Trip.objects.all() if qs is None else qs
    rows = (
        qs.filter(status=Trip.Status.COMPLETED, completed_at__year=year, completed_at__month=month)
        .values("vehicle__name")
        .annotate(trips=Count("id"), km=Sum(F("km_end") - F("km_start")), fuel=Sum("fuel_cost"))
        .order_by("vehicle__name")
    )
    return [
        {
            "vehicle": r["vehicle__name"],
            "trips": r["trips"],
            "km": r["km"] or 0,
            "fuel": r["fuel"] or 0,
            "fuel_per_trip": round((r["fuel"] or 0) / r["trips"], 2) if r["trips"] else 0,
        }
        for r in rows
    ]
