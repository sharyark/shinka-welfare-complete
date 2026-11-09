import pytest
from rest_framework.test import APIClient

from apps.finance.models import Donation, Fund
from apps.finance.services import closing

from .conftest import make_user

pytestmark = pytest.mark.django_db
BASE = "/api/v1/finance"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_login_required():
    assert APIClient().get(f"{BASE}/donations/").status_code == 401


def test_beneficiary_is_forbidden(beneficiary):
    assert client_for(beneficiary).get(f"{BASE}/donations/").status_code == 403


def test_volunteer_records_donation_and_sees_only_own(volunteer, volunteer2, fund, today):
    response = client_for(volunteer).post(
        f"{BASE}/donations/",
        {"fund": str(fund.id), "amount": "2500", "received_on": str(today), "method": "cash"},
    )
    assert response.status_code == 201, response.json()
    assert response.json()["status"] == "pending"

    assert client_for(volunteer).get(f"{BASE}/donations/").json()["count"] == 1
    assert client_for(volunteer2).get(f"{BASE}/donations/").json()["count"] == 0


def test_finance_secretary_sees_all_and_approves(volunteer, finance_sec, fund, today):
    created = (
        client_for(volunteer)
        .post(
            f"{BASE}/donations/",
            {"fund": str(fund.id), "amount": "1000", "received_on": str(today), "method": "jazzcash"},
        )
        .json()
    )

    fs = client_for(finance_sec)
    assert fs.get(f"{BASE}/donations/").json()["count"] == 1
    approved = fs.post(f"{BASE}/donations/{created['id']}/approve/")
    assert approved.status_code == 200
    assert approved.json()["receipt_no"].startswith("SHINKA-")


def test_maker_checker_returns_409(finance_sec, fund, today):
    fs = client_for(finance_sec)
    created = fs.post(
        f"{BASE}/donations/",
        {"fund": str(fund.id), "amount": "1000", "received_on": str(today), "method": "cash"},
    ).json()
    response = fs.post(f"{BASE}/donations/{created['id']}/approve/")
    assert response.status_code == 409
    assert response.json()["code"] == "maker_checker"


def test_volunteer_cannot_approve_returns_403(volunteer, volunteer2, fund, today):
    created = (
        client_for(volunteer)
        .post(
            f"{BASE}/donations/",
            {"fund": str(fund.id), "amount": "1000", "received_on": str(today), "method": "cash"},
        )
        .json()
    )
    # volunteer2 can't even see it (404), and the collector isn't an approver (403)
    assert client_for(volunteer2).post(f"{BASE}/donations/{created['id']}/approve/").status_code == 404
    assert client_for(volunteer).post(f"{BASE}/donations/{created['id']}/approve/").status_code == 403


def test_reject_requires_reason(volunteer, finance_sec, fund, today):
    created = (
        client_for(volunteer)
        .post(
            f"{BASE}/donations/",
            {"fund": str(fund.id), "amount": "1000", "received_on": str(today), "method": "cash"},
        )
        .json()
    )
    fs = client_for(finance_sec)
    assert fs.post(f"{BASE}/donations/{created['id']}/reject/", {}).status_code == 400
    response = fs.post(f"{BASE}/donations/{created['id']}/reject/", {"reason": "Duplicate"})
    assert response.json()["status"] == "rejected"


def test_zakat_salary_expense_is_refused(volunteer, zakat, today):
    response = client_for(volunteer).post(
        f"{BASE}/expenses/",
        {
            "fund": str(zakat.id),
            "category": "salaries",
            "description": "Guard",
            "amount": "15000",
            "paid_to": "Guard",
            "paid_on": str(today),
            "method": "cash",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "fund_category"


def test_expense_flow_shows_who_must_sign(give, fund, volunteer, finance_sec, coordinator, today):
    give(fund, 100_000)
    created = (
        client_for(volunteer)
        .post(
            f"{BASE}/expenses/",
            {
                "fund": str(fund.id),
                "category": "maintenance",
                "description": "Pump repair",
                "amount": "30000",
                "paid_to": "Mechanic",
                "paid_on": str(today),
                "method": "cash",
            },
        )
        .json()
    )
    assert created["waiting_for"] == ["Finance Secretary", "Program Coordinator"]

    after = client_for(finance_sec).post(f"{BASE}/expenses/{created['id']}/approve/").json()
    assert after["waiting_for"] == ["Program Coordinator"]
    done = client_for(coordinator).post(f"{BASE}/expenses/{created['id']}/approve/").json()
    assert done["status"] == "approved"


def test_balances_visible_to_office_only(give, fund, volunteer, finance_sec):
    give(fund, 700)
    general = lambda user: next(  # noqa: E731
        f for f in client_for(user).get(f"{BASE}/funds/").json()["results"] if f["code"] == "general"
    )
    assert general(finance_sec)["balance"] == "700.00"
    assert general(volunteer)["balance"] is None


def test_other_society_data_is_invisible(give, fund, other_society, today):
    give(fund, 500)
    outsider = make_user(other_society, "Finance Secretary")
    response = client_for(outsider).get(f"{BASE}/donations/")
    assert response.json()["count"] == 0
    donation_id = Donation.all_objects.get().id
    assert client_for(outsider).get(f"{BASE}/donations/{donation_id}/").status_code == 404


def test_cannot_use_another_society_fund(volunteer, other_society, today):
    foreign_fund = Fund.all_objects.get(society=other_society, code="general")
    response = client_for(volunteer).post(
        f"{BASE}/donations/",
        {"fund": str(foreign_fund.id), "amount": "100", "received_on": str(today), "method": "cash"},
    )
    assert response.status_code == 400  # not in the list of choosable funds


# --- Public ----------------------------------------------------------------------


def test_public_transparency_shows_only_published(
    society, give, fund, finance_sec, last_month, two_months_ago
):
    give(fund, 1_000, day=two_months_ago)
    first = closing.close_month(society=society, period=f"{two_months_ago:%Y-%m}", user=finance_sec)
    closing.close_month(society=society, period=f"{last_month:%Y-%m}", user=finance_sec)
    closing.publish_month(first, finance_sec)

    response = APIClient().get("/api/v1/public/shinka/transparency/")
    assert response.status_code == 200
    data = response.json()
    assert [r["period"] for r in data] == [first.period]
    assert data[0]["totals"]["totals"]["closing"] == "1000.00"


def test_public_data_contains_no_names(society, give, fund, finance_sec, last_month):
    from apps.finance.models import Donor

    donor = Donor.objects.create(society=society, name="Secret Donor Name", phone="03001234567")
    give(fund, 1_000, day=last_month, donor=donor)
    close = closing.close_month(society=society, period=f"{last_month:%Y-%m}", user=finance_sec)
    closing.publish_month(close, finance_sec)
    body = APIClient().get("/api/v1/public/shinka/transparency/").content.decode()
    assert "Secret Donor Name" not in body
    assert "03001234567" not in body


def test_public_year_filter_and_unknown_society(society, finance_sec, last_month):
    close = closing.close_month(society=society, period=f"{last_month:%Y-%m}", user=finance_sec)
    closing.publish_month(close, finance_sec)
    assert APIClient().get(f"/api/v1/public/shinka/transparency/?year={last_month.year - 1}").json() == []
    assert APIClient().get("/api/v1/public/nowhere/transparency/").status_code == 404


def test_public_funds(society):
    names = [f["name"] for f in APIClient().get("/api/v1/public/shinka/funds/").json()]
    assert "Zakat" in names and len(names) == 9
