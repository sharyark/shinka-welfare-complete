"""
Registry: the households the society helps, and the people in them.

Aid is given to households (architecture principle 2: "household first").
Every household is registered once and reused by every program.

Household lifecycle (changed only through apps/registry/services.py):

    pending ──verify──▶ verified ──archive──▶ archived
       │
       └──reject──▶ rejected ──reopen──▶ pending
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.phone import normalize_phone
from apps.core.models import TenantModel


class Mohalla(TenantModel):
    """A neighbourhood of the village. Used to split work between volunteers and in reports."""

    name = models.CharField(max_length=100)
    name_ur = models.CharField("name (Urdu)", max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "mohallas"
        constraints = [models.UniqueConstraint(fields=["society", "name"], name="uniq_mohalla_name")]

    def __str__(self) -> str:
        return self.name


class HouseholdCounter(TenantModel):
    """Next household number per society (SHK-0001, SHK-0002…). Locked while incremented."""

    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["society"], name="uniq_household_counter")]


class Household(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    code = models.CharField(max_length=20, editable=False, help_text="Given automatically, e.g. SHK-0421.")
    mohalla = models.ForeignKey(Mohalla, on_delete=models.PROTECT, related_name="households")
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=16, blank=True, help_text="Main contact number.")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, editable=False)
    consent_given_at = models.DateTimeField(
        editable=False, help_text="When the family agreed to their data (and photos) being recorded."
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.CharField(max_length=255, blank=True, editable=False)
    notes = models.TextField(blank=True)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="households",
        help_text="App accounts that may see this household (e.g. the head, a son abroad).",
    )

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["society", "code"], name="uniq_household_code")]

    def __str__(self) -> str:
        return self.code or "New household"

    def clean(self):
        super().clean()
        if self.phone:
            self.phone = normalize_phone(self.phone)


class Member(TenantModel):
    class Relation(models.TextChoices):
        HEAD = "head", "Head of household"
        SPOUSE = "spouse", "Wife / husband"
        SON = "son", "Son"
        DAUGHTER = "daughter", "Daughter"
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        BROTHER = "brother", "Brother"
        SISTER = "sister", "Sister"
        GRANDCHILD = "grandchild", "Grandchild"
        OTHER = "other", "Other relative"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class Education(models.TextChoices):
        NONE = "none", "None"
        PRIMARY = "primary", "Primary (1–5)"
        MIDDLE = "middle", "Middle (6–8)"
        MATRIC = "matric", "Matric"
        INTERMEDIATE = "intermediate", "Intermediate"
        GRADUATE = "graduate", "Graduate or higher"
        MADRASSA = "madrassa", "Madrassa"

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="members")
    full_name = models.CharField(max_length=150)
    father_or_husband_name = models.CharField(max_length=150, blank=True)
    relation = models.CharField(max_length=12, choices=Relation.choices)
    gender = models.CharField(max_length=6, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)

    # CNIC / B-form: see cnic.py. Never stored in plain text.
    cnic_encrypted = models.TextField(blank=True, editable=False)
    cnic_hash = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    cnic_masked = models.CharField("CNIC", max_length=15, blank=True, editable=False)

    is_earning = models.BooleanField("earns an income", default=False)
    occupation = models.CharField(max_length=100, blank=True)
    is_disabled = models.BooleanField("has a disability", default=False)
    is_orphan = models.BooleanField(default=False)
    is_widow = models.BooleanField("is a widow", default=False)
    education_level = models.CharField(max_length=12, choices=Education.choices, blank=True)
    school = models.CharField("school / college", max_length=150, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # The database itself refuses a second head or a CNIC registered twice.
            models.UniqueConstraint(
                fields=["household"], condition=Q(relation="head"), name="one_head_per_household"
            ),
            models.UniqueConstraint(
                fields=["society", "cnic_hash"], condition=~Q(cnic_hash=""), name="uniq_member_cnic"
            ),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
