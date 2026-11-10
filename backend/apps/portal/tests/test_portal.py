import json

import pytest
from rest_framework.test import APIClient

from apps.distribution import services as distribution
from apps.registry.qr import household_from_qr

pytestmark = pytest.mark.django_db
ME = "/api/v1/me"


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def family(ready, beneficiary):
    """The beneficiary's household has one Ramadan package ready to collect."""
    ready.enrollment.household.users.add(beneficiary)
    return ready.enrollment.household


def test_account_without_household_gets_404(beneficiary):
    assert api(beneficiary).get(f"{ME}/household/").status_code == 404


def test_my_household_shows_members_but_no_need_score(family, beneficiary):
    body = api(beneficiary).get(f"{ME}/household/").json()
    assert body["code"] == "SHK-0001"
    assert [m["full_name"] for m in body["members"]] == ["Rashid Khan", "Ayesha"]
    assert "score" not in json.dumps(body)


def test_summary_upcoming_then_received(family, beneficiary, volunteer2):
    before = api(beneficiary).get(f"{ME}/summary/").json()
    assert before["received"]["items"] == []
    assert before["upcoming"][0]["status"] == "ready"
    assert before["upcoming"][0]["label_ur"] == "وصولی کے لیے تیار"

    distribution.deliver(entitlement=family.enrollments.get().entitlements.get(), user=volunteer2)
    after = api(beneficiary).get(f"{ME}/summary/").json()
    assert after["upcoming"] == []
    assert after["received"]["items"][0]["program"] == "Ramadan Food Package"
    assert after["received"]["items"][0]["count"] == 1
    assert after["received"]["total_cash_pkr"] == "0.00"  # a package, not cash


def test_planned_benefit_is_labelled_as_not_a_promise(
    scored, make_program, make_cycle, coordinator, beneficiary
):
    from apps.benefits import services as benefits

    household = scored()
    household.users.add(beneficiary)
    benefits.generate_cycle(make_cycle(make_program()), coordinator)
    upcoming = api(beneficiary).get(f"{ME}/summary/").json()["upcoming"][0]
    assert upcoming["label"] == "Expected — depends on available funds"


def test_qr_card_token_identifies_the_family(family, beneficiary, society):
    body = api(beneficiary).get(f"{ME}/qr/").json()
    assert household_from_qr(body["qr_token"], society.pk) == family


def test_a_family_only_ever_sees_itself(family, scored, beneficiary, society):
    from apps.accounts.models import Role
    from apps.core.testing import make_user

    from .conftest import head

    other_user = make_user(society, Role.BENEFICIARY, staff=False)
    scored(members=[head(name="Other family", cnic="")]).users.add(other_user)
    assert api(other_user).get(f"{ME}/household/").json()["code"] == "SHK-0002"
    assert api(other_user).get(f"{ME}/summary/").json()["upcoming"] == []
