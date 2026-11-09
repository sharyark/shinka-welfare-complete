import pytest
from django.test import Client

from apps.finance.models import Donation, MonthlyClose

pytestmark = pytest.mark.django_db
ADMIN = "/admin/finance"


def admin_client(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.parametrize(
    "path",
    [
        "fund/",
        "fund/add/",
        "account/",
        "donor/",
        "donor/add/",
        "donation/",
        "donation/add/",
        "expense/",
        "expense/add/",
        "journalentry/",
        "monthlyclose/",
        "monthlyclose/add/",
    ],
)
def test_finance_secretary_can_open_pages(finance_sec, path):
    assert admin_client(finance_sec).get(f"{ADMIN}/{path}").status_code == 200


def test_auditor_is_read_only(society):
    from .conftest import make_user

    auditor = make_user(society, "Auditor")
    client = admin_client(auditor)
    assert client.get(f"{ADMIN}/donation/").status_code == 200
    assert client.get(f"{ADMIN}/donation/add/").status_code == 403


def test_add_donation_then_approve_with_action(finance_sec, president, fund, today, society):
    response = admin_client(finance_sec).post(
        f"{ADMIN}/donation/add/",
        {"fund": fund.id, "amount": "3000", "method": "cash", "received_on": str(today)},
    )
    assert response.status_code == 302, response.content[:3000]
    donation = Donation.all_objects.get()
    assert donation.society == society and donation.status == "pending"

    # The maker can't approve; the president can.
    admin_client(finance_sec).post(
        f"{ADMIN}/donation/", {"action": "approve", "_selected_action": [donation.pk]}
    )
    donation.refresh_from_db()
    assert donation.status == "pending"
    admin_client(president).post(
        f"{ADMIN}/donation/", {"action": "approve", "_selected_action": [donation.pk]}
    )
    donation.refresh_from_db()
    assert donation.status == "approved"


def test_reject_action_asks_for_reason(volunteer, finance_sec, fund, today, society):
    from apps.finance.services import donations

    donation = donations.record_donation(
        society=society, user=volunteer, fund=fund, amount=100, received_on=today, method="cash"
    )
    client = admin_client(finance_sec)
    form_page = client.post(f"{ADMIN}/donation/", {"action": "reject", "_selected_action": [donation.pk]})
    assert b"Reason" in form_page.content
    client.post(
        f"{ADMIN}/donation/",
        {"action": "reject", "_selected_action": [donation.pk], "apply": "1", "reason": "Test entry"},
    )
    donation.refresh_from_db()
    assert donation.status == "rejected" and donation.decision_note == "Test entry"


def test_zakat_rule_shows_as_form_error(finance_sec, zakat, today):
    response = admin_client(finance_sec).post(
        f"{ADMIN}/expense/add/",
        {
            "fund": zakat.id,
            "category": "salaries",
            "description": "Guard",
            "amount": "100",
            "paid_to": "Guard",
            "paid_on": str(today),
            "method": "cash",
        },
    )
    assert response.status_code == 200
    assert b"cannot pay for" in response.content


def test_close_month_from_admin(finance_sec, last_month, today):
    client = admin_client(finance_sec)
    bad = client.post(f"{ADMIN}/monthlyclose/add/", {"period": f"{today:%Y-%m}"})
    assert b"Only finished months" in bad.content
    ok = client.post(f"{ADMIN}/monthlyclose/add/", {"period": f"{last_month:%Y-%m}"})
    assert ok.status_code == 302
    close = MonthlyClose.all_objects.get()
    assert admin_client(finance_sec).get(f"{ADMIN}/monthlyclose/{close.pk}/change/").status_code == 200


def test_money_records_cannot_be_deleted(give, fund, finance_sec):
    donation = give(fund, 100)
    assert admin_client(finance_sec).get(f"{ADMIN}/donation/{donation.pk}/delete/").status_code == 403
