from decimal import Decimal
from urllib.parse import unquote

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import BusinessRuleError
from apps.finance.models import Donation, Donor, LedgerLine, MonthlyClose
from apps.finance.services import donations, expenses
from apps.finance.services.ledger import fund_balance
from apps.finance.services.receipts import whatsapp_receipt_url

pytestmark = pytest.mark.django_db


@pytest.fixture
def pending(society, volunteer, fund, today):
    return donations.record_donation(
        society=society, user=volunteer, fund=fund, amount=Decimal("10000"), received_on=today, method="cash"
    )


def test_volunteer_records_a_pending_donation(pending, volunteer):
    assert pending.status == Donation.Status.PENDING
    assert pending.collected_by == volunteer
    assert pending.journal_entry is None
    assert LedgerLine.objects.count() == 0  # pending money is not in the books yet


def test_beneficiary_cannot_record_donations(society, beneficiary, fund, today):
    with pytest.raises(PermissionDenied):
        donations.record_donation(
            society=society,
            user=beneficiary,
            fund=fund,
            amount=Decimal("1"),
            received_on=today,
            method="cash",
        )


def test_finance_secretary_approval_posts_double_entry(pending, finance_sec, fund):
    donation = donations.approve_donation(pending, finance_sec)

    assert donation.status == Donation.Status.APPROVED
    assert donation.receipt_no == f"SHINKA-{donation.received_on.year}-00001"
    lines = {line.account.code: (line.debit, line.credit) for line in donation.journal_entry.lines.all()}
    assert lines == {"ASSET-CASH": (Decimal("10000"), 0), "FUND-GENERAL": (0, Decimal("10000"))}
    assert fund_balance(fund) == Decimal("10000")


def test_maker_cannot_approve_own_donation(society, finance_sec, fund, today):
    own = donations.record_donation(
        society=society, user=finance_sec, fund=fund, amount=Decimal("100"), received_on=today, method="cash"
    )
    with pytest.raises(BusinessRuleError) as exc:
        donations.approve_donation(own, finance_sec)
    assert exc.value.code == "maker_checker"


def test_volunteer_cannot_approve(pending, volunteer2):
    with pytest.raises(PermissionDenied):
        donations.approve_donation(pending, volunteer2)


def test_developer_superuser_cannot_approve_money(pending, society):
    from apps.accounts.models import User

    dev = User.objects.create_superuser(phone="03990000000", password="x", name="Dev")
    with pytest.raises(PermissionDenied):
        donations.approve_donation(pending, dev)


def test_cannot_approve_twice(pending, finance_sec, president):
    donations.approve_donation(pending, finance_sec)
    with pytest.raises(BusinessRuleError, match="already approved"):
        donations.approve_donation(pending, president)


def test_receipt_numbers_are_sequential(give, fund):
    numbers = [give(fund, 100).receipt_no for _ in range(3)]
    assert [n[-5:] for n in numbers] == ["00001", "00002", "00003"]


def test_reject_needs_a_reason(pending, finance_sec):
    with pytest.raises(BusinessRuleError, match="reason"):
        donations.reject_donation(pending, finance_sec, "  ")
    rejected = donations.reject_donation(pending, finance_sec, "Duplicate entry")
    assert rejected.status == Donation.Status.REJECTED


def test_reverse_puts_money_back(give, fund, finance_sec):
    donation = give(fund, 5000)
    donations.reverse_donation(donation, finance_sec, "Cheque bounced")
    donation.refresh_from_db()
    assert donation.status == Donation.Status.REVERSED
    assert fund_balance(fund) == 0


def test_cannot_reverse_money_already_spent(give, fund, finance_sec, volunteer, society, today):
    donation = give(fund, 5000)
    expense = expenses.request_expense(
        society=society,
        user=volunteer,
        fund=fund,
        category="other",
        amount=Decimal("4000"),
        paid_on=today,
        description="x",
        paid_to="y",
    )
    expenses.approve_expense(expense, finance_sec)
    with pytest.raises(BusinessRuleError, match="already spent"):
        donations.reverse_donation(donation, finance_sec, "Bounced")


def test_cannot_approve_into_closed_month(society, volunteer, finance_sec, fund, last_month):
    late = donations.record_donation(
        society=society,
        user=volunteer,
        fund=fund,
        amount=Decimal("100"),
        received_on=last_month,
        method="cash",
    )
    MonthlyClose.objects.create(society=society, period=f"{last_month:%Y-%m}", closed_by=finance_sec)
    with pytest.raises(BusinessRuleError, match="closed"):
        donations.approve_donation(late, finance_sec)
    late.refresh_from_db()
    assert late.status == Donation.Status.PENDING  # the failed approval left nothing behind


def test_whatsapp_receipt_link(give, fund, society):
    donor = Donor.objects.create(society=society, name="Ahmed", phone="0300-1112223")
    donation = give(fund, 2500, donor=donor)
    url = whatsapp_receipt_url(donation)
    assert url.startswith("https://wa.me/923001112223?text=")
    assert donation.receipt_no in unquote(url)


def test_anonymous_donor_name_is_hidden(give, fund, society):
    donor = Donor.objects.create(society=society, name="Real Name", phone="+447700900123", is_anonymous=True)
    donation = give(fund, 100, donor=donor)
    text = unquote(whatsapp_receipt_url(donation))
    assert "Real Name" not in text and "Anonymous" in text
    assert whatsapp_receipt_url(donation).startswith("https://wa.me/447700900123")
