from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.core.exceptions import BusinessRuleError
from apps.finance.models import JournalEntry, LedgerLine, MonthlyClose
from apps.finance.services.ledger import (
    Line,
    asset_account,
    fund_account,
    fund_balance,
    post_entry,
    reverse_entry,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cash(society):
    return asset_account(society, "cash")


def test_balanced_entry_is_posted(society, fund, cash, today):
    entry = post_entry(
        society=society,
        day=today,
        description="Test",
        lines=[Line(cash, debit=Decimal("500")), Line(fund_account(fund), credit=Decimal("500"))],
    )
    assert entry.lines.count() == 2
    assert entry.period == f"{today:%Y-%m}"
    assert fund_balance(fund) == Decimal("500")


def test_unbalanced_entry_is_rejected(society, fund, cash, today):
    with pytest.raises(BusinessRuleError, match="Unbalanced"):
        post_entry(
            society=society,
            day=today,
            description="Bad",
            lines=[Line(cash, debit=Decimal("500")), Line(fund_account(fund), credit=Decimal("400"))],
        )
    assert JournalEntry.objects.count() == 0  # nothing half-written


@pytest.mark.parametrize(
    "lines",
    [
        "single",
        "zero",
        "negative",
        "both_sides",
    ],
)
def test_malformed_lines_are_rejected(society, fund, cash, today, lines):
    fa = fund_account(fund)
    cases = {
        "single": [Line(cash, debit=Decimal("1"))],
        "zero": [Line(cash, debit=Decimal("0")), Line(fa, credit=Decimal("0"))],
        "negative": [Line(cash, debit=Decimal("-5")), Line(fa, credit=Decimal("-5"))],
        "both_sides": [Line(cash, debit=Decimal("5"), credit=Decimal("5")), Line(fa, credit=Decimal("0"))],
    }
    with pytest.raises(BusinessRuleError):
        post_entry(society=society, day=today, description="Bad", lines=cases[lines])


def test_account_of_another_society_is_rejected(society, other_society, fund, today):
    with pytest.raises(BusinessRuleError, match="another society"):
        post_entry(
            society=society,
            day=today,
            description="Bad",
            lines=[
                Line(asset_account(other_society, "cash"), debit=Decimal("5")),
                Line(fund_account(fund), credit=Decimal("5")),
            ],
        )


def test_nothing_can_be_posted_into_a_closed_month(society, fund, cash, finance_sec, last_month):
    MonthlyClose.objects.create(society=society, period=f"{last_month:%Y-%m}", closed_by=finance_sec)
    with pytest.raises(BusinessRuleError, match="closed"):
        post_entry(
            society=society,
            day=last_month,
            description="Late",
            lines=[Line(cash, debit=Decimal("5")), Line(fund_account(fund), credit=Decimal("5"))],
        )


def test_reverse_mirrors_the_entry_once(society, fund, cash, today):
    entry = post_entry(
        society=society,
        day=today,
        description="Gift",
        lines=[Line(cash, debit=Decimal("300")), Line(fund_account(fund), credit=Decimal("300"))],
    )
    reversal = reverse_entry(entry, day=today, description="Undo")
    assert reversal.reverses == entry
    assert fund_balance(fund) == 0
    with pytest.raises(BusinessRuleError, match="already been reversed"):
        reverse_entry(entry, day=today, description="Again")


def test_database_refuses_two_sided_line(society, fund, cash, today):
    entry = JournalEntry.objects.create(society=society, date=today, period="2026-01", description="x")
    with pytest.raises(IntegrityError):
        LedgerLine.objects.create(society=society, entry=entry, account=cash, debit=5, credit=5)
