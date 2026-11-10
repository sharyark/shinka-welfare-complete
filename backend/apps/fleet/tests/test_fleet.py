from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import BusinessRuleError
from apps.fleet import selectors, services
from apps.fleet.models import Trip, Vehicle

pytestmark = pytest.mark.django_db
BASE = "/api/v1/fleet"


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_full_trip(family, ambulance, beneficiary, volunteer):
    trip = services.request_trip(user=beneficiary, household=family, destination="THQ Hazro", pickup="Home")
    trip = services.start_trip(trip, volunteer, vehicle=ambulance, km_start=1000, driver_name="Javed")
    trip = services.complete_trip(trip, volunteer, km_end=1046, fuel_cost=Decimal("2500"))
    assert (trip.status, trip.distance_km, trip.driver_name) == (Trip.Status.COMPLETED, 46, "Javed")


def test_family_can_request_only_for_itself(register, beneficiary, ambulance):
    other = register()
    with pytest.raises(BusinessRuleError) as exc:
        services.request_trip(user=beneficiary, household=other, destination="DHQ Attock")
    assert exc.value.code == "not_allowed"


def test_vehicle_cannot_be_on_two_trips(ambulance, volunteer):
    first = services.request_trip(user=volunteer, destination="PIMS")
    second = services.request_trip(user=volunteer, destination="DHQ Attock")
    services.start_trip(first, volunteer, vehicle=ambulance, km_start=10)
    with pytest.raises(BusinessRuleError) as exc:
        services.start_trip(second, volunteer, vehicle=ambulance, km_start=10)
    assert exc.value.code == "vehicle_busy"


def test_vehicle_in_workshop_cannot_go(ambulance, volunteer):
    ambulance.status = Vehicle.Status.MAINTENANCE
    ambulance.save()
    trip = services.request_trip(user=volunteer, destination="PIMS")
    with pytest.raises(BusinessRuleError, match="not in service"):
        services.start_trip(trip, volunteer, vehicle=ambulance, km_start=1)


def test_end_reading_must_not_go_backwards(ambulance, volunteer):
    trip = services.start_trip(
        services.request_trip(user=volunteer, destination="X"), volunteer, vehicle=ambulance, km_start=500
    )
    with pytest.raises(BusinessRuleError):
        services.complete_trip(trip, volunteer, km_end=499)


def test_family_cannot_start_trips_but_can_cancel_own_request(family, beneficiary, ambulance):
    trip = services.request_trip(user=beneficiary, household=family, destination="THQ Hazro")
    with pytest.raises(PermissionDenied):
        services.start_trip(trip, beneficiary, vehicle=ambulance, km_start=1)
    assert services.cancel_trip(trip, beneficiary, "Got a car").status == Trip.Status.CANCELLED


def test_monthly_costs(ambulance, volunteer):
    for km_end, fuel in ((40, "2000"), (100, "4000")):
        trip = services.start_trip(
            services.request_trip(user=volunteer, destination="X"), volunteer, vehicle=ambulance, km_start=0
        )
        services.complete_trip(trip, volunteer, km_end=km_end, fuel_cost=Decimal(fuel))
    today = timezone.localdate()
    assert selectors.monthly_costs(today.year, today.month) == [
        {
            "vehicle": "Ambulance 1",
            "trips": 2,
            "km": 140,
            "fuel": Decimal("6000.00"),
            "fuel_per_trip": Decimal("3000.00"),
        }
    ]


def test_visibility(family, beneficiary, volunteer, register, society):
    from apps.accounts.models import Role
    from apps.core.testing import make_user

    services.request_trip(user=beneficiary, household=family, destination="A")
    services.request_trip(user=volunteer, destination="B")
    assert selectors.trips_for(beneficiary).count() == 1
    assert selectors.trips_for(volunteer).count() == 2
    assert selectors.trips_for(make_user(society, Role.BENEFICIARY)).count() == 0


def test_api_flow(family, beneficiary, volunteer, coordinator, ambulance):
    created = api(beneficiary).post(
        f"{BASE}/trips/", {"household": str(family.id), "destination": "THQ Hazro"}, format="json"
    )
    assert created.status_code == 201, created.json()
    trip_id = created.json()["id"]
    assert (
        api(beneficiary).post(f"{BASE}/trips/{trip_id}/start/", {"km_start": 1}, format="json").status_code
        == 403
    )
    started = api(volunteer).post(
        f"{BASE}/trips/{trip_id}/start/", {"vehicle": str(ambulance.id), "km_start": 100}, format="json"
    )
    assert started.json()["status"] == "on_trip"
    done = api(volunteer).post(
        f"{BASE}/trips/{trip_id}/complete/", {"km_end": 130, "fuel_cost": "1800"}, format="json"
    )
    assert (done.json()["status"], done.json()["distance_km"]) == ("completed", 30)
    assert api(volunteer).get(f"{BASE}/trips/costs/").status_code == 403
    costs = api(coordinator).get(f"{BASE}/trips/costs/").json()
    assert costs["vehicles"][0]["trips"] == 1
    assert [v["name"] for v in api(beneficiary).get(f"{BASE}/vehicles/").json()] == ["Ambulance 1"]


@pytest.mark.parametrize("path", ["vehicle/", "vehicle/add/", "trip/", "trip/add/"])
def test_admin_pages(coordinator, path):
    client = Client()
    client.force_login(coordinator)
    assert client.get(f"/admin/fleet/{path}").status_code == 200
