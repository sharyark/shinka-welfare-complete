"""
Applications: a family asks for help from a program that needs applying for
(marriage fund, water bore, burial). Architecture section 10.2.

    submitted ──visit──▶ under review ──approve──▶ approved  (creates enrollment + confirmed entitlement)
        │                     │
        │                     └──reject──▶ rejected
        ├──(urgent: approve or reject directly, e.g. burial)
        └──withdraw──▶ withdrawn   (also from under review)

These cases are private (architecture 14): only the committee, the volunteers
of that household and the family itself see them. Every change is kept
(django-simple-history).
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.core.models import TenantModel
from apps.finance.models import MONEY, UPLOAD_TYPES


class Application(TenantModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review (visited)"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Urgency(models.TextChoices):
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgent (e.g. burial): may be decided without a home visit"

    class Channel(models.TextChoices):
        APP = "app", "Family, in the app"
        VOLUNTEER = "volunteer", "Through a volunteer"
        OFFICE = "office", "At the office"

    household = models.ForeignKey("registry.Household", on_delete=models.PROTECT, related_name="applications")
    program = models.ForeignKey("programs.Program", on_delete=models.PROTECT, related_name="applications")
    member = models.ForeignKey(
        "registry.Member",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Who it is for, if one person (e.g. the bride).",
    )
    description = models.TextField(help_text="What is needed and why.")
    amount_requested = models.DecimalField(**MONEY, null=True, blank=True, validators=[MinValueValidator(0)])
    needed_by = models.DateField(null=True, blank=True, help_text="e.g. the wedding date.")
    urgency = models.CharField(max_length=6, choices=Urgency.choices, default=Urgency.NORMAL)
    document = models.FileField(
        upload_to="applications/%Y/%m/",
        blank=True,
        validators=[UPLOAD_TYPES],
        help_text="e.g. a death certificate.",
    )
    channel = models.CharField(max_length=10, choices=Channel.choices, editable=False)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED, editable=False)

    visited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    visited_at = models.DateTimeField(null=True, blank=True, editable=False)
    visit_report = models.TextField(blank=True, editable=False)

    # Filled in by the committee before approving (proposals until then).
    approved_amount = models.DecimalField(
        **MONEY, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Set before approving."
    )
    due_date = models.DateField(
        null=True, blank=True, help_text="When the help will be given. Set before approving."
    )

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.CharField(max_length=255, blank=True, editable=False)
    entitlement = models.OneToOneField(
        "benefits.Entitlement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="application",
        editable=False,
    )

    history = HistoricalRecords(excluded_fields=["created_by"])

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One open application per family (or person) per program.
            models.UniqueConstraint(
                fields=["household", "program"],
                condition=Q(status__in=["submitted", "under_review"], member__isnull=True),
                name="one_open_household_application",
            ),
            models.UniqueConstraint(
                fields=["member", "program"],
                condition=Q(status__in=["submitted", "under_review"], member__isnull=False),
                name="one_open_member_application",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.program} · {self.household}"
