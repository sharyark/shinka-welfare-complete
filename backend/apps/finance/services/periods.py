from datetime import date

from django.utils import timezone

from apps.core.exceptions import BusinessRuleError


def period_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def current_period() -> str:
    return period_of(timezone.localdate())


def is_closed(society, period: str) -> bool:
    from apps.finance.models import MonthlyClose

    return MonthlyClose.all_objects.filter(society=society, period=period).exists()


def ensure_open(society, day: date) -> str:
    period = period_of(day)
    if is_closed(society, period):
        raise BusinessRuleError(
            f"{period} is closed. Record this in the current month instead.", code="period_closed"
        )
    return period
