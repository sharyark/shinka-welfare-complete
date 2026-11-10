"""
Programs: the kinds of help the society gives, and their rounds (cycles).

    Program  "Ramadan Food Package"   what is given, to whom, who is eligible
    Cycle    "Ramadan 2027"           one round: dates, budget, due date

Who actually gets what is in the benefits app (enrollments and entitlements).

Cycle lifecycle (changed only through apps/programs/services.py):

    draft ──activate──▶ active ──close──▶ closed
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TenantModel
from apps.finance.models import MONEY


class Program(TenantModel):
    class Kind(models.TextChoices):
        RECURRING = "recurring", "Recurring (e.g. school fees every term)"
        ANNUAL = "annual", "Once a year (e.g. Ramadan, Eid)"
        ONE_TIME = "one_time", "One time (e.g. marriage, water bore)"
        ON_DEMAND = "on_demand", "On demand (e.g. burial)"

    class Target(models.TextChoices):
        HOUSEHOLD = "household", "Per household"
        MEMBER = "member", "Per person (e.g. per student)"

    class Unit(models.TextChoices):
        CASH = "cash", "Cash (Rs)"
        PACKAGE = "package", "Package"
        KG = "kg", "Kilogram"
        SEAT = "seat", "Seat"
        ITEM = "item", "Item"

    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=100)
    name_ur = models.CharField("name (Urdu)", max_length=100, blank=True)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    target = models.CharField(max_length=10, choices=Target.choices, default=Target.HOUSEHOLD)
    unit = models.CharField(max_length=10, choices=Unit.choices)
    default_quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    default_amount = models.DecimalField(
        **MONEY,
        null=True,
        blank=True,
        help_text="Planned value in Rs of one benefit (cash, or cost of a package).",
    )
    fund = models.ForeignKey(
        "finance.Fund",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="The fund that pays for this program.",
    )
    requires_application = models.BooleanField(
        default=False,
        help_text="People must apply (e.g. marriage fund); not given automatically to a whole cycle.",
    )

    # Eligibility. Empty = no limit.
    min_need_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(100)],
        help_text="Households need an approved need score at least this high.",
    )
    member_min_age = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Per-person programs only."
    )
    member_max_age = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Per-person programs only."
    )
    member_gender = models.CharField(
        max_length=6,
        blank=True,
        choices=[("male", "Male only"), ("female", "Female only")],
        help_text="Per-person programs only (e.g. the girls' college bus).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["society", "code"], name="uniq_program_code"),
            models.CheckConstraint(condition=Q(default_quantity__gt=0), name="program_quantity_positive"),
            models.CheckConstraint(
                condition=Q(member_min_age__isnull=True)
                | Q(member_max_age__isnull=True)
                | Q(member_min_age__lte=F("member_max_age")),
                name="program_age_range_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        per_person = (self.member_min_age, self.member_max_age, self.member_gender)
        if self.target == self.Target.HOUSEHOLD and any(v not in (None, "") for v in per_person):
            raise ValidationError("Age and gender limits are only for per-person programs.")
        if self.fund_id and self.society_id and self.fund.society_id != self.society_id:
            raise ValidationError({"fund": "Choose a fund of this society."})


class Cycle(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="cycles")
    name = models.CharField(max_length=100, help_text='e.g. "Ramadan 2027" or "Term 1, 2027"')
    starts_on = models.DateField()
    ends_on = models.DateField()
    due_date = models.DateField(help_text="When the benefits are expected to be given.")
    budget = models.DecimalField(
        **MONEY,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Confirmed benefits can't add up to more than this. Empty = no limit.",
    )
    collection_point = models.CharField(max_length=150, blank=True, help_text="Where families collect.")
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.DRAFT, editable=False)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["program", "name"], name="uniq_cycle_name"),
            models.CheckConstraint(condition=Q(ends_on__gte=F("starts_on")), name="cycle_dates_in_order"),
        ]

    def __str__(self) -> str:
        return f"{self.program.name} · {self.name}"

    def clean(self):
        super().clean()
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "The cycle can't end before it starts."})
