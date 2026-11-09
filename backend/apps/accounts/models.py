"""
Custom User model. Created on day one because Django makes it very hard to
switch to a custom user after the first migration.

People log in with their phone number, not a username or email.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel

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
