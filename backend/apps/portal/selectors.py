"""
What a family sees about itself (architecture section 8): help RECEIVED and help UPCOMING.

This app has no tables of its own. It reads registry, benefits and distribution,
which is why it sits "above" them (it may import them; they never import it).
The need score is never shown here.
"""

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.benefits.models import Entitlement
from apps.distribution.models import Distribution
from apps.registry.models import Household

S = Entitlement.Status
UPCOMING = (S.PLANNED, S.CONFIRMED, S.READY)
LABELS = {
    S.PLANNED: ("Expected — depends on available funds", "متوقع — فنڈز کی دستیابی پر منحصر"),
    S.CONFIRMED: ("Confirmed", "تصدیق شدہ"),
    S.READY: ("Ready to collect", "وصولی کے لیے تیار"),
}


def household_of(user) -> Household | None:
    """The family this app account belongs to (Household.users)."""
    return (
        Household.all_objects.filter(users=user)
        .exclude(status__in=(Household.Status.REJECTED, Household.Status.ARCHIVED))
        .select_related("mohalla")
        .first()
    )


def household_summary(household: Household, year: int | None = None) -> dict:
    year = year or timezone.localdate().year
    received = (
        Distribution.all_objects.filter(household=household, delivered_at__year=year)
        .values("entitlement__enrollment__program__name", "unit")
        .annotate(count=Count("id"), quantity=Sum("quantity"), amount=Sum("amount"))
        .order_by("entitlement__enrollment__program__name")
    )
    upcoming = (
        Entitlement.all_objects.filter(enrollment__household=household, status__in=UPCOMING)
        .select_related("enrollment__program", "enrollment__member")
        .order_by("due_date")
    )
    total_cash = sum((row["amount"] or Decimal("0")) for row in received if row["unit"] == "cash")
    return {
        "household_code": household.code,
        "year": year,
        "received": {
            "total_cash_pkr": total_cash,
            "items": [
                {
                    "program": row["entitlement__enrollment__program__name"],
                    "count": row["count"],
                    "quantity": row["quantity"],
                    "unit": row["unit"],
                    "amount_pkr": row["amount"],
                }
                for row in received
            ],
        },
        "upcoming": [
            {
                "program": e.enrollment.program.name,
                "program_ur": e.enrollment.program.name_ur,
                "person": e.enrollment.member.full_name if e.enrollment.member_id else None,
                "due_date": e.due_date,
                "quantity": e.quantity,
                "unit": e.unit,
                "amount_pkr": e.amount,
                "status": e.status,
                "label": LABELS[e.status][0],
                "label_ur": LABELS[e.status][1],
                "collection_point": e.collection_point if e.status == S.READY else "",
            }
            for e in upcoming
        ],
    }
