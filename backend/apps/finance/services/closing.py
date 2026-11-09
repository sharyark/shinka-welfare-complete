"""
Monthly close: freeze a finished month and compute its report.

After a month is closed nothing can be posted into it (ledger.post_entry
checks this). Corrections go into the current month as reversing entries.
Closed months are never reopened, so published numbers never change.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import require_role
from apps.core.exceptions import BusinessRuleError
from apps.finance.models import (
    ZERO,
    Donation,
    Expense,
    Fund,
    JournalEntry,
    LedgerLine,
    MonthlyClose,
    money_str,
)

from .periods import current_period


@transaction.atomic
def close_month(*, society, period: str, user) -> MonthlyClose:
    check_can_close(society=society, period=period, user=user)
    return MonthlyClose.objects.create(
        society=society,
        period=period,
        closed_by=user,
        created_by=user,
        totals=compute_month_totals(society, period),
    )


def check_can_close(*, society, period: str, user) -> None:
    """All checks for closing a month. Also used by the admin form to show errors before saving."""
    if society is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    require_role(user, Role.FINANCE_SECRETARY, action="close a month")
    _validate_period_format(period)

    if period >= current_period():
        raise BusinessRuleError("Only finished months can be closed.")
    if MonthlyClose.all_objects.filter(society=society, period=period).exists():
        raise BusinessRuleError(f"{period} is already closed.")

    closed = set(MonthlyClose.all_objects.filter(society=society).values_list("period", flat=True))
    earlier_open = sorted(
        p
        for p in JournalEntry.all_objects.filter(society=society, period__lt=period)
        .values_list("period", flat=True)
        .distinct()
        if p not in closed
    )
    if earlier_open:
        raise BusinessRuleError(f"Close {earlier_open[0]} first. Months are closed in order.")

    year, month = (int(x) for x in period.split("-"))
    pending_donations = Donation.all_objects.filter(
        society=society, status=Donation.Status.PENDING, received_on__year=year, received_on__month=month
    ).count()
    pending_expenses = Expense.all_objects.filter(
        society=society, status=Expense.Status.PENDING, paid_on__year=year, paid_on__month=month
    ).count()
    if pending_donations or pending_expenses:
        raise BusinessRuleError(
            f"{period} still has {pending_donations} pending donation(s) and "
            f"{pending_expenses} pending expense(s). Approve or reject them first."
        )


@transaction.atomic
def publish_month(close: MonthlyClose, user) -> MonthlyClose:
    require_role(user, Role.FINANCE_SECRETARY, Role.PRESIDENT, action="publish monthly reports")
    if close.is_published:
        raise BusinessRuleError(f"{close.period} is already published.")
    close.published_at = timezone.now()
    close.save(update_fields=["published_at", "updated_at"])
    return close


def compute_month_totals(society, period: str) -> dict:
    """Per-fund opening / in / out / closing, plus spending by category. Amounts as strings."""
    lines = LedgerLine.all_objects.filter(society=society, account__fund__isnull=False)
    funds = []
    grand = {"opening": ZERO, "in": ZERO, "out": ZERO, "closing": ZERO}

    for fund in Fund.all_objects.filter(society=society).order_by("name"):
        mine = lines.filter(account__fund=fund)
        before = mine.filter(entry__period__lt=period).aggregate(d=Sum("debit"), c=Sum("credit"))
        during = mine.filter(entry__period=period).aggregate(d=Sum("debit"), c=Sum("credit"))
        opening = (before["c"] or ZERO) - (before["d"] or ZERO)
        money_in = during["c"] or ZERO
        money_out = during["d"] or ZERO
        if not (opening or money_in or money_out):
            continue  # skip funds with no activity at all
        row = {
            "opening": opening,
            "in": money_in,
            "out": money_out,
            "closing": opening + money_in - money_out,
        }
        for key in grand:
            grand[key] += row[key]
        funds.append({"code": fund.code, "name": fund.name, "name_ur": fund.name_ur, **_str(row)})

    return {
        "period": period,
        "funds": funds,
        "totals": _str(grand),
        "expenses_by_category": _expenses_by_category(society, period),
        "donations_count": Donation.all_objects.filter(society=society, journal_entry__period=period).count(),
    }


def _expenses_by_category(society, period: str) -> dict:
    """Spending per category in the month; reversals made this month count as negative."""
    totals: dict[str, Decimal] = {}
    posted = Expense.all_objects.filter(society=society, journal_entry__period=period)
    reversed_now = Expense.all_objects.filter(Q(journal_entry__reversed_by__period=period), society=society)
    for expense in posted:
        totals[expense.category] = totals.get(expense.category, ZERO) + expense.amount
    for expense in reversed_now:
        totals[expense.category] = totals.get(expense.category, ZERO) - expense.amount
    return {k: money_str(v) for k, v in sorted(totals.items()) if v}


def _str(values: dict) -> dict:
    return {k: money_str(v) for k, v in values.items()}


def _validate_period_format(period: str) -> None:
    try:
        year, month = period.split("-")
        assert len(year) == 4 and 1 <= int(month) <= 12 and len(month) == 2
    except (ValueError, AssertionError) as exc:
        raise BusinessRuleError("Period must look like 2026-10.") from exc
