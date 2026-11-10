import re
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import mobile_auth
from apps.accounts.models import Device, OneTimeCode, Role
from apps.accounts.sms import MemorySMS
from apps.core.exceptions import BusinessRuleError
from apps.core.testing import make_user

pytestmark = pytest.mark.django_db
AUTH = "/api/v1/auth"


@pytest.fixture(autouse=True)
def sms(settings):
    settings.SMS_BACKEND = "apps.accounts.sms.MemorySMS"
    MemorySMS.outbox.clear()
    return MemorySMS.outbox


@pytest.fixture
def family_user(society):
    return make_user(society, Role.BENEFICIARY, staff=False)


@pytest.fixture
def volunteer_user(society):
    return make_user(society, Role.VOLUNTEER, staff=False)


def last_code(sms) -> str:
    return re.search(r"\b(\d{6})\b", sms[-1][1]).group(1)


def full_setup(user, sms, pin="2580"):
    mobile_auth.request_code(user.phone)
    token = mobile_auth.verify_code(user.phone, last_code(sms))
    mobile_auth.set_pin(token, pin)


# --- SMS codes ---------------------------------------------------------------------


def test_code_is_sent_and_only_its_hash_is_stored(family_user, sms):
    mobile_auth.request_code("0" + family_user.phone[3:])  # typed as 0300…
    assert sms[0][0] == family_user.phone
    code = last_code(sms)
    stored = OneTimeCode.objects.get()
    assert code not in stored.code_hash


def test_unknown_number_gets_no_sms_and_no_error(sms):
    mobile_auth.request_code("03219999999")
    assert sms == []


def test_wrong_code_counts_attempts_then_locks(family_user, sms, settings):
    mobile_auth.request_code(family_user.phone)
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        with pytest.raises(BusinessRuleError):
            mobile_auth.verify_code(family_user.phone, "000000")
    with pytest.raises(BusinessRuleError):
        mobile_auth.verify_code(family_user.phone, last_code(sms))  # right code, but too many tries


def test_expired_code_is_refused(family_user, sms):
    mobile_auth.request_code(family_user.phone)
    OneTimeCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(BusinessRuleError, match="expired"):
        mobile_auth.verify_code(family_user.phone, last_code(sms))


def test_a_code_works_once_and_a_new_code_replaces_the_old(family_user, sms):
    mobile_auth.request_code(family_user.phone)
    first = last_code(sms)
    mobile_auth.request_code(family_user.phone)
    with pytest.raises(BusinessRuleError):
        mobile_auth.verify_code(family_user.phone, first)
    second = last_code(sms)
    mobile_auth.verify_code(family_user.phone, second)
    with pytest.raises(BusinessRuleError):
        mobile_auth.verify_code(family_user.phone, second)


def test_only_a_few_codes_per_15_minutes(family_user, sms, settings):
    for _ in range(settings.OTP_MAX_PER_15_MIN + 2):
        mobile_auth.request_code(family_user.phone)
    assert len(sms) == settings.OTP_MAX_PER_15_MIN


# --- PIN ----------------------------------------------------------------------------


def test_weak_or_badly_formed_pins_are_refused(family_user, sms):
    mobile_auth.request_code(family_user.phone)
    token = mobile_auth.verify_code(family_user.phone, last_code(sms))
    for pin in ("1234", "0000", "12a4", "123"):
        with pytest.raises(BusinessRuleError):
            mobile_auth.set_pin(token, pin)
    mobile_auth.set_pin(token, "2580")
    family_user.refresh_from_db()
    assert family_user.check_pin("2580") and "2580" not in family_user.pin_hash


def test_forged_pin_token_is_refused():
    with pytest.raises(BusinessRuleError):
        mobile_auth.set_pin("not-a-real-token", "2580")


def test_family_logs_in_and_phone_is_approved_automatically(family_user, sms):
    full_setup(family_user, sms)
    tokens = mobile_auth.pin_login(family_user.phone, "2580", device_id="phone-1", platform="android")
    assert set(tokens) == {"access", "refresh"}
    assert Device.objects.get().status == Device.Status.APPROVED


def test_wrong_pin_is_vague_and_locks_after_too_many(family_user, sms, settings):
    full_setup(family_user, sms)
    for _ in range(settings.PIN_MAX_ATTEMPTS):
        with pytest.raises(BusinessRuleError) as exc:
            mobile_auth.pin_login(family_user.phone, "9876", device_id="d")
        assert exc.value.code == "bad_pin"
    with pytest.raises(BusinessRuleError) as exc:
        mobile_auth.pin_login(family_user.phone, "2580", device_id="d")
    assert exc.value.code == "pin_locked"
    full_setup(family_user, sms, pin="3691")  # a new SMS code unlocks
    mobile_auth.pin_login(family_user.phone, "3691", device_id="d")


def test_unknown_phone_gets_the_same_error_as_wrong_pin():
    with pytest.raises(BusinessRuleError) as exc:
        mobile_auth.pin_login("03219999999", "2580", device_id="d")
    assert exc.value.code == "bad_pin"


# --- Devices ------------------------------------------------------------------------


def test_volunteer_phone_needs_approval_then_can_be_blocked(volunteer_user, sms, society):
    full_setup(volunteer_user, sms)
    with pytest.raises(BusinessRuleError) as exc:
        mobile_auth.pin_login(volunteer_user.phone, "2580", device_id="vol-phone")
    assert exc.value.code == "device_pending"

    coordinator = make_user(society, Role.PROGRAM_COORDINATOR)
    device = Device.objects.get()
    mobile_auth.approve_device(device, coordinator)
    tokens = mobile_auth.pin_login(volunteer_user.phone, "2580", device_id="vol-phone")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.get("/api/v1/me/").status_code == 200
    mobile_auth.block_device(device, coordinator)
    assert client.get("/api/v1/me/").status_code == 401  # the same token stops working at once
    refresh = APIClient().post(f"{AUTH}/token/refresh/", {"refresh": tokens["refresh"]})
    assert refresh.status_code == 401
    with pytest.raises(BusinessRuleError) as exc:
        mobile_auth.pin_login(volunteer_user.phone, "2580", device_id="vol-phone")
    assert exc.value.code == "device_blocked"


def test_only_president_or_coordinator_manage_phones(volunteer_user, sms, society):
    from django.core.exceptions import PermissionDenied

    full_setup(volunteer_user, sms)
    with pytest.raises(BusinessRuleError):
        mobile_auth.pin_login(volunteer_user.phone, "2580", device_id="x")
    with pytest.raises(PermissionDenied):
        mobile_auth.approve_device(Device.objects.get(), make_user(society, Role.FINANCE_SECRETARY))


# --- The whole flow through the API ----------------------------------------------------


def test_api_flow(family_user, sms):
    client = APIClient()
    asked = client.post(f"{AUTH}/otp/request/", {"phone": family_user.phone})
    unknown = client.post(f"{AUTH}/otp/request/", {"phone": "03219999999"})
    assert asked.json() == unknown.json()  # same answer either way
    token = client.post(f"{AUTH}/otp/verify/", {"phone": family_user.phone, "code": last_code(sms)}).json()
    assert (
        client.post(f"{AUTH}/pin/set/", {"pin_token": token["pin_token"], "pin": "2580"}).status_code == 200
    )
    login = client.post(
        f"{AUTH}/pin/login/",
        {"phone": family_user.phone, "pin": "2580", "device_id": "abc", "platform": "android"},
    )
    assert login.status_code == 200, login.json()
    bad = client.post(f"{AUTH}/pin/login/", {"phone": family_user.phone, "pin": "1111", "device_id": "abc"})
    assert bad.status_code == 409 and bad.json()["code"] == "bad_pin"


def test_device_admin(volunteer_user, sms, society):
    from django.test import Client

    full_setup(volunteer_user, sms)
    with pytest.raises(BusinessRuleError):
        mobile_auth.pin_login(volunteer_user.phone, "2580", device_id="x")
    president = make_user(society, Role.PRESIDENT)
    client = Client()
    client.force_login(president)
    assert client.get("/admin/accounts/device/").status_code == 200
    device = Device.objects.get()
    client.post("/admin/accounts/device/", {"action": "approve", "_selected_action": [device.pk]})
    device.refresh_from_db()
    assert device.status == Device.Status.APPROVED
