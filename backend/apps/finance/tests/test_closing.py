from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import BusinessRuleError
from apps.finance.services import closing, donations, expenses

pytestmark = pytest.mark.django_db


def period(day):
    return f"{day:%Y-%m}"


def test_close_last_month_with_totals(society, give, fund, zakat, volunteer, finance_sec, last_month):
    give(fund, 20_000, day=last_month)
    give(zakat, 5_000, day=last_month)
    expense = expenses.request_expense(
        society=society,
        user=volunteer,
        fund=fund,
        category="utilities",
        amount=Decimal("3000"),
        paid_on=last_month,
        description="Electricity",
        paid_to="IESCO",
    )
    expenses.approve_expense(expense, finance_sec)

    close = closing.close_month(society=society, period=period(last_month), user=finance_sec)

    funds = {f["code"]: f for f in close.totals["funds"]}
    assert funds["general"] == {
        **funds["general"],
        "opening": "0.00",
        "in": "20000.00",
        "out": "3000.00",
        "closing": "17000.00",
    }
    assert funds["zakat"]["closing"] == "5000.00"
    assert close.totals["totals"]["closing"] == "22000.00"
    assert close.totals["expenses_by_category"] == {"utilities": "3000.00"}
    assert close.totals["donations_count"] == 2
    assert not close.is_published


def test_opening_balance_carries_over(society, give, fund, finance_sec, last_month, two_months_ago):
    give(fund, 1_000, day=two_months_ago)
    closing.close_month(society=society, period=period(two_months_ago), user=finance_sec)
    give(fund, 500, day=last_month)
    close = closing.close_month(society=society, period=period(last_month), user=finance_sec)
    assert close.totals["funds"][0]["opening"] == "1000.00"
    assert close.totals["funds"][0]["closing"] == "1500.00"


def test_cannot_close_current_month(society, finance_sec, today):
    with pytest.raises(BusinessRuleError, match="finished"):
        closing.close_month(society=society, period=period(today), user=finance_sec)


def test_cannot_close_twice(society, finance_sec, last_month):
    closing.close_month(society=society, period=period(last_month), user=finance_sec)
    with pytest.raises(BusinessRuleError, match="already closed"):
        closing.close_month(society=society, period=period(last_month), user=finance_sec)


def test_months_close_in_order(society, give, fund, finance_sec, last_month, two_months_ago):
    give(fund, 100, day=two_months_ago)
    with pytest.raises(BusinessRuleError, match="first"):
        closing.close_month(society=society, period=period(last_month), user=finance_sec)


def test_pending_items_block_closing(society, volunteer, fund, finance_sec, last_month):
    donations.record_donation(
        society=society,
        user=volunteer,
        fund=fund,
        amount=Decimal("100"),
        received_on=last_month,
        method="cash",
    )
    with pytest.raises(BusinessRuleError, match="pending"):
        closing.close_month(society=society, period=period(last_month), user=finance_sec)


def test_only_finance_secretary_closes(society, president, last_month):
    with pytest.raises(PermissionDenied):
        closing.close_month(society=society, period=period(last_month), user=president)


def test_bad_period_format(society, finance_sec):
    with pytest.raises(BusinessRuleError, match="2026-10"):
        closing.close_month(society=society, period="Oct 2026", user=finance_sec)


def test_publish(society, finance_sec, president, last_month):
    close = closing.close_month(society=society, period=period(last_month), user=finance_sec)
    closing.publish_month(close, president)
    assert close.is_published
    with pytest.raises(BusinessRuleError, match="already published"):
        closing.publish_month(close, president)
