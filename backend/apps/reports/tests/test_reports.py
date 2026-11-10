import json
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assets.models import Asset
from apps.distribution import services as distribution
from apps.finance.services import donations
from apps.finance.services.setup import ensure_finance_setup
from apps.fleet import services as fleet
from apps.fleet.models import Vehicle
from apps.reports import selectors

pytestmark = pytest.mark.django_db


@pytest.fixture
def busy_year(ready, society, volunteer, volunteer2, finance_sec):
    """One package delivered, one donation approved, one ambulance trip, two assets."""
    distribution.deliver(entitlement=ready, user=volunteer2)
    ensure_finance_setup(society)
    from apps.finance.models import Fund

    fund = Fund.all_objects.get(society=society, code="general")
    donation = donations.record_donation(
        society=society,
        user=volunteer,
        fund=fund,
        amount=Decimal("10000"),
        received_on=timezone.localdate(),
        method="cash",
    )
    donations.approve_donation(donation, finance_sec)
    ambulance = Vehicle.objects.create(
        society=society, name="Ambulance 1", registration_no="ATK-1", kind="ambulance"
    )
    trip = fleet.start_trip(
        fleet.request_trip(user=volunteer, destination="THQ Hazro"), volunteer, vehicle=ambulance, km_start=0
    )
    fleet.complete_trip(trip, volunteer, km_end=30, fuel_cost=Decimal("1500"))
    Asset.objects.create(society=society, kind="water_bore", name="Bore 1")
    Asset.objects.create(society=society, kind="water_bore", name="Bore 2", status="needs_repair")
    return society


def test_public_impact_is_totals_only(busy_year):
    year = timezone.localdate().year
    impact = selectors.public_impact(busy_year, year)
    assert impact["registered_households"] == 1
    assert impact["households_helped"] == 1
    assert impact["ambulance_trips"] == 1
    assert impact["benefits_given"][0]["program"] == "Ramadan Food Package"
    assert impact["community_assets"] == [
        {"kind": "water_bore", "label": "Water bore", "total": 2, "working": 1}
    ]
    text = json.dumps(impact, default=str)
    for private in ("SHK-0001", "Rashid", "Ayesha", "10000"):
        assert private not in text


def test_committee_overview_adds_money_and_waiting_work(busy_year):
    overview = selectors.committee_overview(busy_year, timezone.localdate().year)
    assert overview["donations"] == {"count": 1, "total": Decimal("10000.00")}
    assert overview["trip_fuel"] == Decimal("1500.00")
    assert overview["waiting"]["assets_needing_repair"] == 1
    assert overview["people_in_registered_households"] == 2


def test_public_endpoint_needs_no_login_and_overview_needs_office(busy_year, volunteer, coordinator):
    public = APIClient().get("/api/v1/public/shinka/impact/")
    assert public.status_code == 200 and public.json()["households_helped"] == 1
    assert APIClient().get("/api/v1/public/nope/impact/").status_code == 404

    def api(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    assert api(volunteer).get("/api/v1/reports/overview/").status_code == 403
    assert api(coordinator).get("/api/v1/reports/overview/").json()["donations"]["count"] == 1


def test_admin_home_shows_dashboard(busy_year, president):
    client = Client()
    client.force_login(president)
    page = client.get("/admin/").content.decode()
    assert "at a glance" in page
    assert "Rs 10,000" in page
    assert "assets needing repair" in page
