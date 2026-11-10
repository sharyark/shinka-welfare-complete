"""
Mobile app login (architecture section 13): SMS code once, then a 4-digit PIN.

    1. request_code(phone)         an SMS code is sent (if the number has an account)
    2. verify_code(phone, code)    → a short-lived "set PIN" token
    3. set_pin(token, pin)
    4. pin_login(phone, pin, device)  → JWT tokens tied to this phone (device)

Safety rules:
- The answers never reveal whether a phone number has an account.
- Codes expire after a few minutes, allow a few tries, and only a few are sent
  per phone per 15 minutes. Only a keyed hash of each code is stored.
- After too many wrong PINs, the PIN is locked until a new SMS code is verified.
- Volunteers' and office bearers' phones must be approved by the office before
  they can log in; families' phones are approved automatically. A blocked phone
  is refused on every request (see authentication.py).
"""

import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.crypto import keyed_hash
from apps.core.exceptions import BusinessRuleError

from .models import Device, OneTimeCode, Role, User
from .phone import normalize_phone
from .roles import has_any_role, require_role
from .sms import send_sms

PIN_TOKEN_SALT = "accounts.set-pin"  # noqa: S105  (a signing namespace, not a secret)
PIN_TOKEN_MAX_AGE = 10 * 60
WEAK_PINS = {"0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999", "1234", "4321"}
APPROVAL_ROLES = (
    Role.PRESIDENT,
    Role.FINANCE_SECRETARY,
    Role.PROGRAM_COORDINATOR,
    Role.VOLUNTEER,
    Role.AUDITOR,
)
DEVICE_MANAGERS = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR)


def _active_user(phone: str) -> User | None:
    return User.objects.filter(phone=phone, is_active=True).first()


def _code_hash(phone: str, code: str) -> str:
    return keyed_hash(f"otp:{phone}:{code}")


# --- SMS codes -----------------------------------------------------------------------


@transaction.atomic
def request_code(raw_phone: str) -> None:
    """Send a code if the number has an account. Says nothing either way (no account fishing)."""
    phone = normalize_phone(raw_phone)
    user = _active_user(phone)
    if user is None:
        return
    since = timezone.now() - timedelta(minutes=15)
    if OneTimeCode.objects.filter(phone=phone, created_at__gte=since).count() >= settings.OTP_MAX_PER_15_MIN:
        return  # too many codes recently; quietly don't send another
    OneTimeCode.objects.filter(phone=phone, used_at__isnull=True).update(
        used_at=timezone.now()
    )  # old codes die
    code = f"{secrets.randbelow(1_000_000):06d}"
    OneTimeCode.objects.create(
        phone=phone,
        code_hash=_code_hash(phone, code),
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_VALID_MINUTES),
    )
    send_sms(
        phone, f"Shinka Welfare code: {code}. Valid {settings.OTP_VALID_MINUTES} minutes. Don't share it."
    )


def verify_code(raw_phone: str, code: str) -> str:
    """Check the code; returns a token that allows setting a PIN for the next 10 minutes."""
    phone = normalize_phone(raw_phone)
    # The attempt counter must be SAVED even when the code is wrong, so decide inside the
    # transaction and raise only after it has committed (raising inside would undo the count).
    with transaction.atomic():
        otp = OneTimeCode.objects.select_for_update().filter(phone=phone, used_at__isnull=True).first()
        usable = (
            otp is not None and otp.expires_at >= timezone.now() and otp.attempts < settings.OTP_MAX_ATTEMPTS
        )
        correct = usable and hmac.compare_digest(otp.code_hash, _code_hash(phone, (code or "").strip()))
        if usable and not correct:
            otp.attempts += 1
            otp.save(update_fields=["attempts", "updated_at"])
        elif correct:
            otp.used_at = timezone.now()
            otp.save(update_fields=["used_at", "updated_at"])
    user = _active_user(phone) if correct else None
    if user is None:
        raise BusinessRuleError("The code is wrong or has expired. Ask for a new one.", code="bad_code")
    return signing.dumps({"u": str(user.pk)}, salt=PIN_TOKEN_SALT)


def check_pin_strength(pin: str) -> None:
    if not (len(pin) == 4 and pin.isdigit()):
        raise BusinessRuleError("The PIN must be exactly 4 digits.", code="weak_pin")
    if pin in WEAK_PINS:
        raise BusinessRuleError("That PIN is too easy to guess. Choose another.", code="weak_pin")


def set_pin(pin_token: str, pin: str) -> User:
    try:
        data = signing.loads(pin_token, salt=PIN_TOKEN_SALT, max_age=PIN_TOKEN_MAX_AGE)
    except signing.BadSignature as exc:  # also raised when expired
        raise BusinessRuleError("This step has expired. Ask for a new SMS code.", code="bad_token") from exc
    check_pin_strength(pin)
    user = User.objects.get(pk=data["u"], is_active=True)
    user.set_pin(pin)  # also clears a PIN lock
    user.save(update_fields=["pin_hash", "pin_failed_attempts"])
    return user


# --- PIN login and devices ------------------------------------------------------------


def tokens_for(user: User, device: Device) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["device"] = str(device.pk)  # copied into every access token made from it
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def pin_login(raw_phone: str, pin: str, *, device_id: str, name: str = "", platform: str = "", push_token=""):
    """Returns JWT tokens. The device must be approved (automatic for families)."""
    try:
        phone = normalize_phone(raw_phone)
    except Exception:
        phone = None
    # As in verify_code: counters and the new device row must be saved even when login
    # fails, so the outcome is decided inside the transaction and raised after it.
    with transaction.atomic():
        user = User.objects.select_for_update().filter(phone=phone, is_active=True).first() if phone else None
        outcome = _pin_outcome(user, pin)
        device = None
        if outcome == "ok":
            device = _register_device(user, device_id, name=name, platform=platform, push_token=push_token)
    if outcome == "locked":
        raise BusinessRuleError("Too many wrong PINs. Log in with a new SMS code.", code="pin_locked")
    if outcome == "wrong":
        raise BusinessRuleError("Wrong phone number or PIN.", code="bad_pin")
    if device.status == Device.Status.BLOCKED:
        raise BusinessRuleError(
            "This phone has been blocked. Contact the society office.", code="device_blocked"
        )
    if device.status == Device.Status.PENDING:
        raise BusinessRuleError(
            "This phone must be approved by the society office before you can use it.", code="device_pending"
        )
    return tokens_for(user, device)


def _pin_outcome(user: User | None, pin: str) -> str:
    """'ok', 'wrong' or 'locked'. Saves the failed-attempt counter. Call with the user row locked."""
    if user is None or not user.pin_hash:
        return "wrong"
    if user.pin_failed_attempts >= settings.PIN_MAX_ATTEMPTS:
        return "locked"
    if not user.check_pin(pin):
        user.pin_failed_attempts += 1
        user.save(update_fields=["pin_failed_attempts"])
        return "wrong"
    user.pin_failed_attempts = 0
    user.last_login = timezone.now()
    user.save(update_fields=["pin_failed_attempts", "last_login"])
    return "ok"


def _register_device(user: User, device_id: str, **info) -> Device:
    needs_approval = has_any_role(user, *APPROVAL_ROLES)
    device, _ = Device.objects.get_or_create(
        user=user,
        device_id=device_id,
        defaults={"status": Device.Status.PENDING if needs_approval else Device.Status.APPROVED},
    )
    device.name = info["name"] or device.name
    device.platform = info["platform"] or device.platform
    device.push_token = info["push_token"] or device.push_token
    device.last_seen = timezone.now()
    device.save()
    return device


def _check_manager(user) -> None:
    if not user.is_superuser:
        require_role(user, *DEVICE_MANAGERS, action="approve or block phones")


def approve_device(device: Device, user) -> Device:
    _check_manager(user)
    device.status = Device.Status.APPROVED
    device.approved_by = user
    device.save(update_fields=["status", "approved_by", "updated_at"])
    return device


def block_device(device: Device, user) -> Device:
    """A lost or stolen phone: its tokens stop working immediately."""
    _check_manager(user)
    device.status = Device.Status.BLOCKED
    device.save(update_fields=["status", "updated_at"])
    return device
