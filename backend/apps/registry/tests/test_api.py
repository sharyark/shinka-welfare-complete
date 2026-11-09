import json

import pytest
from rest_framework.test import APIClient

from apps.registry.models import Household

from .conftest import child, head

pytestmark = pytest.mark.django_db
BASE = "/api/v1/registry"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def new_household(mohalla, members=None, **extra):
    return {
        "mohalla": str(mohalla.id),
        "phone": "0300-1112223",
        "consent": True,
        "members": members or [head(), child()],
        **extra,
    }


def test_login_required():
    assert APIClient().get(f"{BASE}/households/").status_code == 401


def test_beneficiary_and_auditor_are_forbidden(beneficiary, society):
    from apps.accounts.models import Role
    from apps.core.testing import make_user

    auditor = make_user(society, Role.AUDITOR)
    for user in (beneficiary, auditor):
        assert client_for(user).get(f"{BASE}/households/").status_code == 403


def test_mohallas_list(volunteer, mohalla):
    response = client_for(volunteer).get(f"{BASE}/mohallas/")
    assert response.json() == [{"id": str(mohalla.id), "name": "Dhok Syedan", "name_ur": ""}]


def test_volunteer_registers_household(volunteer, mohalla):
    response = client_for(volunteer).post(f"{BASE}/households/", new_household(mohalla), format="json")
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["code"] == "SHK-0001"
    assert body["status"] == "pending"
    assert body["phone"] == "+923001112223"
    assert [m["relation"] for m in body["members"]] == ["head", "daughter"]


def test_full_cnic_never_appears_in_responses(volunteer, mohalla):
    client = client_for(volunteer)
    created = client.post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    for response in (
        created,
        client.get(f"{BASE}/households/").json(),
        client.get(f"{BASE}/households/{created['id']}/").json(),
    ):
        text = json.dumps(response)
        assert "1234567" not in text
        assert "cnic_hash" not in text and "cnic_encrypted" not in text
    assert created["members"][0]["cnic_masked"] == "37101-*****-3"


def test_validation_errors(volunteer, mohalla):
    client = client_for(volunteer)
    bad_cnic = client.post(
        f"{BASE}/households/", new_household(mohalla, members=[head(cnic="123")]), format="json"
    )
    assert bad_cnic.status_code == 400
    no_consent = client.post(f"{BASE}/households/", new_household(mohalla, consent=False), format="json")
    assert no_consent.status_code == 409
    assert no_consent.json()["code"] == "consent"
    no_head = client.post(f"{BASE}/households/", new_household(mohalla, members=[child()]), format="json")
    assert no_head.json()["code"] == "one_head"


def test_duplicate_cnic_returns_409(volunteer, volunteer2, mohalla):
    client_for(volunteer).post(f"{BASE}/households/", new_household(mohalla), format="json")
    again = client_for(volunteer2).post(f"{BASE}/households/", new_household(mohalla), format="json")
    assert again.status_code == 409
    assert again.json()["code"] == "duplicate_cnic"


def test_mohalla_of_another_society_is_invalid(volunteer, other_society):
    from apps.registry.models import Mohalla

    foreign = Mohalla.objects.create(society=other_society, name="Elsewhere")
    response = client_for(volunteer).post(f"{BASE}/households/", new_household(foreign), format="json")
    assert response.status_code == 400
    assert "mohalla" in response.json()


def test_volunteer_sees_only_own_and_search_works(volunteer, volunteer2, coordinator, mohalla):
    client_for(volunteer).post(f"{BASE}/households/", new_household(mohalla), format="json")
    client_for(volunteer2).post(
        f"{BASE}/households/",
        new_household(mohalla, members=[head(name="Bilal", cnic="")], phone=""),
        format="json",
    )
    assert client_for(volunteer).get(f"{BASE}/households/").json()["count"] == 1
    coord = client_for(coordinator)
    assert coord.get(f"{BASE}/households/").json()["count"] == 2
    found = coord.get(f"{BASE}/households/", {"q": "37101-1234567-3"}).json()
    assert [(h["code"], h["head_name"], h["member_count"]) for h in found["results"]] == [
        ("SHK-0001", "Rashid Khan", 2)
    ]


def test_other_volunteers_household_is_not_found(volunteer, volunteer2, mohalla):
    created = client_for(volunteer).post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    assert client_for(volunteer2).get(f"{BASE}/households/{created['id']}/").status_code == 404


def test_add_and_update_members(volunteer, mohalla):
    client = client_for(volunteer)
    created = client.post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    added = client.post(
        f"{BASE}/households/{created['id']}/members/", child(name="Zainab", is_orphan=True), format="json"
    )
    assert added.status_code == 201
    assert len(added.json()["members"]) == 3

    daughter = next(m for m in added.json()["members"] if m["full_name"] == "Ayesha")
    updated = client.patch(
        f"{BASE}/members/{daughter['id']}/", {"school": "Govt Girls School", "cnic": "37101-7654321-2"}
    )
    assert updated.status_code == 200, updated.json()
    assert updated.json()["school"] == "Govt Girls School"
    assert updated.json()["cnic_masked"] == "37101-*****-2"

    assert client.delete(f"{BASE}/members/{daughter['id']}/").status_code == 204


def test_verify_flow_with_maker_checker(volunteer, coordinator, mohalla):
    created = (
        client_for(coordinator).post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    )
    own = client_for(coordinator).post(f"{BASE}/households/{created['id']}/verify/")
    assert own.status_code == 409
    assert own.json()["code"] == "maker_checker"

    by_volunteer = client_for(volunteer).post(f"{BASE}/households/{created['id']}/verify/")
    assert by_volunteer.status_code in (403, 404)  # can't even see it: registered by someone else


def test_coordinator_verifies_rejects_and_archives(volunteer, coordinator, mohalla):
    client = client_for(coordinator)
    first = client_for(volunteer).post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    verified = client.post(f"{BASE}/households/{first['id']}/verify/")
    assert verified.json()["status"] == "verified"
    assert verified.json()["verified_by"] == "Coordinator"
    archived = client.post(f"{BASE}/households/{first['id']}/archive/", {"reason": "Moved away"})
    assert archived.json()["status"] == "archived"

    second = client_for(volunteer).post(
        f"{BASE}/households/",
        new_household(mohalla, members=[head(name="B", cnic="")], phone=""),
        format="json",
    )
    second_id = second.json()["id"]
    assert client.post(f"{BASE}/households/{second_id}/reject/", {}).status_code == 400  # reason needed
    rejected = client.post(f"{BASE}/households/{second_id}/reject/", {"reason": "Duplicate"})
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["decision_note"] == "Duplicate"


def test_patch_household(volunteer, mohalla):
    client = client_for(volunteer)
    created = client.post(f"{BASE}/households/", new_household(mohalla), format="json").json()
    response = client.patch(f"{BASE}/households/{created['id']}/", {"address": "Near the bore"})
    assert response.status_code == 200
    assert Household.all_objects.get().address == "Near the bore"
