from decimal import Decimal

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.benefits.models import Entitlement

from .conftest import head

pytestmark = pytest.mark.django_db
BASE = "/api/v1/benefits"


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def admin(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def cycle(scored, make_program, make_cycle):
    scored()
    return make_cycle(make_program(min_need_score=40), budget=Decimal("4000"))


def test_beneficiary_is_forbidden(beneficiary):
    assert api(beneficiary).get(f"{BASE}/entitlements/").status_code == 403
    assert api(beneficiary).get(f"{BASE}/programs/").status_code == 403


def test_programs_and_cycles_lists(volunteer, cycle):
    programs = api(volunteer).get(f"{BASE}/programs/").json()
    assert [p["name"] for p in programs] == ["Ramadan Food Package"]
    cycles = api(volunteer).get(f"{BASE}/cycles/").json()["results"]
    assert cycles[0]["status"] == "active" and cycles[0]["summary"]["total"] == 0


def test_generate_confirm_over_budget_and_roles(cycle, coordinator, president, volunteer):
    assert api(volunteer).post(f"{BASE}/cycles/{cycle.id}/generate/").status_code == 403
    result = api(coordinator).post(f"{BASE}/cycles/{cycle.id}/generate/")
    assert result.json() == {"enrolled": 1, "planned": 1, "already_planned": 0}

    ent = api(coordinator).get(f"{BASE}/entitlements/", {"cycle": str(cycle.id)}).json()["results"][0]
    assert (ent["status"], ent["amount"], ent["household_code"]) == ("planned", "5000.00", "SHK-0001")
    over = api(president).post(f"{BASE}/entitlements/{ent['id']}/confirm/")  # Rs 5,000 > Rs 4,000 budget
    assert over.status_code == 409 and over.json()["code"] == "over_budget"


def test_entitlement_actions(cycle, coordinator, president):
    cycle.budget = None
    cycle.save()
    api(coordinator).post(f"{BASE}/cycles/{cycle.id}/generate/")
    ent_id = str(Entitlement.all_objects.get().id)
    assert api(president).post(f"{BASE}/entitlements/{ent_id}/confirm/").json()["status"] == "confirmed"
    ready = api(coordinator).post(f"{BASE}/entitlements/{ent_id}/ready/", {"collection_point": "Mosque"})
    assert ready.json()["collection_point"] == "Mosque"
    assert api(coordinator).post(f"{BASE}/entitlements/{ent_id}/miss/").json()["status"] == "missed"
    again = api(coordinator).post(f"{BASE}/entitlements/{ent_id}/reschedule/", {"due_date": "2027-03-01"})
    assert (again.json()["status"], again.json()["due_date"]) == ("ready", "2027-03-01")
    bad = api(coordinator).post(f"{BASE}/entitlements/{ent_id}/cancel/", {"reason": "x"})
    assert bad.status_code == 409 and bad.json()["code"] == "invalid_status_change"


def test_enroll_via_api(scored, make_program, coordinator):
    household = scored(members=[head(cnic="")])
    program = make_program()
    response = api(coordinator).post(
        f"{BASE}/enrollments/", {"program": str(program.id), "household": str(household.id)}
    )
    assert response.status_code == 201, response.json()
    end = api(coordinator).post(f"{BASE}/enrollments/{response.json()['id']}/end/", {"reason": "Done"})
    assert end.json()["status"] == "ended"


@pytest.mark.parametrize(
    "path",
    [
        "programs/program/",
        "programs/program/add/",
        "programs/cycle/",
        "programs/cycle/add/",
        "benefits/enrollment/",
        "benefits/enrollment/add/",
        "benefits/entitlement/",
    ],
)
def test_coordinator_can_open_admin_pages(coordinator, path):
    assert admin(coordinator).get(f"/admin/{path}").status_code == 200


def test_generate_and_confirm_from_admin(cycle, coordinator, president):
    page = admin(coordinator).post(
        "/admin/programs/cycle/", {"action": "generate", "_selected_action": [cycle.pk]}, follow=True
    )
    assert b"1 benefits planned" in page.content
    cycle.budget = None
    cycle.save()
    ent = Entitlement.all_objects.get()
    admin(president).post("/admin/benefits/entitlement/", {"action": "confirm", "_selected_action": [ent.pk]})
    ent.refresh_from_db()
    assert ent.status == "confirmed"
    detail = admin(coordinator).get(f"/admin/programs/cycle/{cycle.pk}/change/")
    assert b"1 confirmed" in detail.content
