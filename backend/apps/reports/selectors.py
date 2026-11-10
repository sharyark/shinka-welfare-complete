"""
Numbers for the committee's dashboard and the public impact page (architecture 17).

This app has no tables. It sits at the top of the dependency chain and reads
every other app; no other app imports it.

Public numbers are totals only: no names, no households, no need scores
(architecture principle 5). Money stays on the finance transparency page,
which shows published months only.
"""

from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.applications.models import Application
from apps.assessment.models import Assessment
from apps.assets.models import Asset
from apps.benefits.models import Enrollment
from apps.distribution.models import Distribution
from apps.finance.models import Donation, Expense
from apps.fleet.models import Trip
from apps.programs.models import Program
from apps.registry.models import Household, Member

ZERO = Decimal("0")


def _benefits_by_program(society, year: int) -> list[dict]:
    rows = (
        Distribution.all_objects.filter(society=society, delivered_at__year=year)
        .values("entitlement__enrollment__program__name", "entitlement__enrollment__program__name_ur", "unit")
        .annotate(
            count=Count("id"),
            quantity=Sum("quantity"),
            amount=Sum("amount"),
            households=Count("household", distinct=True),
        )
        .order_by("-count")
    )
    return [
        {
            "program": r["entitlement__enrollment__program__name"],
            "program_ur": r["entitlement__enrollment__program__name_ur"],
            "unit": r["unit"],
            "count": r["count"],
            "quantity": r["quantity"],
            "households": r["households"],
            "amount": r["amount"],
        }
        for r in rows
    ]


def _assets_by_kind(society) -> list[dict]:
    rows = (
        Asset.all_objects.filter(society=society)
        .exclude(status=Asset.Status.REMOVED)
        .values("kind")
        .annotate(total=Count("id"), working=Count("id", filter=Q(status=Asset.Status.WORKING)))
        .order_by("kind")
    )
    labels = dict(Asset.Kind.choices)
    return [
        {"kind": r["kind"], "label": labels[r["kind"]], "total": r["total"], "working": r["working"]}
        for r in rows
    ]


def public_impact(society, year: int) -> dict:
    """Totals only, safe to publish."""
    verified = Household.all_objects.filter(society=society, status=Household.Status.VERIFIED)
    students = Enrollment.all_objects.filter(
        society=society, status=Enrollment.Status.ACTIVE, program__target=Program.Target.MEMBER
    )
    return {
        "year": year,
        "registered_households": verified.count(),
        "households_helped": Distribution.all_objects.filter(society=society, delivered_at__year=year)
        .values("household")
        .distinct()
        .count(),
        "people_supported_individually": students.count(),
        "benefits_given": [
            {k: v for k, v in row.items() if k != "households"} for row in _benefits_by_program(society, year)
        ],
        "ambulance_trips": Trip.all_objects.filter(
            society=society, status=Trip.Status.COMPLETED, completed_at__year=year, vehicle__kind="ambulance"
        ).count(),
        "community_assets": _assets_by_kind(society),
    }


def committee_overview(society, year: int) -> dict:
    """Everything on the public page, plus money, members and the work waiting for someone."""
    donations = Donation.all_objects.filter(
        society=society, status=Donation.Status.APPROVED, received_on__year=year
    )
    expenses = Expense.all_objects.filter(society=society, status=Expense.Status.APPROVED, paid_on__year=year)
    trips = Trip.all_objects.filter(society=society, status=Trip.Status.COMPLETED, completed_at__year=year)
    return {
        **public_impact(society, year),
        "people_in_registered_households": Member.all_objects.filter(
            society=society, household__status=Household.Status.VERIFIED
        ).count(),
        "benefits_by_program": _benefits_by_program(society, year),
        "cash_given": Distribution.all_objects.filter(
            society=society, delivered_at__year=year, unit="cash"
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO,
        "donations": {"count": donations.count(), "total": donations.aggregate(t=Sum("amount"))["t"] or ZERO},
        "expenses": {"count": expenses.count(), "total": expenses.aggregate(t=Sum("amount"))["t"] or ZERO},
        "trip_fuel": trips.aggregate(t=Sum("fuel_cost"))["t"] or ZERO,
        "waiting": {
            "households_to_verify": Household.all_objects.filter(
                society=society, status=Household.Status.PENDING
            ).count(),
            "surveys_to_approve": Assessment.all_objects.filter(
                society=society, status=Assessment.Status.PENDING
            ).count(),
            "applications_open": Application.all_objects.filter(
                society=society, status__in=(Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW)
            ).count(),
            "donations_to_approve": Donation.all_objects.filter(
                society=society, status=Donation.Status.PENDING
            ).count(),
            "expenses_to_sign": Expense.all_objects.filter(
                society=society, status=Expense.Status.PENDING
            ).count(),
            "assets_needing_repair": Asset.all_objects.filter(
                society=society, status__in=(Asset.Status.NEEDS_REPAIR, Asset.Status.OUT_OF_SERVICE)
            ).count(),
        },
    }
