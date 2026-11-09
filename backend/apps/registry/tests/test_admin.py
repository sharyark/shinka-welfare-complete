import pytest
from django.test import Client

from apps.registry.models import Household, Member

pytestmark = pytest.mark.django_db
ADMIN = "/admin/registry"


def admin_client(user):
    client = Client()
    client.force_login(user)
    return client


def member_rows(*members, initial=0):
    """The POST data Django's admin sends for the members inline."""
    data = {
        "members-TOTAL_FORMS": str(len(members)),
        "members-INITIAL_FORMS": str(initial),
        "members-MIN_NUM_FORMS": "0",
        "members-MAX_NUM_FORMS": "1000",
    }
    for i, member in enumerate(members):
        for key, value in member.items():
            data[f"members-{i}-{key}"] = value
    return data


HEAD = {"full_name": "Rashid Khan", "relation": "head", "gender": "male", "cnic": "37101-1234567-3"}
DAUGHTER = {"full_name": "Ayesha", "relation": "daughter", "gender": "female", "cnic": ""}


def household_post(mohalla, *members, consent="on"):
    return {"mohalla": mohalla.id, "phone": "0300-1112223", "consent": consent, **member_rows(*members)}


@pytest.mark.parametrize("path", ["household/", "household/add/", "mohalla/", "mohalla/add/"])
def test_coordinator_can_open_pages(coordinator, mohalla, path):
    assert admin_client(coordinator).get(f"{ADMIN}/{path}").status_code == 200


def test_auditor_cannot_see_households(society):
    from apps.core.testing import make_user

    assert admin_client(make_user(society, "Auditor")).get(f"{ADMIN}/household/").status_code == 403


def test_add_household_with_members(coordinator, mohalla, society):
    response = admin_client(coordinator).post(
        f"{ADMIN}/household/add/", household_post(mohalla, HEAD, DAUGHTER)
    )
    assert response.status_code == 302, response.content.decode()[:3000]
    household = Household.all_objects.get()
    assert (household.code, household.society, household.registered_by) == ("SHK-0001", society, coordinator)
    assert household.phone == "+923001112223"
    head = household.members.get(relation="head")
    assert head.cnic_masked == "37101-*****-3"
    assert head.society == society


def test_consent_and_one_head_are_required(coordinator, mohalla):
    client = admin_client(coordinator)
    no_consent = client.post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD, consent=""))
    assert b"must agree" in no_consent.content
    two_heads = client.post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD, {**HEAD, "cnic": ""}))
    assert b"exactly one head" in two_heads.content
    assert not Household.all_objects.exists()


def test_bad_and_duplicate_cnic_show_errors(coordinator, mohalla):
    client = admin_client(coordinator)
    bad = client.post(f"{ADMIN}/household/add/", household_post(mohalla, {**HEAD, "cnic": "123"}))
    assert b"not a valid CNIC" in bad.content
    client.post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD))
    duplicate = client.post(f"{ADMIN}/household/add/", household_post(mohalla, {**HEAD, "full_name": "Copy"}))
    assert b"already registered" in duplicate.content
    assert Household.all_objects.count() == 1


def test_swap_head_in_one_save(coordinator, mohalla):
    client = admin_client(coordinator)
    client.post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD, DAUGHTER))
    household = Household.all_objects.get()
    head, daughter = household.members.get(relation="head"), household.members.get(relation="daughter")
    data = {
        "mohalla": mohalla.id,
        "phone": "0300-1112223",
        **member_rows(
            {"id": head.pk, "household": household.pk, **HEAD, "cnic": "", "relation": "father"},
            {"id": daughter.pk, "household": household.pk, **DAUGHTER, "relation": "head"},
            initial=2,
        ),
    }
    response = client.post(f"{ADMIN}/household/{household.pk}/change/", data)
    assert response.status_code == 302, response.content.decode()[:3000]
    assert Member.all_objects.get(relation="head").full_name == "Ayesha"
    head.refresh_from_db()
    assert head.cnic_masked == "37101-*****-3"  # empty CNIC box = unchanged


def test_verify_action_respects_maker_checker(coordinator, president, mohalla):
    admin_client(coordinator).post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD))
    household = Household.all_objects.get()

    admin_client(coordinator).post(
        f"{ADMIN}/household/", {"action": "verify", "_selected_action": [household.pk]}
    )
    household.refresh_from_db()
    assert household.status == "pending"

    admin_client(president).post(
        f"{ADMIN}/household/", {"action": "verify", "_selected_action": [household.pk]}
    )
    household.refresh_from_db()
    assert household.status == "verified"


def test_search_by_cnic_in_admin(coordinator, mohalla):
    client = admin_client(coordinator)
    client.post(f"{ADMIN}/household/add/", household_post(mohalla, HEAD))
    page = client.get(f"{ADMIN}/household/", {"q": "3710112345673"})
    assert b"SHK-0001" in page.content
    assert b"1234567" not in page.content.replace(b"3710112345673", b"")  # only the search box echo
