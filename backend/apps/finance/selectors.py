"""Read-only queries, reused by the API, the admin panel and reports."""

from django.db.models import DecimalField, OuterRef, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .models import ZERO, Account, Fund, LedgerLine, MonthlyClose

_MONEY = DecimalField(max_digits=14, decimal_places=2)


def _sum_subquery(field: str, **filters):
    """SUM(field) of an account's ledger lines, as a subquery (one query for all rows, not one each)."""
    return Coalesce(
        Subquery(
            LedgerLine.all_objects.filter(**filters)
            .values("account")
            .annotate(total=Sum(field))
            .values("total")[:1],
            output_field=_MONEY,
        ),
        Value(ZERO),
        output_field=_MONEY,
    )


def funds_with_balance(qs: QuerySet[Fund] | None = None) -> QuerySet[Fund]:
    qs = Fund.objects.all() if qs is None else qs
    credit = _sum_subquery("credit", account__fund=OuterRef("pk"))
    debit = _sum_subquery("debit", account__fund=OuterRef("pk"))
    return qs.annotate(balance=credit - debit)


def assets_with_balance() -> QuerySet[Account]:
    debit = _sum_subquery("debit", account=OuterRef("pk"))
    credit = _sum_subquery("credit", account=OuterRef("pk"))
    return Account.objects.filter(kind=Account.Kind.ASSET).annotate(balance=debit - credit)


def published_reports(society, year: int | None = None) -> QuerySet[MonthlyClose]:
    qs = MonthlyClose.all_objects.filter(society=society, published_at__isnull=False)
    if year:
        qs = qs.filter(period__startswith=f"{year}-")
    return qs.order_by("period")
