"""
Custom User model. Created on day one because Django makes it very hard to
switch to a custom user after the first migration.

People log in with their phone number, not a username or email.
"""

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel

from .phone import normalize_phone


class Role(models.TextChoices):
    """Role names. Each one is a Django Group created by a data migration."""

    PRESIDENT = "President"
    FINANCE_SECRETARY = "Finance Secretary"
    PROGRAM_COORDINATOR = "Program Coordinator"
    AUDITOR = "Auditor"
    VOLUNTEER = "Volunteer"
    BENEFICIARY = "Beneficiary"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, password, **extra):
        user = self.model(phone=normalize_phone(phone), **extra)
        user.set_password(password)  # stores a hash, never the password itself
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(phone, password, **extra)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    class Language(models.TextChoices):
        URDU = "ur", "اردو"
        ENGLISH = "en", "English"

    phone = models.CharField(max_length=16, unique=True, help_text="Format: +923001234567")
    name = models.CharField(max_length=150)
    society = models.ForeignKey(
        "societies.Society",
        null=True,
        blank=True,  # empty only for the technical super admin
        on_delete=models.PROTECT,
        related_name="users",
    )
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.URDU)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to the admin panel.")
    date_joined = models.DateTimeField(default=timezone.now)
    # 4-digit PIN for the mobile app (set after an SMS code). Stored hashed, like a password.
    pin_hash = models.CharField(max_length=128, blank=True, editable=False)
    pin_failed_attempts = models.PositiveSmallIntegerField(default=0, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.phone})"

    def clean(self):
        super().clean()
        if self.phone:
            self.phone = normalize_phone(self.phone)

    @property
    def roles(self) -> list[str]:
        return list(self.groups.values_list("name", flat=True))

    def has_role(self, role: Role) -> bool:
        return self.groups.filter(name=role).exists()

    def set_pin(self, pin: str) -> None:
        self.pin_hash = make_password(pin)
        self.pin_failed_attempts = 0

    def check_pin(self, pin: str) -> bool:
        return bool(self.pin_hash) and check_password(pin, self.pin_hash)


class OneTimeCode(UUIDModel, TimeStampedModel):
    """A 6-digit code sent by SMS. Only a keyed hash is stored, never the code itself."""

    phone = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Device(UUIDModel, TimeStampedModel):
    """
    A phone that logged in with a PIN. Volunteers' and office bearers' phones must be
    approved by the office; a lost phone can be blocked, which stops its login at once.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"
        BLOCKED = "blocked", "Blocked"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=100, help_text="Made by the app on first start.")
    name = models.CharField(max_length=100, blank=True, help_text="e.g. phone model")
    platform = models.CharField(max_length=10, blank=True)
    push_token = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen"]
        constraints = [models.UniqueConstraint(fields=["user", "device_id"], name="uniq_user_device")]

    def __str__(self) -> str:
        return f"{self.user.name} · {self.name or self.device_id[:8]}"
