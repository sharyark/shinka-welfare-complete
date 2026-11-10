import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from rest_framework.test import APIClient

from apps.benefits import services as benefits
from apps.benefits.models import Entitlement
from apps.distribution import selectors, services
from apps.distribution.models import Distribution
from apps.registry.qr import household_from_qr, household_qr_token

pytestmark = pytest.mark.django_db
BASE = "/api/v1/distribution"


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# --- Service rules -------------------------------------------------------------------


def test_deliver_records_and_marks_delivered(ready, volunteer2):
    head = ready.enrollment.household.members.get(relation="head")
    distribution, created = services.deliver(entitlement=ready, user=volunteer2, received_by=head)
    ready.refresh_from_db()
    assert created and ready.status == Entitlement.Status.DELIVERED
    assert (distribution.delivered_by, distribution.received_by, distribution.amount) == (
        volunteer2,
        head,
        5000,
    )
    assert distribution.household == ready.enrollment.household


def test_cannot_deliver_twice(ready, volunteer, volunteer2):
    services.deliver(entitlement=ready, user=volunteer2)
    with pytest.raises(Exception) as exc:
        services.deliver(entitlement=ready, user=volunteer)
    assert getattr(exc.value, "code", None) == "already_delivered"
    assert Distribution.all_objects.count() == 1


def test_retry_with_same_client_uuid_returns_the_same_record(ready, volunteer2):
    key = uuid.uuid4()
    first, created = services.deliver(entitlement=ready, user=volunteer2, client_uuid=key)
    again, created_again = services.deliver(entitlement=ready, user=volunteer2, client_uuid=key)
    assert (created, created_again, again.pk) == (True, False, first.pk)


def test_client_uuid_cannot_be_reused_for_another_benefit(ready, scored, volunteer2, coordinator, president):
    key = uuid.uuid4()
    services.deliver(entitlement=ready, user=volunteer2, client_uuid=key)
    from apps.registry.tests.conftest import head

    other = scored(members=[head(name="B", cnic="")])
    benefits.generate_cycle(ready.cycle, coordinator)
    second = Entitlement.all_objects.get(enrollment__household=other)
    second = benefits.mark_ready(benefits.confirm_entitlement(second, president), coordinator)
    with pytest.raises(Exception) as exc:
        services.deliver(entitlement=second, user=volunteer2, client_uuid=key)
    assert exc.value.code == "uuid_reused"


def test_only_ready_benefits_can_be_delivered(scored, make_program, make_cycle, coordinator, volunteer2):
    scored()
    cycle = make_cycle(make_program())
    benefits.generate_cycle(cycle, coordinator)
    with pytest.raises(Exception) as exc:
        services.deliver(entitlement=Entitlement.all_objects.get(), user=volunteer2)
    assert exc.value.code == "not_ready"


def test_no_delivery_to_own_family(ready, volunteer2):
    ready.enrollment.household.users.add(volunteer2)
    with pytest.raises(Exception) as exc:
        services.deliver(entitlement=ready, user=volunteer2)
    assert exc.value.code == "conflict_of_interest"


def test_receiver_must_be_in_the_household(ready, scored, volunteer2):
    from apps.registry.tests.conftest import head

    stranger = scored(members=[head(name="Stranger", cnic="")]).members.get()
    with pytest.raises(Exception, match="not in this household"):
        services.deliver(entitlement=ready, user=volunteer2, received_by=stranger)


def test_finance_secretary_and_beneficiary_cannot_deliver(ready, finance_sec, beneficiary):
    for user in (finance_sec, beneficiary):
        with pytest.raises(PermissionDenied):
            services.deliver(entitlement=ready, user=user)


# --- QR cards --------------------------------------------------------------------------


def test_qr_token_finds_household_and_fakes_are_refused(ready, society, other_society):
    household = ready.enrollment.household
    token = household_qr_token(household)
    assert household_from_qr(token, society.pk) == household
    assert household_from_qr(token, other_society.pk) is None
    assert household_from_qr(token[:-2] + "xx", society.pk) is None
    assert household_from_qr("SHK-0001", society.pk) is None  # a plain code isn't a token
    assert services.find_household(society, "shk-0001") == household  # but lookup accepts codes too


# --- Reconciliation --------------------------------------------------------------------


def test_reconciliation_by_mohalla_and_volunteer(ready, volunteer2):
    services.deliver(entitlement=ready, user=volunteer2)
    report = selectors.cycle_reconciliation(ready.cycle)
    assert report["by_mohalla"] == [
        {"mohalla": "Dhok Syedan", "planned": 1, "delivered": 1, "missed": 0, "waiting": 0}
    ]
    assert report["by_volunteer"][0]["volunteer"] == "Volunteer B"
    assert report["by_volunteer"][0]["delivered"] == 1


# --- API -------------------------------------------------------------------------------


def test_lookup_by_qr_shows_family_and_what_can_be_collected(ready, volunteer2):
    token = household_qr_token(ready.enrollment.household)
    body = api(volunteer2).get(f"{BASE}/lookup/", {"q": token}).json()
    assert body["household_code"] == "SHK-0001"
    assert [m["full_name"] for m in body["members"]] == ["Rashid Khan", "Ayesha"]
    assert body["entitlements"][0]["can_deliver"] is True
    assert api(volunteer2).get(f"{BASE}/lookup/", {"q": "nonsense"}).status_code == 404


def test_deliver_via_api_and_retry(ready, volunteer2):
    body = {"entitlement": str(ready.id), "client_uuid": str(uuid.uuid4()), "method": "qr"}
    first = api(volunteer2).post(f"{BASE}/deliver/", body, format="json")
    assert first.status_code == 201, first.json()
    retry = api(volunteer2).post(f"{BASE}/deliver/", body, format="json")
    assert retry.status_code == 200 and retry.json()["id"] == first.json()["id"]
    other_key = api(volunteer2).post(
        f"{BASE}/deliver/", {**body, "client_uuid": str(uuid.uuid4())}, format="json"
    )
    assert other_key.status_code == 409 and other_key.json()["code"] == "already_delivered"


def test_deliver_with_photo(ready, volunteer2):
    from django.core.files.uploadedfile import SimpleUploadedFile

    photo = SimpleUploadedFile("proof.jpg", b"\xff\xd8\xff fake jpeg", content_type="image/jpeg")
    response = api(volunteer2).post(
        f"{BASE}/deliver/",
        {"entitlement": str(ready.id), "client_uuid": str(uuid.uuid4()), "proof": photo},
        format="multipart",
    )
    assert response.status_code == 201, response.json()
    assert Distribution.all_objects.get().proof.name.startswith("distributions/")


def test_future_delivery_time_is_refused(ready, volunteer2):
    body = {
        "entitlement": str(ready.id),
        "client_uuid": str(uuid.uuid4()),
        "delivered_at": "2099-01-01T10:00:00Z",
    }
    assert api(volunteer2).post(f"{BASE}/deliver/", body, format="json").status_code == 400


def test_lists_and_report_permissions(ready, volunteer, volunteer2, coordinator):
    services.deliver(entitlement=ready, user=volunteer2)
    assert api(volunteer2).get(f"{BASE}/").json()["count"] == 1
    assert api(volunteer).get(f"{BASE}/").json()["count"] == 0  # volunteers see their own deliveries
    assert api(coordinator).get(f"{BASE}/").json()["count"] == 1
    assert api(volunteer).get(f"{BASE}/report/", {"cycle": str(ready.cycle_id)}).status_code == 403
    report = api(coordinator).get(f"{BASE}/report/", {"cycle": str(ready.cycle_id)}).json()
    assert report["by_mohalla"][0]["delivered"] == 1


# --- Admin -----------------------------------------------------------------------------


def test_record_delivery_in_admin(ready, coordinator):
    client = Client()
    client.force_login(coordinator)
    assert client.get("/admin/distribution/distribution/").status_code == 200
    response = client.post(
        "/admin/distribution/distribution/add/", {"entitlement": ready.pk, "notes": "Fees paid"}
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    distribution = Distribution.all_objects.get()
    assert (distribution.delivered_by, distribution.notes) == (coordinator, "Fees paid")
    assert client.get(f"/admin/distribution/distribution/{distribution.pk}/change/").status_code == 200
